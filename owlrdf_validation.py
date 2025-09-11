"""
W3C OWL Naming Convention Validation

Comprehensive validation of W3C OWL compliance including:
- Collection naming (PascalCase for vertices, camelCase for edges)
- Property naming (camelCase with singular/plural rules)
- Relationship modeling
- Semantic correctness
"""

import json
from pathlib import Path
from datetime import datetime

from oasis_cluster_setup import OasisClusterManager


class OWLRDFValidator:
    """Comprehensive W3C OWL naming convention validator."""
    
    def __init__(self, manager: OasisClusterManager):
        self.manager = manager
        self.validation_results = {
            "collection_naming": False,
            "property_naming": False,
            "relationship_modeling": False,
            "semantic_correctness": False,
            "tenant_isolation": False
        }
    
    def validate_collection_naming(self) -> bool:
        """Validate W3C OWL collection naming conventions."""
        print("🏛️  Validating W3C OWL Collection Naming...")
        
        try:
            collections = self.manager.database.collections()
            
            # Expected W3C OWL collection names
            expected_vertex_collections = {
                "Device": "Entity representing network devices",
                "DeviceIn": "Proxy entity for device inputs",
                "DeviceOut": "Proxy entity for device outputs", 
                "Location": "Entity representing physical locations",
                "Software": "Entity representing software instances"
            }
            
            expected_edge_collections = {
                "hasConnection": "Predicate linking devices via network connections",
                "hasLocation": "Predicate linking devices to their physical locations",
                "hasSoftware": "Predicate linking devices to installed software",
                "version": "Predicate linking device proxies to configuration versions"
            }
            
            # Validate vertex collections (PascalCase, singular)
            print("   Vertex Collections (Entities - PascalCase, singular):")
            vertex_valid = True
            for collection in collections:
                if collection['name'] in expected_vertex_collections and collection['type'] == 2:
                    name = collection['name']
                    is_pascal = name[0].isupper() and name.replace('_', '').isalnum()
                    is_singular = not name.endswith('s') or name in ['DeviceIn', 'DeviceOut']  # Handle special cases
                    
                    status = "✅" if is_pascal and is_singular else "❌"
                    description = expected_vertex_collections[name]
                    print(f"     {name}: {status} {description}")
                    
                    if not (is_pascal and is_singular):
                        vertex_valid = False
            
            # Validate edge collections (camelCase, singular) 
            print("   Edge Collections (Predicates - camelCase, singular):")
            edge_valid = True
            for collection in collections:
                if collection['name'] in expected_edge_collections and collection['type'] == 3:
                    name = collection['name']
                    is_camel = name[0].islower() and name.replace('_', '').isalnum()
                    is_singular = not name.endswith('s')
                    
                    status = "✅" if is_camel and is_singular else "❌"
                    description = expected_edge_collections[name]
                    print(f"     {name}: {status} {description}")
                    
                    if not (is_camel and is_singular):
                        edge_valid = False
            
            overall_valid = vertex_valid and edge_valid
            print(f"   {'✅' if overall_valid else '❌'} Collection naming validation: {'PASS' if overall_valid else 'FAIL'}")
            
            self.validation_results["collection_naming"] = overall_valid
            return overall_valid
            
        except Exception as e:
            print(f"   ❌ Collection naming validation error: {e}")
            return False
    
    def validate_property_naming(self, tenant_configs) -> bool:
        """Validate W3C OWL property naming conventions."""
        print("\n🏷️  Validating W3C OWL Property Naming...")
        
        try:
            # Test with first tenant
            tenant_config = tenant_configs[0]
            tenant_attr = f"tenant_{tenant_config.tenant_id}_attr"
            
            # W3C OWL property naming rules
            expected_properties = {
                # Device entity properties (camelCase, singular for values)
                "deviceName": {"type": "string", "rule": "camelCase, singular"},
                "deviceType": {"type": "string", "rule": "camelCase, singular"},
                "deviceModel": {"type": "string", "rule": "camelCase, singular"}, 
                "serialNumber": {"type": "string", "rule": "camelCase, singular"},
                "ipAddress": {"type": "string", "rule": "camelCase, singular"},
                "macAddress": {"type": "string", "rule": "camelCase, singular"},
                "operatingSystem": {"type": "string", "rule": "camelCase, singular"},
                "osVersion": {"type": "string", "rule": "camelCase, singular"},
                "hostName": {"type": "string", "rule": "camelCase, singular"},
                # Array properties (camelCase, plural)
                "firewallRules": {"type": "array", "rule": "camelCase, plural for array"},
                # Connection edge properties
                "connectionType": {"type": "string", "rule": "camelCase, singular"},
                "bandwidthCapacity": {"type": "string", "rule": "camelCase, singular"},
                "networkLatency": {"type": "string", "rule": "camelCase, singular"},
                # Location properties
                "locationName": {"type": "string", "rule": "camelCase, singular"},
                "streetAddress": {"type": "string", "rule": "camelCase, singular"},
                "geoLocation": {"type": "object", "rule": "camelCase, singular for sub-document"},
                # Software properties  
                "softwareName": {"type": "string", "rule": "camelCase, singular"},
                "softwareType": {"type": "string", "rule": "camelCase, singular"},
                "softwareVersion": {"type": "string", "rule": "camelCase, singular"},
                "configurationHistory": {"type": "array", "rule": "camelCase, plural for array"}
            }
            
            # Check Device properties
            device_query = f"""
            FOR doc IN Device
            FILTER doc.`{tenant_attr}` == @tenant_id
            LIMIT 1
            RETURN doc
            """
            
            cursor = self.manager.database.aql.execute(device_query, bind_vars={"tenant_id": tenant_config.tenant_id})
            devices = list(cursor)
            
            property_validation = True
            
            if devices:
                device = devices[0]
                print("   Device Entity Properties:")
                
                device_props = ["deviceName", "deviceType", "deviceModel", "serialNumber", 
                              "ipAddress", "macAddress", "operatingSystem", "osVersion", "hostName", "firewallRules"]
                
                for prop in device_props:
                    if prop in device:
                        expected = expected_properties.get(prop, {})
                        is_camel = prop[0].islower() and prop[0].isalpha()
                        
                        # Check plural rule for arrays (special exceptions for compound words)
                        is_array = isinstance(device[prop], list)
                        # Special handling for compound camelCase words ending in non-s
                        exceptions = ['ipAddress', 'macAddress', 'osVersion', 'hostName']
                        if prop in exceptions:
                            proper_plural = not is_array  # These should be singular
                        else:
                            proper_plural = (is_array and prop.endswith('s')) or (not is_array and not prop.endswith('s'))
                        
                        status = "✅" if is_camel and proper_plural else "❌"
                        rule = expected.get("rule", "unknown")
                        print(f"     {prop}: {status} {rule}")
                        
                        if not (is_camel and proper_plural):
                            property_validation = False
                    else:
                        print(f"     {prop}: ⚠️  Missing property")
            
            # Check Connection edge properties
            connection_query = f"""
            FOR doc IN hasConnection
            FILTER doc.`{tenant_attr}` == @tenant_id
            LIMIT 1
            RETURN doc
            """
            
            cursor = self.manager.database.aql.execute(connection_query, bind_vars={"tenant_id": tenant_config.tenant_id})
            connections = list(cursor)
            
            if connections:
                connection = connections[0]
                print("   Connection Edge Properties:")
                
                conn_props = ["connectionType", "bandwidthCapacity", "networkLatency"]
                
                for prop in conn_props:
                    if prop in connection:
                        expected = expected_properties.get(prop, {})
                        is_camel = prop[0].islower() and prop[0].isalpha()
                        
                        status = "✅" if is_camel else "❌"
                        rule = expected.get("rule", "unknown")
                        print(f"     {prop}: {status} {rule}")
                        
                        if not is_camel:
                            property_validation = False
            
            # Check Location properties
            location_query = f"""
            FOR doc IN Location
            FILTER doc.`{tenant_attr}` == @tenant_id
            LIMIT 1
            RETURN doc
            """
            
            cursor = self.manager.database.aql.execute(location_query, bind_vars={"tenant_id": tenant_config.tenant_id})
            locations = list(cursor)
            
            if locations:
                location = locations[0]
                print("   Location Entity Properties:")
                
                loc_props = ["locationName", "streetAddress", "geoLocation"]
                
                for prop in loc_props:
                    if prop in location:
                        expected = expected_properties.get(prop, {})
                        is_camel = prop[0].islower() and prop[0].isalpha()
                        
                        status = "✅" if is_camel else "❌"
                        rule = expected.get("rule", "unknown")
                        print(f"     {prop}: {status} {rule}")
                        
                        if not is_camel:
                            property_validation = False
            
            print(f"   {'✅' if property_validation else '❌'} Property naming validation: {'PASS' if property_validation else 'FAIL'}")
            
            self.validation_results["property_naming"] = property_validation
            return property_validation
            
        except Exception as e:
            print(f"   ❌ Property naming validation error: {e}")
            return False
    
    def validate_relationship_modeling(self, tenant_configs) -> bool:
        """Validate W3C OWL relationship modeling."""
        print("\n🔗 Validating W3C OWL Relationship Modeling...")
        
        try:
            tenant_config = tenant_configs[0]
            tenant_attr = f"tenant_{tenant_config.tenant_id}_attr"
            
            # Validate edge structure (subject-predicate-object)
            relationship_checks = [
                {
                    "edge": "hasConnection",
                    "from_type": "DeviceOut", 
                    "to_type": "DeviceIn",
                    "description": "DeviceOut --hasConnection--> DeviceIn"
                },
                {
                    "edge": "hasLocation",
                    "from_type": "DeviceOut",
                    "to_type": "Location", 
                    "description": "DeviceOut --hasLocation--> Location"
                },
                {
                    "edge": "hasSoftware", 
                    "from_type": "DeviceOut",
                    "to_type": "Software",
                    "description": "DeviceOut --hasSoftware--> Software"
                },
                {
                    "edge": "version",
                    "from_type": "DeviceIn",
                    "to_type": "Device",
                    "description": "DeviceIn --version--> Device"
                }
            ]
            
            relationship_valid = True
            
            print("   RDF Triple Validation (Subject-Predicate-Object):")
            for check in relationship_checks:
                edge_query = f"""
                FOR edge IN {check['edge']}
                FILTER edge.`{tenant_attr}` == @tenant_id
                FILTER edge._fromType == @from_type AND edge._toType == @to_type
                LIMIT 1
                RETURN edge
                """
                
                cursor = self.manager.database.aql.execute(
                    edge_query,
                    bind_vars={
                        "tenant_id": tenant_config.tenant_id,
                        "from_type": check["from_type"],
                        "to_type": check["to_type"]
                    }
                )
                
                edges = list(cursor)
                status = "✅" if edges else "❌"
                print(f"     {check['description']}: {status}")
                
                if not edges:
                    relationship_valid = False
            
            print(f"   {'✅' if relationship_valid else '❌'} Relationship modeling validation: {'PASS' if relationship_valid else 'FAIL'}")
            
            self.validation_results["relationship_modeling"] = relationship_valid
            return relationship_valid
            
        except Exception as e:
            print(f"   ❌ Relationship modeling validation error: {e}")
            return False
    
    def validate_semantic_correctness(self, tenant_configs) -> bool:
        """Validate semantic correctness of W3C OWL model."""
        print("\n🧠 Validating Semantic Correctness...")
        
        try:
            tenant_config = tenant_configs[0]
            tenant_attr = f"tenant_{tenant_config.tenant_id}_attr"
            
            semantic_checks = []
            
            # Check domain-specific semantics
            # 1. Devices should have proper types
            device_type_query = f"""
            FOR device IN Device
            FILTER device.`{tenant_attr}` == @tenant_id
            FILTER device.deviceType NOT IN ["laptop", "desktop", "server", "router", "switch", "firewall", "IoT"]
            RETURN device.deviceType
            """
            
            cursor = self.manager.database.aql.execute(device_type_query, bind_vars={"tenant_id": tenant_config.tenant_id})
            invalid_types = list(cursor)
            
            device_types_valid = len(invalid_types) == 0
            semantic_checks.append(("Device types are from valid domain", device_types_valid))
            
            # 2. IP addresses should be valid format
            ip_format_query = f"""
            FOR device IN Device
            FILTER device.`{tenant_attr}` == @tenant_id
            FILTER NOT REGEX_TEST(device.ipAddress, "^\\\\d{{1,3}}\\\\.\\\\d{{1,3}}\\\\.\\\\d{{1,3}}\\\\.\\\\d{{1,3}}$")
            RETURN device.ipAddress
            """
            
            cursor = self.manager.database.aql.execute(ip_format_query, bind_vars={"tenant_id": tenant_config.tenant_id})
            invalid_ips = list(cursor)
            
            ip_format_valid = len(invalid_ips) == 0
            semantic_checks.append(("IP addresses follow valid format", ip_format_valid))
            
            # 3. GeoJSON locations should be properly structured
            geo_query = f"""
            FOR location IN Location
            FILTER location.`{tenant_attr}` == @tenant_id
            FILTER location.geoLocation.type != "Point" OR LENGTH(location.geoLocation.coordinates) != 2
            RETURN location.locationName
            """
            
            cursor = self.manager.database.aql.execute(geo_query, bind_vars={"tenant_id": tenant_config.tenant_id})
            invalid_geo = list(cursor)
            
            geo_valid = len(invalid_geo) == 0
            semantic_checks.append(("GeoJSON coordinates are properly structured", geo_valid))
            
            # 4. Edge endpoints should exist
            orphan_query = f"""
            FOR edge IN hasConnection
            FILTER edge.`{tenant_attr}` == @tenant_id
            LET from_exists = DOCUMENT(edge._from)
            LET to_exists = DOCUMENT(edge._to)
            FILTER from_exists == null OR to_exists == null
            RETURN edge._key
            """
            
            cursor = self.manager.database.aql.execute(orphan_query, bind_vars={"tenant_id": tenant_config.tenant_id})
            orphan_edges = list(cursor)
            
            referential_valid = len(orphan_edges) == 0
            semantic_checks.append(("No orphaned edge references", referential_valid))
            
            # Display results
            print("   Domain Semantics Validation:")
            overall_semantic_valid = True
            for description, is_valid in semantic_checks:
                status = "✅" if is_valid else "❌"
                print(f"     {description}: {status}")
                if not is_valid:
                    overall_semantic_valid = False
            
            print(f"   {'✅' if overall_semantic_valid else '❌'} Semantic correctness validation: {'PASS' if overall_semantic_valid else 'FAIL'}")
            
            self.validation_results["semantic_correctness"] = overall_semantic_valid
            return overall_semantic_valid
            
        except Exception as e:
            print(f"   ❌ Semantic correctness validation error: {e}")
            return False
    
    def generate_owlrdf_report(self, tenant_configs) -> dict:
        """Generate comprehensive W3C OWL validation report."""
        
        passed_validations = sum(1 for result in self.validation_results.values() if result)
        total_validations = len(self.validation_results)
        
        # Collection summary
        collections = self.manager.database.collections()
        vertex_collections = [c['name'] for c in collections if c['type'] == 2 and not c['name'].startswith('_')]
        edge_collections = [c['name'] for c in collections if c['type'] == 3 and not c['name'].startswith('_')]
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "owlrdf_compliance": {
                "overall_status": "COMPLIANT" if passed_validations == total_validations else "NON_COMPLIANT",
                "passed_validations": passed_validations,
                "total_validations": total_validations,
                "success_rate": f"{(passed_validations/total_validations)*100:.1f}%"
            },
            "collection_structure": {
                "vertex_collections": vertex_collections,
                "edge_collections": edge_collections,
                "naming_convention": "W3C OWL (PascalCase vertices, camelCase edges)"
            },
            "detailed_validations": self.validation_results,
            "tenant_summary": {
                "total_tenants": len(tenant_configs),
                "tenant_isolation": self.validation_results.get("tenant_isolation", False)
            },
            "standards_compliance": {
                "w3c_owlrdf": True,
                "entity_naming": "PascalCase, singular",
                "predicate_naming": "camelCase, singular", 
                "property_naming": "camelCase with singular/plural rules",
                "rdf_triple_structure": "Subject-Predicate-Object"
            }
        }
        
        return report


def main():
    """Run comprehensive W3C OWL validation."""
    
    # Connect to cluster
    OASIS_ENDPOINT = "https://1d53cdf6fad0.arangodb.cloud:8529"
    OASIS_USERNAME = "root"
    OASIS_PASSWORD = "GcZO9wNKLq9faIuIUgnY"
    
    print("🦉 Comprehensive W3C OWL Validation")
    print("=" * 60)
    
    manager = OasisClusterManager(OASIS_ENDPOINT, OASIS_USERNAME, OASIS_PASSWORD)
    
    if not manager.connect():
        return False
        
    manager.database = manager.client.db("network_assets_demo", username=OASIS_USERNAME, password=OASIS_PASSWORD)
    
    # Load tenant configurations
    registry_path = Path("data/tenant_registry_owlrdf.json")
    with open(registry_path, 'r') as f:
        registry = json.load(f)
    
    from tenant_config import create_tenant_config
    tenant_configs = []
    for tenant_id, tenant_info in registry["tenants"].items():
        tenant_config = create_tenant_config(
            tenant_info["tenantName"],
            scale_factor=tenant_info["scaleFactor"],
            description=tenant_info["tenantDescription"]
        )
        tenant_config.tenant_id = tenant_id
        tenant_configs.append(tenant_config)
    
    # Run comprehensive W3C OWL validation
    validator = OWLRDFValidator(manager)
    
    all_passed = True
    all_passed &= validator.validate_collection_naming()
    all_passed &= validator.validate_property_naming(tenant_configs)
    all_passed &= validator.validate_relationship_modeling(tenant_configs)
    all_passed &= validator.validate_semantic_correctness(tenant_configs)
    
    # Also validate tenant isolation
    tenant_isolation_valid = manager.validate_tenant_isolation(tenant_configs)
    validator.validation_results["tenant_isolation"] = tenant_isolation_valid
    all_passed &= tenant_isolation_valid
    
    # Generate and save report
    report = validator.generate_owlrdf_report(tenant_configs)
    
    with open("owlrdf_validation_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Display summary
    print(f"\n📋 W3C OWL Validation Summary:")
    print(f"   Status: {report['owlrdf_compliance']['overall_status']}")
    print(f"   Passed: {report['owlrdf_compliance']['passed_validations']}/{report['owlrdf_compliance']['total_validations']}")
    print(f"   Success Rate: {report['owlrdf_compliance']['success_rate']}")
    print(f"   Report saved: owlrdf_validation_report.json")
    
    print(f"\n🏛️  Standards Compliance:")
    print(f"   Entity Collections: {', '.join(report['collection_structure']['vertex_collections'])}")
    print(f"   Predicate Collections: {', '.join(report['collection_structure']['edge_collections'])}")
    print(f"   Naming Convention: {report['collection_structure']['naming_convention']}")
    
    if all_passed:
        print(f"\n🎉 All W3C OWL validations passed! Deployment is fully standards-compliant.")
        return True
    else:
        print(f"\n❌ Some W3C OWL validations failed. Check the detailed report.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
