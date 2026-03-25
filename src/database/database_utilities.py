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
            logger.info(f"\n[QUERY] {query_name}:")
            logger.info(f"   AQL: {query}")
            if bind_vars:
                logger.info(f"   Variables: {bind_vars}")
        
        try:
            cursor = database.aql.execute(query, bind_vars=bind_vars)
            results = list(cursor)
            
            if show_queries:
                logger.info(f"   Results: {len(results)} documents returned")
                if results and len(results) <= 3:
                    for i, result in enumerate(results[:3]):
                        if isinstance(result, dict):
                            sample = {k: v for k, v in result.items() if k in ['_key', '_id', 'name', 'type', 'created', 'expired']}
                            logger.info(f"   Sample {i+1}: {sample}")
                        else:
                            logger.info(f"   Sample {i+1}: {result}")
                elif results:
                    logger.info(f"   (Large result set - showing count only)")
            
            return results
            
        except Exception as e:
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
            logger.info(f"[DONE] Connected to {self.creds.database_name}")
            if isinstance(version_info, dict):
                logger.info(f"   Version: {version_info.get('version', 'Unknown')}")
            return True
        except Exception as e:
            logger.error("Connection failed: %s", e)
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


