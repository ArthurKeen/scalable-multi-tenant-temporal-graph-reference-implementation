#!/usr/bin/env python3
"""
Transaction Simulation Bug Fix

This script fixes the critical bug where transaction simulation creates new
Software configurations but fails to update hasVersion edges, leaving the
new configurations orphaned and unreachable in the graph.

The fix:
1. Identifies orphaned simulated configurations
2. Updates hasVersion edges to point to the correct current configurations
3. Ensures proper graph connectivity for time travel and traversals
"""

import sys
import re
from typing import Dict, List, Any
from centralized_credentials import CredentialsManager
from arango import ArangoClient
from ttl_constants import NEVER_EXPIRES

class TransactionSimulationBugFixer:
    """Fix the transaction simulation hasVersion edge bug."""
    
    def __init__(self):
        """Initialize the bug fixer."""
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
    
    def identify_orphaned_configurations(self) -> Dict[str, Any]:
        """Identify Software configurations that are orphaned (not connected via hasVersion)."""
        print("🔍 IDENTIFYING ORPHANED CONFIGURATIONS")
        print("=" * 60)
        
        if not self.connect_to_database():
            return {"error": "Failed to connect to database"}
        
        # Find all current Software configurations (expired = NEVER_EXPIRES)
        aql_current_software = """
        FOR doc IN Software
            FILTER doc.expired == 9223372036854775807  // NEVER_EXPIRES
            RETURN {
                key: doc._key,
                id: doc._id,
                name: doc.name,
                tenantId: doc.tenantId,
                created: doc.created,
                isSimulated: REGEX_TEST(doc._key, "_sim_")
            }
        """
        
        cursor = self.database.aql.execute(aql_current_software)
        current_configs = list(cursor)
        
        # Check which ones have hasVersion connections
        orphaned_configs = []
        connected_configs = []
        
        for config in current_configs:
            software_id = config['id']
            
            # Check for incoming hasVersion edges (from SoftwareProxyIn)
            aql_incoming = f"""
            FOR edge IN hasVersion
                FILTER edge._to == "{software_id}"
                FILTER edge._fromType == "SoftwareProxyIn"
                RETURN edge
            """
            
            cursor = self.database.aql.execute(aql_incoming)
            incoming_edges = list(cursor)
            
            # Check for outgoing hasVersion edges (to SoftwareProxyOut)
            aql_outgoing = f"""
            FOR edge IN hasVersion
                FILTER edge._from == "{software_id}"
                FILTER edge._toType == "SoftwareProxyOut"
                RETURN edge
            """
            
            cursor = self.database.aql.execute(aql_outgoing)
            outgoing_edges = list(cursor)
            
            config['incoming_edges'] = len(incoming_edges)
            config['outgoing_edges'] = len(outgoing_edges)
            config['is_connected'] = len(incoming_edges) > 0 and len(outgoing_edges) > 0
            
            if config['is_connected']:
                connected_configs.append(config)
            else:
                orphaned_configs.append(config)
        
        return {
            "total_current_configs": len(current_configs),
            "connected_configs": len(connected_configs),
            "orphaned_configs": len(orphaned_configs),
            "orphaned_details": orphaned_configs,
            "connected_details": connected_configs
        }
    
    def find_correct_proxy_connections(self, orphaned_config: Dict[str, Any]) -> Dict[str, Any]:
        """Find the correct SoftwareProxyIn/Out that should connect to this configuration."""
        
        # Extract base software identifier from the key
        # e.g., "ceed8203fdab_software1-0_sim_1758045639_528822" -> "ceed8203fdab_software1"
        key = orphaned_config['key']
        tenant_id = orphaned_config['tenantId']
        
        # Pattern to extract base software name
        base_pattern = r'^([^-]+_software\d+)'
        match = re.match(base_pattern, key)
        
        if not match:
            return {"error": f"Could not extract base software name from {key}"}
        
        base_software_name = match.group(1)
        
        # Find the corresponding SoftwareProxyIn
        aql_proxy_in = f"""
        FOR doc IN SoftwareProxyIn
            FILTER doc.tenantId == "{tenant_id}"
            FILTER doc._key == "{base_software_name}"
            RETURN doc
        """
        
        cursor = self.database.aql.execute(aql_proxy_in)
        proxy_in_docs = list(cursor)
        
        # Find the corresponding SoftwareProxyOut
        aql_proxy_out = f"""
        FOR doc IN SoftwareProxyOut
            FILTER doc.tenantId == "{tenant_id}"
            FILTER doc._key == "{base_software_name}"
            RETURN doc
        """
        
        cursor = self.database.aql.execute(aql_proxy_out)
        proxy_out_docs = list(cursor)
        
        if not proxy_in_docs or not proxy_out_docs:
            return {
                "error": f"Missing proxy collections for {base_software_name}",
                "proxy_in_found": len(proxy_in_docs) > 0,
                "proxy_out_found": len(proxy_out_docs) > 0
            }
        
        return {
            "base_software_name": base_software_name,
            "proxy_in": proxy_in_docs[0],
            "proxy_out": proxy_out_docs[0]
        }
    
    def fix_orphaned_configuration(self, orphaned_config: Dict[str, Any]) -> Dict[str, Any]:
        """Fix a single orphaned configuration by updating hasVersion edges."""
        
        software_id = orphaned_config['id']
        config_key = orphaned_config['key']
        
        print(f"  Fixing: {config_key}")
        
        # Find the correct proxy connections
        proxy_info = self.find_correct_proxy_connections(orphaned_config)
        
        if "error" in proxy_info:
            print(f"    ❌ {proxy_info['error']}")
            return {"status": "failed", "error": proxy_info["error"]}
        
        proxy_in = proxy_info['proxy_in']
        proxy_out = proxy_info['proxy_out']
        base_name = proxy_info['base_software_name']
        
        proxy_in_id = f"SoftwareProxyIn/{proxy_in['_key']}"
        proxy_out_id = f"SoftwareProxyOut/{proxy_out['_key']}"
        
        print(f"    Target ProxyIn: {proxy_in_id}")
        print(f"    Target ProxyOut: {proxy_out_id}")
        
        # Step 1: Remove old hasVersion edges from proxy_in to other current configs
        aql_remove_old_incoming = f"""
        FOR edge IN hasVersion
            FILTER edge._from == "{proxy_in_id}"
            FILTER edge._toType == "Software"
            LET target_software = DOCUMENT(edge._to)
            FILTER target_software.expired == 9223372036854775807  // NEVER_EXPIRES
            FILTER STARTS_WITH(target_software._key, "{base_name}")
            REMOVE edge IN hasVersion
            RETURN edge._key
        """
        
        cursor = self.database.aql.execute(aql_remove_old_incoming)
        removed_incoming = list(cursor)
        
        # Step 2: Remove old hasVersion edges from other current configs to proxy_out
        aql_remove_old_outgoing = f"""
        FOR edge IN hasVersion
            FILTER edge._to == "{proxy_out_id}"
            FILTER edge._fromType == "Software"
            LET source_software = DOCUMENT(edge._from)
            FILTER source_software.expired == 9223372036854775807  // NEVER_EXPIRES
            FILTER STARTS_WITH(source_software._key, "{base_name}")
            REMOVE edge IN hasVersion
            RETURN edge._key
        """
        
        cursor = self.database.aql.execute(aql_remove_old_outgoing)
        removed_outgoing = list(cursor)
        
        # Step 3: Create new hasVersion edge from proxy_in to current config
        incoming_edge_key = f"version_in_{config_key}"
        incoming_edge = {
            "_key": incoming_edge_key,
            "_from": proxy_in_id,
            "_to": software_id,
            "_fromType": "SoftwareProxyIn",
            "_toType": "Software",
            "created": orphaned_config['created'],
            "expired": NEVER_EXPIRES,
            "tenantId": orphaned_config['tenantId']
        }
        
        try:
            self.database.collection('hasVersion').insert(incoming_edge)
            print(f"    ✓ Created incoming edge: {incoming_edge_key}")
        except Exception as e:
            print(f"    ❌ Failed to create incoming edge: {e}")
            return {"status": "failed", "error": f"Incoming edge creation failed: {e}"}
        
        # Step 4: Create new hasVersion edge from current config to proxy_out
        outgoing_edge_key = f"version_out_{config_key}"
        outgoing_edge = {
            "_key": outgoing_edge_key,
            "_from": software_id,
            "_to": proxy_out_id,
            "_fromType": "Software",
            "_toType": "SoftwareProxyOut",
            "created": orphaned_config['created'],
            "expired": NEVER_EXPIRES,
            "tenantId": orphaned_config['tenantId']
        }
        
        try:
            self.database.collection('hasVersion').insert(outgoing_edge)
            print(f"    ✓ Created outgoing edge: {outgoing_edge_key}")
        except Exception as e:
            print(f"    ❌ Failed to create outgoing edge: {e}")
            return {"status": "failed", "error": f"Outgoing edge creation failed: {e}"}
        
        return {
            "status": "success",
            "config_key": config_key,
            "base_software": base_name,
            "removed_incoming_edges": len(removed_incoming),
            "removed_outgoing_edges": len(removed_outgoing),
            "created_incoming_edge": incoming_edge_key,
            "created_outgoing_edge": outgoing_edge_key
        }
    
    def fix_all_orphaned_configurations(self) -> Dict[str, Any]:
        """Fix all orphaned configurations in the database."""
        print("\n🔧 FIXING ORPHANED CONFIGURATIONS")
        print("=" * 60)
        
        # Get orphaned configurations
        orphan_analysis = self.identify_orphaned_configurations()
        
        if "error" in orphan_analysis:
            return orphan_analysis
        
        orphaned_configs = orphan_analysis['orphaned_details']
        
        if not orphaned_configs:
            print("✅ No orphaned configurations found!")
            return {"status": "success", "fixed_count": 0, "message": "No orphans to fix"}
        
        print(f"Found {len(orphaned_configs)} orphaned configurations:")
        for config in orphaned_configs:
            sim_status = "SIMULATED" if config['isSimulated'] else "ORIGINAL"
            print(f"  {config['key']} ({sim_status})")
        print()
        
        # Fix each orphaned configuration
        fix_results = []
        success_count = 0
        
        for config in orphaned_configs:
            result = self.fix_orphaned_configuration(config)
            fix_results.append(result)
            
            if result.get("status") == "success":
                success_count += 1
                print(f"    ✅ Fixed successfully")
            else:
                print(f"    ❌ Fix failed: {result.get('error', 'Unknown error')}")
            print()
        
        return {
            "status": "completed",
            "total_orphaned": len(orphaned_configs),
            "fixed_count": success_count,
            "failed_count": len(orphaned_configs) - success_count,
            "fix_details": fix_results
        }
    
    def verify_fix(self) -> Dict[str, Any]:
        """Verify that all configurations are properly connected."""
        print("\n✅ VERIFYING FIX")
        print("=" * 60)
        
        # Re-run orphan analysis
        verification = self.identify_orphaned_configurations()
        
        if "error" in verification:
            return verification
        
        print(f"Post-fix analysis:")
        print(f"  Total current configurations: {verification['total_current_configs']}")
        print(f"  Connected configurations: {verification['connected_configs']}")
        print(f"  Orphaned configurations: {verification['orphaned_configs']}")
        print()
        
        if verification['orphaned_configs'] == 0:
            print("🎉 SUCCESS! All configurations are now properly connected.")
            
            # Test a specific configuration that was orphaned
            test_key = "ceed8203fdab_software1-0_sim_1758045639_528822"
            aql_test = f"""
            LET software_id = "Software/{test_key}"
            LET incoming = LENGTH(
                FOR edge IN hasVersion
                    FILTER edge._to == software_id
                    RETURN 1
            )
            LET outgoing = LENGTH(
                FOR edge IN hasVersion
                    FILTER edge._from == software_id
                    RETURN 1
            )
            RETURN {{
                software_key: "{test_key}",
                incoming_edges: incoming,
                outgoing_edges: outgoing,
                is_connected: incoming > 0 AND outgoing > 0
            }}
            """
            
            cursor = self.database.aql.execute(aql_test)
            test_results = list(cursor)
            
            if test_results:
                test = test_results[0]
                print(f"Test case - {test['software_key']}:")
                print(f"  Incoming edges: {test['incoming_edges']}")
                print(f"  Outgoing edges: {test['outgoing_edges']}")
                print(f"  Connected: {'✅' if test['is_connected'] else '❌'}")
        else:
            print(f"⚠️  {verification['orphaned_configs']} configurations still orphaned:")
            for config in verification['orphaned_details']:
                print(f"    {config['key']}")
        
        return verification

def main():
    """Main function to fix transaction simulation bug."""
    print("Transaction Simulation Bug Fix Tool")
    print("=" * 70)
    print("This tool fixes the critical bug where transaction simulation")
    print("creates orphaned Software configurations not connected via hasVersion edges.")
    print()
    
    fixer = TransactionSimulationBugFixer()
    
    # Step 1: Identify orphaned configurations
    orphan_analysis = fixer.identify_orphaned_configurations()
    
    if "error" in orphan_analysis:
        print(f"[ERROR] {orphan_analysis['error']}")
        return 1
    
    print(f"📊 ANALYSIS RESULTS:")
    print(f"   Total current configurations: {orphan_analysis['total_current_configs']}")
    print(f"   Connected configurations: {orphan_analysis['connected_configs']}")
    print(f"   Orphaned configurations: {orphan_analysis['orphaned_configs']}")
    print()
    
    if orphan_analysis['orphaned_configs'] == 0:
        print("✅ No orphaned configurations found! System is healthy.")
        return 0
    
    # Show examples of orphaned configs
    print("🐛 ORPHANED CONFIGURATIONS:")
    for config in orphan_analysis['orphaned_details'][:5]:
        sim_status = "SIMULATED" if config['isSimulated'] else "ORIGINAL"
        print(f"   {config['key']} ({sim_status})")
        print(f"     Incoming edges: {config['incoming_edges']}")
        print(f"     Outgoing edges: {config['outgoing_edges']}")
    
    if len(orphan_analysis['orphaned_details']) > 5:
        remaining = len(orphan_analysis['orphaned_details']) - 5
        print(f"   ... and {remaining} more")
    print()
    
    # Ask user for confirmation
    response = input("Do you want to fix these orphaned configurations? (y/N): ").strip().lower()
    if not response.startswith('y'):
        print("Fix cancelled by user.")
        return 0
    
    # Step 2: Fix orphaned configurations
    fix_results = fixer.fix_all_orphaned_configurations()
    
    if "error" in fix_results:
        print(f"[ERROR] {fix_results['error']}")
        return 1
    
    print(f"🔧 FIX RESULTS:")
    print(f"   Total orphaned: {fix_results['total_orphaned']}")
    print(f"   Successfully fixed: {fix_results['fixed_count']}")
    print(f"   Failed to fix: {fix_results['failed_count']}")
    print()
    
    # Step 3: Verify fix
    verification = fixer.verify_fix()
    
    if "error" in verification:
        print(f"[ERROR] {verification['error']}")
        return 1
    
    if verification['orphaned_configs'] == 0:
        print("🎉 ALL ORPHANED CONFIGURATIONS FIXED!")
        print("   The transaction simulation bug has been resolved.")
        print("   All Software configurations are now properly connected.")
        return 0
    else:
        print("❌ Some configurations are still orphaned.")
        print("   Manual investigation may be required.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
