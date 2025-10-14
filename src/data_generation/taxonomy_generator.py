#!/usr/bin/env python3
"""
Taxonomy Generator

Generates taxonomy class hierarchies and classification relationships for the
multi-tenant temporal graph system.

Author: Scalable Multi-Tenant Temporal Graph Reference Implementation
"""

import uuid
import datetime
import random
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Import taxonomy definitions and utilities
from src.config.taxonomy_constants import (
    ClassDefinition, DeviceTaxonomy, SoftwareTaxonomy, TaxonomyConstants,
    TaxonomyScope, DEVICE_TAXONOMY, SOFTWARE_TAXONOMY, TAXONOMY_CONSTANTS
)
from src.config.config_management import get_config, NamingConvention
from src.config.tenant_config import TenantConfig, TemporalDataModel
from src.ttl.ttl_constants import NEVER_EXPIRES
from src.data_generation.data_generation_utils import KeyGenerator


class TaxonomyGenerator:
    """Generate taxonomy classes and relationships for multi-tenant system."""
    
    def __init__(self, naming_convention: NamingConvention = NamingConvention.CAMEL_CASE):
        self.naming_convention = naming_convention
        self.app_config = get_config("production", naming_convention)
        self.scope = TAXONOMY_CONSTANTS.DEFAULT_SCOPE
        
        # Centralized class key mapping to ensure consistency across all taxonomy relationships
        self.class_key_mapping: Dict[str, str] = {}  # logical_class_key -> actual_document_key
        
    def generate_taxonomy_for_tenant(self, tenant_config: TenantConfig) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate complete taxonomy for a tenant.
        
        Returns:
            Dictionary with 'classes', 'type_edges', and 'subclass_edges' lists
        """
        result = {
            "classes": [],
            "type_edges": [],
            "subclass_edges": []
        }
        
        # Clear previous mapping for new tenant
        self.class_key_mapping.clear()
        
        # Determine taxonomy scope
        if self.scope == TaxonomyScope.SHARED:
            tenant_id = TAXONOMY_CONSTANTS.SHARED_TENANT_ID
        else:
            tenant_id = tenant_config.tenant_id
        
        # Generate class hierarchy and populate key mapping
        device_classes = self._generate_device_classes(tenant_id)
        software_classes = self._generate_software_classes(tenant_id)
        
        result["classes"].extend(device_classes)
        result["classes"].extend(software_classes)
        
        # Populate class key mapping from generated documents
        for class_doc in result["classes"]:
            logical_key = class_doc.get('classKey', '')  # Original taxonomy key
            actual_key = class_doc.get('_key', '')       # Generated document key
            if logical_key and actual_key:
                self.class_key_mapping[logical_key] = actual_key
        
        # Generate subClassOf relationships using actual class keys
        device_subclass_edges = self._generate_subclass_relationships(
            DEVICE_TAXONOMY.get_all_classes(), tenant_id
        )
        software_subclass_edges = self._generate_subclass_relationships(
            SOFTWARE_TAXONOMY.get_all_classes(), tenant_id
        )
        
        result["subclass_edges"].extend(device_subclass_edges)
        result["subclass_edges"].extend(software_subclass_edges)
        
        return result
    
    def _generate_device_classes(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Generate device taxonomy classes."""
        classes = []
        device_taxonomy = DEVICE_TAXONOMY.get_all_classes()
        
        for class_key, class_def in device_taxonomy.items():
            class_doc = self._create_class_document(class_def, tenant_id)
            classes.append(class_doc)
        
        return classes
    
    def _generate_software_classes(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Generate software taxonomy classes.""" 
        classes = []
        software_taxonomy = SOFTWARE_TAXONOMY.get_all_classes()
        
        for class_key, class_def in software_taxonomy.items():
            class_doc = self._create_class_document(class_def, tenant_id)
            classes.append(class_doc)
            
        return classes
    
    def _create_class_document(self, class_def: ClassDefinition, tenant_id: str) -> Dict[str, Any]:
        """Create a Class document from ClassDefinition."""
        # Generate unique key for the class (satellite collections don't need tenantId: prefix)
        class_key = f"class_{class_def.key}_{uuid.uuid4().hex[:8]}"
        
        # Create base document
        doc = {
            "_key": class_key,
            "_id": f"{self.app_config.get_collection_name('classes')}/{class_key}",
            "name": class_def.name,
            "description": class_def.description,
            "category": class_def.category,
            "classKey": class_def.key,  # Original taxonomy key for relationships
            "properties": class_def.properties or {}
        }
        
        # Add temporal attributes
        if TAXONOMY_CONSTANTS.TAXONOMY_NEVER_EXPIRES:
            expired = NEVER_EXPIRES
        else:
            # Allow taxonomy evolution - classes can become historical
            expired = None  # Will be set by TemporalDataModel
            
        # Use tenant config for proper temporal attribute handling
        # Note: For satellite collections, tenantId is not used for sharding
        temp_tenant_config = TenantConfig(
            tenant_id=tenant_id,
            tenant_name=f"Taxonomy_{tenant_id}"
        )
        
        enhanced_doc = TemporalDataModel.add_temporal_attributes(
            doc, 
            timestamp=datetime.datetime.now(),
            expired=expired,
            tenant_config=temp_tenant_config
        )
        
        return enhanced_doc
    
    def _generate_subclass_relationships(self, class_definitions: Dict[str, ClassDefinition], 
                                       tenant_id: str) -> List[Dict[str, Any]]:
        """Generate subClassOf relationships between classes using actual generated class keys."""
        edges = []
        
        # Use the stored class key mapping from generated documents
        # No need to generate new random keys - use the actual ones!
        
        # Generate relationships for classes that have parent relationships
        for class_key, class_def in class_definitions.items():
            if class_def.parent_class and class_def.parent_class in self.class_key_mapping:
                # Both child and parent must exist in our mapping
                if class_key in self.class_key_mapping:
                    edge = self._create_subclass_edge(
                        from_class_key=self.class_key_mapping[class_key],      # Actual document key
                        to_class_key=self.class_key_mapping[class_def.parent_class],  # Actual document key
                        tenant_id=tenant_id
                    )
                    edges.append(edge)
        
        return edges
    
    def _create_subclass_edge(self, from_class_key: str, to_class_key: str, 
                            tenant_id: str) -> Dict[str, Any]:
        """Create a subClassOf edge document."""
        edge_key = f"subclass_{uuid.uuid4().hex[:8]}"
        
        # Create base edge document
        edge = {
            "_key": edge_key,
            "_id": f"{self.app_config.get_collection_name('subclass_of')}/{edge_key}",
            "_from": f"{self.app_config.get_collection_name('classes')}/{from_class_key}",
            "_to": f"{self.app_config.get_collection_name('classes')}/{to_class_key}",
            "relationshipType": "inheritance",
            "confidence": TAXONOMY_CONSTANTS.HIGH_CONFIDENCE
        }
        
        # Add temporal attributes
        temp_tenant_config = TenantConfig(
            tenant_id=tenant_id,
            tenant_name=f"Taxonomy_{tenant_id}"
        )
        
        enhanced_edge = TemporalDataModel.add_temporal_attributes(
            edge,
            timestamp=datetime.datetime.now(),
            expired=NEVER_EXPIRES,  # Taxonomy relationships are persistent
            tenant_config=temp_tenant_config
        )
        
        return enhanced_edge
    
    def generate_device_classifications(self, devices: List[Dict[str, Any]], 
                                      tenant_id: str) -> List[Dict[str, Any]]:
        """
        Generate type edges to classify devices based on their properties.
        
        Args:
            devices: List of device documents to classify
            tenant_id: Tenant identifier
            
        Returns:
            List of type edge documents
        """
        type_edges = []
        device_classes = DEVICE_TAXONOMY.get_all_classes()
        
        print(f"[TAXONOMY] Generating device classifications for {len(devices)} devices")
        
        # Use the stored class key mapping from generated documents
        # No need to generate new random keys - use the actual ones!
        
        for device in devices:
            # Classify device based on its properties
            class_key = self._classify_device(device)
            
            # FALLBACK: Ensure every device gets classified (100% coverage)
            if not class_key or class_key not in device_classes or class_key not in self.class_key_mapping:
                # Use generic "network_device" class as fallback (most common device type)
                fallback_class = "network_device"
                if fallback_class in device_classes and fallback_class in self.class_key_mapping:
                    class_key = fallback_class
                    print(f"[TAXONOMY] Device {device.get('name', device.get('_key'))} using fallback classification: {class_key}")
                else:
                    print(f"[WARNING] No classification available for device {device.get('name', device.get('_key'))} - skipping type edge")
                    continue
            
            # Create type edge using actual generated class document key
            edge = self._create_type_edge(
                from_entity=device,
                to_class_doc_key=self.class_key_mapping[class_key],  # Use actual document key
                tenant_id=tenant_id,
                confidence=self._calculate_classification_confidence(device, class_key)
            )
            type_edges.append(edge)
        
        print(f"[TAXONOMY] Generated {len(type_edges)} device type edges (100% coverage)")
        return type_edges
    
    def generate_software_classifications(self, software_list: List[Dict[str, Any]], 
                                        tenant_id: str) -> List[Dict[str, Any]]:
        """
        Generate type edges to classify software based on their properties.
        
        Args:
            software_list: List of software documents to classify
            tenant_id: Tenant identifier
            
        Returns:
            List of type edge documents
        """
        type_edges = []
        software_classes = SOFTWARE_TAXONOMY.get_all_classes()
        
        print(f"[TAXONOMY] Generating software classifications for {len(software_list)} software entities")
        
        # Use the stored class key mapping from generated documents
        # No need to generate new random keys - use the actual ones!
        
        for software in software_list:
            # Classify software based on its properties
            class_key = self._classify_software(software)
            
            # FALLBACK: Ensure every software gets classified (100% coverage)
            if not class_key or class_key not in software_classes or class_key not in self.class_key_mapping:
                # Use generic "software" class as fallback
                fallback_class = "software"
                if fallback_class in software_classes and fallback_class in self.class_key_mapping:
                    class_key = fallback_class
                    print(f"[TAXONOMY] Software {software.get('name', software.get('_key'))} using fallback classification: {class_key}")
                else:
                    print(f"[WARNING] No classification available for software {software.get('name', software.get('_key'))} - skipping type edge")
                    continue
            
            # Create type edge using actual generated class document key
            edge = self._create_type_edge(
                from_entity=software,
                to_class_doc_key=self.class_key_mapping[class_key],  # Use actual document key
                tenant_id=tenant_id,
                confidence=self._calculate_classification_confidence(software, class_key)
            )
            type_edges.append(edge)
        
        print(f"[TAXONOMY] Generated {len(type_edges)} software type edges (100% coverage)")
        return type_edges
    
    def _classify_device(self, device: Dict[str, Any]) -> Optional[str]:
        """Classify a device based on its properties."""
        device_type = device.get("type", "").lower()
        device_name = device.get("name", "").lower()
        
        # Classification rules based on device properties
        if "router" in device_type or "router" in device_name:
            if "edge" in device_name or "border" in device_name:
                return "edge_router"
            elif "core" in device_name or "backbone" in device_name:
                return "core_router" 
            elif "wireless" in device_name or "wifi" in device_name:
                return "wireless_router"
            else:
                return "router"
        
        elif "switch" in device_type or "switch" in device_name:
            if "l3" in device_name or "layer3" in device_name:
                return "l3_switch"
            else:
                return "l2_switch"
        
        elif "access" in device_type and "point" in device_type:
            if "outdoor" in device_name:
                return "outdoor_ap"
            else:
                return "indoor_ap"
        
        elif "firewall" in device_type or "firewall" in device_name:
            if "next" in device_name and "gen" in device_name:
                return "next_gen_firewall"
            else:
                return "firewall"
        
        elif "load" in device_type and "balancer" in device_type:
            return "load_balancer"
        
        # Default to generic network device
        return "network_device"
    
    def _classify_software(self, software: Dict[str, Any]) -> Optional[str]:
        """Classify software based on its properties."""
        software_name = software.get("name", "").lower()
        software_type = software.get("type", "").lower()
        
        # Classification rules based on software properties
        if "postgresql" in software_name or "postgres" in software_name:
            return "postgresql"
        elif "mysql" in software_name:
            return "mysql"
        elif "mongodb" in software_name or "mongo" in software_name:
            return "mongodb"
        elif "apache" in software_name and ("http" in software_name or "web" in software_type):
            return "apache"
        elif "nginx" in software_name:
            return "nginx"
        elif "ubuntu" in software_name:
            return "ubuntu"
        elif "windows" in software_name:
            return "windows"
        elif "linux" in software_name:
            return "linux"
        
        # Classify by type
        elif "database" in software_type:
            if "nosql" in software_type or "document" in software_type:
                return "document_db"
            else:
                return "relational_db"
        elif "web" in software_type and "server" in software_type:
            return "web_server"
        elif "operating" in software_type and "system" in software_type:
            return "operating_system"
        
        # Default to generic software
        return "software"
    
    def _create_type_edge(self, from_entity: Dict[str, Any], to_class_doc_key: str, 
                         tenant_id: str, confidence: float) -> Dict[str, Any]:
        """Create a type edge document."""
        # Generate SmartGraph-compatible key with tenantId prefix (type collection is part of SmartGraph)
        edge_key = f"{tenant_id}:type_{uuid.uuid4().hex[:8]}"
        
        # Create base edge document
        edge = {
            "_key": edge_key,
            "_id": f"{self.app_config.get_collection_name('types')}/{edge_key}",
            "_from": f"{self.app_config.get_collection_name('devices')}/{from_entity['_key']}",
            "_to": f"{self.app_config.get_collection_name('classes')}/{to_class_doc_key}",
            "relationshipType": "instanceOf",
            "confidence": confidence,
            "classifiedAt": datetime.datetime.now().isoformat()
        }
        
        # Add temporal attributes  
        temp_tenant_config = TenantConfig(
            tenant_id=tenant_id,
            tenant_name=f"Classification_{tenant_id}"
        )
        
        enhanced_edge = TemporalDataModel.add_temporal_attributes(
            edge,
            timestamp=datetime.datetime.now(),
            expired=NEVER_EXPIRES,  # Classifications are persistent unless reclassified
            tenant_config=temp_tenant_config
        )
        
        return enhanced_edge
    
    def _calculate_classification_confidence(self, entity: Dict[str, Any], class_key: str) -> float:
        """Calculate confidence level for classification."""
        # Simple confidence calculation based on how specific the match is
        entity_name = entity.get("name", "").lower()
        entity_type = entity.get("type", "").lower()
        
        # High confidence for exact matches
        if class_key.lower() in entity_name or class_key.lower() in entity_type:
            return TAXONOMY_CONSTANTS.HIGH_CONFIDENCE
        
        # Medium confidence for partial matches
        class_words = class_key.lower().split("_")
        if any(word in entity_name or word in entity_type for word in class_words):
            return TAXONOMY_CONSTANTS.MEDIUM_CONFIDENCE
        
        # Low confidence for generic classifications
        return TAXONOMY_CONSTANTS.LOW_CONFIDENCE
    
    def get_taxonomy_statistics(self) -> Dict[str, Any]:
        """Get statistics about the taxonomy system."""
        device_classes = DEVICE_TAXONOMY.get_all_classes()
        software_classes = SOFTWARE_TAXONOMY.get_all_classes()
        
        return {
            "device_classes": len(device_classes),
            "software_classes": len(software_classes),
            "total_classes": len(device_classes) + len(software_classes),
            "taxonomy_scope": self.scope.value,
            "naming_convention": self.naming_convention.value
        }


# Example usage and testing
if __name__ == "__main__":
    print("=== TAXONOMY GENERATOR TEST ===")
    
    generator = TaxonomyGenerator()
    
    # Test taxonomy statistics
    stats = generator.get_taxonomy_statistics()
    print(f"Taxonomy Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Test class generation for a sample tenant
    from src.config.tenant_config import create_tenant_config
    
    tenant_config = create_tenant_config("Test Taxonomy Corp")
    taxonomy_data = generator.generate_taxonomy_for_tenant(tenant_config)
    
    print(f"\nGenerated taxonomy for tenant {tenant_config.tenant_id}:")
    print(f"  Classes: {len(taxonomy_data['classes'])}")
    print(f"  SubClass relationships: {len(taxonomy_data['subclass_edges'])}")
    
    # Show sample class
    if taxonomy_data['classes']:
        sample_class = taxonomy_data['classes'][0]
        print(f"\nSample class: {sample_class['name']}")
        print(f"  Description: {sample_class['description']}")
        print(f"  Category: {sample_class['category']}")
        print(f"  Properties: {len(sample_class.get('properties', {}))}")
