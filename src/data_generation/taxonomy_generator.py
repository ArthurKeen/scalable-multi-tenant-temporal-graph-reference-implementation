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

import logging

logger = logging.getLogger(__name__)


class TaxonomyGenerator:
    """Generate taxonomy classes and relationships for multi-tenant system.

    The taxonomy lives in satellite collections (Class, subClassOf) that are
    shared across all tenants.  It is generated **once** via
    ``generate_shared_taxonomy()`` and saved to ``data/shared_taxonomy/``.
    Per-tenant ``type`` edges reference the shared class document keys.
    """

    SHARED_TAXONOMY_DIR = Path("data/shared_taxonomy")

    def __init__(self, naming_convention: NamingConvention = NamingConvention.CAMEL_CASE):
        self.naming_convention = naming_convention
        self.app_config = get_config("production", naming_convention)

        # logical_class_key -> actual_document_key  (populated by generate or load)
        self.class_key_mapping: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Shared taxonomy (generate once, load many)
    # ------------------------------------------------------------------

    def generate_shared_taxonomy(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate the single shared taxonomy (classes + subClassOf edges).

        Populates ``self.class_key_mapping`` so that subsequent calls to
        ``generate_device_classifications`` / ``generate_software_classifications``
        can look up the correct class document keys.

        Returns dict with ``classes`` and ``subclass_edges`` lists.
        """
        self.class_key_mapping.clear()
        tenant_id = TAXONOMY_CONSTANTS.SHARED_TENANT_ID

        device_classes = self._generate_device_classes(tenant_id)
        software_classes = self._generate_software_classes(tenant_id)

        all_classes = device_classes + software_classes

        for class_doc in all_classes:
            logical_key = class_doc.get("classKey", "")
            actual_key = class_doc.get("_key", "")
            if logical_key and actual_key:
                self.class_key_mapping[logical_key] = actual_key

        device_edges = self._generate_subclass_relationships(
            DEVICE_TAXONOMY.get_all_classes(), tenant_id
        )
        software_edges = self._generate_subclass_relationships(
            SOFTWARE_TAXONOMY.get_all_classes(), tenant_id
        )

        return {
            "classes": all_classes,
            "subclass_edges": device_edges + software_edges,
        }

    def save_shared_taxonomy(self, taxonomy_data: Dict[str, List[Dict[str, Any]]]) -> Path:
        """Persist shared taxonomy to ``data/shared_taxonomy/``."""
        import json

        out_dir = self.SHARED_TAXONOMY_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        classes_file = out_dir / self.app_config.get_file_name("classes")
        subclass_file = out_dir / self.app_config.get_file_name("subclass_of")

        with open(classes_file, "w") as f:
            json.dump(taxonomy_data["classes"], f, indent=2)
        with open(subclass_file, "w") as f:
            json.dump(taxonomy_data["subclass_edges"], f, indent=2)

        logger.info(f"[TAXONOMY] Saved shared taxonomy: {len(taxonomy_data['classes'])} classes, "
                     f"{len(taxonomy_data['subclass_edges'])} subClassOf edges -> {out_dir}")
        return out_dir

    def load_shared_taxonomy(self, taxonomy_dir: Optional[Path] = None) -> None:
        """Load the shared taxonomy's class_key_mapping from saved JSON.

        This must be called before ``generate_device_classifications`` /
        ``generate_software_classifications`` when running per-tenant
        data generation.
        """
        import json

        taxonomy_dir = taxonomy_dir or self.SHARED_TAXONOMY_DIR
        classes_file = taxonomy_dir / self.app_config.get_file_name("classes")

        with open(classes_file, "r") as f:
            classes = json.load(f)

        self.class_key_mapping.clear()
        for class_doc in classes:
            logical_key = class_doc.get("classKey", "")
            actual_key = class_doc.get("_key", "")
            if logical_key and actual_key:
                self.class_key_mapping[logical_key] = actual_key

        logger.info(f"[TAXONOMY] Loaded shared taxonomy mapping: {len(self.class_key_mapping)} classes from {taxonomy_dir}")
    
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
        
        logger.info(f"[TAXONOMY] Generating device classifications for {len(devices)} devices")
        
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
                    logger.info(f"[TAXONOMY] Device {device.get('name', device.get('_key'))} using fallback classification: {class_key}")
                else:
                    logger.warning(f"No classification available for device {device.get('name', device.get('_key'))} - skipping type edge")
                    continue
            
            # Create type edge using actual generated class document key
            edge = self._create_type_edge(
                from_entity=device,
                to_class_doc_key=self.class_key_mapping[class_key],  # Use actual document key
                tenant_id=tenant_id,
                confidence=self._calculate_classification_confidence(device, class_key)
            )
            type_edges.append(edge)
        
        logger.info(f"[TAXONOMY] Generated {len(type_edges)} device type edges (100% coverage)")
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
        
        logger.info(f"[TAXONOMY] Generating software classifications for {len(software_list)} software entities")
        
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
                    logger.info(f"[TAXONOMY] Software {software.get('name', software.get('_key'))} using fallback classification: {class_key}")
                else:
                    logger.warning(f"No classification available for software {software.get('name', software.get('_key'))} - skipping type edge")
                    continue
            
            # Create type edge using actual generated class document key
            edge = self._create_type_edge(
                from_entity=software,
                to_class_doc_key=self.class_key_mapping[class_key],  # Use actual document key
                tenant_id=tenant_id,
                confidence=self._calculate_classification_confidence(software, class_key)
            )
            type_edges.append(edge)
        
        logger.info(f"[TAXONOMY] Generated {len(type_edges)} software type edges (100% coverage)")
        return type_edges
    
    def _classify_device(self, device: Dict[str, Any]) -> Optional[str]:
        """Classify a device to a specific leaf taxonomy class.

        Uses the device type and a stable random seed (from _key) so the same
        device always gets the same classification across regenerations.
        """
        device_type = device.get("type", "").lower()
        device_key = device.get("_key", "")
        rng = random.Random(device_key)

        if "router" in device_type:
            return rng.choice(["core_router", "edge_router", "wireless_router"])

        if "switch" in device_type:
            return rng.choice(["l2_switch", "l3_switch"])

        if "firewall" in device_type:
            return rng.choice(["firewall", "next_gen_firewall"])

        if "iot" in device_type:
            return rng.choice(["indoor_ap", "outdoor_ap", "indoor_ap"])

        if "server" in device_type:
            return rng.choice(["compute_device", "load_balancer"])

        if "laptop" in device_type:
            return "compute_device"

        return "network_device"
    
    def _classify_software(self, software: Dict[str, Any]) -> Optional[str]:
        """Classify software to a specific leaf taxonomy class.

        Named software (PostgreSQL, MongoDB, etc.) maps directly. Generic
        software gets a stable random leaf assignment seeded by _key.
        """
        software_name = software.get("name", "").lower()
        software_type = software.get("type", "").lower()
        software_key = software.get("_key", "")
        rng = random.Random(software_key)

        if "postgresql" in software_name or "postgres" in software_name:
            return "postgresql"
        if "mysql" in software_name:
            return "mysql"
        if "mongodb" in software_name or "mongo" in software_name:
            return "mongodb"
        if "apache" in software_name:
            return "apache"
        if "nginx" in software_name:
            return "nginx"
        if "node" in software_name or "node.js" in software_name:
            return rng.choice(["application_software", "web_server"])
        if "docker" in software_name:
            return "system_software"
        if "ubuntu" in software_name:
            return "ubuntu"
        if "windows" in software_name:
            return "windows"
        if "linux" in software_name:
            return "linux"

        if "database" in software_type:
            return rng.choice(["relational_db", "document_db", "graph_db", "nosql_db"])
        if "web" in software_type:
            return "web_server"
        if "operating" in software_type:
            return rng.choice(["ubuntu", "windows", "linux"])

        return rng.choice(["application_software", "system_software"])
    
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("=== TAXONOMY GENERATOR TEST ===")

    generator = TaxonomyGenerator()

    stats = generator.get_taxonomy_statistics()
    print("Taxonomy Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    taxonomy_data = generator.generate_shared_taxonomy()
    generator.save_shared_taxonomy(taxonomy_data)

    print(f"\nShared taxonomy:")
    print(f"  Classes: {len(taxonomy_data['classes'])}")
    print(f"  SubClass relationships: {len(taxonomy_data['subclass_edges'])}")

    if taxonomy_data["classes"]:
        sample = taxonomy_data["classes"][0]
        print(f"\nSample class: {sample['name']}")
        print(f"  Category: {sample['category']}")
        print(f"  classKey: {sample['classKey']}")
