#!/usr/bin/env python3
"""
Data Generation Constants

Centralized constants for data generation to eliminate hardwired values
and provide a single source of truth for all generation parameters.
"""

from dataclasses import dataclass
from typing import Dict, List, Any
import sys


@dataclass
class GenerationConstants:
    """Centralized constants for data generation."""
    
    # Port Ranges
    DYNAMIC_PORT_MIN: int = 1000
    DYNAMIC_PORT_MAX: int = 9000
    SOFTWARE_PORT_MIN: int = 8000
    SOFTWARE_PORT_MAX: int = 9000
    
    # Network Configuration
    IP_SUBNET_BASE: str = "192.168"
    IP_RANGE_MIN: int = 1
    IP_RANGE_MAX: int = 254
    
    # Performance Metrics
    BANDWIDTH_MIN: int = 10
    BANDWIDTH_MAX: int = 1000
    
    # Model and Hostname Ranges
    MODEL_NUMBER_MIN: int = 100
    MODEL_NUMBER_MAX: int = 999
    HOSTNAME_NUMBER_MIN: int = 100
    HOSTNAME_NUMBER_MAX: int = 999
    
    # Generation Limits
    MAX_GENERATION_RETRIES: int = 100
    MAX_TENANT_COUNT: int = 100
    MAX_DOCUMENTS_PER_COLLECTION: int = 10000
    BULK_INSERT_BATCH_SIZE: int = 1000
    
    # TTL Configuration (in seconds)
    DEFAULT_TTL_SECONDS: int = 7776000  # 90 days
    SHORT_TTL_SECONDS: int = 2592000    # 30 days
    LONG_TTL_SECONDS: int = 31536000    # 365 days
    
    # Time Constants
    SECONDS_PER_DAY: int = 86400
    SECONDS_PER_HOUR: int = 3600
    SECONDS_PER_MINUTE: int = 60
    
    # Default Firewall Rules
    DEFAULT_FIREWALL_RULES: List[str] = None
    
    def __post_init__(self):
        """Initialize default values that can't be set in dataclass definition."""
        if self.DEFAULT_FIREWALL_RULES is None:
            self.DEFAULT_FIREWALL_RULES = ["allow 80", "allow 443"]


@dataclass
class NetworkConstants:
    """Network-specific constants."""
    
    # Standard Ports
    HTTP_PORT: int = 80
    HTTPS_PORT: int = 443
    SSH_PORT: int = 22
    TELNET_PORT: int = 23
    FTP_PORT: int = 21
    ARANGODB_PORT: int = 8529
    
    # MAC Address Generation
    MAC_ADDRESS_SEGMENTS: int = 6
    MAC_ADDRESS_MAX_VALUE: int = 255
    MAC_ADDRESS_FORMAT: str = "{:02x}"


@dataclass
class SystemConstants:
    """System-wide constants."""
    
    # Maximum Values
    MAX_TIMESTAMP: int = sys.maxsize
    NEVER_EXPIRES: int = sys.maxsize
    
    # Success Rate Calculation
    PERCENTAGE_MULTIPLIER: int = 100
    
    # Test Configuration
    TEST_ITERATIONS_SMALL: int = 100
    TEST_ITERATIONS_LARGE: int = 1000
    PERFORMANCE_THRESHOLD_SECONDS: float = 1.0


@dataclass 
class DatabaseConstants:
    """Database configuration constants."""
    
    # Default database name (should be overridden by environment variable)
    DEFAULT_DATABASE_NAME: str = "network_assets_demo"
    
    # Graph names
    MAIN_GRAPH_NAME: str = "network_assets_graph"
    SATELLITE_GRAPH_NAME: str = "satellite_device_taxonomy"
    
    # Index naming patterns
    TTL_INDEX_PREFIX: str = "ttl_"
    MDI_INDEX_PREFIX: str = "mdi_"
    HASH_INDEX_PREFIX: str = "idx_"


@dataclass
class AlertConstants:
    """Alert system constants."""
    
    # Keywords to filter from alert names
    FILTERED_NAME_KEYWORDS: List[str] = None
    
    # Fallback names
    DEVICE_NAME_FALLBACK: str = "Device"
    SOFTWARE_NAME_FALLBACK: str = "Software"
    
    # Alert name format
    ALERT_NAME_FORMAT: str = "{severity} {alert_type}: {source_name}"
    
    def __post_init__(self):
        """Initialize filtered keywords list."""
        if self.FILTERED_NAME_KEYWORDS is None:
            self.FILTERED_NAME_KEYWORDS = ['proxy', 'out', 'in']


@dataclass
class LocationConstants:
    """Location and geographic constants."""
    
    # Default Locations with coordinates
    DEFAULT_LOCATIONS: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize default locations."""
        if self.DEFAULT_LOCATIONS is None:
            self.DEFAULT_LOCATIONS = [
                {"name": "New York Data Center", "address": "123 Broadway, New York, NY", "lat": 40.7128, "lon": -74.0060},
                {"name": "London Office", "address": "456 Oxford St, London", "lat": 51.5074, "lon": -0.1278},
                {"name": "Tokyo HQ", "address": "789 Ginza, Tokyo", "lat": 35.6895, "lon": 139.6917},
                {"name": "Sydney Warehouse", "address": "101 George St, Sydney", "lat": -33.8688, "lon": 151.2093},
                {"name": "Frankfurt Cloud Region", "address": "222 Mainzer Landstr, Frankfurt", "lat": 50.1109, "lon": 8.6821},
                {"name": "Singapore Hub", "address": "Marina Bay, Singapore", "lat": 1.2966, "lon": 103.8764},
                {"name": "Toronto Branch", "address": "Bay St, Toronto", "lat": 43.6532, "lon": -79.3832},
                {"name": "Mumbai Center", "address": "Nariman Point, Mumbai", "lat": 18.9220, "lon": 72.8347},
                {"name": "São Paulo Office", "address": "Av. Paulista, São Paulo", "lat": -23.5505, "lon": -46.6333},
                {"name": "Cape Town Hub", "address": "V&A Waterfront, Cape Town", "lat": -33.9025, "lon": 18.4167}
            ]


@dataclass
class OperatingSystemConstants:
    """Operating system constants."""
    
    # Device Operating Systems
    DEVICE_OPERATING_SYSTEMS: List[str] = None
    
    # Software Operating Systems
    SOFTWARE_OPERATING_SYSTEMS: List[str] = None
    
    def __post_init__(self):
        """Initialize operating system lists."""
        if self.DEVICE_OPERATING_SYSTEMS is None:
            self.DEVICE_OPERATING_SYSTEMS = [
                "Ubuntu 20.04.6 LTS",
                "CentOS 7.9.2009", 
                "Red Hat Enterprise Linux 8.8",
                "Windows Server 2019 Datacenter",
                "Windows 10 Enterprise LTSC 2021",
                "Windows Server 2022 Datacenter",
                "Debian 11.7",
                "SUSE Linux Enterprise Server 15 SP4"
            ]
        
        if self.SOFTWARE_OPERATING_SYSTEMS is None:
            self.SOFTWARE_OPERATING_SYSTEMS = [
                "Ubuntu 22.04.3 LTS",
                "Alpine Linux 3.18.3",
                "Embedded Linux 4.14.247", 
                "CentOS Stream 9",
                "Embedded Linux 5.4.188",
                "FreeBSD 13.2-RELEASE",
                "OpenWrt 22.03.5"
            ]


class GenerationUtilities:
    """Utility functions for data generation."""
    
    @staticmethod
    def get_ttl_config() -> Dict[str, int]:
        """Get TTL configuration dictionary."""
        constants = GenerationConstants()
        return {
            "default_ttl_seconds": constants.DEFAULT_TTL_SECONDS,
            "short_ttl_seconds": constants.SHORT_TTL_SECONDS,
            "long_ttl_seconds": constants.LONG_TTL_SECONDS
        }
    
    @staticmethod
    def get_port_ranges() -> Dict[str, Dict[str, int]]:
        """Get port range configuration."""
        constants = GenerationConstants()
        return {
            "dynamic": {
                "min": constants.DYNAMIC_PORT_MIN,
                "max": constants.DYNAMIC_PORT_MAX
            },
            "software": {
                "min": constants.SOFTWARE_PORT_MIN,
                "max": constants.SOFTWARE_PORT_MAX
            }
        }
    
    @staticmethod
    def get_generation_limits() -> Dict[str, int]:
        """Get generation limit configuration."""
        constants = GenerationConstants()
        return {
            "max_retries": constants.MAX_GENERATION_RETRIES,
            "max_tenants": constants.MAX_TENANT_COUNT,
            "max_documents": constants.MAX_DOCUMENTS_PER_COLLECTION,
            "batch_size": constants.BULK_INSERT_BATCH_SIZE
        }


class GenerationMessages:
    """Standardized messages for data generation."""
    
    GENERATION_START: str = "Starting data generation"
    GENERATION_COMPLETE: str = "Data generation completed successfully"
    GENERATION_FAILED: str = "Data generation failed"
    
    TENANT_CREATED: str = "Tenant configuration created"
    TENANT_DATA_GENERATED: str = "Tenant data generated"
    TENANT_VALIDATION_PASSED: str = "Tenant validation passed"
    
    COLLECTION_CREATED: str = "Collection created successfully"
    DOCUMENTS_INSERTED: str = "Documents inserted successfully"
    INDEXES_CREATED: str = "Indexes created successfully"
    
    PERFORMANCE_WARNING: str = "Performance threshold exceeded"
    RETRY_ATTEMPT: str = "Retrying generation attempt"
    MAX_RETRIES_EXCEEDED: str = "Maximum retries exceeded"


# Global instances for easy access
GENERATION_CONSTANTS = GenerationConstants()
NETWORK_CONSTANTS = NetworkConstants()
SYSTEM_CONSTANTS = SystemConstants()
LOCATION_CONSTANTS = LocationConstants()
OS_CONSTANTS = OperatingSystemConstants()


if __name__ == "__main__":
    # Test constants loading
    print("Testing generation constants...")
    
    print(f"Port ranges: {GENERATION_CONSTANTS.DYNAMIC_PORT_MIN}-{GENERATION_CONSTANTS.DYNAMIC_PORT_MAX}")
    print(f"TTL default: {GENERATION_CONSTANTS.DEFAULT_TTL_SECONDS} seconds")
    print(f"Max retries: {GENERATION_CONSTANTS.MAX_GENERATION_RETRIES}")
    print(f"Network ports: HTTP={NETWORK_CONSTANTS.HTTP_PORT}, HTTPS={NETWORK_CONSTANTS.HTTPS_PORT}")
    print(f"System max: {SYSTEM_CONSTANTS.MAX_TIMESTAMP}")
    print(f"Locations available: {len(LOCATION_CONSTANTS.DEFAULT_LOCATIONS)}")
    print(f"Device OS options: {len(OS_CONSTANTS.DEVICE_OPERATING_SYSTEMS)}")
    
    # Test utility functions
    ttl_config = GenerationUtilities.get_ttl_config()
    print(f"TTL config: {ttl_config}")
    
    port_ranges = GenerationUtilities.get_port_ranges()
    print(f"Port ranges: {port_ranges}")
    
    print("\n[SUCCESS] All generation constants loaded successfully!")
