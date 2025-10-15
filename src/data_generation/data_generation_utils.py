"""
Data Generation Utilities

Reusable utility functions to eliminate code duplication in multi-tenant data generation.
"""

import random
import uuid
import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from src.config.generation_constants import NETWORK_CONSTANTS

from src.config.tenant_config import TenantConfig, TenantNamingConvention, TemporalDataModel
from src.data_generation.data_generation_config import (
    DeviceType, ConnectionType, SoftwareType, NetworkConfig, DataGenerationLimits,
    DEVICE_OS_VERSIONS, SOFTWARE_VERSIONS, DEFAULT_LOCATIONS_DATA,
    SMARTGRAPH_DEFAULTS
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
            from src.config.tenant_config import TemporalDataModel
            return TemporalDataModel.add_proxy_attributes(document, tenant_config)
        else:
            from src.config.tenant_config import TemporalDataModel
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
        
        Note: For SmartGraph compatibility, _key is NOT included to allow 
        ArangoDB to auto-generate proper SmartGraph edge keys.
        
        Eliminates duplication in edge creation across all generation functions.
        """
        edge = {
            # "_key": key,  # REMOVED: Let SmartGraph auto-generate proper edge keys
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
        return ":".join(f"{random.randint(0, NETWORK_CONSTANTS.MAC_ADDRESS_MAX_VALUE):02x}" for _ in range(NETWORK_CONSTANTS.MAC_ADDRESS_SEGMENTS))
    
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
        Generate a SmartGraph-compatible tenant-scoped key for any entity.
        
        Uses the tenantId: prefix format required for ArangoDB SmartGraphs
        to ensure proper sharding based on the tenantId shard key.
        
        Args:
            tenant_id: Tenant identifier
            entity_type: Type of entity (device, location, software, etc.)
            index: Index number for the entity
            version: Optional version number for versioned entities
            
        Returns:
            SmartGraph-compatible key string with tenantId: prefix
        """
        base_key = f"{tenant_id}:{entity_type}{index}"
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
    def generate_version_key(prefix: str, entity_key: str) -> str:
        """
        Generate a SmartGraph-compatible key for version edges.
        
        Args:
            prefix: Type prefix (e.g., 'device-in', 'software-out')
            entity_key: Entity key (already contains tenantId: prefix)
            
        Returns:
            SmartGraph-compatible key with tenantId: prefix
        """
        # Extract tenant ID from entity key (format: tenantId:entityType-version)
        if ':' in entity_key:
            tenant_id, entity_part = entity_key.split(':', 1)
            # Create SmartGraph-compatible version key
            return f"{tenant_id}:{prefix}-{entity_part}"
        else:
            # Fallback for keys without tenant prefix (shouldn't happen in SmartGraph)
            return f"{prefix}-{entity_key}"


class DeviceConfigurationManager:
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
                "devices": app_config.get_file_name("devices"),
                "device_ins": app_config.get_file_name("device_ins"), 
                "device_outs": app_config.get_file_name("device_outs"),
                "locations": app_config.get_file_name("locations"),
                "software": app_config.get_file_name("software"),
                "software_ins": app_config.get_file_name("software_ins"),
                "software_outs": app_config.get_file_name("software_outs"),
                "classes": app_config.get_file_name("classes"),  # FIXED: Use logical name directly
                "connections": app_config.get_file_name("connections"),
                "has_locations": app_config.get_file_name("has_locations"),
                "has_software": app_config.get_file_name("has_software"),
                "has_device_software": app_config.get_file_name("has_device_software"),
                "versions": app_config.get_file_name("versions"),
                "types": app_config.get_file_name("types"),  # FIXED: Use logical name directly
                "subclass_of": app_config.get_file_name("subclass_of")  # FIXED: Use logical name directly
            }
        else:
            # Use default naming convention (camelCase) when no config provided
            from src.config.config_management import get_config, NamingConvention
            default_config = get_config("production", NamingConvention.CAMEL_CASE)
            
            file_mapping = {
                "devices": default_config.get_file_name("devices"),
                "device_ins": default_config.get_file_name("device_ins"), 
                "device_outs": default_config.get_file_name("device_outs"),
                "locations": default_config.get_file_name("locations"),
                "software": default_config.get_file_name("software"),
                "software_ins": default_config.get_file_name("software_ins"),
                "software_outs": default_config.get_file_name("software_outs"),
                "classes": default_config.get_file_name("classes"),  # FIXED: Use logical name directly
                "connections": default_config.get_file_name("connections"),
                "has_locations": default_config.get_file_name("has_locations"),
                "has_software": default_config.get_file_name("has_software"),
                "has_device_software": default_config.get_file_name("has_device_software"),
                "versions": default_config.get_file_name("versions"),
                "types": default_config.get_file_name("types"),  # FIXED: Use logical name directly
                "subclass_of": default_config.get_file_name("subclass_of")  # FIXED: Use logical name directly
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


class EntityGenerator:
    """Generic entity generator to eliminate duplication between device and software generation."""
    
    def __init__(self, tenant_config: TenantConfig, random_gen: RandomDataGenerator, 
                 network_config: DeviceConfigurationManager, logger):
        self.tenant_config = tenant_config
        self.random_gen = random_gen
        self.network_config = network_config
        self.logger = logger
    
    def generate_proxy_entities(self, entity_type: str, count: int, 
                               type_selector_func, version_selector_func) -> Tuple[List[Dict], List[Dict]]:
        """Generate ProxyIn and ProxyOut collections for any entity type."""
        self.logger.info(f"Generating {count} {entity_type} proxies for tenant {self.tenant_config.tenant_name}")
        
        proxy_ins = []
        proxy_outs = []
        
        for i in range(count):
            selected_type = type_selector_func()
            selected_version = version_selector_func(selected_type)
            proxy_key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, entity_type, i + 1
            )
            
            # ProxyIn - no temporal attributes, only tenant key
            proxy_in = {
                "_key": proxy_key,
                "name": f"{self.tenant_config.tenant_name} {selected_version.split(' ')[0]}",
                "type": selected_type.value,
                "version": selected_version
            }
            proxy_in = DocumentEnhancer.add_tenant_attributes(
                proxy_in, self.tenant_config, is_proxy=True
            )
            proxy_ins.append(proxy_in)
            
            # ProxyOut - no temporal attributes, only tenant key  
            proxy_out = {
                "_key": proxy_key,
                "name": f"{self.tenant_config.tenant_name} {selected_version.split(' ')[0]}",
                "type": selected_type.value,
                "version": selected_version
            }
            proxy_out = DocumentEnhancer.add_tenant_attributes(
                proxy_out, self.tenant_config, is_proxy=True
            )
            proxy_outs.append(proxy_out)
        
        self.logger.info(f"Generated {len(proxy_ins)} {entity_type}ProxyIn and {len(proxy_outs)} {entity_type}ProxyOut entities")
        return proxy_ins, proxy_outs
    
    def generate_entity_configurations(self, entity_type: str, proxy_entities: List[Dict],
                                     config_generator_func, version_edge_creator_func,
                                     historical_generator_func) -> Tuple[List[Dict], List[Dict]]:
        """Generate entity configurations with time travel pattern."""
        self.logger.info(f"Generating {len(proxy_entities)} {entity_type} configurations for tenant {self.tenant_config.tenant_name}")
        
        entities = []
        versions = []
        
        for i, proxy_entity in enumerate(proxy_entities):
            proxy_key = proxy_entity["_key"]
            
            # Generate current configuration
            current_entity_key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, entity_type, i + 1, 0
            )
            current_created = datetime.datetime.now()
            
            # Use provided config generator function
            current_config = config_generator_func(proxy_entity, current_entity_key, i + 1)
            current_config = DocumentEnhancer.add_tenant_attributes(
                current_config, self.tenant_config, current_created
            )
            entities.append(current_config)
            
            # Create version edges for current configuration
            current_versions = version_edge_creator_func(
                entity_type, proxy_key, current_entity_key, current_created
            )
            versions.extend(current_versions)
            
            # Generate historical configurations
            historical_entities, historical_versions = historical_generator_func(
                current_config, proxy_key, i + 1
            )
            entities.extend(historical_entities)
            versions.extend(historical_versions)
        
        self.logger.info(f"Generated {len(entities)} total {entity_type} configurations with time travel")
        return entities, versions


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
        from src.config.tenant_config import SmartGraphDefinition
        
        naming = TenantNamingConvention(tenant_config.tenant_id)
        smartgraph_def = SmartGraphDefinition(naming)
        config = smartgraph_def.get_smartgraph_config()
        
        # Apply defaults from configuration
        config["options"].update(SMARTGRAPH_DEFAULTS)
        
        return config
