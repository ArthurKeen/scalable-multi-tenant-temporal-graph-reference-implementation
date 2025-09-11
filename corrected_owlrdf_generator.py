"""
Corrected W3C OWL Multi-Tenant Generator

Implements all requested corrections:
1. DeviceIn → DeviceProxyIn, DeviceOut → DeviceProxyOut  
2. Remove temporal attributes from proxy collections
3. Rename _observed_at → observedAt in all collections
4. Update _fromType and _toType to use new collection names
"""

import json
import datetime
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


class CorrectedTenantDataGenerator:
    """Corrected W3C OWL compliant tenant data generator."""
    
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
    
    def generate_locations(self) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant location data."""
        self.logger.info(f"Generating {self.tenant_config.num_locations} locations for tenant {self.tenant_config.tenant_name}")
        
        locations = []
        
        for i in range(self.tenant_config.num_locations):
            loc_data = self.location_provider.get_location_data(i)
            
            # W3C OWL compliant property names (camelCase)
            location = {
                "_key": KeyGenerator.generate_tenant_key(
                    self.tenant_config.tenant_id, "location", i + 1
                ),
                "locationName": f"{self.tenant_config.tenant_name} - {loc_data['name']}",
                "streetAddress": loc_data["address"],
                "geoLocation": {
                    "type": "Point",
                    "coordinates": [loc_data["lon"], loc_data["lat"]]
                }
            }
            
            # Add temporal attributes and tenant key (observedAt instead of _observed_at)
            location = DocumentEnhancer.add_tenant_attributes(location, self.tenant_config)
            locations.append(location)
        
        self.logger.info(f"Generated {len(locations)} location entities")
        return locations
    
    def generate_device_proxies(self) -> Tuple[List[Dict], List[Dict]]:
        """Generate corrected DeviceProxyIn and DeviceProxyOut collections (no temporal attributes)."""
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
                "deviceName": f"{self.tenant_config.tenant_name} {device_type.value} {model} proxy in",
                "deviceType": device_type.value
            }
            device_proxy_in = DocumentEnhancer.add_tenant_attributes(device_proxy_in, self.tenant_config, is_proxy=True)
            device_proxy_ins.append(device_proxy_in)
            
            # DeviceProxyOut - no temporal attributes, only tenant key  
            device_proxy_out = {
                "_key": proxy_key,
                "deviceName": f"{self.tenant_config.tenant_name} {device_type.value} {model} proxy out",
                "deviceType": device_type.value
            }
            device_proxy_out = DocumentEnhancer.add_tenant_attributes(device_proxy_out, self.tenant_config, is_proxy=True)
            device_proxy_outs.append(device_proxy_out)
        
        self.logger.info(f"Generated {len(device_proxy_ins)} DeviceProxyIn and {len(device_proxy_outs)} DeviceProxyOut entities")
        return device_proxy_ins, device_proxy_outs
    
    def generate_device_configurations(self, device_proxy_ins: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Generate W3C OWL compliant device configurations with corrected temporal naming."""
        self.logger.info(f"Generating device configurations with {self.tenant_config.num_config_changes} historical versions")
        
        devices = []
        versions = []
        
        for i, device_proxy_in in enumerate(device_proxy_ins):
            device_type_str = device_proxy_in["deviceType"]
            from data_generation_config import DeviceType
            device_type = DeviceType(device_type_str)
            
            os_version = self.random_gen.select_os_version(device_type)
            model = self.random_gen.generate_model_name(device_type)
            proxy_key = device_proxy_in["_key"]
            
            # Generate current configuration with W3C OWL property names
            current_device_key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "device", i + 1, 0
            )
            current_created = datetime.datetime.now()
            
            current_config = {
                "_key": current_device_key,
                "deviceName": f"{self.tenant_config.tenant_name} {device_type.value} {model}",
                "deviceType": device_type.value,
                "deviceModel": model,
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
            
            # Create version edges for current configuration with corrected collection names
            current_versions = self._create_version_edges(
                proxy_key, current_device_key, current_created
            )
            versions.extend(current_versions)
            
            # Generate historical configurations
            historical_devices, historical_versions = self._generate_historical_configurations(
                current_config, proxy_key, i + 1
            )
            devices.extend(historical_devices)
            versions.extend(historical_versions)
        
        self.logger.info(f"Generated {len(devices)} device configurations and {len(versions)} version edges")
        return devices, versions
    
    def _create_version_edges(self, proxy_key: str, device_key: str, 
                            timestamp: datetime.datetime) -> List[Dict[str, Any]]:
        """Create version edges with corrected collection names and types."""
        version_in = DocumentEnhancer.create_edge_document(
            key=KeyGenerator.generate_version_key("in", device_key),
            from_collection=self.app_config.get_collection_name("device_ins"),  # DeviceProxyIn
            from_key=proxy_key,
            to_collection=self.app_config.get_collection_name("devices"),  # Device
            to_key=device_key,
            from_type="DeviceProxyIn",  # Corrected type name
            to_type="Device",
            tenant_config=self.tenant_config,
            timestamp=timestamp
        )
        
        version_out = DocumentEnhancer.create_edge_document(
            key=KeyGenerator.generate_version_key("out", device_key),
            from_collection=self.app_config.get_collection_name("devices"),  # Device
            from_key=device_key,
            to_collection=self.app_config.get_collection_name("device_outs"),  # DeviceProxyOut
            to_key=proxy_key,
            from_type="Device",
            to_type="DeviceProxyOut",  # Corrected type name
            tenant_config=self.tenant_config,
            timestamp=timestamp
        )
        
        return [version_in, version_out]
    
    def _generate_historical_configurations(self, current_config: Dict[str, Any], 
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
            expired = previous_config["created"]
            
            previous_config = DocumentEnhancer.add_tenant_attributes(
                previous_config, self.tenant_config, created, expired
            )
            historical_devices.append(previous_config)
            
            # Create version edges for historical configuration
            historical_version_edges = self._create_version_edges(proxy_key, key, created)
            for edge in historical_version_edges:
                edge["expired"] = expired
            historical_versions.extend(historical_version_edges)
            
            current_config = previous_config
        
        return historical_devices, historical_versions
    
    def generate_software(self) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant software data with corrected temporal naming."""
        self.logger.info(f"Generating {self.tenant_config.num_software} software entities")
        
        software = []
        
        for i in range(self.tenant_config.num_software):
            software_type = self.random_gen.select_software_type()
            software_version = self.random_gen.select_software_version(software_type)
            
            # W3C OWL compliant property names
            soft = {
                "_key": KeyGenerator.generate_tenant_key(
                    self.tenant_config.tenant_id, "software", i + 1
                ),
                "softwareName": f"{self.tenant_config.tenant_name} {software_version.split(' ')[0]}",
                "softwareType": software_type.value,
                "softwareVersion": software_version,
                "configurationHistory": []
            }
            
            # Generate software configuration history
            current_config = {
                "portNumber": self.random_gen.generate_software_port(),
                "isEnabled": True
            }
            current_config = DocumentEnhancer.add_tenant_attributes(
                current_config, self.tenant_config
            )
            soft["configurationHistory"].append(current_config)
            
            # Generate historical software configurations
            for change_no in range(self.tenant_config.num_config_changes):
                created = datetime.datetime.now() - datetime.timedelta(
                    days=__import__('random').randint(change_no*5+1, (change_no+1)*5)
                )
                previous_config = self.config_manager.apply_software_configuration_change(current_config)
                
                # Ensure W3C OWL compliant property names
                if "port" in previous_config:
                    previous_config["portNumber"] = previous_config.pop("port")
                if "enabled" in previous_config:
                    previous_config["isEnabled"] = previous_config.pop("enabled")
                
                expired = previous_config["created"]
                
                previous_config = DocumentEnhancer.add_tenant_attributes(
                    previous_config, self.tenant_config, created, expired
                )
                soft["configurationHistory"].append(previous_config)
                current_config = previous_config
            
            # Add temporal attributes to software document (observedAt instead of _observed_at)
            soft = DocumentEnhancer.add_tenant_attributes(soft, self.tenant_config)
            software.append(soft)
        
        self.logger.info(f"Generated {len(software)} software entities")
        return software
    
    def generate_connections(self, device_proxy_ins: List[Dict], device_proxy_outs: List[Dict]) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant connection edges with corrected types."""
        self.logger.info(f"Generating {self.tenant_config.num_connections} hasConnection edges")
        
        connections = []
        attempts = 0
        
        while len(connections) < self.tenant_config.num_connections and attempts < self.limits.MAX_GENERATION_RETRIES:
            from_device = self.random_gen.select_random_item(device_proxy_outs)
            to_device = self.random_gen.select_random_item(device_proxy_ins)
            
            if from_device["_key"] != to_device["_key"]:  # Prevent self loops
                connection_key = KeyGenerator.generate_connection_key(
                    self.tenant_config.tenant_id, len(connections) + 1
                )
                
                # W3C OWL compliant property names
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
                    from_type="DeviceProxyOut",  # Corrected type name
                    to_type="DeviceProxyIn",  # Corrected type name
                    tenant_config=self.tenant_config,
                    extra_attributes=connection_attrs
                )
                
                connections.append(connection)
            
            attempts += 1
        
        self.logger.info(f"Generated {len(connections)} hasConnection edges")
        return connections
    
    def generate_has_location_edges(self, device_proxy_outs: List[Dict], locations: List[Dict]) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant hasLocation edges with corrected types."""
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
                from_type="DeviceProxyOut",  # Corrected type name
                to_type="Location",
                tenant_config=self.tenant_config
            )
            
            has_locations.append(has_location)
        
        self.logger.info(f"Generated {len(has_locations)} hasLocation edges")
        return has_locations
    
    def generate_has_software_edges(self, device_proxy_outs: List[Dict], software: List[Dict]) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant hasSoftware edges with corrected types."""
        self.logger.info(f"Generating {self.tenant_config.num_has_software} hasSoftware edges")
        
        has_software = []
        attempts = 0
        
        while len(has_software) < self.tenant_config.num_has_software and attempts < self.limits.MAX_GENERATION_RETRIES:
            device = self.random_gen.select_random_item(device_proxy_outs)
            
            # Routers don't typically run additional software
            if device["deviceType"] != "router":
                software_item = self.random_gen.select_random_item(software)
                key = KeyGenerator.generate_has_software_key(
                    self.tenant_config.tenant_id, len(has_software) + 1
                )
                
                has_software_edge = DocumentEnhancer.create_edge_document(
                    key=key,
                    from_collection=self.app_config.get_collection_name("device_outs"),  # DeviceProxyOut
                    from_key=device["_key"],
                    to_collection=self.app_config.get_collection_name("software"),  # Software
                    to_key=software_item["_key"],
                    from_type="DeviceProxyOut",  # Corrected type name
                    to_type="Software",
                    tenant_config=self.tenant_config
                )
                
                has_software.append(has_software_edge)
            
            attempts += 1
        
        self.logger.info(f"Generated {len(has_software)} hasSoftware edges")
        return has_software
    
    def generate_all_data(self) -> Dict[str, Any]:
        """Generate complete corrected W3C OWL compliant network asset data."""
        self.logger.info(f"Starting corrected data generation for tenant: {self.tenant_config.tenant_name} (Scale: {self.tenant_config.scale_factor}x)")
        
        # Generate all data collections
        locations = self.generate_locations()
        device_proxy_ins, device_proxy_outs = self.generate_device_proxies()
        devices, versions = self.generate_device_configurations(device_proxy_ins)
        software = self.generate_software()
        connections = self.generate_connections(device_proxy_ins, device_proxy_outs)
        has_locations = self.generate_has_location_edges(device_proxy_outs, locations)
        has_software = self.generate_has_software_edges(device_proxy_outs, software)
        
        # Organize data collections using centralized configuration
        data_collections = {
            "devices": devices,
            "device_ins": device_proxy_ins,  # Will be saved as DeviceProxyIn.json
            "device_outs": device_proxy_outs,  # Will be saved as DeviceProxyOut.json
            "locations": locations,
            "software": software,
            "connections": connections,
            "has_locations": has_locations,
            "has_software": has_software,
            "versions": versions
        }
        
        # Write data files using centralized file management
        FileManager.write_tenant_data_files(self.tenant_config, data_collections)
        
        # Generate and write SmartGraph configuration
        smartgraph_config = SmartGraphConfigGenerator.generate_config(self.tenant_config)
        tenant_data_path = self.app_config.paths.get_tenant_data_path(self.tenant_config.tenant_id)
        config_file = tenant_data_path / self.app_config.get_file_name("smartgraph_config")
        FileManager.write_json_file(config_file, smartgraph_config)
        
        total_documents = sum(len(data) for data in data_collections.values())
        self.logger.info(f"Completed corrected data generation: {total_documents} total documents")
        
        print(f"✅ Generated {total_documents} corrected W3C OWL compliant documents")
        print(f"   Device entities: {len(devices)} devices, {len(device_proxy_ins)} DeviceProxyIn, {len(device_proxy_outs)} DeviceProxyOut")
        print(f"   Location entities: {len(locations)} locations")
        print(f"   Software entities: {len(software)} software")
        print(f"   Relationship edges: {len(connections)} hasConnection, {len(has_locations)} hasLocation, {len(has_software)} hasSoftware")
        print(f"   Version edges: {len(versions)} version")
        print(f"   🔧 Corrections applied: DeviceProxyIn/Out no temporal data, observedAt property, corrected _fromType/_toType")
        
        return {
            "tenant_config": self.tenant_config,
            "data_counts": {key: len(data) for key, data in data_collections.items()},
            "smartgraph_config": smartgraph_config,
            "data_directory": self.naming.data_directory
        }


def generate_corrected_multi_tenant_demo(environment: str = "production"):
    """Generate corrected W3C OWL compliant multi-tenant demo."""
    
    print("🔧 Corrected W3C OWL Multi-Tenant Generation")
    print("=" * 60)
    print("📋 Corrections applied:")
    print("   • DeviceIn → DeviceProxyIn, DeviceOut → DeviceProxyOut")
    print("   • Removed temporal attributes from proxy collections")
    print("   • Renamed _observed_at → observedAt in all collections")
    print("   • Updated _fromType and _toType to use new collection names")
    print()
    
    app_config = get_config(environment)
    
    # Create tenant configurations
    tenant_configs = [
        create_tenant_config(
            "Acme Corp",
            scale_factor=1,
            description="Small enterprise with standard deployment"
        ),
        create_tenant_config(
            "Global Enterprises", 
            scale_factor=3,
            description="Large enterprise with scaled deployment"
        ),
        create_tenant_config(
            "StartupXYZ",
            scale_factor=1,
            num_devices=8,
            num_locations=2,
            description="Small startup with minimal infrastructure"
        )
    ]
    
    results = {}
    total_documents = 0
    
    # Generate data for each tenant
    for tenant_config in tenant_configs:
        generator = CorrectedTenantDataGenerator(tenant_config, environment)
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
            "owlrdfCompliant": True,
            "corrections": [
                "DeviceIn → DeviceProxyIn",
                "DeviceOut → DeviceProxyOut", 
                "Removed temporal data from proxy collections",
                "_observed_at → observedAt",
                "Updated _fromType/_toType references"
            ]
        }
    }
    
    registry_path = app_config.paths.data_directory / "tenant_registry_corrected.json"
    with open(registry_path, "w") as f:
        json.dump(tenant_registry, f, indent=2)
    
    print(f"\n🎉 Corrected W3C OWL generation completed!")
    print(f"📊 Generated {total_documents} documents across {len(tenant_configs)} tenants")
    print(f"📁 Registry: {registry_path}")
    print(f"🏛️ Standards: W3C OWL naming conventions")
    print(f"🔧 Architecture: All requested corrections applied")
    
    return results


if __name__ == "__main__":
    results = generate_corrected_multi_tenant_demo()
    print(f"\n✅ Ready for corrected W3C OWL compliant deployment!")
