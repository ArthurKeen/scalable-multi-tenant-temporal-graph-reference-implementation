"""
Time Travel Refactored Multi-Tenant Generator

Implements consistent time travel pattern across ALL collections:
- Device: DeviceProxyIn ⟷ Device ⟷ DeviceProxyOut (existing)
- Software: SoftwareProxyIn ⟷ Software ⟷ SoftwareProxyOut (NEW)
- Generic 'version' collection for all time travel relationships
- W3C OWL naming conventions
- Multi-tenant disjoint SmartGraphs
"""

import json
import datetime
import sys
from typing import Dict, List, Any, Tuple
from pathlib import Path

# Import centralized configuration
from config_management import get_config, initialize_logging
from tenant_config import TenantConfig, TenantNamingConvention, create_tenant_config
from data_generation_utils import (
    DocumentEnhancer, RandomDataGenerator, KeyGenerator,
    ConfigurationManager as DataConfigManager, FileManager, LocationDataProvider,
    SmartGraphConfigGenerator
)


class TimeTravelRefactoredGenerator:
    """Complete refactored multi-tenant generator with consistent time travel patterns."""
    
    def __init__(self, tenant_config: TenantConfig, environment: str = "production"):
        self.tenant_config = tenant_config
        self.app_config = get_config(environment)
        self.naming = TenantNamingConvention(tenant_config.tenant_id)
        
        # Initialize data generation components
        from data_generation_config import NetworkConfig, DataGenerationLimits
        self.network_config = NetworkConfig()
        self.limits = DataGenerationLimits()
        self.random_gen = RandomDataGenerator(self.network_config, self.limits)
        self.config_manager = DataConfigManager(self.random_gen)
        self.location_provider = LocationDataProvider()
        
        # Setup logging
        initialize_logging()
        import logging
        self.logger = logging.getLogger(__name__)
    
    # === LOCATION COLLECTION (unchanged) ===
    def generate_locations(self) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant location data."""
        self.logger.info(f"Generating {self.tenant_config.num_locations} locations for tenant {self.tenant_config.tenant_name}")
        
        locations = []
        
        for i in range(self.tenant_config.num_locations):
            loc_data = self.location_provider.get_location_data(i)
            
            location = {
                "_key": KeyGenerator.generate_tenant_key(
                    self.tenant_config.tenant_id, "location", i + 1
                ),
                "name": f"{self.tenant_config.tenant_name} - {loc_data['name']}",
                "streetAddress": loc_data["address"],
                "geoLocation": {
                    "type": "Point",
                    "coordinates": [loc_data["lon"], loc_data["lat"]]
                }
            }
            
            location = DocumentEnhancer.add_tenant_attributes(location, self.tenant_config)
            locations.append(location)
        
        self.logger.info(f"Generated {len(locations)} location entities")
        return locations
    
    # === DEVICE TIME TRAVEL (existing pattern) ===
    def generate_device_proxies(self) -> Tuple[List[Dict], List[Dict]]:
        """Generate DeviceProxyIn and DeviceProxyOut collections."""
        self.logger.info(f"Generating {self.tenant_config.num_devices} device proxies for tenant {self.tenant_config.tenant_name}")
        
        device_proxy_ins = []
        device_proxy_outs = []
        
        for i in range(self.tenant_config.num_devices):
            device_type = self.random_gen.select_device_type()
            model = self.random_gen.generate_model_name(device_type)
            proxy_key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "device", i + 1
            )
            
            # DeviceProxyIn - no temporal attributes, only tenant key
            device_proxy_in = {
                "_key": proxy_key,
                "name": f"{self.tenant_config.tenant_name} {device_type.value} {model} proxy in",
                "type": device_type.value
            }
            device_proxy_in = DocumentEnhancer.add_tenant_attributes(device_proxy_in, self.tenant_config, is_proxy=True)
            device_proxy_ins.append(device_proxy_in)
            
            # DeviceProxyOut - no temporal attributes, only tenant key  
            device_proxy_out = {
                "_key": proxy_key,
                "name": f"{self.tenant_config.tenant_name} {device_type.value} {model} proxy out",
                "type": device_type.value
            }
            device_proxy_out = DocumentEnhancer.add_tenant_attributes(device_proxy_out, self.tenant_config, is_proxy=True)
            device_proxy_outs.append(device_proxy_out)
        
        self.logger.info(f"Generated {len(device_proxy_ins)} DeviceProxyIn and {len(device_proxy_outs)} DeviceProxyOut entities")
        return device_proxy_ins, device_proxy_outs
    
    def generate_device_configurations(self, device_proxy_ins: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Generate versioned Device configurations."""
        self.logger.info(f"Generating device configurations with {self.tenant_config.num_config_changes} historical versions")
        
        devices = []
        versions = []
        
        for i, device_proxy_in in enumerate(device_proxy_ins):
            device_type_str = device_proxy_in["type"]
            from data_generation_config import DeviceType
            device_type = DeviceType(device_type_str)
            
            os_version = self.random_gen.select_os_version(device_type)
            model = self.random_gen.generate_model_name(device_type)
            proxy_key = device_proxy_in["_key"]
            
            # Generate current configuration
            current_device_key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "device", i + 1, 0
            )
            current_created = datetime.datetime.now()
            
            current_config = {
                "_key": current_device_key,
                "name": f"{self.tenant_config.tenant_name} {device_type.value} {model}",
                "type": device_type.value,
                "model": model,
                "serialNumber": str(__import__('uuid').uuid4()),
                "ipAddress": self.random_gen.generate_ip_address(),
                "macAddress": self.random_gen.generate_mac_address(),
                "operatingSystem": os_version.split(" ")[0],
                "osVersion": os_version,
                "hostName": self.random_gen.generate_hostname(self.tenant_config.tenant_id, i + 1),
                "firewallRules": self.network_config.DEFAULT_FIREWALL_RULES.copy()
            }
            current_config = DocumentEnhancer.add_tenant_attributes(
                current_config, self.tenant_config, current_created
            )
            devices.append(current_config)
            
            # Create version edges for current configuration
            current_versions = self._create_version_edges(
                "device", proxy_key, current_device_key, current_created
            )
            versions.extend(current_versions)
            
            # Generate historical configurations
            historical_devices, historical_versions = self._generate_historical_device_configurations(
                current_config, proxy_key, i + 1
            )
            devices.extend(historical_devices)
            versions.extend(historical_versions)
        
        self.logger.info(f"Generated {len(devices)} device configurations and {len(versions)} device version edges")
        return devices, versions
    
    def _create_version_edges(self, entity_type: str, proxy_key: str, entity_key: str, 
                            timestamp: datetime.datetime) -> List[Dict[str, Any]]:
        """Create version edges for any entity type (Device or Software) time travel."""
        if entity_type == "device":
            proxy_in_collection = self.app_config.get_collection_name("device_ins")
            proxy_out_collection = self.app_config.get_collection_name("device_outs")
            entity_collection = self.app_config.get_collection_name("devices")
            proxy_in_type = "DeviceProxyIn"
            proxy_out_type = "DeviceProxyOut"
            entity_type_name = "Device"
        elif entity_type == "software":
            proxy_in_collection = self.app_config.get_collection_name("software_ins")
            proxy_out_collection = self.app_config.get_collection_name("software_outs")
            entity_collection = self.app_config.get_collection_name("software")
            proxy_in_type = "SoftwareProxyIn"
            proxy_out_type = "SoftwareProxyOut"
            entity_type_name = "Software"
        else:
            raise ValueError(f"Unsupported entity type: {entity_type}")
        
        version_in = DocumentEnhancer.create_edge_document(
            key=KeyGenerator.generate_version_key(f"{entity_type}-in", entity_key),
            from_collection=proxy_in_collection,
            from_key=proxy_key,
            to_collection=entity_collection,
            to_key=entity_key,
            from_type=proxy_in_type,
            to_type=entity_type_name,
            tenant_config=self.tenant_config,
            timestamp=timestamp
        )
        
        version_out = DocumentEnhancer.create_edge_document(
            key=KeyGenerator.generate_version_key(f"{entity_type}-out", entity_key),
            from_collection=entity_collection,
            from_key=entity_key,
            to_collection=proxy_out_collection,
            to_key=proxy_key,
            from_type=entity_type_name,
            to_type=proxy_out_type,
            tenant_config=self.tenant_config,
            timestamp=timestamp
        )
        
        return [version_in, version_out]
    
    def _generate_historical_device_configurations(self, current_config: Dict[str, Any], 
                                                 proxy_key: str, device_index: int) -> Tuple[List[Dict], List[Dict]]:
        """Generate historical device configurations with proper temporal attributes."""
        historical_devices = []
        historical_versions = []
        
        for change_no in range(self.tenant_config.num_config_changes):
            previous_config = self.config_manager.apply_device_configuration_change(current_config)
            key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "device", device_index, change_no + 1
            )
            previous_config["_key"] = key
            
            # Ensure proper W3C OWL property naming
            if "hostname" in previous_config:
                previous_config["hostName"] = previous_config.pop("hostname")
            elif "_key" in previous_config:
                tenant_id = previous_config["_key"].split("_")[0]
                previous_config["hostName"] = self.random_gen.generate_random_hostname(tenant_id)
            
            # Set temporal timestamps
            created = datetime.datetime.now() - datetime.timedelta(
                days=__import__('random').randint(change_no*5+1, (change_no+1)*5)
            )
            expired = previous_config["created"]  # Historical records expire when replaced
            
            previous_config = DocumentEnhancer.add_tenant_attributes(
                previous_config, self.tenant_config, created, expired
            )
            historical_devices.append(previous_config)
            
            # Create version edges for historical configuration
            historical_version_edges = self._create_version_edges("device", proxy_key, key, created)
            for edge in historical_version_edges:
                edge["expired"] = expired
            historical_versions.extend(historical_version_edges)
            
            current_config = previous_config
        
        return historical_devices, historical_versions
    
    # === SOFTWARE TIME TRAVEL (NEW refactored pattern) ===
    def generate_software_proxies(self) -> Tuple[List[Dict], List[Dict]]:
        """Generate SoftwareProxyIn and SoftwareProxyOut collections (no temporal attributes)."""
        self.logger.info(f"Generating {self.tenant_config.num_software} software proxies for tenant {self.tenant_config.tenant_name}")
        
        software_proxy_ins = []
        software_proxy_outs = []
        
        for i in range(self.tenant_config.num_software):
            software_type = self.random_gen.select_software_type()
            software_version = self.random_gen.select_software_version(software_type)
            proxy_key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "software", i + 1
            )
            
            # SoftwareProxyIn - no temporal attributes, only tenant key
            software_proxy_in = {
                "_key": proxy_key,
                "name": f"{self.tenant_config.tenant_name} {software_version.split(' ')[0]}",
                "type": software_type.value,
                "version": software_version
            }
            software_proxy_in = DocumentEnhancer.add_tenant_attributes(
                software_proxy_in, self.tenant_config, is_proxy=True
            )
            software_proxy_ins.append(software_proxy_in)
            
            # SoftwareProxyOut - no temporal attributes, only tenant key  
            software_proxy_out = {
                "_key": proxy_key,
                "name": f"{self.tenant_config.tenant_name} {software_version.split(' ')[0]}",
                "type": software_type.value,
                "version": software_version
            }
            software_proxy_out = DocumentEnhancer.add_tenant_attributes(
                software_proxy_out, self.tenant_config, is_proxy=True
            )
            software_proxy_outs.append(software_proxy_out)
        
        self.logger.info(f"Generated {len(software_proxy_ins)} SoftwareProxyIn and {len(software_proxy_outs)} SoftwareProxyOut entities")
        return software_proxy_ins, software_proxy_outs
    
    def generate_software_configurations(self, software_proxy_ins: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Generate versioned Software configurations (NO configurationHistory array)."""
        self.logger.info(f"Generating software configurations with {self.tenant_config.num_config_changes} historical versions")
        
        software = []
        versions = []
        
        for i, software_proxy_in in enumerate(software_proxy_ins):
            software_type_str = software_proxy_in["type"]
            from data_generation_config import SoftwareType
            software_type = SoftwareType(software_type_str)
            
            software_version = software_proxy_in["version"]
            proxy_key = software_proxy_in["_key"]
            
            # Generate current configuration (FLATTENED - no configurationHistory array)
            current_software_key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "software", i + 1, 0
            )
            current_created = datetime.datetime.now()
            
            current_config = {
                "_key": current_software_key,
                "name": software_proxy_in["name"],
                "type": software_type.value,
                "version": software_version,
                # Flattened configuration - no configurationHistory array
                "portNumber": self.random_gen.generate_software_port(),
                "isEnabled": True
            }
            current_config = DocumentEnhancer.add_tenant_attributes(
                current_config, self.tenant_config, current_created
            )
            software.append(current_config)
            
            # Create version edges for current configuration
            current_versions = self._create_version_edges(
                "software", proxy_key, current_software_key, current_created
            )
            versions.extend(current_versions)
            
            # Generate historical configurations (flattened, no array)
            historical_software, historical_versions = self._generate_historical_software_configurations(
                current_config, proxy_key, i + 1
            )
            software.extend(historical_software)
            versions.extend(historical_versions)
        
        self.logger.info(f"Generated {len(software)} software configurations and {len(versions)} software version edges")
        return software, versions
    
    
    def _generate_historical_software_configurations(self, current_config: Dict[str, Any], 
                                                   proxy_key: str, software_index: int) -> Tuple[List[Dict], List[Dict]]:
        """Generate historical software configurations with proper temporal attributes."""
        historical_software = []
        historical_versions = []
        
        for change_no in range(self.tenant_config.num_config_changes):
            previous_config = self.config_manager.apply_software_configuration_change(current_config)
            key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "software", software_index, change_no + 1
            )
            previous_config["_key"] = key
            
            # Ensure W3C OWL property naming
            if "port" in previous_config:
                previous_config["portNumber"] = previous_config.pop("port")
            if "enabled" in previous_config:
                previous_config["isEnabled"] = previous_config.pop("enabled")
            
            # Set temporal timestamps
            created = datetime.datetime.now() - datetime.timedelta(
                days=__import__('random').randint(change_no*5+1, (change_no+1)*5)
            )
            expired = previous_config["created"]  # Historical records expire when replaced
            
            previous_config = DocumentEnhancer.add_tenant_attributes(
                previous_config, self.tenant_config, created, expired
            )
            historical_software.append(previous_config)
            
            # Create version edges for historical configuration
            historical_version_edges = self._create_version_edges("software", proxy_key, key, created)
            for edge in historical_version_edges:
                edge["expired"] = expired
            historical_versions.extend(historical_version_edges)
            
            current_config = previous_config
        
        return historical_software, historical_versions
    
    # === RELATIONSHIP EDGES ===
    def generate_connections(self, device_proxy_ins: List[Dict], device_proxy_outs: List[Dict]) -> List[Dict[str, Any]]:
        """Generate hasConnection edges ensuring better network connectivity."""
        self.logger.info(f"Generating hasConnection edges with improved connectivity")
        
        connections = []
        used_pairs = set()
        
        # Ensure we have enough unique pairs possible
        max_possible_connections = len(device_proxy_outs) * (len(device_proxy_ins) - 1)  # Exclude self-connections
        target_connections = min(self.tenant_config.num_connections, max_possible_connections)
        
        attempts = 0
        while len(connections) < target_connections and attempts < self.limits.MAX_GENERATION_RETRIES:
            from_device = self.random_gen.select_random_item(device_proxy_outs)
            to_device = self.random_gen.select_random_item(device_proxy_ins)
            
            # Prevent self loops and duplicate connections
            connection_pair = (from_device["_key"], to_device["_key"])
            if from_device["_key"] != to_device["_key"] and connection_pair not in used_pairs:
                connection_key = KeyGenerator.generate_connection_key(
                    self.tenant_config.tenant_id, len(connections) + 1
                )
                
                connection_attrs = {
                    "connectionType": self.random_gen.select_connection_type().value,
                    "bandwidthCapacity": self.random_gen.generate_bandwidth(),
                    "networkLatency": self.random_gen.generate_latency()
                }
                
                connection = DocumentEnhancer.create_edge_document(
                    key=connection_key,
                    from_collection=self.app_config.get_collection_name("device_outs"),  # DeviceProxyOut
                    from_key=from_device["_key"],
                    to_collection=self.app_config.get_collection_name("device_ins"),  # DeviceProxyIn
                    to_key=to_device["_key"],
                    from_type="DeviceProxyOut",
                    to_type="DeviceProxyIn",
                    tenant_config=self.tenant_config,
                    extra_attributes=connection_attrs
                )
                
                connections.append(connection)
                used_pairs.add(connection_pair)
            
            attempts += 1
        
        self.logger.info(f"Generated {len(connections)} hasConnection edges")
        return connections
    
    def generate_has_location_edges(self, device_proxy_outs: List[Dict], locations: List[Dict]) -> List[Dict[str, Any]]:
        """Generate hasLocation edges (Device → Location relationships)."""
        self.logger.info("Generating hasLocation edges")
        
        has_locations = []
        
        for device in device_proxy_outs:
            location = self.random_gen.select_random_item(locations)
            key = KeyGenerator.generate_has_location_key(
                self.tenant_config.tenant_id, len(has_locations) + 1
            )
            
            has_location = DocumentEnhancer.create_edge_document(
                key=key,
                from_collection=self.app_config.get_collection_name("device_outs"),  # DeviceProxyOut
                from_key=device["_key"],
                to_collection=self.app_config.get_collection_name("locations"),  # Location
                to_key=location["_key"],
                from_type="DeviceProxyOut",
                to_type="Location",
                tenant_config=self.tenant_config
            )
            
            has_locations.append(has_location)
        
        self.logger.info(f"Generated {len(has_locations)} hasLocation edges")
        return has_locations
    
    def generate_has_device_software_edges(self, device_proxy_outs: List[Dict], 
                                         software_proxy_ins: List[Dict]) -> List[Dict[str, Any]]:
        """Generate hasDeviceSoftware edges ensuring all software entities are connected."""
        self.logger.info(f"Generating hasDeviceSoftware edges with improved connectivity")
        
        has_device_software = []
        connected_software = set()
        
        # Filter out routers (they don't run additional software)
        non_router_devices = [d for d in device_proxy_outs if d["type"] != "router"]
        
        if not non_router_devices:
            self.logger.warning("No non-router devices available for software connections")
            return has_device_software
        
        # PHASE 1: Ensure every software entity gets at least one connection
        for i, software_proxy in enumerate(software_proxy_ins):
            device = self.random_gen.select_random_item(non_router_devices)
            key = KeyGenerator.generate_has_software_key(
                self.tenant_config.tenant_id, len(has_device_software) + 1
            )
            
            has_device_software_edge = DocumentEnhancer.create_edge_document(
                key=key,
                from_collection=self.app_config.get_collection_name("device_outs"),  # DeviceProxyOut
                from_key=device["_key"],
                to_collection=self.app_config.get_collection_name("software_ins"),  # SoftwareProxyIn
                to_key=software_proxy["_key"],
                from_type="DeviceProxyOut",
                to_type="SoftwareProxyIn",
                tenant_config=self.tenant_config
            )
            
            has_device_software.append(has_device_software_edge)
            connected_software.add(software_proxy["_key"])
        
        # PHASE 2: Add additional connections to reach target count
        attempts = 0
        target_additional = max(0, self.tenant_config.num_has_software - len(software_proxy_ins))
        
        while len(has_device_software) < len(software_proxy_ins) + target_additional and attempts < self.limits.MAX_GENERATION_RETRIES:
            device = self.random_gen.select_random_item(non_router_devices)
            software_proxy = self.random_gen.select_random_item(software_proxy_ins)
            
            # Create unique edge key to avoid duplicates
            edge_signature = f"{device['_key']}->{software_proxy['_key']}"
            existing_signatures = {f"{e['_from'].split('/')[1]}->{e['_to'].split('/')[1]}" for e in has_device_software}
            
            if edge_signature not in existing_signatures:
                key = KeyGenerator.generate_has_software_key(
                    self.tenant_config.tenant_id, len(has_device_software) + 1
                )
                
                has_device_software_edge = DocumentEnhancer.create_edge_document(
                    key=key,
                    from_collection=self.app_config.get_collection_name("device_outs"),  # DeviceProxyOut
                    from_key=device["_key"],
                    to_collection=self.app_config.get_collection_name("software_ins"),  # SoftwareProxyIn
                    to_key=software_proxy["_key"],
                    from_type="DeviceProxyOut",
                    to_type="SoftwareProxyIn",
                    tenant_config=self.tenant_config
                )
                
                has_device_software.append(has_device_software_edge)
            
            attempts += 1
        
        self.logger.info(f"Generated {len(has_device_software)} hasDeviceSoftware edges")
        self.logger.info(f"Connected {len(connected_software)} software entities (100% coverage)")
        return has_device_software
    
    # === MAIN GENERATION METHOD ===
    def generate_all_data(self) -> Dict[str, Any]:
        """Generate complete time travel refactored network asset data."""
        self.logger.info(f"Starting time travel refactored data generation for tenant: {self.tenant_config.tenant_name} (Scale: {self.tenant_config.scale_factor}x)")
        
        # Generate all data collections
        locations = self.generate_locations()
        device_proxy_ins, device_proxy_outs = self.generate_device_proxies()
        devices, device_versions = self.generate_device_configurations(device_proxy_ins)
        software_proxy_ins, software_proxy_outs = self.generate_software_proxies()
        software, software_versions = self.generate_software_configurations(software_proxy_ins)
        
        # Generate relationship edges
        connections = self.generate_connections(device_proxy_ins, device_proxy_outs)
        has_locations = self.generate_has_location_edges(device_proxy_outs, locations)
        has_device_software = self.generate_has_device_software_edges(device_proxy_outs, software_proxy_ins)
        
        # Combine all version edges (unified collection)
        all_versions = device_versions + software_versions
        
        # Organize data collections using centralized configuration
        data_collections = {
            "devices": devices,
            "device_ins": device_proxy_ins,
            "device_outs": device_proxy_outs,
            "locations": locations,
            "software": software,
            "software_ins": software_proxy_ins,  # NEW
            "software_outs": software_proxy_outs,  # NEW
            "connections": connections,
            "has_locations": has_locations,
            "has_device_software": has_device_software,  # NEW (replaces has_software)
            "versions": all_versions  # UNIFIED - contains both device and software versions
        }
        
        # Write data files using centralized file management
        FileManager.write_tenant_data_files(self.tenant_config, data_collections)
        
        # Generate and write SmartGraph configuration
        smartgraph_config = SmartGraphConfigGenerator.generate_config(self.tenant_config)
        tenant_data_path = self.app_config.paths.get_tenant_data_path(self.tenant_config.tenant_id)
        config_file = tenant_data_path / self.app_config.get_file_name("smartgraph_config")
        FileManager.write_json_file(config_file, smartgraph_config)
        
        total_documents = sum(len(data) for data in data_collections.values())
        self.logger.info(f"Completed time travel refactored data generation: {total_documents} total documents")
        
        print(f"✅ Generated {total_documents} time travel refactored documents")
        print(f"   Device entities: {len(devices)} devices, {len(device_proxy_ins)} DeviceProxyIn, {len(device_proxy_outs)} DeviceProxyOut")
        print(f"   Software entities: {len(software)} software, {len(software_proxy_ins)} SoftwareProxyIn, {len(software_proxy_outs)} SoftwareProxyOut")
        print(f"   Location entities: {len(locations)} locations")
        print(f"   Relationship edges: {len(connections)} hasConnection, {len(has_locations)} hasLocation, {len(has_device_software)} hasDeviceSoftware")
        print(f"   Version edges: {len(all_versions)} version (unified - {len(device_versions)} device + {len(software_versions)} software)")
        print(f"   🔄 Consistent time travel pattern: Generic 'version' collection for all entities")
        
        return {
            "tenant_config": self.tenant_config,
            "data_counts": {key: len(data) for key, data in data_collections.items()},
            "smartgraph_config": smartgraph_config,
            "data_directory": self.naming.data_directory
        }


def generate_time_travel_refactored_demo(environment: str = "production"):
    """Generate time travel refactored multi-tenant demo."""
    
    print("🔄 Time Travel Refactored Multi-Tenant Generation")
    print("=" * 60)
    print("📋 Time travel patterns:")
    print("   • Device: DeviceProxyIn ⟷ Device ⟷ DeviceProxyOut")
    print("   • Software: SoftwareProxyIn ⟷ Software ⟷ SoftwareProxyOut (NEW)")
    print("   • Generic 'version' collection for all time travel relationships")
    print("   • Consistent temporal queries across all entities")
    print()
    
    app_config = get_config(environment)
    
    # Create tenant configurations
    tenant_configs = [
        create_tenant_config(
            "Acme Corp",
            scale_factor=1,
            description="Small enterprise with refactored time travel"
        ),
        create_tenant_config(
            "Global Enterprises", 
            scale_factor=2,
            description="Large enterprise with refactored time travel"
        )
    ]
    
    results = {}
    total_documents = 0
    
    # Generate data for each tenant
    for tenant_config in tenant_configs:
        generator = TimeTravelRefactoredGenerator(tenant_config, environment)
        tenant_result = generator.generate_all_data()
        results[tenant_config.tenant_id] = tenant_result
        total_documents += sum(tenant_result["data_counts"].values())
    
    # Generate centralized tenant registry
    tenant_registry = {
        "tenants": {
            config.tenant_id: {
                "tenantName": config.tenant_name,
                "tenantStatus": config.status.value,
                "databaseName": config.database_name,
                "smartGraphName": f"tenant_{config.tenant_id}_network_assets",
                "smartGraphAttribute": config.smartgraph_attribute,
                "dataDirectory": app_config.paths.get_tenant_data_path(config.tenant_id).as_posix(),
                "scaleFactor": config.scale_factor,
                "createdAt": config.created_at.isoformat(),
                "tenantDescription": config.description
            }
            for config in tenant_configs
        },
        "summary": {
            "totalTenants": len(tenant_configs),
            "totalDocuments": total_documents,
            "sharedDatabase": app_config.credentials.database_name,
            "generatedAt": datetime.datetime.now().isoformat(),
            "environment": environment,
            "owlCompliant": True,
            "timeTravel": {
                "refactored": True,
                "consistentPattern": True,
                "deviceTimeTravel": "DeviceProxyIn ⟷ Device ⟷ DeviceProxyOut",
                "softwareTimeTravel": "SoftwareProxyIn ⟷ Software ⟷ SoftwareProxyOut",
                "unifiedVersionCollection": True,
                "softwareConfigurationHistory": "Removed - flattened to versioned documents"
            }
        }
    }
    
    registry_path = app_config.paths.data_directory / "tenant_registry_time_travel.json"
    with open(registry_path, "w") as f:
        json.dump(tenant_registry, f, indent=2)
    
    print(f"\n🎉 Time travel refactored generation completed!")
    print(f"📊 Generated {total_documents} documents across {len(tenant_configs)} tenants")
    print(f"📁 Registry: {registry_path}")
    print(f"🔄 Time Travel: Consistent pattern across Device and Software")
    print(f"📝 Software: Removed configurationHistory array, now uses version edges")
    
    return results


if __name__ == "__main__":
    results = generate_time_travel_refactored_demo()
    print(f"\n✅ Ready for time travel refactored deployment!")
