"""
Centralized Configuration and Credentials Management

Eliminates hard-wired values throughout the codebase and provides
secure credential management for the multi-tenant demo.
"""

import os
import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, Any
from enum import Enum


# Import centralized credentials to avoid duplication
from centralized_credentials import DatabaseCredentials, CredentialsManager


class NamingConvention(Enum):
    """Supported naming conventions for collections and properties."""
    CAMEL_CASE = "camelCase"
    SNAKE_CASE = "snake_case"


class NamingConverter:
    """Utility class for converting between naming conventions."""
    
    @staticmethod
    def camel_to_snake(name: str) -> str:
        """Convert camelCase to snake_case."""
        # Handle special cases first
        if name == "hasConnection":
            return "has_connection"
        elif name == "hasLocation":
            return "has_location"
        elif name == "hasDeviceSoftware":
            return "has_device_software"
        elif name == "hasVersion":
            return "has_version"
        elif name == "DeviceProxyIn":
            return "device_proxy_in"
        elif name == "DeviceProxyOut":
            return "device_proxy_out"
        elif name == "SoftwareProxyIn":
            return "software_proxy_in"
        elif name == "SoftwareProxyOut":
            return "software_proxy_out"
        
        # General conversion: insert underscore before uppercase letters
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    @staticmethod
    def snake_to_camel(name: str, pascal_case: bool = False) -> str:
        """Convert snake_case to camelCase or PascalCase."""
        # Handle special cases first
        if name == "has_connection":
            return "hasConnection"
        elif name == "has_location":
            return "hasLocation"
        elif name == "has_device_software":
            return "hasDeviceSoftware"
        elif name == "has_version":
            return "hasVersion"
        elif name == "device_proxy_in":
            return "DeviceProxyIn"
        elif name == "device_proxy_out":
            return "DeviceProxyOut"
        elif name == "software_proxy_in":
            return "SoftwareProxyIn"
        elif name == "software_proxy_out":
            return "SoftwareProxyOut"
        
        # General conversion
        components = name.split('_')
        if pascal_case:
            return ''.join(word.capitalize() for word in components)
        else:
            return components[0] + ''.join(word.capitalize() for word in components[1:])
    
    @staticmethod
    def convert_name(name: str, from_convention: NamingConvention, 
                    to_convention: NamingConvention, is_vertex: bool = False) -> str:
        """Convert name between conventions."""
        if from_convention == to_convention:
            return name
        
        if from_convention == NamingConvention.CAMEL_CASE and to_convention == NamingConvention.SNAKE_CASE:
            return NamingConverter.camel_to_snake(name)
        elif from_convention == NamingConvention.SNAKE_CASE and to_convention == NamingConvention.CAMEL_CASE:
            # Vertex collections use PascalCase, edge collections use camelCase
            return NamingConverter.snake_to_camel(name, pascal_case=is_vertex)
        
        return name


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
    """Collection configuration supporting multiple naming conventions."""
    
    # Vertex collections (PascalCase/snake_case, singular)
    vertex_collections: Dict[str, str]
    # Edge collections (camelCase/snake_case, singular)  
    edge_collections: Dict[str, str]
    # File name mappings
    file_mappings: Dict[str, str]
    # Naming convention used
    naming_convention: NamingConvention
    
    @classmethod
    def get_camel_case_config(cls) -> 'CollectionConfiguration':
        """Get camelCase naming convention configuration."""
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
            file_mappings=file_mappings,
            naming_convention=NamingConvention.CAMEL_CASE
        )
    
    @classmethod
    def get_snake_case_config(cls) -> 'CollectionConfiguration':
        """Get snake_case naming convention configuration."""
        vertex_collections = {
            "devices": "device",
            "device_ins": "device_proxy_in", 
            "device_outs": "device_proxy_out",
            "locations": "location",
            "software": "software",
            "software_ins": "software_proxy_in",
            "software_outs": "software_proxy_out"
        }
        
        edge_collections = {
            "connections": "has_connection",
            "has_locations": "has_location", 
            "has_software": "has_software",
            "has_device_software": "has_device_software",
            "versions": "has_version"
        }
        
        file_mappings = {
            "device": "device.json",
            "device_proxy_in": "device_proxy_in.json", 
            "device_proxy_out": "device_proxy_out.json",
            "location": "location.json",
            "software": "software.json",
            "software_proxy_in": "software_proxy_in.json",
            "software_proxy_out": "software_proxy_out.json",
            "has_connection": "has_connection.json",
            "has_location": "has_location.json",
            "has_software": "has_software.json",
            "has_device_software": "has_device_software.json",
            "has_version": "has_version.json",
            "smartgraph_config": "smartgraph_config.json"
        }
        
        return cls(
            vertex_collections=vertex_collections,
            edge_collections=edge_collections,
            file_mappings=file_mappings,
            naming_convention=NamingConvention.SNAKE_CASE
        )
    
    @classmethod
    def get_config(cls, naming_convention: NamingConvention) -> 'CollectionConfiguration':
        """Get configuration for specified naming convention."""
        if naming_convention == NamingConvention.CAMEL_CASE:
            return cls.get_camel_case_config()
        elif naming_convention == NamingConvention.SNAKE_CASE:
            return cls.get_snake_case_config()
        else:
            raise ValueError(f"Unsupported naming convention: {naming_convention}")
    
    # Backward compatibility
    @classmethod
    def get_owlrdf_config(cls) -> 'CollectionConfiguration':
        """Get camelCase configuration (backward compatibility)."""
        return cls.get_camel_case_config()


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
    
    def __init__(self, environment: str = "production", naming_convention: NamingConvention = NamingConvention.CAMEL_CASE):
        self.environment = environment
        self.naming_convention = naming_convention
        self.credentials = CredentialsManager.get_database_credentials(environment)
        self.paths = ApplicationPaths.initialize_default()
        self.collections = CollectionConfiguration.get_config(naming_convention)
        
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
        """Get collection name using configured naming convention."""
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


# Global configuration instance (default: camelCase)
config = ConfigurationManager()


def get_config(environment: str = "production", naming_convention: NamingConvention = NamingConvention.CAMEL_CASE) -> ConfigurationManager:
    """Get global configuration instance."""
    global config
    if config.environment != environment or config.naming_convention != naming_convention:
        config = ConfigurationManager(environment, naming_convention)
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
