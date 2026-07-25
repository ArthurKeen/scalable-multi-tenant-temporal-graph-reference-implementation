"""
Verify the new tenant-aware vertex-centric indexes are actually used.

Two checks:
  1. Collection-level: a direct FILTER on (_to, tenantId) should EXPLAIN to
     `idx_type_to_tenantid`.
  2. Traversal: a satellite -> tenant INBOUND traversal with a tenant filter
     on the edge should be cheap. We compare runtime against the same
     traversal without the index hint (forcing it through the primary edge
     index by filtering on the target vertex's tenantId instead).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arango import ArangoClient
from src.config.centralized_credentials import CredentialsManager


def collect_index_names(obj: Any, acc: List[str]) -> None:
    if isinstance(obj, dict):
        if "name" in obj and "fields" in obj:
            acc.append(f"{obj['name']} {obj.get('fields')}")
        for v in obj.values():
            collect_index_names(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_index_names(v, acc)


def main() -> int:
    creds = CredentialsManager.get_database_credentials()
    db = ArangoClient(hosts=creds.endpoint).db(
        creds.database_name, **CredentialsManager.get_database_params()
    )

    sample = list(db.aql.execute(
        """
        FOR e IN type
          LIMIT 1
          LET cls = DOCUMENT(e._to)
          RETURN { to: e._to, classKey: cls.classKey, tenantId: e.tenantId }
        """
    ))[0]
    print(f"sample: {sample}")
    to = sample["to"]
    tenant_id = sample["tenantId"]
    class_key = sample["classKey"]

    print("\n--- 1. Direct collection FILTER on (_to, tenantId) ---")
    q1 = """
    FOR e IN type
      FILTER e._to == @to AND e.tenantId == @tenantId
      RETURN e._key
    """
    plan1 = db.aql.explain(q1, bind_vars={"to": to, "tenantId": tenant_id})
    names: List[str] = []
    collect_index_names(plan1, names)
    print(f"indexes: {names}")

    print("\n--- 2. Direct collection FILTER on _to only (no tenant) ---")
    q2 = """
    FOR e IN type
      FILTER e._to == @to
      RETURN e._key
    """
    plan2 = db.aql.explain(q2, bind_vars={"to": to})
    names2: List[str] = []
    collect_index_names(plan2, names2)
    print(f"indexes: {names2}")

    print("\n--- 3. Satellite -> tenant traversal (path filter -- canonical pattern) ---")
    q3 = """
    WITH Class, Device, Software, type
    FOR c IN Class
      FILTER c.classKey == @classKey
      FOR v, e, p IN 1..1 INBOUND c type
        FILTER p.edges[*].tenantId ALL == @tenantId
        RETURN { v: v._key, t: e.tenantId }
    """
    bind3 = {"classKey": class_key, "tenantId": tenant_id}
    # Run twice -- first call hits cold caches.
    db.aql.execute(q3, bind_vars=bind3, count=True).batch()
    t0 = time.perf_counter()
    cur = db.aql.execute(q3, bind_vars=bind3, count=True)
    rows = list(cur)
    t1 = time.perf_counter()
    print(f"rows={len(rows)}  elapsed={1000*(t1-t0):.1f} ms")
    plan3 = db.aql.explain(q3, bind_vars=bind3)
    names3: List[str] = []
    collect_index_names(plan3, names3)
    print(f"indexes (high-level): {names3}")

    print("\n--- 4. Same traversal, NO edge filter, post-filter on target vertex ---")
    q4 = """
    WITH Class, Device, Software, type
    FOR c IN Class
      FILTER c.classKey == @classKey
      FOR v, e IN 1..1 INBOUND c type
        FILTER v.tenantId == @tenantId
        RETURN { v: v._key, t: v.tenantId }
    """
    bind4 = {"classKey": class_key, "tenantId": tenant_id}
    db.aql.execute(q4, bind_vars=bind4, count=True).batch()
    t0 = time.perf_counter()
    cur = db.aql.execute(q4, bind_vars=bind4, count=True)
    rows = list(cur)
    t1 = time.perf_counter()
    print(f"rows={len(rows)}  elapsed={1000*(t1-t0):.1f} ms")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
