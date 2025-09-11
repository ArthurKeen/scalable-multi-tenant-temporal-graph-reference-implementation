"""
Deploy Final Corrected Data to ArangoDB Oasis

This script deploys the final corrected data with:
- No observedAt property
- expired property set to largest possible value
- TTL disabled
- W3C OWL collection names
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from arango import ArangoClient

# Import memory for cluster credentials
# [[memory:8684340]]
CLUSTER_ENDPOINT = "https://1d53cdf6fad0.arangodb.cloud:8529"
CLUSTER_USERNAME = "root"
CLUSTER_PASSWORD = "GcZO9wNKLq9faIuIUgnY"
DATABASE_NAME = "network_assets_demo"


class FinalCorrectedDatabaseDeployment:
    """Deploy final corrected W3C OWL data to ArangoDB Oasis."""
    
    def __init__(self):
        self.client = ArangoClient(hosts=CLUSTER_ENDPOINT)
        self.sys_db = None
        self.database = None
        
    def connect_to_cluster(self) -> bool:
        """Connect to ArangoDB Oasis cluster."""
        try:
            print(f"🔗 Connecting to ArangoDB Oasis cluster...")
            print(f"   Endpoint: {CLUSTER_ENDPOINT}")
            
            # Connect to system database
            self.sys_db = self.client.db('_system', username=CLUSTER_USERNAME, password=CLUSTER_PASSWORD)
            
            # Test connection
            version_info = self.sys_db.version()
            if isinstance(version_info, dict):
                print(f"   Version: {version_info.get('version', 'Unknown')}")
                print(f"   Server: {version_info.get('server', 'Unknown')}")
            else:
                print(f"   Connected: {version_info}")
            
            # Connect to target database
            if self.sys_db.has_database(DATABASE_NAME):
                self.database = self.client.db(DATABASE_NAME, username=CLUSTER_USERNAME, password=CLUSTER_PASSWORD)
                print(f"✅ Connected to database: {DATABASE_NAME}")
                return True
            else:
                print(f"❌ Database '{DATABASE_NAME}' not found")
                return False
                
        except Exception as e:
            print(f"❌ Connection failed: {str(e)}")
            return False
    
    def drop_and_recreate_database(self) -> bool:
        """Drop existing database and recreate with corrected structure."""
        try:
            print(f"\n🗑️  Dropping existing database: {DATABASE_NAME}")
            
            # Drop database if it exists
            if self.sys_db.has_database(DATABASE_NAME):
                self.sys_db.delete_database(DATABASE_NAME)
                print(f"   Dropped: {DATABASE_NAME}")
            
            # Create fresh database
            self.sys_db.create_database(DATABASE_NAME)
            self.database = self.client.db(DATABASE_NAME, username=CLUSTER_USERNAME, password=CLUSTER_PASSWORD)
            print(f"✅ Created fresh database: {DATABASE_NAME}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error recreating database: {str(e)}")
            return False
    
    def create_collections(self) -> bool:
        """Create W3C OWL compliant collections."""
        try:
            print(f"\n📋 Creating W3C OWL compliant collections...")
            
            # W3C OWL collection definitions
            vertex_collections = [
                {"name": "Device", "type": "vertex"},
                {"name": "DeviceProxyIn", "type": "vertex"},
                {"name": "DeviceProxyOut", "type": "vertex"},
                {"name": "Location", "type": "vertex"},
                {"name": "Software", "type": "vertex"}
            ]
            
            edge_collections = [
                {"name": "hasConnection", "type": "edge"},
                {"name": "hasLocation", "type": "edge"},
                {"name": "hasSoftware", "type": "edge"},
                {"name": "version", "type": "edge"}
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
            
            print(f"✅ Collections created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error creating collections: {str(e)}")
            return False
    
    def create_corrected_indexes(self) -> bool:
        """Create indexes without TTL (since observedAt removed)."""
        try:
            print(f"\n🔍 Creating corrected indexes (no TTL)...")
            
            # Corrected index configurations (no TTL, no observedAt)
            index_configs = [
                # Hash indexes for quick key lookups
                {
                    "collection": "Device",
                    "type": "hash",
                    "fields": ["_key"],
                    "name": "idx_devices_key"
                },
                
                # Vertex-centric indexes for graph performance
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
                    "collection": "hasSoftware",
                    "type": "persistent",
                    "fields": ["_from", "_toType"], 
                    "name": "idx_software_from_totype"
                },
                {
                    "collection": "version",
                    "type": "persistent",
                    "fields": ["created", "expired"],
                    "name": "idx_versions_temporal"
                }
            ]
            
            for index_config in index_configs:
                collection_name = index_config["collection"]
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    
                    if index_config["type"] == "persistent":
                        # Create persistent index
                        collection.add_persistent_index(
                            fields=index_config["fields"],
                            name=index_config.get("name")
                        )
                        print(f"   ✅ Created persistent index: {index_config['name']}")
                        
                    elif index_config["type"] == "hash":
                        # Create hash index
                        collection.add_hash_index(
                            fields=index_config["fields"],
                            name=index_config.get("name")
                        )
                        print(f"   ✅ Created hash index: {index_config['name']}")
            
            print(f"✅ Corrected indexes created (TTL disabled)")
            return True
            
        except Exception as e:
            print(f"❌ Error creating indexes: {str(e)}")
            return False
    
    def load_tenant_data(self) -> bool:
        """Load final corrected tenant data into collections."""
        try:
            print(f"\n📊 Loading final corrected tenant data...")
            
            # Find all tenant directories
            data_dir = Path("data")
            tenant_dirs = [d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("tenant_")]
            
            if not tenant_dirs:
                print(f"❌ No tenant data directories found in {data_dir}")
                return False
            
            # W3C OWL file to collection mappings
            file_mappings = {
                "Device.json": "Device",
                "DeviceProxyIn.json": "DeviceProxyIn",
                "DeviceProxyOut.json": "DeviceProxyOut",
                "Location.json": "Location",
                "Software.json": "Software",
                "hasConnection.json": "hasConnection",
                "hasLocation.json": "hasLocation",
                "hasSoftware.json": "hasSoftware",
                "version.json": "version"
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
                        print(f"      ⚠️  {filename}: file not found")
                
                print(f"   📊 Tenant {tenant_id}: {tenant_total} documents loaded")
            
            print(f"\n✅ Total documents loaded: {total_loaded}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {str(e)}")
            return False
    
    def create_named_graphs(self) -> bool:
        """Create named graphs for each tenant."""
        try:
            print(f"\n🕸️  Creating tenant named graphs...")
            
            # Read tenant registry
            registry_path = Path("data/tenant_registry_final.json")
            if not registry_path.exists():
                print(f"❌ Tenant registry not found: {registry_path}")
                return False
            
            with open(registry_path, 'r') as f:
                registry = json.load(f)
            
            # Create named graph for each tenant
            for tenant_id, tenant_info in registry["tenants"].items():
                graph_name = tenant_info["smartGraphName"]
                
                # Define edge relationships
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
                        "edge_collection": "hasSoftware",
                        "from_vertex_collections": ["DeviceProxyOut"],
                        "to_vertex_collections": ["Software"]
                    },
                    {
                        "edge_collection": "version",
                        "from_vertex_collections": ["DeviceProxyIn", "Device"],
                        "to_vertex_collections": ["Device", "DeviceProxyOut"]
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
                    print(f"   ✅ Created named graph: {graph_name}")
            
            print(f"✅ Named graphs created")
            return True
            
        except Exception as e:
            print(f"❌ Error creating named graphs: {str(e)}")
            return False
    
    def verify_corrected_deployment(self) -> bool:
        """Verify the corrected data structure is properly deployed."""
        try:
            print(f"\n🔍 Verifying corrected deployment...")
            
            # Check that observedAt is removed
            device_collection = self.database.collection("Device")
            sample_devices = device_collection.all(limit=3)
            
            for doc in sample_devices:
                if "observedAt" in doc:
                    print(f"❌ Found observedAt in document: {doc['_key']}")
                    return False
                
                if "expired" not in doc:
                    print(f"❌ Missing expired in document: {doc['_key']}")
                    return False
                
                # Check if expired is set to max value (for current documents)
                if doc.get("expired") == 9223372036854775807:
                    print(f"   ✅ Document {doc['_key']}: expired = max value")
                else:
                    print(f"   📋 Document {doc['_key']}: expired = {doc.get('expired')} (historical)")
            
            # Check DeviceProxyIn/Out have no temporal data
            proxy_in_collection = self.database.collection("DeviceProxyIn")
            sample_proxy = proxy_in_collection.all(limit=1)
            
            for doc in sample_proxy:
                has_temporal = any(key in doc for key in ["observedAt", "created", "expired"])
                if has_temporal:
                    print(f"❌ DeviceProxyIn has temporal data: {doc['_key']}")
                    return False
                else:
                    print(f"   ✅ DeviceProxyIn clean (no temporal data): {doc['_key']}")
            
            # Verify collections exist with correct names
            expected_collections = [
                "Device", "DeviceProxyIn", "DeviceProxyOut", "Location", "Software",
                "hasConnection", "hasLocation", "hasSoftware", "version"
            ]
            
            for collection_name in expected_collections:
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    count = collection.count()
                    print(f"   ✅ {collection_name}: {count} documents")
                else:
                    print(f"❌ Missing collection: {collection_name}")
                    return False
            
            print(f"✅ Corrected deployment verified successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error verifying deployment: {str(e)}")
            return False
    
    def deploy_final_corrected_data(self) -> bool:
        """Execute complete deployment of final corrected data."""
        print("🚀 Final Corrected Database Deployment")
        print("=" * 50)
        print("📋 Deploying:")
        print("   • No observedAt property")
        print("   • expired = largest possible value")
        print("   • TTL disabled")
        print("   • W3C OWL collection names")
        print()
        
        # Execute deployment steps
        steps = [
            ("Connect to cluster", self.connect_to_cluster),
            ("Drop and recreate database", self.drop_and_recreate_database),
            ("Create collections", self.create_collections),
            ("Create corrected indexes", self.create_corrected_indexes),
            ("Load tenant data", self.load_tenant_data),
            ("Create named graphs", self.create_named_graphs),
            ("Verify deployment", self.verify_corrected_deployment)
        ]
        
        for step_name, step_function in steps:
            print(f"\n🔄 {step_name}...")
            if not step_function():
                print(f"❌ Failed at step: {step_name}")
                return False
        
        print(f"\n🎉 Final corrected deployment completed successfully!")
        print(f"📊 Database: {DATABASE_NAME}")
        print(f"🔗 Endpoint: {CLUSTER_ENDPOINT}")
        print(f"🔧 Corrections applied:")
        print(f"   • observedAt removed from all collections")
        print(f"   • expired defaults to max value")
        print(f"   • TTL configuration disabled")
        print(f"   • W3C OWL naming conventions")
        
        return True


def main():
    """Main deployment function."""
    deployment = FinalCorrectedDatabaseDeployment()
    success = deployment.deploy_final_corrected_data()
    
    if success:
        print(f"\n✅ Database updated with final corrections!")
        sys.exit(0)
    else:
        print(f"\n❌ Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
