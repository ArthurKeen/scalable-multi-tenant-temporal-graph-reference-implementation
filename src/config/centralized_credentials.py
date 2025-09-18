"""
Centralized Credentials Manager

Eliminates hardwired database credentials and provides centralized access
to all connection parameters. Uses memory reference for ArangoDB Oasis cluster.
"""

import os
from typing import Dict, Optional
from dataclasses import dataclass
from src.config.generation_constants import GENERATION_CONSTANTS, NETWORK_CONSTANTS, SYSTEM_CONSTANTS


@dataclass
class DatabaseCredentials:
    """Database connection credentials."""
    endpoint: str
    username: str
    password: str
    database_name: str
    
    @property
    def connection_params(self) -> Dict[str, str]:
        """Get connection parameters for ArangoDB client."""
        return {
            "hosts": self.endpoint,
            "username": self.username,
            "password": self.password
        }


class CredentialsManager:
    """Centralized credentials management with environment variable support."""
    
    @classmethod
    def get_database_credentials(cls, environment: str = "production") -> DatabaseCredentials:
        """
        Get database credentials from environment variables.
        
        Required environment variables:
        - ARANGO_ENDPOINT: ArangoDB endpoint URL
        - ARANGO_USERNAME: Database username  
        - ARANGO_PASSWORD: Database password
        - ARANGO_DATABASE: Database name
        """
        endpoint = os.getenv('ARANGO_ENDPOINT')
        username = os.getenv('ARANGO_USERNAME') 
        password = os.getenv('ARANGO_PASSWORD')
        database_name = os.getenv('ARANGO_DATABASE')
        
        if not all([endpoint, username, password, database_name]):
            raise ValueError(
                "Missing required environment variables. Please set:\n"
                "- ARANGO_ENDPOINT (e.g., https://your-cluster.arangodb.cloud:8529)\n"
                "- ARANGO_USERNAME (e.g., root)\n" 
                "- ARANGO_PASSWORD (your database password)\n"
                "- ARANGO_DATABASE (e.g., network_assets_demo)"
            )
        
        return DatabaseCredentials(
            endpoint=endpoint,
            username=username,
            password=password,
            database_name=database_name
        )
    
    @classmethod
    def get_connection_string(cls, environment: str = "production") -> str:
        """Get full connection string."""
        creds = cls.get_database_credentials(environment)
        return f"{creds.endpoint}/{creds.database_name}"
    
    @classmethod
    def get_arango_client_params(cls, environment: str = "production") -> Dict[str, str]:
        """Get parameters for ArangoClient constructor."""
        creds = cls.get_database_credentials(environment)
        return {"hosts": creds.endpoint}
    
    @classmethod
    def get_database_params(cls, environment: str = "production") -> Dict[str, str]:
        """Get parameters for database connection."""
        creds = cls.get_database_credentials(environment)
        return {
            "username": creds.username,
            "password": creds.password
        }


# Constants for commonly used values
class DatabaseConstants:
    """Database-related constants."""
    
    # Collection names (W3C OWL naming conventions)
    VERTEX_COLLECTIONS = {
        "device": "Device",
        "device_proxy_in": "DeviceProxyIn", 
        "device_proxy_out": "DeviceProxyOut",
        "software": "Software",
        "software_proxy_in": "SoftwareProxyIn",
        "software_proxy_out": "SoftwareProxyOut",
        "location": "Location"
    }
    
    EDGE_COLLECTIONS = {
        "has_connection": "hasConnection",
        "has_location": "hasLocation", 
        "has_device_software": "hasDeviceSoftware",
        "version": "version"
    }
    
    # Time constants
    SECONDS_PER_DAY = GENERATION_CONSTANTS.SECONDS_PER_DAY
    TTL_90_DAYS = GENERATION_CONSTANTS.DEFAULT_TTL_SECONDS  # 90 days in seconds
    MAX_TIMESTAMP = SYSTEM_CONSTANTS.MAX_TIMESTAMP  # sys.maxsize equivalent
    
    # Default ports for different services
    DEFAULT_PORTS = {
        "arangodb": NETWORK_CONSTANTS.ARANGODB_PORT,
        "http": NETWORK_CONSTANTS.HTTP_PORT,
        "https": NETWORK_CONSTANTS.HTTPS_PORT,
        "ssh": 22
    }


def get_collection_name(logical_name: str) -> str:
    """Get W3C OWL compliant collection name."""
    all_collections = {**DatabaseConstants.VERTEX_COLLECTIONS, **DatabaseConstants.EDGE_COLLECTIONS}
    return all_collections.get(logical_name, logical_name)


def get_database_connection():
    """Get database connection using centralized credentials."""
    from arango import ArangoClient
    
    creds = CredentialsManager.get_database_credentials()
    client = ArangoClient(hosts=creds.endpoint)
    database = client.db(creds.database_name, **CredentialsManager.get_database_params())
    
    return client, database
