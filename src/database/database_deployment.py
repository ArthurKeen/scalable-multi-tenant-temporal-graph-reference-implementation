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

# Import centralized credentials and configuration
from src.config.centralized_credentials import CredentialsManager
from src.config.config_management import get_config, NamingConvention
from src.ttl.ttl_config import (create_ttl_configuration, create_demo_ttl_configuration, TTLManager)
from src.ttl.ttl_constants import DEFAULT_TTL_DAYS, TTLConstants


class TimeTravelRefactoredDeployment:
    """Deploy time travel refactored data to ArangoDB Oasis."""
    
    def __init__(self, naming_convention: NamingConvention = NamingConvention.CAMEL_CASE, demo_mode: bool = False):
        self.naming_convention = naming_convention
        self.demo_mode = demo_mode
        self.app_config = get_config("production", naming_convention)
        creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=creds.endpoint)
        self.sys_db = None
        self.database = None
        self.creds = creds
        
        # Initialize TTL configuration
        if demo_mode:
            # Use short TTL periods for demo (5 minutes)
            if naming_convention == NamingConvention.SNAKE_CASE:
                self.ttl_config = create_demo_snake_case_ttl_configuration("deployment")
            else:
                self.ttl_config = create_demo_ttl_configuration("deployment")
            print(f"[DEMO] Using demo TTL configuration ({TTLConstants.DEMO_TTL_EXPIRE_MINUTES} minutes)")
        else:
            # Use production TTL periods (30 days)
            if naming_convention == NamingConvention.SNAKE_CASE:
                self.ttl_config = create_snake_case_ttl_configuration("deployment", expire_after_days=DEFAULT_TTL_DAYS)
            else:
                self.ttl_config = create_ttl_configuration("deployment", expire_after_days=DEFAULT_TTL_DAYS)
            print(f"[PRODUCTION] Using production TTL configuration (30 days)")
        
        self.ttl_manager = TTLManager(self.ttl_config)
        
    def connect_to_cluster(self) -> bool:
        """Connect to ArangoDB Oasis cluster."""
        try:
            print(f"[LINK] Connecting to ArangoDB Oasis cluster...")
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
            
            # Connect to target database or create it if it doesn't exist
            if self.sys_db.has_database(self.creds.database_name):
                self.database = self.client.db(self.creds.database_name, **CredentialsManager.get_database_params())
                print(f"[DONE] Connected to existing database: {self.creds.database_name}")
                return True
            else:
                print(f"[INFO] Database '{self.creds.database_name}' not found - creating it...")
                try:
                    # Create the database
                    self.sys_db.create_database(self.creds.database_name)
                    self.database = self.client.db(self.creds.database_name, **CredentialsManager.get_database_params())
                    print(f"[DONE] Created and connected to database: {self.creds.database_name}")
                    return True
                except Exception as create_error:
                    print(f"[ERROR] Failed to create database '{self.creds.database_name}': {create_error}")
                    return False
                
        except Exception as e:
            print(f"[ERROR] Connection failed: {str(e)}")
            return False
    
    def drop_and_recreate_database(self) -> bool:
        """Drop existing database and recreate with refactored structure."""
        try:
            print(f"\n[DELETE]  Dropping existing database: {self.creds.database_name}")
            
            # Drop database if it exists
            if self.sys_db.has_database(self.creds.database_name):
                self.sys_db.delete_database(self.creds.database_name)
                print(f"   Dropped: {self.creds.database_name}")
            
            # Create fresh database
            self.sys_db.create_database(self.creds.database_name)
            self.database = self.client.db(self.creds.database_name, **CredentialsManager.get_database_params())
            print(f"[DONE] Created fresh database: {self.creds.database_name}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Error recreating database: {str(e)}")
            return False
    
    def create_refactored_collections(self) -> bool:
        """Create satellite collections only - SmartGraph collections are auto-created by SmartGraph."""
        try:
            convention_name = "camelCase" if self.naming_convention == NamingConvention.CAMEL_CASE else "snake_case"
            print(f"\n[INFO] Creating satellite collections with {convention_name} naming...")

            # Only create satellite collections - SmartGraph will auto-create its own collections
            satellite_collections = [
                {"name": self.app_config.get_collection_name("classes"), "type": "vertex"}
            ]

            print(f"   Creating satellite collections for shared taxonomy...")
            for collection_config in satellite_collections:
                name = collection_config["name"]
                is_edge = collection_config["type"] == "edge"

                if not self.database.has_collection(name):
                    # Create satellite collection (replicated to all servers)
                    self.database.create_collection(
                        name=name,
                        edge=is_edge,
                        replication_factor="satellite"  # This makes it a satellite collection
                    )
                    print(f"   [DONE] Created satellite {collection_config['type']} collection: {name}")
                else:
                    print(f"   [INFO] Satellite collection '{name}' already exists")

            print(f"[DONE] Satellite collections created (SmartGraph will auto-create its collections)")
            return True

        except Exception as e:
            print(f"[ERROR] Error creating satellite collections: {str(e)}")
            return False
    
    def create_refactored_indexes(self) -> bool:
        """Create indexes optimized for time travel refactored structure."""
        try:
            print(f"\n[ANALYSIS] Creating time travel refactored indexes...")
            
            # Refactored index configurations
            index_configs = [
                # NOTE: _key fields already have automatic primary indexes, so no hash indexes needed
                
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
                    "collection": "hasVersion",
                    "type": "persistent",
                    "fields": ["_from", "_toType"],
                    "name": "idx_version_from_totype"
                },
                {
                    "collection": "hasVersion",
                    "type": "persistent",
                    "fields": ["_to", "_fromType"],
                    "name": "idx_version_to_fromtype"
                },
                
                # NOTE: Redundant persistent temporal indexes removed - MDI-prefixed indexes below provide superior performance
                
                # Multi-dimensional indexes (MDI-prefixed) for optimal temporal range queries
                {
                    "collection": "Device",
                    "type": "mdi",
                    "fields": ["created", "expired"],
                    "fieldValueTypes": "double",
                    "prefixFields": ["created"],
                    "unique": False,
                    "sparse": False,
                    "name": "idx_device_mdi_temporal"
                },
                {
                    "collection": "Software",
                    "type": "mdi",
                    "fields": ["created", "expired"],
                    "fieldValueTypes": "double",
                    "prefixFields": ["created"],
                    "unique": False,
                    "sparse": False,
                    "name": "idx_software_mdi_temporal"
                },
                {
                    "collection": "hasVersion",
                    "type": "mdi",
                    "fields": ["created", "expired"],
                    "fieldValueTypes": "double",
                    "prefixFields": ["created"],
                    "unique": False,
                    "sparse": False,
                    "name": "idx_version_mdi_temporal"
                }
                # NOTE: Redundant idx_version_temporal removed - idx_version_mdi_temporal provides superior performance
            ]
            
            # Add TTL indexes for historical document aging
            ttl_specs = self.ttl_manager.get_arango_index_specs()
            for ttl_spec in ttl_specs:
                # Extract collection name from TTL spec name (format: ttl_CollectionName_ttlExpireAt)
                spec_parts = ttl_spec["name"].split("_")
                if len(spec_parts) >= 3:
                    base_collection_name = spec_parts[1]  # Get the collection name part (e.g., "Device")
                    
                    # Map PascalCase collection names to logical names for config lookup
                    logical_name_mapping = {
                        "Device": "devices",
                        "Software": "software", 
                        "Location": "locations",
                        "DeviceProxyIn": "device_ins",
                        "DeviceProxyOut": "device_outs",
                        "SoftwareProxyIn": "software_ins",
                        "SoftwareProxyOut": "software_outs",
                        "hasConnection": "connections",
                        "hasLocation": "has_locations",
                        "hasDeviceSoftware": "has_device_software",
                        "hasVersion": "versions"
                    }
                    
                    logical_name = logical_name_mapping.get(base_collection_name)
                    if logical_name:
                        collection_name = self.app_config.get_collection_name(logical_name)
                        if collection_name:
                            index_configs.append({
                                "collection": collection_name,
                                "type": "ttl",
                                "fields": ttl_spec["fields"],
                                "name": ttl_spec["name"],
                                "expireAfter": ttl_spec["expireAfter"],
                                "sparse": ttl_spec["sparse"],
                                "selectivityEstimate": ttl_spec["selectivityEstimate"]
                            })
            
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
                        print(f"   [DONE] Created persistent index: {index_config['name']}")
                        
                    elif index_config["type"] == "hash":
                        collection.add_index({
                            'type': 'hash',
                            'fields': index_config["fields"],
                            'name': index_config.get("name")
                        })
                        print(f"   [DONE] Created hash index: {index_config['name']}")
                    
                    elif index_config["type"] == "ttl":
                        # Drop existing TTL index if it exists (to ensure correct expireAfter value)
                        try:
                            existing_indexes = collection.indexes()
                            for existing_idx in existing_indexes:
                                if existing_idx.get('name') == index_config.get("name"):
                                    collection.delete_index(existing_idx['id'])
                                    print(f"   [TTL] Dropped existing TTL index: {index_config['name']}")
                                    break
                        except Exception as e:
                            print(f"   [INFO] No existing TTL index to drop: {e}")
                        
                        # Create new TTL index with correct configuration
                        collection.add_index({
                            'type': 'ttl',
                            'fields': index_config["fields"],
                            'name': index_config.get("name"),
                            'expireAfter': index_config["expireAfter"],
                            'sparse': index_config.get("sparse", True),
                            'selectivityEstimate': index_config.get("selectivityEstimate", 0.1)
                        })
                        expire_minutes = index_config["expireAfter"] / 60 if index_config["expireAfter"] > 0 else 0
                        print(f"   [TTL] Created TTL index: {index_config['name']} (expire after {expire_minutes} minutes)")
                    
                    elif index_config["type"] == "mdi":
                        collection.add_index({
                            'type': 'mdi-prefixed',
                            'fields': index_config["fields"],
                            'name': index_config.get("name"),
                            'fieldValueTypes': index_config.get("fieldValueTypes", "double"),
                            'prefixFields': index_config.get("prefixFields", [index_config["fields"][0]]),  # Use first field as prefix
                            'unique': index_config.get("unique", False),
                            'sparse': index_config.get("sparse", False)
                        })
                        field_names = ", ".join(index_config["fields"])
                        prefix_fields = ", ".join(index_config.get("prefixFields", [index_config["fields"][0]]))
                        print(f"   [MDI] Created MDI-prefixed multi-dimensional index: {index_config['name']} on [{field_names}] with prefix [{prefix_fields}]")
                    
                    else:
                        print(f"   [SKIP] Unknown index type: {index_config['type']}")
                else:
                    print(f"   [SKIP] Collection not found: {collection_name}")
            
            print(f"[DONE] Time travel refactored indexes created (including TTL)")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error creating indexes: {str(e)}")
            return False
    
    def load_refactored_data(self) -> bool:
        """Load time travel refactored tenant data into collections."""
        try:
            print(f"\n[DATA] Loading time travel refactored data...")
            
            # Find tenant directories with refactored data
            data_dir = Path("data")
            tenant_dirs = [d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("tenant_")]
            
            if not tenant_dirs:
                print(f"[ERROR] No tenant data directories found in {data_dir}")
                return False
            
            # Time travel refactored file to collection mappings - use configuration manager
            file_mappings = {
                self.app_config.get_file_name("devices"): self.app_config.get_collection_name("devices"),
                self.app_config.get_file_name("device_ins"): self.app_config.get_collection_name("device_ins"),
                self.app_config.get_file_name("device_outs"): self.app_config.get_collection_name("device_outs"),
                self.app_config.get_file_name("locations"): self.app_config.get_collection_name("locations"),
                self.app_config.get_file_name("software"): self.app_config.get_collection_name("software"),
                self.app_config.get_file_name("software_ins"): self.app_config.get_collection_name("software_ins"),
                self.app_config.get_file_name("software_outs"): self.app_config.get_collection_name("software_outs"),
                self.app_config.get_file_name("classes"): self.app_config.get_collection_name("classes"),  # TAXONOMY
                self.app_config.get_file_name("connections"): self.app_config.get_collection_name("connections"),
                self.app_config.get_file_name("has_locations"): self.app_config.get_collection_name("has_locations"),
                self.app_config.get_file_name("has_device_software"): self.app_config.get_collection_name("has_device_software"),
                self.app_config.get_file_name("versions"): self.app_config.get_collection_name("versions"),  # UNIFIED
                self.app_config.get_file_name("types"): self.app_config.get_collection_name("types"),  # TAXONOMY
                self.app_config.get_file_name("subclass_of"): self.app_config.get_collection_name("subclass_of")  # TAXONOMY
            }
            
            total_loaded = 0
            
            for tenant_dir in tenant_dirs:
                tenant_id = tenant_dir.name.replace("tenant_", "")
                print(f"\n    Loading tenant: {tenant_id}")
                
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
                            print(f"      [DONE] {collection_name}: {doc_count} documents")
                        else:
                            print(f"      [INFO] {collection_name}: empty file")
                    else:
                        if filename in ["SoftwareProxyIn.json", "SoftwareProxyOut.json", "hasDeviceSoftware.json"]:
                            print(f"      [WARNING]  {filename}: NEW collection - file not found (expected for old data)")
                        else:
                            print(f"      [WARNING]  {filename}: file not found")
                
                print(f"   [DATA] Tenant {tenant_id}: {tenant_total} documents loaded")
            
            print(f"\n[DONE] Total documents loaded: {total_loaded}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error loading data: {str(e)}")
            return False
    
    def create_refactored_named_graphs(self) -> bool:
        """Create a single unified SmartGraph for all tenants with proper smartGraphAttribute."""
        try:
            print(f"\n[GRAPH] Creating unified SmartGraph for multi-tenant isolation...")
            
            # Single SmartGraph name for all tenants
            smartgraph_name = "network_assets_smartgraph"
            
            # Check if SmartGraph already exists
            if self.database.has_graph(smartgraph_name):
                print(f"   [INFO] SmartGraph '{smartgraph_name}' already exists")
                return True
            
            # Define edge definitions for the unified SmartGraph
            # Includes edges to satellite collections (SmartGraph → Satellite pattern)
            edge_definitions = [
                {
                    "edge_collection": self.app_config.get_collection_name("connections"),
                    "from_vertex_collections": [self.app_config.get_collection_name("devices")],
                    "to_vertex_collections": [self.app_config.get_collection_name("devices")]
                },
                {
                    "edge_collection": self.app_config.get_collection_name("has_locations"),
                    "from_vertex_collections": [self.app_config.get_collection_name("devices")],
                    "to_vertex_collections": [self.app_config.get_collection_name("locations")]
                },
                {
                    "edge_collection": self.app_config.get_collection_name("has_device_software"),
                    "from_vertex_collections": [self.app_config.get_collection_name("devices")],
                    "to_vertex_collections": [self.app_config.get_collection_name("software")]
                },
                {
                    "edge_collection": self.app_config.get_collection_name("versions"),
                    "from_vertex_collections": [
                        self.app_config.get_collection_name("device_ins"),
                        self.app_config.get_collection_name("devices"),
                        self.app_config.get_collection_name("software_ins"),
                        self.app_config.get_collection_name("software")
                    ],
                    "to_vertex_collections": [
                        self.app_config.get_collection_name("devices"),
                        self.app_config.get_collection_name("device_outs"),
                        self.app_config.get_collection_name("software"),
                        self.app_config.get_collection_name("software_outs")
                    ]
                },
                {
                    "edge_collection": self.app_config.get_collection_name("types"),
                    "from_vertex_collections": [
                        self.app_config.get_collection_name("devices"),
                        self.app_config.get_collection_name("software")
                    ],
                    "to_vertex_collections": [
                        self.app_config.get_collection_name("classes")
                    ]
                },
                {
                    "edge_collection": self.app_config.get_collection_name("has_alerts"),
                    "from_vertex_collections": [
                        self.app_config.get_collection_name("device_outs"),
                        self.app_config.get_collection_name("software_outs")
                    ],
                    "to_vertex_collections": [
                        self.app_config.get_collection_name("alerts")
                    ]
                }
            ]
            
            # Note: type edges ARE part of SmartGraph, connecting to Satellite Class collection
            # This follows ArangoDB's SmartGraph → Satellite pattern for optimal performance
            
            try:
                # Create the unified SmartGraph with tenantId as smartGraphAttribute
                graph = self.database.create_graph(
                    name=smartgraph_name,
                    edge_definitions=edge_definitions,
                    smart=True,
                    smart_field="tenantId"  # This enables tenant-based sharding
                )
                
                print(f"   [DONE] Created unified SmartGraph: {smartgraph_name}")
                print(f"          Smart attribute: tenantId")
                print(f"          Tenant isolation: Automatic via smartGraphAttribute")
                
                # Create satellite graph for taxonomy (shared across all tenants)
                satellite_graph_name = "taxonomy_satellite_graph"
                if not self.database.has_graph(satellite_graph_name):
                    satellite_edge_definitions = [
                        {
                            "edge_collection": self.app_config.get_collection_name("subclass_of"),
                            "from_vertex_collections": [self.app_config.get_collection_name("classes")],
                            "to_vertex_collections": [self.app_config.get_collection_name("classes")]
                        }
                    ]
                    
                    try:
                        satellite_graph = self.database.create_graph(
                            name=satellite_graph_name,
                            edge_definitions=satellite_edge_definitions
                            # Note: satellite=True parameter may need different syntax in this driver
                        )
                        print(f"   [DONE] Created satellite graph: {satellite_graph_name}")
                        
                    except Exception as satellite_error:
                        print(f"   [WARNING] Satellite graph creation failed: {satellite_error}")
                        print(f"             Taxonomy will use regular graph")
                else:
                    print(f"   [INFO] Satellite graph '{satellite_graph_name}' already exists")
                
                print(f"[DONE] SmartGraph configuration completed")
                return True
                
            except Exception as graph_error:
                print(f"   [ERROR] Failed to create SmartGraph '{smartgraph_name}': {graph_error}")
                return False
            
        except Exception as e:
            print(f"[ERROR] Error creating unified SmartGraph: {str(e)}")
            return False
    
    def verify_refactored_deployment(self) -> bool:
        """Verify the refactored time travel deployment."""
        try:
            print(f"\n[ANALYSIS] Verifying time travel refactored deployment...")
            
            # Check new Software proxy collections exist
            software_proxy_collections = ["SoftwareProxyIn", "SoftwareProxyOut"]
            for collection_name in software_proxy_collections:
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    count = collection.count()
                    print(f"   [DONE] {collection_name}: {count} documents")
                else:
                    print(f"   [WARNING]  {collection_name}: collection not found (may be from old data)")
            
            # Check Software collection is refactored (no configurationHistory)
            software_collection = self.database.collection("Software")
            sample_software = software_collection.all(limit=1)
            
            for doc in sample_software:
                if "configurationHistory" in doc:
                    print(f"   [ERROR] Software still has configurationHistory: {doc['_key']}")
                    return False
                else:
                    print(f"   [DONE] Software refactored (no configurationHistory): {doc['_key']}")
                
                # Check for flattened configuration
                if "portNumber" in doc and "isEnabled" in doc:
                    print(f"   [DONE] Software has flattened configuration: portNumber={doc.get('portNumber')}, isEnabled={doc.get('isEnabled')}")
                else:
                    print(f"   [WARNING]  Software missing flattened configuration")
            
            # Check unified version collection has both device and software edges
            version_collection = self.database.collection("hasVersion")
            
            # Query for device version edges
            device_version_count = version_collection.find({"_fromType": "DeviceProxyIn"}).count()
            print(f"   [DONE] Device version edges: {device_version_count}")
            
            # Query for software version edges  
            software_version_count = version_collection.find({"_fromType": "SoftwareProxyIn"}).count()
            print(f"   [DONE] Software version edges: {software_version_count}")
            
            # Check hasDeviceSoftware collection
            if self.database.has_collection("hasDeviceSoftware"):
                has_device_software = self.database.collection("hasDeviceSoftware")
                count = has_device_software.count()
                print(f"   [DONE] hasDeviceSoftware: {count} edges")
            else:
                print(f"   [WARNING]  hasDeviceSoftware: collection not found")
            
            # Verify all collections exist with correct names
            expected_collections = [
                "Device", "DeviceProxyIn", "DeviceProxyOut", "Location", "Software",
                "hasConnection", "hasLocation", "hasVersion"
            ]
            
            for collection_name in expected_collections:
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    count = collection.count()
                    print(f"   [DONE] {collection_name}: {count} documents")
                else:
                    print(f"[ERROR] Missing collection: {collection_name}")
                    return False
            
            print(f"[DONE] Time travel refactored deployment verified successfully")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error verifying deployment: {str(e)}")
            return False

    def deploy_all_tenant_data(self) -> bool:
        """Deploy all tenant data to the database with collections and indexes."""
        try:
            print("[DEPLOY] Starting complete deployment with MDI-prefix indexes...")
            
            # Step 1: Connect to cluster
            if not self.connect_to_cluster():
                return False
            
            # Step 2: Create/recreate database
            if not self.drop_and_recreate_database():
                return False
            
            # Step 3: Create collections
            if not self.create_refactored_collections():
                return False
            
            # Step 4: Create indexes (including MDI-prefix indexes)
            if not self.create_refactored_indexes():
                return False
            
            # Step 5: Load tenant data
            if not self.load_refactored_data():
                return False
            
            # Step 6: Create named graphs
            if not self.create_refactored_named_graphs():
                return False
            
            # Step 7: Verify deployment
            if not self.verify_deployment():
                return False
            
            print(f"\n[SUCCESS] Complete deployment with MDI-prefix indexes successful!")
            return True
            
        except Exception as e:
            print(f"[ERROR] Complete deployment failed: {e}")
            return False
    
    def deploy_time_travel_refactored(self) -> bool:
        """Execute complete deployment of time travel refactored data."""
        print("[DEPLOY] Time Travel Refactored Database Deployment")
        print("=" * 60)
        print("[INFO] Deploying:")
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
            print(f"\n-> {step_name}...")
            if not step_function():
                print(f"[ERROR] Failed at step: {step_name}")
                return False
        
        print(f"\n[SUCCESS] Time travel refactored deployment completed successfully!")
        print(f"[DATA] Database: {self.creds.database_name}")
        print(f"[LINK] Endpoint: {self.creds.endpoint}")
        print(f"-> Time Travel Refactoring:")
        print(f"   • Device: Existing pattern maintained")
        print(f"   • Software: NEW time travel pattern implemented")
        print(f"   • Unified version collection for consistent queries")
        print(f"   • Software configurationHistory array eliminated")
        print(f"   • W3C OWL naming conventions")
        
        return True


def main():
    """Main deployment function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy multi-tenant network asset data to ArangoDB")
    parser.add_argument("--naming", choices=["camelCase"], default="camelCase",
                       help="Naming convention for collections and properties (camelCase only)")
    parser.add_argument("--demo-mode", action="store_true",
                       help="Use short TTL periods (5 minutes) for demonstration purposes")
    
    args = parser.parse_args()
    
    # Convert naming argument to enum
    naming_convention = NamingConvention.CAMEL_CASE if args.naming == "camelCase" else NamingConvention.SNAKE_CASE
    
    deployment = TimeTravelRefactoredDeployment(naming_convention, demo_mode=args.demo_mode)
    success = deployment.deploy_time_travel_refactored()
    
    if success:
        print(f"\n[DONE] Database updated with {args.naming} naming convention!")
        sys.exit(0)
    else:
        print(f"\n[ERROR] Deployment failed!")
        sys.exit(1)
