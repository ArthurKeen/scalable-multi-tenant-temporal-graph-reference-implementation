#!/usr/bin/env python3
"""
Fix Multiple Current Configurations Bug

This script identifies and fixes the bug where multiple software configurations
are marked as "current" (expired = NEVER_EXPIRES) for the same software entity.
"""

import sys
from centralized_credentials import CredentialsManager
from arango import ArangoClient
from ttl_constants import NEVER_EXPIRES, TTLConstants

class MultipleCurrentConfigsFixer:
    """Fix the multiple current configurations bug."""
    
    def __init__(self):
        """Initialize the fixer."""
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
    
    def diagnose_multiple_current_configs(self) -> dict:
        """Find software entities with multiple current configurations."""
        print("🔍 DIAGNOSING MULTIPLE CURRENT CONFIGURATIONS")
        print("=" * 60)
        
        if not self.connect_to_database():
            return {"error": "Failed to connect to database"}
        
        # Find software entities with multiple current configs
        aql_multiple_current = """
        FOR doc IN Software
            FILTER doc.expired == 9223372036854775807  // NEVER_EXPIRES
            COLLECT tenantId = doc.tenantId, 
                    softwareBase = REGEX_REPLACE(doc._key, "_sim_.*$", "")
                    WITH COUNT INTO currentCount
            FILTER currentCount > 1
            RETURN {
                tenantId: tenantId,
                softwareBase: softwareBase,
                currentCount: currentCount
            }
        """
        
        cursor = self.database.aql.execute(aql_multiple_current)
        multiple_current = list(cursor)
        
        # Get examples of problematic software
        examples = []
        for item in multiple_current[:5]:  # Show first 5 examples
            tenant_id = item['tenantId']
            software_base = item['softwareBase']
            
            aql_example = f"""
            FOR doc IN Software
                FILTER doc.tenantId == "{tenant_id}"
                FILTER REGEX_TEST(doc._key, "^{software_base}")
                SORT doc.created DESC
                RETURN {{
                    key: doc._key,
                    name: doc.name,
                    created: doc.created,
                    expired: doc.expired,
                    isCurrent: doc.expired == 9223372036854775807,
                    ttlExpireAt: HAS(doc, "ttlExpireAt") ? doc.ttlExpireAt : "NOT_SET"
                }}
            """
            
            cursor = self.database.aql.execute(aql_example)
            versions = list(cursor)
            
            examples.append({
                "tenant_id": tenant_id,
                "software_base": software_base,
                "versions": versions
            })
        
        return {
            "multiple_current_count": len(multiple_current),
            "examples": examples,
            "all_problematic": multiple_current
        }
    
    def fix_multiple_current_configs(self) -> dict:
        """Fix multiple current configurations by keeping newest, making others historical."""
        print("\n🔧 FIXING MULTIPLE CURRENT CONFIGURATIONS")
        print("=" * 60)
        
        if not self.database:
            if not self.connect_to_database():
                return {"error": "Failed to connect to database"}
        
        # Get all software entities with multiple current configs
        aql_get_problematic = """
        FOR doc IN Software
            FILTER doc.expired == 9223372036854775807  // NEVER_EXPIRES
            COLLECT tenantId = doc.tenantId, 
                    softwareBase = REGEX_REPLACE(doc._key, "_sim_.*$", "")
                    WITH COUNT INTO currentCount, 
                         AGGREGATE configs = doc
            FILTER currentCount > 1
            RETURN {
                tenantId: tenantId,
                softwareBase: softwareBase,
                currentCount: currentCount,
                configs: configs
            }
        """
        
        cursor = self.database.aql.execute(aql_get_problematic)
        problematic_software = list(cursor)
        
        fixed_count = 0
        fix_details = []
        
        for software_group in problematic_software:
            tenant_id = software_group['tenantId']
            software_base = software_group['softwareBase']
            configs = software_group['configs']
            
            # Sort by creation time, keep the newest as current
            configs_sorted = sorted(configs, key=lambda x: x['created'], reverse=True)
            newest_config = configs_sorted[0]
            older_configs = configs_sorted[1:]
            
            print(f"Fixing {software_base} (tenant: {tenant_id[:8]}...)")
            print(f"  Keeping as current: {newest_config['_key']}")
            print(f"  Making historical: {len(older_configs)} configs")
            
            # Make older configs historical
            for old_config in older_configs:
                # Update to historical status
                historical_timestamp = newest_config['created'] - 1  # Slightly before newest
                ttl_timestamp = historical_timestamp + TTLConstants.DEFAULT_TTL_EXPIRE_SECONDS
                
                update_result = self.database.collection('Software').update(
                    old_config['_key'],
                    {
                        'expired': historical_timestamp,
                        'ttlExpireAt': ttl_timestamp
                    }
                )
                
                fixed_count += 1
                fix_details.append({
                    'software_base': software_base,
                    'tenant_id': tenant_id,
                    'fixed_key': old_config['_key'],
                    'new_expired': historical_timestamp,
                    'new_ttl': ttl_timestamp,
                    'kept_current': newest_config['_key']
                })
                
                print(f"    Fixed: {old_config['_key']} → historical")
        
        return {
            "software_groups_fixed": len(problematic_software),
            "individual_configs_fixed": fixed_count,
            "fix_details": fix_details[:10]  # Show first 10 details
        }
    
    def verify_fix(self) -> dict:
        """Verify that no software has multiple current configurations."""
        print("\n✅ VERIFYING FIX")
        print("=" * 60)
        
        if not self.database:
            if not self.connect_to_database():
                return {"error": "Failed to connect to database"}
        
        # Check for remaining multiple current configs
        aql_check = """
        FOR doc IN Software
            FILTER doc.expired == 9223372036854775807  // NEVER_EXPIRES
            COLLECT tenantId = doc.tenantId, 
                    softwareBase = REGEX_REPLACE(doc._key, "_sim_.*$", "")
                    WITH COUNT INTO currentCount
            FILTER currentCount > 1
            RETURN {
                tenantId: tenantId,
                softwareBase: softwareBase,
                currentCount: currentCount
            }
        """
        
        cursor = self.database.aql.execute(aql_check)
        remaining_issues = list(cursor)
        
        # Get overall statistics
        aql_stats = """
        LET totalSoftware = LENGTH(FOR doc IN Software RETURN 1)
        LET currentConfigs = LENGTH(
            FOR doc IN Software 
                FILTER doc.expired == 9223372036854775807 
                RETURN 1
        )
        LET historicalConfigs = LENGTH(
            FOR doc IN Software 
                FILTER doc.expired != 9223372036854775807 
                RETURN 1
        )
        LET uniqueSoftwareEntities = LENGTH(
            FOR doc IN Software
                FILTER doc.expired == 9223372036854775807
                COLLECT tenantId = doc.tenantId, 
                        softwareBase = REGEX_REPLACE(doc._key, "_sim_.*$", "")
                RETURN 1
        )
        RETURN {
            totalSoftware: totalSoftware,
            currentConfigs: currentConfigs,
            historicalConfigs: historicalConfigs,
            uniqueSoftwareEntities: uniqueSoftwareEntities,
            ratio: currentConfigs / uniqueSoftwareEntities
        }
        """
        
        cursor = self.database.aql.execute(aql_stats)
        stats = list(cursor)[0]
        
        return {
            "remaining_multiple_current": len(remaining_issues),
            "fix_successful": len(remaining_issues) == 0,
            "stats": stats,
            "remaining_issues": remaining_issues[:5]
        }

def main():
    """Main function to fix multiple current configurations."""
    print("Multiple Current Configurations Fix Tool")
    print("=" * 70)
    print("This tool fixes the bug where multiple software configurations")
    print("are incorrectly marked as 'current' for the same software entity.")
    print()
    
    fixer = MultipleCurrentConfigsFixer()
    
    # Step 1: Diagnose
    diagnosis = fixer.diagnose_multiple_current_configs()
    
    if "error" in diagnosis:
        print(f"[ERROR] {diagnosis['error']}")
        return 1
    
    print(f"📊 DIAGNOSIS RESULTS:")
    print(f"   Software entities with multiple current configs: {diagnosis['multiple_current_count']}")
    print()
    
    if diagnosis['multiple_current_count'] == 0:
        print("✅ No multiple current configuration bugs detected!")
        return 0
    
    # Show examples
    print("🐛 EXAMPLES OF PROBLEMATIC SOFTWARE:")
    for example in diagnosis['examples'][:3]:
        tenant_short = example['tenant_id'][:8]
        print(f"\n   {example['software_base']} (tenant: {tenant_short}...):")
        current_count = 0
        historical_count = 0
        for version in example['versions']:
            if version['isCurrent']:
                current_count += 1
                print(f"     CURRENT: {version['key']} (created: {version['created']})")
            else:
                historical_count += 1
                if historical_count <= 2:  # Show first 2 historical
                    print(f"     historical: {version['key']} (expired: {version['expired']})")
        if historical_count > 2:
            print(f"     ... and {historical_count - 2} more historical versions")
        print(f"   → Problem: {current_count} current configs (should be 1)")
    
    # Step 2: Ask user if they want to fix
    response = input("\nDo you want to fix these multiple current configuration bugs? (y/N): ").strip().lower()
    if not response.startswith('y'):
        print("Fix cancelled by user.")
        return 0
    
    # Step 3: Fix
    fix_result = fixer.fix_multiple_current_configs()
    
    if "error" in fix_result:
        print(f"[ERROR] {fix_result['error']}")
        return 1
    
    print(f"\n🔧 FIX RESULTS:")
    print(f"   Software groups fixed: {fix_result['software_groups_fixed']}")
    print(f"   Individual configs fixed: {fix_result['individual_configs_fixed']}")
    print()
    
    # Step 4: Verify
    verification = fixer.verify_fix()
    
    if "error" in verification:
        print(f"[ERROR] {verification['error']}")
        return 1
    
    print(f"✅ VERIFICATION RESULTS:")
    print(f"   Fix successful: {verification['fix_successful']}")
    print(f"   Remaining issues: {verification['remaining_multiple_current']}")
    print(f"   Total software documents: {verification['stats']['totalSoftware']}")
    print(f"   Current configurations: {verification['stats']['currentConfigs']}")
    print(f"   Historical configurations: {verification['stats']['historicalConfigs']}")
    print(f"   Unique software entities: {verification['stats']['uniqueSoftwareEntities']}")
    print(f"   Current/Entity ratio: {verification['stats']['ratio']:.2f} (should be 1.0)")
    print()
    
    if verification['fix_successful']:
        print("🎉 Multiple current configurations bug successfully fixed!")
        print("   Each software entity now has exactly 1 current configuration")
        print("   All older configurations properly marked as historical with TTL")
    else:
        print("❌ Some issues remain - manual investigation needed")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
