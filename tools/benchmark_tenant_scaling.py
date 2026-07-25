"""
Demonstrate that per-tenant traversal cost stays flat as the number of
tenants grows, when the satellite-to-tenant edge carries a redundant
`tenantId` and a `(_to, tenantId)` vertex-centric persistent index is
present (Pattern 3 in docs/MULTI_TENANT_PATTERNS.md).

The benchmark generates a synthetic, isolated schema in the same database
as the live demo (everything is `bench_*`-prefixed and dropped at the
end of the run). It then walks a series of tenant-count steps and, for
each step, times the canonical "find this tenant's instances of this
class" query in two shapes:

  - GOOD  : path-filter idiom -- the planner picks the (_to, tenantId)
            vertex-centric index.
  - ANTI  : filter on target-vertex tenantId -- the planner can't engage
            the vertex-centric index and must dereference each candidate.

At small N the two are within noise. As N grows the GOOD shape stays
~constant while the ANTI shape grows roughly linearly. That's the point
of the demo: the architectural choice doesn't *speed up* per-tenant
queries, it makes them *not slow down* as you add tenants.

Usage:
    PYTHONPATH=. python3 tools/benchmark_tenant_scaling.py
    PYTHONPATH=. python3 tools/benchmark_tenant_scaling.py --steps 100,1000,5000
    PYTHONPATH=. python3 tools/benchmark_tenant_scaling.py --no-cleanup    # keep bench_* for inspection
    PYTHONPATH=. python3 tools/benchmark_tenant_scaling.py --cleanup-only  # drop bench_* and exit
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
import uuid
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arango import ArangoClient
from arango.database import StandardDatabase
from arango.exceptions import IndexCreateError

from src.config.centralized_credentials import CredentialsManager

logger = logging.getLogger("scaling-bench")


# ---------------------------------------------------------------------------
# Schema definition
#
# We use a minimal schema that mirrors the production pattern:
#   bench_Software (smart, sharded by tenantId)
#   bench_Class    (satellite, replicated to all DB-servers)
#   bench_type     (edge: bench_Software -> bench_Class)
#
# Indexes mirror the ones in src/database/database_deployment.py:
#   bench_idx_type_to_tenantid     (_to, tenantId)
#   bench_idx_type_to_fromtype     (_to, _fromType)
# ---------------------------------------------------------------------------


GRAPH_NAME = "bench_smartgraph"
SOFTWARE = "bench_Software"
CLASS = "bench_Class"
TYPE = "bench_type"

INDEX_TO_TENANT = "bench_idx_type_to_tenantid"
INDEX_TO_FROMTYPE = "bench_idx_type_to_fromtype"

CLASSES_PER_TENANT_HIT = 1   # how many of the M classes the bench query targets
M_CLASSES = 8                # total satellite classes
ROWS_PER_TENANT = 50         # software rows per tenant; one type-edge each


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def cleanup(db: StandardDatabase) -> None:
    """Drop the benchmark graph and its collections."""
    if db.has_graph(GRAPH_NAME):
        db.delete_graph(GRAPH_NAME, drop_collections=True, ignore_missing=True)
        logger.info("[cleanup] dropped graph %s and its collections", GRAPH_NAME)
    for name in (TYPE, SOFTWARE, CLASS):
        if db.has_collection(name):
            db.delete_collection(name)
            logger.info("[cleanup] dropped %s", name)


def ensure_schema(db: StandardDatabase) -> None:
    """Create the benchmark SmartGraph + satellite collection + indexes if missing."""
    if not db.has_collection(CLASS):
        db.create_collection(CLASS, replication_factor="satellite")
        logger.info("[setup] created satellite collection %s", CLASS)

    if not db.has_graph(GRAPH_NAME):
        db.create_graph(
            name=GRAPH_NAME,
            edge_definitions=[{
                "edge_collection": TYPE,
                "from_vertex_collections": [SOFTWARE],
                "to_vertex_collections": [CLASS],
            }],
            smart=True,
            smart_field="tenantId",
        )
        logger.info("[setup] created SmartGraph %s (smart_field=tenantId)", GRAPH_NAME)

    type_coll = db.collection(TYPE)
    existing = {ix.get("name") for ix in type_coll.indexes()}
    if INDEX_TO_TENANT not in existing:
        try:
            type_coll.add_index({"type": "persistent",
                                 "fields": ["_to", "tenantId"],
                                 "name": INDEX_TO_TENANT})
            logger.info("[setup] created index %s", INDEX_TO_TENANT)
        except IndexCreateError as err:
            logger.warning("[setup] index %s create failed: %s", INDEX_TO_TENANT, err)
    if INDEX_TO_FROMTYPE not in existing:
        try:
            type_coll.add_index({"type": "persistent",
                                 "fields": ["_to", "_fromType"],
                                 "name": INDEX_TO_FROMTYPE})
            logger.info("[setup] created index %s", INDEX_TO_FROMTYPE)
        except IndexCreateError as err:
            logger.warning("[setup] index %s create failed: %s", INDEX_TO_FROMTYPE, err)


def seed_classes(db: StandardDatabase) -> List[str]:
    """Idempotent seed of M satellite Class vertices. Returns their _ids."""
    cls = db.collection(CLASS)
    ids: List[str] = []
    for i in range(M_CLASSES):
        key = f"bench_class_{i:02d}"
        if not cls.has(key):
            cls.insert({"_key": key, "name": f"bench-class-{i}"})
        ids.append(f"{CLASS}/{key}")
    return ids


# ---------------------------------------------------------------------------
# Synthetic data generation
#
# Each tenant gets ROWS_PER_TENANT software rows, each with one type-edge
# to a randomly-chosen Class. Inserts go through bulk endpoints in
# CHUNK-sized batches.
# ---------------------------------------------------------------------------


CHUNK = 1000


def _chunk(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def existing_tenants(db: StandardDatabase) -> int:
    """Return the highest bench-tenant id already present (0 if none)."""
    rows = list(db.aql.execute(
        "RETURN COUNT(FOR sw IN @@coll FILTER STARTS_WITH(sw.tenantId, 'bt') RETURN 1)",
        bind_vars={"@coll": SOFTWARE},
    ))
    return int(rows[0] or 0)


def seed_tenants(db: StandardDatabase, n_tenants: int, class_ids: List[str]) -> None:
    """Add bench tenants up to n_tenants. Idempotent: existing tenants are skipped."""
    sw = db.collection(SOFTWARE)
    type_coll = db.collection(TYPE)

    have_rows = sw.count()
    target_rows = n_tenants * ROWS_PER_TENANT
    if have_rows >= target_rows:
        logger.info("[seed] already have %d rows >= target %d, skipping",
                    have_rows, target_rows)
        return

    starting_tenant = have_rows // ROWS_PER_TENANT
    rng = random.Random(0xBEEF)
    logger.info("[seed] generating tenants %d..%d (%d rows total)",
                starting_tenant, n_tenants - 1,
                (n_tenants - starting_tenant) * ROWS_PER_TENANT)

    sw_buf: List[dict] = []
    edge_buf: List[dict] = []
    t0 = time.perf_counter()

    for t_idx in range(starting_tenant, n_tenants):
        tenant_id = f"bt{t_idx:06d}"
        for r in range(ROWS_PER_TENANT):
            sw_key = f"{tenant_id}:sw{r:03d}"
            sw_buf.append({"_key": sw_key, "tenantId": tenant_id, "name": f"sw-{r}"})

            target = rng.choice(class_ids)
            edge_buf.append({
                "_key": f"{tenant_id}:type_{uuid.uuid4().hex[:8]}",
                "tenantId": tenant_id,
                "_from": f"{SOFTWARE}/{sw_key}",
                "_to": target,
                "_fromType": "Software",
                "_toType": "Class",
            })

        if len(sw_buf) >= CHUNK:
            sw.insert_many(sw_buf, overwrite=True)
            type_coll.insert_many(edge_buf, overwrite=True)
            sw_buf.clear()
            edge_buf.clear()

    if sw_buf:
        sw.insert_many(sw_buf, overwrite=True)
        type_coll.insert_many(edge_buf, overwrite=True)

    elapsed = time.perf_counter() - t0
    logger.info("[seed] %d tenants in %.1f s", n_tenants - starting_tenant, elapsed)


# ---------------------------------------------------------------------------
# Benchmark queries
# ---------------------------------------------------------------------------


# GOOD: path-filter on the edge's tenantId -- engages idx_type_to_tenantid.
GOOD_QUERY = f"""
WITH {CLASS}, {SOFTWARE}, {TYPE}
FOR v, e, p IN 1..1 INBOUND @startClass {TYPE}
  FILTER p.edges[*].tenantId ALL == @tenantId
  RETURN v._key
"""


# ANTI: filter on the *target vertex's* tenantId. The planner must read
# every incident edge, dereference each target Software, then filter.
ANTI_QUERY = f"""
WITH {CLASS}, {SOFTWARE}, {TYPE}
FOR v, e IN 1..1 INBOUND @startClass {TYPE}
  FILTER v.tenantId == @tenantId
  RETURN v._key
"""


def time_query(db: StandardDatabase, q: str, bind_vars: dict, repetitions: int) -> Tuple[float, int]:
    """Run the query `repetitions` times after one warmup; return (median ms, last-row-count)."""
    db.aql.execute(q, bind_vars=bind_vars).batch()
    timings: List[float] = []
    n_rows = 0
    for _ in range(repetitions):
        t0 = time.perf_counter()
        cur = db.aql.execute(q, bind_vars=bind_vars)
        rows = list(cur)
        timings.append(time.perf_counter() - t0)
        n_rows = len(rows)
    timings.sort()
    median = timings[len(timings) // 2]
    return median * 1000.0, n_rows


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def parse_steps(raw: str) -> List[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", default="10,100,1000",
                        help="comma-separated tenant counts (default: 10,100,1000)")
    parser.add_argument("--repetitions", type=int, default=5,
                        help="query repetitions per measurement (default: 5)")
    parser.add_argument("--no-cleanup", action="store_true",
                        help="do not drop bench_* collections at exit")
    parser.add_argument("--cleanup-only", action="store_true",
                        help="drop bench_* collections and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    creds = CredentialsManager.get_database_credentials()
    db = ArangoClient(hosts=creds.endpoint).db(
        creds.database_name, **CredentialsManager.get_database_params()
    )

    logger.info("Endpoint: %s", creds.endpoint)
    logger.info("Database: %s", creds.database_name)

    if args.cleanup_only:
        cleanup(db)
        return 0

    steps = parse_steps(args.steps)
    if not steps or any(s <= 0 for s in steps):
        logger.error("invalid --steps")
        return 2
    steps.sort()

    logger.info("\n[1/3] Setup schema")
    ensure_schema(db)
    class_ids = seed_classes(db)
    target_class = class_ids[0]

    logger.info("\n[2/3] Run scaling sweep: %s", steps)
    rng = random.Random(0xC0DE)
    results: List[Tuple[int, float, int, float, int]] = []

    for n in steps:
        logger.info("\n--- step: %d tenants ---", n)
        seed_tenants(db, n, class_ids)

        sample_tenant = f"bt{rng.randrange(n):06d}"
        bind_vars = {"startClass": target_class, "tenantId": sample_tenant}

        good_ms, good_rows = time_query(db, GOOD_QUERY, bind_vars, args.repetitions)
        anti_ms, anti_rows = time_query(db, ANTI_QUERY, bind_vars, args.repetitions)
        ratio = anti_ms / good_ms if good_ms > 0 else float("inf")

        logger.info("  tenant sampled: %s", sample_tenant)
        logger.info("  GOOD (path-filter, idx_type_to_tenantid): %7.2f ms (%d rows)",
                    good_ms, good_rows)
        logger.info("  ANTI (target-vertex filter):              %7.2f ms (%d rows)  ratio %.1fx",
                    anti_ms, anti_rows, ratio)
        results.append((n, good_ms, good_rows, anti_ms, anti_rows))

    logger.info("\n[3/3] Summary")
    logger.info("  %-10s  %-12s  %-12s  %-8s",
                "tenants", "GOOD ms", "ANTI ms", "ANTI/GOOD")
    for n, g, _gr, a, _ar in results:
        logger.info("  %-10d  %-12.2f  %-12.2f  %.1fx", n, g, a, a / g if g > 0 else 0.0)
    logger.info("\nInterpretation: GOOD should stay roughly flat as tenant count grows.")
    logger.info("ANTI grows roughly linearly with #tenants -- it scans every incident edge.")

    if not args.no_cleanup:
        logger.info("\n[cleanup]")
        cleanup(db)
    else:
        logger.info("\n[--no-cleanup] bench_* objects retained; rerun with --cleanup-only to drop")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
