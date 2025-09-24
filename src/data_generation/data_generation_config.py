"""
Data Generation Configuration

Centralized configuration for multi-tenant network asset generation.
Eliminates hard-coded values and provides consistent defaults.
"""

from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from src.config.generation_constants import GENERATION_CONSTANTS, NETWORK_CONSTANTS, LOCATION_CONSTANTS, OS_CONSTANTS


class DeviceType(Enum):
    """Device types with consistent string values."""
    SERVER = "server"
    ROUTER = "router"
    LAPTOP = "laptop"
    IOT = "IoT"
    FIREWALL = "firewall"


class ConnectionType(Enum):
    """Network connection types."""
    ETHERNET = "ethernet"
    WIFI = "wifi"
    FIBER = "fiber"


class SoftwareType(Enum):
    """Software categories."""
    APPLICATION = "application"
    DATABASE = "database"
    SERVICE = "service"


@dataclass
class NetworkConfig:
    """Network configuration constants."""
    # Default firewall rules
    DEFAULT_FIREWALL_RULES: List[str] = None
    
    # Port ranges
    DYNAMIC_PORT_MIN: int = GENERATION_CONSTANTS.DYNAMIC_PORT_MIN
    DYNAMIC_PORT_MAX: int = GENERATION_CONSTANTS.DYNAMIC_PORT_MAX
    SOFTWARE_PORT_MIN: int = GENERATION_CONSTANTS.SOFTWARE_PORT_MIN
    SOFTWARE_PORT_MAX: int = GENERATION_CONSTANTS.SOFTWARE_PORT_MAX
    
    # Network parameters
    IP_SUBNET_BASE: str = GENERATION_CONSTANTS.IP_SUBNET_BASE
    IP_RANGE_MIN: int = GENERATION_CONSTANTS.IP_RANGE_MIN
    IP_RANGE_MAX: int = GENERATION_CONSTANTS.IP_RANGE_MAX
    
    # Connection parameters
    BANDWIDTH_MIN: int = GENERATION_CONSTANTS.BANDWIDTH_MIN
    BANDWIDTH_MAX: int = GENERATION_CONSTANTS.BANDWIDTH_MAX
    LATENCY_MIN: int = 1
    LATENCY_MAX: int = 10
    
    def __post_init__(self):
        if self.DEFAULT_FIREWALL_RULES is None:
            self.DEFAULT_FIREWALL_RULES = GENERATION_CONSTANTS.DEFAULT_FIREWALL_RULES


@dataclass
class DataGenerationLimits:
    """Limits and constraints for data generation."""
    # Model number ranges
    MODEL_NUMBER_MIN: int = GENERATION_CONSTANTS.MODEL_NUMBER_MIN
    MODEL_NUMBER_MAX: int = GENERATION_CONSTANTS.MODEL_NUMBER_MAX
    
    # Hostname number ranges
    HOSTNAME_NUMBER_MIN: int = GENERATION_CONSTANTS.HOSTNAME_NUMBER_MIN
    HOSTNAME_NUMBER_MAX: int = GENERATION_CONSTANTS.HOSTNAME_NUMBER_MAX
    
    # Maximum retry attempts for unique generation
    MAX_GENERATION_RETRIES: int = GENERATION_CONSTANTS.MAX_GENERATION_RETRIES


# Device type configurations
DEVICE_OS_VERSIONS: Dict[DeviceType, List[str]] = {
    DeviceType.SERVER: OS_CONSTANTS.DEVICE_OPERATING_SYSTEMS,
    DeviceType.ROUTER: [
        "IOS XE 17.6.4a", 
        "JUNOS 21.2R3-S1",
        "IOS XE 17.9.3a",
        "JUNOS 22.1R1",
        "pfSense 2.6.0"
    ],
    DeviceType.LAPTOP: [
        "Windows 10 Pro 21H2", 
        "macOS Monterey 12.4", 
        "Ubuntu 22.04 LTS",
        "Windows 11 Pro 22H2",
        "macOS Ventura 13.2",
        "Fedora 37 Workstation"
    ],
    DeviceType.IOT: [
        "Embedded Linux 4.14.247", 
        "FreeRTOS 10.4.6",
        "Embedded Linux 5.4.188",
        "FreeRTOS 10.5.1",
        "Zephyr 3.2.0"
    ],
    DeviceType.FIREWALL: [
        "FortiOS 7.0.9", 
        "pfSense 2.5.2",
        "FortiOS 7.2.4",
        "pfSense 2.6.0",
        "OpnSense 22.7"
    ]
}

# Software configurations
SOFTWARE_VERSIONS: Dict[SoftwareType, List[str]] = {
    SoftwareType.APPLICATION: [
        "Apache HTTP Server 2.4.53", 
        "Nginx 1.22.0", 
        "Python 3.10.6",
        "Apache HTTP Server 2.4.57",
        "Nginx 1.24.0",
        "Python 3.11.3",
        "Node.js 18.16.0"
    ],
    SoftwareType.DATABASE: [
        "MySQL 8.0.30", 
        "PostgreSQL 14.5", 
        "MongoDB 6.0.2",
        "MySQL 8.0.33",
        "PostgreSQL 15.3",
        "MongoDB 6.0.6",
        "Redis 7.0.11"
    ],
    SoftwareType.SERVICE: [
        "OpenSSH 8.9p1", 
        "Docker 20.10.17", 
        "Kubernetes 1.25.2",
        "OpenSSH 9.3p1",
        "Docker 24.0.2",
        "Kubernetes 1.27.2",
        "Consul 1.15.3"
    ]
}

# Default location data (can be extended)
DEFAULT_LOCATIONS_DATA: List[Dict[str, Any]] = [
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

# SmartGraph configuration defaults
SMARTGRAPH_DEFAULTS: Dict[str, Any] = {
    "number_of_shards": 3,
    "replication_factor": 2,
    "orphan_collections": []
}

# TTL configuration defaults (in seconds)
TTL_DEFAULTS: Dict[str, int] = {
    "default_ttl_seconds": GENERATION_CONSTANTS.DEFAULT_TTL_SECONDS,  # 90 days
    "short_ttl_seconds": GENERATION_CONSTANTS.SHORT_TTL_SECONDS,      # 30 days
    "long_ttl_seconds": GENERATION_CONSTANTS.LONG_TTL_SECONDS         # 365 days
}

# Generation default sizes
GENERATION_DEFAULTS: Dict[str, int] = {
    "num_devices": 20,
    "num_locations": 5,
    "num_software": 30,
    "num_connections": 30,
    "num_has_software": 40,
    "num_config_changes": 5
}

# NOTE: Collection and file name definitions moved to src/config/config_management.py
# This eliminates duplication and provides single source of truth.
# Use ConfigurationManager.get_collection_name() and .get_file_name() instead.

# Shared database configuration - TODO: Move to environment variables
DATABASE_CONFIG: Dict[str, str] = {
    "shared_database_name": "network_assets_demo",
    "satellite_graph_name": "satellite_device_taxonomy"
}
