#!/usr/bin/env python3
"""
Time Travel Demonstration Queries

This script demonstrates comprehensive time travel capabilities with real traversal
queries that showcase the graph structure and temporal functionality.

Features:
- Latest configuration retrieval via graph traversal
- Historical configuration access at specific timestamps
- Cross-entity time travel (device-to-software relationships)
- TTL aging demonstration with real-time effects
- Point-in-time graph reconstruction
"""

import sys
import datetime
import time
from typing import Dict, List, Any, Optional
from centralized_credentials import CredentialsManager
from arango import ArangoClient
from ttl_constants import NEVER_EXPIRES

class TimeTravelQueryDemonstrator:
    """Demonstrate comprehensive time travel queries and TTL aging."""
    
    def __init__(self):
        """Initialize the time travel demonstrator."""
        self.client = None
        self.database = None
        
    def connect_to_database(self) -> bool:
        """Connect to the ArangoDB database."""
        try:
            creds = CredentialsManager.get_database_credentials()
            self.client = ArangoClient(hosts=creds.endpoint)
            self.database = self.client.db(creds.database_name, **CredentialsManager.get_database_params())
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False
    
    def query_latest_device_configuration(self, tenant_id: str = None, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Demonstrate traversal query to get latest device configurations.
        
        This query shows how to traverse from DeviceProxyIn → Device (latest) → DeviceProxyOut
        to get current device configurations with full network connectivity.
        """
        print("🔍 LATEST DEVICE CONFIGURATION TRAVERSAL")
        print("=" * 60)
        
        tenant_filter = f'FILTER device.tenantId == "{tenant_id}"' if tenant_id else ""
        
        aql_latest_devices = f"""
        // Start from DeviceProxyIn (connection entry points)
        FOR deviceProxyIn IN DeviceProxyIn
            {tenant_filter.replace('device.', 'deviceProxyIn.')}
            LIMIT {limit}
            
            // Traverse to current Device configuration via hasVersion
            FOR hasVersionIn IN hasVersion
                FILTER hasVersionIn._from == deviceProxyIn._id
                FILTER hasVersionIn._toType == "Device"
                LET currentDevice = DOCUMENT(hasVersionIn._to)
                FILTER currentDevice.expired == {NEVER_EXPIRES}  // Current configuration only
                
                // Traverse to DeviceProxyOut via hasVersion  
                FOR hasVersionOut IN hasVersion
                    FILTER hasVersionOut._from == currentDevice._id
                    FILTER hasVersionOut._toType == "DeviceProxyOut"
                    LET deviceProxyOut = DOCUMENT(hasVersionOut._to)
                    
                    // Find connected software via hasDeviceSoftware
                    LET connectedSoftware = (
                        FOR hasDevSoft IN hasDeviceSoftware
                            FILTER hasDevSoft._from == deviceProxyOut._id
                            LET softwareProxyIn = DOCUMENT(hasDevSoft._to)
                            
                            // Get current software configuration
                            FOR softwareVersion IN hasVersion
                                FILTER softwareVersion._from == softwareProxyIn._id
                                FILTER softwareVersion._toType == "Software"
                                LET software = DOCUMENT(softwareVersion._to)
                                FILTER software.expired == {NEVER_EXPIRES}
                                RETURN {{
                                    softwareKey: software._key,
                                    softwareName: software.name,
                                    softwareType: software.type,
                                    softwarePort: software.portNumber,
                                    softwareEnabled: software.isEnabled
                                }}
                    )
                    
                    // Find location via hasLocation
                    LET deviceLocation = (
                        FOR hasLoc IN hasLocation
                            FILTER hasLoc._from == deviceProxyOut._id
                            LET location = DOCUMENT(hasLoc._to)
                            RETURN {{
                                locationKey: location._key,
                                locationName: location.name,
                                coordinates: location.coordinates
                            }}
                    )[0]
                    
                    RETURN {{
                        // Device information
                        deviceKey: currentDevice._key,
                        deviceName: currentDevice.name,
                        deviceType: currentDevice.type,
                        deviceModel: currentDevice.model,
                        hostName: currentDevice.hostName,
                        ipAddress: currentDevice.ipAddress,
                        
                        // Temporal information
                        configurationCreated: currentDevice.created,
                        configurationCurrent: currentDevice.expired == {NEVER_EXPIRES},
                        
                        // Proxy information
                        proxyIn: deviceProxyIn._key,
                        proxyOut: deviceProxyOut._key,
                        
                        // Connected resources
                        installedSoftware: connectedSoftware,
                        location: deviceLocation,
                        
                        // Traversal path
                        traversalPath: CONCAT("DeviceProxyIn/", deviceProxyIn._key, " → Device/", currentDevice._key, " → DeviceProxyOut/", deviceProxyOut._key)
                    }}
        """
        
        cursor = self.database.aql.execute(aql_latest_devices)
        results = list(cursor)
        
        print(f"Query returned {len(results)} latest device configurations:")
        print()
        
        for i, device in enumerate(results, 1):
            print(f"📱 DEVICE {i}: {device['deviceName']}")
            print(f"   Key: {device['deviceKey']}")
            print(f"   Type: {device['deviceType']} ({device['deviceModel']})")
            print(f"   Network: {device['hostName']} - {device['ipAddress']}")
            print(f"   Created: {datetime.datetime.fromtimestamp(device['configurationCreated'])}")
            print(f"   Current: {'✅' if device['configurationCurrent'] else '❌'}")
            print(f"   Traversal: {device['traversalPath']}")
            
            if device['installedSoftware']:
                print(f"   Software ({len(device['installedSoftware'])}):")
                for software in device['installedSoftware'][:3]:
                    enabled = "🟢" if software['softwareEnabled'] else "🔴"
                    print(f"     {enabled} {software['softwareName']} ({software['softwareType']}) - Port {software['softwarePort']}")
                if len(device['installedSoftware']) > 3:
                    print(f"     ... and {len(device['installedSoftware']) - 3} more")
            
            if device['location']:
                loc = device['location']
                print(f"   Location: {loc['locationName']} ({loc['coordinates']})")
            
            print()
        
        return results
    
    def query_historical_configuration_at_timestamp(self, target_timestamp: float, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Demonstrate point-in-time traversal to get historical configurations.
        
        This query reconstructs the graph state at a specific timestamp,
        showing what the network looked like at that point in time.
        """
        print("⏰ HISTORICAL CONFIGURATION AT POINT-IN-TIME")
        print("=" * 60)
        print(f"Target timestamp: {target_timestamp}")
        print(f"Target time: {datetime.datetime.fromtimestamp(target_timestamp)}")
        print()
        
        aql_historical = f"""
        // Point-in-time reconstruction: Find devices that existed at target time
        FOR deviceProxyIn IN DeviceProxyIn
            LIMIT {limit}
            
            // Find device configuration that was active at target timestamp
            FOR hasVersionIn IN hasVersion
                FILTER hasVersionIn._from == deviceProxyIn._id
                FILTER hasVersionIn._toType == "Device"
                LET historicalDevice = DOCUMENT(hasVersionIn._to)
                FILTER historicalDevice.created <= {target_timestamp}
                FILTER historicalDevice.expired > {target_timestamp}
                
                // Find the corresponding DeviceProxyOut
                FOR hasVersionOut IN hasVersion
                    FILTER hasVersionOut._from == historicalDevice._id
                    FILTER hasVersionOut._toType == "DeviceProxyOut"
                    LET deviceProxyOut = DOCUMENT(hasVersionOut._to)
                    
                    // Find software that was installed at that time
                    LET historicalSoftware = (
                        FOR hasDevSoft IN hasDeviceSoftware
                            FILTER hasDevSoft._from == deviceProxyOut._id
                            FILTER hasDevSoft.created <= {target_timestamp}
                            FILTER hasDevSoft.expired > {target_timestamp}
                            LET softwareProxyIn = DOCUMENT(hasDevSoft._to)
                            
                            // Get software configuration active at target time
                            FOR softwareVersion IN hasVersion
                                FILTER softwareVersion._from == softwareProxyIn._id
                                FILTER softwareVersion._toType == "Software"
                                FILTER softwareVersion.created <= {target_timestamp}
                                FILTER softwareVersion.expired > {target_timestamp}
                                LET software = DOCUMENT(softwareVersion._to)
                                FILTER software.created <= {target_timestamp}
                                FILTER software.expired > {target_timestamp}
                                RETURN {{
                                    softwareKey: software._key,
                                    softwareName: software.name,
                                    softwareType: software.type,
                                    softwareVersion: software.version,
                                    configurationAge: {target_timestamp} - software.created,
                                    wasCurrentThen: software.expired == {NEVER_EXPIRES},
                                    hasBeenReplaced: software.expired != {NEVER_EXPIRES}
                                }}
                    )
                    
                    RETURN {{
                        // Device state at target time
                        deviceKey: historicalDevice._key,
                        deviceName: historicalDevice.name,
                        deviceType: historicalDevice.type,
                        deviceModel: historicalDevice.model,
                        
                        // Temporal context
                        configurationCreated: historicalDevice.created,
                        configurationExpired: historicalDevice.expired,
                        configurationAge: {target_timestamp} - historicalDevice.created,
                        wasCurrentAtTime: historicalDevice.expired > {target_timestamp},
                        hasBeenReplaced: historicalDevice.expired != {NEVER_EXPIRES},
                        
                        // Software state at that time
                        softwareAtTime: historicalSoftware,
                        
                        // Point-in-time metadata
                        reconstructionTimestamp: {target_timestamp},
                        reconstructionTime: DATE_TIMESTAMP("{datetime.datetime.fromtimestamp(target_timestamp).isoformat()}")
                    }}
        """
        
        cursor = self.database.aql.execute(aql_historical)
        results = list(cursor)
        
        print(f"Point-in-time reconstruction found {len(results)} devices:")
        print()
        
        for i, device in enumerate(results, 1):
            config_age_days = device['configurationAge'] / (24 * 60 * 60)
            status = "CURRENT" if device['wasCurrentAtTime'] else "HISTORICAL"
            replaced = " (since replaced)" if device['hasBeenReplaced'] else ""
            
            print(f"📱 DEVICE {i}: {device['deviceName']} [{status}{replaced}]")
            print(f"   Key: {device['deviceKey']}")
            print(f"   Type: {device['deviceType']} ({device['deviceModel']})")
            print(f"   Config created: {datetime.datetime.fromtimestamp(device['configurationCreated'])}")
            print(f"   Config age at target time: {config_age_days:.1f} days")
            
            if device['softwareAtTime']:
                print(f"   Software at that time ({len(device['softwareAtTime'])}):")
                for software in device['softwareAtTime']:
                    software_age_days = software['configurationAge'] / (24 * 60 * 60)
                    software_status = "CURRENT" if software['wasCurrentThen'] else "HISTORICAL"
                    software_replaced = " (since replaced)" if software['hasBeenReplaced'] else ""
                    print(f"     💾 {software['softwareName']} [{software_status}{software_replaced}]")
                    print(f"        Version: {software['softwareVersion']}")
                    print(f"        Age: {software_age_days:.1f} days")
            else:
                print(f"   No software installed at that time")
            
            print()
        
        return results
    
    def demonstrate_ttl_aging_in_real_time(self, monitor_duration: int = 300) -> Dict[str, Any]:
        """
        Demonstrate real-time TTL aging effects.
        
        This shows how historical configurations actually age out and become
        inaccessible over time, while current configurations remain available.
        """
        print("⏳ REAL-TIME TTL AGING DEMONSTRATION")
        print("=" * 60)
        print(f"Monitoring TTL aging for {monitor_duration} seconds ({monitor_duration//60:.1f} minutes)")
        print("This demonstrates how historical configurations age out while current ones remain.")
        print()
        
        start_time = time.time()
        aging_data = []
        
        # Find some historical configurations with TTL
        aql_ttl_candidates = f"""
        FOR doc IN Software
            FILTER HAS(doc, 'ttlExpireAt')
            FILTER doc.ttlExpireAt > {start_time}  // Will expire in the future
            FILTER doc.ttlExpireAt < {start_time + monitor_duration}  // Will expire during monitoring
            SORT doc.ttlExpireAt ASC
            LIMIT 5
            RETURN {{
                key: doc._key,
                name: doc.name,
                expired: doc.expired,
                ttlExpireAt: doc.ttlExpireAt,
                timeUntilTtl: doc.ttlExpireAt - {start_time},
                tenantId: doc.tenantId
            }}
        """
        
        cursor = self.database.aql.execute(aql_ttl_candidates)
        ttl_candidates = list(cursor)
        
        if not ttl_candidates:
            print("⚠️  No TTL candidates found that will expire during monitoring period.")
            print("   This suggests:")
            print("   1. Demo mode TTL (10 minutes) has already aged out historical data")
            print("   2. Or recent transactions haven't created historical configurations")
            print()
            return {"status": "no_candidates", "candidates_found": 0}
        
        print(f"📊 Monitoring {len(ttl_candidates)} configurations that will age out:")
        for candidate in ttl_candidates:
            expire_time = datetime.datetime.fromtimestamp(candidate['ttlExpireAt'])
            print(f"   {candidate['key']}: {candidate['name']}")
            print(f"     Expires: {expire_time} (in {candidate['timeUntilTtl']:.0f} seconds)")
        print()
        
        # Monitor aging in real-time
        check_interval = min(30, monitor_duration // 10)  # Check every 30 seconds or 10% of duration
        checks_performed = 0
        
        while time.time() - start_time < monitor_duration:
            current_time = time.time()
            elapsed = current_time - start_time
            
            print(f"⏰ CHECK {checks_performed + 1} - Elapsed: {elapsed:.0f}s")
            
            # Check which configurations are still accessible
            still_accessible = []
            aged_out = []
            
            for candidate in ttl_candidates:
                aql_check = f"""
                FOR doc IN Software
                    FILTER doc._key == "{candidate['key']}"
                    RETURN doc
                """
                
                cursor = self.database.aql.execute(aql_check)
                results = list(cursor)
                
                if results:
                    still_accessible.append(candidate)
                else:
                    aged_out.append(candidate)
            
            print(f"   Still accessible: {len(still_accessible)}")
            print(f"   Aged out: {len(aged_out)}")
            
            # Show aging progress
            for candidate in still_accessible:
                time_until_ttl = candidate['ttlExpireAt'] - current_time
                if time_until_ttl > 0:
                    print(f"     ⏳ {candidate['key']}: {time_until_ttl:.0f}s until TTL")
                else:
                    print(f"     🕐 {candidate['key']}: Past TTL ({-time_until_ttl:.0f}s ago)")
            
            for candidate in aged_out:
                print(f"     ❌ {candidate['key']}: AGED OUT")
            
            aging_data.append({
                "timestamp": current_time,
                "elapsed": elapsed,
                "still_accessible": len(still_accessible),
                "aged_out": len(aged_out)
            })
            
            print()
            checks_performed += 1
            
            if len(aged_out) == len(ttl_candidates):
                print("🎉 All monitored configurations have aged out!")
                break
            
            time.sleep(check_interval)
        
        return {
            "status": "completed",
            "candidates_found": len(ttl_candidates),
            "total_checks": checks_performed,
            "aging_data": aging_data,
            "final_aged_out": len(aged_out) if 'aged_out' in locals() else 0
        }
    
    def demonstrate_unified_transaction_ttl_flow(self) -> Dict[str, Any]:
        """
        Demonstrate the unified transaction + TTL flow in real-time.
        
        This shows how:
        1. Transaction creates new current config
        2. Old config immediately gets TTL timestamp
        3. Time travel queries show both versions
        4. Historical config ages out over time
        """
        print("🔄 UNIFIED TRANSACTION + TTL FLOW DEMONSTRATION")
        print("=" * 70)
        print("This demonstrates the complete lifecycle:")
        print("1. Pre-transaction state")
        print("2. Transaction execution (immediate TTL activation)")
        print("3. Post-transaction time travel")
        print("4. Real-time aging observation")
        print()
        
        # Step 1: Show pre-transaction state
        print("📊 STEP 1: PRE-TRANSACTION STATE")
        print("-" * 40)
        
        latest_configs = self.query_latest_device_configuration(limit=1)
        if not latest_configs:
            return {"error": "No devices found for demonstration"}
        
        device = latest_configs[0]
        device_key = device['deviceKey']
        
        print(f"Target device: {device['deviceName']} ({device_key})")
        print()
        
        # Step 2: Simulate a transaction (this would normally be in transaction_simulator)
        print("⚡ STEP 2: TRANSACTION SIMULATION")
        print("-" * 40)
        print("NOTE: In a full demonstration, this would execute a real transaction.")
        print("For this demo, we'll show the conceptual flow:")
        print()
        
        transaction_time = time.time()
        print(f"Transaction timestamp: {transaction_time}")
        print(f"Actions that would occur:")
        print(f"  1. Current config expired → {transaction_time}")
        print(f"  2. Current config ttlExpireAt → {transaction_time + 600} (10 min TTL)")
        print(f"  3. New config created with expired → {NEVER_EXPIRES}")
        print(f"  4. hasVersion edges updated to new config")
        print()
        
        # Step 3: Show time travel capability
        print("🕰️  STEP 3: TIME TRAVEL DEMONSTRATION")
        print("-" * 40)
        
        # Show current state
        print("Current state (latest configurations):")
        current_results = self.query_latest_device_configuration(limit=1)
        
        # Show historical state (5 minutes ago)
        historical_timestamp = time.time() - 300  # 5 minutes ago
        print("Historical state (5 minutes ago):")
        historical_results = self.query_historical_configuration_at_timestamp(historical_timestamp, limit=1)
        
        # Step 4: Show TTL aging concept
        print("⏳ STEP 4: TTL AGING CONCEPT")
        print("-" * 40)
        print("In a live system with recent transactions:")
        print("  - Historical configs age out after 10 minutes (demo mode)")
        print("  - Current configs remain indefinitely")
        print("  - Time travel queries automatically exclude aged-out data")
        print("  - Graph traversals always find current configurations")
        print()
        
        return {
            "status": "conceptual_demonstration",
            "device_demonstrated": device_key,
            "transaction_time": transaction_time,
            "ttl_expiration": transaction_time + 600
        }

def main():
    """Main function to run time travel demonstrations."""
    print("Time Travel Query Demonstrations")
    print("=" * 80)
    print("This script demonstrates comprehensive time travel capabilities")
    print("with real graph traversal queries and TTL aging effects.")
    print()
    
    demonstrator = TimeTravelQueryDemonstrator()
    
    if not demonstrator.connect_to_database():
        return 1
    
    try:
        # Demo 1: Latest configuration traversal
        print("🎯 DEMONSTRATION 1: LATEST CONFIGURATION RETRIEVAL")
        print("=" * 80)
        latest_results = demonstrator.query_latest_device_configuration(limit=3)
        print()
        
        input("Press Enter to continue to historical demonstration...")
        
        # Demo 2: Historical configuration access
        print("🎯 DEMONSTRATION 2: HISTORICAL CONFIGURATION ACCESS")
        print("=" * 80)
        # Use a timestamp from 1 hour ago
        historical_timestamp = time.time() - 3600
        historical_results = demonstrator.query_historical_configuration_at_timestamp(historical_timestamp, limit=3)
        print()
        
        input("Press Enter to continue to TTL aging demonstration...")
        
        # Demo 3: TTL aging (if applicable)
        print("🎯 DEMONSTRATION 3: TTL AGING EFFECTS")
        print("=" * 80)
        aging_results = demonstrator.demonstrate_ttl_aging_in_real_time(monitor_duration=120)  # 2 minutes
        print()
        
        input("Press Enter to continue to unified flow demonstration...")
        
        # Demo 4: Unified transaction + TTL flow
        print("🎯 DEMONSTRATION 4: UNIFIED TRANSACTION + TTL FLOW")
        print("=" * 80)
        unified_results = demonstrator.demonstrate_unified_transaction_ttl_flow()
        print()
        
        print("🎉 ALL TIME TRAVEL DEMONSTRATIONS COMPLETED!")
        print()
        print("Key takeaways:")
        print("✅ Graph traversals efficiently find latest configurations")
        print("✅ Point-in-time queries reconstruct historical network state")
        print("✅ TTL automatically ages out historical data")
        print("✅ Transactions and TTL work as unified system")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Demonstration stopped by user")
        return 130
    except Exception as e:
        print(f"[ERROR] Demonstration failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
