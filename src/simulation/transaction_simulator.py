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
from src.database.database_utilities import DatabaseMixin, QueryExecutor
from src.config.centralized_credentials import CredentialsManager
from src.config.config_management import get_config, NamingConvention
from src.ttl.ttl_config import TTLManager, create_ttl_configuration
from src.ttl.ttl_constants import TTLConstants, TTLMessages, TTLUtilities, NEVER_EXPIRES, DEFAULT_TTL_DAYS
from src.data_generation.data_generation_utils import KeyGenerator, RandomDataGenerator
from src.data_generation.data_generation_config import NetworkConfig, DataGenerationLimits


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


class TransactionSimulator(DatabaseMixin):
    """Simulates realistic configuration change transactions."""
    
    def __init__(self, naming_convention: NamingConvention = NamingConvention.CAMEL_CASE, show_queries: bool = False):
        super().__init__()  # Initialize DatabaseMixin
        self.naming_convention = naming_convention
        self.app_config = get_config("production", naming_convention)
        self.show_queries = show_queries
        
        # TTL configuration - use camelCase only (snake_case support removed)
        self.ttl_config = create_ttl_configuration("simulator", expire_after_days=DEFAULT_TTL_DAYS)
        self.ttl_manager = TTLManager(self.ttl_config)
        
        # Data generation utilities
        self.network_config = NetworkConfig()
        self.limits = DataGenerationLimits()
        self.random_gen = RandomDataGenerator(self.network_config, self.limits)
        
        # Track simulated changes
        self.simulated_changes: List[ConfigurationChange] = []
    
    
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
            
            results = self.execute_aql(aql)
            
            if self.show_queries:
                print(f"[QUERY] Find Current {entity_type.title()} Configurations")
                print(f"[AQL] {aql}")
                print(f"[RESULTS] Found {len(results)} current {entity_type} configurations")
            
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
            
            # Generate new key with proper SmartGraph format (avoiding conflicts)
            original_key = current_device["_key"]  # e.g., "ace9c0fd580b:device1-0"
            
            if ":" in original_key:
                tenant_id, entity_part = original_key.split(":", 1)  # Split on colon for SmartGraph keys
                
                # Extract base entity and find next available version number
                if "-" in entity_part:
                    base_entity, version_str = entity_part.rsplit("-", 1)  # e.g., "device1", "0"
                    try:
                        # Find next available version by checking database for conflicts
                        version_num = int(version_str)
                        max_attempts = 100  # Prevent infinite loops
                        attempts = 0
                        
                        while attempts < max_attempts:
                            new_version = version_num + 1 + attempts
                            new_key = f"{tenant_id}:{base_entity}-{new_version}"
                            
                            # Check if this key already exists in the database
                            if not self.database.collection(self.app_config.get_collection_name("devices")).has(new_key):
                                break
                            attempts += 1
                        else:
                            # Fallback: use timestamp suffix if we can't find available version
                            unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                            new_key = f"{tenant_id}:{base_entity}_{unique_suffix}"
                            
                    except ValueError:
                        # Fallback: use timestamp suffix
                        unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                        new_key = f"{tenant_id}:{entity_part}_{unique_suffix}"
                else:
                    # Fallback: use timestamp suffix  
                    unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                    new_key = f"{tenant_id}:{entity_part}_{unique_suffix}"
            else:
                # Fallback for non-SmartGraph keys
                unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                new_key = f"{original_key}_{unique_suffix}"
            
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
            
            # Generate new key with proper SmartGraph format (avoiding conflicts)
            original_key = current_software["_key"]  # e.g., "ace9c0fd580b:software1-0"
            
            if ":" in original_key:
                tenant_id, entity_part = original_key.split(":", 1)  # Split on colon for SmartGraph keys
                
                # Extract base entity and find next available version number
                if "-" in entity_part:
                    base_entity, version_str = entity_part.rsplit("-", 1)  # e.g., "software1", "0"
                    try:
                        # Find next available version by checking database for conflicts
                        version_num = int(version_str)
                        max_attempts = 100  # Prevent infinite loops
                        attempts = 0
                        
                        while attempts < max_attempts:
                            new_version = version_num + 1 + attempts
                            new_key = f"{tenant_id}:{base_entity}-{new_version}"
                            
                            # Check if this key already exists in the database
                            if not self.database.collection(self.app_config.get_collection_name("software")).has(new_key):
                                break
                            attempts += 1
                        else:
                            # Fallback: use timestamp suffix if we can't find available version
                            unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                            new_key = f"{tenant_id}:{base_entity}_{unique_suffix}"
                            
                    except ValueError:
                        # Fallback: use timestamp suffix
                        unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                        new_key = f"{tenant_id}:{entity_part}_{unique_suffix}"
                else:
                    # Fallback: use timestamp suffix  
                    unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                    new_key = f"{tenant_id}:{entity_part}_{unique_suffix}"
            else:
                # Fallback for non-SmartGraph keys
                unique_suffix = f"sim_{int(timestamp.timestamp())}_{timestamp.microsecond}"
                new_key = f"{original_key}_{unique_suffix}"
            
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
                print(f"[ERROR] No collection name found for entity type: {change.entity_type}")
                return False
            
            collection = self.database.collection(collection_name)
            
            # Step 1: Update current configuration to historical (set expired timestamp and TTL)
            old_config = change.old_config.copy()
            expired_timestamp = change.timestamp.timestamp()
            old_config["expired"] = expired_timestamp  # For time travel queries
            old_config["ttlExpireAt"] = expired_timestamp + TTLConstants.DEMO_TTL_EXPIRE_SECONDS  # TTL deletion timestamp (5 minutes for demo)
            
            collection.update(old_config)
            print(f"   [HISTORICAL] Converted {change.entity_key} to historical (expired={old_config['expired']}, ttlExpireAt={old_config['ttlExpireAt']})")
            
            # Step 2: Insert new current configuration (no TTL field for current configs)
            new_config = change.new_config.copy()
            # Ensure current configurations don't have ttlExpireAt field
            if "ttlExpireAt" in new_config:
                del new_config["ttlExpireAt"]
            
            try:
                insert_result = collection.insert(new_config)
                print(f"   [CURRENT] Created new current config {new_config['_key']} (expired={NEVER_EXPIRES}, no TTL)")
                    
            except Exception as insert_error:
                print(f"[ERROR] Failed to insert new config: {str(insert_error)}")
                return False
            
            # Output full vertex IDs for graph visualization
            old_vertex_id = f"{collection_name}/{change.entity_key}"
            new_vertex_id = f"{collection_name}/{new_config['_key']}"
            ttl_expire_minutes = TTLConstants.DEMO_TTL_EXPIRE_SECONDS // 60
            
            print(f"\n   [GRAPH] GRAPH VISUALIZATION IDs:")
            print(f"   [BEFORE] BEFORE (Historical): {old_vertex_id}")
            print(f"      [TTL] Will be deleted by TTL in {ttl_expire_minutes} minutes")
            print(f"   [AFTER] AFTER (Current): {new_vertex_id}")
            print(f"      [NEVER] Never expires (current configuration)")
            print(f"   [COPY] Copy these IDs to paste into Graph Visualizer:")
            print(f"      Historical: {old_vertex_id}")
            print(f"      Current: {new_vertex_id}")
            print()
            
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
                print(f"   [VERSION] No version collection found, skipping edge updates")
                return
            
            version_collection = self.database.collection(version_collection_name)
            
            # Find existing version edges that reference the old configuration
            aql_find_old_edges = f"""
            FOR edge IN {version_collection_name}
                FILTER edge._to == "{change.old_config['_id']}" OR edge._from == "{change.old_config['_id']}"
                RETURN edge
            """
            
            cursor = self.database.aql.execute(aql_find_old_edges)
            existing_edges = list(cursor)
            
            # Update existing edges to historical
            for edge in existing_edges:
                edge["expired"] = change.timestamp.timestamp()
                version_collection.update(edge)
            
            print(f"   [VERSION] Expired {len(existing_edges)} old version edges")
            
            # For Software entities, create new hasVersion edges to maintain graph connectivity
            if change.entity_type == "software":
                self._create_software_version_edges(change, version_collection)
            elif change.entity_type == "device":
                self._create_device_version_edges(change, version_collection)
            
        except Exception as e:
            print(f"[WARNING] Failed to update version edges: {str(e)}")
    
    def _create_software_version_edges(self, change: ConfigurationChange, version_collection):
        """Create hasVersion edges for new Software configuration."""
        try:
            # Extract base entity name from the old key to find proxy keys
            old_key = change.entity_key
            key_parts = old_key.split("_")
            if len(key_parts) < 2:
                print(f"   [VERSION] Cannot parse entity key format: {old_key}")
                return
            
            tenant_id = key_parts[0]
            entity_base = key_parts[1]  # e.g., "software3-0"
            
            # Remove the "-0" suffix to get the proxy base name
            if "-" in entity_base:
                proxy_base = entity_base.split("-")[0]  # "software3"
            else:
                proxy_base = entity_base
            
            # Find the SoftwareProxyIn and SoftwareProxyOut keys (same key for both)
            proxy_in_key = f"{tenant_id}_{proxy_base}"
            proxy_out_key = f"{tenant_id}_{proxy_base}"
            
            # Verify proxies exist
            proxy_in_collection = self.database.collection("SoftwareProxyIn")
            proxy_out_collection = self.database.collection("SoftwareProxyOut")
            
            proxy_in_exists = proxy_in_collection.has(proxy_in_key)
            proxy_out_exists = proxy_out_collection.has(proxy_out_key)
            
            if not proxy_in_exists or not proxy_out_exists:
                print(f"   [VERSION] Proxy vertices not found: ProxyIn={proxy_in_exists}, ProxyOut={proxy_out_exists}")
                return
            
            # Construct the full document ID (collection/key)
            collection_name = self.app_config.get_collection_name("software")
            new_software_id = f"{collection_name}/{change.new_config['_key']}"
            
            # Create hasVersion edge from SoftwareProxyIn to new Software
            incoming_edge = {
                "_key": f"version_in_{change.new_config['_key']}",
                "_from": f"SoftwareProxyIn/{proxy_in_key}",
                "_to": new_software_id,
                "_fromType": "SoftwareProxyIn",
                "_toType": "Software",
                "created": change.timestamp.timestamp(),
                "expired": NEVER_EXPIRES,
                "tenantId": change.new_config.get("tenantId", tenant_id)
            }
            
            # Create hasVersion edge from new Software to SoftwareProxyOut
            outgoing_edge = {
                "_key": f"version_out_{change.new_config['_key']}",
                "_from": new_software_id,
                "_to": f"SoftwareProxyOut/{proxy_out_key}",
                "_fromType": "Software",
                "_toType": "SoftwareProxyOut",
                "created": change.timestamp.timestamp(),
                "expired": NEVER_EXPIRES,
                "tenantId": change.new_config.get("tenantId", tenant_id)
            }
            
            # Insert the new edges
            version_collection.insert(incoming_edge)
            version_collection.insert(outgoing_edge)
            
            print(f"   [VERSION] Created hasVersion edges: ProxyIn→Software→ProxyOut")
            print(f"            Incoming: {incoming_edge['_key']}")
            print(f"            Outgoing: {outgoing_edge['_key']}")
            
        except Exception as e:
            print(f"   [VERSION] Failed to create software version edges: {str(e)}")
    
    def _create_device_version_edges(self, change: ConfigurationChange, version_collection):
        """Create hasVersion edges for new Device configuration."""
        try:
            # Extract base entity name from the old key to find proxy keys
            old_key = change.entity_key
            key_parts = old_key.split("_")
            if len(key_parts) < 2:
                print(f"   [VERSION] Cannot parse entity key format: {old_key}")
                return
            
            tenant_id = key_parts[0]
            entity_base = key_parts[1]  # e.g., "device1-0"
            
            # Remove the "-0" suffix to get the proxy base name
            if "-" in entity_base:
                proxy_base = entity_base.split("-")[0]  # "device1"
            else:
                proxy_base = entity_base
            
            # Find the DeviceProxyIn and DeviceProxyOut keys (same key for both)
            proxy_in_key = f"{tenant_id}_{proxy_base}"
            proxy_out_key = f"{tenant_id}_{proxy_base}"
            
            # Verify proxies exist
            proxy_in_collection = self.database.collection("DeviceProxyIn")
            proxy_out_collection = self.database.collection("DeviceProxyOut")
            
            proxy_in_exists = proxy_in_collection.has(proxy_in_key)
            proxy_out_exists = proxy_out_collection.has(proxy_out_key)
            
            if not proxy_in_exists or not proxy_out_exists:
                print(f"   [VERSION] Proxy vertices not found: ProxyIn={proxy_in_exists}, ProxyOut={proxy_out_exists}")
                return
            
            # Construct the full document ID (collection/key)
            collection_name = self.app_config.get_collection_name("devices")
            new_device_id = f"{collection_name}/{change.new_config['_key']}"
            
            # Create hasVersion edge from DeviceProxyIn to new Device
            incoming_edge = {
                "_key": f"version_in_{change.new_config['_key']}",
                "_from": f"DeviceProxyIn/{proxy_in_key}",
                "_to": new_device_id,
                "_fromType": "DeviceProxyIn",
                "_toType": "Device",
                "created": change.timestamp.timestamp(),
                "expired": NEVER_EXPIRES,
                "tenantId": change.new_config.get("tenantId", tenant_id)
            }
            
            # Create hasVersion edge from new Device to DeviceProxyOut
            outgoing_edge = {
                "_key": f"version_out_{change.new_config['_key']}",
                "_from": new_device_id,
                "_to": f"DeviceProxyOut/{proxy_out_key}",
                "_fromType": "Device",
                "_toType": "DeviceProxyOut",
                "created": change.timestamp.timestamp(),
                "expired": NEVER_EXPIRES,
                "tenantId": change.new_config.get("tenantId", tenant_id)
            }
            
            # Insert the new edges
            version_collection.insert(incoming_edge)
            version_collection.insert(outgoing_edge)
            
            print(f"   [VERSION] Created hasVersion edges: ProxyIn→Device→ProxyOut")
            print(f"            Incoming: {incoming_edge['_key']}")
            print(f"            Outgoing: {outgoing_edge['_key']}")
            
        except Exception as e:
            print(f"   [VERSION] Failed to create device version edges: {str(e)}")
    
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
        current_devices = self.find_current_configurations("devices", device_count)
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
        current_software = self.find_current_configurations("software", software_count)
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
