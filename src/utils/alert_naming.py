#!/usr/bin/env python3
"""
Alert Naming Utilities

Centralized alert naming logic to eliminate duplication across
AlertGenerator and AlertSimulator modules.

Author: Scalable Multi-Tenant Temporal Graph Reference Implementation
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from src.config.generation_constants import AlertConstants


@dataclass
class AlertNamingConfig:
    """Configuration for alert naming behavior."""
    
    # Use centralized constants for consistency
    def __init__(self):
        self.alert_constants = AlertConstants()
        self.FILTERED_KEYWORDS = self.alert_constants.FILTERED_NAME_KEYWORDS
        self.DEVICE_FALLBACK = self.alert_constants.DEVICE_NAME_FALLBACK
        self.SOFTWARE_FALLBACK = self.alert_constants.SOFTWARE_NAME_FALLBACK
        self.NAME_FORMAT = self.alert_constants.ALERT_NAME_FORMAT


class AlertNamingUtility:
    """
    Centralized utility for generating consistent alert names across the system.
    
    Eliminates code duplication between AlertGenerator and AlertSimulator modules
    while providing consistent, visualization-friendly alert names.
    """
    
    def __init__(self, config: AlertNamingConfig = None):
        """Initialize with optional custom configuration."""
        self.config = config or AlertNamingConfig()
    
    def extract_meaningful_name(self, source_name: str, source_type: str) -> str:
        """
        Extract meaningful identifier from device/software proxy names.
        
        Args:
            source_name: Full name from proxy entity (e.g., "Digital Dynamics Router Model 819 proxy out")
            source_type: "device" or "software" for fallback selection
            
        Returns:
            Meaningful identifier (e.g., "819", "Router", "PostgreSQL")
        """
        if not source_name or source_name.lower() in ['unknown', 'unknown device', 'unknown software']:
            return self.config.DEVICE_FALLBACK if source_type == "device" else self.config.SOFTWARE_FALLBACK
        
        # Split name into parts and filter out keywords
        name_parts = source_name.split()
        meaningful_parts = [
            part for part in name_parts 
            if part.lower() not in self.config.FILTERED_KEYWORDS
        ]
        
        if meaningful_parts:
            # Prefer model numbers (numeric) or last meaningful part
            for part in reversed(meaningful_parts):
                if part.isdigit() or any(char.isdigit() for char in part):
                    return part
            # Fallback to last meaningful part
            return meaningful_parts[-1]
        else:
            # All parts were filtered out, use fallback
            return self.config.DEVICE_FALLBACK if source_type == "device" else self.config.SOFTWARE_FALLBACK
    
    def generate_alert_name(self, severity: str, alert_type: str, source_name: str, source_type: str) -> str:
        """
        Generate a complete alert name for visualization.
        
        Args:
            severity: Alert severity ("critical", "warning", "info")
            alert_type: Alert type ("hardware", "software", "security", "performance", "connectivity")
            source_name: Full name from proxy entity
            source_type: "device" or "software"
            
        Returns:
            Formatted alert name (e.g., "Critical Hardware: Router819")
        """
        meaningful_name = self.extract_meaningful_name(source_name, source_type)
        
        return self.config.NAME_FORMAT.format(
            severity=severity.title(),
            alert_type=alert_type.title(),
            source_name=meaningful_name
        )
    
    def generate_alert_name_from_template(self, severity_enum, alert_type_enum, source_name: str, source_type: str) -> str:
        """
        Generate alert name from enum values (for AlertGenerator compatibility).
        
        Args:
            severity_enum: AlertSeverity enum value
            alert_type_enum: AlertType enum value  
            source_name: Full name from proxy entity
            source_type: "device" or "software"
            
        Returns:
            Formatted alert name
        """
        return self.generate_alert_name(
            severity_enum.value,
            alert_type_enum.value,
            source_name,
            source_type
        )


# Global instance for easy access
alert_namer = AlertNamingUtility()


def create_alert_name(severity: str, alert_type: str, source_name: str, source_type: str) -> str:
    """
    Convenience function for creating alert names.
    
    Args:
        severity: Alert severity ("critical", "warning", "info")
        alert_type: Alert type ("hardware", "software", etc.)
        source_name: Full name from proxy entity
        source_type: "device" or "software"
        
    Returns:
        Formatted alert name for visualization
    """
    return alert_namer.generate_alert_name(severity, alert_type, source_name, source_type)


def extract_device_name(device_proxy_name: str) -> str:
    """
    Convenience function for extracting device names.
    
    Args:
        device_proxy_name: Full device proxy name
        
    Returns:
        Meaningful device identifier
    """
    return alert_namer.extract_meaningful_name(device_proxy_name, "device")


def extract_software_name(software_proxy_name: str) -> str:
    """
    Convenience function for extracting software names.
    
    Args:
        software_proxy_name: Full software proxy name
        
    Returns:
        Meaningful software identifier  
    """
    return alert_namer.extract_meaningful_name(software_proxy_name, "software")
