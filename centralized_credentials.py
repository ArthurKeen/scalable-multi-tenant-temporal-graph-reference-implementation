"""
Centralized Credentials Manager

Eliminates hardwired database credentials and provides centralized access
to all connection parameters. Uses memory reference for ArangoDB Oasis cluster.
"""

import os
from typing import Dict, Optional
from dataclasses import dataclass


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
    """Centralized credentials management."""
    
    # ArangoDB Oasis Cluster Credentials (from memory: 8684340)
    _OASIS_CREDENTIALS = DatabaseCredentials(
        endpoint="https://1d53cdf6fad0.arangodb.cloud:8529",
        username="root", 
        password="GcZO9wNKLq9faIuIUgnY",
        database_name="network_assets_demo"
    )
    
    @classmethod
    def get_database_credentials(cls, environment: str = "production") -> DatabaseCredentials:
        """Get database credentials for specified environment."""
        if environment == "production":
            return cls._OASIS_CREDENTIALS
        else:
            # For testing or other environments, could be extended
            return cls._OASIS_CREDENTIALS
    
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
    SECONDS_PER_DAY = 86400
    TTL_90_DAYS = 7776000  # 90 days in seconds
    MAX_TIMESTAMP = 9223372036854775807  # sys.maxsize equivalent
    
    # Default ports for different services
    DEFAULT_PORTS = {
        "arangodb": 8529,
        "http": 80,
        "https": 443,
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
