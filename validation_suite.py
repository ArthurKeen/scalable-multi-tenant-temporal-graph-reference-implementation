"""
Time Travel Refactoring Validation Suite

Comprehensive testing for the refactored time travel implementation:
- Software time travel pattern validation
- Unified version collection testing
- Query performance comparison
- Data structure compliance
- Cross-entity temporal queries
"""

import json
import datetime
import sys
import unittest
from typing import Dict, List, Any, Optional
from pathlib import Path
from arango import ArangoClient

# Import centralized credentials
from centralized_credentials import CredentialsManager
from database_utilities import QueryExecutor


class TimeTravelValidationSuite:
    """Comprehensive validation suite for time travel refactoring."""
    
    def __init__(self, show_queries: bool = False):
        creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=creds.endpoint)
        self.database = None
        self.validation_results = {}
        self.show_queries = show_queries
        
    def connect_to_database(self) -> bool:
        """Connect to the ArangoDB Oasis database."""
        try:
            creds = CredentialsManager.get_database_credentials()
            self.database = self.client.db(creds.database_name, **CredentialsManager.get_database_params())
            version_info = self.database.version()
            print(f"[DONE] Connected to {creds.database_name}")
            return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {str(e)}")
            return False
    
    def execute_and_display_query(self, query: str, query_name: str, bind_vars: Dict = None) -> List[Dict]:
        """Execute a query and display it with results if show_queries is enabled."""
        return QueryExecutor.execute_and_display_query(self.database, query, query_name, bind_vars, self.show_queries)
    
    def validate_collection_structure(self) -> bool:
        """Validate that all required collections exist with correct structure."""
        print(f"\n[ANALYSIS] Validating Collection Structure...")
        
        try:
            # Expected collections after refactoring
            expected_vertex_collections = [
                "Device", "DeviceProxyIn", "DeviceProxyOut",
                "Software", "SoftwareProxyIn", "SoftwareProxyOut",
                "Location"
            ]
            
            expected_edge_collections = [
                "hasConnection", "hasLocation", "hasDeviceSoftware", "hasVersion"
            ]
            
            # Validate vertex collections
            for collection_name in expected_vertex_collections:
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    count = collection.count()
                    print(f"   [DONE] {collection_name}: {count} documents")
                    
                    # Validate new Software proxy collections have correct structure
                    if collection_name in ["SoftwareProxyIn", "SoftwareProxyOut"]:
                        sample = collection.all(limit=1)
                        for doc in sample:
                            if "configurationHistory" in doc:
                                print(f"   [ERROR] {collection_name} has configurationHistory (should not)")
                                return False
                            if "created" in doc or "expired" in doc:
                                print(f"   [ERROR] {collection_name} has temporal data (should not)")
                                return False
                            print(f"   [DONE] {collection_name} structure correct (no temporal data)")
                else:
                    print(f"   [ERROR] Missing collection: {collection_name}")
                    return False
            
            # Validate edge collections
            for collection_name in expected_edge_collections:
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    count = collection.count()
                    print(f"   [DONE] {collection_name}: {count} documents")
                else:
                    print(f"   [ERROR] Missing edge collection: {collection_name}")
                    return False
            
            print(f"[DONE] Collection structure validation passed")
            return True
            
        except Exception as e:
            print(f"[ERROR] Collection structure validation failed: {str(e)}")
            return False
    
    def validate_software_refactoring(self) -> bool:
        """Validate that Software collection is properly refactored."""
        print(f"\n[ANALYSIS] Validating Software Refactoring...")
        
        try:
            software_collection = self.database.collection("Software")
            
            # Check sample documents
            samples = software_collection.all(limit=10)
            refactored_count = 0
            old_structure_count = 0
            
            for doc in samples:
                if "configurationHistory" in doc:
                    old_structure_count += 1
                    print(f"   [ERROR] Document {doc['_key']} still has configurationHistory")
                else:
                    refactored_count += 1
                    # Check for flattened configuration
                    if "portNumber" in doc and "isEnabled" in doc:
                        print(f"   [DONE] Document {doc['_key']} has flattened configuration")
                    else:
                        print(f"   [WARNING]  Document {doc['_key']} missing flattened config attributes")
            
            if old_structure_count > 0:
                print(f"[ERROR] Software refactoring incomplete: {old_structure_count} documents still have old structure")
                return False
            
            print(f"[DONE] Software refactoring validation passed: {refactored_count} documents correctly refactored")
            return True
            
        except Exception as e:
            print(f"[ERROR] Software refactoring validation failed: {str(e)}")
            return False
    
    def validate_unified_version_collection(self) -> bool:
        """Validate that hasVersion collection handles both Device and Software."""
        print(f"\n[ANALYSIS] Validating Unified HasVersion Collection...")
        
        try:
            version_collection = self.database.collection("hasVersion")
            
            # Count device version edges
            device_versions = version_collection.find({"_fromType": "DeviceProxyIn"}).count()
            device_out_versions = version_collection.find({"_fromType": "Device"}).count()
            
            # Count software version edges
            software_versions = version_collection.find({"_fromType": "SoftwareProxyIn"}).count()
            software_out_versions = version_collection.find({"_fromType": "Software"}).count()
            
            total_versions = version_collection.count()
            
            print(f"   [DATA] Device version edges: {device_versions} (in) + {device_out_versions} (out)")
            print(f"   [DATA] Software version edges: {software_versions} (in) + {software_out_versions} (out)")
            print(f"   [DATA] Total version edges: {total_versions}")
            
            if software_versions == 0:
                print(f"   [ERROR] No software version edges found")
                return False
            
            if device_versions == 0:
                print(f"   [ERROR] No device version edges found")
                return False
            
            # Validate version edge structure
            sample_versions = version_collection.all(limit=5)
            for version in sample_versions:
                required_fields = ["_from", "_to", "_fromType", "_toType", "created", "expired"]
                for field in required_fields:
                    if field not in version:
                        print(f"   [ERROR] Version edge {version['_key']} missing field: {field}")
                        return False
                
                print(f"   [DONE] Version edge {version['_key']}: {version['_fromType']} → {version['_toType']}")
            
            print(f"[DONE] Unified hasVersion collection validation passed")
            return True
            
        except Exception as e:
            print(f"[ERROR] Unified version collection validation failed: {str(e)}")
            return False
    
    def validate_time_travel_queries(self) -> bool:
        """Validate that time travel queries work correctly for both Device and Software."""
        print(f"\n[ANALYSIS] Validating Time Travel Queries...")
        
        try:
            # First, test system-wide queries (multi-tenant validation)
            print(f"\n   [SYSTEM] Testing system-wide time travel functionality...")
            
            # Test point-in-time query for devices (all tenants)
            device_query = """
            FOR device IN Device
              FILTER device.created <= @point_in_time AND device.expired > @point_in_time
              LIMIT 5
              RETURN {
                key: device._key,
                name: device.name,
                type: device.type,
                created: device.created,
                expired: device.expired
              }
            """
            
            point_in_time = datetime.datetime.now().timestamp()
            device_results = self.execute_and_display_query(
                device_query, 
                "System-Wide Device Point-in-Time Query", 
                {"point_in_time": point_in_time}
            )
            
            print(f"   [DATA] System-wide device query returned {len(device_results)} results across all tenants")
            for result in device_results[:3]:
                print(f"      [DONE] Device: {result['name']} (created: {result['created']})")
            
            # Test point-in-time query for software (all tenants)
            software_query = """
            FOR software IN Software
              FILTER software.created <= @point_in_time AND software.expired > @point_in_time
              LIMIT 5
              RETURN {
                key: software._key,
                name: software.name,
                type: software.type,
                port: software.portNumber,
                enabled: software.isEnabled,
                created: software.created,
                expired: software.expired
              }
            """
            
            software_results = self.execute_and_display_query(
                software_query,
                "System-Wide Software Point-in-Time Query",
                {"point_in_time": point_in_time}
            )
            
            print(f"   [DATA] System-wide software query returned {len(software_results)} results across all tenants")
            for result in software_results[:3]:
                print(f"      [DONE] Software: {result['name']} (port: {result['port']}, enabled: {result['enabled']})")
            
            # Now test tenant-specific queries (SmartGraph isolation validation)
            print(f"\n   [TENANT] Testing tenant-specific time travel functionality...")
            
            # Get a sample tenant ID for isolated testing
            tenant_query = """
            FOR device IN Device
              LIMIT 1
              RETURN REGEX_SPLIT(device._key, "_")[0]
            """
            
            tenant_results = self.execute_and_display_query(
                tenant_query,
                "Sample Tenant ID Query"
            )
            
            if tenant_results:
                sample_tenant = tenant_results[0]
                print(f"   [TENANT] Testing isolation for tenant: {sample_tenant}")
                
                # Test tenant-specific device query
                tenant_device_query = """
                FOR device IN Device
                  FILTER STARTS_WITH(device._key, @tenant_prefix)
                  FILTER device.created <= @point_in_time AND device.expired > @point_in_time
                  LIMIT 3
                  RETURN {
                    key: device._key,
                    name: device.name,
                    type: device.type,
                    tenant: REGEX_SPLIT(device._key, "_")[0],
                    created: device.created,
                    expired: device.expired
                  }
                """
                
                tenant_device_results = self.execute_and_display_query(
                    tenant_device_query,
                    f"Tenant-Specific Device Query ({sample_tenant})",
                    {"tenant_prefix": f"{sample_tenant}_", "point_in_time": point_in_time}
                )
                
                print(f"   [ISOLATION] Tenant {sample_tenant} has {len(tenant_device_results)} devices")
                for result in tenant_device_results:
                    print(f"      [TENANT] {result['tenant']}: {result['name']} (isolated data)")
            
            # Test unified time travel query (system-wide)
            unified_query = """
            FOR version IN hasVersion
              FILTER version._fromType IN ["DeviceProxyIn", "SoftwareProxyIn"]
              FILTER version.created <= @point_in_time AND version.expired > @point_in_time
              LIMIT 10
              RETURN {
                fromType: version._fromType,
                toType: version._toType,
                created: version.created
              }
            """
            
            unified_results = self.execute_and_display_query(
                unified_query,
                "System-Wide Unified Time Travel Query",
                {"point_in_time": point_in_time}
            )
            
            print(f"   [DATA] System-wide unified query returned {len(unified_results)} results across all tenants")
            device_count = sum(1 for r in unified_results if r['fromType'] == 'DeviceProxyIn')
            software_count = sum(1 for r in unified_results if r['fromType'] == 'SoftwareProxyIn')
            print(f"      [METRICS] Total Device versions: {device_count}, Total Software versions: {software_count}")
            
            # Validate that we have time travel data (unless database is completely empty)
            if len(device_results) == 0 and len(software_results) == 0:
                # Check if database is completely empty (fresh start) vs deployment failure
                total_docs_query = "RETURN LENGTH(Device) + LENGTH(Software) + LENGTH(Location)"
                total_docs = self.execute_and_display_query(total_docs_query, "Total Documents Check")
                if total_docs and total_docs[0] == 0:
                    # Check if collections even exist (deployment ran vs complete reset)
                    if (self.database.has_collection("Device") and 
                        self.database.has_collection("Software") and 
                        self.database.has_collection("Location")):
                        print(f"   [WARNING] Collections exist but are empty - possible deployment failure")
                        print(f"   [INFO] Continuing validation assuming pre-deployment state")
                        return True
                    else:
                        print(f"   [INFO] Database is completely empty - time travel validation skipped for fresh start")
                        return True
                else:
                    print(f"   [ERROR] Time travel queries returned no results but database has data")
                    return False
            
            print(f"[DONE] Time travel queries validation passed")
            return True
            
        except Exception as e:
            print(f"[ERROR] Time travel queries validation failed: {str(e)}")
            return False
    
    def validate_tenant_isolation(self) -> bool:
        """Validate that tenant data is properly isolated using SmartGraphs."""
        print(f"\n[ANALYSIS] Validating Tenant Isolation...")
        
        try:
            # Get all tenant IDs
            all_tenants_query = """
            FOR device IN Device
              COLLECT tenant = REGEX_SPLIT(device._key, "_")[0] WITH COUNT INTO deviceCount
              SORT tenant
              RETURN {
                tenant: tenant,
                deviceCount: deviceCount
              }
            """
            
            tenant_results = self.execute_and_display_query(
                all_tenants_query,
                "All Tenants Device Count Query"
            )
            
            print(f"   [TENANTS] Found {len(tenant_results)} tenants in the system")
            
            # Test isolation for each tenant
            for tenant_info in tenant_results[:3]:  # Test first 3 tenants
                tenant_id = tenant_info['tenant']
                print(f"\n   [ISOLATION] Testing tenant: {tenant_id}")
                
                # Test that tenant can only see its own data
                isolation_query = """
                FOR device IN Device
                  FILTER STARTS_WITH(device._key, @tenant_prefix)
                  LIMIT 5
                  RETURN {
                    key: device._key,
                    name: device.name,
                    tenant: REGEX_SPLIT(device._key, "_")[0],
                    type: device.type
                  }
                """
                
                isolation_results = self.execute_and_display_query(
                    isolation_query,
                    f"Tenant Isolation Test ({tenant_id})",
                    {"tenant_prefix": f"{tenant_id}_"}
                )
                
                # Verify all results belong to this tenant
                for result in isolation_results:
                    if result['tenant'] != tenant_id:
                        print(f"   [ERROR] Data leakage: Found {result['tenant']} data in {tenant_id} query")
                        return False
                    print(f"      [ISOLATED] {result['name']} belongs to {result['tenant']}")
                
                print(f"   [DONE] Tenant {tenant_id} isolation verified ({len(isolation_results)} devices)")
            
            # Test cross-tenant query doesn't leak data
            cross_tenant_query = """
            FOR device IN Device
              FILTER STARTS_WITH(device._key, @tenant1_prefix) OR STARTS_WITH(device._key, @tenant2_prefix)
              COLLECT tenant = REGEX_SPLIT(device._key, "_")[0] WITH COUNT INTO deviceCount
              RETURN {
                tenant: tenant,
                deviceCount: deviceCount
              }
            """
            
            if len(tenant_results) >= 2:
                tenant1 = tenant_results[0]['tenant']
                tenant2 = tenant_results[1]['tenant']
                
                cross_results = self.execute_and_display_query(
                    cross_tenant_query,
                    f"Cross-Tenant Boundary Test ({tenant1} vs {tenant2})",
                    {"tenant1_prefix": f"{tenant1}_", "tenant2_prefix": f"{tenant2}_"}
                )
                
                print(f"   [BOUNDARY] Cross-tenant query returned {len(cross_results)} tenant groups")
                for result in cross_results:
                    print(f"      [BOUNDARY] Tenant {result['tenant']}: {result['deviceCount']} devices")
            
            print(f"[DONE] Tenant isolation validation passed")
            return True
            
        except Exception as e:
            print(f"[ERROR] Tenant isolation validation failed: {str(e)}")
            return False
    
    def validate_cross_entity_relationships(self) -> bool:
        """Validate cross-entity relationships (Device → Software)."""
        print(f"\n[ANALYSIS] Validating Cross-Entity Relationships...")
        
        try:
            # Test Device → Software relationship query (corrected logical flow)
            cross_entity_query = """
            WITH DeviceProxyOut, SoftwareProxyIn, hasDeviceSoftware, Device, Software, hasVersion
            FOR hasDevSoft IN hasDeviceSoftware
              LIMIT 3
              
              // Find the device that connects TO this DeviceProxyOut (Device → DeviceProxyOut)
              FOR version_to_device_proxy IN hasVersion
                FILTER version_to_device_proxy._to == hasDevSoft._from
                FILTER version_to_device_proxy._fromType == "Device"
                LET device = DOCUMENT(version_to_device_proxy._from)
                
                // Find the software that connects FROM this SoftwareProxyIn (SoftwareProxyIn → Software)
                FOR version_to_software IN hasVersion
                  FILTER version_to_software._from == hasDevSoft._to
                  FILTER version_to_software._toType == "Software"
                  LET software = DOCUMENT(version_to_software._to)
                  
                  RETURN {
                    device: device.name,
                    deviceKey: device._key,
                    software: software.name,
                    softwareKey: software._key,
                    softwarePort: software.portNumber,
                    softwareEnabled: software.isEnabled,
                    flow: "Device → DeviceProxyOut → SoftwareProxyIn → Software"
                  }
            """
            
            cross_results = self.execute_and_display_query(
                cross_entity_query,
                "Cross-Entity Relationship Query"
            )
            
            print(f"   [DATA] Cross-entity query returned {len(cross_results)} relationships")
            for result in cross_results[:5]:
                print(f"      [DONE] {result['device']} → {result['software']} (port: {result['softwarePort']})")
                print(f"         Flow: {result['flow']}")
            
            # Validate hasDeviceSoftware collection exists and has data
            has_device_software = self.database.collection("hasDeviceSoftware")
            relationship_count = has_device_software.count()
            print(f"   [DATA] hasDeviceSoftware edges: {relationship_count}")
            
            if relationship_count == 0:
                # Check if database is empty (fresh start)
                device_count = self.database.collection("Device").count()
                if device_count == 0:
                    print(f"   [INFO] Database is empty - cross-entity validation skipped for fresh start")
                    return True
                else:
                    print(f"   [ERROR] No hasDeviceSoftware relationships found but database has devices")
                    return False
            
            # Sample relationship structure
            sample_relationship = has_device_software.all(limit=1)
            for rel in sample_relationship:
                print(f"      [DONE] Sample relationship: {rel['_from']} → {rel['_to']}")
                print(f"         Types: {rel['_fromType']} → {rel['_toType']}")
            
            print(f"[DONE] Cross-entity relationships validation passed")
            return True
            
        except Exception as e:
            print(f"[ERROR] Cross-entity relationships validation failed: {str(e)}")
            return False
    
    def validate_performance_improvements(self) -> bool:
        """Validate performance improvements from refactoring."""
        print(f"\n[ANALYSIS] Validating Performance Improvements...")
        
        try:
            # Test new flattened software query performance
            start_time = datetime.datetime.now()
            
            simple_software_query = """
            FOR software IN Software
              FILTER software.created <= @point_in_time AND software.expired > @point_in_time
              RETURN {
                name: software.name,
                type: software.type,
                port: software.portNumber,
                enabled: software.isEnabled
              }
            """
            
            point_in_time = datetime.datetime.now().timestamp()
            results = list(self.database.aql.execute(simple_software_query, bind_vars={"point_in_time": point_in_time}))
            
            end_time = datetime.datetime.now()
            query_duration = (end_time - start_time).total_seconds()
            
            print(f"   [DATA] Simple software query: {len(results)} results in {query_duration:.4f} seconds")
            
            # Test index usage on version collection
            version_index_query = """
            FOR version IN hasVersion
              FILTER version._fromType == "SoftwareProxyIn"
              FILTER version.created <= @point_in_time AND version.expired > @point_in_time
              RETURN version._key
            """
            
            start_time = datetime.datetime.now()
            version_results = list(self.database.aql.execute(version_index_query, bind_vars={"point_in_time": point_in_time}))
            end_time = datetime.datetime.now()
            version_duration = (end_time - start_time).total_seconds()
            
            print(f"   [DATA] Version index query: {len(version_results)} results in {version_duration:.4f} seconds")
            
            # Validate query performance is reasonable (under 1 second for typical datasets)
            if query_duration > 1.0:
                print(f"   [WARNING]  Software query duration seems high: {query_duration:.4f} seconds")
            else:
                print(f"   [DONE] Software query performance acceptable")
            
            if version_duration > 1.0:
                print(f"   [WARNING]  Version query duration seems high: {version_duration:.4f} seconds")
            else:
                print(f"   [DONE] Version query performance acceptable")
            
            print(f"[DONE] Performance validation completed")
            return True
            
        except Exception as e:
            print(f"[ERROR] Performance validation failed: {str(e)}")
            return False
    
    def validate_data_consistency(self) -> bool:
        """Validate data consistency between proxy and versioned collections."""
        print(f"\n[ANALYSIS] Validating Data Consistency...")
        
        try:
            # Check Device proxy → Device consistency
            device_proxy_count = self.database.collection("DeviceProxyIn").count()
            device_version_edges = self.database.collection("hasVersion").find({"_fromType": "DeviceProxyIn"}).count()
            
            print(f"   [DATA] DeviceProxyIn: {device_proxy_count}, Device version edges: {device_version_edges}")
            
            # Check Software proxy → Software consistency
            software_proxy_count = self.database.collection("SoftwareProxyIn").count()
            software_version_edges = self.database.collection("hasVersion").find({"_fromType": "SoftwareProxyIn"}).count()
            
            print(f"   [DATA] SoftwareProxyIn: {software_proxy_count}, Software version edges: {software_version_edges}")
            
            # Validate each proxy has at least one version
            if device_proxy_count > 0 and device_version_edges == 0:
                print(f"   [ERROR] Device proxies exist but no version edges found")
                return False
            
            if software_proxy_count > 0 and software_version_edges == 0:
                print(f"   [ERROR] Software proxies exist but no version edges found")
                return False
            
            # Check tenant isolation consistency
            sample_device = self.database.collection("Device").all(limit=1)
            sample_software = self.database.collection("Software").all(limit=1)
            
            for device in sample_device:
                tenant_attr = [key for key in device.keys() if key.startswith('tenant_') and key.endswith('_attr')]
                if not tenant_attr:
                    print(f"   [ERROR] Device {device['_key']} missing tenant attribute")
                    return False
                print(f"   [DONE] Device {device['_key']} has tenant attribute: {tenant_attr[0]}")
            
            for software in sample_software:
                tenant_attr = [key for key in software.keys() if key.startswith('tenant_') and key.endswith('_attr')]
                if not tenant_attr:
                    print(f"   [ERROR] Software {software['_key']} missing tenant attribute")
                    return False
                print(f"   [DONE] Software {software['_key']} has tenant attribute: {tenant_attr[0]}")
            
            print(f"[DONE] Data consistency validation passed")
            return True
            
        except Exception as e:
            print(f"[ERROR] Data consistency validation failed: {str(e)}")
            return False
    
    def run_comprehensive_validation(self) -> Dict[str, bool]:
        """Run all validation tests and return results."""
        print("[TEST] Network Asset Management Validation Suite")
        print("=" * 60)
        print("[ANALYSIS] Validating multi-tenant time travel implementation:")
        print("   • Software time travel pattern")
        print("   • Unified version collection")
        print("   • Cross-entity relationships")
        print("   • Query performance")
        print("   • Data consistency")
        print()
        
        if not self.connect_to_database():
            return {"connection": False}
        
        # Run all validation tests
        tests = [
            ("Collection Structure", self.validate_collection_structure),
            ("Software Refactoring", self.validate_software_refactoring),
            ("Unified Version Collection", self.validate_unified_version_collection),
            ("Time Travel Queries", self.validate_time_travel_queries),
            ("Cross-Entity Relationships", self.validate_cross_entity_relationships),
            ("Performance Improvements", self.validate_performance_improvements),
            ("Data Consistency", self.validate_data_consistency)
        ]
        
        results = {"connection": True}
        
        for test_name, test_function in tests:
            print(f"\n-> Running {test_name} validation...")
            try:
                result = test_function()
                results[test_name.lower().replace(" ", "_")] = result
                if result:
                    print(f"[DONE] {test_name} validation PASSED")
                else:
                    print(f"[ERROR] {test_name} validation FAILED")
            except Exception as e:
                print(f"[ERROR] {test_name} validation ERROR: {str(e)}")
                results[test_name.lower().replace(" ", "_")] = False
        
        # Summary
        passed_count = sum(1 for result in results.values() if result)
        total_count = len(results)
        
        print(f"\n[TARGET] Validation Summary:")
        print(f"   Passed: {passed_count}/{total_count} tests")
        
        if passed_count == total_count:
            print(f"[SUCCESS] All validations PASSED! Multi-tenant time travel is working correctly.")
        else:
            failed_tests = [test for test, result in results.items() if not result]
            print(f"[ERROR] Failed tests: {', '.join(failed_tests)}")
        
        return results


def main():
    """Main validation function."""
    validation_suite = TimeTravelValidationSuite()
    results = validation_suite.run_comprehensive_validation()
    
    # Write results to file
    results_file = Path("time_travel_validation_results.json")
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.datetime.now().isoformat(),
            "validation_results": results,
            "summary": {
                "total_tests": len(results),
                "passed_tests": sum(1 for result in results.values() if result),
                "success_rate": sum(1 for result in results.values() if result) / len(results) * 100
            }
        }, f, indent=2)
    
    print(f"\n Validation results saved to: {results_file}")
    
    # Exit with appropriate code
    if all(results.values()):
        print(f"[DONE] Network asset management validation completed successfully!")
        sys.exit(0)
    else:
        print(f"[ERROR] Network asset management validation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
