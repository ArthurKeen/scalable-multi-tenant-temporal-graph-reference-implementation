"""
Centralized Configuration and Credentials Management

Eliminates hard-wired values throughout the codebase and provides
secure credential management for the multi-tenant demo.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, Any


# Import centralized credentials to avoid duplication
from centralized_credentials import DatabaseCredentials, CredentialsManager


@dataclass
class ApplicationPaths:
    """Centralized path management."""
    
    project_root: Path
    data_directory: Path
    docs_directory: Path
    logs_directory: Path
    reports_directory: Path
    
    def __post_init__(self):
        """Ensure all directories exist."""
        for directory in [self.data_directory, self.docs_directory, 
                         self.logs_directory, self.reports_directory]:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def initialize_default(cls) -> 'ApplicationPaths':
        """Initialize with default project structure."""
        project_root = Path(__file__).parent
        return cls(
            project_root=project_root,
            data_directory=project_root / 'data',
            docs_directory=project_root / 'docs',
            logs_directory=project_root / 'logs',
            reports_directory=project_root / 'reports'
        )
    
    def get_tenant_data_path(self, tenant_id: str) -> Path:
        """Get data path for specific tenant."""
        return self.data_directory / f"tenant_{tenant_id}"
    
    def get_report_path(self, report_name: str) -> Path:
        """Get path for specific report."""
        return self.reports_directory / report_name


@dataclass  
class CollectionConfiguration:
    """W3C OWL compliant collection configuration."""
    
    # Vertex collections (PascalCase, singular)
    vertex_collections: Dict[str, str]
    # Edge collections (camelCase, singular)  
    edge_collections: Dict[str, str]
    # File name mappings
    file_mappings: Dict[str, str]
    
    @classmethod
    def get_owlrdf_config(cls) -> 'CollectionConfiguration':
        """Get W3C OWL compliant configuration."""
        vertex_collections = {
            "devices": "Device",
            "device_ins": "DeviceProxyIn", 
            "device_outs": "DeviceProxyOut",
            "locations": "Location",
            "software": "Software",
            "software_ins": "SoftwareProxyIn",
            "software_outs": "SoftwareProxyOut"
        }
        
        edge_collections = {
            "connections": "hasConnection",
            "has_locations": "hasLocation", 
            "has_software": "hasSoftware",
            "has_device_software": "hasDeviceSoftware",
            "versions": "hasVersion"
        }
        
        file_mappings = {
            "Device": "Device.json",
            "DeviceProxyIn": "DeviceProxyIn.json", 
            "DeviceProxyOut": "DeviceProxyOut.json",
            "Location": "Location.json",
            "Software": "Software.json",
            "SoftwareProxyIn": "SoftwareProxyIn.json",
            "SoftwareProxyOut": "SoftwareProxyOut.json",
            "hasConnection": "hasConnection.json",
            "hasLocation": "hasLocation.json",
            "hasSoftware": "hasSoftware.json",
            "hasDeviceSoftware": "hasDeviceSoftware.json",
            "hasVersion": "hasVersion.json",
            "smartgraph_config": "smartgraph_config.json"
        }
        
        return cls(
            vertex_collections=vertex_collections,
            edge_collections=edge_collections,
            file_mappings=file_mappings
        )


@dataclass
class GenerationLimits:
    """Data generation limits and constraints."""
    
    max_generation_retries: int = 1000
    max_tenant_count: int = 100
    max_documents_per_collection: int = 10000
    max_config_changes: int = 10
    connection_timeout_seconds: int = 30
    bulk_insert_batch_size: int = 1000
    
    @classmethod
    def get_default_limits(cls) -> 'GenerationLimits':
        """Get default generation limits."""
        return cls()
    
    @classmethod
    def get_development_limits(cls) -> 'GenerationLimits':
        """Get limits suitable for development/testing."""
        return cls(
            max_generation_retries=100,
            max_tenant_count=10,
            max_documents_per_collection=1000,
            max_config_changes=5,
            bulk_insert_batch_size=100
        )


class ConfigurationManager:
    """Centralized configuration management."""
    
    def __init__(self, environment: str = "production"):
        self.environment = environment
        self.credentials = CredentialsManager.get_database_credentials(environment)
        self.paths = ApplicationPaths.initialize_default()
        self.collections = CollectionConfiguration.get_owlrdf_config()
        
        if environment == "development":
            self.limits = GenerationLimits.get_development_limits()
        else:
            self.limits = GenerationLimits.get_default_limits()
    
    def get_database_connection_params(self) -> Dict[str, str]:
        """Get database connection parameters."""
        return {
            "endpoint": self.credentials.endpoint,
            "username": self.credentials.username,
            "password": self.credentials.password,
            "database_name": self.credentials.database_name
        }
    
    def get_collection_name(self, logical_name: str) -> str:
        """Get W3C OWL compliant collection name."""
        vertex_name = self.collections.vertex_collections.get(logical_name)
        if vertex_name:
            return vertex_name
        
        edge_name = self.collections.edge_collections.get(logical_name)
        if edge_name:
            return edge_name
        
        raise ValueError(f"Unknown logical collection name: {logical_name}")
    
    def get_file_name(self, collection_name: str) -> str:
        """Get file name for collection."""
        return self.collections.file_mappings.get(collection_name, f"{collection_name}.json")
    
    def get_all_vertex_collections(self) -> Dict[str, str]:
        """Get all vertex collections."""
        return self.collections.vertex_collections
    
    def get_all_edge_collections(self) -> Dict[str, str]:
        """Get all edge collections."""
        return self.collections.edge_collections
    
    def save_configuration(self, file_path: Path = None) -> None:
        """Save current configuration to file."""
        if not file_path:
            file_path = self.paths.project_root / "current_config.json"
        
        config_data = {
            "environment": self.environment,
            "database": {
                "endpoint": self.credentials.endpoint,
                "database_name": self.credentials.database_name
                # Note: Don't save sensitive credentials to file
            },
            "collections": {
                "vertex_collections": self.collections.vertex_collections,
                "edge_collections": self.collections.edge_collections
            },
            "limits": {
                "max_generation_retries": self.limits.max_generation_retries,
                "max_tenant_count": self.limits.max_tenant_count,
                "max_documents_per_collection": self.limits.max_documents_per_collection
            }
        }
        
        with open(file_path, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    def validate_configuration(self) -> Dict[str, bool]:
        """Validate current configuration."""
        validation_results = {
            "credentials_valid": bool(self.credentials.endpoint and 
                                    self.credentials.username and 
                                    self.credentials.password),
            "paths_exist": all(path.exists() for path in [
                self.paths.data_directory,
                self.paths.docs_directory
            ]),
            "collections_configured": bool(self.collections.vertex_collections and 
                                         self.collections.edge_collections),
            "limits_reasonable": (self.limits.max_tenant_count > 0 and 
                                self.limits.max_documents_per_collection > 0)
        }
        
        return validation_results


# Global configuration instance
config = ConfigurationManager()


def get_config(environment: str = "production") -> ConfigurationManager:
    """Get global configuration instance."""
    global config
    if config.environment != environment:
        config = ConfigurationManager(environment)
    return config


def initialize_logging(log_level: str = "INFO") -> None:
    """Initialize centralized logging."""
    import logging
    
    config = get_config()
    log_file = config.paths.logs_directory / "demo.log"
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


if __name__ == "__main__":
    # Configuration validation demo
    config = get_config()
    
    print("[CONFIG] Configuration Management Validation")
    print("=" * 50)
    
    validation = config.validate_configuration()
    for check, result in validation.items():
        status = "[DONE]" if result else "[ERROR]"
        print(f"   {check}: {status}")
    
    print(f"\n Paths:")
    print(f"   Project root: {config.paths.project_root}")
    print(f"   Data directory: {config.paths.data_directory}")
    print(f"   Reports directory: {config.paths.reports_directory}")
    
    print(f"\n🏛️ Collections:")
    print(f"   Vertex collections: {len(config.collections.vertex_collections)}")
    print(f"   Edge collections: {len(config.collections.edge_collections)}")
    
    print(f"\n⚙️ Limits:")
    print(f"   Max tenants: {config.limits.max_tenant_count}")
    print(f"   Max documents: {config.limits.max_documents_per_collection}")
    
    # Save configuration
    config.save_configuration()
    print(f"\n💾 Configuration saved to: current_config.json")
