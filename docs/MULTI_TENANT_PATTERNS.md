# Multi-Tenant Graph Patterns at Scale

A blueprint, with worked examples, for running a graph database with thousands of
tenants on a single shared cluster while keeping per-tenant queries cheap.

This document is the take-home artifact for prospects evaluating ArangoDB for
multi-tenant SaaS. The repository it lives in is the runnable reference
implementation; every pattern below cites the exact file and line that shows
how to wire it.

> **Audience.** Technical evaluators (architects, senior engineers) who already
> know what a graph database is and want to understand how ArangoDB makes
> tenant isolation cheap *and* still lets a small "shared" pool of metadata
> participate in tenant queries without breaking the tenant boundary.

---

## TL;DR — The five patterns

| # | Pattern                                                              | Solves                                                                |
|---|----------------------------------------------------------------------|-----------------------------------------------------------------------|
| 1 | **SmartGraph sharded by `tenantId`**                                 | Per-tenant query cost is independent of #tenants.                     |
| 2 | **Satellite collections for shared metadata**                        | Tenant queries can join shared reference data without cross-shard hops. |
| 3 | **Redundant `tenantId` on satellite-bridge edges + vertex-centric index** | Traversals starting from a shared vertex still scope to one tenant via index seek. |
| 4 | **`_fromType` / `_toType` on every edge + path-filter AQL idiom**    | Type-aware traversals stay on the index instead of materializing whole vertices. |
| 5 | **Cross-graph edges anchor at proxies, not versioned entities**      | A single classification (or other long-lived bridge edge) survives version churn and TTL aging without becoming an orphan. |

Each pattern has a cost rationale, a code anchor, and an anti-pattern to avoid.

---

## Pattern 1 — Tenant data lives on a SmartGraph sharded by `tenantId`

### What

A SmartGraph is a graph collection set whose shards are colocated by a chosen
attribute. We pick `tenantId` as the smart field, so every vertex and edge for
a given tenant lives on a single shard, and so do its neighbors. A traversal
that starts at a tenant vertex never has to leave that shard.

### Where

```476:483:src/database/database_deployment.py
            try:
                # Create the unified SmartGraph with tenantId as smartGraphAttribute
                graph = self.database.create_graph(
                    name=smartgraph_name,
                    edge_definitions=edge_definitions,
                    smart=True,
                    smart_field="tenantId"  # This enables tenant-based sharding
                )
```

### Why it scales

Per-tenant query cost is `O(size_of_one_tenant)`, *not* `O(total_dataset)`.
Adding tenants 1001..10000 doesn't slow down tenant 42's query. This is the
single most important property of the design.

### Anti-pattern

Storing tenants in separate databases or separate collections "for isolation".
That defeats fan-out queries (cross-tenant analytics, abuse detection) and
produces 10,000 schemas to migrate the next time the model changes.

---

## Pattern 2 — Shared metadata lives in satellite collections

### What

Some data is genuinely tenant-agnostic: a product taxonomy, a country list,
a CVE catalog. Replicate it to every DB-server as a "satellite collection"
so that a tenant query joining against it never crosses the network.

### Where

```117:132:src/database/database_deployment.py
            satellite_collections = [
                {"name": self.app_config.get_collection_name("classes"), "type": "vertex"}
            ]

            logger.info(f"   Creating satellite collections for shared taxonomy...")
            for collection_config in satellite_collections:
                name = collection_config["name"]
                is_edge = collection_config["type"] == "edge"

                if not self.database.has_collection(name):
                    # Create satellite collection (replicated to all servers)
                    self.database.create_collection(
                        name=name,
                        edge=is_edge,
                        replication_factor="satellite"  # This makes it a satellite collection
                    )
```

### When to use

- Reference data that **all** tenants reference, that's small (≤ few hundred MB),
  and that updates rarely. Examples: taxonomies, geo data, product catalogues,
  CVE/CWE catalogs, regulatory codes.
- **Not** for fact data ("user activity", "telemetry"). That's tenant data.

### Cost rationale

Satellites trade *write amplification* (every node holds a copy) for
*join locality* (no network hop). For read-heavy reference data this is
trivially correct. Don't make a satellite collection of anything you write
more than a few times an hour.

---

## Pattern 3 — Cross-graph edges carry a redundant `tenantId` + vertex-centric index

This is the pattern most people miss, and the reason for this whole document.

### The problem

Consider a query that starts at a *shared* `Class` vertex (e.g.
`class:apache_http_server`) and asks "which of *my* tenant's `Software`
instances are classified under this?". The traversal direction is
`INBOUND Class type`.

```aql
FOR v, e IN 1..1 INBOUND @startClassId type
  RETURN v
```

`Class` is a satellite vertex — it has no `tenantId`. SmartGraph sharding
**cannot help us** here: the engine has to visit every `type` edge that
lands on `@startClassId` *across every tenant shard* and dereference each
target `Software` document just to discover its `tenantId`.

At 10 tenants this is fine. At 10,000 tenants, where each `Class` may have
~10,000 incident `type` edges (one or two per tenant), every per-tenant
classification query reads 10,000 edges and 10,000 vertex records to keep
the 1–2 it actually wanted.

### The fix

Two changes.

**1. Materialize `tenantId` onto the edge.** The edge already conceptually
belongs to one tenant (it connects that tenant's `Software` to a shared
`Class`); we just need to write it down explicitly. The edge is built
with `_fromType` / `_toType`, and `tenantId` is added by the temporal
helper that runs immediately after:

```427:450:src/data_generation/taxonomy_generator.py
        edge = {
            "_key": edge_key,
            "_id": f"{self.app_config.get_collection_name('types')}/{edge_key}",
            "_from": f"{from_collection}/{from_entity['_key']}",
            "_to": f"{self.app_config.get_collection_name('classes')}/{to_class_doc_key}",
            "_fromType": from_type,
            "_toType": "Class",
            "relationshipType": "instanceOf",
            "confidence": confidence,
            "classifiedAt": datetime.datetime.now().isoformat()
        }
        
        # Add temporal attributes  
        temp_tenant_config = TenantConfig(
            tenant_id=tenant_id,
            tenant_name=f"Classification_{tenant_id}"
        )
        
        enhanced_edge = TemporalDataModel.add_temporal_attributes(
            edge,
            timestamp=datetime.datetime.now(),
            expired=NEVER_EXPIRES,  # Classifications are persistent unless reclassified
            tenant_config=temp_tenant_config
        )
```

**2. Add a vertex-centric persistent index on `(_to, tenantId)`** so the
engine can satisfy the traversal with a single index seek per tenant
instead of reading every incident edge:

```198:205:src/database/database_deployment.py
                # `type` (Device|Software -> Class satellite). PRIMARY win:
                # the `(_to, tenantId)` index turns a multi-shard scan into a
                # single index seek when traversing INBOUND from a Class
                # vertex with `FILTER e.tenantId == @tenantId`.
                {"collection": "type", "type": "persistent",
                 "fields": ["_to", "tenantId"], "name": "idx_type_to_tenantid"},
                {"collection": "type", "type": "persistent",
                 "fields": ["_from", "tenantId"], "name": "idx_type_from_tenantid"},
```

### How to actually engage the index in AQL — Pattern 4 below

For a traversal, the optimizer only promotes the `(_to, tenantId)` index
when the tenant filter is expressed on the **path**, not on the edge variable:

```aql
// GOOD -- promotes to idx_type_to_tenantid
WITH Class, Device, Software, type
FOR c IN Class FILTER c.classKey == @classKey
  FOR v, e, p IN 1..1 INBOUND c type
    FILTER p.edges[*].tenantId ALL == @tenantId
    RETURN v
```

```aql
// SUBOPTIMAL -- falls back to primary edge index, scans every tenant
FOR v, e IN 1..1 INBOUND c type
  FILTER e.tenantId == @tenantId
  RETURN v
```

The repository's AQL skill (`.cursor/skills/aql/SKILL.md`) documents this
idiom; assistants and humans can both pattern-match against it.

### Cost rationale: how this scales

Let:

- `T` = number of tenants
- `K_t` = type-edges per tenant (≈ devices + software in the tenant)
- `C` = number of `Class` vertices in the satellite (constant)

Without the index, an INBOUND traversal from a `Class` vertex with N
incident type-edges costs `O(N) = O(Σ K_t)` — it grows linearly in the
**total** dataset.

With the `(_to, tenantId)` index, the same traversal costs `O(K_t / C_avg) ≈ O(1)`
per (class, tenant) pair — it's a single index seek into a sorted leaf
that holds only edges for *this* tenant landing on *this* class.

At 10,000 tenants with 1,000 type-edges each, on a popular class touched by
every tenant, the difference is 10,000,000 edges scanned vs ~1 index seek.
That's six orders of magnitude.

### Anti-patterns

- **Filtering on the target vertex's `tenantId` after the traversal** — the
  engine has already done the expensive part by the time you filter.
- **Dropping `tenantId` from the edge** "because it's redundant with the
  target's tenantId". The whole point is that the redundancy lets you
  filter without dereferencing the target.
- **Inverting the model** to make `Class` per-tenant. You lose all the
  benefits of a shared satellite catalog (one document update per
  classification change instead of T document updates).

---

## Pattern 4 — Type-aware edges (`_fromType` / `_toType`) and the path-filter idiom

### What

Every edge carries `_fromType` and `_toType` strings naming the kind of
endpoint at each side, e.g.

```json
{
  "_from": "DeviceProxyOut/abc:device-12",
  "_to":   "Alert/abc:alert-9",
  "_fromType": "DeviceProxyOut",
  "_toType":   "Alert",
  "tenantId":  "abc"
}
```

We then build a vertex-centric index pair on `(_from, _toType)` and
`(_to, _fromType)` for every edge collection:

```172:185:src/database/database_deployment.py
                # Tenant-internal edges: standard vertex-centric pair
                {"collection": "hasConnection", "type": "persistent",
                 "fields": ["_from", "_toType"], "name": "idx_connections_from_totype"},
                {"collection": "hasConnection", "type": "persistent",
                 "fields": ["_to", "_fromType"], "name": "idx_connections_to_fromtype"},
                {"collection": "hasLocation", "type": "persistent",
                 "fields": ["_from", "_toType"], "name": "idx_locations_from_totype"},
                {"collection": "hasDeviceSoftware", "type": "persistent",
                 "fields": ["_from", "_toType"], "name": "idx_device_software_from_totype"},
                {"collection": "hasDeviceSoftware", "type": "persistent",
                 "fields": ["_to", "_fromType"], "name": "idx_device_software_to_fromtype"},
                {"collection": "hasVersion", "type": "persistent",
                 "fields": ["_from", "_toType"], "name": "idx_version_from_totype"},
                {"collection": "hasVersion", "type": "persistent",
                 "fields": ["_to", "_fromType"], "name": "idx_version_to_fromtype"},
```

### Why

Many edge collections are heterogeneous — `hasVersion` connects four
different vertex types in this model (`DeviceProxyIn`, `Device`,
`SoftwareProxyIn`, `Software`). Without `_fromType`/`_toType`, the only way
to filter "give me hasVersion edges where the target is a `Device`" is to
dereference the target. With the type-aware index it's an index seek.

This is doubly important when you combine multi-tenancy and time travel:
the same physical edge collection holds versions of devices and versions of
software, all interleaved across all tenants. Without the type-aware index
a query like "current versions of all devices for tenant `abc`" forks into
a hot loop.

### Anti-pattern

Putting heterogeneous endpoint types into one edge collection without
recording the type on the edge. The optimizer can't tell them apart, and
filtering by collection name in AQL after the traversal is too late.

---

## Pattern 5 — Cross-graph edges anchor at proxies, not versioned entities

### What

When a vertex has a temporal lifecycle (current configuration plus retained
historical versions, ageing out via TTL), classifications and other
long-lived bridge edges anchor at the **proxy** -- the stable per-entity
identity in `DeviceProxyOut` / `SoftwareProxyOut` -- not at any particular
versioned `Device` / `Software` document.

### Where

```451:463:src/database/database_deployment.py
                    "edge_collection": self.app_config.get_collection_name("types"),
                    # Classifications anchor at the proxy (stable per-entity
                    # identity), not at the versioned Device/Software, so they
                    # survive version churn and historical-version TTL aging.
                    "from_vertex_collections": [
                        self.app_config.get_collection_name("device_outs"),
                        self.app_config.get_collection_name("software_outs")
                    ],
                    "to_vertex_collections": [
                        self.app_config.get_collection_name("classes")
                    ]
                },
```

```247:295:src/data_generation/taxonomy_generator.py
    def generate_device_classifications(self, device_proxy_outs: List[Dict[str, Any]],
                                      tenant_id: str) -> List[Dict[str, Any]]:
        """
        Generate type edges classifying each device.

        The classification is anchored at the **DeviceProxyOut** -- the
        stable per-device identity -- not at any particular versioned
        Device document. This way a single classification survives
        configuration changes and historical-version TTL aging, instead
        of producing one orphan type-edge per version retired.
        ...
```

### Why

Anchoring at the versioned entity has two failure modes that grow with
time and tenant count:

1. **Orphan explosion under TTL.** If a `type` edge points at
   `Device/<tenant>:device12-3`, then when version `-3` is TTL-aged out,
   the edge points at nothing. With `N` versions per device aged out per
   day, the edge collection's "live" fraction drops fast. We saw 83% of
   `type` edges become orphans within a week of normal version churn
   (see `tools/repair_type_edges.py`).
2. **Reclassification on every config change.** A single firewall-rule
   tweak should not change what kind of device it is. Anchoring at the
   versioned doc forces you to either re-emit the classification on every
   write (write amplification) or accept stale orphans.

Anchoring at the `*ProxyOut` solves both: the proxy is permanent, the
classification is one row per logical entity, and the proxy already
participates in the SmartGraph (same `tenantId`), so the index-pruned
traversal in P3 still works.

### Cost rationale

There is no extra storage cost relative to the versioned-anchor model --
in fact there is *less*, because we emit one type edge per logical
entity rather than one per version. The architectural change is purely
in *what* we point at.

### Caveat: traversing from `Class` down to current `Device` takes two hops

In the proxy-anchored model, a traversal that wants the current
configuration must walk `type` (cls -> proxy) and then `hasVersion`
(proxy -> versioned). In ArangoDB 3.12.x cluster mode, do **not** express
this as two nested `FOR ... INBOUND` traversals -- that combination trips
an internal `SingleServerEdgeCursor` optimizer bug. Use the single
multi-edge form:

```aql
FOR cls IN Class FILTER cls.name == @className
  FOR v, e, p IN 2..2 INBOUND cls type, hasVersion
    FILTER LENGTH(p.edges) == 2
    FILTER p.edges[0].tenantId == @tenantId      // engages idx_type_to_tenantid
    FILTER IS_SAME_COLLECTION('Device', v)
    FILTER v.expired == 9223372036854775807       // current version only
    RETURN v
```

### Anti-pattern

Anchoring `type` (or any other long-lived classification / annotation /
membership edge) at a versioned entity. You will accumulate orphans at
the rate of version churn, and a single config edit will reclassify the
device.

---

## Putting it all together — what does a "good" tenant query look like?

```aql
// "Show me every Apache server in tenant abc, with its current alerts."
//
// IMPORTANT: in ArangoDB 3.12.x cluster mode, chaining a satellite-bridge
// `INBOUND ... type` traversal with a *separate* nested `INBOUND ... hasVersion`
// traversal trips an internal cursor optimizer bug ("index conditions in
// SingleServerEdgeCursor should not be empty"). Use the single multi-edge
// traversal form below to walk type+hasVersion in one step instead.
WITH Class, SoftwareProxyOut, Software, hasVersion, hasAlert, Alert, type
FOR c IN Class
  FILTER c.classKey == "apache_http_server"
  // P3+P4: tenant-pruned satellite-to-tenant traversal (idx_type_to_tenantid).
  // hop 1 = type (cls -> SoftwareProxyOut), hop 2 = hasVersion (proxy -> Software)
  FOR sw, e, p IN 2..2 INBOUND c type, hasVersion
    FILTER LENGTH(p.edges) == 2
    FILTER p.edges[0].tenantId == "abc"
    FILTER IS_SAME_COLLECTION("Software", sw)
    FILTER sw.expired == 9223372036854775807
    // The proxy is the second-to-last vertex on the path; it's the natural
    // attachment point for hasAlert (P4) since hasAlert (_from, _toType) is
    // anchored at the proxy.
    LET po = p.vertices[1]
    FOR alert IN OUTBOUND po hasAlert
      FILTER alert.expired == 9223372036854775807
      RETURN { sw: sw.name, alert: alert._key, severity: alert.severity }
```

> **Note on the path filter:** when `c` is a satellite vertex (e.g. `Class`)
> and you want the planner to use `idx_type_to_tenantid`, the tenant filter
> must reference the **type edge specifically** (`p.edges[0].tenantId == @t`).
> Using `p.edges[*].tenantId ALL == @t` works for single-edge traversals but
> for multi-edge paths it would also constrain `hasVersion` (which doesn't
> need filtering -- proxies are already shard-local).

Every hop is either an index seek or a single-shard local read. Cost is
proportional to *that tenant's* Apache instances, not to the dataset.

---

## How to verify this on your own data

The repo ships two tools:

- `tools/inspect_satellite_edges.py` — inventory of `tenantId` /
  `_fromType` / `_toType` coverage and which indexes exist on each
  satellite-bridge edge collection.
- `tools/verify_vertex_centric_index_use.py` — runs `EXPLAIN` on the four
  canonical query shapes (good / suboptimal × direct / traversal) and
  prints which indexes the planner picked.

A scaling-characteristics benchmark ships separately as
`tools/benchmark_tenant_scaling.py` (invoked via `make demo-scaling`).
It builds an isolated `bench_*` schema mirroring the production patterns,
seeds `T × 50` synthetic rows, and runs two query shapes against the same
data:

- **GOOD** — the path-filter idiom, which engages `idx_type_to_tenantid`.
- **ANTI** — filtering on the *target vertex's* `tenantId`, which doesn't.

Sample run on a 3-DB-server cloud cluster (median of 5 runs, M=8 satellite
classes, 50 software/tenant):

| #tenants | GOOD (ms) | ANTI (ms) | ANTI / GOOD |
|---------:|----------:|----------:|------------:|
|       50 |       189 |       193 |        1.0× |
|      500 |       185 |       212 |        1.1× |
|    2,500 |       190 |       307 |        1.6× |

GOOD stays flat — its cost is dominated by the round-trip latency to the
cluster. ANTI's growth is linear in the number of incident edges per
class (~`T / M`), as expected.

To reproduce:

```bash
make demo-scaling                          # runs 10, 100, 1000 by default
STEPS=100,1000,5000 make demo-scaling      # opt into a heavier sweep
make demo-scaling-clean                    # drop the bench_* collections
```

---

## Operational caveats and trade-offs

### Caveat 1 — Redundant data must be kept consistent

`tenantId` on the bridge edge duplicates the `tenantId` on the SmartGraph
endpoint. If they ever drift, a tenant query on the bridge edge will see
stale results. Mitigations:

- **Generation path**: the edge is built atomically with the endpoint in
  the same generator step (`_create_type_edge` and friends). There is no
  "set tenantId later" code path.
- **Migration path**: when you change a vertex's tenantId, treat all
  bridge edges as well. (We don't expect this to happen in production —
  tenants are immutable identities — but for completeness.)
- **Verification path**: a periodic batch job can join edges to endpoints
  and assert equality; a single mismatch is loud.

### Caveat 2 — Satellite collections cost RAM on every DB-server

Each DB-server holds the full satellite. A 200 MB taxonomy with 10
DB-servers costs 2 GB of redundant storage. That's the price of join
locality. Past ~1 GB per satellite collection, reconsider whether all of
that data is truly tenant-agnostic.

### Caveat 3 — The path-filter idiom is non-obvious

`FILTER p.edges[*].tenantId ALL == @tenantId` looks like it should be
equivalent to `FILTER e.tenantId == @tenantId`. Semantically they are; for
the optimizer they are not (in current ArangoDB versions). This is the
single most likely failure mode for a developer who is implementing this
pattern from memory. The AQL skill in this repo
(`.cursor/skills/aql/SKILL.md`) makes the difference explicit, and
`tools/verify_vertex_centric_index_use.py` will catch a regression.

### Caveat 4 — Index churn on hot edge collections

Each new vertex-centric index costs write amplification on its edge
collection. For `type` (~1 edge per (device|software, classification)) the
write rate is low and the trade is excellent. For a `clickStream`-style
edge collection with millions of writes per minute you would want fewer
indexes and probably a different model (TTL-aged buckets).

---

## Reference: file map

| Concern                              | File                                               |
|--------------------------------------|----------------------------------------------------|
| SmartGraph creation, `smart_field`   | `src/database/database_deployment.py:476-483`      |
| Satellite collections                | `src/database/database_deployment.py:111-141`      |
| Index strategy (all five patterns)   | `src/database/database_deployment.py:156-215`      |
| Proxy-anchored `type` edge definition (P5)         | `src/database/database_deployment.py:451-463`      |
| `tenantId` + `_fromType`/`_toType` on `type` edges (proxy-anchored) | `src/data_generation/taxonomy_generator.py:247-343` |
| `tenantId` + `_fromType`/`_toType` on `hasAlert` edges | `src/data_generation/alert_generator.py`           |
| AQL idiom (path filter + multi-edge bug workaround) | `.cursor/skills/aql/SKILL.md`                      |
| Verifier                             | `tools/verify_vertex_centric_index_use.py`         |
| Live-data repair tool (one-off, orphan cleanup)    | `tools/repair_type_edges.py`                       |
| Live migration to proxy anchoring (one-off, P5)    | `tools/migrate_type_anchor_to_proxy.py`            |
| Vertex-centric backfill              | `tools/apply_tenantid_vertex_centric_indexes.py`   |
| Scaling benchmark                    | `tools/benchmark_tenant_scaling.py`                |

---

## Further reading

- ArangoDB SmartGraph docs:
  <https://docs.arangodb.com/stable/graphs/smartgraphs/>
- ArangoDB SatelliteGraph / SatelliteCollection docs:
  <https://docs.arangodb.com/stable/graphs/satellitegraphs/>
- Vertex-centric indexes in AQL traversals:
  <https://docs.arangodb.com/stable/index-and-search/indexing/working-with-indexes/vertex-centric-indexes/>
