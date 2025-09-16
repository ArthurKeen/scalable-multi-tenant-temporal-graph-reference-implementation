"""
TTL Configuration Constants

Centralized constants for TTL time travel implementation to eliminate
hardwired values and ensure consistency across all modules.
"""

import sys
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class TTLConstants:
    """Centralized TTL configuration constants."""
    
    # TTL Timing Configuration
    DEFAULT_TTL_EXPIRE_DAYS: int = 30
    DEFAULT_TTL_EXPIRE_SECONDS: int = 30 * 24 * 60 * 60  # 30 days in seconds
    
    # Demo-specific TTL Configuration (shorter periods for visible aging)
    DEMO_TTL_EXPIRE_MINUTES: int = 10  # 10 minutes for demo
    DEMO_TTL_EXPIRE_SECONDS: int = 10 * 60  # 600 seconds
    
    # Timestamp Constants
    NEVER_EXPIRES: int = sys.maxsize
    MAX_TIMESTAMP: int = sys.maxsize
    
    # TTL Index Configuration
    TTL_SELECTIVITY_ESTIMATE: float = 0.1  # ~10% of documents are historical
    TTL_SPARSE_INDEX: bool = True  # Skip documents where expired = sys.maxsize
    
    # Demo and Simulation Constants
    DEMO_TIME_BUFFER_SECONDS: int = 30  # Buffer for time travel queries
    SIMULATION_SLEEP_SECONDS: int = 1   # Sleep between simulated changes
    
    # Transaction Simulation Ranges
    DEVICE_VERSION_MINOR_MIN: int = 2
    DEVICE_VERSION_MINOR_MAX: int = 9
    DEVICE_VERSION_MAJOR_MIN: int = 2
    DEVICE_VERSION_MAJOR_MAX: int = 5
    
    SOFTWARE_PORT_UPDATE_MIN: int = 8000
    SOFTWARE_PORT_UPDATE_MAX: int = 9999
    SOFTWARE_PORT_MAJOR_MIN: int = 3000
    SOFTWARE_PORT_MAJOR_MAX: int = 7999
    
    # Default Simulation Counts
    DEFAULT_DEVICE_SIMULATION_COUNT: int = 3
    DEFAULT_SOFTWARE_SIMULATION_COUNT: int = 3
    DEFAULT_UPGRADE_SEQUENCE_COUNT: int = 3


@dataclass
class TTLMessages:
    """Standardized messages for TTL operations."""
    
    # Status Messages
    TTL_ENABLED: str = "TTL enabled for historical documents"
    TTL_DISABLED: str = "TTL disabled"
    CURRENT_CONFIG_PRESERVED: str = "Current configuration preserved (never expires)"
    HISTORICAL_CONFIG_AGING: str = "Historical configuration subject to TTL aging"
    
    # Operation Messages
    CONFIG_CONVERTED_TO_HISTORICAL: str = "Configuration converted to historical"
    NEW_CURRENT_CONFIG_CREATED: str = "New current configuration created"
    TTL_INDEX_CREATED: str = "TTL index created"
    TIME_TRAVEL_QUERY_EXECUTED: str = "Time travel query executed"
    
    # Error Messages
    TTL_CONFIG_ERROR: str = "Failed to configure TTL"
    SIMULATION_ERROR: str = "Transaction simulation failed"
    TIME_TRAVEL_ERROR: str = "Time travel query failed"


class TTLConfigurationFactory:
    """Factory for creating consistent TTL configurations."""
    
    @staticmethod
    def create_ttl_config_params(tenant_id: str, 
                                expire_after_days: int = None) -> Dict[str, Any]:
        """Create standardized TTL configuration parameters."""
        if expire_after_days is None:
            expire_after_days = TTLConstants.DEFAULT_TTL_EXPIRE_DAYS
        
        return {
            "tenant_id": tenant_id,
            "expire_after_days": expire_after_days,
            "expire_after_seconds": expire_after_days * 24 * 60 * 60,
            "never_expires_value": TTLConstants.NEVER_EXPIRES,
            "selectivity_estimate": TTLConstants.TTL_SELECTIVITY_ESTIMATE,
            "sparse_index": TTLConstants.TTL_SPARSE_INDEX
        }
    
    @staticmethod
    def get_simulation_ranges() -> Dict[str, Dict[str, int]]:
        """Get standardized simulation value ranges."""
        return {
            "device_version_minor": {
                "min": TTLConstants.DEVICE_VERSION_MINOR_MIN,
                "max": TTLConstants.DEVICE_VERSION_MINOR_MAX
            },
            "device_version_major": {
                "min": TTLConstants.DEVICE_VERSION_MAJOR_MIN,
                "max": TTLConstants.DEVICE_VERSION_MAJOR_MAX
            },
            "software_port_update": {
                "min": TTLConstants.SOFTWARE_PORT_UPDATE_MIN,
                "max": TTLConstants.SOFTWARE_PORT_UPDATE_MAX
            },
            "software_port_major": {
                "min": TTLConstants.SOFTWARE_PORT_MAJOR_MIN,
                "max": TTLConstants.SOFTWARE_PORT_MAJOR_MAX
            }
        }
    
    @staticmethod
    def get_default_simulation_counts() -> Dict[str, int]:
        """Get default simulation counts."""
        return {
            "devices": TTLConstants.DEFAULT_DEVICE_SIMULATION_COUNT,
            "software": TTLConstants.DEFAULT_SOFTWARE_SIMULATION_COUNT,
            "upgrade_sequence": TTLConstants.DEFAULT_UPGRADE_SEQUENCE_COUNT
        }


class TTLUtilities:
    """Common utility functions for TTL operations."""
    
    @staticmethod
    def is_current_configuration(document: Dict[str, Any]) -> bool:
        """Check if a document represents a current configuration."""
        expired_value = document.get("expired", TTLConstants.NEVER_EXPIRES)
        return expired_value == TTLConstants.NEVER_EXPIRES
    
    @staticmethod
    def is_historical_configuration(document: Dict[str, Any]) -> bool:
        """Check if a document represents a historical configuration."""
        return not TTLUtilities.is_current_configuration(document)
    
    @staticmethod
    def format_ttl_status_message(ttl_enabled: bool, expire_days: int) -> str:
        """Format standardized TTL status message."""
        if ttl_enabled:
            return f"TTL enabled: Historical data expires after {expire_days} days, current data never expires"
        else:
            return "TTL disabled: All data preserved indefinitely"
    
    @staticmethod
    def calculate_ttl_expire_time(created_timestamp: float, expire_days: int) -> float:
        """Calculate when a document will expire via TTL."""
        return created_timestamp + (expire_days * 24 * 60 * 60)


# Export commonly used constants for easy import
DEFAULT_TTL_DAYS = TTLConstants.DEFAULT_TTL_EXPIRE_DAYS
NEVER_EXPIRES = TTLConstants.NEVER_EXPIRES
TTL_SELECTIVITY = TTLConstants.TTL_SELECTIVITY_ESTIMATE

# Export factory and utilities
ttl_factory = TTLConfigurationFactory()
ttl_utils = TTLUtilities()
ttl_messages = TTLMessages()


if __name__ == "__main__":
    # Test the constants and utilities
    print("TTL Constants Test:")
    print(f"  Default TTL Days: {TTLConstants.DEFAULT_TTL_EXPIRE_DAYS}")
    print(f"  Never Expires Value: {TTLConstants.NEVER_EXPIRES}")
    print(f"  TTL Selectivity: {TTLConstants.TTL_SELECTIVITY_ESTIMATE}")
    
    print("\nTTL Configuration Factory Test:")
    config_params = ttl_factory.create_ttl_config_params("test_tenant")
    print(f"  Config Params: {config_params}")
    
    print("\nTTL Utilities Test:")
    current_doc = {"_key": "test", "expired": NEVER_EXPIRES}
    historical_doc = {"_key": "test_v1", "expired": 1672531200}
    
    print(f"  Current doc is current: {ttl_utils.is_current_configuration(current_doc)}")
    print(f"  Historical doc is current: {ttl_utils.is_current_configuration(historical_doc)}")
    print(f"  Status message: {ttl_utils.format_ttl_status_message(True, 30)}")
