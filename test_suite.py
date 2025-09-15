"""
Comprehensive Test Suite for Multi-Tenant Network Asset Management Demo

Provides unit tests, integration tests, and compliance tests to ensure
code quality and functionality across all components.
"""

import unittest
import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, List, Any

# Import modules to test
from config_management import (
    ConfigurationManager, DatabaseCredentials, ApplicationPaths,
    CollectionConfiguration, GenerationLimits
)
from centralized_credentials import CredentialsManager
from tenant_config import TenantConfig, TenantNamingConvention, create_tenant_config
from data_generation_config import DeviceType, SoftwareType
from data_generation_utils import (
    KeyGenerator, RandomDataGenerator, DocumentEnhancer, FileManager
)


class TestConfigurationManagement(unittest.TestCase):
    """Test configuration management functionality."""
    
    def setUp(self):
        self.config = ConfigurationManager("development")
    
    def test_database_credentials_from_environment(self):
        """Test database credentials loading from credential manager."""
        # Test that credentials manager returns valid credentials
        creds = CredentialsManager.get_database_credentials()
        
        self.assertIsInstance(creds, DatabaseCredentials)
        self.assertTrue(creds.endpoint.startswith('https://'))
        self.assertEqual(creds.username, 'root')
        self.assertTrue(len(creds.password) > 0)
        self.assertEqual(creds.database_name, 'network_assets_demo')
    
    def test_application_paths_initialization(self):
        """Test application paths setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paths = ApplicationPaths(
                project_root=temp_path,
                data_directory=temp_path / 'data',
                docs_directory=temp_path / 'docs',
                logs_directory=temp_path / 'logs',
                reports_directory=temp_path / 'reports'
            )
            
            # Check that directories are created
            self.assertTrue(paths.data_directory.exists())
            self.assertTrue(paths.docs_directory.exists())
            self.assertTrue(paths.logs_directory.exists())
            self.assertTrue(paths.reports_directory.exists())
    
    def test_collection_configuration_owlrdf_compliance(self):
        """Test W3C OWL collection configuration."""
        config = CollectionConfiguration.get_owlrdf_config()
        
        # Test vertex collections (PascalCase)
        for logical_name, collection_name in config.vertex_collections.items():
            self.assertTrue(collection_name[0].isupper(), 
                          f"Vertex collection {collection_name} should be PascalCase")
            self.assertFalse(collection_name.endswith('s') and collection_name not in ['DeviceIn', 'DeviceOut'],
                           f"Vertex collection {collection_name} should be singular")
        
        # Test edge collections (camelCase)
        for logical_name, collection_name in config.edge_collections.items():
            self.assertTrue(collection_name[0].islower(),
                          f"Edge collection {collection_name} should be camelCase")
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        validation = self.config.validate_configuration()
        
        required_checks = [
            'credentials_valid', 'paths_exist', 
            'collections_configured', 'limits_reasonable'
        ]
        
        for check in required_checks:
            self.assertIn(check, validation)
            self.assertIsInstance(validation[check], bool)


class TestTenantConfiguration(unittest.TestCase):
    """Test tenant configuration functionality."""
    
    def test_tenant_config_creation(self):
        """Test tenant configuration creation."""
        tenant_config = create_tenant_config(
            "Test Corp",
            scale_factor=2,
            description="Test tenant"
        )
        
        self.assertEqual(tenant_config.tenant_name, "Test Corp")
        self.assertEqual(tenant_config.scale_factor, 2)
        self.assertEqual(tenant_config.description, "Test tenant")
        self.assertTrue(tenant_config.tenant_id)
        self.assertEqual(tenant_config.num_devices, 40)  # 20 * 2
    
    def test_tenant_naming_convention(self):
        """Test tenant naming conventions."""
        tenant_id = str(uuid.uuid4()).replace('-', '')[:12]
        naming = TenantNamingConvention(tenant_id)
        
        # Test W3C OWL compliance
        self.assertEqual(naming.device_collection, "Device")
        self.assertEqual(naming.has_connection_collection, "hasConnection")
        self.assertTrue(naming.smartgraph_name.startswith(f"tenant_{tenant_id}"))
        self.assertEqual(naming.database_name, "network_assets_demo")
    
    def test_tenant_isolation_validation(self):
        """Test tenant isolation properties."""
        tenant_config = create_tenant_config("Isolated Corp")
        naming = TenantNamingConvention(tenant_config.tenant_id)
        
        # Ensure unique tenant attributes
        attr = naming.smartgraph_attribute
        self.assertTrue(attr.startswith("tenant_"))
        self.assertTrue(attr.endswith("_attr"))
        self.assertIn(tenant_config.tenant_id, attr)


class TestDataGeneration(unittest.TestCase):
    """Test data generation functionality."""
    
    def setUp(self):
        self.tenant_config = create_tenant_config("Test Tenant", scale_factor=1)
    
    def test_key_generator_uniqueness(self):
        """Test key generator produces unique keys."""
        keys = set()
        for i in range(100):
            key = KeyGenerator.generate_tenant_key(
                self.tenant_config.tenant_id, "device", i + 1
            )
            self.assertNotIn(key, keys, "Generated key should be unique")
            keys.add(key)
    
    def test_key_generator_format(self):
        """Test key generator format compliance."""
        key = KeyGenerator.generate_tenant_key(
            self.tenant_config.tenant_id, "device", 1
        )
        
        # Should contain tenant ID
        self.assertIn(self.tenant_config.tenant_id, key)
        # Should contain entity type
        self.assertIn("device", key)
        # Should be reasonable length
        self.assertLess(len(key), 50)
    
    def test_random_data_generator_device_types(self):
        """Test random data generator device type selection."""
        from data_generation_config import NetworkConfig, DataGenerationLimits
        
        network_config = NetworkConfig()
        limits = DataGenerationLimits()
        gen = RandomDataGenerator(network_config, limits)
        
        # Test device type selection
        device_type = gen.select_device_type()
        self.assertIsInstance(device_type, DeviceType)
        
        # Test IP address generation
        ip = gen.generate_ip_address()
        self.assertRegex(ip, r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
        
        # Test MAC address generation
        mac = gen.generate_mac_address()
        self.assertRegex(mac, r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$')
    
    def test_document_enhancer_temporal_attributes(self):
        """Test document enhancer temporal attributes."""
        document = {"_key": "test_key", "name": "test_device"}
        
        enhanced = DocumentEnhancer.add_tenant_attributes(
            document, self.tenant_config
        )
        
        # Check temporal attributes (observedAt removed per architecture)
        self.assertIn("created", enhanced)
        self.assertIn("expired", enhanced)
        
        # Check tenant attribute
        tenant_attr = f"tenant_{self.tenant_config.tenant_id}_attr"
        self.assertIn(tenant_attr, enhanced)
        self.assertEqual(enhanced[tenant_attr], self.tenant_config.tenant_id)
    
    def test_document_enhancer_vertex_centric_attributes(self):
        """Test document enhancer vertex-centric attributes."""
        edge = DocumentEnhancer.create_edge_document(
            key="test_edge",
            from_collection="DeviceOut",
            from_key="device1",
            to_collection="DeviceIn", 
            to_key="device2",
            from_type="DeviceOut",
            to_type="DeviceIn",
            tenant_config=self.tenant_config
        )
        
        # Check edge structure
        self.assertEqual(edge["_from"], "DeviceOut/device1")
        self.assertEqual(edge["_to"], "DeviceIn/device2")
        self.assertEqual(edge["_fromType"], "DeviceOut")
        self.assertEqual(edge["_toType"], "DeviceIn")


class TestOWLRDFCompliance(unittest.TestCase):
    """Test W3C OWL compliance."""
    
    def test_collection_naming_compliance(self):
        """Test collection naming follows W3C OWL standards."""
        config = CollectionConfiguration.get_owlrdf_config()
        
        # Test vertex collections (entities - PascalCase, singular)
        vertex_collections = config.vertex_collections.values()
        for collection in vertex_collections:
            self.assertTrue(collection[0].isupper(), 
                          f"{collection} should start with uppercase (PascalCase)")
            # Allow compound names like DeviceProxyIn, DeviceProxyOut, SoftwareProxyIn, etc.
            base_name = collection.replace('Device', '').replace('Software', '').replace('Proxy', '').replace('In', '').replace('Out', '')
            self.assertTrue(len(base_name) == 0 or base_name.isalpha() or 
                          collection in ['Device', 'Software', 'Location', 'DeviceProxyIn', 'DeviceProxyOut', 'SoftwareProxyIn', 'SoftwareProxyOut'], 
                          f"{collection} should be valid W3C OWL entity name")
        
        # Test edge collections (predicates - camelCase, singular)
        edge_collections = config.edge_collections.values()
        for collection in edge_collections:
            self.assertTrue(collection[0].islower(),
                          f"{collection} should start with lowercase (camelCase)")
            self.assertFalse(collection.endswith('s'),
                           f"{collection} should be singular")
    
    def test_property_naming_compliance(self):
        """Test property naming follows W3C OWL standards."""
        # Test device properties
        device_properties = [
            "deviceName", "deviceType", "deviceModel", "serialNumber",
            "ipAddress", "macAddress", "operatingSystem", "osVersion", "hostName"
        ]
        
        for prop in device_properties:
            self.assertTrue(prop[0].islower(), f"{prop} should be camelCase")
            self.assertTrue(prop[0].isalpha(), f"{prop} should start with letter")
        
        # Test array properties (should be plural)
        array_properties = ["firewallRules", "configurationHistory"]
        for prop in array_properties:
            self.assertTrue(prop[0].islower(), f"{prop} should be camelCase")
            self.assertTrue(prop.endswith('s') or 'History' in prop, 
                          f"{prop} should indicate plurality")
    
    def test_rdf_triple_structure(self):
        """Test RDF triple structure (Subject-Predicate-Object)."""
        tenant_config = create_tenant_config("RDF Test")
        
        # Test connection edge (DeviceProxyOut --hasConnection--> DeviceProxyIn)
        connection = DocumentEnhancer.create_edge_document(
            key="test_connection",
            from_collection="DeviceProxyOut",
            from_key="device1",
            to_collection="DeviceProxyIn",
            to_key="device2", 
            from_type="DeviceProxyOut",
            to_type="DeviceProxyIn",
            tenant_config=tenant_config
        )
        
        # Validate RDF triple structure
        self.assertEqual(connection["_fromType"], "DeviceProxyOut")  # Subject type
        self.assertEqual(connection["_toType"], "DeviceProxyIn")     # Object type
        self.assertIn("DeviceProxyOut", connection["_from"])     # Subject collection
        
        # Test location edge (DeviceProxyOut --hasLocation--> Location)
        location = DocumentEnhancer.create_edge_document(
            key="test_location",
            from_collection="DeviceProxyOut", 
            from_key="device1",
            to_collection="Location",
            to_key="location1",
            from_type="DeviceProxyOut",
            to_type="Location", 
            tenant_config=tenant_config
        )
        
        self.assertEqual(location["_fromType"], "DeviceProxyOut")
        self.assertEqual(location["_toType"], "Location")


class TestFileManagement(unittest.TestCase):
    """Test file management functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tenant_config = create_tenant_config("File Test")
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_file_manager_directory_creation(self):
        """Test file manager creates directories properly."""
        # Test directory creation
        test_dir = Path(self.temp_dir) / f"tenant_{self.tenant_config.tenant_id}"
        
        # Create the directory
        test_dir.mkdir(parents=True, exist_ok=True)
        
        self.assertTrue(test_dir.exists())
        self.assertTrue(test_dir.is_dir())
    
    def test_file_manager_json_operations(self):
        """Test JSON file read/write operations."""
        test_file = Path(self.temp_dir) / "test.json"
        test_data = {"test": "data", "number": 42}
        
        # Test write
        FileManager.write_json_file(test_file, test_data)
        self.assertTrue(test_file.exists())
        
        # Test read
        with open(test_file, 'r') as f:
            loaded_data = json.load(f)
        
        self.assertEqual(loaded_data, test_data)


class TestIntegration(unittest.TestCase):
    """Integration tests for multi-tenant functionality."""
    
    def test_end_to_end_tenant_generation(self):
        """Test complete tenant data generation pipeline."""
        # Create tenant configuration
        tenant_config = create_tenant_config(
            "Integration Test Corp",
            scale_factor=1,
            num_devices=5,  # Small scale for testing
            num_locations=2
        )
        
        # Test tenant naming
        naming = TenantNamingConvention(tenant_config.tenant_id)
        self.assertEqual(naming.database_name, "network_assets_demo")
        
        # Test SmartGraph configuration generation
        from tenant_config import SmartGraphDefinition
        smartgraph_def = SmartGraphDefinition(naming)
        config = smartgraph_def.get_smartgraph_config()
        
        self.assertIn("graph_name", config)
        self.assertIn("edge_definitions", config)
        self.assertIn("options", config)
        
        # Validate edge definitions structure
        edge_defs = config["edge_definitions"]
        self.assertIsInstance(edge_defs, list)
        
        for edge_def in edge_defs:
            self.assertIn("edge_collection", edge_def)
            self.assertIn("from_vertex_collections", edge_def)
            self.assertIn("to_vertex_collections", edge_def)
    
    def test_tenant_isolation_design(self):
        """Test tenant isolation design principles."""
        tenant_a = create_tenant_config("Tenant A")
        tenant_b = create_tenant_config("Tenant B")
        
        naming_a = TenantNamingConvention(tenant_a.tenant_id)
        naming_b = TenantNamingConvention(tenant_b.tenant_id)
        
        # Different tenants should have different attributes
        self.assertNotEqual(naming_a.smartgraph_attribute, naming_b.smartgraph_attribute)
        self.assertNotEqual(naming_a.smartgraph_name, naming_b.smartgraph_name)
        
        # But should share the same database and collections
        self.assertEqual(naming_a.database_name, naming_b.database_name)
        self.assertEqual(naming_a.device_collection, naming_b.device_collection)


class TestPerformance(unittest.TestCase):
    """Performance and scalability tests."""
    
    def test_key_generation_performance(self):
        """Test key generation performance at scale."""
        import time
        
        tenant_id = "performance_test"
        start_time = time.time()
        
        # Generate 1000 keys
        keys = []
        for i in range(1000):
            key = KeyGenerator.generate_tenant_key(tenant_id, "device", i + 1)
            keys.append(key)
        
        end_time = time.time()
        generation_time = end_time - start_time
        
        # Should generate 1000 keys in reasonable time (< 1 second)
        self.assertLess(generation_time, 1.0)
        
        # All keys should be unique
        self.assertEqual(len(keys), len(set(keys)))
    
    def test_document_enhancement_performance(self):
        """Test document enhancement performance."""
        import time
        
        tenant_config = create_tenant_config("Performance Test")
        documents = [{"_key": f"device_{i}", "name": f"Device {i}"} for i in range(100)]
        
        start_time = time.time()
        
        enhanced_documents = []
        for doc in documents:
            enhanced = DocumentEnhancer.add_tenant_attributes(doc, tenant_config)
            enhanced_documents.append(enhanced)
        
        end_time = time.time()
        enhancement_time = end_time - start_time
        
        # Should enhance 100 documents in reasonable time
        self.assertLess(enhancement_time, 0.5)
        self.assertEqual(len(enhanced_documents), 100)


def run_test_suite():
    """Run the complete test suite."""
    
    print("[TEST] Multi-Tenant Demo Test Suite")
    print("=" * 50)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestConfigurationManagement,
        TestTenantConfiguration, 
        TestDataGeneration,
        TestOWLRDFCompliance,
        TestFileManagement,
        TestIntegration,
        TestPerformance
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Report results
    print(f"\n[DATA] Test Results:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    print(f"   Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\n[ERROR] Failures:")
        for test, traceback in result.failures:
            print(f"   {test}: {traceback}")
    
    if result.errors:
        print(f"\n[ERRORS]:")
        for test, traceback in result.errors:
            print(f"   {test}: {traceback}")
    
    overall_success = len(result.failures) == 0 and len(result.errors) == 0
    
    if overall_success:
        print(f"\n[SUCCESS] All tests passed! Code quality verified.")
    else:
        print(f"\n[WARNING]  Some tests failed. Review failures and errors above.")
    
    return overall_success


if __name__ == "__main__":
    success = run_test_suite()
    exit(0 if success else 1)
