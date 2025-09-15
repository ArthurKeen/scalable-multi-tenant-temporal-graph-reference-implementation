# Current vs Historical TTL Strategy - Implementation Plan

## Executive Summary

**Goal**: Implement TTL-based time travel demonstration using a **"Current vs Historical"** strategy where only historical configurations age out automatically, while current configurations remain permanently available.

## TTL Strategy: Current vs Historical

### **Core Principle**
- **Current Configurations**: `expired = sys.maxsize` (never age out, no TTL)
- **Historical Configurations**: `expired = actual_timestamp` (age out with TTL)

### **Benefits**
- ✅ **Current configs always available** for operational queries
- ✅ **Historical configs age out automatically** for demo cleanup
- ✅ **Realistic operational pattern** (current vs archived data)
- ✅ **Time travel queries work perfectly** across both types

## Current Implementation Analysis

### ✅ **PERFECT: Data Generator Already Implements This Strategy**

**Current Configurations (Never Expire):**
```python
# From TemporalDataModel.add_temporal_attributes() line 198:
enhanced_doc["expired"] = sys.maxsize  # Always use largest possible value
```

**Historical Configurations (Expire When Replaced):**
```python
# From _generate_historical_device_configurations() line 240:
expired = previous_config["created"]  # Historical records expire when replaced
```

### **Impact on Initial Data Generation: MINIMAL**

The current data generator **already creates the perfect data structure**:
- ✅ Current device/software configs: `expired = sys.maxsize`
- ✅ Historical device/software configs: `expired = <replacement_timestamp>`
- ✅ All version edges follow the same pattern
- ✅ Time travel queries work correctly

## Required Changes

### **1. TTL Index Configuration (NEW)**
```python
# Only apply TTL to documents where expired != sys.maxsize
def create_selective_ttl_index(collection_name: str, ttl_seconds: int):
    \"\"\"Create TTL index that only affects historical documents.\"\"\"
    return {
        "type": "ttl",
        "fields": ["expired"],
        "expireAfter": 0,  # Expire when expired timestamp is reached
        "selectivityEstimate": 0.1,  # Only ~10% of docs are historical
        "sparse": True  # Skip documents where expired = sys.maxsize
    }
```

### **2. Transaction Simulation Infrastructure (NEW)**
```python
def simulate_configuration_change(entity_type: str, proxy_key: str, new_config: Dict):
    \"\"\"Simulate a real-world configuration change.\"\"\"
    # 1. Find current configuration
    current_config = find_current_config(entity_type, proxy_key)
    
    # 2. Convert current to historical (set real expired timestamp)
    current_config["expired"] = datetime.now().timestamp()
    # TTL will now apply to this document
    
    # 3. Create new current configuration
    new_config["expired"] = sys.maxsize  # Never expires (current)
    # No TTL on current config
    
    # 4. Update version edges accordingly
    update_version_edges(proxy_key, current_config["_key"], new_config["_key"])
```

### **3. TTL Activation Strategy (NEW)**
```python
# Enable TTL only for tenant configurations that opt-in
@dataclass
class TenantConfig:
    # ... existing fields ...
    ttl_enabled: bool = True  # Enable TTL for historical documents
    ttl_expire_after_days: int = 30  # Age out historical configs after 30 days
    preserve_current_configs: bool = True  # Never age out current configs
```

## Implementation Phases

### **Phase 1: TTL Index Implementation** (1-2 days)
1. **Enable TTL in tenant configuration**
2. **Create selective TTL indexes** (historical documents only)
3. **Test TTL behavior** with existing historical data
4. **Verify current configs never expire**

### **Phase 2: Transaction Simulation** (2-3 days)
1. **Create transaction simulator module**
2. **Implement configuration change simulation**
3. **Add realistic change scenarios** (software updates, device reconfigs)
4. **Test current → historical → TTL aging flow**

### **Phase 3: Demo Scenarios** (1-2 days)
1. **Create compelling demo scripts**
2. **Show time travel before/after changes**
3. **Demonstrate automatic aging of historical data**
4. **Validate current configs remain available**

## Demo Flow Example

```python
# 1. Initial state: Current config (never expires)
device_config = {
    "_key": "device_001",
    "hostName": "server-prod-01",
    "created": 1640995200,  # Jan 1, 2022
    "expired": sys.maxsize  # Never expires
}

# 2. Simulate configuration change
new_config = simulate_device_update(device_config, {"hostName": "server-prod-01-v2"})

# Result:
# - Old config: expired = 1672531200 (Jan 1, 2023) → Will age out via TTL
# - New config: expired = sys.maxsize → Current, never ages out

# 3. Time travel queries work across both:
# - Query at Jan 15, 2022: Returns old config
# - Query at Jan 15, 2023: Returns new config
# - Query at "now": Returns new config (old config aged out)
```

## Key Advantages

1. **Zero Impact on Current Data Generation**: Existing generator already creates perfect data structure
2. **Realistic Operational Pattern**: Mirrors real-world current vs archived data management
3. **Selective TTL**: Only historical documents age out, current configs always available
4. **Perfect Time Travel**: Queries work seamlessly across current and historical data
5. **Demo-Friendly**: Clear before/after scenarios with automatic cleanup

## Next Steps

1. ✅ **Analyze current data generation** (COMPLETED)
2. 🔄 **Update TTL configuration system** (IN PROGRESS)
3. ⏳ **Implement selective TTL indexes**
4. ⏳ **Create transaction simulation infrastructure**
5. ⏳ **Build compelling demo scenarios**
