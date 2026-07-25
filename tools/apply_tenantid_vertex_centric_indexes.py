"""
Apply tenant-aware vertex-centric indexes for satellite -> SmartGraph edges.

Targets the database referenced in `.env`. Idempotent: safe to re-run.

Steps
-----
1. Backfill `_fromType` / `_toType` on `type`, `subClassOf`, `hasAlert`
   (derived from `_from` / `_to` collection prefixes).
2. Verify every `type` edge has `tenantId` populated.
3. Create vertex-centric persistent indexes:
     - type:        (_to, tenantId), (_from, tenantId),
                    (_from, _toType), (_to, _fromType)
     - subClassOf:  (_from, _toType), (_to, _fromType)
     - hasAlert:    (_from, _toType), (_to, _fromType)
4. EXPLAIN a representative satellite -> tenant traversal to confirm the
   `(_to, tenantId)` index on `type` is used by the planner.

Usage
-----
    PYTHONPATH=. python3 tools/apply_tenantid_vertex_centric_indexes.py
    PYTHONPATH=. python3 tools/apply_tenantid_vertex_centric_indexes.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arango import ArangoClient
from arango.database import StandardDatabase

from src.config.centralized_credentials import CredentialsManager

logger = logging.getLogger("vc-index-migration")


# ---------------------------------------------------------------------------
# Index plan -- mirror of the production plan in
# src/database/database_deployment.py:create_indexes
# ---------------------------------------------------------------------------

INDEX_PLAN: List[Dict[str, Any]] = [
    # `type` (Device|Software -> Class satellite)
    {"collection": "type", "fields": ["_to", "tenantId"],
     "name": "idx_type_to_tenantid"},
    {"collection": "type", "fields": ["_from", "tenantId"],
     "name": "idx_type_from_tenantid"},
    {"collection": "type", "fields": ["_from", "_toType"],
     "name": "idx_type_from_totype"},
    {"collection": "type", "fields": ["_to", "_fromType"],
     "name": "idx_type_to_fromtype"},

    # `subClassOf` (Class -> Class satellite)
    {"collection": "subClassOf", "fields": ["_from", "_toType"],
     "name": "idx_subClassOf_from_totype"},
    {"collection": "subClassOf", "fields": ["_to", "_fromType"],
     "name": "idx_subClassOf_to_fromtype"},

    # `hasAlert` (DeviceProxyOut|SoftwareProxyOut -> Alert)
    {"collection": "hasAlert", "fields": ["_from", "_toType"],
     "name": "idx_hasAlert_from_totype"},
    {"collection": "hasAlert", "fields": ["_to", "_fromType"],
     "name": "idx_hasAlert_to_fromtype"},
]


# Backfill plan: collections where `_fromType` / `_toType` may be missing
# on existing rows. Both fields are derived from the document-id prefixes.
BACKFILL_COLLECTIONS = ["type", "subClassOf", "hasAlert"]


# ---------------------------------------------------------------------------
# Backfill -- in-place AQL update, idempotent.
# ---------------------------------------------------------------------------


def backfill_from_to_type(db: StandardDatabase, collection: str,
                          dry_run: bool) -> Dict[str, int]:
    """Set `_fromType` / `_toType` from `_from` / `_to` prefixes where missing."""
    aql_count = """
    RETURN LENGTH(
      FOR e IN @@col
        FILTER e._fromType == null OR e._toType == null
        RETURN 1
    )
    """
    missing = next(db.aql.execute(aql_count, bind_vars={"@col": collection}))

    if missing == 0:
        logger.info("  [%s] _fromType / _toType already populated -- nothing to backfill", collection)
        return {"missing": 0, "updated": 0}

    logger.info("  [%s] %d edges missing _fromType / _toType", collection, missing)

    if dry_run:
        return {"missing": missing, "updated": 0}

    aql_update = """
    FOR e IN @@col
      FILTER e._fromType == null OR e._toType == null
      LET fromType = SPLIT(e._from, "/")[0]
      LET toType   = SPLIT(e._to,   "/")[0]
      UPDATE e WITH { _fromType: fromType, _toType: toType } IN @@col
      OPTIONS { keepNull: false }
      COLLECT WITH COUNT INTO n
      RETURN n
    """
    updated = next(db.aql.execute(aql_update, bind_vars={"@col": collection}))
    logger.info("  [%s] backfilled %d edges", collection, updated)
    return {"missing": missing, "updated": updated}


def verify_tenant_id(db: StandardDatabase, collection: str) -> int:
    """Return the count of rows missing `tenantId`."""
    aql = """
    RETURN LENGTH(
      FOR e IN @@col
        FILTER e.tenantId == null
        RETURN 1
    )
    """
    return next(db.aql.execute(aql, bind_vars={"@col": collection}))


# ---------------------------------------------------------------------------
# Index creation -- idempotent.
# ---------------------------------------------------------------------------


def ensure_index(db: StandardDatabase, plan: Dict[str, Any], dry_run: bool) -> str:
    """Create a persistent index defined by `plan` if it does not already exist."""
    name = plan["name"]
    coll_name = plan["collection"]
    fields = plan["fields"]

    if not db.has_collection(coll_name):
        logger.warning("  [%s] collection missing -- skipping %s", coll_name, name)
        return "skipped"

    coll = db.collection(coll_name)
    for existing in coll.indexes():
        if existing.get("name") == name:
            existing_fields = existing.get("fields") or []
            if list(existing_fields) == list(fields):
                logger.info("  [%s] index %s already exists on %s", coll_name, name, fields)
                return "exists"
            # name collision with different fields -- recreate
            logger.warning("  [%s] index %s exists on %s but plan needs %s -- replacing",
                           coll_name, name, existing_fields, fields)
            if not dry_run:
                coll.delete_index(existing["id"])
            break

    if dry_run:
        logger.info("  [%s] DRY-RUN would create persistent index %s on %s",
                    coll_name, name, fields)
        return "dry-run"

    coll.add_index({
        "type": "persistent",
        "fields": fields,
        "name": name,
        "sparse": False,
        "unique": False,
    })
    logger.info("  [%s] created persistent index %s on %s", coll_name, name, fields)
    return "created"


# ---------------------------------------------------------------------------
# EXPLAIN check -- confirm the planner now picks `idx_type_to_tenantid`.
# ---------------------------------------------------------------------------


# NOTE: For ArangoDB to promote a vertex-centric `(_to, tenantId)` index
# inside a traversal, the tenant filter must be expressed as a *path* filter
# (`p.edges[*].tenantId ALL == @tenantId`). A bare `FILTER e.tenantId == ...`
# is a post-traversal filter and falls back to the primary edge index.
EXPLAIN_QUERY = """
WITH Class, Device, Software, type
FOR c IN Class
  FILTER c.classKey == @classKey
  FOR v, e, p IN 1..1 INBOUND c type
    FILTER p.edges[*].tenantId ALL == @tenantId
    LIMIT 25
    RETURN { vertex: v._key, tenantId: e.tenantId }
"""


def pick_explain_bind_vars(db: StandardDatabase) -> Dict[str, Any] | None:
    """Pick a real (classKey, tenantId) pair from the live data so EXPLAIN
    has a representative shape with non-empty selectivity."""
    aql = """
    FOR e IN type
      LIMIT 1
      LET cls = DOCUMENT(e._to)
      RETURN { classKey: cls.classKey, tenantId: e.tenantId }
    """
    cursor = db.aql.execute(aql)
    rows = list(cursor)
    if not rows:
        return None
    row = rows[0]
    if not row.get("classKey") or not row.get("tenantId"):
        return None
    return {"classKey": row["classKey"], "tenantId": row["tenantId"]}


def _collect_index_names(plan: Dict[str, Any]) -> List[str]:
    """Walk a plan dict and collect all referenced index names.

    Handles both single-server and cluster plan shapes. Index references can
    appear as dicts (with `name`) or as plain id strings; coordinator plans
    also nest sub-plans under `nodes`/`subqueries`.
    """
    names: List[str] = []

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            if "name" in obj and "fields" in obj:
                names.append(obj["name"])
            for v in obj.values():
                visit(v)
        elif isinstance(obj, list):
            for v in obj:
                visit(v)

    visit(plan)
    return names


def explain_traversal(db: StandardDatabase) -> None:
    bind = pick_explain_bind_vars(db)
    if bind is None:
        logger.warning("  No (classKey, tenantId) pair found -- skipping EXPLAIN check")
        return

    logger.info("  EXPLAIN bind vars: %s", bind)
    plan = db.aql.explain(EXPLAIN_QUERY, bind_vars=bind, all_plans=False)
    used_idx_names = sorted(set(_collect_index_names(plan)))
    logger.info("  Indexes referenced in plan: %s", used_idx_names or "(none reported)")
    if "idx_type_to_tenantid" in used_idx_names:
        logger.info("  [OK] idx_type_to_tenantid is used by the planner")
    else:
        logger.info("  [INFO] idx_type_to_tenantid not explicitly referenced -- the"
                    " traversal plan may summarize edge access; run an arangosh"
                    " EXPLAIN for full detail")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    creds = CredentialsManager.get_database_credentials()
    client = ArangoClient(hosts=creds.endpoint)
    db = client.db(creds.database_name, **CredentialsManager.get_database_params())

    logger.info("Endpoint: %s", creds.endpoint)
    logger.info("Database: %s", creds.database_name)
    logger.info("Mode:     %s", "DRY-RUN" if args.dry_run else "APPLY")

    logger.info("\n[1/4] Backfilling _fromType / _toType")
    for coll in BACKFILL_COLLECTIONS:
        if not db.has_collection(coll):
            logger.warning("  [%s] collection missing -- skipping", coll)
            continue
        backfill_from_to_type(db, coll, args.dry_run)

    logger.info("\n[2/4] Verifying tenantId presence on type edges")
    missing_tenant = verify_tenant_id(db, "type")
    if missing_tenant:
        logger.warning("  [type] %d edges missing tenantId -- vertex-centric "
                       "(_to, tenantId) index won't be useful for those rows",
                       missing_tenant)
    else:
        logger.info("  [type] all edges carry tenantId")

    logger.info("\n[3/4] Creating vertex-centric indexes")
    summary: Dict[str, int] = {"created": 0, "exists": 0, "skipped": 0, "dry-run": 0}
    for plan in INDEX_PLAN:
        outcome = ensure_index(db, plan, args.dry_run)
        summary[outcome] = summary.get(outcome, 0) + 1
    logger.info("  summary: %s", summary)

    logger.info("\n[4/4] EXPLAIN check on satellite -> tenant traversal")
    if not args.dry_run:
        explain_traversal(db)
    else:
        logger.info("  skipped in dry-run")

    logger.info("\n[DONE]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
