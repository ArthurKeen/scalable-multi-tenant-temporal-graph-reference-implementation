"""
TTL Time Travel Demo Scenarios

Demonstrates the "Current vs Historical" TTL strategy with compelling
real-world scenarios that showcase:
1. Time travel queries before/after configuration changes
2. Automatic aging of historical data via TTL
3. Preservation of current configurations
4. Realistic operational workflows
"""

import sys
import json
import datetime
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from arango import ArangoClient

# Import project modules
from centralized_credentials import CredentialsManager
from config_management import get_config, NamingConvention
from transaction_simulator import TransactionSimulator
from database_utilities import QueryHelper
from ttl_constants import TTLConstants, TTLMessages, TTLUtilities, NEVER_EXPIRES, DEFAULT_TTL_DAYS


class TTLDemoScenarios:
    """Demonstrates TTL time travel capabilities with realistic scenarios."""
    
    def __init__(self, naming_convention: NamingConvention = NamingConvention.CAMEL_CASE):
        self.naming_convention = naming_convention
        self.app_config = get_config("production", naming_convention)
        
        # Database connection
        creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=creds.endpoint)
        self.database = None
        self.creds = creds
        
        # Transaction simulator
        self.simulator = TransactionSimulator(naming_convention)
        
        # Query helper for time travel queries
        self.query_helper = QueryHelper()
        
        # Demo state tracking
        self.demo_timestamps = {}
        self.demo_results = {}
    
    def connect_to_database(self) -> bool:
        """Connect to database and simulator."""
        try:
            self.database = self.client.db(
                self.creds.database_name,
                **CredentialsManager.get_database_params()
            )
            
            # Connect simulator
            if not self.simulator.connect_to_database():
                return False
            
            print(f"[DEMO] Connected to database for TTL demo scenarios")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to connect: {str(e)}")
            return False
    
    def scenario_1_device_maintenance_cycle(self) -> Dict[str, Any]:
        """
        Scenario 1: Device Maintenance Cycle
        
        Demonstrates:
        - Current device configuration (never expires)
        - Maintenance update creates historical version (expires via TTL)
        - Time travel queries show before/after states
        - Historical data ages out automatically
        """
        print(f"\n" + "="*60)
        print(f"SCENARIO 1: Device Maintenance Cycle")
        print(f"="*60)
        
        scenario_results = {
            "scenario": "device_maintenance_cycle",
            "start_time": datetime.datetime.now().isoformat(),
            "steps": []
        }
        
        # Step 1: Find a current device configuration
        print(f"\n[STEP 1] Finding current device configuration...")
        current_devices = self.simulator.find_current_configurations("Device", 1)
        if not current_devices:
            print(f"[ERROR] No current device configurations found")
            return scenario_results
        
        target_device = current_devices[0]
        device_key = target_device["_key"]
        print(f"   Target device: {device_key}")
        print(f"   Current hostname: {target_device.get('hostName', 'N/A')}")
        never_expires_msg = "never expires" if target_device['expired'] == NEVER_EXPIRES else f"expires at {target_device['expired']}"
        print(f"   Current expired: {target_device['expired']} ({never_expires_msg})")
        
        scenario_results["steps"].append({
            "step": 1,
            "description": "Found current device configuration",
            "device_key": device_key,
            "hostname": target_device.get('hostName', 'N/A'),
            "expired": target_device['expired']
        })
        
        # Step 2: Record "before" timestamp for time travel
        before_timestamp = datetime.datetime.now()
        self.demo_timestamps["before_maintenance"] = before_timestamp
        print(f"\n[STEP 2] Recording 'before maintenance' timestamp: {before_timestamp}")
        
        # Step 3: Query current state at "before" time
        print(f"\n[STEP 3] Querying device state before maintenance...")
        before_query_result = self._query_device_at_time(device_key, before_timestamp)
        if before_query_result:
            print(f"   Found device at {before_timestamp}: {before_query_result.get('hostName', 'N/A')}")
        
        scenario_results["steps"].append({
            "step": 3,
            "description": "Queried device state before maintenance",
            "timestamp": before_timestamp.isoformat(),
            "result": before_query_result
        })
        
        # Step 4: Simulate maintenance configuration change
        print(f"\n[STEP 4] Simulating maintenance configuration change...")
        change = self.simulator.simulate_device_configuration_change(target_device)
        if not change:
            print(f"[ERROR] Failed to simulate configuration change")
            return scenario_results
        
        print(f"   Change type: {change.change_type}")
        print(f"   Description: {change.change_description}")
        print(f"   Old hostname: {change.old_config.get('hostName', 'N/A')}")
        print(f"   New hostname: {change.new_config.get('hostName', 'N/A')}")
        
        # Step 5: Execute the configuration change
        print(f"\n[STEP 5] Executing configuration change transaction...")
        if not self.simulator.execute_configuration_change(change):
            print(f"[ERROR] Failed to execute configuration change")
            return scenario_results
        
        after_timestamp = datetime.datetime.now()
        self.demo_timestamps["after_maintenance"] = after_timestamp
        print(f"   Configuration change completed at: {after_timestamp}")
        print(f"   Old config now historical (expired={change.old_config['expired']})")
        print(f"   New config is current (expired={NEVER_EXPIRES})")
        
        scenario_results["steps"].append({
            "step": 5,
            "description": "Executed configuration change",
            "change_type": change.change_type,
            "change_description": change.change_description,
            "old_hostname": change.old_config.get('hostName', 'N/A'),
            "new_hostname": change.new_config.get('hostName', 'N/A'),
            "timestamp": after_timestamp.isoformat()
        })
        
        # Step 6: Demonstrate time travel queries
        print(f"\n[STEP 6] Demonstrating time travel queries...")
        
        # Query at "before" time (should return old config)
        before_result = self._query_device_at_time(device_key, before_timestamp)
        print(f"   Query at {before_timestamp.strftime('%H:%M:%S')}: {before_result.get('hostName', 'N/A') if before_result else 'Not found'}")
        
        # Query at "after" time (should return new config)
        after_result = self._query_device_at_time(device_key, after_timestamp)
        print(f"   Query at {after_timestamp.strftime('%H:%M:%S')}: {after_result.get('hostName', 'N/A') if after_result else 'Not found'}")
        
        # Query at "now" (should return new config)
        now_result = self._query_device_at_time(device_key, datetime.datetime.now())
        print(f"   Query at now: {now_result.get('hostName', 'N/A') if now_result else 'Not found'}")
        
        scenario_results["steps"].append({
            "step": 6,
            "description": "Time travel query demonstration",
            "before_result": before_result.get('hostName', 'N/A') if before_result else None,
            "after_result": after_result.get('hostName', 'N/A') if after_result else None,
            "now_result": now_result.get('hostName', 'N/A') if now_result else None
        })
        
        # Step 7: Show TTL status
        print(f"\n[STEP 7] TTL Status and Aging Information...")
        ttl_status = self.simulator.ttl_manager.get_ttl_status_summary()
        print(f"   TTL Strategy: {ttl_status['strategy']}")
        print(f"   Historical data expires after: {ttl_status['expire_after_days']} days")
        print(f"   Current configs preserved: {ttl_status['preserve_current_configs']}")
        
        # Calculate when historical data will age out
        historical_expire_time = datetime.datetime.fromtimestamp(change.old_config['expired'])
        ttl_expire_time = historical_expire_time + datetime.timedelta(days=ttl_status['expire_after_days'])
        print(f"   Historical config will age out at: {ttl_expire_time}")
        
        scenario_results["steps"].append({
            "step": 7,
            "description": "TTL status and aging information",
            "ttl_strategy": ttl_status['strategy'],
            "expire_after_days": ttl_status['expire_after_days'],
            "historical_expire_time": historical_expire_time.isoformat(),
            "ttl_expire_time": ttl_expire_time.isoformat()
        })
        
        scenario_results["end_time"] = datetime.datetime.now().isoformat()
        scenario_results["success"] = True
        
        print(f"\n[SUCCESS] Scenario 1 completed successfully!")
        print(f"   Current config: Always available (expired = {NEVER_EXPIRES})")
        print(f"   Historical config: Will age out via TTL in {ttl_status['expire_after_days']} days")
        
        return scenario_results
    
    def scenario_2_software_upgrade_rollback(self) -> Dict[str, Any]:
        """
        Scenario 2: Software Upgrade and Rollback Simulation
        
        Demonstrates:
        - Multiple configuration changes over time
        - Time travel to any point in the upgrade timeline
        - Historical versions aging out while current remains
        """
        print(f"\n" + "="*60)
        print(f"SCENARIO 2: Software Upgrade and Rollback Simulation")
        print(f"="*60)
        
        scenario_results = {
            "scenario": "software_upgrade_rollback",
            "start_time": datetime.datetime.now().isoformat(),
            "steps": [],
            "timeline": []
        }
        
        # Step 1: Find current software configuration
        print(f"\n[STEP 1] Finding current software configuration...")
        current_software = self.simulator.find_current_configurations("Software", 1)
        if not current_software:
            print(f"[ERROR] No current software configurations found")
            return scenario_results
        
        target_software = current_software[0]
        software_key = target_software["_key"]
        print(f"   Target software: {software_key}")
        print(f"   Current port: {target_software.get('portNumber', 'N/A')}")
        print(f"   Current enabled: {target_software.get('isEnabled', 'N/A')}")
        
        # Step 2: Simulate upgrade sequence (3 changes)
        print(f"\n[STEP 2] Simulating software upgrade sequence...")
        
        changes = []
        current_config = target_software
        
        for i in range(TTLConstants.DEFAULT_UPGRADE_SEQUENCE_COUNT):
            # Record timestamp before change
            before_change = datetime.datetime.now()
            time.sleep(TTLConstants.SIMULATION_SLEEP_SECONDS)  # Ensure different timestamps
            
            # Simulate change
            change = self.simulator.simulate_software_configuration_change(current_config)
            if not change:
                continue
            
            # Execute change
            if self.simulator.execute_configuration_change(change):
                changes.append(change)
                current_config = change.new_config
                
                timeline_entry = {
                    "change_number": i + 1,
                    "timestamp": change.timestamp.isoformat(),
                    "change_type": change.change_type,
                    "description": change.change_description,
                    "port": change.new_config.get('portNumber', 'N/A'),
                    "enabled": change.new_config.get('isEnabled', 'N/A')
                }
                scenario_results["timeline"].append(timeline_entry)
                
                print(f"   Change {i+1}: {change.change_description}")
                print(f"      Port: {change.new_config.get('portNumber', 'N/A')}")
                print(f"      Enabled: {change.new_config.get('isEnabled', 'N/A')}")
        
        print(f"   Completed {len(changes)} configuration changes")
        
        # Step 3: Demonstrate time travel across the timeline
        print(f"\n[STEP 3] Time travel demonstration across upgrade timeline...")
        
        time_travel_results = []
        for i, change in enumerate(changes):
            # Query just before this change
            before_time = change.timestamp - datetime.timedelta(seconds=TTLConstants.DEMO_TIME_BUFFER_SECONDS)
            result = self._query_software_at_time(software_key, before_time)
            
            if result:
                time_travel_results.append({
                    "query_time": before_time.isoformat(),
                    "description": f"Before change {i+1}",
                    "port": result.get('portNumber', 'N/A'),
                    "enabled": result.get('isEnabled', 'N/A')
                })
                print(f"   Before change {i+1}: Port {result.get('portNumber', 'N/A')}, Enabled {result.get('isEnabled', 'N/A')}")
        
        # Query current state
        current_result = self._query_software_at_time(software_key, datetime.datetime.now())
        if current_result:
            time_travel_results.append({
                "query_time": datetime.datetime.now().isoformat(),
                "description": "Current state",
                "port": current_result.get('portNumber', 'N/A'),
                "enabled": current_result.get('isEnabled', 'N/A')
            })
            print(f"   Current state: Port {current_result.get('portNumber', 'N/A')}, Enabled {current_result.get('isEnabled', 'N/A')}")
        
        scenario_results["time_travel_results"] = time_travel_results
        
        scenario_results["end_time"] = datetime.datetime.now().isoformat()
        scenario_results["success"] = True
        scenario_results["total_changes"] = len(changes)
        
        print(f"\n[SUCCESS] Scenario 2 completed successfully!")
        print(f"   Total configuration changes: {len(changes)}")
        print(f"   Historical versions: {len(changes)} (will age out via TTL)")
        print(f"   Current version: 1 (never expires)")
        
        return scenario_results
    
    def _query_device_at_time(self, device_key: str, timestamp: datetime.datetime) -> Optional[Dict[str, Any]]:
        """Query device configuration at a specific point in time."""
        try:
            collection_name = self.app_config.get_collection_name("Device")
            if not collection_name:
                return None
            
            # Extract base key (remove any suffixes)
            base_key = device_key.split("_sim_")[0] if "_sim_" in device_key else device_key
            
            aql = f"""
            FOR doc IN {collection_name}
                FILTER doc._key LIKE "{base_key}%" OR doc._key == "{device_key}"
                FILTER doc.created <= {timestamp.timestamp()} AND doc.expired > {timestamp.timestamp()}
                SORT doc.created DESC
                LIMIT 1
                RETURN doc
            """
            
            cursor = self.database.aql.execute(aql)
            results = list(cursor)
            return results[0] if results else None
            
        except Exception as e:
            print(f"[ERROR] Failed to query device at time: {str(e)}")
            return None
    
    def _query_software_at_time(self, software_key: str, timestamp: datetime.datetime) -> Optional[Dict[str, Any]]:
        """Query software configuration at a specific point in time."""
        try:
            collection_name = self.app_config.get_collection_name("Software")
            if not collection_name:
                return None
            
            # Extract base key
            base_key = software_key.split("_sim_")[0] if "_sim_" in software_key else software_key
            
            aql = f"""
            FOR doc IN {collection_name}
                FILTER doc._key LIKE "{base_key}%" OR doc._key == "{software_key}"
                FILTER doc.created <= {timestamp.timestamp()} AND doc.expired > {timestamp.timestamp()}
                SORT doc.created DESC
                LIMIT 1
                RETURN doc
            """
            
            cursor = self.database.aql.execute(aql)
            results = list(cursor)
            return results[0] if results else None
            
        except Exception as e:
            print(f"[ERROR] Failed to query software at time: {str(e)}")
            return None
    
    def run_all_scenarios(self) -> Dict[str, Any]:
        """Run all demo scenarios and return comprehensive results."""
        print(f"\n" + "="*80)
        print(f"TTL TIME TRAVEL DEMO - COMPREHENSIVE SCENARIOS")
        print(f"="*80)
        print(f"Strategy: Current vs Historical TTL")
        print(f"- Current configurations: Never expire (expired = {NEVER_EXPIRES})")
        print(f"- Historical configurations: Age out via TTL after {DEFAULT_TTL_DAYS} days")
        print(f"- Time travel queries: Work across both current and historical data")
        
        demo_results = {
            "demo_start": datetime.datetime.now().isoformat(),
            "strategy": "current_vs_historical_ttl",
            "naming_convention": self.naming_convention.value,
            "scenarios": {}
        }
        
        # Run Scenario 1
        try:
            scenario1_results = self.scenario_1_device_maintenance_cycle()
            demo_results["scenarios"]["device_maintenance_cycle"] = scenario1_results
        except Exception as e:
            print(f"[ERROR] Scenario 1 failed: {str(e)}")
            demo_results["scenarios"]["device_maintenance_cycle"] = {"error": str(e)}
        
        # Run Scenario 2
        try:
            scenario2_results = self.scenario_2_software_upgrade_rollback()
            demo_results["scenarios"]["software_upgrade_rollback"] = scenario2_results
        except Exception as e:
            print(f"[ERROR] Scenario 2 failed: {str(e)}")
            demo_results["scenarios"]["software_upgrade_rollback"] = {"error": str(e)}
        
        demo_results["demo_end"] = datetime.datetime.now().isoformat()
        
        # Summary
        successful_scenarios = len([s for s in demo_results["scenarios"].values() if s.get("success", False)])
        total_scenarios = len(demo_results["scenarios"])
        
        print(f"\n" + "="*80)
        print(f"DEMO SUMMARY")
        print(f"="*80)
        print(f"Successful scenarios: {successful_scenarios}/{total_scenarios}")
        print(f"TTL Strategy: Current configurations never expire, historical age out")
        print(f"Time Travel: Queries work seamlessly across current and historical data")
        print(f"Operational Benefit: Current configs always available, historical cleanup automatic")
        
        return demo_results


def main():
    """Main function for running TTL demo scenarios."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run TTL time travel demo scenarios")
    parser.add_argument("--naming", choices=["camelCase", "snake_case"], default="camelCase",
                       help="Naming convention (default: camelCase)")
    parser.add_argument("--scenario", choices=["1", "2", "all"], default="all",
                       help="Which scenario to run (default: all)")
    
    args = parser.parse_args()
    
    # Convert naming argument to enum
    naming_convention = NamingConvention.CAMEL_CASE if args.naming == "camelCase" else NamingConvention.SNAKE_CASE
    
    # Create demo runner
    demo = TTLDemoScenarios(naming_convention)
    
    if not demo.connect_to_database():
        print("[ERROR] Failed to connect to database")
        sys.exit(1)
    
    # Run selected scenario(s)
    if args.scenario == "1":
        results = demo.scenario_1_device_maintenance_cycle()
    elif args.scenario == "2":
        results = demo.scenario_2_software_upgrade_rollback()
    else:
        results = demo.run_all_scenarios()
    
    # Save results
    results_path = Path("reports") / f"ttl_demo_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    results_path.parent.mkdir(exist_ok=True)
    
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[RESULTS] Demo results saved to: {results_path}")


if __name__ == "__main__":
    main()
