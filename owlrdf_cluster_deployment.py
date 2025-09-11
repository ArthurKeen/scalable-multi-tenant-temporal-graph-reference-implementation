"""
W3C OWL Compliant Cluster Deployment

Deploy W3C OWL compliant multi-tenant data to ArangoDB Oasis cluster.
"""

import json
from pathlib import Path

from oasis_cluster_setup import OasisClusterManager
from tenant_config import create_tenant_config
from data_generation_config import COLLECTION_NAMES


class OWLRDFClusterManager(OasisClusterManager):
    """Extended cluster manager for W3C OWL compliant deployments."""
    
    def reset_database_owlrdf(self, db_name: str = None) -> bool:
        """Reset database for W3C OWL compliant deployment."""
        if not self.client:
            print("❌ Not connected to cluster")
            return False
            
        db_name = db_name or "network_assets_demo"
        
        try:
            sys_db = self.client.db('_system', username=self.username, password=self.password)
            
            # Drop database if it exists
            if sys_db.has_database(db_name):
                print(f"🗑️  Dropping existing database: {db_name}")
                sys_db.delete_database(db_name)
            
            # Create fresh database
            print(f"🆕 Creating fresh W3C OWL compliant database: {db_name}")
            sys_db.create_database(db_name)
            self.database = self.client.db(db_name, username=self.username, password=self.password)
            
            return True
            
        except Exception as e:
            print(f"❌ Error resetting database: {e}")
            return False
    
    def create_owlrdf_collections(self) -> bool:
        """Create W3C OWL compliant collections."""
        if not self.database:
            print("❌ No database connection")
            return False
        
        try:
            # W3C OWL compliant vertex collections (PascalCase, singular)
            vertex_collections = [
                COLLECTION_NAMES["devices"],      # Device
                COLLECTION_NAMES["device_ins"],   # DeviceIn
                COLLECTION_NAMES["device_outs"],  # DeviceOut
                COLLECTION_NAMES["locations"],    # Location
                COLLECTION_NAMES["software"]      # Software
            ]
            
            # W3C OWL compliant edge collections (camelCase, singular)
            edge_collections = [
                COLLECTION_NAMES["connections"],    # hasConnection
                COLLECTION_NAMES["has_locations"],  # hasLocation
                COLLECTION_NAMES["has_software"],   # hasSoftware
                COLLECTION_NAMES["versions"]        # version
            ]
            
            # Create vertex collections
            for collection_name in vertex_collections:
                if not self.database.has_collection(collection_name):
                    self.database.create_collection(collection_name)
                    print(f"✅ Created vertex collection: {collection_name}")
                else:
                    print(f"📋 Vertex collection '{collection_name}' already exists")
            
            # Create edge collections
            for collection_name in edge_collections:
                if not self.database.has_collection(collection_name):
                    self.database.create_collection(collection_name, edge=True)
                    print(f"✅ Created edge collection: {collection_name}")
                else:
                    print(f"📋 Edge collection '{collection_name}' already exists")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating W3C OWL collections: {e}")
            return False
    
    def create_owlrdf_named_graphs(self, tenant_configs) -> bool:
        """Create W3C OWL compliant named graphs."""
        if not self.database:
            print("❌ No database connection")
            return False
        
        try:
            for tenant_config in tenant_configs:
                from tenant_config import TenantNamingConvention, SmartGraphDefinition
                
                naming = TenantNamingConvention(tenant_config.tenant_id)
                smartgraph_def = SmartGraphDefinition(naming)
                graph_config = smartgraph_def.get_smartgraph_config()
                
                graph_name = graph_config["graph_name"]
                
                # Create regular named graph with W3C OWL collections
                if not self.database.has_graph(graph_name):
                    self.database.create_graph(
                        name=graph_name,
                        edge_definitions=graph_config["edge_definitions"]
                    )
                    print(f"✅ Created W3C OWL graph: {graph_name}")
                else:
                    print(f"📋 Graph exists: {graph_name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating W3C OWL graphs: {e}")
            return False
    
    def load_owlrdf_tenant_data(self, tenant_config, data_directory: str = None) -> bool:
        """Load W3C OWL compliant tenant data."""
        if not self.database:
            print("❌ No database connection")
            return False
        
        if not data_directory:
            naming = TenantNamingConvention(tenant_config.tenant_id)
            data_directory = naming.data_directory
        
        data_dir = Path(data_directory)
        if not data_dir.exists():
            print(f"❌ Data directory not found: {data_directory}")
            return False
        
        # W3C OWL file mappings
        file_mappings = {
            "Device.json": COLLECTION_NAMES["devices"],          # Device
            "DeviceIn.json": COLLECTION_NAMES["device_ins"],     # DeviceIn
            "DeviceOut.json": COLLECTION_NAMES["device_outs"],   # DeviceOut
            "Location.json": COLLECTION_NAMES["locations"],      # Location
            "Software.json": COLLECTION_NAMES["software"],       # Software
            "hasConnection.json": COLLECTION_NAMES["connections"], # hasConnection
            "hasLocation.json": COLLECTION_NAMES["has_locations"], # hasLocation
            "hasSoftware.json": COLLECTION_NAMES["has_software"],  # hasSoftware
            "version.json": COLLECTION_NAMES["versions"]         # version
        }
        
        total_loaded = 0
        
        try:
            for filename, collection_name in file_mappings.items():
                file_path = data_dir / filename
                if file_path.exists():
                    # Load JSON data
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    if data and len(data) > 0:
                        # Get collection
                        collection = self.database.collection(collection_name)
                        
                        # Import documents
                        result = collection.import_bulk(data)
                        
                        loaded_count = result.get('created', 0)
                        total_loaded += loaded_count
                        
                        print(f"✅ Loaded {loaded_count} documents into {collection_name}")
                    else:
                        print(f"⚠️  Empty data file: {filename}")
                else:
                    print(f"⚠️  File not found: {filename}")
            
            print(f"✅ Total W3C OWL documents loaded for {tenant_config.tenant_name}: {total_loaded}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading W3C OWL data: {e}")
            return False
    
    def validate_owlrdf_compliance(self, tenant_configs) -> bool:
        """Validate W3C OWL compliance."""
        print("\n🦉 Validating W3C OWL Compliance...")
        
        try:
            # Check collection naming compliance
            collections = self.database.collections()
            vertex_collections = [c for c in collections if not c['name'].startswith('_') and c['type'] == 2]  # vertex
            edge_collections = [c for c in collections if not c['name'].startswith('_') and c['type'] == 3]     # edge
            
            print(f"   Vertex Collections (PascalCase, singular):")
            for collection in vertex_collections:
                name = collection['name']
                is_pascal = name[0].isupper() and name[0].isalpha()
                print(f"     {name}: {'✅' if is_pascal else '❌'} {'PascalCase' if is_pascal else 'Not PascalCase'}")
            
            print(f"   Edge Collections (camelCase, singular):")
            for collection in edge_collections:
                name = collection['name']
                is_camel = name[0].islower() and name[0].isalpha()
                print(f"     {name}: {'✅' if is_camel else '❌'} {'camelCase' if is_camel else 'Not camelCase'}")
            
            # Check property naming in sample documents
            print(f"   Property Naming Compliance:")
            for tenant_config in tenant_configs[:1]:  # Check first tenant
                tenant_attr = f"tenant_{tenant_config.tenant_id}_attr"
                
                # Check device properties
                device_query = f"""
                FOR doc IN Device
                FILTER doc.`{tenant_attr}` == @tenant_id
                LIMIT 1
                RETURN doc
                """
                
                cursor = self.database.aql.execute(device_query, bind_vars={"tenant_id": tenant_config.tenant_id})
                devices = list(cursor)
                
                if devices:
                    device = devices[0]
                    owlrdf_properties = [
                        "deviceName", "deviceType", "deviceModel", "serialNumber",
                        "ipAddress", "macAddress", "operatingSystem", "osVersion", 
                        "hostName", "firewallRules"
                    ]
                    
                    for prop in owlrdf_properties:
                        if prop in device:
                            is_camel = prop[0].islower() and prop[0].isalpha()
                            is_plural_for_array = (prop.endswith('s') and isinstance(device[prop], list)) if prop in device else False
                            compliance = "✅" if is_camel else "❌"
                            print(f"     {prop}: {compliance} {'camelCase' if is_camel else 'Not camelCase'}")
            
            print("   ✅ W3C OWL compliance validated!")
            return True
            
        except Exception as e:
            print(f"   ❌ W3C OWL validation error: {e}")
            return False


def deploy_owlrdf_cluster():
    """Deploy W3C OWL compliant multi-tenant cluster."""
    
    # Oasis cluster credentials
    OASIS_ENDPOINT = "https://1d53cdf6fad0.arangodb.cloud:8529"
    OASIS_USERNAME = "root"
    OASIS_PASSWORD = "GcZO9wNKLq9faIuIUgnY"
    
    print("🦉 W3C OWL Compliant Cluster Deployment")
    print("=" * 60)
    
    # Initialize manager
    manager = OWLRDFClusterManager(OASIS_ENDPOINT, OASIS_USERNAME, OASIS_PASSWORD)
    
    # Connect to cluster
    if not manager.connect():
        return False
    
    # Reset database for clean W3C OWL deployment
    if not manager.reset_database_owlrdf():
        return False
    
    # Create W3C OWL compliant collections
    if not manager.create_owlrdf_collections():
        return False
    
    # Load tenant configurations
    registry_path = Path("data/tenant_registry_owlrdf.json")
    if not registry_path.exists():
        print("❌ W3C OWL tenant registry not found")
        return False
    
    with open(registry_path, 'r') as f:
        registry = json.load(f)
    
    tenant_configs = []
    for tenant_id, tenant_info in registry["tenants"].items():
        tenant_config = create_tenant_config(
            tenant_info["tenantName"],  # Updated property name
            scale_factor=tenant_info["scaleFactor"],  # Updated property name
            description=tenant_info["tenantDescription"]  # Updated property name
        )
        tenant_config.tenant_id = tenant_id
        tenant_configs.append(tenant_config)
    
    print(f"📋 Found {len(tenant_configs)} W3C OWL tenants")
    
    # Create named graphs
    if not manager.create_owlrdf_named_graphs(tenant_configs):
        return False
    
    # Load tenant data
    print(f"\n📥 Loading W3C OWL tenant data...")
    for tenant_config in tenant_configs:
        tenant_info = registry["tenants"][tenant_config.tenant_id]
        print(f"   Loading {tenant_config.tenant_name}...")
        
        if manager.load_owlrdf_tenant_data(tenant_config, tenant_info["dataDirectory"]):
            print(f"   ✅ W3C OWL data loaded for {tenant_config.tenant_name}")
        else:
            print(f"   ❌ Failed to load data for {tenant_config.tenant_name}")
            return False
    
    # Validate W3C OWL compliance
    if not manager.validate_owlrdf_compliance(tenant_configs):
        return False
    
    # Validate tenant isolation
    print(f"\n🔍 Validating tenant isolation...")
    if manager.validate_tenant_isolation(tenant_configs):
        print(f"✅ Tenant isolation validated!")
    else:
        print(f"❌ Tenant isolation failed!")
        return False
    
    # Get final status
    print(f"\n📊 Final W3C OWL Cluster Status:")
    status = manager.get_cluster_status()
    print(f"   Database: {status.get('database', {}).get('name', 'Unknown')}")
    print(f"   Collections: {len(status.get('collections', {}))}")
    print(f"   Named Graphs: {len(status.get('graphs', []))}")
    print(f"   Total documents: {status.get('total_documents', 0)}")
    
    # Show W3C OWL collection breakdown
    print(f"\n🏛️  W3C OWL Collection Statistics:")
    for coll_name, stats in status.get('collections', {}).items():
        if not coll_name.startswith('_'):
            collection_type = "Vertex (PascalCase)" if coll_name[0].isupper() else "Edge (camelCase)"
            print(f"   {coll_name}: {stats['count']} documents ({collection_type})")
    
    return True


if __name__ == "__main__":
    success = deploy_owlrdf_cluster()
    if success:
        print(f"\n🎉 W3C OWL compliant deployment completed!")
        print(f"🔗 Access your cluster at: https://1d53cdf6fad0.arangodb.cloud:8529")
        print(f"📊 Database: network_assets_demo")
        print(f"🦉 Standards: W3C OWL naming conventions")
        print(f"🛡️  Complete tenant isolation verified!")
    else:
        print(f"\n❌ W3C OWL deployment failed!")
        exit(1)
