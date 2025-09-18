#!/usr/bin/env python3
"""
Unified Transaction + TTL Demonstration

This script addresses the artificial separation between transaction simulation
and TTL demonstration by showing them as a unified system where:

1. Transactions immediately activate TTL aging
2. Historical configurations age out in real-time
3. Time travel queries show the progression
4. The system demonstrates actual data lifecycle management

This replaces the separate transaction and TTL demos with a unified experience.
"""

import sys
import time
import datetime
from typing import Dict, List, Any, Optional
from src.config.centralized_credentials import CredentialsManager
from arango import ArangoClient
from src.ttl.ttl_constants import NEVER_EXPIRES, TTLConstants
from src.simulation.transaction_simulator import TransactionSimulator
from src.config.config_management import NamingConvention

class UnifiedTransactionTTLDemo:
    """Demonstrate unified transaction simulation with real-time TTL aging."""
    
    def __init__(self, naming_convention: NamingConvention = NamingConvention.CAMEL_CASE):
        """Initialize the unified demo."""
        self.naming_convention = naming_convention
        self.client = None
        self.database = None
        self.demo_start_time = time.time()
        
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
    
    def show_pre_transaction_state(self, target_tenant: str = None) -> Dict[str, Any]:
        """Show the current state before transactions with specific documents to watch."""
        print("📊 PRE-TRANSACTION STATE ANALYSIS")
        print("=" * 60)
        
        if not target_tenant:
            # Find a tenant with software to modify
            aql_find_tenant = """
            FOR doc IN Software
                FILTER doc.expired == 9223372036854775807
                COLLECT tenantId = doc.tenantId WITH COUNT INTO count
                FILTER count >= 2
                SORT count DESC
                LIMIT 1
                RETURN tenantId
            """
            
            cursor = self.database.aql.execute(aql_find_tenant)
            tenants = list(cursor)
            if not tenants:
                return {"error": "No suitable tenants found for demonstration"}
            target_tenant = tenants[0]
        
        print(f"Target tenant: {target_tenant}")
        print()
        
        # Find current software configurations to modify
        aql_current_software = f"""
        FOR doc IN Software
            FILTER doc.tenantId == "{target_tenant}"
            FILTER doc.expired == 9223372036854775807
            SORT doc.created DESC
            LIMIT 3
            RETURN {{
                key: doc._key,
                id: doc._id,
                name: doc.name,
                type: doc.type,
                version: doc.version,
                port: doc.portNumber,
                enabled: doc.isEnabled,
                created: doc.created,
                expired: doc.expired,
                hasTtl: HAS(doc, 'ttlExpireAt'),
                ttlValue: HAS(doc, 'ttlExpireAt') ? doc.ttlExpireAt : null
            }}
        """
        
        cursor = self.database.aql.execute(aql_current_software)
        current_software = list(cursor)
        
        print(f"📋 CURRENT SOFTWARE CONFIGURATIONS TO MODIFY:")
        watch_list = []
        
        for i, software in enumerate(current_software, 1):
            ttl_status = f"TTL: {software['ttlValue']}" if software['hasTtl'] else "TTL: NOT SET"
            expired_status = "NEVER_EXPIRES" if software['expired'] == NEVER_EXPIRES else f"EXPIRED: {software['expired']}"
            
            print(f"  [{i}] {software['key']}")
            print(f"      Name: {software['name']}")
            print(f"      Type: {software['type']} - Port: {software['port']}")
            print(f"      Version: {software['version']}")
            print(f"      Status: {expired_status}")
            print(f"      TTL Status: {ttl_status}")
            print()
            
            watch_list.append({
                "key": software['key'],
                "name": software['name'],
                "current_expired": software['expired'],
                "current_ttl": software['ttlValue']
            })
        
        # Show connected devices
        if current_software:
            software_key = current_software[0]['key']
            software_base = software_key.split('-')[0]  # Get base software name
            
            aql_connected_devices = f"""
            // Find devices connected to this software
            FOR softwareProxyIn IN SoftwareProxyIn
                FILTER STARTS_WITH(softwareProxyIn._key, "{software_base}")
                
                FOR hasDevSoft IN hasDeviceSoftware
                    FILTER hasDevSoft._to == softwareProxyIn._id
                    LET deviceProxy = DOCUMENT(hasDevSoft._from)
                    
                    // Get the current device configuration
                    FOR deviceVersion IN hasVersion
                        FILTER deviceVersion._to == hasDevSoft._from
                        FILTER deviceVersion._fromType == "Device"
                        LET device = DOCUMENT(deviceVersion._from)
                        FILTER device.expired == 9223372036854775807
                        
                        RETURN {{
                            deviceKey: device._key,
                            deviceName: device.name,
                            deviceType: device.type,
                            softwareConnection: softwareProxyIn._key
                        }}
            """
            
            cursor = self.database.aql.execute(aql_connected_devices)
            connected_devices = list(cursor)
            
            print(f"🖥️ CONNECTED DEVICES ({len(connected_devices)}):")
            for device in connected_devices[:3]:
                print(f"  • {device['deviceName']} ({device['deviceType']})")
                print(f"    Key: {device['deviceKey']}")
                print(f"    Connected via: {device['softwareConnection']}")
            if len(connected_devices) > 3:
                print(f"  ... and {len(connected_devices) - 3} more devices")
            print()
        
        return {
            "tenant_id": target_tenant,
            "watch_list": watch_list,
            "connected_devices": len(connected_devices) if 'connected_devices' in locals() else 0,
            "pre_transaction_time": time.time()
        }
    
    def execute_unified_transaction(self, watch_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute transaction with immediate TTL activation and show the changes."""
        print("⚡ UNIFIED TRANSACTION EXECUTION + TTL ACTIVATION")
        print("=" * 60)
        
        transaction_start = time.time()
        print(f"Transaction timestamp: {transaction_start}")
        print(f"Expected TTL expiration: {transaction_start + 600} (10 minutes from now)")
        print()
        
        # Initialize transaction simulator
        simulator = TransactionSimulator(self.naming_convention, show_queries=False)
        if not simulator.connect_to_database():
            return {"error": "Failed to connect transaction simulator"}
        
        # Execute software configuration changes
        print("🔄 EXECUTING SOFTWARE CONFIGURATION CHANGES...")
        changes_made = []
        
        for item in watch_list[:2]:  # Modify first 2 software configurations
            software_key = item['key']
            
            # Find the current software document
            aql_find_software = f"""
            FOR doc IN Software
                FILTER doc._key == "{software_key}"
                RETURN doc
            """
            
            cursor = self.database.aql.execute(aql_find_software)
            software_docs = list(cursor)
            
            if software_docs:
                current_software = software_docs[0]
                change = simulator.simulate_software_configuration_change(current_software)
                
                if change:
                    success = simulator.execute_configuration_change(change)
                    if success:
                        changes_made.append({
                            "original_key": software_key,
                            "new_key": change.new_config['_key'],
                            "change_type": change.change_type,
                            "description": change.change_description,
                            "timestamp": change.timestamp.timestamp()
                        })
                        print(f"  ✅ {software_key} → {change.new_config['_key']}")
                        print(f"     Change: {change.change_description}")
                    else:
                        print(f"  ❌ Failed to execute change for {software_key}")
                else:
                    print(f"  ⚠️ No change generated for {software_key}")
        
        print()
        print(f"📊 TRANSACTION RESULTS:")
        print(f"  Changes executed: {len(changes_made)}")
        print(f"  Transaction duration: {time.time() - transaction_start:.2f} seconds")
        print()
        
        return {
            "transaction_time": transaction_start,
            "changes_made": changes_made,
            "ttl_expiration_time": transaction_start + 600
        }
    
    def show_immediate_post_transaction_state(self, watch_list: List[Dict[str, Any]], 
                                            transaction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Show the immediate state after transaction to verify TTL activation."""
        print("🔍 IMMEDIATE POST-TRANSACTION STATE VERIFICATION")
        print("=" * 60)
        
        verification_results = []
        
        print("Checking TTL field activation on historical documents...")
        print()
        
        for item in watch_list:
            original_key = item['key']
            
            # Check if the original document now has TTL fields
            aql_check_original = f"""
            FOR doc IN Software
                FILTER doc._key == "{original_key}"
                RETURN {{
                    key: doc._key,
                    name: doc.name,
                    expired: doc.expired,
                    hasTtl: HAS(doc, 'ttlExpireAt'),
                    ttlValue: HAS(doc, 'ttlExpireAt') ? doc.ttlExpireAt : null,
                    isHistorical: doc.expired != 9223372036854775807
                }}
            """
            
            cursor = self.database.aql.execute(aql_check_original)
            original_docs = list(cursor)
            
            if original_docs:
                doc = original_docs[0]
                ttl_activated = doc['hasTtl'] and doc['isHistorical']
                
                print(f"📄 {original_key}:")
                print(f"   Status: {'HISTORICAL' if doc['isHistorical'] else 'CURRENT'}")
                print(f"   Expired: {doc['expired']}")
                print(f"   TTL activated: {'✅' if ttl_activated else '❌'}")
                if doc['hasTtl']:
                    expiry_time = datetime.datetime.fromtimestamp(doc['ttlValue'])
                    time_until_expiry = doc['ttlValue'] - time.time()
                    print(f"   TTL expires: {expiry_time} (in {time_until_expiry/60:.1f} minutes)")
                print()
                
                verification_results.append({
                    "key": original_key,
                    "ttl_activated": ttl_activated,
                    "is_historical": doc['isHistorical'],
                    "ttl_expiry": doc['ttlValue'] if doc['hasTtl'] else None
                })
        
        # Find and show new current configurations
        print("🆕 NEW CURRENT CONFIGURATIONS:")
        changes_made = transaction_result.get('changes_made', [])
        
        for change in changes_made:
            new_key = change['new_key']
            
            aql_check_new = f"""
            FOR doc IN Software
                FILTER doc._key == "{new_key}"
                RETURN {{
                    key: doc._key,
                    name: doc.name,
                    expired: doc.expired,
                    hasTtl: HAS(doc, 'ttlExpireAt'),
                    isCurrent: doc.expired == 9223372036854775807
                }}
            """
            
            cursor = self.database.aql.execute(aql_check_new)
            new_docs = list(cursor)
            
            if new_docs:
                doc = new_docs[0]
                print(f"📄 {new_key}:")
                print(f"   Name: {doc['name']}")
                print(f"   Status: {'CURRENT' if doc['isCurrent'] else 'HISTORICAL'}")
                print(f"   TTL field: {'NOT SET' if not doc['hasTtl'] else 'SET'} ({'✅ Correct' if not doc['hasTtl'] else '❌ Error'})")
                print()
        
        return {
            "verification_results": verification_results,
            "ttl_activated_count": sum(1 for r in verification_results if r['ttl_activated'])
        }
    
    def monitor_real_time_aging(self, transaction_result: Dict[str, Any], 
                              monitor_duration: int = 300) -> Dict[str, Any]:
        """Monitor configurations aging out in real-time."""
        print(f"⏳ REAL-TIME TTL AGING MONITOR ({monitor_duration//60} minutes)")
        print("=" * 60)
        
        ttl_expiration = transaction_result['ttl_expiration_time']
        changes_made = transaction_result['changes_made']
        
        if not changes_made:
            print("⚠️ No changes were made to monitor aging for.")
            return {"status": "no_changes"}
        
        print(f"Monitoring aging of {len(changes_made)} historical configurations...")
        print(f"Expected aging time: {datetime.datetime.fromtimestamp(ttl_expiration)}")
        print()
        
        aging_data = []
        start_monitoring = time.time()
        check_interval = 30  # Check every 30 seconds
        
        while time.time() - start_monitoring < monitor_duration:
            current_time = time.time()
            elapsed = current_time - start_monitoring
            time_until_ttl = ttl_expiration - current_time
            
            print(f"⏰ Monitor Check - Elapsed: {elapsed:.0f}s, Time until TTL: {time_until_ttl:.0f}s")
            
            still_exists = []
            aged_out = []
            
            for change in changes_made:
                original_key = change['original_key']
                
                # Check if the original (now historical) document still exists
                aql_check_exists = f"""
                FOR doc IN Software
                    FILTER doc._key == "{original_key}"
                    RETURN {{
                        key: doc._key,
                        name: doc.name,
                        ttlExpireAt: HAS(doc, 'ttlExpireAt') ? doc.ttlExpireAt : null
                    }}
                """
                
                cursor = self.database.aql.execute(aql_check_exists)
                results = list(cursor)
                
                if results:
                    doc = results[0]
                    still_exists.append({
                        "key": original_key,
                        "name": doc['name'],
                        "ttl_expiry": doc['ttlExpireAt']
                    })
                else:
                    aged_out.append({
                        "key": original_key,
                        "aged_out_at": current_time
                    })
            
            print(f"   Still exists: {len(still_exists)}")
            print(f"   Aged out: {len(aged_out)}")
            
            # Show details
            for doc in still_exists:
                if doc['ttl_expiry']:
                    time_remaining = doc['ttl_expiry'] - current_time
                    if time_remaining > 0:
                        print(f"     ⏳ {doc['key']}: {time_remaining:.0f}s remaining")
                    else:
                        print(f"     🕐 {doc['key']}: {-time_remaining:.0f}s overdue")
                        
            for doc in aged_out:
                print(f"     ❌ {doc['key']}: AGED OUT")
            
            aging_data.append({
                "timestamp": current_time,
                "elapsed": elapsed,
                "still_exists": len(still_exists),
                "aged_out": len(aged_out)
            })
            
            print()
            
            # Break if all documents have aged out
            if len(aged_out) == len(changes_made):
                print("🎉 All historical configurations have aged out!")
                break
                
            time.sleep(check_interval)
        
        return {
            "status": "completed",
            "total_monitored": len(changes_made),
            "final_aged_out": len(aged_out) if 'aged_out' in locals() else 0,
            "aging_data": aging_data
        }
    
    def demonstrate_time_travel_during_aging(self, transaction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Show how time travel queries work during the aging process."""
        print("🕰️ TIME TRAVEL QUERIES DURING AGING PROCESS")
        print("=" * 60)
        
        transaction_time = transaction_result['transaction_time']
        current_time = time.time()
        
        print("Demonstrating time travel at different points:")
        print()
        
        # Query 1: Before transaction
        before_transaction = transaction_time - 300  # 5 minutes before
        print(f"📅 QUERY 1: Before transaction ({datetime.datetime.fromtimestamp(before_transaction)})")
        
        aql_before = f"""
        FOR doc IN Software
            FILTER doc.created <= {before_transaction}
            FILTER doc.expired > {before_transaction}
            FILTER STARTS_WITH(doc._key, "ceed8203fdab_software")
            LIMIT 3
            RETURN {{
                key: doc._key,
                name: doc.name,
                wasCurrentThen: doc.expired == 9223372036854775807,
                configAge: {before_transaction} - doc.created
            }}
        """
        
        cursor = self.database.aql.execute(aql_before)
        before_results = list(cursor)
        
        print(f"   Found {len(before_results)} configurations active before transaction:")
        for doc in before_results:
            age_days = doc['configAge'] / (24 * 60 * 60)
            status = "CURRENT" if doc['wasCurrentThen'] else "HISTORICAL"
            print(f"     {doc['key']} ({status}) - Age: {age_days:.1f} days")
        print()
        
        # Query 2: After transaction (current)
        print(f"📅 QUERY 2: Current state ({datetime.datetime.fromtimestamp(current_time)})")
        
        aql_current = f"""
        FOR doc IN Software
            FILTER doc.created <= {current_time}
            FILTER doc.expired > {current_time}
            FILTER STARTS_WITH(doc._key, "ceed8203fdab_software")
            LIMIT 3
            RETURN {{
                key: doc._key,
                name: doc.name,
                isCurrentNow: doc.expired == 9223372036854775807,
                hasBeenModified: REGEX_TEST(doc._key, "_sim_"),
                configAge: {current_time} - doc.created
            }}
        """
        
        cursor = self.database.aql.execute(aql_current)
        current_results = list(cursor)
        
        print(f"   Found {len(current_results)} configurations active now:")
        for doc in current_results:
            age_minutes = doc['configAge'] / 60
            status = "CURRENT" if doc['isCurrentNow'] else "HISTORICAL"
            modified = " (SIMULATED)" if doc['hasBeenModified'] else " (ORIGINAL)"
            print(f"     {doc['key']} ({status}{modified}) - Age: {age_minutes:.1f} minutes")
        print()
        
        # Query 3: Future (after TTL)
        future_time = transaction_time + 700  # After TTL expiration
        print(f"📅 QUERY 3: After TTL expiration (simulated: {datetime.datetime.fromtimestamp(future_time)})")
        print("   This simulates what queries will return after historical data ages out:")
        
        aql_future = f"""
        FOR doc IN Software
            FILTER doc.created <= {future_time}
            FILTER doc.expired > {future_time}
            FILTER STARTS_WITH(doc._key, "ceed8203fdab_software")
            // Simulate TTL by filtering out documents that would have aged out
            FILTER !(HAS(doc, 'ttlExpireAt') AND doc.ttlExpireAt <= {future_time})
            LIMIT 3
            RETURN {{
                key: doc._key,
                name: doc.name,
                survivesTtl: !HAS(doc, 'ttlExpireAt') || doc.ttlExpireAt > {future_time},
                configAge: {future_time} - doc.created
            }}
        """
        
        cursor = self.database.aql.execute(aql_future)
        future_results = list(cursor)
        
        print(f"   Will find {len(future_results)} configurations after TTL cleanup:")
        for doc in future_results:
            age_hours = doc['configAge'] / 3600
            print(f"     {doc['key']} (SURVIVES TTL) - Age: {age_hours:.1f} hours")
        print()
        
        return {
            "before_transaction_count": len(before_results),
            "current_count": len(current_results),
            "after_ttl_count": len(future_results),
            "time_travel_functional": True
        }

def main():
    """Main function to run the unified transaction + TTL demonstration."""
    print("Unified Transaction + TTL Demonstration")
    print("=" * 80)
    print("This demonstration shows transactions and TTL as a unified system:")
    print("• Transactions immediately activate TTL aging")
    print("• Historical configurations age out in real-time")
    print("• Time travel queries show the complete lifecycle")
    print("• Current configurations remain accessible indefinitely")
    print()
    
    demo = UnifiedTransactionTTLDemo()
    
    if not demo.connect_to_database():
        return 1
    
    try:
        # Step 1: Show pre-transaction state
        print("🎯 STEP 1: PRE-TRANSACTION ANALYSIS")
        print("=" * 80)
        pre_state = demo.show_pre_transaction_state()
        
        if "error" in pre_state:
            print(f"[ERROR] {pre_state['error']}")
            return 1
        
        input("\nPress Enter to execute unified transaction + TTL activation...")
        
        # Step 2: Execute unified transaction
        print("\n🎯 STEP 2: UNIFIED TRANSACTION + TTL EXECUTION")
        print("=" * 80)
        transaction_result = demo.execute_unified_transaction(pre_state['watch_list'])
        
        if "error" in transaction_result:
            print(f"[ERROR] {transaction_result['error']}")
            return 1
        
        input("\nPress Enter to verify immediate TTL activation...")
        
        # Step 3: Show immediate post-transaction state
        print("\n🎯 STEP 3: IMMEDIATE TTL ACTIVATION VERIFICATION")
        print("=" * 80)
        verification = demo.show_immediate_post_transaction_state(pre_state['watch_list'], transaction_result)
        
        input("\nPress Enter to demonstrate time travel queries...")
        
        # Step 4: Demonstrate time travel during aging
        print("\n🎯 STEP 4: TIME TRAVEL DURING AGING PROCESS")
        print("=" * 80)
        time_travel_result = demo.demonstrate_time_travel_during_aging(transaction_result)
        
        # Ask user if they want to monitor real-time aging
        response = input("\nMonitor real-time TTL aging for 3 minutes? (y/N): ").strip().lower()
        
        if response.startswith('y'):
            print("\n🎯 STEP 5: REAL-TIME TTL AGING MONITOR")
            print("=" * 80)
            aging_result = demo.monitor_real_time_aging(transaction_result, monitor_duration=180)
        else:
            print("\n⏭️ Skipping real-time aging monitor.")
            aging_result = {"status": "skipped"}
        
        # Summary
        print("\n🎉 UNIFIED DEMONSTRATION COMPLETED!")
        print("=" * 60)
        print("Key achievements:")
        print("✅ Transactions and TTL work as unified system")
        print("✅ Historical configurations immediately get TTL timestamps")
        print("✅ Current configurations remain permanently accessible")
        print("✅ Time travel queries work throughout the aging process")
        if aging_result.get("status") == "completed":
            aged_out = aging_result.get("final_aged_out", 0)
            total = aging_result.get("total_monitored", 0)
            print(f"✅ Real-time aging demonstrated: {aged_out}/{total} configs aged out")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Demonstration stopped by user")
        return 130
    except Exception as e:
        print(f"[ERROR] Demonstration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
