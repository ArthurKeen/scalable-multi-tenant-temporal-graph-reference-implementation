"""
Inspect satellite-touching edges (`type`, `subClassOf`) and the `network_assets_smartgraph`
to confirm:
  - whether edges currently carry tenantId / _fromType / _toType
  - whether vertex-centric indexes exist that include tenantId
  - per-tenant counts on `type` edges

This is read-only.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

# Ensure project root is on PYTHONPATH when invoked directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arango import ArangoClient
from src.config.centralized_credentials import CredentialsManager


def main() -> int:
    creds = CredentialsManager.get_database_credentials()
    client = ArangoClient(hosts=creds.endpoint)
    db = client.db(creds.database_name, **CredentialsManager.get_database_params())

    print(f"Endpoint: {creds.endpoint}")
    print(f"Database: {creds.database_name}")

    edge_collections = ["type", "subClassOf", "hasConnection", "hasLocation",
                        "hasDeviceSoftware", "hasVersion", "hasAlert"]

    for coll_name in edge_collections:
        if not db.has_collection(coll_name):
            print(f"\n[SKIP] {coll_name}: collection not found")
            continue
        coll = db.collection(coll_name)
        count = coll.count()
        print(f"\n=== {coll_name} ({count} edges) ===")

        sample = list(coll.all(limit=1))
        if sample:
            doc = sample[0]
            keys = sorted(doc.keys())
            has_tenant = "tenantId" in doc
            has_from_type = "_fromType" in doc
            has_to_type = "_toType" in doc
            print(f"  sample fields: {keys}")
            print(f"  tenantId present: {has_tenant}")
            print(f"  _fromType present: {has_from_type} ({doc.get('_fromType')})")
            print(f"  _toType present: {has_to_type} ({doc.get('_toType')})")

        for idx in coll.indexes():
            name = idx.get("name")
            fields = idx.get("fields")
            itype = idx.get("type")
            print(f"  index: {name:40s} type={itype:12s} fields={fields}")

    if db.has_collection("type"):
        print("\n--- per-tenant type-edge counts ---")
        cursor = db.aql.execute(
            """
            FOR e IN type
              COLLECT t = e.tenantId WITH COUNT INTO n
              SORT n DESC
              RETURN { tenantId: t, edges: n }
            """
        )
        for row in cursor:
            print(f"  {row}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
