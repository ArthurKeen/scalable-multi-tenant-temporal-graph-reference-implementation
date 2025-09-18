"""
Scale-Out Manager for Multi-Tenant Network Asset Management

Provides capabilities for:
1. Adding new tenants to existing database
2. Adding database servers to cluster
3. Rebalancing shards across servers
4. Demonstrating horizontal scale-out scenarios

This module enables live demonstration of multi-tenant scale-out capabilities
without disrupting existing tenant operations.
"""

import json
import datetime
import sys
import time
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from arango import ArangoClient
from arango.exceptions import (
    ArangoServerError, DatabaseCreateError, GraphCreateError, 
    CollectionCreateError, ServerConnectionError
)

# Import project modules
from src.config.centralized_credentials import CredentialsManager
from src.config.config_management import get_config, NamingConvention
from src.config.tenant_config import TenantConfig, TenantNamingConvention, SmartGraphDefinition, create_tenant_config
from src.ttl.ttl_constants import TTLConstants, TTLMessages, DEFAULT_TTL_DAYS
from src.data_generation.asset_generator import TimeTravelRefactoredGenerator
from src.database.database_deployment import TimeTravelRefactoredDeployment
from src.database.oasis_cluster_setup import OasisClusterManager


@dataclass
class ScaleOutMetrics:
    """Metrics for tracking scale-out operations."""
    operation_start: datetime.datetime
    operation_end: Optional[datetime.datetime] = None
    tenants_before: int = 0
    tenants_after: int = 0
    documents_before: int = 0
    documents_after: int = 0
    servers_before: int = 0
    servers_after: int = 0
    shards_rebalanced: int = 0
    operation_type: str = ""
    success: bool = False
    
    def get_duration_seconds(self) -> float:
        """Get operation duration in seconds."""
        if self.operation_end:
            return (self.operation_end - self.operation_start).total_seconds()
        return 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of scale-out metrics."""
        return {
            "operation_type": self.operation_type,
            "duration_seconds": self.get_duration_seconds(),
            "tenants_added": self.tenants_after - self.tenants_before,
            "documents_added": self.documents_after - self.documents_before,
            "servers_added": self.servers_after - self.servers_before,
            "shards_rebalanced": self.shards_rebalanced,
            "success": self.success,
            "start_time": self.operation_start.isoformat(),
            "end_time": self.operation_end.isoformat() if self.operation_end else None
        }


class TenantAdditionManager:
    """Manages addition of new tenants to existing database."""
    
    def __init__(self, naming_convention: NamingConvention = NamingConvention.CAMEL_CASE):
        self.naming_convention = naming_convention
        self.app_config = get_config("production", naming_convention)
        
        # Database connection
        creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=creds.endpoint)
        self.database = None
        self.creds = creds
        
        # Cluster manager for SmartGraph operations
        self.cluster_manager = OasisClusterManager()
        
        # Track added tenants
        self.added_tenants: List[TenantConfig] = []
    
    def connect_to_database(self) -> bool:
        """Connect to existing database."""
        try:
            print(f"[CONNECT] Connecting to existing database for tenant addition...")
            self.database = self.client.db(
                self.creds.database_name,
                **CredentialsManager.get_database_params()
            )
            
            # Test connection and get current state
            collections = self.database.collections()
            print(f"[CONNECT] Connected successfully - {len(collections)} collections found")
            
            # Connect cluster manager
            if not self.cluster_manager.connect():
                return False
            
            # Set cluster manager database
            self.cluster_manager.database = self.database
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to connect to database: {str(e)}")
            return False
    
    def get_current_tenants(self) -> List[str]:
        """Get list of current tenant IDs from database."""
        try:
            # Query for existing tenant IDs by looking at smartgraph attributes
            device_collection = self.app_config.get_collection_name("Device")
            if not device_collection or not self.database.has_collection(device_collection):
                return []
            
            collection = self.database.collection(device_collection)
            
            # Get unique tenant attributes (smartgraph partitioning keys)
            aql = f"""
            FOR doc IN {device_collection}
                COLLECT tenant_attr = doc.{self._get_tenant_attribute_pattern()}
                RETURN tenant_attr
            """
            
            cursor = self.database.aql.execute(aql)
            tenant_attrs = list(cursor)
            
            # Extract tenant IDs from tenant attributes
            tenant_ids = []
            for attr in tenant_attrs:
                if attr and isinstance(attr, str):
                    # Extract tenant ID from attribute like "tenant_abc123_attr"
                    if attr.startswith("tenant_") and attr.endswith("_attr"):
                        tenant_id = attr[7:-5]  # Remove "tenant_" and "_attr"
                        tenant_ids.append(tenant_id)
            
            return tenant_ids
            
        except Exception as e:
            print(f"[WARNING] Could not determine current tenants: {str(e)}")
            return []
    
    def _get_tenant_attribute_field(self) -> str:
        """Get the standardized tenant attribute field name."""
        # Now using a consistent tenantId field across all documents
        return "tenantId"
    
    def create_new_tenant(self, tenant_name: str, scale_factor: int = 1, 
                         description: str = "") -> TenantConfig:
        """Create a new tenant configuration."""
        return create_tenant_config(
            tenant_name=tenant_name,
            scale_factor=scale_factor,
            description=description or f"Scale-out tenant: {tenant_name}"
        )
    
    def generate_tenant_data(self, tenant_config: TenantConfig) -> bool:
        """Generate data for a new tenant."""
        try:
            print(f"\n[GENERATE] Generating data for new tenant: {tenant_config.tenant_name}")
            print(f"   Tenant ID: {tenant_config.tenant_id}")
            print(f"   Scale factor: {tenant_config.scale_factor}")
            
            # Create generator for this tenant
            generator = TimeTravelRefactoredGenerator(
                tenant_config, 
                environment="production",
                naming_convention=self.naming_convention
            )
            
            # Generate all data
            result = generator.generate_all_data()
            
            if result:
                data_counts = result.get("data_counts", {})
                total_docs = sum(data_counts.values())
                print(f"   [DONE] Generated {total_docs} documents")
                print(f"   Data directory: {result.get('data_directory', 'Unknown')}")
                return True
            else:
                print(f"   [ERROR] Failed to generate data")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to generate tenant data: {str(e)}")
            return False
    
    def deploy_tenant_to_database(self, tenant_config: TenantConfig) -> bool:
        """Deploy a new tenant's data to the existing database."""
        try:
            print(f"\n[DEPLOY] Deploying tenant to database: {tenant_config.tenant_name}")
            
            # Load tenant data files
            tenant_data_path = self.app_config.paths.get_tenant_data_path(tenant_config.tenant_id)
            if not tenant_data_path.exists():
                print(f"[ERROR] Tenant data directory not found: {tenant_data_path}")
                return False
            
            # Get file mappings for collections
            file_mappings = self._get_file_mappings()
            
            total_loaded = 0
            
            # Load each collection's data
            for filename, collection_name in file_mappings.items():
                file_path = tenant_data_path / filename
                if file_path.exists():
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    if data:
                        collection = self.database.collection(collection_name)
                        result = collection.insert_many(data, overwrite=False)  # Don't overwrite existing
                        
                        doc_count = len(data)
                        total_loaded += doc_count
                        print(f"   [DONE] {collection_name}: {doc_count} documents")
                    else:
                        print(f"   [INFO] {collection_name}: empty file")
                else:
                    print(f"   [WARNING] {filename}: file not found")
            
            print(f"   [TOTAL] Loaded {total_loaded} documents for tenant {tenant_config.tenant_id}")
            
            # Create SmartGraph for tenant
            if self.cluster_manager.create_tenant_smartgraph(tenant_config):
                print(f"   [GRAPH] SmartGraph created for tenant")
            else:
                print(f"   [WARNING] SmartGraph creation failed")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to deploy tenant to database: {str(e)}")
            return False
    
    def _get_file_mappings(self) -> Dict[str, str]:
        """Get mapping of data files to collection names."""
        return {
            "Device.json": self.app_config.get_collection_name("Device"),
            "DeviceProxyIn.json": self.app_config.get_collection_name("DeviceProxyIn"),
            "DeviceProxyOut.json": self.app_config.get_collection_name("DeviceProxyOut"),
            "Software.json": self.app_config.get_collection_name("Software"),
            "SoftwareProxyIn.json": self.app_config.get_collection_name("SoftwareProxyIn"),
            "SoftwareProxyOut.json": self.app_config.get_collection_name("SoftwareProxyOut"),
            "Location.json": self.app_config.get_collection_name("Location"),
            "hasConnection.json": self.app_config.get_collection_name("hasConnection"),
            "hasLocation.json": self.app_config.get_collection_name("hasLocation"),
            "hasDeviceSoftware.json": self.app_config.get_collection_name("hasDeviceSoftware"),
            "hasVersion.json": self.app_config.get_collection_name("hasVersion")
        }
    
    def add_tenant(self, tenant_name: str, scale_factor: int = 1, 
                   description: str = "") -> Tuple[bool, TenantConfig]:
        """Add a complete new tenant to the existing database."""
        try:
            print(f"\n{'='*60}")
            print(f"ADDING NEW TENANT: {tenant_name}")
            print(f"{'='*60}")
            
            # Create tenant configuration
            tenant_config = self.create_new_tenant(tenant_name, scale_factor, description)
            
            # Generate tenant data
            if not self.generate_tenant_data(tenant_config):
                return False, tenant_config
            
            # Deploy to database
            if not self.deploy_tenant_to_database(tenant_config):
                return False, tenant_config
            
            # Track added tenant
            self.added_tenants.append(tenant_config)
            
            print(f"\n[SUCCESS] Tenant '{tenant_name}' added successfully!")
            print(f"   Tenant ID: {tenant_config.tenant_id}")
            print(f"   Scale factor: {tenant_config.scale_factor}")
            print(f"   SmartGraph: tenant_{tenant_config.tenant_id}_network_assets")
            
            return True, tenant_config
            
        except Exception as e:
            print(f"[ERROR] Failed to add tenant: {str(e)}")
            return False, tenant_config
    
    def add_multiple_tenants(self, tenant_specs: List[Dict[str, Any]]) -> List[Tuple[bool, TenantConfig]]:
        """Add multiple tenants in sequence."""
        results = []
        
        print(f"\n{'='*60}")
        print(f"ADDING MULTIPLE TENANTS: {len(tenant_specs)} tenants")
        print(f"{'='*60}")
        
        for i, spec in enumerate(tenant_specs, 1):
            print(f"\n[TENANT {i}/{len(tenant_specs)}]")
            
            success, tenant_config = self.add_tenant(
                tenant_name=spec.get("name", f"Tenant {i}"),
                scale_factor=spec.get("scale_factor", 1),
                description=spec.get("description", "")
            )
            
            results.append((success, tenant_config))
            
            if success:
                print(f"[PROGRESS] {i}/{len(tenant_specs)} tenants added successfully")
            else:
                print(f"[ERROR] Failed to add tenant {i}/{len(tenant_specs)}")
        
        successful = sum(1 for success, _ in results if success)
        print(f"\n[SUMMARY] Added {successful}/{len(tenant_specs)} tenants successfully")
        
        return results
    
    def get_tenant_addition_summary(self) -> Dict[str, Any]:
        """Get summary of tenant addition operations."""
        return {
            "tenants_added": len(self.added_tenants),
            "tenant_details": [
                {
                    "tenant_id": config.tenant_id,
                    "tenant_name": config.tenant_name,
                    "scale_factor": config.scale_factor,
                    "created_at": config.created_at.isoformat(),
                    "description": config.description
                }
                for config in self.added_tenants
            ],
            "naming_convention": self.naming_convention.value,
            "database": self.creds.database_name
        }


class DatabaseServerManager:
    """Manages database server addition and cluster scaling."""
    
    def __init__(self):
        creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=creds.endpoint)
        self.database = None
        self.creds = creds
    
    def connect_to_cluster(self) -> bool:
        """Connect to ArangoDB cluster."""
        try:
            print(f"[CONNECT] Connecting to ArangoDB cluster for server management...")
            
            # Connect to system database for cluster operations
            self.sys_db = self.client.db('_system', **CredentialsManager.get_database_params())
            
            # Connect to target database
            self.database = self.client.db(
                self.creds.database_name,
                **CredentialsManager.get_database_params()
            )
            
            print(f"[CONNECT] Connected to cluster successfully")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to connect to cluster: {str(e)}")
            return False
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """Get current cluster information."""
        try:
            # Note: In ArangoDB Oasis, detailed cluster management is typically
            # handled through the Oasis web interface. This provides basic info.
            
            cluster_info = {
                "timestamp": datetime.datetime.now().isoformat(),
                "database": self.creds.database_name,
                "collections": {},
                "total_documents": 0,
                "server_info": {}
            }
            
            # Get collection information
            collections = self.database.collections()
            for collection in collections:
                if not collection['name'].startswith('_'):  # Skip system collections
                    coll = self.database.collection(collection['name'])
                    count = coll.count()
                    cluster_info["collections"][collection['name']] = {
                        "document_count": count,
                        "type": collection['type']
                    }
                    cluster_info["total_documents"] += count
            
            # Get basic server information
            version_info = self.sys_db.version()
            cluster_info["server_info"] = {
                "version": version_info if isinstance(version_info, str) else version_info.get('version', 'Unknown'),
                "license": version_info.get('license', 'Unknown') if isinstance(version_info, dict) else 'Unknown'
            }
            
            return cluster_info
            
        except Exception as e:
            print(f"[ERROR] Failed to get cluster info: {str(e)}")
            return {"error": str(e)}
    
    def get_scaling_recommendations(self, target_server_count: int = 2) -> Dict[str, Any]:
        """
        Get recommendations for manual server addition.
        
        Note: In ArangoDB Oasis, server addition is performed through
        the web interface. This provides analysis to support manual operations.
        """
        print(f"\n[ANALYZE] Analyzing cluster for manual addition of {target_server_count} database server(s)")
        print(f"[INFO] Server addition is performed manually via ArangoDB Oasis web interface")
        
        # Get current cluster state
        cluster_info = self.get_cluster_info()
        
        recommendations_result = {
            "operation": "server_addition_analysis",
            "target_servers": target_server_count,
            "timestamp": datetime.datetime.now().isoformat(),
            "current_state": cluster_info,
            "manual_steps": [
                "1. Access ArangoDB Oasis web interface",
                "2. Navigate to cluster scaling options",
                "3. Add desired number of servers",
                "4. Monitor automatic shard redistribution",
                "5. Verify cluster health and performance"
            ],
            "expected_benefits": [
                "Increased storage capacity",
                "Improved query performance through parallelization",
                "Better fault tolerance with more replicas",
                "Enhanced horizontal scaling capability"
            ],
            "pre_addition_metrics": {
                "collections": len(cluster_info.get('collections', {})),
                "total_documents": cluster_info.get('total_documents', 0),
                "current_server_info": cluster_info.get('server_info', {})
            }
        }
        
        print(f"[ANALYSIS] Server addition analysis completed")
        print(f"   Target servers to add: {target_server_count}")
        print(f"   Current collections: {len(cluster_info.get('collections', {}))}")
        print(f"   Total documents: {cluster_info.get('total_documents', 0):,}")
        print(f"   Ready for manual server addition via Oasis interface")
        
        return recommendations_result


class ShardRebalancingManager:
    """Manages shard rebalancing across database servers."""
    
    def __init__(self):
        creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=creds.endpoint)
        self.database = None
        self.creds = creds
    
    def connect_to_cluster(self) -> bool:
        """Connect to ArangoDB cluster."""
        try:
            self.database = self.client.db(
                self.creds.database_name,
                **CredentialsManager.get_database_params()
            )
            return True
        except Exception as e:
            print(f"[ERROR] Failed to connect: {str(e)}")
            return False
    
    def get_shard_distribution(self) -> Dict[str, Any]:
        """Get current shard distribution information."""
        try:
            print(f"[ANALYZE] Analyzing current shard distribution...")
            
            collections = self.database.collections()
            shard_info = {
                "timestamp": datetime.datetime.now().isoformat(),
                "database": self.creds.database_name,
                "collections": {},
                "total_shards": 0
            }
            
            for collection in collections:
                if not collection['name'].startswith('_'):  # Skip system collections
                    coll = self.database.collection(collection['name'])
                    
                    # Get collection properties (includes shard information in cluster)
                    properties = coll.properties()
                    
                    shard_info["collections"][collection['name']] = {
                        "type": collection['type'],
                        "document_count": coll.count(),
                        "shard_count": properties.get('numberOfShards', 1),
                        "replication_factor": properties.get('replicationFactor', 1)
                    }
                    
                    shard_info["total_shards"] += properties.get('numberOfShards', 1)
            
            print(f"   [DONE] Analyzed {len(shard_info['collections'])} collections")
            print(f"   Total shards: {shard_info['total_shards']}")
            
            return shard_info
            
        except Exception as e:
            print(f"[ERROR] Failed to get shard distribution: {str(e)}")
            return {"error": str(e)}
    
    def simulate_shard_rebalancing(self) -> Dict[str, Any]:
        """
        Simulate shard rebalancing across servers.
        
        Note: In ArangoDB Oasis, shard rebalancing is typically automatic
        or managed through the web interface.
        """
        print(f"\n[SIMULATE] Simulating shard rebalancing operation")
        
        # Get current shard distribution
        shard_info = self.get_shard_distribution()
        
        if "error" in shard_info:
            return shard_info
        
        # Simulate rebalancing process
        rebalancing_result = {
            "operation": "shard_rebalancing_simulation",
            "timestamp": datetime.datetime.now().isoformat(),
            "current_distribution": shard_info,
            "rebalancing_actions": [
                "Analyze current shard distribution across servers",
                "Identify uneven shard distribution patterns",
                "Calculate optimal shard placement strategy",
                "Move shards to achieve balanced distribution",
                "Update cluster routing information",
                "Verify data consistency after rebalancing"
            ],
            "expected_improvements": [
                "Even distribution of data across all servers",
                "Balanced query load across cluster nodes",
                "Improved overall cluster performance",
                "Better resource utilization"
            ],
            "collections_affected": list(shard_info.get("collections", {}).keys()),
            "total_shards": shard_info.get("total_shards", 0),
            "estimated_duration": "5-15 minutes depending on data size"
        }
        
        print(f"[SIMULATION] Shard rebalancing simulation completed")
        print(f"   Collections to rebalance: {len(rebalancing_result['collections_affected'])}")
        print(f"   Total shards: {rebalancing_result['total_shards']}")
        
        return rebalancing_result
    
    def analyze_shard_distribution(self) -> Dict[str, Any]:
        """Analyze and return detailed shard distribution information."""
        try:
            print(f"\n[ANALYSIS] Analyzing shard distribution and balance...")
            
            # Get base shard information
            shard_info = self.get_shard_distribution()
            
            if "error" in shard_info:
                return shard_info
            
            # Add analysis metrics
            analysis = {
                "timestamp": datetime.datetime.now().isoformat(),
                "database": self.creds.database_name,
                "shard_distribution": shard_info,
                "balance_metrics": {
                    "total_collections": len(shard_info.get("collections", {})),
                    "total_shards": shard_info.get("total_shards", 0),
                    "average_shards_per_collection": 0,
                    "shard_distribution_summary": {}
                },
                "recommendations": []
            }
            
            collections = shard_info.get("collections", {})
            if collections:
                total_shards = sum(coll.get("shard_count", 1) for coll in collections.values())
                analysis["balance_metrics"]["average_shards_per_collection"] = total_shards / len(collections)
                
                # Analyze distribution
                shard_counts = {}
                for coll_name, coll_info in collections.items():
                    shard_count = coll_info.get("shard_count", 1)
                    if shard_count not in shard_counts:
                        shard_counts[shard_count] = 0
                    shard_counts[shard_count] += 1
                
                analysis["balance_metrics"]["shard_distribution_summary"] = shard_counts
                
                # Generate recommendations
                if total_shards > 20:
                    analysis["recommendations"].append("Consider shard rebalancing for large cluster")
                if len(shard_counts) > 3:
                    analysis["recommendations"].append("Uneven shard distribution detected")
                else:
                    analysis["recommendations"].append("Shard distribution appears balanced")
            
            print(f"   [ANALYSIS] Complete - {analysis['balance_metrics']['total_collections']} collections analyzed")
            print(f"   [SHARDS] Total: {analysis['balance_metrics']['total_shards']}")
            
            for rec in analysis["recommendations"]:
                print(f"   [RECOMMENDATION] {rec}")
            
            return analysis
            
        except Exception as e:
            print(f"[ERROR] Failed to analyze shard distribution: {str(e)}")
            return {"error": str(e)}


def main():
    """Main function for testing scale-out capabilities."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-tenant scale-out management")
    parser.add_argument("--operation", choices=["add-tenant", "add-tenants", "server-info", "shard-info"], 
                       default="add-tenant", help="Scale-out operation to perform")
    parser.add_argument("--tenant-name", default="Scale-Out Demo Corp", 
                       help="Name for new tenant")
    parser.add_argument("--scale-factor", type=int, default=1,
                       help="Scale factor for tenant data generation")
    parser.add_argument("--naming", choices=["camelCase", "snake_case"], default="camelCase",
                       help="Naming convention")
    
    args = parser.parse_args()
    
    # Convert naming argument to enum
    naming_convention = NamingConvention.CAMEL_CASE if args.naming == "camelCase" else NamingConvention.SNAKE_CASE
    
    if args.operation == "add-tenant":
        # Add single tenant
        manager = TenantAdditionManager(naming_convention)
        
        if not manager.connect_to_database():
            sys.exit(1)
        
        success, tenant_config = manager.add_tenant(
            args.tenant_name, 
            args.scale_factor
        )
        
        if success:
            print(f"\n[SUCCESS] Tenant addition completed successfully!")
            summary = manager.get_tenant_addition_summary()
            print(f"Summary: {json.dumps(summary, indent=2)}")
        else:
            print(f"\n[ERROR] Tenant addition failed!")
            sys.exit(1)
    
    elif args.operation == "add-tenants":
        # Add multiple tenants
        tenant_specs = [
            {"name": "Retail Chain Corp", "scale_factor": 2, "description": "Large retail chain"},
            {"name": "Manufacturing Inc", "scale_factor": 1, "description": "Manufacturing company"},
            {"name": "Tech Startup", "scale_factor": 1, "description": "Technology startup"}
        ]
        
        manager = TenantAdditionManager(naming_convention)
        
        if not manager.connect_to_database():
            sys.exit(1)
        
        results = manager.add_multiple_tenants(tenant_specs)
        successful = sum(1 for success, _ in results if success)
        
        print(f"\n[FINAL] Added {successful}/{len(tenant_specs)} tenants successfully")
    
    elif args.operation == "server-info":
        # Get server information
        server_manager = DatabaseServerManager()
        
        if not server_manager.connect_to_cluster():
            sys.exit(1)
        
        cluster_info = server_manager.get_cluster_info()
        print(f"\nCluster Information:")
        print(json.dumps(cluster_info, indent=2))
        
        # Get scaling recommendations
        recommendations = server_manager.get_scaling_recommendations(2)
        print(f"\nServer Addition Recommendations:")
        print(json.dumps(recommendations, indent=2))
    
    elif args.operation == "shard-info":
        # Get shard information and simulate rebalancing
        shard_manager = ShardRebalancingManager()
        
        if not shard_manager.connect_to_cluster():
            sys.exit(1)
        
        shard_info = shard_manager.get_shard_distribution()
        print(f"\nShard Distribution:")
        print(json.dumps(shard_info, indent=2))
        
        # Simulate rebalancing
        rebalancing = shard_manager.simulate_shard_rebalancing()
        print(f"\nShard Rebalancing Simulation:")
        print(json.dumps(rebalancing, indent=2))


if __name__ == "__main__":
    main()
