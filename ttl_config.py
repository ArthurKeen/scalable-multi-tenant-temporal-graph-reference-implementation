"""
TTL Configuration System for Current vs Historical Strategy

Implements selective TTL indexes that only affect historical documents
while preserving current configurations permanently.
"""

import sys
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum

# Import centralized constants
from ttl_constants import (
    TTLConstants, TTLMessages, TTLConfigurationFactory, TTLUtilities,
    DEFAULT_TTL_DAYS, NEVER_EXPIRES, TTL_SELECTIVITY
)


class TTLStrategy(Enum):
    """TTL application strategies."""
    DISABLED = "disabled"
    ALL_DOCUMENTS = "all_documents" 
    HISTORICAL_ONLY = "historical_only"  # Our strategy


@dataclass
class TTLIndexConfiguration:
    """Configuration for a single TTL index."""
    collection_name: str
    field_name: str = "expired"
    expire_after_seconds: int = 0  # Expire when timestamp is reached
    strategy: TTLStrategy = TTLStrategy.HISTORICAL_ONLY
    sparse: bool = TTLConstants.TTL_SPARSE_INDEX  # Skip documents where expired = sys.maxsize
    selectivity_estimate: float = TTLConstants.TTL_SELECTIVITY_ESTIMATE  # Estimate of documents affected
    
    def to_arango_index_spec(self) -> Dict[str, Any]:
        """Convert to ArangoDB index specification."""
        if self.strategy == TTLStrategy.DISABLED:
            return None
            
        spec = {
            "type": "ttl",
            "fields": [self.field_name],
            "expireAfter": self.expire_after_seconds,
            "sparse": self.sparse,
            "selectivityEstimate": self.selectivity_estimate
        }
        
        # Add name for identification
        spec["name"] = f"ttl_{self.collection_name}_{self.field_name}"
        
        return spec


@dataclass 
class TTLConfiguration:
    """Complete TTL configuration for a tenant."""
    tenant_id: str
    strategy: TTLStrategy = TTLStrategy.HISTORICAL_ONLY
    default_expire_after_seconds: int = TTLConstants.DEFAULT_TTL_EXPIRE_SECONDS
    preserve_current_configs: bool = True
    
    # Collection-specific configurations
    vertex_collections: List[str] = None
    edge_collections: List[str] = None
    
    def __post_init__(self):
        """Initialize default collections if not provided."""
        if self.vertex_collections is None:
            self.vertex_collections = [
                "Device", "Software", "Location",
                "DeviceProxyIn", "DeviceProxyOut", 
                "SoftwareProxyIn", "SoftwareProxyOut"
            ]
        
        if self.edge_collections is None:
            self.edge_collections = [
                "hasConnection", "hasLocation", 
                "hasDeviceSoftware", "hasVersion"
            ]
    
    def get_ttl_index_configs(self) -> List[TTLIndexConfiguration]:
        """Generate TTL index configurations for all collections."""
        configs = []
        
        if self.strategy == TTLStrategy.DISABLED:
            return configs
        
        # Vertex collections
        for collection in self.vertex_collections:
            configs.append(TTLIndexConfiguration(
                collection_name=collection,
                expire_after_seconds=self.default_expire_after_seconds,
                strategy=self.strategy
            ))
        
        # Edge collections  
        for collection in self.edge_collections:
            configs.append(TTLIndexConfiguration(
                collection_name=collection,
                expire_after_seconds=self.default_expire_after_seconds,
                strategy=self.strategy
            ))
        
        return configs
    
    def is_document_subject_to_ttl(self, document: Dict[str, Any]) -> bool:
        """Check if a document should be subject to TTL."""
        if self.strategy == TTLStrategy.DISABLED:
            return False
        
        if self.strategy == TTLStrategy.ALL_DOCUMENTS:
            return True
        
        if self.strategy == TTLStrategy.HISTORICAL_ONLY:
            # Only historical documents (expired != NEVER_EXPIRES) are subject to TTL
            return TTLUtilities.is_historical_configuration(document)
        
        return False


class TTLManager:
    """Manages TTL operations for the Current vs Historical strategy."""
    
    def __init__(self, ttl_config: TTLConfiguration):
        self.config = ttl_config
    
    def get_arango_index_specs(self) -> List[Dict[str, Any]]:
        """Get all ArangoDB index specifications."""
        specs = []
        for index_config in self.config.get_ttl_index_configs():
            spec = index_config.to_arango_index_spec()
            if spec:
                specs.append(spec)
        return specs
    
    def should_apply_ttl_to_document(self, document: Dict[str, Any]) -> bool:
        """Determine if TTL should apply to a specific document."""
        return self.config.is_document_subject_to_ttl(document)
    
    def get_ttl_status_summary(self) -> Dict[str, Any]:
        """Get summary of TTL configuration status."""
        return {
            "tenant_id": self.config.tenant_id,
            "strategy": self.config.strategy.value,
            "expire_after_days": self.config.default_expire_after_seconds // 86400,
            "preserve_current_configs": self.config.preserve_current_configs,
            "total_collections": len(self.config.vertex_collections) + len(self.config.edge_collections),
            "vertex_collections": len(self.config.vertex_collections),
            "edge_collections": len(self.config.edge_collections),
            "index_count": len(self.config.get_ttl_index_configs())
        }


def create_ttl_configuration(tenant_id: str, 
                           expire_after_days: int = DEFAULT_TTL_DAYS,
                           strategy: TTLStrategy = TTLStrategy.HISTORICAL_ONLY) -> TTLConfiguration:
    """Create a TTL configuration with sensible defaults."""
    config_params = TTLConfigurationFactory.create_ttl_config_params(tenant_id, expire_after_days)
    return TTLConfiguration(
        tenant_id=config_params["tenant_id"],
        strategy=strategy,
        default_expire_after_seconds=config_params["expire_after_seconds"],
        preserve_current_configs=True
    )


def create_snake_case_ttl_configuration(tenant_id: str,
                                      expire_after_days: int = DEFAULT_TTL_DAYS,
                                      strategy: TTLStrategy = TTLStrategy.HISTORICAL_ONLY) -> TTLConfiguration:
    """Create TTL configuration for snake_case naming convention."""
    config_params = TTLConfigurationFactory.create_ttl_config_params(tenant_id, expire_after_days)
    config = TTLConfiguration(
        tenant_id=config_params["tenant_id"],
        strategy=strategy,
        default_expire_after_seconds=config_params["expire_after_seconds"],
        preserve_current_configs=True,
        vertex_collections=[
            "device", "software", "location",
            "device_proxy_in", "device_proxy_out",
            "software_proxy_in", "software_proxy_out"
        ],
        edge_collections=[
            "has_connection", "has_location",
            "has_device_software", "has_version"
        ]
    )
    return config


# Example usage and testing
if __name__ == "__main__":
    # Test camelCase configuration
    camel_config = create_ttl_configuration("test_tenant_camel")
    camel_manager = TTLManager(camel_config)
    
    print("CamelCase TTL Configuration:")
    print("=" * 40)
    print(f"Index specifications: {len(camel_manager.get_arango_index_specs())}")
    print(f"Status: {camel_manager.get_ttl_status_summary()}")
    
    # Test snake_case configuration
    snake_config = create_snake_case_ttl_configuration("test_tenant_snake")
    snake_manager = TTLManager(snake_config)
    
    print("\nSnake_case TTL Configuration:")
    print("=" * 40)
    print(f"Index specifications: {len(snake_manager.get_arango_index_specs())}")
    print(f"Status: {snake_manager.get_ttl_status_summary()}")
    
    # Test document TTL applicability
    current_doc = {"_key": "device_001", "expired": NEVER_EXPIRES}
    historical_doc = {"_key": "device_001_v1", "expired": 1672531200}
    
    print(f"\nTTL Applicability:")
    print(f"Current doc (expired={NEVER_EXPIRES}): {camel_manager.should_apply_ttl_to_document(current_doc)}")
    print(f"Historical doc (expired=1672531200): {camel_manager.should_apply_ttl_to_document(historical_doc)}")
