#!/usr/bin/env python3
"""
Alert Simulation System

Simulates real-time alert generation and resolution for demonstration purposes.
Demonstrates alert lifecycle: generation → acknowledgment → resolution → TTL aging.

Author: Scalable Multi-Tenant Temporal Graph Reference Implementation
"""

import json
import random
import uuid
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from arango import ArangoClient
from src.config.config_management import get_config, NamingConvention
from src.config.centralized_credentials import CredentialsManager
from src.ttl.ttl_constants import TTLConstants, NEVER_EXPIRES
from src.data_generation.alert_generator import AlertType, AlertSeverity, AlertStatus, AlertTemplate
from src.utils.alert_naming import create_alert_name
from src.config.generation_constants import GenerationConstants


class AlertSimulator:
    """Simulate real-time alert generation and lifecycle management."""
    
    def __init__(self, naming_convention: NamingConvention = NamingConvention.CAMEL_CASE):
        self.naming_convention = naming_convention
        self.app_config = get_config("production", naming_convention)
        
        # Database connection
        creds = CredentialsManager.get_database_credentials()
        self.client = ArangoClient(hosts=creds.endpoint)
        self.database = self.client.db(
            creds.database_name,
            username=creds.username,
            password=creds.password
        )
        
        # Collection references
        self.alerts_collection = self.database.collection(self.app_config.get_collection_name("alerts"))
        self.hasAlert_collection = self.database.collection(self.app_config.get_collection_name("has_alerts"))
        self.device_proxy_collection = self.database.collection(self.app_config.get_collection_name("device_outs"))
        self.software_proxy_collection = self.database.collection(self.app_config.get_collection_name("software_outs"))
        
    def generate_critical_hardware_alert(self, tenant_id: str) -> Dict[str, Any]:
        """Generate a critical hardware alert for demonstration."""
        # Find a random device proxy for this tenant
        device_proxies = list(self.device_proxy_collection.find({"tenantId": tenant_id}))
        if not device_proxies:
            raise ValueError(f"No device proxies found for tenant: {tenant_id}")
            
        device_proxy = random.choice(device_proxies)
        
        # Generate critical alert
        # Generate SmartGraph-compatible alert key with tenantId prefix
        alert_key = f"{tenant_id}:alert_critical_{uuid.uuid4().hex[:8]}"
        alert_id = f"{self.app_config.get_collection_name('alerts')}/{alert_key}"
        
        created_time = int(datetime.now().timestamp())
        
        # Generate alert name using centralized utility
        device_name = device_proxy.get('name', 'Unknown device')
        alert_name = create_alert_name("critical", "hardware", device_name, "device")
        alert_doc = {
            "_key": alert_key,
            "_id": alert_id,
            "tenantId": tenant_id,
            "name": alert_name,
            "alertType": AlertType.HARDWARE.value,
            "severity": AlertSeverity.CRITICAL.value,
            "status": AlertStatus.ACTIVE.value,
            "message": f"CRITICAL: {device_proxy.get('name', 'Unknown device')} CPU temperature reached 92°C",
            "created": created_time,
            "expired": NEVER_EXPIRES,
            "metadata": {
                "temperature": 92,
                "threshold": 80,
                "device_name": device_proxy.get('name'),
                "device_type": device_proxy.get('type', 'unknown'),
                "sensor": "cpu_temp_1"
            }
        }
        
        # Create hasAlert relationship (SmartGraph will auto-generate _key)
        hasAlert_edge = {
            # "_key": edge_key,  # REMOVED: Let SmartGraph auto-generate proper edge keys
            "_from": device_proxy["_id"],
            "_to": alert_id,
            "tenantId": tenant_id,
            "relationshipType": "generated_by",
            "created": created_time,
            "expired": NEVER_EXPIRES
        }
        
        # Insert into database
        self.alerts_collection.insert(alert_doc)
        self.hasAlert_collection.insert(hasAlert_edge)
        
        return {
            "alert": alert_doc,
            "edge": hasAlert_edge,
            "source_device": device_proxy.get('name', 'Unknown')
        }
    
    def generate_software_performance_alert(self, tenant_id: str) -> Dict[str, Any]:
        """Generate a software performance alert for demonstration."""
        # Find a random software proxy for this tenant
        software_proxies = list(self.software_proxy_collection.find({"tenantId": tenant_id}))
        if not software_proxies:
            raise ValueError(f"No software proxies found for tenant: {tenant_id}")
            
        software_proxy = random.choice(software_proxies)
        
        # Generate performance warning
        # Generate SmartGraph-compatible alert key with tenantId prefix
        alert_key = f"{tenant_id}:alert_perf_{uuid.uuid4().hex[:8]}"
        alert_id = f"{self.app_config.get_collection_name('alerts')}/{alert_key}"
        
        created_time = int(datetime.now().timestamp())
        
        # Generate alert name using centralized utility
        software_name = software_proxy.get('name', 'Unknown software')
        alert_name = create_alert_name("warning", "performance", software_name, "software")
        alert_doc = {
            "_key": alert_key,
            "_id": alert_id,
            "tenantId": tenant_id,
            "name": alert_name,
            "alertType": AlertType.PERFORMANCE.value,
            "severity": AlertSeverity.WARNING.value,
            "status": AlertStatus.ACTIVE.value,
            "message": f"Performance degraded: {software_proxy.get('name', 'Unknown software')} response time 2.8s",
            "created": created_time,
            "expired": NEVER_EXPIRES,
            "metadata": {
                "response_time": 2.8,
                "threshold": 1.0,
                "software_name": software_proxy.get('name'),
                "software_type": software_proxy.get('type', 'unknown'),
                "request_count": 1200
            }
        }
        
        # Create hasAlert relationship (SmartGraph will auto-generate _key)
        hasAlert_edge = {
            # "_key": edge_key,  # REMOVED: Let SmartGraph auto-generate proper edge keys
            "_from": software_proxy["_id"],
            "_to": alert_id,
            "tenantId": tenant_id,
            "relationshipType": "generated_by",
            "created": created_time,
            "expired": NEVER_EXPIRES
        }
        
        # Insert into database
        self.alerts_collection.insert(alert_doc)
        self.hasAlert_collection.insert(hasAlert_edge)
        
        return {
            "alert": alert_doc,
            "edge": hasAlert_edge,
            "source_software": software_proxy.get('name', 'Unknown')
        }
    
    def generate_connectivity_alert(self, tenant_id: str) -> Dict[str, Any]:
        """Generate a connectivity alert for demonstration."""
        # Find a random device proxy for this tenant
        device_proxies = list(self.device_proxy_collection.find({"tenantId": tenant_id}))
        if not device_proxies:
            raise ValueError(f"No device proxies found for tenant: {tenant_id}")
            
        device_proxy = random.choice(device_proxies)
        
        # Generate connectivity alert
        # Generate SmartGraph-compatible alert key with tenantId prefix
        alert_key = f"{tenant_id}:alert_conn_{uuid.uuid4().hex[:8]}"
        alert_id = f"{self.app_config.get_collection_name('alerts')}/{alert_key}"
        
        created_time = int(datetime.now().timestamp())
        
        # Generate alert name using centralized utility
        device_name = device_proxy.get('name', 'Unknown device')
        alert_name = create_alert_name("critical", "connectivity", device_name, "device")
        alert_doc = {
            "_key": alert_key,
            "_id": alert_id,
            "tenantId": tenant_id,
            "name": alert_name,
            "alertType": AlertType.CONNECTIVITY.value,
            "severity": AlertSeverity.CRITICAL.value,
            "status": AlertStatus.ACTIVE.value,
            "message": f"Connection lost: {device_proxy.get('name', 'Unknown device')} interface eth0 down",
            "created": created_time,
            "expired": NEVER_EXPIRES,
            "metadata": {
                "device_name": device_proxy.get('name'),
                "interface": "eth0",
                "connection_type": "ethernet",
                "target_ip": f"{GenerationConstants().IP_SUBNET_BASE}.1.1",
                "last_seen": created_time - 30
            }
        }
        
        # Create hasAlert relationship (SmartGraph will auto-generate _key)
        hasAlert_edge = {
            # "_key": edge_key,  # REMOVED: Let SmartGraph auto-generate proper edge keys
            "_from": device_proxy["_id"],
            "_to": alert_id,
            "tenantId": tenant_id,
            "relationshipType": "generated_by",
            "created": created_time,
            "expired": NEVER_EXPIRES
        }
        
        # Insert into database
        self.alerts_collection.insert(alert_doc)
        self.hasAlert_collection.insert(hasAlert_edge)
        
        return {
            "alert": alert_doc,
            "edge": hasAlert_edge,
            "source_device": device_proxy.get('name', 'Unknown')
        }
    
    def resolve_alert(self, alert_key: str, tenant_id: str) -> Dict[str, Any]:
        """Resolve an active alert and trigger TTL aging."""
        # Find the alert
        alert = self.alerts_collection.get(alert_key)
        if not alert:
            raise ValueError(f"Alert not found: {alert_key}")
            
        if alert["tenantId"] != tenant_id:
            raise ValueError(f"Alert {alert_key} does not belong to tenant {tenant_id}")
            
        if alert["status"] != AlertStatus.ACTIVE.value:
            raise ValueError(f"Alert {alert_key} is not active (status: {alert['status']})")
        
        # Calculate resolution time and TTL
        resolved_time = int(datetime.now().timestamp())
        
        # Use demo TTL if available, otherwise production TTL
        # FIXED: Use DEMO_TTL_EXPIRE_SECONDS directly instead of converting minutes
        if hasattr(TTLConstants, 'DEMO_TTL_EXPIRE_SECONDS'):
            ttl_expire_at = resolved_time + TTLConstants.DEMO_TTL_EXPIRE_SECONDS
            print(f"DEBUG: resolved_time={resolved_time}, ttl_expire_at={ttl_expire_at}, diff={TTLConstants.DEMO_TTL_EXPIRE_SECONDS}s")
        else:
            ttl_expire_at = resolved_time + (30 * 24 * 60 * 60)  # 30 days
            print(f"DEBUG: Using 30-day fallback TTL")
        
        # Update alert document using replace (more reliable than update for this collection)
        alert_doc = self.alerts_collection.get(alert_key)
        alert_doc.update({
            "status": AlertStatus.RESOLVED.value,
            "expired": resolved_time,
            "ttlExpireAt": ttl_expire_at,
            "resolution_notes": "Resolved via simulation"
        })
        updated_alert = self.alerts_collection.replace(alert_doc)
        
        # Update hasAlert relationship using replace method
        hasAlert_edges = list(self.hasAlert_collection.find({"_to": alert["_id"]}))
        for edge in hasAlert_edges:
            edge_doc = self.hasAlert_collection.get(edge["_key"])
            edge_doc.update({
                "expired": resolved_time,
                "ttlExpireAt": ttl_expire_at
            })
            print(f"DEBUG: Updating edge {edge['_key']} - expired={resolved_time}, ttlExpireAt={ttl_expire_at}")
            self.hasAlert_collection.replace(edge_doc)
        
        return {
            "alert_key": alert_key,
            "resolved_time": resolved_time,
            "ttl_expire_at": ttl_expire_at,
            "message": alert["message"]
        }
    
    def get_tenant_alerts(self, tenant_id: str, status: Optional[str] = None) -> List[Dict]:
        """Get alerts for a specific tenant."""
        query_filter = {"tenantId": tenant_id}
        if status:
            query_filter["status"] = status
            
        alerts = list(self.alerts_collection.find(query_filter))
        
        # Sort by created time (newest first)
        alerts.sort(key=lambda x: x["created"], reverse=True)
        
        return alerts
    
    def get_alert_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get alert summary statistics for a tenant."""
        all_alerts = self.get_tenant_alerts(tenant_id)
        
        summary = {
            "total_alerts": len(all_alerts),
            "active": len([a for a in all_alerts if a["status"] == "active"]),
            "resolved": len([a for a in all_alerts if a["status"] == "resolved"]),
            "by_severity": {
                "critical": len([a for a in all_alerts if a["severity"] == "critical"]),
                "warning": len([a for a in all_alerts if a["severity"] == "warning"]),
                "info": len([a for a in all_alerts if a["severity"] == "info"])
            },
            "by_type": {}
        }
        
        # Count by alert type
        for alert in all_alerts:
            alert_type = alert["alertType"]
            summary["by_type"][alert_type] = summary["by_type"].get(alert_type, 0) + 1
            
        return summary
    
    def run_alert_simulation_demo(self, tenant_id: str, num_alerts: int = 5) -> List[Dict]:
        """Run a complete alert simulation demonstration."""
        print(f"\n{'='*60}")
        print(f"ALERT SIMULATION DEMO - Tenant: {tenant_id}")
        print(f"{'='*60}")
        
        generated_alerts = []
        
        # Generate different types of alerts
        alert_generators = [
            ("Critical Hardware Alert", self.generate_critical_hardware_alert),
            ("Software Performance Alert", self.generate_software_performance_alert),
            ("Connectivity Alert", self.generate_connectivity_alert)
        ]
        
        for i in range(num_alerts):
            alert_type, generator_func = random.choice(alert_generators)
            
            print(f"\n[{i+1}/{num_alerts}] Generating {alert_type}...")
            
            try:
                result = generator_func(tenant_id)
                generated_alerts.append(result)
                
                alert = result["alert"]
                print(f"   ✅ Alert created: {alert['_key']}")
                print(f"   📋 Message: {alert['message']}")
                print(f"   🚨 Severity: {alert['severity']}")
                print(f"   📅 Created: {datetime.fromtimestamp(alert['created']).strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Randomly resolve some alerts for demonstration
                if random.random() < 0.3:  # 30% chance to resolve immediately
                    print(f"   🔧 Resolving alert for demonstration...")
                    resolution = self.resolve_alert(alert["_key"], tenant_id)
                    print(f"   ✅ Alert resolved - TTL expires at {datetime.fromtimestamp(resolution['ttl_expire_at']).strftime('%Y-%m-%d %H:%M:%S')}")
                    
            except Exception as e:
                print(f"   ❌ Error generating alert: {e}")
                
            time.sleep(1)  # Brief pause for demo effect
        
        # Show final summary
        print(f"\n{'='*60}")
        print("ALERT SIMULATION SUMMARY")
        print(f"{'='*60}")
        
        summary = self.get_alert_summary(tenant_id)
        print(f"Total Alerts Generated: {len(generated_alerts)}")
        print(f"Current Alert Status:")
        print(f"  - Active: {summary['active']}")
        print(f"  - Resolved: {summary['resolved']}")
        print(f"Alert Severity Distribution:")
        for severity, count in summary['by_severity'].items():
            if count > 0:
                print(f"  - {severity.title()}: {count}")
        
        return generated_alerts


def main():
    """Demo the alert simulation system."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simulate alert generation and lifecycle")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID to generate alerts for")
    parser.add_argument("--naming", choices=["camelCase", "snake_case"], default="camelCase")
    parser.add_argument("--num-alerts", type=int, default=5, help="Number of alerts to generate")
    parser.add_argument("--type", choices=["hardware", "software", "connectivity"], help="Specific alert type to generate")
    
    args = parser.parse_args()
    
    naming = NamingConvention.CAMEL_CASE if args.naming == "camelCase" else NamingConvention.SNAKE_CASE
    simulator = AlertSimulator(naming)
    
    if args.type:
        # Generate specific type of alert
        print(f"[INFO] Generating {args.type} alert for tenant: {args.tenant_id}")
        
        if args.type == "hardware":
            result = simulator.generate_critical_hardware_alert(args.tenant_id)
        elif args.type == "software":
            result = simulator.generate_software_performance_alert(args.tenant_id)
        elif args.type == "connectivity":
            result = simulator.generate_connectivity_alert(args.tenant_id)
            
        print(f"[SUCCESS] Alert generated: {result['alert']['_key']}")
        print(f"[MESSAGE] {result['alert']['message']}")
    else:
        # Run full simulation demo
        simulator.run_alert_simulation_demo(args.tenant_id, args.num_alerts)


if __name__ == "__main__":
    main()
