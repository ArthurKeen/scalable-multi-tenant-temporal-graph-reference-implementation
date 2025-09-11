"""
W3C OWL Compliant Multi-Tenant Network Asset Generator

Refactored version using W3C OWL naming conventions:
- Vertex collections: PascalCase, singular (Device, Location, Software)
- Edge collections: camelCase, singular (hasConnection, hasLocation, hasSoftware)  
- Properties: camelCase, singular for values, plural for arrays
"""

import json
import datetime
from typing import Dict, List, Any, Tuple
from pathlib import Path

# Import configuration and utilities
from tenant_config import (
    TenantConfig, 
    TenantNamingConvention,
    create_tenant_config
)
from data_generation_config import (
    DeviceType, SoftwareType, NetworkConfig, DataGenerationLimits,
    COLLECTION_NAMES, FILE_NAMES, DATABASE_CONFIG
)
from data_generation_utils import (
    DocumentEnhancer, RandomDataGenerator, KeyGenerator,
    ConfigurationManager, FileManager, LocationDataProvider,
    SmartGraphConfigGenerator
)


class OWLRDFTenantDataGenerator:
    """W3C OWL compliant tenant data generator."""
    
    def __init__(self, tenant_config: TenantConfig):
        self.tenant_config = tenant_config
        self.naming = TenantNamingConvention(tenant_config.tenant_id)
        self.network_config = NetworkConfig()
        self.limits = DataGenerationLimits()
        self.random_gen = RandomDataGenerator(self.network_config, self.limits)
        self.config_manager = ConfigurationManager(self.random_gen)
        self.location_provider = LocationDataProvider()
        
    def generate_locations(self) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant location data."""
        locations = []
        
        for i in range(self.tenant_config.num_locations):
            loc_data = self.location_provider.get_location_data(i)
            
            # W3C OWL compliant property names (camelCase)
            location = {
                "_key": KeyGenerator.generate_tenant_key(
                    self.tenant_config.tenant_id, "location", i + 1
                ),
                "locationName": f"{self.tenant_config.tenant_name} - {loc_data['name']}",  # camelCase
                "streetAddress": loc_data["address"],  # camelCase
                "geoLocation": {  # camelCase, singular for sub-document
                    "type": "Point",
                    "coordinates": [loc_data["lon"], loc_data["lat"]]
                }
            }
            
            # Add temporal attributes and tenant key
            location = DocumentEnhancer.add_tenant_attributes(location, self.tenant_config)
            locations.append(location)
        
        return locations
    
    def generate_device_proxies(self) -> Tuple[List[Dict], List[Dict]]:
        """Generate W3C OWL compliant device proxy collections."""
        device_ins = []
        device_outs = []
        
        for i in range(self.tenant_config.num_devices):
            device_type = self.random_gen.select_device_type()
            model = self.random_gen.generate_model_name(device_type)
            proxy_key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "device", i + 1
            )
            
            # W3C OWL compliant property names
            device_in = {
                "_key": proxy_key,
                "deviceName": f"{self.tenant_config.tenant_name} {device_type.value} {model} proxy in",  # camelCase
                "deviceType": device_type.value  # camelCase
            }
            device_in = DocumentEnhancer.add_tenant_attributes(device_in, self.tenant_config)
            device_ins.append(device_in)
            
            device_out = {
                "_key": proxy_key,
                "deviceName": f"{self.tenant_config.tenant_name} {device_type.value} {model} proxy out",  # camelCase
                "deviceType": device_type.value  # camelCase
            }
            device_out = DocumentEnhancer.add_tenant_attributes(device_out, self.tenant_config)
            device_outs.append(device_out)
        
        return device_ins, device_outs
    
    def generate_device_configurations(self, device_ins: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Generate W3C OWL compliant device configurations."""
        devices = []
        versions = []
        
        for i, device_in in enumerate(device_ins):
            device_type = DeviceType(device_in["deviceType"])  # Updated property name
            os_version = self.random_gen.select_os_version(device_type)
            model = self.random_gen.generate_model_name(device_type)
            proxy_key = device_in["_key"]
            
            # Generate current configuration with W3C OWL property names
            current_device_key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "device", i + 1, 0
            )
            current_created = datetime.datetime.now()
            
            current_config = {
                "_key": current_device_key,
                "deviceName": f"{self.tenant_config.tenant_name} {device_type.value} {model}",  # camelCase
                "deviceType": device_type.value,  # camelCase
                "deviceModel": model,  # camelCase (was "model")
                "serialNumber": str(__import__('uuid').uuid4()),  # camelCase
                "ipAddress": self.random_gen.generate_ip_address(),  # camelCase
                "macAddress": self.random_gen.generate_mac_address(),  # camelCase
                "operatingSystem": os_version.split(" ")[0],  # camelCase (was "os")
                "osVersion": os_version,  # camelCase
                "hostName": self.random_gen.generate_hostname(self.tenant_config.tenant_id, i + 1),  # camelCase (was "hostname")
                "firewallRules": self.network_config.DEFAULT_FIREWALL_RULES.copy()  # camelCase, plural for array
            }
            current_config = DocumentEnhancer.add_tenant_attributes(
                current_config, self.tenant_config, current_created
            )
            devices.append(current_config)
            
            # Create version edges for current configuration
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
        
        return devices, versions
    
    def _create_version_edges(self, proxy_key: str, device_key: str, 
                            timestamp: datetime.datetime) -> List[Dict[str, Any]]:
        """Create version edges with W3C OWL compliant naming."""
        version_in = DocumentEnhancer.create_edge_document(
            key=KeyGenerator.generate_version_key("in", device_key),
            from_collection=self.naming.device_in_collection,
            from_key=proxy_key,
            to_collection=self.naming.device_collection,
            to_key=device_key,
            from_type="DeviceIn",  # PascalCase for vertex type
            to_type="Device",     # PascalCase for vertex type
            tenant_config=self.tenant_config,
            timestamp=timestamp
        )
        
        version_out = DocumentEnhancer.create_edge_document(
            key=KeyGenerator.generate_version_key("out", device_key),
            from_collection=self.naming.device_collection,
            from_key=device_key,
            to_collection=self.naming.device_out_collection,
            to_key=proxy_key,
            from_type="Device",    # PascalCase for vertex type
            to_type="DeviceOut",   # PascalCase for vertex type
            tenant_config=self.tenant_config,
            timestamp=timestamp
        )
        
        return [version_in, version_out]
    
    def _generate_historical_configurations(self, current_config: Dict[str, Any], 
                                          proxy_key: str, device_index: int) -> Tuple[List[Dict], List[Dict]]:
        """Generate historical device configurations with proper property names."""
        historical_devices = []
        historical_versions = []
        
        for change_no in range(self.tenant_config.num_config_changes):
            # Create historical configuration
            previous_config = self.config_manager.apply_device_configuration_change(current_config)
            key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "device", device_index, change_no + 1
            )
            previous_config["_key"] = key
            
            # Update hostName with proper camelCase (handle both old and new property names)
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
        """Generate W3C OWL compliant software data."""
        software = []
        
        for i in range(self.tenant_config.num_software):
            software_type = self.random_gen.select_software_type()
            software_version = self.random_gen.select_software_version(software_type)
            
            # W3C OWL compliant property names
            soft = {
                "_key": KeyGenerator.generate_tenant_key(
                    self.tenant_config.tenant_id, "software", i + 1
                ),
                "softwareName": f"{self.tenant_config.tenant_name} {software_version.split(' ')[0]}",  # camelCase
                "softwareType": software_type.value,  # camelCase
                "softwareVersion": software_version,  # camelCase
                "configurationHistory": []  # camelCase, plural for array
            }
            
            # Generate software configuration history
            current_config = {
                "portNumber": self.random_gen.generate_software_port(),  # camelCase (was "port")
                "isEnabled": True  # camelCase (was "enabled")
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
                
                # Update property names to W3C OWL compliant
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
            
            # Add temporal attributes to software document
            soft = DocumentEnhancer.add_tenant_attributes(soft, self.tenant_config)
            software.append(soft)
        
        return software
    
    def generate_connections(self, device_ins: List[Dict], device_outs: List[Dict]) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant connection edges."""
        connections = []
        attempts = 0
        
        while len(connections) < self.tenant_config.num_connections and attempts < self.limits.MAX_GENERATION_RETRIES:
            from_device = self.random_gen.select_random_item(device_outs)
            to_device = self.random_gen.select_random_item(device_ins)
            
            if from_device["_key"] != to_device["_key"]:  # Prevent self loops
                connection_key = KeyGenerator.generate_connection_key(
                    self.tenant_config.tenant_id, len(connections) + 1
                )
                
                # W3C OWL compliant property names
                connection_attrs = {
                    "connectionType": self.random_gen.select_connection_type().value,  # camelCase (was "type")
                    "bandwidthCapacity": self.random_gen.generate_bandwidth(),  # camelCase (was "bandwidth")
                    "networkLatency": self.random_gen.generate_latency()  # camelCase (was "latency")
                }
                
                connection = DocumentEnhancer.create_edge_document(
                    key=connection_key,
                    from_collection=self.naming.device_out_collection,
                    from_key=from_device["_key"],
                    to_collection=self.naming.device_in_collection,
                    to_key=to_device["_key"],
                    from_type="DeviceOut",  # PascalCase for vertex type
                    to_type="DeviceIn",     # PascalCase for vertex type
                    tenant_config=self.tenant_config,
                    extra_attributes=connection_attrs
                )
                
                connections.append(connection)
            
            attempts += 1
        
        return connections
    
    def generate_has_location_edges(self, device_outs: List[Dict], locations: List[Dict]) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant hasLocation edges."""
        has_locations = []
        
        for device in device_outs:
            location = self.random_gen.select_random_item(locations)
            key = KeyGenerator.generate_has_location_key(
                self.tenant_config.tenant_id, len(has_locations) + 1
            )
            
            has_location = DocumentEnhancer.create_edge_document(
                key=key,
                from_collection=self.naming.device_out_collection,
                from_key=device["_key"],
                to_collection=self.naming.location_collection,
                to_key=location["_key"],
                from_type="DeviceOut",  # PascalCase for vertex type
                to_type="Location",     # PascalCase for vertex type
                tenant_config=self.tenant_config
            )
            
            has_locations.append(has_location)
        
        return has_locations
    
    def generate_has_software_edges(self, device_outs: List[Dict], software: List[Dict]) -> List[Dict[str, Any]]:
        """Generate W3C OWL compliant hasSoftware edges."""
        has_software = []
        attempts = 0
        
        while len(has_software) < self.tenant_config.num_has_software and attempts < self.limits.MAX_GENERATION_RETRIES:
            device = self.random_gen.select_random_item(device_outs)
            
            # Routers don't typically run additional software
            if device["deviceType"] != DeviceType.ROUTER.value:  # Updated property name
                software_item = self.random_gen.select_random_item(software)
                key = KeyGenerator.generate_has_software_key(
                    self.tenant_config.tenant_id, len(has_software) + 1
                )
                
                has_software_edge = DocumentEnhancer.create_edge_document(
                    key=key,
                    from_collection=self.naming.device_out_collection,
                    from_key=device["_key"],
                    to_collection=self.naming.software_collection,
                    to_key=software_item["_key"],
                    from_type="DeviceOut",  # PascalCase for vertex type
                    to_type="Software",     # PascalCase for vertex type
                    tenant_config=self.tenant_config
                )
                
                has_software.append(has_software_edge)
            
            attempts += 1
        
        return has_software
    
    def generate_all_data(self) -> Dict[str, Any]:
        """Generate complete W3C OWL compliant network asset data."""
        print(f"\nGenerating W3C OWL compliant data for tenant: {self.tenant_config.tenant_name} (ID: {self.tenant_config.tenant_id})")
        print(f"Scale factor: {self.tenant_config.scale_factor}x")
        print(f"Collections: Device, Location, Software, hasConnection, hasLocation, hasSoftware, version")
        
        # Generate all data collections
        locations = self.generate_locations()
        device_ins, device_outs = self.generate_device_proxies()
        devices, versions = self.generate_device_configurations(device_ins)
        software = self.generate_software()
        connections = self.generate_connections(device_ins, device_outs)
        has_locations = self.generate_has_location_edges(device_outs, locations)
        has_software = self.generate_has_software_edges(device_outs, software)
        
        # Organize data collections with new naming
        data_collections = {
            "devices": devices,
            "device_ins": device_ins,
            "device_outs": device_outs,
            "locations": locations,
            "software": software,
            "connections": connections,
            "has_locations": has_locations,
            "has_software": has_software,
            "versions": versions
        }
        
        # Write data files
        FileManager.write_tenant_data_files(self.tenant_config, data_collections)
        
        # Generate and write SmartGraph configuration
        smartgraph_config = SmartGraphConfigGenerator.generate_config(self.tenant_config)
        data_dir = FileManager.ensure_tenant_directory(self.tenant_config)
        config_file = data_dir / FILE_NAMES["smartgraph_config"]
        FileManager.write_json_file(config_file, smartgraph_config)
        
        print(f"✅ Generated {sum(len(data) for data in data_collections.values())} documents")
        print(f"   Device entities: {len(devices)} devices, {len(device_ins)} device_ins, {len(device_outs)} device_outs")
        print(f"   Location entities: {len(locations)} locations")
        print(f"   Software entities: {len(software)} software")
        print(f"   Relationship edges: {len(connections)} hasConnection, {len(has_locations)} hasLocation, {len(has_software)} hasSoftware")
        print(f"   Version edges: {len(versions)} version")
        
        return {
            "tenant_config": self.tenant_config,
            "data_counts": {key: len(data) for key, data in data_collections.items()},
            "smartgraph_config": smartgraph_config,
            "data_directory": self.naming.data_directory
        }


def generate_owlrdf_multi_tenant_demo():
    """Generate W3C OWL compliant multi-tenant demo."""
    
    print("🦉 W3C OWL Compliant Multi-Tenant Generation")
    print("=" * 60)
    
    # Create example tenant configurations
    tenant_a = create_tenant_config(
        "Acme Corp",
        scale_factor=1,
        description="Small enterprise with standard deployment"
    )
    
    tenant_b = create_tenant_config(
        "Global Enterprises", 
        scale_factor=3,  # Reduced for testing
        description="Large enterprise with scaled deployment"
    )
    
    tenant_c = create_tenant_config(
        "StartupXYZ",
        scale_factor=1,
        num_devices=8,
        num_locations=2,
        description="Small startup with minimal infrastructure"
    )
    
    tenant_configs = [tenant_a, tenant_b, tenant_c]
    results = {}
    total_documents = 0
    
    # Generate data for each tenant
    for tenant_config in tenant_configs:
        generator = OWLRDFTenantDataGenerator(tenant_config)
        tenant_result = generator.generate_all_data()
        results[tenant_config.tenant_id] = tenant_result
        total_documents += sum(tenant_result["data_counts"].values())
    
    # Generate tenant registry
    tenant_registry = {
        "tenants": {
            config.tenant_id: {
                "tenantName": config.tenant_name,  # camelCase
                "tenantStatus": config.status.value,  # camelCase
                "databaseName": config.database_name,  # camelCase
                "smartGraphName": f"tenant_{config.tenant_id}_network_assets",  # camelCase
                "smartGraphAttribute": config.smartgraph_attribute,  # camelCase
                "dataDirectory": f"data/tenant_{config.tenant_id}",  # camelCase
                "scaleFactor": config.scale_factor,  # camelCase
                "createdAt": config.created_at.isoformat(),  # camelCase
                "tenantDescription": config.description  # camelCase
            }
            for config in tenant_configs
        },
        "summary": {
            "totalTenants": len(tenant_configs),  # camelCase
            "totalDocuments": total_documents,  # camelCase
            "sharedDatabase": DATABASE_CONFIG["shared_database_name"],  # camelCase
            "generatedAt": datetime.datetime.now().isoformat()  # camelCase
        }
    }
    
    with open("data/tenant_registry_owlrdf.json", "w") as f:
        json.dump(tenant_registry, f, indent=2)
    
    print(f"\n🎉 W3C OWL compliant generation completed!")
    print(f"📊 Generated {total_documents} documents across {len(tenant_configs)} tenants")
    print(f"📁 Registry: data/tenant_registry_owlrdf.json")
    print(f"🏛️  Standards: W3C OWL naming conventions")
    
    return results


if __name__ == "__main__":
    results = generate_owlrdf_multi_tenant_demo()
    print(f"\n✅ Ready for W3C OWL compliant database deployment!")
