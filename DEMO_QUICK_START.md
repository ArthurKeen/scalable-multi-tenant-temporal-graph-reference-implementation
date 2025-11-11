# Demo Quick Start - One Page Guide
**Multi-Tenant Temporal Graph Demo**

---

## 🚀 Start Demo (3 Commands)

```bash
# 1. Go to project
cd /Users/arthurkeen/code/network-asset-management-demo

# 2. Set credentials
source setup_env.sh

# 3. Run demo
PYTHONPATH=. python3 demos/automated_demo_walkthrough.py --interactive
```

**That's it!** Press Enter at each pause to advance through the demo.

---

## ⏱️ Demo Timeline (15-20 minutes)

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

## 🌐 ArangoDB Web UI

**URL**: https://9c12006b5b1e.arangodb.cloud:8529  
**Database**: `disjoint-smartgraph-temporal-database`  
**Credentials**: In `setup_env.sh`

### What to Show:
1. **Collections** → See all vertex/edge collections
2. **Graphs** → Visualize network topology
3. **Queries** → Run time travel queries

---

## 💡 Key Talking Points

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
- "100% test coverage, production ready"

### Scalability
- "Linear scaling with tenant count"
- "Zero downtime tenant addition"
- "Automatic shard rebalancing"

---

## 🔍 Show in Browser

### Time Travel Query Example:
```aql
FOR device IN Device
  FILTER device.created <= @point_in_time 
  AND device.expired > @point_in_time
  LIMIT 10
  RETURN device
```

### Check MDI Indexes:
1. Collections → Device → Indexes tab
2. Look for: `idx_device_mdi_temporal`
3. Type: `mdi-prefixed` on `[created, expired]`

---

## ⚠️ Troubleshooting

**"Connection failed"**  
→ Run: `source setup_env.sh`

**"Module not found"**  
→ Use: `PYTHONPATH=.` prefix

**"Demo is slow"**  
→ Normal! 21K docs takes 2-3 min

---

## ✅ Pre-Demo Checklist

- [ ] Can access project directory
- [ ] Environment variables set (`source setup_env.sh`)
- [ ] Browser open to ArangoDB UI
- [ ] Tests passing: `PYTHONPATH=. python3 src/validation/test_suite.py`
- [ ] Backup internet available

---

## 🎯 Success Metrics

Demo is successful if you show:
- ✅ Multi-tenant data generation
- ✅ SmartGraph deployment
- ✅ Time travel queries
- ✅ 100% test validation
- ✅ Performance metrics

---

## 📞 Emergency Contacts

**Primary**: Arthur Keen  
**Docs**: See `DEMO_HANDOFF_GUIDE.md` for detailed walkthrough  
**Repo**: https://github.com/ArthurKeen/scalable-multi-tenant-temporal-graph-reference-implementation

---

## 🎬 Opening Line

*"Today I'm demonstrating a production-ready reference implementation for multi-tenant temporal graph databases. We'll show complete tenant isolation, time travel capabilities, and horizontal scalability using ArangoDB SmartGraphs. Let's start by generating data for 8 tenants..."*

---

**System Status**: ✅ All 30/30 tests passing (100%)  
**Ready for**: Production demos  
**Updated**: November 11, 2025

