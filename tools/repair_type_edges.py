"""
Repair the `type` collection in the live multi-tenant-blueprint database.

Two distinct issues are addressed:

  1. Misrouted software classifications: a pre-existing generator bug placed
     `_from = Device/<...:software*>` for every Software classification.
     This script rewrites each such edge with `_from = Software/<key>`
     and `_fromType = "Software"` *if and only if* the target Software
     document still exists. SmartGraph edges encode `_from`/`_to` into
     `_key`, so we delete-and-reinsert rather than UPDATE.

  2. Orphan classifications: the generator currently emits a `type` edge
     for every version of every device/software, including historical
     versions that subsequently get TTL-aged out. Their `type` edges then
     point to a non-existent vertex. We delete those.

The script is idempotent and read-driven (it discovers what needs doing
each time, so re-running on a clean collection is a no-op).

Follow-up (not done here): the generator should anchor `type` edges at the
proxy (`DeviceProxyOut` / `SoftwareProxyOut`), not at the versioned
entity, so a classification survives version churn. That requires
extending the SmartGraph `type` edge definition to allow proxy
collections as `from_vertex_collections`. Recommend tracking separately.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arango import ArangoClient
from arango.database import StandardDatabase

from src.config.centralized_credentials import CredentialsManager

logger = logging.getLogger("type-repair")


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


DIAGNOSTIC_AQL = """
FOR e IN type
  LET fromKey = SPLIT(e._from, "/")[1]
  LET tail = SPLIT(fromKey, ":")[1]
  LET kind = LIKE(tail, "software%") ? "software"
           : LIKE(tail, "device%")   ? "device"
           : "other"
  LET liveDevice   = DOCUMENT("Device", fromKey)   != null
  LET liveSoftware = DOCUMENT("Software", fromKey) != null
  COLLECT k = kind, ld = liveDevice, ls = liveSoftware WITH COUNT INTO n
  RETURN { kind: k, liveDevice: ld, liveSoftware: ls, count: n }
"""


def diagnose(db: StandardDatabase) -> List[Dict[str, Any]]:
    rows = list(db.aql.execute(DIAGNOSTIC_AQL))
    logger.info("type-collection census:")
    for r in rows:
        logger.info("  %s", r)
    return rows


# ---------------------------------------------------------------------------
# Repair queries
#
# We keep the work in two AQL passes so each is restartable on its own.
# The COLLECT-WITH-COUNT idiom returns a single integer summary even when
# the FOR loop performs writes.
# ---------------------------------------------------------------------------


# Pass 1 -- collect (then delete) the candidate edges to reroute.
# AQL forbids read-then-write-then-write to the same collection in a single
# query ("access after data-modification"), so we materialize the list
# first via a pure-read query, then drive delete+insert from Python.
SELECT_REROUTE_AQL = """
FOR e IN type
  LET fromKey = SPLIT(e._from, "/")[1]
  LET tail = SPLIT(fromKey, ":")[1]
  FILTER LIKE(tail, "software%")
  FILTER DOCUMENT("Software", fromKey) != null
  RETURN e
"""


# Pass 2 -- collect (then delete) orphan edges.
SELECT_ORPHANS_AQL = """
FOR e IN type
  LET fromKey = SPLIT(e._from, "/")[1]
  LET inDevice   = DOCUMENT("Device", fromKey)   != null
  LET inSoftware = DOCUMENT("Software", fromKey) != null
  FILTER NOT inDevice AND NOT inSoftware
  RETURN e._key
"""


CHUNK = 500


def _chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def reroute_software_edges(db: StandardDatabase) -> int:
    """Delete-and-reinsert misrouted software type-edges with corrected
    `_from` and `_fromType`. Same `_key` keeps the edge on the same
    SmartGraph shard (tenantId prefix is unchanged)."""
    coll = db.collection("type")
    candidates: List[Dict[str, Any]] = list(db.aql.execute(SELECT_REROUTE_AQL))
    logger.info("  selected %d candidates", len(candidates))
    if not candidates:
        return 0

    rerouted = 0
    for batch in _chunked(candidates, CHUNK):
        keys = [e["_key"] for e in batch]
        coll.delete_many([{"_key": k} for k in keys])
        corrected = []
        for e in batch:
            from_key = e["_from"].split("/", 1)[1]
            new_doc = {k: v for k, v in e.items() if k not in ("_id", "_rev")}
            new_doc["_from"] = f"Software/{from_key}"
            new_doc["_fromType"] = "Software"
            corrected.append(new_doc)
        coll.insert_many(corrected)
        rerouted += len(batch)
    return rerouted


def delete_orphan_edges(db: StandardDatabase) -> int:
    """Delete type-edges whose `_from` resolves to nothing in either
    `Device` or `Software`."""
    coll = db.collection("type")
    keys: List[str] = list(db.aql.execute(SELECT_ORPHANS_AQL))
    logger.info("  selected %d orphan keys", len(keys))
    if not keys:
        return 0

    deleted = 0
    for batch in _chunked(keys, CHUNK):
        coll.delete_many([{"_key": k} for k in batch])
        deleted += len(batch)
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Diagnose only, do not modify the database")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    creds = CredentialsManager.get_database_credentials()
    client = ArangoClient(hosts=creds.endpoint)
    db = client.db(creds.database_name, **CredentialsManager.get_database_params())
    type_coll = db.collection("type")

    logger.info("Endpoint: %s", creds.endpoint)
    logger.info("Database: %s", creds.database_name)
    logger.info("Mode:     %s", "DRY-RUN" if args.dry_run else "APPLY")

    logger.info("\n[1/4] Diagnose")
    before_total = type_coll.count()
    logger.info("type collection size: %d", before_total)
    rows_before = diagnose(db)

    misrouted_live = sum(
        r["count"] for r in rows_before
        if r["kind"] == "software" and r["liveSoftware"]
    )
    orphans = sum(
        r["count"] for r in rows_before
        if not r["liveDevice"] and not r["liveSoftware"]
    )
    correct_live = sum(
        r["count"] for r in rows_before
        if r["kind"] == "device" and r["liveDevice"]
    )

    logger.info("\nplanned operations:")
    logger.info("  reroute (software, target live): %d", misrouted_live)
    logger.info("  delete  (orphan):                %d", orphans)
    logger.info("  leave   (device, target live):   %d", correct_live)

    if args.dry_run:
        logger.info("\n[DRY-RUN] no changes applied")
        return 0

    logger.info("\n[2/4] Reroute software classifications")
    rerouted = reroute_software_edges(db)
    logger.info("  rerouted: %d", rerouted)

    logger.info("\n[3/4] Delete orphan classifications")
    deleted = delete_orphan_edges(db)
    logger.info("  deleted: %d", deleted)

    logger.info("\n[4/4] Re-diagnose")
    after_total = type_coll.count()
    logger.info("type collection size: %d -> %d", before_total, after_total)
    diagnose(db)

    expected_after = correct_live + misrouted_live
    if after_total == expected_after:
        logger.info("\n[OK] type collection now has only live, correctly-routed classifications")
    else:
        logger.warning("\n[WARN] expected %d rows, got %d -- inspect manually",
                       expected_after, after_total)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
