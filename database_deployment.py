"""
Deploy Time Travel Refactored Data to ArangoDB Oasis

Deploys the refactored time travel pattern with:
- Device time travel: DeviceProxyIn ⟷ Device ⟷ DeviceProxyOut
- Software time travel: SoftwareProxyIn ⟷ Software ⟷ SoftwareProxyOut (NEW)
- Unified 'version' collection for all time travel relationships
- New hasDeviceSoftware edge collection
- W3C OWL naming conventions
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from arango import ArangoClient

# Import centralized credentials
from centralized_credentials import CredentialsManager, DatabaseConstants


class TimeTravelRefactoredDeployment:
    """Deploy time travel refactored data to ArangoDB Oasis."""
    
    def __init__(self):
        creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=creds.endpoint)
        self.sys_db = None
        self.database = None
        self.creds = creds
        
    def connect_to_cluster(self) -> bool:
        """Connect to ArangoDB Oasis cluster."""
        try:
            print(f"🔗 Connecting to ArangoDB Oasis cluster...")
            print(f"   Endpoint: {self.creds.endpoint}")
            
            # Connect to system database
            self.sys_db = self.client.db('_system', **CredentialsManager.get_database_params())
            
            # Test connection
            version_info = self.sys_db.version()
            if isinstance(version_info, dict):
                print(f"   Version: {version_info.get('version', 'Unknown')}")
                print(f"   Server: {version_info.get('server', 'Unknown')}")
            else:
                print(f"   Connected: {version_info}")
            
            # Connect to target database
            if self.sys_db.has_database(self.creds.database_name):
                self.database = self.client.db(self.creds.database_name, **CredentialsManager.get_database_params())
                print(f"✅ Connected to database: {self.creds.database_name}")
                return True
            else:
                print(f"❌ Database '{self.creds.database_name}' not found")
                return False
                
        except Exception as e:
            print(f"❌ Connection failed: {str(e)}")
            return False
    
    def drop_and_recreate_database(self) -> bool:
        """Drop existing database and recreate with refactored structure."""
        try:
            print(f"\n🗑️  Dropping existing database: {self.creds.database_name}")
            
            # Drop database if it exists
            if self.sys_db.has_database(self.creds.database_name):
                self.sys_db.delete_database(self.creds.database_name)
                print(f"   Dropped: {self.creds.database_name}")
            
            # Create fresh database
            self.sys_db.create_database(self.creds.database_name)
            self.database = self.client.db(self.creds.database_name, **CredentialsManager.get_database_params())
            print(f"✅ Created fresh database: {self.creds.database_name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error recreating database: {str(e)}")
            return False
    
    def create_refactored_collections(self) -> bool:
        """Create time travel refactored collections."""
        try:
            print(f"\n📋 Creating time travel refactored collections...")
            
            # Refactored vertex collections (W3C OWL naming)
            vertex_collections = [
                {"name": "Device", "type": "vertex"},
                {"name": "DeviceProxyIn", "type": "vertex"},
                {"name": "DeviceProxyOut", "type": "vertex"},
                {"name": "Location", "type": "vertex"},
                {"name": "Software", "type": "vertex"},
                {"name": "SoftwareProxyIn", "type": "vertex"},  # NEW
                {"name": "SoftwareProxyOut", "type": "vertex"}  # NEW
            ]
            
            # Refactored edge collections (W3C OWL naming)
            edge_collections = [
                {"name": "hasConnection", "type": "edge"},
                {"name": "hasLocation", "type": "edge"},
                {"name": "hasDeviceSoftware", "type": "edge"},  # NEW - clearer naming
                {"name": "version", "type": "edge"}  # UNIFIED - handles both Device and Software versioning
            ]
            
            # Create vertex collections
            for collection_config in vertex_collections:
                name = collection_config["name"]
                if not self.database.has_collection(name):
                    self.database.create_collection(name)
                    print(f"   ✅ Created vertex collection: {name}")
                else:
                    print(f"   📋 Vertex collection '{name}' already exists")
            
            # Create edge collections
            for collection_config in edge_collections:
                name = collection_config["name"]
                if not self.database.has_collection(name):
                    self.database.create_collection(name, edge=True)
                    print(f"   ✅ Created edge collection: {name}")
                else:
                    print(f"   📋 Edge collection '{name}' already exists")
            
            print(f"✅ Time travel refactored collections created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error creating collections: {str(e)}")
            return False
    
    def create_refactored_indexes(self) -> bool:
        """Create indexes optimized for time travel refactored structure."""
        try:
            print(f"\n🔍 Creating time travel refactored indexes...")
            
            # Refactored index configurations
            index_configs = [
                # Hash indexes for quick key lookups
                {
                    "collection": "Device",
                    "type": "hash",
                    "fields": ["_key"],
                    "name": "idx_devices_key"
                },
                {
                    "collection": "Software",
                    "type": "hash", 
                    "fields": ["_key"],
                    "name": "idx_software_key"
                },
                
                # Vertex-centric indexes for graph performance (EXPANDED for Software)
                {
                    "collection": "hasConnection",
                    "type": "persistent",
                    "fields": ["_from", "_toType"],
                    "name": "idx_connections_from_totype"
                },
                {
                    "collection": "hasConnection", 
                    "type": "persistent",
                    "fields": ["_to", "_fromType"],
                    "name": "idx_connections_to_fromtype"
                },
                {
                    "collection": "hasLocation",
                    "type": "persistent", 
                    "fields": ["_from", "_toType"],
                    "name": "idx_locations_from_totype"
                },
                {
                    "collection": "hasDeviceSoftware",  # NEW
                    "type": "persistent",
                    "fields": ["_from", "_toType"], 
                    "name": "idx_device_software_from_totype"
                },
                {
                    "collection": "hasDeviceSoftware",  # NEW
                    "type": "persistent",
                    "fields": ["_to", "_fromType"], 
                    "name": "idx_device_software_to_fromtype"
                },
                
                # UNIFIED version collection indexes (handles Device + Software)
                {
                    "collection": "version",
                    "type": "persistent",
                    "fields": ["_from", "_toType"],
                    "name": "idx_version_from_totype"
                },
                {
                    "collection": "version",
                    "type": "persistent",
                    "fields": ["_to", "_fromType"],
                    "name": "idx_version_to_fromtype"
                },
                
                # Temporal range indexes for time travel queries (EXPANDED)
                {
                    "collection": "Device",
                    "type": "persistent",
                    "fields": ["created", "expired"],
                    "name": "idx_device_temporal"
                },
                {
                    "collection": "Software",  # NEW
                    "type": "persistent",
                    "fields": ["created", "expired"],
                    "name": "idx_software_temporal"
                },
                {
                    "collection": "version",
                    "type": "persistent",
                    "fields": ["created", "expired"],
                    "name": "idx_version_temporal"
                }
            ]
            
            for index_config in index_configs:
                collection_name = index_config["collection"]
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    
                    if index_config["type"] == "persistent":
                        collection.add_index({
                            'type': 'persistent',
                            'fields': index_config["fields"],
                            'name': index_config.get("name")
                        })
                        print(f"   ✅ Created persistent index: {index_config['name']}")
                        
                    elif index_config["type"] == "hash":
                        collection.add_index({
                            'type': 'hash',
                            'fields': index_config["fields"],
                            'name': index_config.get("name")
                        })
                        print(f"   ✅ Created hash index: {index_config['name']}")
            
            print(f"✅ Time travel refactored indexes created")
            return True
            
        except Exception as e:
            print(f"❌ Error creating indexes: {str(e)}")
            return False
    
    def load_refactored_data(self) -> bool:
        """Load time travel refactored tenant data into collections."""
        try:
            print(f"\n📊 Loading time travel refactored data...")
            
            # Find tenant directories with refactored data
            data_dir = Path("data")
            tenant_dirs = [d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("tenant_")]
            
            if not tenant_dirs:
                print(f"❌ No tenant data directories found in {data_dir}")
                return False
            
            # Time travel refactored file to collection mappings
            file_mappings = {
                "Device.json": "Device",
                "DeviceProxyIn.json": "DeviceProxyIn",
                "DeviceProxyOut.json": "DeviceProxyOut",
                "Location.json": "Location",
                "Software.json": "Software",
                "SoftwareProxyIn.json": "SoftwareProxyIn",      # NEW
                "SoftwareProxyOut.json": "SoftwareProxyOut",    # NEW
                "hasConnection.json": "hasConnection",
                "hasLocation.json": "hasLocation",
                "hasDeviceSoftware.json": "hasDeviceSoftware",  # NEW
                "version.json": "version"  # UNIFIED
            }
            
            total_loaded = 0
            
            for tenant_dir in tenant_dirs:
                tenant_id = tenant_dir.name.replace("tenant_", "")
                print(f"\n   📁 Loading tenant: {tenant_id}")
                
                tenant_total = 0
                
                for filename, collection_name in file_mappings.items():
                    file_path = tenant_dir / filename
                    if file_path.exists():
                        # Load JSON data
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        
                        if data:  # Only load if data exists
                            # Insert documents into collection
                            collection = self.database.collection(collection_name)
                            result = collection.insert_many(data, overwrite=True)
                            
                            doc_count = len(data)
                            tenant_total += doc_count
                            total_loaded += doc_count
                            print(f"      ✅ {collection_name}: {doc_count} documents")
                        else:
                            print(f"      📋 {collection_name}: empty file")
                    else:
                        if filename in ["SoftwareProxyIn.json", "SoftwareProxyOut.json", "hasDeviceSoftware.json"]:
                            print(f"      ⚠️  {filename}: NEW collection - file not found (expected for old data)")
                        else:
                            print(f"      ⚠️  {filename}: file not found")
                
                print(f"   📊 Tenant {tenant_id}: {tenant_total} documents loaded")
            
            print(f"\n✅ Total documents loaded: {total_loaded}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {str(e)}")
            return False
    
    def create_refactored_named_graphs(self) -> bool:
        """Create named graphs with refactored edge relationships."""
        try:
            print(f"\n🕸️  Creating refactored named graphs...")
            
            # Read tenant registry
            registry_path = Path("data/tenant_registry_time_travel.json")
            if not registry_path.exists():
                print(f"❌ Time travel tenant registry not found: {registry_path}")
                return False
            
            with open(registry_path, 'r') as f:
                registry = json.load(f)
            
            # Create named graph for each tenant with refactored relationships
            for tenant_id, tenant_info in registry["tenants"].items():
                graph_name = tenant_info["smartGraphName"]
                
                # Define refactored edge relationships
                edge_definitions = [
                    {
                        "edge_collection": "hasConnection",
                        "from_vertex_collections": ["DeviceProxyOut"],
                        "to_vertex_collections": ["DeviceProxyIn"]
                    },
                    {
                        "edge_collection": "hasLocation",
                        "from_vertex_collections": ["DeviceProxyOut"],
                        "to_vertex_collections": ["Location"]
                    },
                    {
                        "edge_collection": "hasDeviceSoftware",  # NEW - CORRECTED LOGIC
                        "from_vertex_collections": ["DeviceProxyOut"],
                        "to_vertex_collections": ["SoftwareProxyIn"]
                    },
                    {
                        "edge_collection": "version",  # UNIFIED - handles both Device and Software
                        "from_vertex_collections": ["DeviceProxyIn", "Device", "SoftwareProxyIn", "Software"],
                        "to_vertex_collections": ["Device", "DeviceProxyOut", "Software", "SoftwareProxyOut"]
                    }
                ]
                
                # Create or update named graph
                if self.database.has_graph(graph_name):
                    print(f"   📋 Graph '{graph_name}' already exists")
                else:
                    self.database.create_graph(
                        graph_name,
                        edge_definitions=edge_definitions
                    )
                    print(f"   ✅ Created refactored named graph: {graph_name}")
            
            print(f"✅ Refactored named graphs created")
            return True
            
        except Exception as e:
            print(f"❌ Error creating named graphs: {str(e)}")
            return False
    
    def verify_refactored_deployment(self) -> bool:
        """Verify the refactored time travel deployment."""
        try:
            print(f"\n🔍 Verifying time travel refactored deployment...")
            
            # Check new Software proxy collections exist
            software_proxy_collections = ["SoftwareProxyIn", "SoftwareProxyOut"]
            for collection_name in software_proxy_collections:
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    count = collection.count()
                    print(f"   ✅ {collection_name}: {count} documents")
                else:
                    print(f"   ⚠️  {collection_name}: collection not found (may be from old data)")
            
            # Check Software collection is refactored (no configurationHistory)
            software_collection = self.database.collection("Software")
            sample_software = software_collection.all(limit=1)
            
            for doc in sample_software:
                if "configurationHistory" in doc:
                    print(f"   ❌ Software still has configurationHistory: {doc['_key']}")
                    return False
                else:
                    print(f"   ✅ Software refactored (no configurationHistory): {doc['_key']}")
                
                # Check for flattened configuration
                if "portNumber" in doc and "isEnabled" in doc:
                    print(f"   ✅ Software has flattened configuration: portNumber={doc.get('portNumber')}, isEnabled={doc.get('isEnabled')}")
                else:
                    print(f"   ⚠️  Software missing flattened configuration")
            
            # Check unified version collection has both device and software edges
            version_collection = self.database.collection("version")
            
            # Query for device version edges
            device_version_count = version_collection.find({"_fromType": "DeviceProxyIn"}).count()
            print(f"   ✅ Device version edges: {device_version_count}")
            
            # Query for software version edges  
            software_version_count = version_collection.find({"_fromType": "SoftwareProxyIn"}).count()
            print(f"   ✅ Software version edges: {software_version_count}")
            
            # Check hasDeviceSoftware collection
            if self.database.has_collection("hasDeviceSoftware"):
                has_device_software = self.database.collection("hasDeviceSoftware")
                count = has_device_software.count()
                print(f"   ✅ hasDeviceSoftware: {count} edges")
            else:
                print(f"   ⚠️  hasDeviceSoftware: collection not found")
            
            # Verify all collections exist with correct names
            expected_collections = [
                "Device", "DeviceProxyIn", "DeviceProxyOut", "Location", "Software",
                "hasConnection", "hasLocation", "version"
            ]
            
            for collection_name in expected_collections:
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    count = collection.count()
                    print(f"   ✅ {collection_name}: {count} documents")
                else:
                    print(f"❌ Missing collection: {collection_name}")
                    return False
            
            print(f"✅ Time travel refactored deployment verified successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error verifying deployment: {str(e)}")
            return False
    
    def deploy_time_travel_refactored(self) -> bool:
        """Execute complete deployment of time travel refactored data."""
        print("🚀 Time Travel Refactored Database Deployment")
        print("=" * 60)
        print("📋 Deploying:")
        print("   • Device time travel: DeviceProxyIn ⟷ Device ⟷ DeviceProxyOut")
        print("   • Software time travel: SoftwareProxyIn ⟷ Software ⟷ SoftwareProxyOut (NEW)")
        print("   • Unified 'version' collection for all time travel relationships")
        print("   • New hasDeviceSoftware edge collection")
        print("   • Software configurationHistory array removed (flattened)")
        print()
        
        # Execute deployment steps
        steps = [
            ("Connect to cluster", self.connect_to_cluster),
            ("Drop and recreate database", self.drop_and_recreate_database),
            ("Create refactored collections", self.create_refactored_collections),
            ("Create refactored indexes", self.create_refactored_indexes),
            ("Load refactored data", self.load_refactored_data),
            ("Create refactored named graphs", self.create_refactored_named_graphs),
            ("Verify refactored deployment", self.verify_refactored_deployment)
        ]
        
        for step_name, step_function in steps:
            print(f"\n🔄 {step_name}...")
            if not step_function():
                print(f"❌ Failed at step: {step_name}")
                return False
        
        print(f"\n🎉 Time travel refactored deployment completed successfully!")
        print(f"📊 Database: {self.creds.database_name}")
        print(f"🔗 Endpoint: {self.creds.endpoint}")
        print(f"🔄 Time Travel Refactoring:")
        print(f"   • Device: Existing pattern maintained")
        print(f"   • Software: NEW time travel pattern implemented")
        print(f"   • Unified version collection for consistent queries")
        print(f"   • Software configurationHistory array eliminated")
        print(f"   • W3C OWL naming conventions")
        
        return True


def main():
    """Main deployment function."""
    deployment = TimeTravelRefactoredDeployment()
    success = deployment.deploy_time_travel_refactored()
    
    if success:
        print(f"\n✅ Database updated with time travel refactored structure!")
        sys.exit(0)
    else:
        print(f"\n❌ Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
