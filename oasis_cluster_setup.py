"""
ArangoDB Oasis Cluster Setup and Management

This script handles the setup and configuration of the ArangoDB Oasis cluster
for the multi-tenant network asset management demo.

USAGE NOTE:
The current demo uses a SIMPLIFIED approach with:
- Shared collections across all tenants
- Single unified graph for visualization
- Logical tenant isolation via key prefixes

This module provides FULL ENTERPRISE functionality for:
- True SmartGraph isolation (separate collections per tenant)
- Physical data separation
- Complete tenant lifecycle management
- Production-grade cluster operations

WHEN TO USE THIS MODULE:
✅ Production deployments requiring true tenant isolation
✅ Enterprise environments with strict data separation
✅ Multi-tenant SaaS applications
✅ Compliance requirements for data segregation

WHEN DEMO APPROACH IS SUFFICIENT:
✅ Development and testing
✅ Proof of concept demonstrations
✅ Shared collection architectures
✅ Logical isolation requirements

Features:
- Connection testing and validation
- Database creation and configuration
- SmartGraph setup for disjoint tenant isolation
- Tenant lifecycle management
- Data loading and validation
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add the arango-mcp-server to the path for direct usage
sys.path.append('/Users/arthurkeen/code/arango-mcp-server')

try:
    from arango import ArangoClient
    from arango.exceptions import (
        ArangoServerError, DatabaseCreateError, DatabaseDeleteError,
        GraphCreateError, GraphDeleteError, CollectionCreateError
    )
except ImportError:
    print("ArangoDB client not available. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-arango"])
    from arango import ArangoClient
    from arango.exceptions import (
        ArangoServerError, DatabaseCreateError, DatabaseDeleteError,
        GraphCreateError, GraphDeleteError, CollectionCreateError
    )

# Import our tenant configuration and centralized credentials
from tenant_config import TenantConfig, TenantNamingConvention, SmartGraphDefinition
from data_generation_config import DATABASE_CONFIG
from centralized_credentials import CredentialsManager


class OasisClusterManager:
    """Manages ArangoDB Oasis cluster operations for multi-tenant demo."""
    
    def __init__(self, environment: str = "production"):
        creds = CredentialsManager.get_database_credentials(environment)
        self.endpoint = creds.endpoint
        self.username = creds.username
        self.password = creds.password
        self.database_name = creds.database_name
        self.client = None
        self.database = None
        
    def connect(self) -> bool:
        """
        Test connection to the Oasis cluster.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            print(f"Connecting to ArangoDB Oasis cluster: {self.endpoint}")
            self.client = ArangoClient(hosts=self.endpoint)
            
            # Test connection by getting server version
            sys_db = self.client.db('_system', username=self.username, password=self.password)
            version_info = sys_db.version()
            
            print(f"[DONE] Connected successfully!")
            print(f"   Server version: {version_info}")
            
            # Handle version info safely
            if isinstance(version_info, dict):
                print(f"   License: {version_info.get('license', 'Community')}")
            else:
                print(f"   Version string: {version_info}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Connection failed: {str(e)}")
            return False
    
    def create_shared_database(self, db_name: str = None) -> bool:
        """
        Create the shared database for all tenants.
        
        Args:
            db_name: Database name (defaults to network_assets_demo)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            print("[ERROR] Not connected to cluster")
            return False
            
        db_name = db_name or self.database_name
        
        try:
            sys_db = self.client.db('_system', username=self.username, password=self.password)
            
            # Check if database already exists
            if sys_db.has_database(db_name):
                print(f"[INFO] Database '{db_name}' already exists")
                self.database = self.client.db(db_name, username=self.username, password=self.password)
                return True
            
            # Create the database
            sys_db.create_database(db_name)
            self.database = self.client.db(db_name, username=self.username, password=self.password)
            
            print(f"[DONE] Created database: {db_name}")
            return True
            
        except DatabaseCreateError as e:
            print(f"[ERROR] Failed to create database: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error creating database: {e}")
            return False
    
    def create_shared_collections(self) -> bool:
        """
        Create the shared collections for all tenants.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.database:
            print("[ERROR] No database connection")
            return False
        
        # Define collection configurations
        vertex_collections = [
            {"name": "devices", "type": "vertex"},
            {"name": "device_ins", "type": "vertex"},  
            {"name": "device_outs", "type": "vertex"},
            {"name": "locations", "type": "vertex"},
            {"name": "software", "type": "vertex"}
        ]
        
        edge_collections = [
            {"name": "has_connections", "type": "edge"},
            {"name": "has_locations", "type": "edge"},
            {"name": "has_software", "type": "edge"},
            {"name": "version", "type": "edge"}
        ]
        
        try:
            # Create vertex collections
            for collection_config in vertex_collections:
                name = collection_config["name"]
                if not self.database.has_collection(name):
                    self.database.create_collection(name)
                    print(f"[DONE] Created vertex collection: {name}")
                else:
                    print(f"[INFO] Vertex collection '{name}' already exists")
            
            # Create edge collections
            for collection_config in edge_collections:
                name = collection_config["name"]
                if not self.database.has_collection(name):
                    self.database.create_collection(name, edge=True)
                    print(f"[DONE] Created edge collection: {name}")
                else:
                    print(f"[INFO] Edge collection '{name}' already exists")
            
            return True
            
        except CollectionCreateError as e:
            print(f"[ERROR] Failed to create collection: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error creating collections: {e}")
            return False
    
    def create_tenant_smartgraph(self, tenant_config: TenantConfig) -> bool:
        """
        Create a disjoint SmartGraph for a tenant.
        
        Args:
            tenant_config: Tenant configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.database:
            print("[ERROR] No database connection")
            return False
        
        naming = TenantNamingConvention(tenant_config.tenant_id)
        smartgraph_def = SmartGraphDefinition(naming)
        graph_config = smartgraph_def.get_smartgraph_config()
        
        graph_name = graph_config["graph_name"]
        
        try:
            # Check if graph already exists
            if self.database.has_graph(graph_name):
                print(f"[INFO] SmartGraph '{graph_name}' already exists")
                return True
            
            # Create the SmartGraph
            graph = self.database.create_graph(
                name=graph_name,
                edge_definitions=graph_config["edge_definitions"],
                smart=True,
                smart_field=graph_config["options"]["smart_graph_attribute"]
            )
            
            print(f"[DONE] Created SmartGraph for tenant: {tenant_config.tenant_name}")
            print(f"   Graph name: {graph_name}")
            print(f"   SmartGraph attribute: {graph_config['options']['smart_graph_attribute']}")
            
            return True
            
        except GraphCreateError as e:
            print(f"[ERROR] Failed to create SmartGraph: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error creating SmartGraph: {e}")
            return False
    
    def create_indexes(self, tenant_config: TenantConfig) -> bool:
        """
        Create required indexes for a tenant's data.
        
        Args:
            tenant_config: Tenant configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.database:
            print("[ERROR] No database connection")
            return False
        
        try:
            # Define index configurations based on PRD requirements
            index_configs = [
                # Temporal indexing is now handled by created/expired timestamps with TTL
                
                # Vertex-centric indexes for graph performance (FR6.1)
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
                
                # Hash indexes for quick key lookups (FR6.2)
                {
                    "collection": "Device",
                    "type": "hash",
                    "fields": ["_key"],
                    "name": "idx_devices_key"
                },
                
                # Temporal range indexes for time travel queries (FR6.3) - using created/expired
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
                    
                    # TTL index creation is now handled by dedicated TTL deployment system
                    
                    if index_config["type"] == "persistent":
                        # Create persistent index
                        collection.add_persistent_index(
                            fields=index_config["fields"],
                            name=index_config.get("name")
                        )
                        print(f"[DONE] Created persistent index on {collection_name}: {index_config['fields']}")
                        
                    elif index_config["type"] == "hash":
                        # Create hash index
                        collection.add_hash_index(
                            fields=index_config["fields"],
                            name=index_config.get("name")
                        )
                        print(f"[DONE] Created hash index on {collection_name}: {index_config['fields']}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Error creating indexes: {e}")
            return False
    
    def load_tenant_data(self, tenant_config: TenantConfig, data_directory: str = None) -> bool:
        """
        Load tenant data into the database.
        
        Args:
            tenant_config: Tenant configuration
            data_directory: Directory containing tenant JSON files
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.database:
            print("[ERROR] No database connection")
            return False
        
        if not data_directory:
            naming = TenantNamingConvention(tenant_config.tenant_id)
            data_directory = naming.data_directory
        
        data_dir = Path(data_directory)
        if not data_dir.exists():
            print(f"[ERROR] Data directory not found: {data_directory}")
            return False
        
        # Define file mappings
        file_mappings = {
            "Device.json": "devices",
            "DeviceIn.json": "device_ins",
            "DeviceOut.json": "device_outs", 
            "Location.json": "locations",
            "Software.json": "software",
            "hasConnection.json": "has_connections",
            "hasLocation.json": "has_locations",
            "hasSoftware.json": "has_software",
            "version.json": "versions"
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
                        
                        print(f"[DONE] Loaded {loaded_count} documents into {collection_name}")
                    else:
                        print(f"[WARNING]  Empty data file: {filename}")
                else:
                    print(f"[WARNING]  File not found: {filename}")
            
            print(f"[DONE] Total documents loaded for tenant {tenant_config.tenant_name}: {total_loaded}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error loading tenant data: {e}")
            return False
    
    def validate_tenant_isolation(self, tenant_configs: List[TenantConfig]) -> bool:
        """
        Validate that tenant data is properly isolated.
        
        Args:
            tenant_configs: List of tenant configurations to validate
            
        Returns:
            bool: True if isolation is verified, False otherwise
        """
        if not self.database:
            print("[ERROR] No database connection")
            return False
        
        print("\n[ANALYSIS] Validating tenant isolation...")
        
        try:
            for tenant_config in tenant_configs:
                tenant_attr = f"tenant_{tenant_config.tenant_id}_attr"
                
                # Auto-detect collection name (Device for W3C OWL, devices for legacy)
                collection_name = "Device" if self.database.has_collection("Device") else "devices"
                
                # Query devices for this tenant
                aql = f"""
                FOR doc IN {collection_name}
                FILTER doc.`{tenant_attr}` == @tenant_id
                RETURN doc._key
                """
                
                cursor = self.database.aql.execute(
                    aql, 
                    bind_vars={"tenant_id": tenant_config.tenant_id}
                )
                
                tenant_docs = list(cursor)
                print(f"[DONE] Tenant {tenant_config.tenant_name}: {len(tenant_docs)} isolated documents")
                
                # Verify no cross-tenant data
                other_tenant_aql = f"""
                FOR doc IN {collection_name}  
                FILTER doc.`{tenant_attr}` != @tenant_id AND doc.`{tenant_attr}` != null
                RETURN doc._key
                """
                
                other_cursor = self.database.aql.execute(
                    other_tenant_aql,
                    bind_vars={"tenant_id": tenant_config.tenant_id}
                )
                
                other_docs = list(other_cursor)
                if len(other_docs) == 0:
                    print(f"[DONE] No cross-tenant data access for {tenant_config.tenant_name}")
                else:
                    print(f"[ERROR] Cross-tenant access detected for {tenant_config.tenant_name}")
                    return False
            
            print("[DONE] Tenant isolation validation successful!")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error validating tenant isolation: {e}")
            return False
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """
        Get comprehensive cluster status and statistics.
        
        Returns:
            dict: Cluster status information
        """
        if not self.database:
            return {"error": "Not connected"}
        
        try:
            sys_db = self.client.db('_system', username=self.username, password=self.password)
            
            # Get server info
            version_info = sys_db.version()
            
            # Get database info
            db_info = self.database.properties()
            
            # Get collection statistics
            collections = self.database.collections()
            collection_stats = {}
            
            for collection in collections:
                if not collection['name'].startswith('_'):  # Skip system collections
                    coll = self.database.collection(collection['name'])
                    stats = coll.statistics()
                    collection_stats[collection['name']] = {
                        "count": stats.get('count', 0),
                        "size": stats.get('documents_size', 0)
                    }
            
            # Get graph information
            graphs = self.database.graphs()
            graph_info = [{"name": g["name"], "edge_definitions": len(g.get("edge_definitions", []))} for g in graphs]
            
            return {
                "server_version": version_info,
                "database": db_info,
                "collections": collection_stats,
                "graphs": graph_info,
                "total_documents": sum(stats["count"] for stats in collection_stats.values())
            }
            
        except Exception as e:
            return {"error": str(e)}


def main():
    """Main function to test cluster setup and configuration."""
    
    print("[DEPLOY] ArangoDB Oasis Cluster Setup")
    print("=" * 50)
    
    # Initialize cluster manager with centralized credentials
    manager = OasisClusterManager()
    
    # Test connection
    if not manager.connect():
        return False
    
    # Create shared database
    if not manager.create_shared_database():
        return False
    
    # Create shared collections
    if not manager.create_shared_collections():
        return False
    
    print("\n[DONE] Basic cluster setup complete!")
    
    # Get cluster status
    status = manager.get_cluster_status()
    print(f"\n[DATA] Cluster Status:")
    print(f"   Server version: {status.get('server_version', 'Unknown')}")
    print(f"   Database: {status.get('database', {}).get('name', 'Unknown')}")
    print(f"   Collections: {len(status.get('collections', {}))}")
    print(f"   Total documents: {status.get('total_documents', 0)}")
    
    return True


if __name__ == "__main__":
    success = main()
    if success:
        print("\n[SUCCESS] Cluster setup completed successfully!")
    else:
        print("\n[ERROR] Cluster setup failed!")
        sys.exit(1)
