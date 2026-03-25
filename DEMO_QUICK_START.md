# Demo Quick Start - One Page Guide
**Multi-Tenant Temporal Graph Demo**

---

## Start Demo

```bash
# 1. Go to project and install dependencies
cd /path/to/network-asset-management-demo
pip install -r requirements.txt

# 2. Set credentials (first time: cp environment_variables.example setup_env.sh, then edit)
source setup_env.sh

# 3. Run demo
make demo
```

**That's it!** Press Enter at each pause to advance through the demo.

> **First time?** `setup_env.sh` is not in git. Create it:
> `cp environment_variables.example setup_env.sh`, edit with your ArangoDB Oasis
> credentials, then `source setup_env.sh`.

---

## Demo Timeline (15-20 minutes)

| Section | Time | What Happens |
|---------|------|--------------|
| 0. Reset | 1 min | Clean database |
| 1. Data Gen | 2-3 min | Generate 8 tenants, 21K+ docs |
| 2. Deploy | 2-3 min | SmartGraphs + indexes |
| 3. Validate | 1 min | Check system health |
| 4. Transactions | 2 min | TTL demo |
| 5. Time Travel | 2 min | Historical queries |
| 6-7. Features | 2 min | Alerts + taxonomy |
| 8. Scale-Out | 3 min | Add tenants |
| 9. Final | 1 min | Validation |

---

## ArangoDB Web UI

**URL**: Your cluster endpoint (from `$ARANGO_ENDPOINT`)
**Database**: Your database name (from `$ARANGO_DATABASE`)
**Credentials**: In `setup_env.sh`

### What to Show:
1. **Collections** -> See all vertex/edge collections
2. **Graphs** -> Visualize network topology
3. **Queries** -> Run time travel queries

---

## Key Talking Points

### Multi-Tenancy
- "8 tenants with complete data isolation"
- "21,000+ documents across shared collections"
- "Physical partitioning via SmartGraph sharding"

### Time Travel
- "Query system state at any point in time"
- "MDI indexes optimize temporal queries"
- "Critical for compliance and auditing"

### Performance
- "Queries complete in ~0.1 seconds"
- "MDI-prefixed indexes on created/expired"
- "30/30 tests passing, production ready"

### Scalability
- "Linear scaling with tenant count"
- "Zero downtime tenant addition"
- "Automatic shard rebalancing"

---

## Show in Browser

### Time Travel Query Example:
```aql
FOR device IN Device
  FILTER device.created <= @point_in_time 
  AND device.expired > @point_in_time
  LIMIT 10
  RETURN device
```

### Check MDI Indexes:
1. Collections -> Device -> Indexes tab
2. Look for: `idx_device_mdi_temporal`
3. Type: `mdi-prefixed` on `[created, expired]`

---

## Troubleshooting

**"Connection failed"**
-> Run: `source setup_env.sh`

**"Module not found"**
-> Use: `PYTHONPATH=.` prefix

**"Demo is slow"**
-> Normal! 21K docs takes 2-3 min

---

## Pre-Demo Checklist

- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Environment variables set (`source setup_env.sh`)
- [ ] Browser open to ArangoDB UI
- [ ] Tests passing: `make test`
- [ ] Backup internet available

---

## Success Criteria

Demo is successful when you have shown:
- Multi-tenant data generation and isolation
- SmartGraph deployment with MDI indexes
- Time travel queries with temporal filtering
- Validation passing across all checks
- Scale-out with zero-downtime tenant addition

---

## Opening Line

*"Today I'm demonstrating a production-ready reference implementation for multi-tenant temporal graph databases. We'll show complete tenant isolation, time travel capabilities, and horizontal scalability using ArangoDB SmartGraphs. Let's start by generating data for 8 tenants..."*

---

**Detailed guide**: See `docs/PRESENTER_GUIDE.md` for full walkthrough with talking points.
