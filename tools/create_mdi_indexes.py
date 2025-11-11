#!/usr/bin/env python3
"""
Create MDI-Prefix Multi-Dimensional Indexes

This script creates MDI-prefixed indexes on temporal collections
for optimal time travel query performance.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arango import ArangoClient
from src.config.centralized_credentials import CredentialsManager


class MDIIndexCreator:
    """Create MDI-prefixed multi-dimensional indexes."""
    
    def __init__(self):
        self.creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=self.creds.endpoint)
        self.database = None
        
    def connect(self) -> bool:
        """Connect to database."""
        try:
            print(f"[CONNECT] Connecting to {self.creds.database_name}...")
            self.database = self.client.db(
                self.creds.database_name,
                **CredentialsManager.get_database_params()
            )
            version = self.database.version()
            print(f"[SUCCESS] Connected to ArangoDB {version}")
            return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False
    
    def check_mdi_support(self) -> bool:
        """Check if MDI indexes are supported."""
        try:
            # Try to get version info
            version_info = self.database.version()
            if isinstance(version_info, dict):
                version = version_info.get('version', '0.0.0')
                print(f"[INFO] ArangoDB version: {version}")
                
                # MDI indexes are available in ArangoDB 3.12+
                major, minor, _ = version.split('.')[:3]
                if int(major) >= 3 and int(minor) >= 12:
                    print(f"[SUCCESS] MDI indexes supported in version {version}")
                    return True
                else:
                    print(f"[WARNING] MDI indexes require ArangoDB 3.12+, found {version}")
                    print(f"[INFO] Will attempt to create with fallback to persistent indexes")
                    return False
            return True  # Assume support if we can't determine version
        except Exception as e:
            print(f"[WARNING] Could not check version: {e}")
            return True  # Assume support
    
    def create_mdi_index(self, collection_name: str, index_name: str, 
                          fields: list, field_value_types: str = "double") -> bool:
        """Create an MDI-prefixed multi-dimensional index."""
        try:
            if not self.database.has_collection(collection_name):
                print(f"[SKIP] Collection '{collection_name}' does not exist")
                return False
            
            collection = self.database.collection(collection_name)
            
            # Check if index already exists
            existing_indexes = collection.indexes()
            for idx in existing_indexes:
                if idx.get('name') == index_name:
                    print(f"[EXISTS] Index '{index_name}' already exists on {collection_name}")
                    if idx.get('type') == 'mdi' or idx.get('type') == 'mdi-prefixed':
                        print(f"[SUCCESS] MDI index already configured")
                        return True
                    else:
                        print(f"[WARNING] Existing index is type '{idx.get('type')}', not MDI")
                        # Delete and recreate
                        try:
                            collection.delete_index(idx['id'])
                            print(f"[DELETED] Removed non-MDI index")
                        except Exception as del_error:
                            print(f"[ERROR] Could not delete index: {del_error}")
                            return False
            
            # Try to create MDI-prefixed index
            print(f"[CREATE] Creating MDI index '{index_name}' on {collection_name}...")
            print(f"         Fields: {fields}")
            print(f"         Prefix: {fields[0]}")
            
            try:
                # Try with 'mdi-prefixed' type (ArangoDB 3.12+)
                index_result = collection.add_index({
                    'type': 'mdi-prefixed',
                    'fields': fields,
                    'name': index_name,
                    'fieldValueTypes': field_value_types,
                    'prefixFields': [fields[0]],  # Use first field as prefix
                    'unique': False,
                    'sparse': False
                })
                print(f"[SUCCESS] Created MDI-prefixed index: {index_name}")
                print(f"          Type: {index_result.get('type', 'unknown')}")
                return True
                
            except Exception as mdi_error:
                error_str = str(mdi_error)
                if 'unknown index type' in error_str.lower() or 'invalid index type' in error_str.lower():
                    print(f"[WARNING] MDI-prefixed indexes not supported: {mdi_error}")
                    print(f"[FALLBACK] Creating persistent index instead...")
                    
                    # Fallback to persistent index
                    index_result = collection.add_index({
                        'type': 'persistent',
                        'fields': fields,
                        'name': index_name,
                        'unique': False,
                        'sparse': False
                    })
                    print(f"[SUCCESS] Created persistent index as fallback: {index_name}")
                    return True
                else:
                    raise mdi_error
                    
        except Exception as e:
            print(f"[ERROR] Failed to create index '{index_name}' on {collection_name}: {e}")
            return False
    
    def create_all_mdi_indexes(self) -> bool:
        """Create all MDI indexes for temporal collections."""
        print("\n[START] Creating MDI-prefixed multi-dimensional indexes...")
        print("=" * 70)
        
        # Define MDI index configurations
        mdi_configs = [
            {
                "collection": "Device",
                "name": "idx_device_mdi_temporal",
                "fields": ["created", "expired"],
                "field_value_types": "double"
            },
            {
                "collection": "Software",
                "name": "idx_software_mdi_temporal",
                "fields": ["created", "expired"],
                "field_value_types": "double"
            },
            {
                "collection": "hasVersion",
                "name": "idx_version_mdi_temporal",
                "fields": ["created", "expired"],
                "field_value_types": "double"
            }
        ]
        
        success_count = 0
        total_count = len(mdi_configs)
        
        for config in mdi_configs:
            if self.create_mdi_index(
                config["collection"],
                config["name"],
                config["fields"],
                config.get("field_value_types", "double")
            ):
                success_count += 1
            print()  # Blank line between indexes
        
        print("=" * 70)
        print(f"[SUMMARY] Created {success_count}/{total_count} MDI indexes")
        
        if success_count == total_count:
            print(f"[SUCCESS] All MDI indexes created successfully!")
            return True
        elif success_count > 0:
            print(f"[PARTIAL] Some MDI indexes created")
            return True
        else:
            print(f"[ERROR] No MDI indexes were created")
            return False
    
    def verify_indexes(self) -> None:
        """Verify that indexes were created."""
        print("\n[VERIFY] Checking created indexes...")
        print("=" * 70)
        
        collections_to_check = ["Device", "Software", "hasVersion"]
        
        for collection_name in collections_to_check:
            if not self.database.has_collection(collection_name):
                print(f"[SKIP] {collection_name}: Collection does not exist")
                continue
            
            collection = self.database.collection(collection_name)
            indexes = collection.indexes()
            
            print(f"\n[COLLECTION] {collection_name}")
            print(f"   Total indexes: {len(indexes)}")
            
            # Look for MDI or temporal indexes
            mdi_found = False
            temporal_found = False
            
            for idx in indexes:
                idx_type = idx.get('type', 'unknown')
                idx_name = idx.get('name', 'unnamed')
                idx_fields = idx.get('fields', [])
                
                if 'mdi' in idx_type:
                    mdi_found = True
                    print(f"   [MDI] {idx_name}: {idx_type} on {idx_fields}")
                elif 'temporal' in idx_name.lower() or 'created' in str(idx_fields):
                    temporal_found = True
                    print(f"   [TEMPORAL] {idx_name}: {idx_type} on {idx_fields}")
            
            if mdi_found:
                print(f"   [STATUS] ✅ MDI indexes present")
            elif temporal_found:
                print(f"   [STATUS] ⚠️ Temporal indexes present (but not MDI)")
            else:
                print(f"   [STATUS] ❌ No temporal/MDI indexes found")
        
        print("\n" + "=" * 70)


def main():
    """Main execution function."""
    print("\n" + "=" * 70)
    print("MDI-Prefix Multi-Dimensional Index Creator")
    print("=" * 70)
    
    creator = MDIIndexCreator()
    
    # Connect to database
    if not creator.connect():
        print("\n[ERROR] Could not connect to database")
        return 1
    
    # Check MDI support
    creator.check_mdi_support()
    
    # Create indexes
    if not creator.create_all_mdi_indexes():
        print("\n[WARNING] Some indexes may not have been created")
        # Don't fail - verification will show what was created
    
    # Verify indexes
    creator.verify_indexes()
    
    print("\n[COMPLETE] MDI index creation process finished")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

