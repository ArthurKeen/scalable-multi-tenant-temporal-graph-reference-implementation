#!/usr/bin/env python3
"""
Taxonomy Constants and Class Hierarchies

Defines the device and software taxonomy hierarchies used for semantic classification
in the multi-tenant temporal graph system.

Author: Scalable Multi-Tenant Temporal Graph Reference Implementation
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum


class TaxonomyScope(Enum):
    """Taxonomy deployment scope options."""
    SHARED = "shared"  # Shared across all tenants
    TENANT_SPECIFIC = "tenant_specific"  # Each tenant has their own taxonomy
    HYBRID = "hybrid"  # Core shared + tenant extensions


@dataclass
class ClassDefinition:
    """Definition of a taxonomy class."""
    key: str
    name: str
    description: str
    category: str
    parent_class: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize default properties."""
        if self.properties is None:
            self.properties = {}


class DeviceTaxonomy:
    """Device classification hierarchy."""
    
    # Root categories
    ROOT_CLASSES = {
        "network_device": ClassDefinition(
            key="network_device",
            name="NetworkDevice", 
            description="Base class for all network devices",
            category="Infrastructure",
            properties={
                "hasNetworkInterface": True,
                "supportsRemoteManagement": True,
                "requiresIPAddress": True
            }
        ),
        "compute_device": ClassDefinition(
            key="compute_device",
            name="ComputeDevice",
            description="Base class for computing devices", 
            category="Infrastructure",
            properties={
                "hasCPU": True,
                "hasMemory": True,
                "hasStorage": True
            }
        ),
        "security_device": ClassDefinition(
            key="security_device", 
            name="SecurityDevice",
            description="Base class for security devices",
            category="Security",
            properties={
                "providesSecurityFunction": True,
                "supportsLogging": True,
                "hasSecurityPolicies": True
            }
        )
    }
    
    # Network device hierarchy
    NETWORK_CLASSES = {
        "router": ClassDefinition(
            key="router",
            name="Router",
            description="Network routing device",
            category="NetworkDevice", 
            parent_class="network_device",
            properties={
                "hasRoutingTable": True,
                "supportsProtocols": ["BGP", "OSPF", "RIP"],
                "forwardsPackets": True
            }
        ),
        "edge_router": ClassDefinition(
            key="edge_router",
            name="EdgeRouter", 
            description="Edge/border routing device",
            category="NetworkDevice",
            parent_class="router",
            properties={
                "connectsToISP": True,
                "supportsBGP": True,
                "hasWANInterface": True
            }
        ),
        "core_router": ClassDefinition(
            key="core_router",
            name="CoreRouter",
            description="Core network routing device", 
            category="NetworkDevice",
            parent_class="router",
            properties={
                "highThroughput": True,
                "supportsOSPF": True,
                "backboneDevice": True
            }
        ),
        "wireless_router": ClassDefinition(
            key="wireless_router",
            name="WirelessRouter",
            description="Wireless routing device",
            category="NetworkDevice", 
            parent_class="router",
            properties={
                "hasWiFiInterface": True,
                "supports802_11": True,
                "hasAntennas": True
            }
        ),
        "switch": ClassDefinition(
            key="switch",
            name="Switch",
            description="Network switching device",
            category="NetworkDevice",
            parent_class="network_device", 
            properties={
                "hasSwitchingTable": True,
                "supportsVLAN": True,
                "forwardsFrames": True
            }
        ),
        "l2_switch": ClassDefinition(
            key="l2_switch", 
            name="L2Switch",
            description="Layer 2 switching device",
            category="NetworkDevice",
            parent_class="switch",
            properties={
                "operatesAtLayer2": True,
                "learnsMAC": True,
                "supportsSpanningTree": True
            }
        ),
        "l3_switch": ClassDefinition(
            key="l3_switch",
            name="L3Switch", 
            description="Layer 3 switching device",
            category="NetworkDevice",
            parent_class="switch",
            properties={
                "operatesAtLayer3": True,
                "supportsRouting": True,
                "hasRoutingTable": True
            }
        ),
        "access_point": ClassDefinition(
            key="access_point",
            name="AccessPoint",
            description="Wireless access point",
            category="NetworkDevice",
            parent_class="network_device",
            properties={
                "providesWiFiAccess": True,
                "supports802_11": True,
                "hasPowerOverEthernet": True
            }
        ),
        "indoor_ap": ClassDefinition(
            key="indoor_ap",
            name="IndoorAP", 
            description="Indoor wireless access point",
            category="NetworkDevice",
            parent_class="access_point",
            properties={
                "indoorRated": True,
                "lowerPowerOutput": True,
                "aestheticDesign": True
            }
        ),
        "outdoor_ap": ClassDefinition(
            key="outdoor_ap",
            name="OutdoorAP",
            description="Outdoor wireless access point", 
            category="NetworkDevice",
            parent_class="access_point",
            properties={
                "weatherResistant": True,
                "higherPowerOutput": True,
                "ruggedDesign": True
            }
        )
    }
    
    # Security device hierarchy
    SECURITY_CLASSES = {
        "firewall": ClassDefinition(
            key="firewall",
            name="Firewall",
            description="Network firewall device",
            category="SecurityDevice",
            parent_class="security_device",
            properties={
                "filtersTraffic": True,
                "hasSecurityRules": True,
                "supportsStatefulInspection": True
            }
        ),
        "next_gen_firewall": ClassDefinition(
            key="next_gen_firewall",
            name="NextGenFirewall", 
            description="Next-generation firewall",
            category="SecurityDevice",
            parent_class="firewall",
            properties={
                "supportsApplicationInspection": True,
                "hasIntrusionPrevention": True,
                "supportsUserIdentification": True
            }
        ),
        "load_balancer": ClassDefinition(
            key="load_balancer",
            name="LoadBalancer",
            description="Network load balancing device",
            category="NetworkDevice",
            parent_class="network_device",
            properties={
                "distributesTraffic": True,
                "supportsHealthChecks": True,
                "providesHighAvailability": True
            }
        )
    }
    
    @classmethod
    def get_all_classes(cls) -> Dict[str, ClassDefinition]:
        """Get all device taxonomy classes."""
        all_classes = {}
        all_classes.update(cls.ROOT_CLASSES)
        all_classes.update(cls.NETWORK_CLASSES) 
        all_classes.update(cls.SECURITY_CLASSES)
        return all_classes


class SoftwareTaxonomy:
    """Software classification hierarchy."""
    
    # Root categories
    ROOT_CLASSES = {
        "software": ClassDefinition(
            key="software",
            name="Software",
            description="Base class for all software",
            category="Software",
            properties={
                "hasVersion": True,
                "requiresInstallation": True,
                "hasLicense": True
            }
        ),
        "system_software": ClassDefinition(
            key="system_software",
            name="SystemSoftware",
            description="Base class for system software",
            category="Software",
            parent_class="software",
            properties={
                "managesResources": True,
                "providesServices": True,
                "runsAtSystemLevel": True
            }
        ),
        "application_software": ClassDefinition(
            key="application_software", 
            name="ApplicationSoftware",
            description="Base class for application software",
            category="Software", 
            parent_class="software",
            properties={
                "providesUserInterface": True,
                "solvesSpecificProblem": True,
                "runsAtUserLevel": True
            }
        )
    }
    
    # Database hierarchy
    DATABASE_CLASSES = {
        "database": ClassDefinition(
            key="database",
            name="Database", 
            description="Database management system",
            category="SystemSoftware",
            parent_class="system_software",
            properties={
                "storesData": True,
                "supportsQueries": True,
                "providesACID": True
            }
        ),
        "relational_db": ClassDefinition(
            key="relational_db",
            name="RelationalDB",
            description="Relational database system",
            category="SystemSoftware",
            parent_class="database",
            properties={
                "supportsSQL": True,
                "hasTableStructure": True,
                "supportsJoins": True
            }
        ),
        "postgresql": ClassDefinition(
            key="postgresql",
            name="PostgreSQL",
            description="PostgreSQL relational database",
            category="SystemSoftware", 
            parent_class="relational_db",
            properties={
                "openSource": True,
                "supportsJSONB": True,
                "supportsExtensions": True
            }
        ),
        "mysql": ClassDefinition(
            key="mysql", 
            name="MySQL",
            description="MySQL relational database",
            category="SystemSoftware",
            parent_class="relational_db",
            properties={
                "openSource": True,
                "highPerformance": True,
                "widelyUsed": True
            }
        ),
        "nosql_db": ClassDefinition(
            key="nosql_db",
            name="NoSQLDB",
            description="NoSQL database system", 
            category="SystemSoftware",
            parent_class="database",
            properties={
                "schemaFlexible": True,
                "horizontallyScalable": True,
                "distributedArchitecture": True
            }
        ),
        "document_db": ClassDefinition(
            key="document_db",
            name="DocumentDB",
            description="Document-oriented database",
            category="SystemSoftware",
            parent_class="nosql_db",
            properties={
                "storesDocuments": True,
                "supportsJSON": True,
                "flexibleSchema": True
            }
        ),
        "mongodb": ClassDefinition(
            key="mongodb",
            name="MongoDB", 
            description="MongoDB document database",
            category="SystemSoftware",
            parent_class="document_db",
            properties={
                "supportsBSON": True,
                "supportsSharding": True,
                "hasAggregationFramework": True
            }
        ),
        "graph_db": ClassDefinition(
            key="graph_db",
            name="GraphDB",
            description="Graph database system",
            category="SystemSoftware",
            parent_class="nosql_db", 
            properties={
                "storesGraphs": True,
                "supportsTraversal": True,
                "optimizedForRelationships": True
            }
        )
    }
    
    # Web server hierarchy
    WEBSERVER_CLASSES = {
        "web_server": ClassDefinition(
            key="web_server",
            name="WebServer",
            description="Web server software",
            category="SystemSoftware",
            parent_class="system_software",
            properties={
                "servesHTTP": True,
                "supportsSSL": True,
                "servesStaticContent": True
            }
        ),
        "apache": ClassDefinition(
            key="apache",
            name="Apache",
            description="Apache HTTP Server", 
            category="SystemSoftware",
            parent_class="web_server",
            properties={
                "openSource": True,
                "supportsModules": True,
                "crossPlatform": True
            }
        ),
        "nginx": ClassDefinition(
            key="nginx", 
            name="Nginx",
            description="Nginx web server",
            category="SystemSoftware",
            parent_class="web_server",
            properties={
                "highPerformance": True,
                "supportsReverseProxy": True,
                "lowMemoryUsage": True
            }
        )
    }
    
    # Operating system hierarchy  
    OS_CLASSES = {
        "operating_system": ClassDefinition(
            key="operating_system",
            name="OperatingSystem",
            description="Operating system software",
            category="SystemSoftware", 
            parent_class="system_software",
            properties={
                "managesHardware": True,
                "providesAPI": True,
                "schedulesProcesses": True
            }
        ),
        "linux": ClassDefinition(
            key="linux",
            name="Linux",
            description="Linux operating system",
            category="SystemSoftware",
            parent_class="operating_system",
            properties={
                "openSource": True,
                "unixLike": True,
                "supportsMultiuser": True
            }
        ),
        "ubuntu": ClassDefinition(
            key="ubuntu", 
            name="Ubuntu",
            description="Ubuntu Linux distribution",
            category="SystemSoftware",
            parent_class="linux",
            properties={
                "debianBased": True,
                "userFriendly": True,
                "regularReleases": True
            }
        ),
        "windows": ClassDefinition(
            key="windows",
            name="Windows",
            description="Microsoft Windows operating system",
            category="SystemSoftware",
            parent_class="operating_system", 
            properties={
                "proprietary": True,
                "guiOriented": True,
                "widelyUsed": True
            }
        )
    }
    
    @classmethod
    def get_all_classes(cls) -> Dict[str, ClassDefinition]:
        """Get all software taxonomy classes."""
        all_classes = {}
        all_classes.update(cls.ROOT_CLASSES)
        all_classes.update(cls.DATABASE_CLASSES)
        all_classes.update(cls.WEBSERVER_CLASSES) 
        all_classes.update(cls.OS_CLASSES)
        return all_classes


@dataclass
class TaxonomyConstants:
    """Constants for taxonomy system configuration."""
    
    # Taxonomy deployment configuration
    DEFAULT_SCOPE: TaxonomyScope = TaxonomyScope.SHARED
    SHARED_TENANT_ID: str = "shared_taxonomy"
    
    # Class generation limits
    MAX_CLASSES_PER_TENANT: int = 1000
    MAX_HIERARCHY_DEPTH: int = 10
    
    # Classification confidence levels
    HIGH_CONFIDENCE: float = 1.0
    MEDIUM_CONFIDENCE: float = 0.8
    LOW_CONFIDENCE: float = 0.6
    
    # Temporal settings for taxonomy
    TAXONOMY_NEVER_EXPIRES: bool = True  # Taxonomy classes are persistent
    ALLOW_TAXONOMY_EVOLUTION: bool = True  # Classes can be updated over time


# Export commonly used constants
DEVICE_TAXONOMY = DeviceTaxonomy()
SOFTWARE_TAXONOMY = SoftwareTaxonomy()
TAXONOMY_CONSTANTS = TaxonomyConstants()


if __name__ == "__main__":
    # Test taxonomy definitions
    print("=== DEVICE TAXONOMY TEST ===")
    device_classes = DEVICE_TAXONOMY.get_all_classes()
    print(f"Total device classes: {len(device_classes)}")
    
    for key, class_def in device_classes.items():
        parent = f" (extends {class_def.parent_class})" if class_def.parent_class else " (root)"
        print(f"  {class_def.name}{parent}")
    
    print("\n=== SOFTWARE TAXONOMY TEST ===")
    software_classes = SOFTWARE_TAXONOMY.get_all_classes()
    print(f"Total software classes: {len(software_classes)}")
    
    for key, class_def in software_classes.items():
        parent = f" (extends {class_def.parent_class})" if class_def.parent_class else " (root)"
        print(f"  {class_def.name}{parent}")
    
    print(f"\n=== TAXONOMY STATISTICS ===")
    print(f"Device classes: {len(device_classes)}")
    print(f"Software classes: {len(software_classes)}")
    print(f"Total classes: {len(device_classes) + len(software_classes)}")
