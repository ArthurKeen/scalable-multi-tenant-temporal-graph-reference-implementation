"""
Tenant Configuration and Data Model for Multi-Tenant Network Asset Management Demo

This module defines the tenant data model, naming conventions, and configuration
structure required for multi-tenant ArangoDB disjoint smartgraphs.

Compliance with PRD Requirements:
- FR1: Tenant Data Model - UUID-based tenant identifiers with scoped collections
- FR2.5: Temporal attributes included in all data structures  
- FR2.6: Vertex-centric indexing attributes (_fromType, _toType)
- FR3.7: Independent smartGraphAttribute per tenant
- NFR2.1: Complete data isolation between tenants
"""

import uuid
import datetime
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from ttl_constants import NEVER_EXPIRES


class TenantStatus(Enum):
    """Tenant lifecycle status for management and automation."""
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class TenantConfig:
    """
    Tenant configuration defining data generation parameters and database settings.
    
    Supports both single-tenant compatibility and multi-tenant scale-out scenarios.
    """
    # Core tenant identification
    tenant_id: str
    tenant_name: str
    status: TenantStatus = TenantStatus.PROVISIONING
    
    # Data generation parameters (FR2.1, FR2.2)
    num_devices: int = 20
    num_locations: int = 5
    num_software: int = 30
    num_connections: int = 30
    num_has_software: int = 40
    num_config_changes: int = 5
    
    # Scale-out demo parameters (FR2.7)
    scale_factor: int = 1  # Multiply base counts by this factor for large datasets
    
    # Temporal data management (FR2.5, FR5.1, FR5.2) - Current vs Historical TTL strategy
    ttl_enabled: bool = True  # Enable TTL for historical documents only
    ttl_expire_after_seconds: int = None  # Will be set from TTLConstants in __post_init__
    preserve_current_configs: bool = True  # Never age out current configurations (expired = NEVER_EXPIRES)
    temporal_attribute_name: str = "expired"  # TTL applies to expired field
    
    # Database and graph configuration (FR3.1, FR3.7)
    database_name: str = "network_assets_demo"  # Shared database for all tenants
    smartgraph_attribute: Optional[str] = None  # If None, auto-generated
    
    # Metadata
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    description: str = ""
    
    def __post_init__(self):
        """Initialize auto-generated fields and validate configuration."""
        # Set TTL expire seconds from constants if not provided
        if self.ttl_expire_after_seconds is None:
            try:
                from ttl_constants import TTLConstants, NEVER_EXPIRES
                self.ttl_expire_after_seconds = TTLConstants.DEFAULT_TTL_EXPIRE_SECONDS
            except ImportError:
                self.ttl_expire_after_seconds = TTLConstants.DEFAULT_TTL_EXPIRE_SECONDS  # Fallback to 30 days
        
        if self.smartgraph_attribute is None:
            self.smartgraph_attribute = f"tenant_{self.tenant_id}_attr"
        
        # Apply scale factor to data generation parameters (FR2.7)
        if self.scale_factor > 1:
            self.num_devices *= self.scale_factor
            self.num_locations *= self.scale_factor
            self.num_software *= self.scale_factor
            self.num_connections *= self.scale_factor
            self.num_has_software *= self.scale_factor


class TenantNamingConvention:
    """
    Centralized naming convention for tenant-scoped resources.
    
    Ensures consistent naming across all collections, graphs, and files
    while maintaining complete data isolation (NFR2.1).
    """
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
    
    # Database and graph names (FR3.1, FR3.7)
    @property
    def database_name(self) -> str:
        return "network_assets_demo"  # Shared database for all tenants using disjoint smartgraphs
    
    @property
    def smartgraph_name(self) -> str:
        return f"tenant_{self.tenant_id}_network_assets"
    
    @property
    def smartgraph_attribute(self) -> str:
        return f"tenant_{self.tenant_id}_attr"
    
    # W3C OWL compliant collection names (shared across all tenants)
    @property 
    def device_collection(self) -> str:
        return "Device"
    
    @property
    def device_in_collection(self) -> str:
        return "DeviceProxyIn"
    
    @property
    def device_out_collection(self) -> str:
        return "DeviceProxyOut"
    
    @property
    def location_collection(self) -> str:
        return "Location"
    
    @property
    def software_collection(self) -> str:
        return "Software"
    
    # Edge collection names (camelCase, singular - W3C OWL)
    @property
    def has_connection_collection(self) -> str:
        return "hasConnection"
    
    @property
    def has_location_collection(self) -> str:
        return "hasLocation"
    
    @property
    def has_software_collection(self) -> str:
        return "hasSoftware"
    
    @property
    def version_collection(self) -> str:
        return "version"
    
    # File paths for data generation output (FR2.4)
    @property
    def data_directory(self) -> str:
        return f"data/tenant_{self.tenant_id}"
    
    def get_json_file_path(self, collection_type: str) -> str:
        """Get file path for tenant-specific JSON data files."""
        return f"{self.data_directory}/{collection_type}.json"
    
    # Vertex-centric index names (FR6.1)
    def get_vertex_centric_index_name(self, collection: str, index_type: str) -> str:
        """Generate vertex-centric index names for optimization."""
        return f"idx_{collection}_{index_type}_vertex_centric"
    
    # TTL index names (FR5.1)
    def get_ttl_index_name(self, collection: str) -> str:
        """Generate TTL index names for temporal data management."""
        return f"idx_{collection}_ttl_observedAt"


class TemporalDataModel:
    """
    Temporal data model utilities for time travel blueprint implementation.
    
    Ensures all generated data includes proper temporal attributes (FR2.5, FR3.5).
    """
    
    @staticmethod
    def add_temporal_attributes(document: Dict[str, Any], 
                              timestamp: Optional[datetime.datetime] = None,
                              expired: Optional[int] = None,
                              tenant_config: Optional['TenantConfig'] = None) -> Dict[str, Any]:
        """
        Add temporal attributes to any document for time travel support.
        
        Args:
            document: Base document to enhance
            timestamp: Observation timestamp (defaults to now)
            expired: Expiration timestamp (defaults to max value for current observations)
            tenant_config: Tenant configuration for smartgraph attribute assignment
            
        Returns:
            Document with temporal attributes and tenant partitioning key added
        """
        if timestamp is None:
            timestamp = datetime.datetime.now()
        
        if expired is None:
            expired = NEVER_EXPIRES  # Default to not expired for current observations
        
        # Add temporal attributes (FR2.5) - observedAt removed, expired defaults to max value
        enhanced_doc = document.copy()
        enhanced_doc["created"] = timestamp.timestamp()
        enhanced_doc["expired"] = expired
        
        # Add tenant key for disjoint smartgraph partitioning
        if tenant_config is not None:
            enhanced_doc[tenant_config.smartgraph_attribute] = tenant_config.tenant_id
        
        return enhanced_doc
    
    @staticmethod
    def add_vertex_centric_attributes(edge_document: Dict[str, Any],
                                    from_type: str,
                                    to_type: str) -> Dict[str, Any]:
        """
        Add vertex-centric indexing attributes to edge documents.
        
        Enables efficient graph traversals by vertex type (FR2.6, FR6.1).
        
        Args:
            edge_document: Base edge document
            from_type: Type of source vertex (e.g., 'device', 'location')
            to_type: Type of target vertex (e.g., 'software', 'location')
            
        Returns:
            Edge document with vertex-centric attributes
        """
        enhanced_edge = edge_document.copy()
        enhanced_edge["_fromType"] = from_type
        enhanced_edge["_toType"] = to_type
        
        return enhanced_edge
    
    @staticmethod
    def add_proxy_attributes(document: Dict[str, Any], tenant_config: 'TenantConfig') -> Dict[str, Any]:
        """
        Add only tenant attributes to proxy documents (no temporal data).
        
        DeviceProxyIn and DeviceProxyOut should not have temporal attributes.
        """
        enhanced_doc = document.copy()
        
        # Add only tenant key for disjoint smartgraph partitioning
        if tenant_config is not None:
            enhanced_doc[tenant_config.smartgraph_attribute] = tenant_config.tenant_id
        
        return enhanced_doc


class SmartGraphDefinition:
    """
    SmartGraph configuration generator for disjoint tenant graphs.
    
    Creates proper edge definitions and configurations for ArangoDB smartgraphs (FR3.1, FR3.5).
    """
    
    def __init__(self, naming: TenantNamingConvention):
        self.naming = naming
    
    def get_edge_definitions(self) -> List[Dict[str, Any]]:
        """
        Generate edge definitions for the tenant's smartgraph.
        
        Defines all relationships in the network asset graph with proper
        vertex-centric organization for time travel queries.
        """
        return [
            {
                "edge_collection": self.naming.has_connection_collection,
                "from_vertex_collections": [self.naming.device_out_collection],
                "to_vertex_collections": [self.naming.device_in_collection]
            },
            {
                "edge_collection": self.naming.has_location_collection,
                "from_vertex_collections": [self.naming.device_out_collection],
                "to_vertex_collections": [self.naming.location_collection]
            },
            {
                "edge_collection": self.naming.has_software_collection,
                "from_vertex_collections": [self.naming.device_out_collection],
                "to_vertex_collections": [self.naming.software_collection]
            },
            {
                "edge_collection": self.naming.version_collection,
                "from_vertex_collections": [
                    self.naming.device_in_collection,
                    self.naming.device_collection
                ],
                "to_vertex_collections": [
                    self.naming.device_collection,
                    self.naming.device_out_collection
                ]
            }
        ]
    
    def get_vertex_collections(self) -> List[str]:
        """Get all vertex collections for the tenant graph."""
        return [
            self.naming.device_collection,
            self.naming.device_in_collection,
            self.naming.device_out_collection,
            self.naming.location_collection,
            self.naming.software_collection
        ]
    
    def get_smartgraph_config(self) -> Dict[str, Any]:
        """
        Generate complete smartgraph configuration for MCP service.
        
        Returns configuration suitable for ArangoDB MCP service graph creation.
        """
        return {
            "graph_name": self.naming.smartgraph_name,
            "edge_definitions": self.get_edge_definitions(),
            "orphan_collections": [],  # All collections have relationships
            "is_smart": True,
            "options": {
                "smart_graph_attribute": self.naming.smartgraph_attribute,
                "number_of_shards": 3,  # Configurable for scale-out demo
                "replication_factor": 2
            }
        }


# Satellite graph for device taxonomy (FR3.6)
DEVICE_TAXONOMY_GRAPH = {
    "graph_name": "satellite_device_taxonomy",
    "edge_definitions": [
        {
            "edge_collection": "device_type_edges",
            "from_vertex_collections": ["device_instances"],
            "to_vertex_collections": ["device_models"]
        },
        {
            "edge_collection": "device_hierarchy_edges", 
            "from_vertex_collections": ["device_models"],
            "to_vertex_collections": ["device_categories"]
        }
    ],
    "is_satellite": True,
    "options": {
        "replication_factor": "satellite"  # Replicated to all database servers
    }
}


def generate_tenant_id() -> str:
    """Generate a unique tenant identifier."""
    return str(uuid.uuid4()).replace("-", "")[:12]  # 12-character hex string


def create_tenant_config(tenant_name: str, 
                        scale_factor: int = 1,
                        **kwargs) -> TenantConfig:
    """
    Create a new tenant configuration with proper defaults.
    
    Args:
        tenant_name: Human-readable tenant name
        scale_factor: Data generation scale multiplier (FR2.7)
        **kwargs: Additional configuration overrides
        
    Returns:
        Configured TenantConfig instance
    """
    tenant_id = generate_tenant_id()
    
    config = TenantConfig(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        scale_factor=scale_factor,
        **kwargs
    )
    
    return config


def validate_tenant_isolation(config1: TenantConfig, config2: TenantConfig) -> bool:
    """
    Validate that two tenant configurations maintain proper isolation.
    
    Ensures no naming conflicts or shared resources (NFR2.1).
    With disjoint smartgraphs, tenants share the same database but have
    completely isolated data through different smartgraph attributes.
    """
    naming1 = TenantNamingConvention(config1.tenant_id)
    naming2 = TenantNamingConvention(config2.tenant_id)
    
    # Database is shared - this is expected for disjoint smartgraphs
    assert naming1.database_name == naming2.database_name, "Tenants should share database"
    
    # Check smartgraph isolation - each tenant has unique smartgraph
    if naming1.smartgraph_name == naming2.smartgraph_name:
        return False
    
    # Check smartgraph attribute isolation - this provides the disjoint partitioning
    if naming1.smartgraph_attribute == naming2.smartgraph_attribute:
        return False
    
    # Collections are shared - isolation is provided by smartgraph attribute
    assert naming1.device_collection == naming2.device_collection, "Collections should be shared"
    assert naming1.location_collection == naming2.location_collection, "Collections should be shared"
    
    return True


# Example usage and testing
if __name__ == "__main__":
    # Create test tenant configurations
    tenant_a = create_tenant_config("Company A", scale_factor=1)
    tenant_b = create_tenant_config("Company B", scale_factor=10)
    
    print(f"Tenant A ID: {tenant_a.tenant_id}")
    print(f"Tenant B ID: {tenant_b.tenant_id}")
    
    # Test naming conventions
    naming_a = TenantNamingConvention(tenant_a.tenant_id)
    naming_b = TenantNamingConvention(tenant_b.tenant_id)
    
    print(f"\nTenant A Collections:")
    print(f"  Database: {naming_a.database_name}")
    print(f"  SmartGraph: {naming_a.smartgraph_name}")
    print(f"  Devices: {naming_a.device_collection}")
    
    print(f"\nTenant B Collections:")
    print(f"  Database: {naming_b.database_name}")
    print(f"  SmartGraph: {naming_b.smartgraph_name}")
    print(f"  Devices: {naming_b.device_collection}")
    
    # Validate isolation
    isolation_valid = validate_tenant_isolation(tenant_a, tenant_b)
    print(f"\nTenant isolation valid: {isolation_valid}")
    
    # Test smartgraph configuration
    graph_def_a = SmartGraphDefinition(naming_a)
    config_a = graph_def_a.get_smartgraph_config()
    print(f"\nSmartGraph config for Tenant A:")
    print(f"  Graph name: {config_a['graph_name']}")
    print(f"  Edge definitions: {len(config_a['edge_definitions'])}")
    
    # Test temporal data model
    sample_device = {"_key": "device1", "name": "Router 1", "type": "router"}
    temporal_device = TemporalDataModel.add_temporal_attributes(sample_device)
    print(f"\nTemporal device sample:")
    print(f"  Keys: {list(temporal_device.keys())}")
    
    sample_edge = {"_key": "conn1", "_from": "devices/dev1", "_to": "devices/dev2"}
    vertex_centric_edge = TemporalDataModel.add_vertex_centric_attributes(
        sample_edge, "device", "device"
    )
    print(f"\nVertex-centric edge sample:")
    print(f"  Keys: {list(vertex_centric_edge.keys())}")
