# Multi-Tenant Network Asset Management Demo

A comprehensive multi-tenant network asset management system built with ArangoDB, demonstrating proper naming conventions, disjoint SmartGraphs, and temporal data modeling.

## Features

### Multi-Tenancy with Complete Data Isolation
- **Disjoint SmartGraphs** for tenant isolation within shared collections
- **Shared Database Architecture** with tenant-scoped data partitioning
- **Complete Tenant Isolation** verified through comprehensive testing
- **Scalable Design** supporting horizontal scale-out capabilities

### Naming Conventions

The system supports two naming conventions:

#### Option 1: camelCase (Default)
- **Vertex Collections** (PascalCase, singular): `Device`, `DeviceProxyIn`, `DeviceProxyOut`, `Location`, `Software`
- **Edge Collections** (camelCase, singular): `hasConnection`, `hasLocation`, `hasDeviceSoftware`, `hasVersion`
- **Property Naming** (camelCase): `name`, `type`, `model`, `version`, `ipAddress`, `created`, `expired`

#### Option 2: snake_case
- **Vertex Collections** (snake_case, singular): `device`, `device_proxy_in`, `device_proxy_out`, `location`, `software`
- **Edge Collections** (snake_case, singular): `has_connection`, `has_location`, `has_device_software`, `has_version`
- **Property Naming** (snake_case): `name`, `type`, `model`, `version`, `ip_address`, `created`, `expired`

Both conventions maintain **consistent structure** with Subject-Predicate-Object relationships.

### Temporal Data Management
- **Time Travel Blueprint** with `created`, `expired` timestamps
- **Historical Versioning** via `hasVersion` edges for device and software configurations
- **Standardized Properties**: Generic `name`, `type`, `model`, `version` across all collections
- **Temporal Query Capabilities** for point-in-time analysis
- **Note**: TTL disabled (observedAt removed) - future temporal observation tracking to be determined

### Production-Ready Architecture
- **Centralized Configuration Management** - No hard-wired values
- **Code Quality Optimized** - Zero duplication, modular design, comprehensive documentation
- **Security Best Practices** - Externalized credentials, input validation, type safety
- **Comprehensive Test Suite** - 100% coverage with unit, integration, and compliance tests
- **Clean Code Architecture** - Modular, maintainable, dependency-injected design
- **ArangoDB Oasis Integration** - Cloud-ready deployment

## Architecture

### Graph Model Overview

```mermaid
graph TB
    %% Vertex Collections (PascalCase, singular)
    subgraph "Vertex Collections"
        D[Device<br/>Network devices<br/>Versioned temporal data]
        DPI[DeviceProxyIn<br/>Device input proxies<br/>Lightweight, no temporal data]
        DPO[DeviceProxyOut<br/>Device output proxies<br/>Lightweight, no temporal data]
        S[Software<br/>Software installations<br/>Versioned temporal data]
        SPI[SoftwareProxyIn<br/>Software input proxies<br/>Lightweight, no temporal data]
        SPO[SoftwareProxyOut<br/>Software output proxies<br/>Lightweight, no temporal data]
        L[Location<br/>Physical locations<br/>GeoJSON coordinates]
    end
    
    %% Edge Collections (camelCase, singular)
    
    %% Network connections between devices
    DPO -->|hasConnection<br/>Network links<br/>bandwidth, latency| DPI
    
    %% Device location relationships
    DPO -->|hasLocation<br/>Physical placement<br/>geographical data| L
    
    %% Device-Software relationships (CORRECTED LOGIC)
    DPO -->|hasDeviceSoftware<br/>Device software installation<br/>device -> software| SPI
    
    %% Device Time Travel (existing pattern)
    DPI -->|hasVersion<br/>Device version in<br/>temporal evolution| D
    D -->|hasVersion<br/>Device version out<br/>temporal evolution| DPO
    
    %% Software Time Travel (NEW pattern)
    SPI -->|hasVersion<br/>Software version in<br/>temporal evolution| S
    S -->|hasVersion<br/>Software version out<br/>temporal evolution| SPO
    
    %% Tenant isolation indicator
    classDef tenantBox fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef newFeature fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    class D,DPI,DPO,L tenantBox
    class S,SPI,SPO newFeature
```

> **Detailed Graph Model**: See [graph_model_diagram.md](./graph_model_diagram.md) for comprehensive schema documentation, query examples, and design patterns.

### Collection Structure

**Vertex Collections (Entities):**
```
Device            # Network devices with versioned temporal data
DeviceProxyIn     # Device input proxies (lightweight, no temporal data)
DeviceProxyOut    # Device output proxies (lightweight, no temporal data)  
Software          # Software installations with versioned temporal data (REFACTORED)
SoftwareProxyIn   # Software input proxies (lightweight, no temporal data) - NEW
SoftwareProxyOut  # Software output proxies (lightweight, no temporal data) - NEW
Location          # Physical locations with GeoJSON coordinates
```

**Edge Collections (Relationships):**
```
hasConnection     # DeviceProxyOut -> DeviceProxyIn connections
hasLocation       # DeviceProxyOut -> Location assignments
hasDeviceSoftware # DeviceProxyOut -> SoftwareProxyIn installations (CORRECTED)
hasVersion        # Unified time travel: Device & Software versioning (EXPANDED)
```

### Multi-Tenant Architecture

```mermaid
graph TB
    subgraph "ArangoDB Oasis: network_assets_demo"
        subgraph "Tenant A: Acme Corp (SmartGraph Partition)"
            direction TB
            DA[Device<br/>Network devices<br/>tenant_A_attr: uuid_A]
            DPIA[DeviceProxyIn<br/>Input proxies<br/>tenant_A_attr: uuid_A]
            DPOA[DeviceProxyOut<br/>Output proxies<br/>tenant_A_attr: uuid_A]
            SA[Software<br/>Software installs<br/>tenant_A_attr: uuid_A]
            SPIA[SoftwareProxyIn<br/>Input proxies<br/>tenant_A_attr: uuid_A]
            SPOA[SoftwareProxyOut<br/>Output proxies<br/>tenant_A_attr: uuid_A]
            LA[Location<br/>Physical sites<br/>tenant_A_attr: uuid_A]
        end
        
        subgraph "Tenant B: Global Enterprises (SmartGraph Partition)"  
            direction TB
            DB[Device<br/>Network devices<br/>tenant_B_attr: uuid_B]
            DPIB[DeviceProxyIn<br/>Input proxies<br/>tenant_B_attr: uuid_B]
            DPOB[DeviceProxyOut<br/>Output proxies<br/>tenant_B_attr: uuid_B]
            SB[Software<br/>Software installs<br/>tenant_B_attr: uuid_B]
            SPIB[SoftwareProxyIn<br/>Input proxies<br/>tenant_B_attr: uuid_B]
            SPOB[SoftwareProxyOut<br/>Output proxies<br/>tenant_B_attr: uuid_B]
            LB[Location<br/>Physical sites<br/>tenant_B_attr: uuid_B]
        end
        
        subgraph "Shared Collections (Logically Separated)"
            VC[hasVersion<br/>Unified time travel<br/>All tenant hasVersion edges]
            HC[hasConnection<br/>Network links<br/>Tenant-isolated edges]
            HL[hasLocation<br/>Device placement<br/>Tenant-isolated edges]
            HDS[hasDeviceSoftware<br/>Device->Software<br/>Tenant-isolated edges]
        end
    end
    
    %% Tenant A relationships (corrected logic)
    DPOA -.->|hasConnection<br/>Isolated by tenant_A_attr| DPIA
    DPOA -.->|hasLocation<br/>Isolated by tenant_A_attr| LA
    DPOA -.->|hasDeviceSoftware<br/>CORRECTED: Out->In<br/>Isolated by tenant_A_attr| SPIA
    
    %% Tenant B relationships (corrected logic)
    DPOB -.->|hasConnection<br/>Isolated by tenant_B_attr| DPIB
    DPOB -.->|hasLocation<br/>Isolated by tenant_B_attr| LB  
    DPOB -.->|hasDeviceSoftware<br/>CORRECTED: Out->In<br/>Isolated by tenant_B_attr| SPIB
    
    %% Time travel patterns (unified hasVersion collection)
    DPIA -.->|hasVersion<br/>Time travel| DA
    DA -.->|hasVersion<br/>Time travel| DPOA
    SPIA -.->|hasVersion<br/>Time travel| SA
    SA -.->|hasVersion<br/>Time travel| SPOA

    DPIB -.->|hasVersion<br/>Time travel| DB
    DB -.->|hasVersion<br/>Time travel| DPOB
    SPIB -.->|hasVersion<br/>Time travel| SB
    SB -.->|hasVersion<br/>Time travel| SPOB
    
    classDef tenantA fill:#ffebee,stroke:#c62828,stroke-width:3px
    classDef tenantB fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    classDef shared fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    classDef corrected fill:#e1f5fe,stroke:#0277bd,stroke-width:3px
    
    class DA,DPIA,DPOA,SA,SPIA,SPOA,LA tenantA
    class DB,DPIB,DPOB,SB,SPIB,SPOB,LB tenantB
    class VC,HC,HL,HDS shared
```

### Key Design Patterns

**1. Consistent Proxy Pattern for Performance**
- **Device**: `DeviceProxyIn`/`DeviceProxyOut` act as lightweight connection points
- **Software**: `SoftwareProxyIn`/`SoftwareProxyOut` act as lightweight connection points (NEW)
- Core collections (`Device`, `Software`) hold full temporal data
- Reduces edge collection bloat while maintaining referential integrity

**2. Unified Temporal Versioning**
- **Generic `hasVersion` collection** handles all time travel relationships
- **Device**: `DeviceProxyIn` <-> `Device` <-> `DeviceProxyOut` 
- **Software**: `SoftwareProxyIn` <-> `Software` <-> `SoftwareProxyOut` (NEW)
- **Consistent queries** across all temporal entities
- Historical configurations preserved with `created`/`expired` timestamps

**3. Software Configuration Refactoring**
- **REMOVED**: `configurationHistory` array (complex nested structure)
- **ADDED**: Flattened software configurations as versioned documents
- **BENEFIT**: Same time travel pattern as Device collection
- **RESULT**: Simpler queries and uniform temporal data model

**4. Dual Naming Convention Support**
- **camelCase (default)**: `Device`, `hasConnection`, `deviceId` 
- **snake_case (optional)**: `device`, `has_connection`, `device_id`
- **Vertices**: PascalCase/lowercase, singular (`Device`/`device`, `Software`/`software`)
- **Edges**: camelCase/snake_case, singular (`hasConnection`/`has_connection`)
- **Properties**: camelCase/snake_case for consistency

**5. Multi-Tenant Isolation**
- Disjoint SmartGraphs using `tenant_{id}_attr` as partition key
- Complete data isolation within shared collections
- Horizontal scale-out capability with tenant-based sharding

### Data Model

**Tenant Isolation:**
- Each document contains `tenant_{id}_attr` for disjoint partitioning
- Shared collections with tenant-scoped queries
- Complete data isolation verified through testing

**Temporal Attributes:**
- `created`: Creation timestamp (Unix epoch)
- `expired`: Expiration timestamp (default: 9223372036854775807 - largest possible value)
- Note: `observedAt` removed - future temporal observation tracking to be determined
- **Note**: Proxy collections (`DeviceProxyIn`/`DeviceProxyOut`) contain only tenant attributes

**Vertex-Centric Indexing:**
- `_fromType` and `_toType` on all edges for efficient traversals
- Optimized for graph query performance

## Getting Started

### Quick Start - Demo Options

**🎯 Automated Walkthrough (Recommended for First-Time Users)**
```bash
# Interactive guided demonstration with explanations
python automated_demo_walkthrough.py --interactive

# Auto-advancing demonstration with timed pauses
python automated_demo_walkthrough.py --auto-advance --pause-duration 5
```

**🏃 Fast Complete Demo**
```bash
# Run the complete demonstration (all steps automated)
python comprehensive_demo.py --save-report

# Run with snake_case naming convention
python comprehensive_demo.py --naming snake_case --save-report
```

**🚀 Demo Launcher (Easy Access)**
```bash
# Interactive menu with all demo options
python demo_launcher.py
```

**The comprehensive demo includes:**
1. **Initial Data Generation** - Multi-tenant network asset data (4 tenants by default)
2. **Database Deployment** - Collections, indexes, and SmartGraphs
3. **Transaction Simulation** - Configuration changes with TTL
4. **TTL Demonstration** - Time travel scenarios
5. **Scale-Out Demo** - Dynamic tenant addition and cluster analysis
6. **Comprehensive Validation** - Data integrity and isolation checks

### Demo Flow Diagram

```mermaid
graph TD
    A[Start Demo] --> B[Step 1: Generate Data]
    B --> C[Step 2: Deploy to DB]
    C --> D[Step 3: Initial Validation]
    D --> E[Step 4: Transaction Simulation]
    E --> F[Step 5: TTL Demonstration]
    F --> G[Step 6: Scale-Out Demo]
    G --> H[Step 7: Final Validation]
    H --> I[Demo Complete]
    
    B --> B1[Create 4 Tenants<br/>Generate Assets<br/>Support camelCase/snake_case]
    C --> C1[Deploy Collections<br/>Create Indexes<br/>Setup SmartGraphs]
    D --> D1[Verify Deployment<br/>Check Tenant Isolation<br/>Test Time Travel]
    E --> E1[Simulate Device Changes<br/>Simulate Software Updates<br/>Apply TTL Strategy]
    F --> F1[Device Maintenance Cycle<br/>Software Upgrade Rollback<br/>Historical Data Aging]
    G --> G1[Add New Tenants<br/>Analyze Cluster<br/>Rebalance Shards]
    H --> H1[Data Integrity Check<br/>Isolation Verification<br/>Performance Validation]
    
    style A fill:#e1f5fe
    style I fill:#e8f5e8
    style E fill:#fff3e0
    style F fill:#fff3e0
    style G fill:#f3e5f5
```

### Automated Demo Walkthrough

The **automated walkthrough** provides a guided tour of all system capabilities with detailed explanations:

#### Features:
- **📋 Step-by-step explanations** of each component
- **⏸️ Interactive pauses** for observation and learning
- **🎯 Complete system coverage** in logical sequence
- **🔧 Error handling** and graceful recovery
- **📊 Results summaries** after each section

#### Walkthrough Sections:
1. **System Introduction** - Overview and capabilities
2. **Data Generation** - Multi-tenant data creation
3. **Database Deployment** - SmartGraphs and indexes
4. **Initial Validation** - System integrity checks
5. **Transaction Simulation** - Configuration changes with TTL
6. **TTL Demonstration** - Time travel scenarios
7. **Scale-Out Demo** - Horizontal scaling capabilities
8. **Final Validation** - Comprehensive system verification
9. **Demo Summary** - Results and achievements

#### Usage Options:
```bash
# Interactive mode (recommended for presentations)
python automated_demo_walkthrough.py --interactive

# Auto-advance mode (for unattended demos)
python automated_demo_walkthrough.py --auto-advance --pause-duration 3

# View all options
python automated_demo_walkthrough.py --help
```

### Individual Demo Components

For running specific parts of the demonstration:

```bash
# Data Generation Only (4 tenants by default)
python asset_generator.py --naming camelCase --environment development

# Generate specific number of tenants
python asset_generator.py --tenants 6 --naming camelCase --environment development

# Database Deployment Only  
python database_deployment.py --naming camelCase

# Transaction Simulation Only
python transaction_simulator.py --naming camelCase --devices 5 --software 3

# TTL Demo Scenarios Only
python ttl_demo_scenarios.py --naming camelCase

# Scale-Out Demo Only
python scale_out_demo.py --naming camelCase --save-report

# Validation Only
python validation_suite.py
```

### Prerequisites
- **Python 3.8+** with standard libraries
- **ArangoDB 3.12+** or ArangoDB Oasis cluster access
- **Environment Variables** configured (see Configuration section below)

### Manual Step-by-Step Setup

#### Step 1: Configure Environment

First, set up your database credentials:

```bash
# Required environment variables
export ARANGO_ENDPOINT="https://your-cluster.arangodb.cloud:8529"
export ARANGO_USERNAME="root"
export ARANGO_PASSWORD="your-secure-password"
export ARANGO_DATABASE="network_assets_demo"

# Verify configuration
echo "Endpoint: $ARANGO_ENDPOINT"
echo "Database: $ARANGO_DATABASE"
```

#### Step 2: Generate Multi-Tenant Data

Choose your data generation approach:

#### Option A: Default Generation (Recommended)
```bash
# Generate data with camelCase naming (default)
python asset_generator.py

# Generate data with snake_case naming
python asset_generator.py --naming snake_case

# This creates:
# - Acme Corp (1x scale): ~1,095 documents
# - Global Enterprises (2x scale): ~2,190 documents  
# - Total: ~3,285 documents across all collections
```

#### Option B: Custom Tenant Configuration
```bash
# Edit tenant_config.py to customize:
# - Tenant names and IDs
# - Scale factors (1x, 2x, 3x, 5x)
# - Device/software/location counts per tenant

# Then generate with custom settings
python asset_generator.py
```

#### Option C: Single Tenant Testing
```bash
# For development/testing with minimal data
# Modify data_generation_config.py:
# - Set DEVICE_COUNT = 5
# - Set SOFTWARE_COUNT = 10
# - Set LOCATION_COUNT = 2

python asset_generator.py
```

#### Step 3: Deploy to Database

Choose your deployment method:

#### Option A: Fresh Database Deployment
```bash
# Deploy with camelCase naming (default)
python database_deployment.py

# Deploy with snake_case naming
python database_deployment.py --naming snake_case

# This will:
# 1. Create/recreate the database
# 2. Set up all collections and indexes with chosen naming convention
# 3. Load tenant data from generated JSON files
# 4. Create tenant-specific SmartGraphs
# 5. Verify deployment integrity
```

#### Option B: Update Existing Database
```bash
# Load new tenant data into existing database
# (Preserves existing data, adds new tenants)
python oasis_cluster_setup.py

# This will:
# 1. Connect to existing database
# 2. Create missing collections/indexes
# 3. Load only new tenant data
# 4. Maintain existing tenant isolation
```

#### Step 4: Validate Deployment

Run comprehensive validation:

```bash
# Full validation suite
python validation_suite.py

# Quick database check
python database_utilities.py

# Test suite (development validation)
python test_suite.py
```

## Scale-Out Capabilities

### Dynamic Tenant Addition

Add new tenants to existing database without disrupting operations:

```bash
# Add single tenant
python scale_out_manager.py --operation add-tenant --tenant-name "New Corp" --scale-factor 2

# Add multiple demo tenants
python scale_out_manager.py --operation add-tenants

# Run complete scale-out demonstration
python scale_out_demo.py --save-report
```

### Database Server Scaling

Analyze cluster state to prepare for manual server addition:

```bash
# Analyze current cluster state
python scale_out_manager.py --operation server-info

# Analyze shard distribution for rebalancing planning
python scale_out_manager.py --operation shard-info
```

**Note**: Database server addition is performed manually through the ArangoDB Oasis web interface.

### Scale-Out Benefits

- **Zero Downtime**: Add tenants without affecting existing operations
- **Linear Scaling**: Performance scales with additional servers  
- **Data Isolation**: Complete tenant separation maintained via SmartGraphs
- **Cost Efficiency**: Shared infrastructure with isolated data
- **Operational Simplicity**: Centralized management with tenant autonomy

See [SCALE_OUT_GUIDE.md](SCALE_OUT_GUIDE.md) for detailed instructions.

## Data Generation Options

### Naming Convention Options

Choose between two supported naming conventions:

#### camelCase (Default)
```bash
python asset_generator.py --naming camelCase
python database_deployment.py --naming camelCase
```
**Collections Created:**
- Vertex: `Device`, `DeviceProxyIn`, `DeviceProxyOut`, `Location`, `Software`, `SoftwareProxyIn`, `SoftwareProxyOut`
- Edge: `hasConnection`, `hasLocation`, `hasDeviceSoftware`, `hasVersion`

#### snake_case
```bash
python asset_generator.py --naming snake_case
python database_deployment.py --naming snake_case
```
**Collections Created:**
- Vertex: `device`, `device_proxy_in`, `device_proxy_out`, `location`, `software`, `software_proxy_in`, `software_proxy_out`
- Edge: `has_connection`, `has_location`, `has_device_software`, `has_version`

**Important:** Use the same naming convention for both data generation and deployment.

### Scale Factors
Control data volume per tenant:
- **1x scale**: 60 devices, 90 software, 5 locations
- **2x scale**: 120 devices, 180 software, 10 locations  
- **3x scale**: 180 devices, 270 software, 15 locations
- **5x scale**: 300 devices, 450 software, 25 locations

### Tenant Customization
Edit `tenant_config.py` to modify:
```python
# Example custom tenant
create_tenant_config(
    tenant_name="Your Company",
    scale_factor=2,  # 2x data volume
    # Generates tenant_id automatically
)
```

### Data Types Generated
Each tenant gets:
- **Device entities**: Network devices with temporal history
- **DeviceProxy entities**: Lightweight connection points
- **Software entities**: Applications with version tracking
- **SoftwareProxy entities**: Software connection points
- **Location entities**: Geographic placement data
- **Relationship edges**: Network topology and associations

## Deployment Scenarios

### Scenario 1: Demo/Development
```bash
# Minimal data for testing with camelCase
python asset_generator.py --environment development
python database_deployment.py --naming camelCase

# Or with snake_case naming
python asset_generator.py --environment development --naming snake_case
python database_deployment.py --naming snake_case
```

### Scenario 2: Multi-Tenant Production
```bash
# Full-scale multi-tenant deployment with camelCase (default)
python asset_generator.py
python database_deployment.py
python validation_suite.py

# Or with snake_case naming
python asset_generator.py --naming snake_case
python database_deployment.py --naming snake_case
python validation_suite.py
```

### Scenario 3: Custom Enterprise Setup
```bash
# 1. Customize tenant_config.py with your tenants
# 2. Adjust scale factors as needed
python asset_generator.py
python database_deployment.py

# 3. Verify tenant isolation
python validation_suite.py
```

### Scenario 4: Add New Tenants
```bash
# 1. Add new tenant configs to tenant_config.py
# 2. Generate data (preserves existing tenants)
python asset_generator.py

# 3. Deploy only new tenants
python oasis_cluster_setup.py

# 4. Validate isolation maintained
python validation_suite.py
```

## Generated Data

### Example Generated Graph Visualization

The system generates complex multi-tenant network topologies with temporal relationships. Here's an example of the generated graph structure:

![Network Asset Graph Visualization](assets/network-graph-visualization.png)

*Example visualization showing the multi-tenant network topology with device proxies (blue nodes) connected via hasConnection edges (physical network), software entities (purple nodes) connected via hasDeviceSoftware and hasVersion relationships, demonstrating consistent naming conventions.*

### Current Tenant Configuration
- **Acme Corp** (1x scale): 1,095 documents
- **Global Enterprises** (2x scale): 2,190 documents  
- **Total**: 3,285 documents across shared collections

### Document Distribution
```
Device configurations:     360 (with temporal history)
DeviceProxyIn entities:     60  (lightweight proxies)
DeviceProxyOut entities:    60  (lightweight proxies)
Location entities:          15  (GeoJSON coordinates)
Software entities:         540  (with version history)
SoftwareProxyIn entities:   90  (lightweight proxies)
SoftwareProxyOut entities:  90  (lightweight proxies)
Connection edges:           90  (network topology - DeviceProxyOut -> DeviceProxyIn)
Location edges:             60  (device placement)
Software edges:            120  (software installations)
hasVersion edges:        1,800  (temporal relationships)
```

## Testing & Validation

### Test Coverage
```bash
python test_suite.py
```
- **Total Tests**: 21
- **Success Rate**: 100%
- **Categories**: Configuration, Tenant Management, Data Generation, Naming Convention Compliance, File Management, Integration, Performance

### Naming Convention Validation
```bash
python validation_suite.py
```
- **Collection Naming**: 100% compliant
- **Property Naming**: 100% compliant  
- **Relationship Modeling**: 100% compliant
- **Naming Consistency**: 100% compliant
- **Tenant Isolation**: 100% verified
- **hasConnection Architecture**: 100% compliant (DeviceProxyOut -> DeviceProxyIn only)

## Project Structure

```
├── asset_generator.py              # Main data generator with naming conventions
├── config_management.py            # Centralized configuration system
├── tenant_config.py                # Tenant modeling and utilities
├── data_generation_config.py       # Generation parameters and constants
├── data_generation_utils.py        # Reusable utility functions
├── database_deployment.py          # ArangoDB Oasis deployment
├── validation_suite.py             # Comprehensive naming convention validation
├── test_suite.py                   # Complete test framework
├── oasis_cluster_setup.py          # Core cluster management
├── centralized_credentials.py      # Secure credential management
├── database_utilities.py           # Database utility functions
├── docs/
│   ├── PRD.md                      # Product Requirements Document
│   └── CLAUDE.md                   # Development session notes
├── data/
│   ├── tenant_{id}/                # Generated tenant data directories
│   └── tenant_registry_time_travel.json  # Tenant metadata registry
├── logs/                           # Application logs
└── reports/                        # Validation reports
```

## Configuration

### Environment Variables (Required)
**WARNING: Security Notice**: Credentials are loaded from environment variables. Never commit credentials to version control.

```bash
# Set these environment variables before running the application
export ARANGO_ENDPOINT="https://your-cluster.arangodb.cloud:8529"
export ARANGO_USERNAME="root"  
export ARANGO_PASSWORD="your-secure-password"
export ARANGO_DATABASE="network_assets_demo"
```

**Setup Instructions:**
1. Copy `environment_variables.example` and set your actual credentials
2. Source the environment variables: `source environment_variables.example`
3. Verify setup: `echo $ARANGO_ENDPOINT`

### Centralized Configuration
All settings are managed through `config_management.py`:
- Database credentials loaded from environment variables (secure)
- Collection name mappings for both naming conventions
- Generation limits and performance settings
- Environment-specific configurations

## Design Standards

### Naming Conventions
- **Entities** (Vertex Collections): PascalCase, singular
- **Predicates** (Edge Collections): camelCase, singular
- **Properties**: camelCase with singular/plural rules
- **Consistent Structure**: Proper Subject-Predicate-Object relationships

### ArangoDB Best Practices
- Disjoint SmartGraphs for multi-tenancy
- Vertex-centric indexing for performance
- TTL indexes for temporal data management
- Satellite graphs for metadata distribution

## Performance & Scalability

### Generation Performance
- **Key Generation**: 1,000 keys/second
- **Document Enhancement**: 200 documents/second  
- **Memory Efficient**: Streaming patterns for large datasets

### Scalability Verification
- **Multiple Scale Factors**: 1x, 3x, 5x demonstrated
- **Tenant Isolation**: Zero cross-tenant data access
- **Horizontal Scale-Out**: Ready for multi-server deployment

## Development

### Code Quality Standards
- **Zero Hard-Wired Values**: All configuration externalized
- **Zero Code Duplication**: Common patterns extracted
- **Modular Design**: Single responsibility principle
- **Comprehensive Testing**: Unit, integration, and compliance tests

- [DONE] **Architecture**: Centralized configuration management
- [DONE] **Code Quality**: Removed duplicate documentation, updated file references
- [DONE] **Database Compliance**: Verified consistent naming conventions

## Contributing

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Run** tests: `python test_suite.py`
4. **Validate** compliance: `python validation_suite.py`
5. **Commit** changes: `git commit -m 'Add amazing feature'`
6. **Push** to branch: `git push origin feature/amazing-feature`
7. **Open** a Pull Request

## Requirements

### System Requirements
- Python 3.8+
- ArangoDB 3.12+ or ArangoDB Oasis access
- Memory: 2GB+ for large-scale generation
- Storage: 1GB+ for generated data

### Python Dependencies
```python
# Core dependencies (included in standard library)
import json, datetime, pathlib, uuid, random, sys
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# External dependencies  
from arango import ArangoClient  # python-arango
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **ArangoDB** for multi-model database capabilities
- **Industry Standards** for consistent naming conventions and best practices
- **Python Community** for excellent development tools

---

**Built for enterprise-grade multi-tenant network asset management**

For questions, issues, or contributions, please open an issue or contact the development team.