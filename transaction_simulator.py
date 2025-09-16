"""
Transaction Simulation Infrastructure for TTL Time Travel Demo

Simulates real-world configuration changes that:
1. Convert current configs to historical (set real expired timestamp)
2. Create new current configs (expired = sys.maxsize)
3. Demonstrate TTL aging of historical data
4. Maintain time travel query compatibility
"""

import sys
import json
import datetime
import random
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from arango import ArangoClient

# Import project modules
from centralized_credentials import CredentialsManager
from database_utilities import QueryExecutor
from config_management import get_config, NamingConvention
from ttl_config import TTLManager, create_ttl_configuration, create_snake_case_ttl_configuration
from ttl_constants import TTLConstants, TTLMessages, TTLUtilities, NEVER_EXPIRES, DEFAULT_TTL_DAYS
from data_generation_utils import KeyGenerator, RandomDataGenerator
from data_generation_config import NetworkConfig, DataGenerationLimits


@dataclass
class ConfigurationChange:
    """Represents a simulated configuration change."""
    entity_type: str  # "device" or "software"
    entity_key: str
    proxy_key: str
    change_type: str  # "update", "patch", "major_update"
    old_config: Dict[str, Any]
    new_config: Dict[str, Any]
    timestamp: datetime.datetime
    change_description: str


class TransactionSimulator:
    """Simulates realistic configuration change transactions."""
    
    def __init__(self, naming_convention: NamingConvention = NamingConvention.CAMEL_CASE, show_queries: bool = False):
        self.naming_convention = naming_convention
        self.app_config = get_config("production", naming_convention)
        self.show_queries = show_queries
        
        # Database connection
        creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=creds.endpoint)
        self.database = None
        self.creds = creds
        
        # TTL configuration
        if naming_convention == NamingConvention.SNAKE_CASE:
            self.ttl_config = create_snake_case_ttl_configuration("simulator", expire_after_days=DEFAULT_TTL_DAYS)
        else:
            self.ttl_config = create_ttl_configuration("simulator", expire_after_days=DEFAULT_TTL_DAYS)
        self.ttl_manager = TTLManager(self.ttl_config)
        
        # Data generation utilities
        self.network_config = NetworkConfig()
        self.limits = DataGenerationLimits()
        self.random_gen = RandomDataGenerator(self.network_config, self.limits)
        
        # Track simulated changes
        self.simulated_changes: List[ConfigurationChange] = []
    
    def connect_to_database(self) -> bool:
        """Connect to the ArangoDB database."""
        try:
            print(f"[CONNECT] Connecting to database for transaction simulation...")
            self.database = self.client.db(
                self.creds.database_name,
                **CredentialsManager.get_database_params()
            )
            
            # Test connection
            collections = self.database.collections()
            print(f"[CONNECT] Connected successfully - {len(collections)} collections found")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to connect to database: {str(e)}")
            return False
    
    def execute_and_display_query(self, query: str, query_name: str, bind_vars: Dict = None) -> List[Dict]:
        """Execute a query and display it with results if show_queries is enabled."""
        if self.show_queries:
            print(f"\n[QUERY] {query_name}:")
            print(f"   AQL: {query}")
            if bind_vars:
                print(f"   Variables: {bind_vars}")
        
        try:
            cursor = self.database.aql.execute(query, bind_vars=bind_vars)
            results = list(cursor)
            
            if self.show_queries:
                print(f"   Results: {len(results)} documents returned")
                if results and len(results) <= 3:  # Show sample results for small result sets
                    for i, result in enumerate(results[:3]):
                        if isinstance(result, dict):
                            # Show key fields only
                            sample = {k: v for k, v in result.items() if k in ['_key', '_id', 'name', 'type', 'created', 'expired']}
                            print(f"   Sample {i+1}: {sample}")
                elif results:
                    print(f"   (Large result set - showing count only)")
                print()
            
            return results
        except Exception as e:
            if self.show_queries:
                print(f"   ERROR: {e}")
                print()
            raise e
    
    def find_current_configurations(self, entity_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find current configurations for simulation."""
        try:
            collection_name = self.app_config.get_collection_name(entity_type)
            if not collection_name:
                return []
            
            # Query for current configurations (expired = NEVER_EXPIRES)
            aql = f"""
            FOR doc IN {collection_name}
                FILTER doc.expired == {NEVER_EXPIRES}
                LIMIT {limit}
                RETURN doc
            """
            
            results = self.execute_and_display_query(
                aql, 
                f"Find Current {entity_type.title()} Configurations"
            )
            return results
            
        except Exception as e:
            print(f"[ERROR] Failed to find current {entity_type} configurations: {str(e)}")
            return []
    
    def simulate_device_configuration_change(self, current_device: Dict[str, Any]) -> Optional[ConfigurationChange]:
        """Simulate a realistic device configuration change."""
        try:
            # Generate new configuration based on current
            new_config = current_device.copy()
            change_type = random.choice(["update", "patch", "major_update"])
            timestamp = datetime.datetime.now()
            
            # Get simulation ranges from constants
            ranges = TTLConstants()
            
            # Apply realistic changes based on type
            if change_type == "update":
                # Minor configuration update
                if "hostName" in new_config:
                    base_name = new_config["hostName"].split("-")[0]
                    version_num = random.randint(ranges.DEVICE_VERSION_MINOR_MIN, ranges.DEVICE_VERSION_MINOR_MAX)
                    new_config["hostName"] = f"{base_name}-v{version_num}"
                change_description = "Hostname update for maintenance"
                
            elif change_type == "patch":
                # Security patch or minor version update
                if "version" in new_config:
                    version_parts = new_config["version"].split(".")
                    if len(version_parts) >= 3:
                        version_parts[2] = str(int(version_parts[2]) + 1)
                        new_config["version"] = ".".join(version_parts)
                change_description = "Security patch applied"
                
            elif change_type == "major_update":
                # Major configuration overhaul
                if "hostName" in new_config:
                    tenant_id = new_config["_key"].split("_")[0]
                    new_config["hostName"] = self.random_gen.generate_random_hostname(tenant_id)
                if "version" in new_config:
                    major = random.randint(ranges.DEVICE_VERSION_MAJOR_MIN, ranges.DEVICE_VERSION_MAJOR_MAX)
                    minor = random.randint(0, 9)
                    new_config["version"] = f"{major}.{minor}.0"
                change_description = "Major system upgrade"
            
            # Update timestamps
            new_config["created"] = timestamp.timestamp()
            new_config["expired"] = NEVER_EXPIRES  # New current configuration
            
            # Generate new key for the new configuration
            key_parts = current_device["_key"].split("_")
            if len(key_parts) >= 2:
                tenant_id = key_parts[0]
                entity_part = key_parts[1]  # e.g., "device1-0"
                # Use microseconds to ensure uniqueness
                unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                new_key = f"{tenant_id}_{entity_part}_{unique_suffix}"
                new_config["_key"] = new_key
            
            return ConfigurationChange(
                entity_type="device",
                entity_key=current_device["_key"],
                proxy_key=f"{current_device['_key']}_proxy",  # Approximate proxy key
                change_type=change_type,
                old_config=current_device,
                new_config=new_config,
                timestamp=timestamp,
                change_description=change_description
            )
            
        except Exception as e:
            print(f"[ERROR] Failed to simulate device configuration change: {str(e)}")
            return None
    
    def simulate_software_configuration_change(self, current_software: Dict[str, Any]) -> Optional[ConfigurationChange]:
        """Simulate a realistic software configuration change."""
        try:
            new_config = current_software.copy()
            change_type = random.choice(["update", "patch", "major_update"])
            timestamp = datetime.datetime.now()
            
            # Get simulation ranges from constants
            ranges = TTLConstants()
            
            # Apply realistic changes
            if change_type == "update":
                # Port or configuration update
                if "portNumber" in new_config:
                    new_config["portNumber"] = random.randint(ranges.SOFTWARE_PORT_UPDATE_MIN, ranges.SOFTWARE_PORT_UPDATE_MAX)
                change_description = "Port configuration update"
                
            elif change_type == "patch":
                # Enable/disable or minor setting change
                if "isEnabled" in new_config:
                    new_config["isEnabled"] = not new_config["isEnabled"]
                change_description = "Service enable/disable toggle"
                
            elif change_type == "major_update":
                # Complete software reconfiguration
                if "portNumber" in new_config:
                    new_config["portNumber"] = random.randint(ranges.SOFTWARE_PORT_MAJOR_MIN, ranges.SOFTWARE_PORT_MAJOR_MAX)
                if "isEnabled" in new_config:
                    new_config["isEnabled"] = True
                change_description = "Major software reconfiguration"
            
            # Update timestamps
            new_config["created"] = timestamp.timestamp()
            new_config["expired"] = NEVER_EXPIRES  # New current configuration
            
            # Generate new key
            key_parts = current_software["_key"].split("_")
            if len(key_parts) >= 2:
                tenant_id = key_parts[0]
                entity_part = key_parts[1]  # e.g., "software3-0"
                # Use microseconds to ensure uniqueness
                unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                new_key = f"{tenant_id}_{entity_part}_{unique_suffix}"
                new_config["_key"] = new_key
            
            return ConfigurationChange(
                entity_type="software",
                entity_key=current_software["_key"],
                proxy_key=f"{current_software['_key']}_proxy",
                change_type=change_type,
                old_config=current_software,
                new_config=new_config,
                timestamp=timestamp,
                change_description=change_description
            )
            
        except Exception as e:
            print(f"[ERROR] Failed to simulate software configuration change: {str(e)}")
            return None
    
    def execute_configuration_change(self, change: ConfigurationChange) -> bool:
        """Execute a configuration change transaction."""
        try:
            collection_name = self.app_config.get_collection_name(change.entity_type)
            if not collection_name:
                return False
            
            collection = self.database.collection(collection_name)
            
            # Step 1: Update current configuration to historical (set expired timestamp and TTL)
            old_config = change.old_config.copy()
            expired_timestamp = change.timestamp.timestamp()
            old_config["expired"] = expired_timestamp  # For time travel queries
            old_config["ttlExpireAt"] = expired_timestamp + TTLConstants.DEFAULT_TTL_EXPIRE_SECONDS  # TTL deletion timestamp
            
            collection.update(old_config)
            print(f"   [HISTORICAL] Converted {change.entity_key} to historical (expired={old_config['expired']}, ttlExpireAt={old_config['ttlExpireAt']})")
            
            # Step 2: Insert new current configuration (no TTL field for current configs)
            new_config = change.new_config.copy()
            # Ensure current configurations don't have ttlExpireAt field
            if "ttlExpireAt" in new_config:
                del new_config["ttlExpireAt"]
            
            collection.insert(new_config)
            print(f"   [CURRENT] Created new current config {new_config['_key']} (expired={NEVER_EXPIRES}, no TTL)")
            
            # Step 3: Update version edges if they exist
            self._update_version_edges(change)
            
            self.simulated_changes.append(change)
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to execute configuration change: {str(e)}")
            return False
    
    def _update_version_edges(self, change: ConfigurationChange):
        """Update version edges for the configuration change."""
        try:
            version_collection_name = self.app_config.get_collection_name("versions")
            if not version_collection_name:
                return
            
            version_collection = self.database.collection(version_collection_name)
            
            # Find existing version edges for this entity
            aql = f"""
            FOR edge IN {version_collection_name}
                FILTER edge._to LIKE "{change.entity_key}%"
                RETURN edge
            """
            
            cursor = self.database.aql.execute(aql)
            existing_edges = list(cursor)
            
            # Update existing edges to historical
            for edge in existing_edges:
                edge["expired"] = change.timestamp.timestamp()
                version_collection.update(edge)
            
            # Create new version edges for the new configuration
            # This is simplified - in a real implementation, you'd need to find the correct proxy keys
            print(f"   [VERSION] Updated {len(existing_edges)} version edges")
            
        except Exception as e:
            print(f"[WARNING] Failed to update version edges: {str(e)}")
    
    def run_simulation_batch(self, device_count: int = 3, software_count: int = 3) -> Dict[str, Any]:
        """Run a batch of configuration change simulations."""
        print(f"\n[SIMULATION] Starting transaction simulation batch")
        print(f"   Target: {device_count} device changes, {software_count} software changes")
        
        results = {
            "timestamp": datetime.datetime.now().isoformat(),
            "device_changes": [],
            "software_changes": [],
            "total_changes": 0,
            "success_count": 0,
            "error_count": 0
        }
        
        # Simulate device changes
        current_devices = self.find_current_configurations("Device", device_count)
        print(f"   Found {len(current_devices)} current device configurations")
        
        for device in current_devices[:device_count]:
            change = self.simulate_device_configuration_change(device)
            if change and self.execute_configuration_change(change):
                results["device_changes"].append({
                    "entity_key": change.entity_key,
                    "change_type": change.change_type,
                    "description": change.change_description,
                    "timestamp": change.timestamp.isoformat()
                })
                results["success_count"] += 1
            else:
                results["error_count"] += 1
            results["total_changes"] += 1
        
        # Simulate software changes
        current_software = self.find_current_configurations("Software", software_count)
        print(f"   Found {len(current_software)} current software configurations")
        
        for software in current_software[:software_count]:
            change = self.simulate_software_configuration_change(software)
            if change and self.execute_configuration_change(change):
                results["software_changes"].append({
                    "entity_key": change.entity_key,
                    "change_type": change.change_type,
                    "description": change.change_description,
                    "timestamp": change.timestamp.isoformat()
                })
                results["success_count"] += 1
            else:
                results["error_count"] += 1
            results["total_changes"] += 1
        
        print(f"\n[SIMULATION] Batch completed:")
        print(f"   Total changes: {results['total_changes']}")
        print(f"   Successful: {results['success_count']}")
        print(f"   Errors: {results['error_count']}")
        
        return results
    
    def simulate_device_configuration_changes(self, device_count: int = 3) -> List[ConfigurationChange]:
        """Simulate multiple device configuration changes."""
        try:
            print(f"[SIMULATION] Starting {device_count} device configuration changes...")
            changes = []
            
            # Find current device configurations
            current_devices = self.find_current_configurations("devices", device_count)
            
            for device in current_devices:
                change = self.simulate_device_configuration_change(device)
                if change:
                    if self.execute_configuration_change(change):
                        changes.append(change)
                        print(f"   [CHANGE] {change.change_description}")
                    else:
                        print(f"   [ERROR] Failed to execute change for {device['_key']}")
                else:
                    print(f"   [SKIP] No change generated for {device['_key']}")
            
            return changes
            
        except Exception as e:
            print(f"[ERROR] Failed to simulate device configuration changes: {str(e)}")
            return []
    
    def simulate_software_configuration_changes(self, software_count: int = 3) -> List[ConfigurationChange]:
        """Simulate multiple software configuration changes."""
        try:
            print(f"[SIMULATION] Starting {software_count} software configuration changes...")
            changes = []
            
            # Find current software configurations
            current_software = self.find_current_configurations("software", software_count)
            
            for software in current_software:
                change = self.simulate_software_configuration_change(software)
                if change:
                    if self.execute_configuration_change(change):
                        changes.append(change)
                        print(f"   [CHANGE] {change.change_description}")
                    else:
                        print(f"   [ERROR] Failed to execute change for {software['_key']}")
                else:
                    print(f"   [SKIP] No change generated for {software['_key']}")
            
            return changes
            
        except Exception as e:
            print(f"[ERROR] Failed to simulate software configuration changes: {str(e)}")
            return []
    
    def get_simulation_summary(self) -> Dict[str, Any]:
        """Get summary of all simulated changes."""
        return {
            "total_simulated_changes": len(self.simulated_changes),
            "device_changes": len([c for c in self.simulated_changes if c.entity_type == "device"]),
            "software_changes": len([c for c in self.simulated_changes if c.entity_type == "software"]),
            "change_types": {
                "update": len([c for c in self.simulated_changes if c.change_type == "update"]),
                "patch": len([c for c in self.simulated_changes if c.change_type == "patch"]),
                "major_update": len([c for c in self.simulated_changes if c.change_type == "major_update"])
            },
            "ttl_status": self.ttl_manager.get_ttl_status_summary()
        }


def main():
    """Main function for running transaction simulation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simulate configuration change transactions")
    parser.add_argument("--naming", choices=["camelCase", "snake_case"], default="camelCase",
                       help="Naming convention (default: camelCase)")
    parser.add_argument("--devices", type=int, default=TTLConstants.DEFAULT_DEVICE_SIMULATION_COUNT,
                       help=f"Number of device configuration changes to simulate (default: {TTLConstants.DEFAULT_DEVICE_SIMULATION_COUNT})")
    parser.add_argument("--software", type=int, default=TTLConstants.DEFAULT_SOFTWARE_SIMULATION_COUNT,
                       help=f"Number of software configuration changes to simulate (default: {TTLConstants.DEFAULT_SOFTWARE_SIMULATION_COUNT})")
    
    args = parser.parse_args()
    
    # Convert naming argument to enum
    naming_convention = NamingConvention.CAMEL_CASE if args.naming == "camelCase" else NamingConvention.SNAKE_CASE
    
    # Create and run simulator
    simulator = TransactionSimulator(naming_convention)
    
    if not simulator.connect_to_database():
        print("[ERROR] Failed to connect to database")
        sys.exit(1)
    
    # Run simulation
    results = simulator.run_simulation_batch(args.devices, args.software)
    
    # Save results
    results_path = Path("reports") / f"transaction_simulation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    results_path.parent.mkdir(exist_ok=True)
    
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[RESULTS] Simulation results saved to: {results_path}")
    
    # Print summary
    summary = simulator.get_simulation_summary()
    print(f"\n[SUMMARY] Transaction Simulation Summary:")
    print(f"   Total changes simulated: {summary['total_simulated_changes']}")
    print(f"   Device changes: {summary['device_changes']}")
    print(f"   Software changes: {summary['software_changes']}")
    print(f"   TTL Strategy: {summary['ttl_status']['strategy']}")
    print(f"   TTL Expire After: {summary['ttl_status']['expire_after_days']} days")


if __name__ == "__main__":
    main()
