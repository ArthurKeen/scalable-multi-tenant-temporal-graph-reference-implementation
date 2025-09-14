"""
Data Generation Utilities

Reusable utility functions to eliminate code duplication in multi-tenant data generation.
"""

import random
import uuid
import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from tenant_config import TenantConfig, TenantNamingConvention, TemporalDataModel
from data_generation_config import (
    DeviceType, ConnectionType, SoftwareType, NetworkConfig, DataGenerationLimits,
    DEVICE_OS_VERSIONS, SOFTWARE_VERSIONS, DEFAULT_LOCATIONS_DATA,
    SMARTGRAPH_DEFAULTS, FILE_NAMES
)


class DocumentEnhancer:
    """Centralized document enhancement utilities."""
    
    @staticmethod
    def add_tenant_attributes(document: Dict[str, Any], 
                            tenant_config: TenantConfig,
                            timestamp: Optional[datetime.datetime] = None,
                            expired: Optional[int] = None,
                            is_proxy: bool = False) -> Dict[str, Any]:
        """
        Add temporal attributes and tenant key to any document.
        
        Consolidates the common pattern of adding temporal data and tenant isolation.
        For proxy collections (DeviceProxyIn/DeviceProxyOut), only adds tenant attributes.
        """
        if is_proxy:
            from tenant_config import TemporalDataModel
            return TemporalDataModel.add_proxy_attributes(document, tenant_config)
        else:
            from tenant_config import TemporalDataModel
            return TemporalDataModel.add_temporal_attributes(
                document,
                timestamp=timestamp,
                expired=expired,
                tenant_config=tenant_config
            )
    
    @staticmethod
    def create_edge_document(key: str,
                           from_collection: str, from_key: str,
                           to_collection: str, to_key: str,
                           from_type: str, to_type: str,
                           tenant_config: TenantConfig,
                           extra_attributes: Optional[Dict[str, Any]] = None,
                           timestamp: Optional[datetime.datetime] = None,
                           expired: Optional[int] = None) -> Dict[str, Any]:
        """
        Create a complete edge document with all required attributes.
        
        Eliminates duplication in edge creation across all generation functions.
        """
        edge = {
            "_key": key,
            "_from": f"{from_collection}/{from_key}",
            "_to": f"{to_collection}/{to_key}"
        }
        
        # Add any extra attributes
        if extra_attributes:
            edge.update(extra_attributes)
        
        # Add temporal attributes and tenant key
        edge = DocumentEnhancer.add_tenant_attributes(
            edge, tenant_config, timestamp, expired
        )
        
        # Add vertex-centric attributes
        edge = TemporalDataModel.add_vertex_centric_attributes(
            edge, from_type, to_type
        )
        
        return edge


class RandomDataGenerator:
    """Centralized random data generation utilities."""
    
    def __init__(self, config: NetworkConfig = None, limits: DataGenerationLimits = None):
        self.config = config or NetworkConfig()
        self.limits = limits or DataGenerationLimits()
    
    def generate_ip_address(self) -> str:
        """Generate a random IP address in the configured subnet."""
        return f"{self.config.IP_SUBNET_BASE}.{random.randint(self.config.IP_RANGE_MIN, self.config.IP_RANGE_MAX)}.{random.randint(self.config.IP_RANGE_MIN, self.config.IP_RANGE_MAX)}"
    
    def generate_mac_address(self) -> str:
        """Generate a random MAC address."""
        return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))
    
    def generate_model_name(self, device_type: DeviceType) -> str:
        """Generate a model name for a device type."""
        model_number = random.randint(self.limits.MODEL_NUMBER_MIN, self.limits.MODEL_NUMBER_MAX)
        return f"{device_type.value.capitalize()} Model {model_number}"
    
    def generate_hostname(self, tenant_id: str, device_index: int) -> str:
        """Generate a hostname for a device."""
        return f"{tenant_id}_device{device_index}"
    
    def generate_random_hostname(self, tenant_id: str) -> str:
        """Generate a random hostname for configuration changes."""
        number = random.randint(self.limits.HOSTNAME_NUMBER_MIN, self.limits.HOSTNAME_NUMBER_MAX)
        return f"{tenant_id}_new-device-{number}"
    
    def generate_bandwidth(self) -> str:
        """Generate random bandwidth specification."""
        bandwidth = random.randint(self.config.BANDWIDTH_MIN, self.config.BANDWIDTH_MAX)
        return f"{bandwidth}Mbps"
    
    def generate_latency(self) -> str:
        """Generate random latency specification."""
        latency = random.randint(self.config.LATENCY_MIN, self.config.LATENCY_MAX)
        return f"{latency}ms"
    
    def generate_firewall_rule(self) -> str:
        """Generate a random firewall rule."""
        port = random.randint(self.config.DYNAMIC_PORT_MIN, self.config.DYNAMIC_PORT_MAX)
        return f"allow {port}"
    
    def generate_software_port(self) -> int:
        """Generate a random port for software configuration."""
        return random.randint(self.config.SOFTWARE_PORT_MIN, self.config.SOFTWARE_PORT_MAX)
    
    def select_device_type(self) -> DeviceType:
        """Select a random device type."""
        return random.choice(list(DeviceType))
    
    def select_os_version(self, device_type: DeviceType) -> str:
        """Select a random OS version for a device type."""
        return random.choice(DEVICE_OS_VERSIONS[device_type])
    
    def select_software_type(self) -> SoftwareType:
        """Select a random software type."""
        return random.choice(list(SoftwareType))
    
    def select_software_version(self, software_type: SoftwareType) -> str:
        """Select a random software version for a software type."""
        return random.choice(SOFTWARE_VERSIONS[software_type])
    
    def select_connection_type(self) -> ConnectionType:
        """Select a random connection type."""
        return random.choice(list(ConnectionType))
    
    def select_random_item(self, items: List[Any]) -> Any:
        """Select a random item from a list."""
        if not items:
            raise ValueError("Cannot select from empty list")
        return random.choice(items)


class KeyGenerator:
    """Centralized key generation utilities."""
    
    @staticmethod
    def generate_tenant_key(tenant_id: str, entity_type: str, index: int, version: Optional[int] = None) -> str:
        """
        Generate a tenant-scoped key for any entity.
        
        Args:
            tenant_id: Tenant identifier
            entity_type: Type of entity (device, location, software, etc.)
            index: Index number for the entity
            version: Optional version number for versioned entities
            
        Returns:
            Formatted key string
        """
        base_key = f"{tenant_id}_{entity_type}{index}"
        if version is not None:
            return f"{base_key}-{version}"
        return base_key
    
    @staticmethod
    def generate_connection_key(tenant_id: str, connection_index: int) -> str:
        """Generate a key for connection edges."""
        return KeyGenerator.generate_tenant_key(tenant_id, "connection", connection_index)
    
    @staticmethod
    def generate_has_location_key(tenant_id: str, index: int) -> str:
        """Generate a key for hasLocation edges."""
        return KeyGenerator.generate_tenant_key(tenant_id, "hasLocation", index)
    
    @staticmethod
    def generate_has_software_key(tenant_id: str, index: int) -> str:
        """Generate a key for hasSoftware edges."""
        return KeyGenerator.generate_tenant_key(tenant_id, "hasSoftware", index)
    
    @staticmethod
    def generate_version_key(prefix: str, device_key: str) -> str:
        """Generate a key for version edges."""
        return f"{prefix}-{device_key}"


class ConfigurationManager:
    """Manages configuration changes and historical data."""
    
    def __init__(self, random_generator: RandomDataGenerator):
        self.random_generator = random_generator
    
    def apply_device_configuration_change(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a random configuration change to a device.
        
        Args:
            config: Current device configuration
            
        Returns:
            Modified configuration
        """
        new_config = config.copy()
        
        if random.random() < 0.5:
            # Modify firewall rules
            if random.random() < 0.5:
                # Add firewall rule
                new_rule = self.random_generator.generate_firewall_rule()
                if "firewallRules" not in new_config:
                    new_config["firewallRules"] = []
                new_config["firewallRules"].append(new_rule)
            else:
                # Remove firewall rule
                if "firewallRules" in new_config and len(new_config["firewallRules"]) > 0:
                    index = random.randint(0, len(new_config["firewallRules"]) - 1)
                    new_config["firewallRules"].pop(index)
        else:
            # Change hostname
            if "_key" in new_config:
                tenant_id = new_config["_key"].split("_")[0]
                new_config["hostname"] = self.random_generator.generate_random_hostname(tenant_id)
        
        return new_config
    
    def apply_software_configuration_change(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a random configuration change to software.
        
        Args:
            config: Current software configuration
            
        Returns:
            Modified configuration
        """
        new_config = config.copy()
        
        if random.random() < 0.5:
            # Change port
            new_config["port"] = self.random_generator.generate_software_port()
        else:
            # Toggle enabled status
            new_config["enabled"] = not new_config.get("enabled", True)
        
        return new_config


class FileManager:
    """Manages file I/O operations for tenant data."""
    
    @staticmethod
    def ensure_tenant_directory(tenant_config: TenantConfig) -> Path:
        """
        Ensure tenant data directory exists.
        
        Args:
            tenant_config: Tenant configuration
            
        Returns:
            Path to tenant directory
        """
        naming = TenantNamingConvention(tenant_config.tenant_id)
        data_dir = Path(naming.data_directory)
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    
    @staticmethod
    def write_json_file(file_path: Path, data: Any) -> None:
        """
        Write data to JSON file with consistent formatting.
        
        Args:
            file_path: Path to output file
            data: Data to write
        """
        import json
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def write_tenant_data_files(tenant_config: TenantConfig,
                               data_collections: Dict[str, List[Dict]],
                               app_config=None) -> None:
        """
        Write all tenant data files using consistent naming and formatting.
        
        Args:
            tenant_config: Tenant configuration
            data_collections: Dictionary mapping collection types to data
            app_config: Application configuration (optional, uses default if None)
        """
        data_dir = FileManager.ensure_tenant_directory(tenant_config)
        
        # Use app configuration for file names if provided, otherwise fall back to hardcoded names
        if app_config:
            file_mapping = {
                "devices": app_config.get_file_name(app_config.get_collection_name("devices")),
                "device_ins": app_config.get_file_name(app_config.get_collection_name("device_ins")), 
                "device_outs": app_config.get_file_name(app_config.get_collection_name("device_outs")),
                "locations": app_config.get_file_name(app_config.get_collection_name("locations")),
                "software": app_config.get_file_name(app_config.get_collection_name("software")),
                "software_ins": app_config.get_file_name(app_config.get_collection_name("software_ins")),
                "software_outs": app_config.get_file_name(app_config.get_collection_name("software_outs")),
                "connections": app_config.get_file_name(app_config.get_collection_name("connections")),
                "has_locations": app_config.get_file_name(app_config.get_collection_name("has_locations")),
                "has_software": app_config.get_file_name(app_config.get_collection_name("has_software")),
                "has_device_software": app_config.get_file_name(app_config.get_collection_name("has_device_software")),
                "versions": app_config.get_file_name(app_config.get_collection_name("versions"))
            }
        else:
            # Fallback to hardcoded names for backward compatibility
            file_mapping = {
                "devices": FILE_NAMES["devices"],
                "device_ins": FILE_NAMES["device_ins"], 
                "device_outs": FILE_NAMES["device_outs"],
                "locations": FILE_NAMES["locations"],
                "software": FILE_NAMES["software"],
                "software_ins": FILE_NAMES["software_ins"],
                "software_outs": FILE_NAMES["software_outs"],
                "connections": FILE_NAMES["connections"],
                "has_locations": FILE_NAMES["has_locations"],
                "has_software": FILE_NAMES["has_software"],
                "has_device_software": FILE_NAMES["has_device_software"],
                "versions": FILE_NAMES["versions"]
            }
        
        total_documents = 0
        for collection_type, data in data_collections.items():
            if collection_type in file_mapping:
                file_path = data_dir / file_mapping[collection_type]
                FileManager.write_json_file(file_path, data)
                total_documents += len(data)
        
        print(f"Generated {len(file_mapping)} data files for tenant '{tenant_config.tenant_name}' ({tenant_config.tenant_id})")
        print(f"  -> {data_dir}")
        print(f"  -> {total_documents} total documents")


class LocationDataProvider:
    """Provides location data with cycling support for large datasets."""
    
    def __init__(self, locations_data: Optional[List[Dict]] = None):
        self.locations_data = locations_data or DEFAULT_LOCATIONS_DATA
    
    def get_location_data(self, index: int) -> Dict[str, Any]:
        """
        Get location data by index, cycling through available data.
        
        Args:
            index: Location index
            
        Returns:
            Location data dictionary
        """
        return self.locations_data[index % len(self.locations_data)]
    
    def get_all_locations(self) -> List[Dict[str, Any]]:
        """Get all available location data."""
        return self.locations_data.copy()


class SmartGraphConfigGenerator:
    """Generates SmartGraph configurations with consistent defaults."""
    
    @staticmethod
    def generate_config(tenant_config: TenantConfig) -> Dict[str, Any]:
        """
        Generate SmartGraph configuration for a tenant.
        
        Args:
            tenant_config: Tenant configuration
            
        Returns:
            Complete SmartGraph configuration
        """
        from tenant_config import SmartGraphDefinition
        
        naming = TenantNamingConvention(tenant_config.tenant_id)
        smartgraph_def = SmartGraphDefinition(naming)
        config = smartgraph_def.get_smartgraph_config()
        
        # Apply defaults from configuration
        config["options"].update(SMARTGRAPH_DEFAULTS)
        
        return config
