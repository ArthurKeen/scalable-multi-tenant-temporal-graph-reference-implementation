#!/usr/bin/env python3
"""
TTL Bug Fix Script

This script identifies and fixes the TTL bug where current configurations
incorrectly have ttlExpireAt fields set.
"""

import sys
from pathlib import Path
from centralized_credentials import CredentialsManager
from arango import ArangoClient
from ttl_constants import NEVER_EXPIRES

class TTLBugFixer:
    """Diagnose and fix TTL field bugs."""
    
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
    
    def diagnose_ttl_issue(self) -> dict:
        """Diagnose the TTL issue in the current database."""
        print("🔍 DIAGNOSING TTL ISSUE")
        print("=" * 50)
        
        if not self.connect_to_database():
            return {"error": "Failed to connect to database"}
        
        # Check Software collection for TTL issues
        aql_current_with_ttl = """
        FOR doc IN Software
            FILTER doc.expired == 9223372036854775807  // NEVER_EXPIRES
            FILTER HAS(doc, 'ttlExpireAt')
            RETURN {
                key: doc._key,
                name: doc.name,
                expired: doc.expired,
                ttlExpireAt: doc.ttlExpireAt,
                tenantId: doc.tenantId
            }
        """
        
        cursor = self.database.aql.execute(aql_current_with_ttl)
        current_with_ttl = list(cursor)
        
        # Check for historical without TTL
        aql_historical_without_ttl = """
        FOR doc IN Software
            FILTER doc.expired != 9223372036854775807  // Not NEVER_EXPIRES
            FILTER !HAS(doc, 'ttlExpireAt')
            RETURN {
                key: doc._key,
                name: doc.name,
                expired: doc.expired,
                ttlExpireAt: "NOT_SET",
                tenantId: doc.tenantId
            }
        """
        
        cursor = self.database.aql.execute(aql_historical_without_ttl)
        historical_without_ttl = list(cursor)
        
        # Check all current configurations
        aql_all_current = """
        FOR doc IN Software
            FILTER doc.expired == 9223372036854775807
            COLLECT tenantId = doc.tenantId WITH COUNT INTO count
            RETURN {
                tenantId: tenantId,
                currentConfigs: count
            }
        """
        
        cursor = self.database.aql.execute(aql_all_current)
        current_by_tenant = list(cursor)
        
        # Check all historical configurations  
        aql_all_historical = """
        FOR doc IN Software
            FILTER doc.expired != 9223372036854775807
            COLLECT tenantId = doc.tenantId WITH COUNT INTO count
            RETURN {
                tenantId: tenantId,
                historicalConfigs: count
            }
        """
        
        cursor = self.database.aql.execute(aql_all_historical)
        historical_by_tenant = list(cursor)
        
        diagnosis = {
            "current_with_ttl_bug": len(current_with_ttl),
            "historical_without_ttl_bug": len(historical_without_ttl),
            "current_by_tenant": current_by_tenant,
            "historical_by_tenant": historical_by_tenant,
            "bug_examples": current_with_ttl[:5],  # Show first 5 examples
            "historical_missing_ttl": historical_without_ttl[:5]
        }
        
        return diagnosis
    
    def fix_ttl_bug(self) -> dict:
        """Fix the TTL bug by removing ttlExpireAt from current configurations."""
        print("\n🔧 FIXING TTL BUG")
        print("=" * 50)
        
        if not self.database:
            if not self.connect_to_database():
                return {"error": "Failed to connect to database"}
        
        # Fix 1: Remove ttlExpireAt from current configurations (expired = NEVER_EXPIRES)
        aql_fix_current = """
        FOR doc IN Software
            FILTER doc.expired == 9223372036854775807  // NEVER_EXPIRES
            FILTER HAS(doc, 'ttlExpireAt')
            UPDATE doc WITH { ttlExpireAt: null } IN Software
            OPTIONS { keepNull: false }
            RETURN {
                key: doc._key,
                name: doc.name,
                action: "removed_ttl_from_current"
            }
        """
        
        cursor = self.database.aql.execute(aql_fix_current)
        fixed_current = list(cursor)
        
        # Fix 2: Add ttlExpireAt to historical configurations that don't have it
        from ttl_constants import TTLConstants
        
        aql_fix_historical = f"""
        FOR doc IN Software
            FILTER doc.expired != 9223372036854775807  // Not NEVER_EXPIRES
            FILTER !HAS(doc, 'ttlExpireAt')
            UPDATE doc WITH {{ 
                ttlExpireAt: doc.expired + {TTLConstants.DEFAULT_TTL_EXPIRE_SECONDS}
            }} IN Software
            RETURN {{
                key: doc._key,
                name: doc.name,
                expired: doc.expired,
                newTtlExpireAt: doc.expired + {TTLConstants.DEFAULT_TTL_EXPIRE_SECONDS},
                action: "added_ttl_to_historical"
            }}
        """
        
        cursor = self.database.aql.execute(aql_fix_historical)
        fixed_historical = list(cursor)
        
        return {
            "current_configs_fixed": len(fixed_current),
            "historical_configs_fixed": len(fixed_historical),
            "current_examples": fixed_current[:3],
            "historical_examples": fixed_historical[:3]
        }
    
    def verify_fix(self) -> dict:
        """Verify that the TTL bug has been fixed."""
        print("\n✅ VERIFYING FIX")
        print("=" * 50)
        
        if not self.database:
            if not self.connect_to_database():
                return {"error": "Failed to connect to database"}
        
        # Check that no current configs have TTL
        aql_current_check = """
        FOR doc IN Software
            FILTER doc.expired == 9223372036854775807
            FILTER HAS(doc, 'ttlExpireAt')
            RETURN doc._key
        """
        
        cursor = self.database.aql.execute(aql_current_check)
        current_with_ttl = list(cursor)
        
        # Check that all historical configs have TTL
        aql_historical_check = """
        FOR doc IN Software
            FILTER doc.expired != 9223372036854775807
            FILTER !HAS(doc, 'ttlExpireAt')
            RETURN doc._key
        """
        
        cursor = self.database.aql.execute(aql_historical_check)
        historical_without_ttl = list(cursor)
        
        # Get summary counts
        aql_summary = """
        LET currentCount = LENGTH(
            FOR doc IN Software
                FILTER doc.expired == 9223372036854775807
                RETURN 1
        )
        LET historicalCount = LENGTH(
            FOR doc IN Software  
                FILTER doc.expired != 9223372036854775807
                RETURN 1
        )
        LET currentWithTtl = LENGTH(
            FOR doc IN Software
                FILTER doc.expired == 9223372036854775807
                FILTER HAS(doc, 'ttlExpireAt')
                RETURN 1
        )
        LET historicalWithTtl = LENGTH(
            FOR doc IN Software
                FILTER doc.expired != 9223372036854775807
                FILTER HAS(doc, 'ttlExpireAt')
                RETURN 1
        )
        RETURN {
            currentConfigs: currentCount,
            historicalConfigs: historicalCount,
            currentWithTtlBug: currentWithTtl,
            historicalWithTtlCorrect: historicalWithTtl
        }
        """
        
        cursor = self.database.aql.execute(aql_summary)
        summary = list(cursor)[0]
        
        verification = {
            "bug_fixed": len(current_with_ttl) == 0 and len(historical_without_ttl) == 0,
            "remaining_current_with_ttl": len(current_with_ttl),
            "remaining_historical_without_ttl": len(historical_without_ttl),
            "summary": summary
        }
        
        return verification

def main():
    """Main function to diagnose and fix TTL bug."""
    print("TTL Bug Diagnosis and Fix Tool")
    print("=" * 60)
    print("This tool identifies and fixes the TTL strategy bug where")
    print("current configurations incorrectly have ttlExpireAt fields.")
    print()
    
    fixer = TTLBugFixer()
    
    # Step 1: Diagnose
    diagnosis = fixer.diagnose_ttl_issue()
    
    if "error" in diagnosis:
        print(f"[ERROR] {diagnosis['error']}")
        return 1
    
    print(f"📊 DIAGNOSIS RESULTS:")
    print(f"   Current configs with TTL bug: {diagnosis['current_with_ttl_bug']}")
    print(f"   Historical configs missing TTL: {diagnosis['historical_without_ttl_bug']}")
    print()
    
    if diagnosis['current_with_ttl_bug'] > 0:
        print(f"🐛 BUG EXAMPLES (Current with TTL):")
        for example in diagnosis['bug_examples']:
            print(f"   {example['key']}: {example['name']} (ttlExpireAt: {example['ttlExpireAt']})")
        print()
    
    if diagnosis['current_with_ttl_bug'] == 0 and diagnosis['historical_without_ttl_bug'] == 0:
        print("✅ No TTL bugs detected! The system is working correctly.")
        return 0
    
    # Step 2: Ask user if they want to fix
    response = input("Do you want to fix these TTL bugs? (y/N): ").strip().lower()
    if not response.startswith('y'):
        print("Fix cancelled by user.")
        return 0
    
    # Step 3: Fix
    fix_result = fixer.fix_ttl_bug()
    
    if "error" in fix_result:
        print(f"[ERROR] {fix_result['error']}")
        return 1
    
    print(f"🔧 FIX RESULTS:")
    print(f"   Current configs fixed: {fix_result['current_configs_fixed']}")
    print(f"   Historical configs fixed: {fix_result['historical_configs_fixed']}")
    print()
    
    # Step 4: Verify
    verification = fixer.verify_fix()
    
    if "error" in verification:
        print(f"[ERROR] {verification['error']}")
        return 1
    
    print(f"✅ VERIFICATION RESULTS:")
    print(f"   Bug fixed: {verification['bug_fixed']}")
    print(f"   Current configs: {verification['summary']['currentConfigs']}")
    print(f"   Historical configs: {verification['summary']['historicalConfigs']}")
    print(f"   Current with TTL (should be 0): {verification['summary']['currentWithTtlBug']}")
    print(f"   Historical with TTL (should be all): {verification['summary']['historicalWithTtlCorrect']}")
    print()
    
    if verification['bug_fixed']:
        print("🎉 TTL bug successfully fixed!")
        print("   Current configurations: No ttlExpireAt field (never expire)")
        print("   Historical configurations: ttlExpireAt field set (will age out)")
    else:
        print("❌ TTL bug fix incomplete - manual investigation needed")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
