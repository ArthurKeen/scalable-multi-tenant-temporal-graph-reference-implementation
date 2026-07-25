"""
Migrate the live ``type`` edge collection from versioned-entity anchoring
to proxy anchoring.

Before:
    type._from = Device/<tenant>:device<i>-<v>
    type._fromType = "Device"
              -- or --
    type._from = Software/<tenant>:software<i>-<v>
    type._fromType = "Software"

After:
    type._from = DeviceProxyOut/<tenant>:device<i>
    type._fromType = "DeviceProxyOut"
              -- or --
    type._from = SoftwareProxyOut/<tenant>:software<i>
    type._fromType = "SoftwareProxyOut"

Why: anchoring at the proxy makes a classification stable across version
churn. A configuration change does not reclassify the device; a
historical-version TTL aging does not orphan the type-edge. See
`docs/MULTI_TENANT_PATTERNS.md` for the full rationale.

Order of operations:
  1. Broaden the SmartGraph `type` edge definition to allow both legacy
     (Device, Software) AND new (DeviceProxyOut, SoftwareProxyOut)
     `from_vertex_collections`. This avoids rejecting in-flight inserts
     while we rewrite rows.
  2. For every existing type edge:
       - parse the version off the `_from` key
       - confirm the corresponding ProxyOut exists for that tenant
       - delete-and-reinsert the edge with the new `_from` / `_fromType`
       - if the ProxyOut is missing (shouldn't happen post-repair), drop
         the edge and report it.
  3. Tighten the edge definition to proxy-only.

The script is idempotent: rerunning it on already-migrated data is a no-op.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arango import ArangoClient
from arango.database import StandardDatabase

from src.config.centralized_credentials import CredentialsManager

logger = logging.getLogger("type-anchor-migration")

GRAPH_NAME = "network_assets_smartgraph"
TYPE_EDGE = "type"
CLASS = "Class"

# Mapping rule: parse the key portion of `_from` (after the `tenantId:`
# prefix) which has the form "<entity><index>-<version>" -- e.g.
# "device12-3" or "software7-0". Strip the "-<version>" tail to get the
# proxy key, and pick the proxy collection by inspecting the entity
# prefix.
LEGACY_TO_PROXY_COLLECTION = {
    "Device": "DeviceProxyOut",
    "Software": "SoftwareProxyOut",
}


def split_id(arango_id: str) -> Tuple[str, str]:
    """`coll/key` -> (coll, key)."""
    coll, key = arango_id.split("/", 1)
    return coll, key


def proxy_key_from_versioned(versioned_key: str) -> str:
    """`<tenant>:device12-3` -> `<tenant>:device12`. If no version suffix,
    return as-is (lets us be idempotent on already-migrated rows)."""
    if "-" not in versioned_key:
        return versioned_key
    head, _, tail = versioned_key.rpartition("-")
    if tail.isdigit():
        return head
    return versioned_key


def widen_edge_definition(db: StandardDatabase) -> bool:
    """Step 1: allow both legacy and proxy collections as `from`."""
    g = db.graph(GRAPH_NAME)
    current = next((e for e in g.edge_definitions()
                    if e["edge_collection"] == TYPE_EDGE), None)
    if not current:
        raise RuntimeError(f"no edge definition for {TYPE_EDGE} in {GRAPH_NAME}")

    target_from = sorted(set(current["from_vertex_collections"]) |
                         {"DeviceProxyOut", "SoftwareProxyOut"})
    if sorted(current["from_vertex_collections"]) == target_from:
        logger.info("[1/3] edge definition already widened: %s", target_from)
        return False
    g.replace_edge_definition(
        edge_collection=TYPE_EDGE,
        from_vertex_collections=target_from,
        to_vertex_collections=current["to_vertex_collections"],
    )
    logger.info("[1/3] widened edge definition: from=%s", target_from)
    return True


def narrow_edge_definition(db: StandardDatabase) -> bool:
    """Step 3: tighten to proxy-only after data is migrated."""
    g = db.graph(GRAPH_NAME)
    current = next((e for e in g.edge_definitions()
                    if e["edge_collection"] == TYPE_EDGE), None)
    if not current:
        raise RuntimeError(f"no edge definition for {TYPE_EDGE} in {GRAPH_NAME}")

    target_from = ["DeviceProxyOut", "SoftwareProxyOut"]
    if sorted(current["from_vertex_collections"]) == sorted(target_from):
        logger.info("[3/3] edge definition already narrowed to proxy-only")
        return False
    g.replace_edge_definition(
        edge_collection=TYPE_EDGE,
        from_vertex_collections=target_from,
        to_vertex_collections=current["to_vertex_collections"],
    )
    logger.info("[3/3] narrowed edge definition to %s", target_from)
    return True


CHUNK = 500


def _chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _bulk_existing_keys(db: StandardDatabase, collection: str,
                        keys: List[str]) -> set:
    """Return the subset of `keys` that exist as documents in `collection`,
    via a single AQL roundtrip."""
    if not keys:
        return set()
    rows = db.aql.execute(
        f"FOR k IN @keys "
        f"  LET d = DOCUMENT(@@coll, k) "
        f"  FILTER d != null "
        f"  RETURN k",
        bind_vars={"keys": keys, "@coll": collection},
    )
    return set(rows)


def _plan_migration(db: StandardDatabase, rows: List[Dict[str, Any]]
                    ) -> Tuple[List[Tuple[Dict[str, Any], Dict[str, Any]]],
                               List[str], Counter]:
    """Return (rewrites, orphan_keys_to_delete, counter)."""
    counts = Counter()
    candidates: List[Tuple[Dict[str, Any], str, str]] = []

    for e in rows:
        from_coll, from_key = split_id(e["_from"])
        if from_coll in ("DeviceProxyOut", "SoftwareProxyOut"):
            counts["already_migrated"] += 1
            continue
        proxy_coll = LEGACY_TO_PROXY_COLLECTION.get(from_coll)
        if proxy_coll is None:
            counts["skipped_unknown_collection"] += 1
            logger.warning("  skipping unknown _from collection %s on edge %s",
                           from_coll, e["_key"])
            continue
        proxy_key = proxy_key_from_versioned(from_key)
        candidates.append((e, proxy_coll, proxy_key))

    by_coll: Dict[str, List[str]] = {}
    for _, proxy_coll, proxy_key in candidates:
        by_coll.setdefault(proxy_coll, []).append(proxy_key)
    existing: Dict[str, set] = {
        coll: _bulk_existing_keys(db, coll, list(set(keys)))
        for coll, keys in by_coll.items()
    }

    rewrites: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    orphans: List[str] = []
    for e, proxy_coll, proxy_key in candidates:
        if proxy_key not in existing.get(proxy_coll, set()):
            counts["orphan_no_proxy"] += 1
            orphans.append(e["_key"])
            continue
        new_doc = {k: v for k, v in e.items() if k not in ("_id", "_rev")}
        new_doc["_from"] = f"{proxy_coll}/{proxy_key}"
        new_doc["_fromType"] = proxy_coll
        rewrites.append((e, new_doc))
        counts["rewrite_planned"] += 1
    return rewrites, orphans, counts


def migrate_rows(db: StandardDatabase) -> Dict[str, int]:
    """Step 2: rewrite every legacy type-edge to anchor at its proxy."""
    type_coll = db.collection(TYPE_EDGE)
    total = type_coll.count()
    logger.info("[2/3] scanning %d type edges", total)

    rows: List[Dict[str, Any]] = list(db.aql.execute(
        f"FOR e IN {TYPE_EDGE} RETURN e"
    ))

    rewrites, deletes_orphan, counts = _plan_migration(db, rows)
    logger.info("  plan: %s", dict(counts))

    # Apply rewrites in chunks: delete originals, then insert corrected.
    rewritten = 0
    for batch in _chunked(rewrites, CHUNK):
        type_coll.delete_many([{"_key": e["_key"]} for e, _ in batch])
        type_coll.insert_many([new for _, new in batch])
        rewritten += len(batch)
    counts["rewritten"] = rewritten

    deleted = 0
    for batch in _chunked(deletes_orphan, CHUNK):
        type_coll.delete_many([{"_key": k} for k in batch])
        deleted += len(batch)
    counts["deleted_orphans"] = deleted

    return dict(counts)


def diagnose(db: StandardDatabase) -> None:
    rows = list(db.aql.execute(
        f"FOR e IN {TYPE_EDGE} COLLECT t = e._fromType WITH COUNT INTO n "
        "RETURN { fromType: t, count: n }"
    ))
    logger.info("post-migration census:")
    for r in rows:
        logger.info("  %s", r)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change; touch nothing.")
    parser.add_argument("--skip-widen", action="store_true",
                        help="Don't widen the edge definition before migrating "
                             "(use if you already widened it manually).")
    parser.add_argument("--skip-narrow", action="store_true",
                        help="Don't narrow the edge definition after migrating; "
                             "leave Device/Software in the from list. Useful if "
                             "you have other writers still emitting legacy edges.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    creds = CredentialsManager.get_database_credentials()
    db = ArangoClient(hosts=creds.endpoint).db(
        creds.database_name, **CredentialsManager.get_database_params()
    )

    logger.info("Endpoint: %s", creds.endpoint)
    logger.info("Database: %s", creds.database_name)
    logger.info("Mode:     %s", "DRY-RUN" if args.dry_run else "APPLY")

    type_coll = db.collection(TYPE_EDGE)
    logger.info("type collection size: %d", type_coll.count())
    diagnose(db)

    if args.dry_run:
        logger.info("\n[dry-run plan]")
        rows = list(db.aql.execute(f"FOR e IN {TYPE_EDGE} RETURN e"))
        _, _, plan = _plan_migration(db, rows)
        for k, v in plan.items():
            logger.info("  %s: %d", k, v)
        return 0

    if not args.skip_widen:
        widen_edge_definition(db)
    else:
        logger.info("[1/3] --skip-widen: leaving edge definition as-is")

    counts = migrate_rows(db)
    logger.info("[2/3] migration result: %s", counts)

    if not args.skip_narrow:
        narrow_edge_definition(db)
    else:
        logger.info("[3/3] --skip-narrow: leaving edge definition widened")

    logger.info("\nfinal type collection size: %d", type_coll.count())
    diagnose(db)
    logger.info("\n[OK] migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
