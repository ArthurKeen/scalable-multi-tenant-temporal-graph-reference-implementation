"""
Deploy Multi-Tenant Temporal Graph to ArangoDB Oasis

Deploys the time travel pattern with:
- Device time travel: DeviceProxyIn <-> Device <-> DeviceProxyOut
- Software time travel: SoftwareProxyIn <-> Software <-> SoftwareProxyOut
- Unified 'version' collection for all time travel relationships
- hasDeviceSoftware edge collection
- W3C OWL naming conventions
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any
from arango import ArangoClient

# Import centralized credentials and configuration
from src.config.centralized_credentials import CredentialsManager
from src.config.config_management import get_config, NamingConvention
from src.ttl.ttl_config import (create_ttl_configuration, create_demo_ttl_configuration, TTLManager)
from src.ttl.ttl_constants import DEFAULT_TTL_DAYS, TTLConstants

logger = logging.getLogger(__name__)


class DatabaseDeployment:
    """Deploy multi-tenant temporal graph data to ArangoDB Oasis."""
    
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
            logger.info(f"[DEMO] Using demo TTL configuration ({TTLConstants.DEMO_TTL_EXPIRE_MINUTES} minutes)")
        else:
            # Use production TTL periods (30 days)
            if naming_convention == NamingConvention.SNAKE_CASE:
                self.ttl_config = create_snake_case_ttl_configuration("deployment", expire_after_days=DEFAULT_TTL_DAYS)
            else:
                self.ttl_config = create_ttl_configuration("deployment", expire_after_days=DEFAULT_TTL_DAYS)
            logger.info(f"[PRODUCTION] Using production TTL configuration (30 days)")
        
        self.ttl_manager = TTLManager(self.ttl_config)
        
    def connect_to_cluster(self) -> bool:
        """Connect to ArangoDB Oasis cluster."""
        try:
            logger.info(f"[LINK] Connecting to ArangoDB Oasis cluster...")
            logger.info(f"   Endpoint: {self.creds.endpoint}")
            
            # Connect to system database
            self.sys_db = self.client.db('_system', **CredentialsManager.get_database_params())
            
            # Test connection
            version_info = self.sys_db.version()
            if isinstance(version_info, dict):
                logger.info(f"   Version: {version_info.get('version', 'Unknown')}")
                logger.info(f"   Server: {version_info.get('server', 'Unknown')}")
            else:
                logger.info(f"   Connected: {version_info}")
            
            # Connect to target database or create it if it doesn't exist
            if self.sys_db.has_database(self.creds.database_name):
                self.database = self.client.db(self.creds.database_name, **CredentialsManager.get_database_params())
                logger.info(f"[DONE] Connected to existing database: {self.creds.database_name}")
                return True
            else:
                logger.info(f"[INFO] Database '{self.creds.database_name}' not found - creating it...")
                try:
                    # Create the database
                    self.sys_db.create_database(self.creds.database_name)
                    self.database = self.client.db(self.creds.database_name, **CredentialsManager.get_database_params())
                    logger.info(f"[DONE] Created and connected to database: {self.creds.database_name}")
                    return True
                except Exception as create_error:
                    logger.error(f"Failed to create database '{self.creds.database_name}': {create_error}")
                    return False
                
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            return False
    
    def drop_and_recreate_database(self) -> bool:
        """Drop existing database and recreate fresh."""
        try:
            logger.info(f"\n[DELETE]  Dropping existing database: {self.creds.database_name}")
            
            # Drop database if it exists
            if self.sys_db.has_database(self.creds.database_name):
                self.sys_db.delete_database(self.creds.database_name)
                logger.info(f"   Dropped: {self.creds.database_name}")
            
            # Create fresh database
            self.sys_db.create_database(self.creds.database_name)
            self.database = self.client.db(self.creds.database_name, **CredentialsManager.get_database_params())
            logger.info(f"[DONE] Created fresh database: {self.creds.database_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error recreating database: {str(e)}")
            return False
    
    def create_collections(self) -> bool:
        """Create satellite collections only - SmartGraph collections are auto-created by SmartGraph."""
        try:
            convention_name = "camelCase" if self.naming_convention == NamingConvention.CAMEL_CASE else "snake_case"
            logger.info(f"\n[INFO] Creating satellite collections with {convention_name} naming...")

            # Only create satellite collections - SmartGraph will auto-create its own collections
            satellite_collections = [
                {"name": self.app_config.get_collection_name("classes"), "type": "vertex"}
            ]

            logger.info(f"   Creating satellite collections for shared taxonomy...")
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
                    logger.info(f"   [DONE] Created satellite {collection_config['type']} collection: {name}")
                else:
                    logger.info(f"   [INFO] Satellite collection '{name}' already exists")

            logger.info(f"[DONE] Satellite collections created (SmartGraph will auto-create its collections)")
            return True

        except Exception as e:
            logger.error(f"Error creating satellite collections: {str(e)}")
            return False
    
    def create_indexes(self) -> bool:
        """Create indexes optimized for temporal queries and graph traversal."""
        try:
            logger.info(f"\n[ANALYSIS] Creating indexes...")

            # All collections that carry temporal created/expired fields
            TEMPORAL_COLLECTIONS = [
                "Device", "Software", "Alert",
                "hasVersion", "hasConnection", "hasLocation",
                "hasDeviceSoftware", "hasAlert",
            ]

            # Index configurations
            index_configs = [
                # Vertex-centric indexes for graph performance
                {"collection": "hasConnection", "type": "persistent",
                 "fields": ["_from", "_toType"], "name": "idx_connections_from_totype"},
                {"collection": "hasConnection", "type": "persistent",
                 "fields": ["_to", "_fromType"], "name": "idx_connections_to_fromtype"},
                {"collection": "hasLocation", "type": "persistent",
                 "fields": ["_from", "_toType"], "name": "idx_locations_from_totype"},
                {"collection": "hasDeviceSoftware", "type": "persistent",
                 "fields": ["_from", "_toType"], "name": "idx_device_software_from_totype"},
                {"collection": "hasDeviceSoftware", "type": "persistent",
                 "fields": ["_to", "_fromType"], "name": "idx_device_software_to_fromtype"},
                {"collection": "hasVersion", "type": "persistent",
                 "fields": ["_from", "_toType"], "name": "idx_version_from_totype"},
                {"collection": "hasVersion", "type": "persistent",
                 "fields": ["_to", "_fromType"], "name": "idx_version_to_fromtype"},
            ]

            # MDI-prefixed indexes on [created, expired] for every temporal collection
            for coll_name in TEMPORAL_COLLECTIONS:
                safe = coll_name[0].lower() + coll_name[1:]
                index_configs.append({
                    "collection": coll_name,
                    "type": "mdi",
                    "fields": ["created", "expired"],
                    "fieldValueTypes": "double",
                    "prefixFields": ["created"],
                    "unique": False,
                    "sparse": False,
                    "name": f"idx_{safe}_mdi_temporal",
                })

            # TTL indexes -- use collection names directly from TTL specs
            ttl_specs = self.ttl_manager.get_arango_index_specs()
            for ttl_spec in ttl_specs:
                parts = ttl_spec["name"].split("_", 2)
                if len(parts) >= 2:
                    collection_name = parts[1]
                    index_configs.append({
                        "collection": collection_name,
                        "type": "ttl",
                        "fields": ttl_spec["fields"],
                        "name": ttl_spec["name"],
                        "expireAfter": ttl_spec["expireAfter"],
                        "sparse": ttl_spec["sparse"],
                        "selectivityEstimate": ttl_spec["selectivityEstimate"],
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
                        logger.info(f"   [DONE] Created persistent index: {index_config['name']}")
                        
                    elif index_config["type"] == "hash":
                        collection.add_index({
                            'type': 'hash',
                            'fields': index_config["fields"],
                            'name': index_config.get("name")
                        })
                        logger.info(f"   [DONE] Created hash index: {index_config['name']}")
                    
                    elif index_config["type"] == "ttl":
                        # Drop existing TTL index if it exists (to ensure correct expireAfter value)
                        try:
                            existing_indexes = collection.indexes()
                            for existing_idx in existing_indexes:
                                if existing_idx.get('name') == index_config.get("name"):
                                    collection.delete_index(existing_idx['id'])
                                    logger.info(f"   [TTL] Dropped existing TTL index: {index_config['name']}")
                                    break
                        except Exception as e:
                            logger.info(f"   [INFO] No existing TTL index to drop: {e}")
                        
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
                        logger.info(f"   [TTL] Created TTL index: {index_config['name']} (expire after {expire_minutes} minutes)")
                    
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
                        logger.info(f"   [MDI] Created MDI-prefixed multi-dimensional index: {index_config['name']} on [{field_names}] with prefix [{prefix_fields}]")
                    
                    else:
                        logger.info(f"   [SKIP] Unknown index type: {index_config['type']}")
                else:
                    logger.info(f"   [SKIP] Collection not found: {collection_name}")
            
            logger.info(f"[DONE] Indexes created (including TTL)")
            return True
            
        except Exception as e:
            logger.error(f"Error creating indexes: {str(e)}")
            return False
    
    def load_data(self) -> bool:
        """Load tenant data into collections."""
        try:
            logger.info(f"\n[DATA] Loading tenant data...")
            
            # Find tenant directories
            data_dir = Path("data")
            tenant_dirs = [d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("tenant_")]
            
            if not tenant_dirs:
                logger.error(f"No tenant data directories found in {data_dir}")
                return False
            
            # File to collection mappings
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
                self.app_config.get_file_name("subclass_of"): self.app_config.get_collection_name("subclass_of"),  # TAXONOMY
                self.app_config.get_file_name("alerts"): self.app_config.get_collection_name("alerts"),
                self.app_config.get_file_name("has_alerts"): self.app_config.get_collection_name("has_alerts"),
            }
            
            total_loaded = 0
            
            for tenant_dir in tenant_dirs:
                tenant_id = tenant_dir.name.replace("tenant_", "")
                logger.info(f"\n    Loading tenant: {tenant_id}")
                
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
                            logger.info(f"      [DONE] {collection_name}: {doc_count} documents")
                        else:
                            logger.info(f"      [INFO] {collection_name}: empty file")
                    else:
                        if filename in ["SoftwareProxyIn.json", "SoftwareProxyOut.json", "hasDeviceSoftware.json"]:
                            logger.warning(f"      {filename}: NEW collection - file not found (expected for old data)")
                        else:
                            logger.warning(f"      {filename}: file not found")
                
                logger.info(f"   [DATA] Tenant {tenant_id}: {tenant_total} documents loaded")
            
            logger.info(f"\n[DONE] Total documents loaded: {total_loaded}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
            return False
    
    def create_named_graphs(self) -> bool:
        """Create a single unified SmartGraph for all tenants with proper smartGraphAttribute."""
        try:
            logger.info(f"\n[GRAPH] Creating unified SmartGraph for multi-tenant isolation...")
            
            # Single SmartGraph name for all tenants
            smartgraph_name = "network_assets_smartgraph"
            
            # Check if SmartGraph already exists
            if self.database.has_graph(smartgraph_name):
                logger.info(f"   [INFO] SmartGraph '{smartgraph_name}' already exists")
                return True
            
            # Define edge definitions for the unified SmartGraph
            # Includes edges to satellite collections (SmartGraph -> Satellite pattern)
            # Edge definitions must match the actual _from/_to collection
            # patterns in the generated data:
            #   hasConnection:     DeviceProxyOut → DeviceProxyIn
            #   hasLocation:       DeviceProxyOut → Location
            #   hasDeviceSoftware: DeviceProxyOut → SoftwareProxyIn
            #   hasVersion:        ProxyIn → Entity → ProxyOut (for both Device and Software)
            #   type:              Device/Software → Class (satellite)
            #   hasAlert:          ProxyOut → Alert
            edge_definitions = [
                {
                    "edge_collection": self.app_config.get_collection_name("connections"),
                    "from_vertex_collections": [self.app_config.get_collection_name("device_outs")],
                    "to_vertex_collections": [self.app_config.get_collection_name("device_ins")]
                },
                {
                    "edge_collection": self.app_config.get_collection_name("has_locations"),
                    "from_vertex_collections": [self.app_config.get_collection_name("device_outs")],
                    "to_vertex_collections": [self.app_config.get_collection_name("locations")]
                },
                {
                    "edge_collection": self.app_config.get_collection_name("has_device_software"),
                    "from_vertex_collections": [self.app_config.get_collection_name("device_outs")],
                    "to_vertex_collections": [self.app_config.get_collection_name("software_ins")]
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
            # This follows ArangoDB's SmartGraph -> Satellite pattern for optimal performance
            
            try:
                # Create the unified SmartGraph with tenantId as smartGraphAttribute
                graph = self.database.create_graph(
                    name=smartgraph_name,
                    edge_definitions=edge_definitions,
                    smart=True,
                    smart_field="tenantId"  # This enables tenant-based sharding
                )
                
                logger.info(f"   [DONE] Created unified SmartGraph: {smartgraph_name}")
                logger.info(f"          Smart attribute: tenantId")
                logger.info(f"          Tenant isolation: Automatic via smartGraphAttribute")
                
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
                        logger.info(f"   [DONE] Created satellite graph: {satellite_graph_name}")
                        
                    except Exception as satellite_error:
                        logger.warning(f"Satellite graph creation failed: {satellite_error}")
                        logger.info(f"             Taxonomy will use regular graph")
                else:
                    logger.info(f"   [INFO] Satellite graph '{satellite_graph_name}' already exists")
                
                logger.info(f"[DONE] SmartGraph configuration completed")
                return True
                
            except Exception as graph_error:
                logger.error(f"Failed to create SmartGraph '{smartgraph_name}': {graph_error}")
                return False
            
        except Exception as e:
            logger.error(f"Error creating unified SmartGraph: {str(e)}")
            return False
    
    def verify_deployment(self) -> bool:
        """Verify the deployment completed correctly."""
        try:
            logger.info(f"\n[ANALYSIS] Verifying deployment...")
            
            # Check new Software proxy collections exist
            software_proxy_collections = ["SoftwareProxyIn", "SoftwareProxyOut"]
            for collection_name in software_proxy_collections:
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    count = collection.count()
                    logger.info(f"   [DONE] {collection_name}: {count} documents")
                else:
                    logger.warning(f"   {collection_name}: collection not found (may be from old data)")
            
            # Check Software collection uses flattened structure (no configurationHistory)
            software_collection = self.database.collection("Software")
            sample_software = software_collection.all(limit=1)
            
            for doc in sample_software:
                if "configurationHistory" in doc:
                    logger.error(f"Software still has configurationHistory: {doc['_key']}")
                    return False
                else:
                    logger.info(f"   [DONE] Software structure valid (no configurationHistory): {doc['_key']}")
                
                # Check for flattened configuration
                if "portNumber" in doc and "isEnabled" in doc:
                    logger.info(f"   [DONE] Software has flattened configuration: portNumber={doc.get('portNumber')}, isEnabled={doc.get('isEnabled')}")
                else:
                    logger.warning(f"   Software missing flattened configuration")
            
            # Check unified version collection has both device and software edges
            version_collection = self.database.collection("hasVersion")
            
            # Query for device version edges
            device_version_count = version_collection.find({"_fromType": "DeviceProxyIn"}).count()
            logger.info(f"   [DONE] Device version edges: {device_version_count}")
            
            # Query for software version edges  
            software_version_count = version_collection.find({"_fromType": "SoftwareProxyIn"}).count()
            logger.info(f"   [DONE] Software version edges: {software_version_count}")
            
            # Check hasDeviceSoftware collection
            if self.database.has_collection("hasDeviceSoftware"):
                has_device_software = self.database.collection("hasDeviceSoftware")
                count = has_device_software.count()
                logger.info(f"   [DONE] hasDeviceSoftware: {count} edges")
            else:
                logger.warning(f"   hasDeviceSoftware: collection not found")
            
            # Verify all collections exist with correct names
            expected_collections = [
                "Device", "DeviceProxyIn", "DeviceProxyOut", "Location", "Software",
                "hasConnection", "hasLocation", "hasVersion"
            ]
            
            for collection_name in expected_collections:
                if self.database.has_collection(collection_name):
                    collection = self.database.collection(collection_name)
                    count = collection.count()
                    logger.info(f"   [DONE] {collection_name}: {count} documents")
                else:
                    logger.error(f"Missing collection: {collection_name}")
                    return False
            
            logger.info(f"[DONE] Deployment verified successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying deployment: {str(e)}")
            return False

    def install_visualizer_assets(self) -> bool:
        """Install Graph Visualizer theme, saved queries, and canvas actions for all graphs."""
        try:
            from scripts.setup.install_visualizer import install_all

            logger.info("\n[VIS] Installing Graph Visualizer customizations...")
            results = install_all(self.database, database_name=self.creds.database_name)
            for r in results:
                graph_id = r["graph_id"]
                if r.get("skipped"):
                    logger.info(f"   [{graph_id}] SKIPPED (graph not found)")
                    continue
                logger.info(f"   [{graph_id}]")
                logger.info(f"     Theme:          {r.get('theme_name', '?')} (isDefault=true)")
                logger.info(f"     Saved queries:  {r.get('query_count', 0)}")
                logger.info(f"     Canvas actions: {r.get('action_count', 0)}")
            return True
        except Exception as e:
            logger.error(f"Visualizer installation failed: {e}")
            return False

    def deploy_all_tenant_data(self) -> bool:
        """Deploy all tenant data to the database with collections and indexes."""
        try:
            logger.info("[DEPLOY] Starting complete deployment with MDI-prefix indexes...")
            
            # Step 1: Connect to cluster
            if not self.connect_to_cluster():
                return False
            
            # Step 2: Create/recreate database
            if not self.drop_and_recreate_database():
                return False
            
            # Step 3: Create satellite collections
            if not self.create_collections():
                return False
            
            # Step 4: Create named graphs (auto-creates SmartGraph vertex/edge collections)
            if not self.create_named_graphs():
                return False
            
            # Step 5: Create indexes (collections now exist from SmartGraph)
            if not self.create_indexes():
                return False
            
            # Step 6: Load tenant data
            if not self.load_data():
                return False
            
            # Step 7: Verify deployment
            if not self.verify_deployment():
                return False
            
            # Step 8: Install visualizer assets
            if not self.install_visualizer_assets():
                return False
            
            logger.info(f"\n[SUCCESS] Complete deployment with MDI-prefix indexes successful!")
            return True
            
        except Exception as e:
            logger.error(f"Complete deployment failed: {e}")
            return False
    
    def deploy(self) -> bool:
        """Execute complete database deployment."""
        logger.info("[DEPLOY] Multi-Tenant Temporal Graph Deployment")
        logger.info("=" * 60)
        logger.info("[INFO] Deploying:")
        logger.info("   - Device time travel: DeviceProxyIn <-> Device <-> DeviceProxyOut")
        logger.info("   - Software time travel: SoftwareProxyIn <-> Software <-> SoftwareProxyOut (NEW)")
        logger.info("   - Unified 'version' collection for all time travel relationships")
        logger.info("   - New hasDeviceSoftware edge collection")
        logger.info("   - Software configurationHistory array removed (flattened)")
        logger.info("")
        
        # SmartGraph creation must precede indexes and data loading because
        # it auto-creates the vertex/edge collections (Device, Software, etc.)
        steps = [
            ("Connect to cluster", self.connect_to_cluster),
            ("Drop and recreate database", self.drop_and_recreate_database),
            ("Create collections", self.create_collections),
            ("Create named graphs", self.create_named_graphs),
            ("Create indexes", self.create_indexes),
            ("Load data", self.load_data),
            ("Verify deployment", self.verify_deployment),
            ("Install visualizer assets", self.install_visualizer_assets),
        ]
        
        for step_name, step_function in steps:
            logger.info(f"\n-> {step_name}...")
            if not step_function():
                logger.error(f"Failed at step: {step_name}")
                return False
        
        logger.info(f"\n[SUCCESS] Deployment completed successfully!")
        logger.info(f"[DATA] Database: {self.creds.database_name}")
        logger.info(f"[LINK] Endpoint: {self.creds.endpoint}")
        logger.info(f"-> Architecture:")
        logger.info(f"   - Device time travel: ProxyIn <-> Device <-> ProxyOut")
        logger.info(f"   - Software time travel: ProxyIn <-> Software <-> ProxyOut")
        logger.info(f"   - Unified version collection for consistent queries")
        logger.info(f"   - W3C OWL naming conventions")
        
        return True


def main():
    """Main deployment function."""
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Deploy multi-tenant network asset data to ArangoDB")
    parser.add_argument("--naming", choices=["camelCase"], default="camelCase",
                       help="Naming convention for collections and properties (camelCase only)")
    parser.add_argument("--demo-mode", action="store_true",
                       help="Use short TTL periods (5 minutes) for demonstration purposes")

    args = parser.parse_args()

    naming_convention = NamingConvention.CAMEL_CASE if args.naming == "camelCase" else NamingConvention.SNAKE_CASE

    deployment = DatabaseDeployment(naming_convention, demo_mode=args.demo_mode)
    success = deployment.deploy()

    if success:
        print(f"\n[DONE] Database updated with {args.naming} naming convention!")
        sys.exit(0)
    else:
        print("\nDeployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
