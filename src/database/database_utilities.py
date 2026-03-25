"""
Code Refactoring Utilities

Provides common utilities to eliminate duplicate code patterns:
- Database connection management
- Collection name utilities
- Query execution helpers
- Version edge creation
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from arango import ArangoClient
from arango.database import StandardDatabase
from pathlib import Path
import json

from src.config.centralized_credentials import CredentialsManager, get_collection_name

logger = logging.getLogger(__name__)


class DatabaseMixin:
    """
    Mixin class that provides standardized database connection functionality.
    
    Classes that inherit from this mixin get:
    - Consistent database connection patterns
    - Lazy initialization of client and database
    - Error handling for connection issues
    - Standardized credential management
    
    Usage:
        class MyClass(DatabaseMixin):
            def __init__(self):
                super().__init__()
                # Your initialization code
    """
    
    def __init__(self, environment: str = "production"):
        self.environment = environment
        self.creds = CredentialsManager.get_database_credentials(environment)
        self._client: Optional[ArangoClient] = None
        self._database: Optional[StandardDatabase] = None
    
    @property
    def client(self) -> ArangoClient:
        """Get ArangoDB client with lazy initialization."""
        if self._client is None:
            self._client = ArangoClient(hosts=self.creds.endpoint)
        return self._client
    
    @property
    def database(self) -> StandardDatabase:
        """Get database connection with lazy initialization."""
        if self._database is None:
            self._database = self.client.db(
                self.creds.database_name,
                **CredentialsManager.get_database_params(self.environment)
            )
        return self._database
    
    def connect_to_database(self) -> bool:
        """Connect to database and test connection."""
        try:
            self.database.version()
            return True
        except Exception as e:
            logger.error("Database connection failed: %s", e)
            return False
    
    def execute_aql(self, query: str, bind_vars: Optional[Dict] = None) -> List[Dict]:
        """Execute AQL query and return results."""
        try:
            return list(self.database.aql.execute(query, bind_vars=bind_vars or {}))
        except Exception as e:
            logger.error("Query failed: %s", e)
            return []
    
    def get_collection(self, logical_name: str):
        """Get collection by logical name."""
        collection_name = get_collection_name(logical_name)
        return self.database.collection(collection_name)


class QueryExecutor:
    """Common query execution functionality with optional query display."""
    
    @staticmethod
    def execute_and_display_query(database, query: str, query_name: str, bind_vars: Dict = None, show_queries: bool = False) -> List[Dict]:
        """Execute a query and display it with results if show_queries is enabled."""
        if show_queries:
            print(f"\n[QUERY] {query_name}:")
            print(f"   AQL: {query}")
            if bind_vars:
                print(f"   Variables: {bind_vars}")
        
        try:
            cursor = database.aql.execute(query, bind_vars=bind_vars)
            results = list(cursor)
            
            if show_queries:
                print(f"   Results: {len(results)} documents returned")
                if results and len(results) <= 3:
                    for i, result in enumerate(results[:3]):
                        if isinstance(result, dict):
                            sample = {k: v for k, v in result.items() if k in ['_key', '_id', 'name', 'type', 'created', 'expired']}
                            print(f"   Sample {i+1}: {sample}")
                        else:
                            print(f"   Sample {i+1}: {result}")
                elif results:
                    print(f"   (Large result set - showing count only)")
            
            return results
            
        except Exception as e:
            if show_queries:
                print(f"   [ERROR] Query failed: {e}")
            logger.error("Query '%s' failed: %s", query_name, e)
            return []


class DatabaseConnectionManager(DatabaseMixin):
    """
    Manages database connections and provides common operations.
    
    Extends DatabaseMixin with additional convenience methods for
    collection inspection and connection testing with verbose output.
    """
    
    def connect_and_test(self) -> bool:
        """Connect to database and test connection with status output."""
        try:
            version_info = self.database.version()
            print(f"[DONE] Connected to {self.creds.database_name}")
            if isinstance(version_info, dict):
                print(f"   Version: {version_info.get('version', 'Unknown')}")
            return True
        except Exception as e:
            logger.error("Connection failed: %s", e)
            print(f"[ERROR] Connection failed: {e}")
            return False
    
    def collection_exists(self, logical_name: str) -> bool:
        """Check if collection exists."""
        collection_name = get_collection_name(logical_name)
        return self.database.has_collection(collection_name)
    
    def get_collection_count(self, logical_name: str) -> int:
        """Get document count for collection."""
        if self.collection_exists(logical_name):
            return self.get_collection(logical_name).count()
        return 0


class QueryHelper:
    """Helper for common query patterns."""
    
    @staticmethod
    def time_travel_filter(time_param: str = "@point_in_time") -> str:
        """Get standard time travel filter."""
        return f"FILTER doc.created <= {time_param} AND doc.expired > {time_param}"
    
    @staticmethod
    def tenant_filter(tenant_attr: str) -> str:
        """Get tenant isolation filter."""
        return f"FILTER doc.{tenant_attr} == @tenant_id"
    
    @staticmethod
    def version_edge_query(from_type: str, to_type: str) -> str:
        """Get query for version edges between specific types."""
        return f"""
        FOR version IN version
          FILTER version._fromType == "{from_type}" AND version._toType == "{to_type}"
          RETURN version
        """
    
    @staticmethod
    def cross_entity_traversal(start_collection: str, edge_collection: str, end_collection: str) -> str:
        """
        Get template for cross-entity traversal.
        
        Note: AQL does not support bind variables for collection names, so
        f-string interpolation from trusted config values is the standard pattern.
        """
        return f"""
        WITH {start_collection}, {edge_collection}, {end_collection}
        FOR start IN {start_collection}
          FOR end IN 1..1 OUTBOUND start {edge_collection}
            FILTER end._collection == "{end_collection}"
            RETURN {{start, end}}
        """


class CollectionUtility:
    """Utilities for collection operations."""
    
    @staticmethod
    def get_all_collection_names() -> Dict[str, str]:
        """Get all logical to actual collection name mappings."""
        from src.config.config_management import get_config, NamingConvention
        config = get_config("production", NamingConvention.CAMEL_CASE)
        return {**config.get_all_vertex_collections(), **config.get_all_edge_collections()}
    
    @staticmethod
    def get_vertex_collections() -> Dict[str, str]:
        """Get vertex collection mappings."""
        from src.config.config_management import get_config, NamingConvention
        config = get_config("production", NamingConvention.CAMEL_CASE)
        return config.get_all_vertex_collections()
    
    @staticmethod
    def get_edge_collections() -> Dict[str, str]:
        """Get edge collection mappings."""
        from src.config.config_management import get_config, NamingConvention
        config = get_config("production", NamingConvention.CAMEL_CASE)
        return config.get_all_edge_collections()
    
    @staticmethod
    def is_proxy_collection(collection_name: str) -> bool:
        """Check if collection is a proxy collection."""
        proxy_suffixes = ["ProxyIn", "ProxyOut"]
        return any(collection_name.endswith(suffix) for suffix in proxy_suffixes)
    
    @staticmethod
    def get_proxy_collections() -> List[str]:
        """Get list of proxy collection names."""
        all_collections = CollectionUtility.get_all_collection_names()
        return [name for name in all_collections.values() if CollectionUtility.is_proxy_collection(name)]


class FileUtility:
    """Utilities for file operations."""
    
    @staticmethod
    def read_json_file(file_path: Path) -> Dict:
        """Read JSON file safely."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error reading %s: %s", file_path, e)
            return {}
    
    @staticmethod
    def write_json_file(file_path: Path, data: Any, indent: int = 2) -> bool:
        """Write JSON file safely."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent)
            return True
        except Exception as e:
            logger.error("Error writing %s: %s", file_path, e)
            return False
    
    @staticmethod
    def find_tenant_data_directories(data_dir: Path = Path("data")) -> List[Path]:
        """Find all tenant data directories."""
        if not data_dir.exists():
            return []
        
        return [d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("tenant_")]
    
    @staticmethod
    def get_collection_files_in_directory(directory: Path) -> Dict[str, Path]:
        """Get mapping of collection names to file paths in directory."""
        collection_files = {}
        all_collections = CollectionUtility.get_all_collection_names()
        
        for logical_name, collection_name in all_collections.items():
            file_path = directory / f"{collection_name}.json"
            if file_path.exists():
                collection_files[logical_name] = file_path
        
        return collection_files


class ValidationHelper:
    """Helper for validation operations."""
    
    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db_manager = db_manager
    
    def validate_collection_structure(self) -> Dict[str, bool]:
        """Validate all expected collections exist."""
        results = {}
        all_collections = CollectionUtility.get_all_collection_names()
        
        for logical_name, collection_name in all_collections.items():
            exists = self.db_manager.collection_exists(logical_name)
            count = self.db_manager.get_collection_count(logical_name) if exists else 0
            
            results[logical_name] = {
                "exists": exists,
                "count": count,
                "collection_name": collection_name
            }
            
            status = "[DONE]" if exists else "[ERROR]"
            print(f"   {status} {collection_name}: {count} documents")
        
        return results
    
    def validate_tenant_isolation(self, tenant_id: str) -> bool:
        """Validate tenant isolation for specific tenant."""
        query = """
        FOR doc IN Device
          FILTER doc.tenantId == @tenant_id
          LIMIT 1
          RETURN doc._key
        """
        
        results = self.db_manager.execute_aql(query, {
            "tenant_id": tenant_id
        })
        
        return len(results) > 0
    
    def validate_time_travel_pattern(self, collection_logical_name: str) -> Dict[str, int]:
        """
        Validate time travel pattern for collection.
        
        Note: AQL does not support bind variables for collection names, so
        f-string interpolation from trusted config values is the standard pattern.
        """
        collection_name = get_collection_name(collection_logical_name)
        
        query = f"""
        FOR doc IN {collection_name}
          FILTER doc.created != null AND doc.expired != null
          COLLECT WITH COUNT INTO count
          RETURN count
        """
        
        temporal_count = self.db_manager.execute_aql(query)
        
        return {
            "total_documents": self.db_manager.get_collection_count(collection_logical_name),
            "temporal_documents": temporal_count[0] if temporal_count else 0
        }


def get_database_manager(environment: str = "production") -> DatabaseConnectionManager:
    """Get configured database manager."""
    return DatabaseConnectionManager(environment)


def run_quick_validation(environment: str = "production") -> Dict[str, Any]:
    """Run quick validation of database structure."""
    db_manager = get_database_manager(environment)
    
    if not db_manager.connect_and_test():
        return {"connected": False}
    
    validator = ValidationHelper(db_manager)
    
    print("\n[ANALYSIS] Quick Database Validation:")
    collection_results = validator.validate_collection_structure()
    
    version_stats = validator.validate_time_travel_pattern("version")
    
    return {
        "connected": True,
        "collections": collection_results,
        "version_collection": version_stats
    }
