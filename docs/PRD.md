# Product Requirements Document: Multi-Tenant Scale-Out Demo

## 1. Overview

This document outlines the requirements for developing a demonstration of ArangoDB's capabilities for multi-tenant graph scale-out and temporal data management. The demo will use the existing Network Asset Management data generation repository to showcase how a system can be designed to handle disjoint data sets (one per tenant), scale horizontally on demand, and automatically manage the lifecycle of temporal data using Time-to-Live (TTL) indexes.

This refactoring of the network asset management demo will support multi-tenant architecture using ArangoDB disjoint smartgraphs, with each tenant having a completely isolated smartgraph containing their network assets, devices, locations, and relationships.

## 2. Project Goals

The primary objective is to create a fully automated, end-to-end demo lifecycle that proves ArangoDB's suitability for large-scale, multi-tenant graph applications. Specific goals include:

* **Multi-Tenancy:** Demonstrate the use of **disjoint SmartGraphs** to provide strong data isolation for each tenant.

* **Horizontal Scale-Out:** Showcase the ability to seamlessly add a new database server to the cluster and rebalance tenant data to leverage the new capacity.

* **Temporal Data Management:** Implement the **time travel blueprint** and utilize **TTL indexes** to automatically expire outdated network observations, ensuring the database remains lean and performant.

* **Automation:** Automate all aspects of the demo, from cluster provisioning to data loading and a continuous "keep-alive" data stream.

### Additional Objectives
- **Complete Data Isolation**: Each tenant's data must be completely isolated from other tenants
- **Scalable Architecture**: Support for numerous tenants without performance degradation
- **Backward Compatibility**: Maintain existing data generation capabilities

### Success Criteria
- Generate isolated tenant datasets with configurable parameters
- Create tenant-specific ArangoDB smartgraphs
- Validate complete data isolation between tenants
- Demonstrate scalable tenant provisioning and horizontal scale-out
- Implement automated temporal data lifecycle management

## Current State Analysis

### Existing Architecture
- Single-tenant data generator creating JSON files for ArangoDB import
- Collections: Device, DeviceIn, DeviceOut, Location, Software
- Edge Collections: hasConnection, hasLocation, hasSoftware, version
- Proxy pattern for device versioning with temporal data

### Limitations
- No tenant isolation mechanism
- Hard-coded collection names
- Shared data structures across all generated data
- No tenant management utilities

## 3. Key Requirements

### 3.1 Data Generation Refactoring

The `scalable-multi-tenant-temporal-network-asset-management-demo` repository provides comprehensive demonstration capabilities including data generation, API functionality, and interactive demos:

* **Tenant-Specific Data:** The script must generate distinct, partitioned data sets for multiple tenants. Each tenant's data will be part of its own disjoint smartgraph.

* **Temporal Fields:** Ensure the data includes a consistent temporal attribute (e.g., `_observed_at` or `timestamp`) that will be used for both the time travel blueprint and the TTL index.

* **Vertex-Centric Indexing:** The generated edge documents must include `_fromType` and `_toType` attributes to enable efficient vertex-centric indexing. This is crucial for optimizing queries related to specific asset types.

* **Increased Data Size:** The default data generation size must be increased by a factor of 10 to 100 times to provide a substantial dataset for the scale-out demo.

### 3.2 Graph & Index Requirements

The database schema and indexing strategy must be designed for performance and lifecycle management.

* **Disjoint Smartgraphs:** The data will be loaded into one or more **disjoint smartgraphs**. Each graph will be configured to represent a separate tenant, with its own independent `smartGraphAttribute`.

* **Time Travel Blueprint:** The graph model must adhere to the time travel blueprint where temporal observations are stored as vertices, and edges connect these observations to the assets they describe.

* **TTL Indexes:** A TTL index must be created on the temporal attribute of the collections containing observed data. This index will automatically expire documents after a defined period. The `expireAfterSeconds` value will be managed by the demo automation scripts.

* **Vertex-Centric Indexes:** To optimize graph traversals and queries, the following vertex-centric indexes must be created on edge collections:
  * An index on `(_from, _toType)`.
  * An index on `(_to, _fromType)`.

* **Indexes for Time Travel Queries:** To optimize the retrieval of temporal data and enable fast time-slice queries, the following indexes are required:
  * **Hash Index:** A hash index on the document `_key` is necessary for quick lookups of specific observations.
  * **Temporal Range Index:** A persistent or `skiplist` index on the temporal attribute (e.g., `_observed_at` or `timestamp`) of the observation vertices is crucial for efficiently filtering data within a specific time range. This allows queries to quickly find all observations active at a given point in time or over a period.
  * **Edge Indexing:** The vertex-centric indexes on edge collections (`_from`, `_toType`) and (`_to`, `_fromType`) are also critical for time travel queries, as they significantly speed up traversals from an asset to its temporal observations.

* **Satellite Graph for Device Taxonomy:** A device taxonomy will be created as a **satellite graph**. Each device instance will be connected to its device model via a `'type'` edge. The taxonomy itself will be a hierarchy defined by `'subClassOf'` relationships. As a satellite graph, this metagraph will be replicated to all database servers, providing low-latency, local access to the schema metadata for all disjoint smartgraph tenants.

### 3.3 Demo Automation

A series of scripts must be developed to manage the entire demo lifecycle. These scripts will interact with the ArangoDB cluster management APIs.

## Detailed Functional Requirements

#### FR1: Tenant Data Model
- **FR1.1**: Each tenant must have a unique identifier (UUID or string-based)
- **FR1.2**: All generated data must include tenant context
- **FR1.3**: Collection names must be tenant-scoped (e.g., `tenant_abc123_devices`)
- **FR1.4**: Edge references must use tenant-scoped collection names

#### FR2: Data Generation
- **FR2.1**: Generate isolated datasets for multiple tenants
- **FR2.2**: Support configurable parameters per tenant (device count, locations, etc.)
- **FR2.3**: Maintain existing data quality and relationships within each tenant
- **FR2.4**: Generate tenant-specific JSON files for ArangoDB import
- **FR2.5**: Include temporal attributes (`_observed_at` or `timestamp`) in all generated data
- **FR2.6**: Add `_fromType` and `_toType` attributes to edge documents for vertex-centric indexing
- **FR2.7**: Increase default data generation size by 10-100x for scale-out demonstrations
- **FR2.8**: Generate continuous "keep-alive" data streams for ongoing demo operations
- **FR2.9**: Support dual naming conventions (camelCase default, snake_case alternative) configurable per tenant

#### FR3: SmartGraph Configuration
- **FR3.1**: Create disjoint smartgraph definitions for each tenant
- **FR3.2**: Generate ArangoDB setup scripts for tenant provisioning
- **FR3.3**: Support tenant graph creation and deletion
- **FR3.4**: Validate smartgraph disjoint properties
- **FR3.5**: Implement time travel blueprint graph model with temporal observations as vertices
- **FR3.6**: Create satellite graph for device taxonomy with global replication
- **FR3.7**: Configure independent `smartGraphAttribute` for each tenant graph

#### FR4: Tenant Management
- **FR4.1**: Utilities for creating new tenants
- **FR4.2**: Tenant metadata management
- **FR4.3**: Bulk tenant data generation capabilities
- **FR4.4**: Tenant cleanup and deletion utilities
- **FR4.5**: Automated cluster provisioning and management
- **FR4.6**: Horizontal scale-out demonstration with new database server addition
- **FR4.7**: Tenant data rebalancing across cluster nodes

#### FR5: Temporal Data Management
- **FR5.1**: Implement TTL indexes on temporal attributes for automatic data expiration
- **FR5.2**: Configurable `expireAfterSeconds` values managed by automation scripts
- **FR5.3**: Time travel query optimization with appropriate indexing
- **FR5.4**: Temporal data lifecycle management and cleanup

#### FR6: Index Optimization
- **FR6.1**: Create vertex-centric indexes on `(_from, _toType)` and `(_to, _fromType)`
- **FR6.2**: Implement hash indexes on document `_key` for quick lookups
- **FR6.3**: Create temporal range indexes on observation timestamps
- **FR6.4**: Optimize edge indexing for time travel query performance
- **FR6.5**: Ensure index configuration and processing logic consistency (config type must match code conditions)

### Non-Functional Requirements

#### NFR1: Performance
- **NFR1.1**: Data generation must scale linearly with tenant count
- **NFR1.2**: Memory usage must remain reasonable for large tenant datasets
- **NFR1.3**: File I/O operations must be optimized for bulk generation
- **NFR1.4**: Horizontal scale-out must demonstrate improved performance with additional nodes
- **NFR1.5**: TTL index operations must not impact query performance
- **NFR1.6**: Time travel queries must execute efficiently with proper indexing

#### NFR2: Data Integrity
- **NFR2.1**: Complete isolation between tenant datasets
- **NFR2.2**: Referential integrity within each tenant's data
- **NFR2.3**: Consistent data formats across all tenants

#### NFR3: Maintainability
- **NFR3.1**: Clean separation between tenant-aware and core generation logic
- **NFR3.2**: Configurable parameters via external configuration
- **NFR3.3**: Comprehensive logging and error handling

#### NFR4: Code Quality and Consistency
- **NFR4.1**: Index configuration changes must include corresponding logic updates
- **NFR4.2**: Configuration-driven features require validation that config types match processing logic
- **NFR4.3**: Breaking changes to data structures must include comprehensive testing of dependent code

## Technical Architecture

### Tenant Identification Strategy
- **Format**: `tenant_{uuid}` or configurable string identifiers
- **Scope**: All collections, edges, and file names include tenant context
- **Metadata**: Tenant configuration stored separately from generated data

### Naming Convention Support

The system supports **dual naming conventions** to accommodate different organizational preferences and technical requirements:

#### Default: camelCase (W3C OWL Compliant)
Following W3C OWL standards for professional data modeling:

**Vertex Collections**
- **Format**: PascalCase, singular form
- **Examples**: `Device`, `Location`, `Software`, `DeviceProxyIn`, `DeviceProxyOut`
- **Rationale**: Represents entity classes/types in RDF ontologies

**Edge Collections**  
- **Format**: camelCase, singular form
- **Examples**: `hasConnection`, `hasLocation`, `hasDeviceSoftware`, `hasVersion`
- **Rationale**: Represents predicates/relationships in RDF ontologies

**Property Names**
- **Single Values**: camelCase, singular form
  - Examples: `deviceType`, `ipAddress`, `macAddress`, `serialNumber`
- **Lists/Arrays**: camelCase, plural form  
  - Examples: `firewallRules`, `configurationHistory`, `edgeDefinitions`
- **Sub-documents**: camelCase, singular form
  - Examples: `location` (GeoJSON), `softwareVersion`

#### Alternative: snake_case (Technical/Database Standard)
For organizations preferring database-friendly naming:

**Vertex Collections**
- **Format**: snake_case, singular form
- **Examples**: `device`, `location`, `software`, `device_proxy_in`, `device_proxy_out`
- **Rationale**: Consistent with SQL database conventions

**Edge Collections**
- **Format**: snake_case, singular form
- **Examples**: `has_connection`, `has_location`, `has_device_software`, `has_version`
- **Rationale**: Readable and consistent with technical documentation

**Property Names**
- **Single Values**: snake_case, singular form
  - Examples: `device_type`, `ip_address`, `mac_address`, `serial_number`
- **Lists/Arrays**: snake_case, plural form
  - Examples: `firewall_rules`, `configuration_history`, `edge_definitions`
- **Sub-documents**: snake_case, singular form
  - Examples: `location_data`, `software_version`

#### Convention Selection
- **Default**: camelCase (automatically applied unless specified otherwise)
- **Configuration**: Selectable via `NamingConvention.CAMEL_CASE` or `NamingConvention.SNAKE_CASE`
- **Consistency**: Once selected, the convention applies to all collections, properties, and files within a tenant
- **Isolation**: Different tenants can use different naming conventions simultaneously

#### Collection Naming Examples

**camelCase (Default)**
```
# Vertex Collections
Device (tenant-scoped via smartGraph attribute)
DeviceProxyIn (tenant-scoped via smartGraph attribute)  
DeviceProxyOut (tenant-scoped via smartGraph attribute)
Location (tenant-scoped via smartGraph attribute)
Software (tenant-scoped via smartGraph attribute)
SoftwareProxyIn (tenant-scoped via smartGraph attribute)
SoftwareProxyOut (tenant-scoped via smartGraph attribute)

# Edge Collections  
hasConnection (tenant-scoped via smartGraph attribute)
hasLocation (tenant-scoped via smartGraph attribute)
hasDeviceSoftware (tenant-scoped via smartGraph attribute)
hasVersion (tenant-scoped via smartGraph attribute)
```

**snake_case (Alternative)**
```
# Vertex Collections
device (tenant-scoped via smartGraph attribute)
device_proxy_in (tenant-scoped via smartGraph attribute)
device_proxy_out (tenant-scoped via smartGraph attribute)
location (tenant-scoped via smartGraph attribute)
software (tenant-scoped via smartGraph attribute)
software_proxy_in (tenant-scoped via smartGraph attribute)
software_proxy_out (tenant-scoped via smartGraph attribute)

# Edge Collections
has_connection (tenant-scoped via smartGraph attribute)
has_location (tenant-scoped via smartGraph attribute)
has_device_software (tenant-scoped via smartGraph attribute)
has_version (tenant-scoped via smartGraph attribute)
```

### File Structure

**camelCase (Default)**
```
data/
├── tenant_{tenant_id}/
│   ├── Device.json
│   ├── DeviceProxyIn.json
│   ├── DeviceProxyOut.json
│   ├── Location.json
│   ├── Software.json
│   ├── SoftwareProxyIn.json
│   ├── SoftwareProxyOut.json
│   ├── hasConnection.json
│   ├── hasLocation.json
│   ├── hasDeviceSoftware.json
│   └── hasVersion.json
└── tenant_registry_time_travel.json (tenant metadata)
```

**snake_case (Alternative)**
```
data/
├── tenant_{tenant_id}/
│   ├── device.json
│   ├── device_proxy_in.json
│   ├── device_proxy_out.json
│   ├── location.json
│   ├── software.json
│   ├── software_proxy_in.json
│   ├── software_proxy_out.json
│   ├── has_connection.json
│   ├── has_location.json
│   ├── has_device_software.json
│   └── has_version.json
└── tenant_registry_time_travel.json (tenant metadata)
```

## Demo and Presentation Capabilities

### Interactive Demo Walkthrough

The system includes a comprehensive automated demo script that supports both naming conventions for live presentations and development testing.

#### Command-Line Interface

**Basic Usage:**
```bash
# Interactive mode with camelCase (default)
PYTHONPATH=. python3 demos/automated_demo_walkthrough.py --interactive

# Interactive mode with snake_case  
PYTHONPATH=. python3 demos/automated_demo_walkthrough.py --interactive --naming snake_case

# Automated mode for testing
PYTHONPATH=. python3 demos/automated_demo_walkthrough.py --auto-advance --naming snake_case
```

**Available Flags:**
- `--interactive`: Force interactive mode with manual pauses
- `--auto-advance`: Run in automatic mode with timed pauses  
- `--pause-duration N`: Duration of automatic pauses in seconds (default: 3)
- `--naming {camelCase,snake_case}`: Naming convention for properties and files (default: camelCase)

#### Naming Convention Integration

The demo script dynamically adapts to the selected naming convention:

**File Import Mappings:**
- **camelCase**: `Device.json` → `Device` collection, `hasConnection.json` → `hasConnection` collection
- **snake_case**: `device.json` → `Device` collection, `has_connection.json` → `hasConnection` collection

**Property Generation:**
- **camelCase**: `serialNumber`, `ipAddress`, `portNumber`, `isEnabled`
- **snake_case**: `serial_number`, `ip_address`, `port_number`, `is_enabled`

**Data Generation Consistency:**
- All 8 demo tenants use the same naming convention
- Scale-out operations maintain naming convention consistency
- Database deployment adapts file mappings automatically

#### Demo Flow Coverage

The interactive demo supports both naming conventions across all sections:
1. **Database Reset and Cleanup** - Convention-aware file cleanup
2. **Data Generation** - PropertyNameGenerator integration  
3. **Database Deployment** - Dynamic file mapping
4. **Initial Validation** - Convention-agnostic queries
5. **Temporal TTL Transactions** - Property-aware updates
6. **Time Travel Demonstration** - Naming-independent temporal queries
7. **Scale-Out Operations** - Consistent convention for new tenants
8. **Final Validation** - Comprehensive testing across conventions

### SmartGraph Definition
Each tenant will have a disjoint smartgraph with:
- **Graph Name**: `tenant_{tenant_id}_network_assets`
- **Vertex Collections**: All tenant-scoped vertex collections
- **Edge Definitions**: All tenant-scoped edge collections with proper from/to mappings
- **Disjoint Property**: Ensures complete isolation between tenant graphs

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
1. Design tenant data model and configuration system
2. Refactor core generator functions to accept tenant context
3. Implement tenant-aware collection and file naming
4. Create tenant metadata management

### Phase 2: Infrastructure (Week 3-4)
5. Generate ArangoDB smartgraph configuration scripts
6. Implement tenant provisioning utilities
7. Create bulk tenant data generation
8. Add data validation and integrity checks

### Phase 3: Validation (Week 5)
9. Comprehensive testing of tenant isolation
10. Performance testing with multiple tenants
11. Documentation and deployment guides

## Acceptance Criteria

### Data Generation
- [ ] Generate isolated datasets for configurable number of tenants
- [ ] Each tenant has complete set of network asset data
- [ ] No cross-tenant data references or contamination
- [ ] Configurable parameters per tenant (devices, locations, software)
- [ ] Support both camelCase (default) and snake_case naming conventions
- [ ] Naming convention consistency within each tenant

### Demo and Presentation
- [ ] Interactive demo script supports both naming conventions via `--naming` flag
- [ ] Demo workflow adapts file mappings automatically based on selected convention
- [ ] All demo sections (data generation, deployment, scale-out) maintain naming consistency
- [ ] PropertyNameGenerator eliminates hardcoded property names across all demo components
- [ ] Backward compatibility maintained (camelCase remains default behavior)

### SmartGraph Integration
- [ ] Generate valid ArangoDB smartgraph definitions
- [ ] Create tenant-specific database setup scripts
- [ ] Validate disjoint smartgraph properties
- [ ] Support tenant graph lifecycle management

### Data Isolation
- [ ] Complete separation of tenant data in all collections
- [ ] Proper tenant-scoped collection naming
- [ ] Isolated file storage per tenant
- [ ] No shared references between tenant datasets

### Management Utilities
- [ ] Tenant creation and deletion scripts
- [ ] Bulk tenant data generation
- [ ] Tenant metadata management
- [ ] Data validation and integrity checks

### Code Quality and Consistency
- [ ] Index configuration types match processing logic conditions
- [ ] All configured index types are successfully created (no "Unknown index type" errors)
- [ ] Configuration changes include corresponding implementation updates

## Risks and Mitigation

### Risk 1: Data Contamination
- **Risk**: Accidental cross-tenant data references
- **Mitigation**: Comprehensive validation scripts and automated testing

### Risk 2: Performance Degradation
- **Risk**: Poor performance with large numbers of tenants
- **Mitigation**: Optimize data generation algorithms and file I/O operations

### Risk 3: Configuration Complexity
- **Risk**: Complex configuration management for multiple tenants
- **Mitigation**: Clear configuration schema and validation

## Success Metrics

- **Isolation Completeness**: 100% isolation between tenant datasets
- **Generation Performance**: Linear scaling with tenant count
- **Data Integrity**: Zero cross-tenant references
- **Setup Time**: < 5 minutes for new tenant provisioning
- **Scale-out Performance**: Measurable performance improvement with cluster expansion
- **Temporal Data Management**: Automatic TTL-based data expiration working correctly
- **Query Performance**: Time travel queries executing within acceptable performance thresholds
- **Automation Coverage**: 100% automated demo lifecycle from provisioning to cleanup

## Timeline

- **Week 1-2**: Foundation and core refactoring
- **Week 3-4**: Infrastructure and utilities
- **Week 5**: Testing and validation
- **Week 6**: Documentation and final integration

## Dependencies

- ArangoDB cluster with smartgraph and disjoint smartgraph support
- ArangoDB cluster management APIs for automation
- Python environment with existing dependencies (geojson, uuid, datetime)
- File system access for tenant-specific data storage
- Configuration management system for tenant and cluster parameters
- TTL index support in ArangoDB
- Satellite graph capability for device taxonomy replication
