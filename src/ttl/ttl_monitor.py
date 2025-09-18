#!/usr/bin/env python3
"""
TTL Monitor for Demo

Monitors TTL expiration and shows live aging of historical documents
during demonstration. Displays countdown timers and document counts.
"""

import time
import datetime
import sys
from typing import Dict, List, Any
from arango import ArangoClient

from src.config.centralized_credentials import CredentialsManager
from src.ttl.ttl_constants import TTLConstants


class TTLMonitor:
    """Monitor TTL aging during demonstration."""
    
    def __init__(self):
        """Initialize TTL monitor."""
        self.database = None
        self.connect_to_database()
        
    def connect_to_database(self) -> bool:
        """Connect to the ArangoDB database."""
        try:
            creds = CredentialsManager.get_database_credentials()
            client = ArangoClient(hosts=creds.endpoint)
            self.database = client.db(creds.database_name, **CredentialsManager.get_database_params())
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False
    
    def get_document_counts(self) -> Dict[str, Dict[str, int]]:
        """Get counts of current vs historical documents with TTL info."""
        collections = ["Device", "Software", "hasVersion"]
        counts = {}
        
        for collection_name in collections:
            try:
                if not self.database.has_collection(collection_name):
                    continue
                    
                collection = self.database.collection(collection_name)
                
                # Current documents (no ttlExpireAt field)
                current_query = f"""
                FOR doc IN {collection_name}
                  FILTER !HAS(doc, 'ttlExpireAt')
                  RETURN 1
                """
                current_count = len(list(self.database.aql.execute(current_query)))
                
                # Historical documents with TTL
                historical_query = f"""
                FOR doc IN {collection_name}
                  FILTER HAS(doc, 'ttlExpireAt')
                  RETURN doc.ttlExpireAt
                """
                historical_docs = list(self.database.aql.execute(historical_query))
                
                # Count documents by TTL status
                now = time.time()
                pending_expiry = len([ts for ts in historical_docs if ts > now])
                already_expired = len([ts for ts in historical_docs if ts <= now])
                
                counts[collection_name] = {
                    "current": current_count,
                    "historical_pending": pending_expiry,
                    "historical_expired": already_expired,
                    "total_historical": len(historical_docs)
                }
                
            except Exception as e:
                print(f"[WARNING] Could not count {collection_name}: {e}")
                counts[collection_name] = {"current": 0, "historical_pending": 0, "historical_expired": 0, "total_historical": 0}
        
        return counts
    
    def get_next_expiry_time(self) -> Dict[str, Any]:
        """Get the next document expiry time across all collections."""
        collections = ["Device", "Software", "hasVersion"]
        next_expiry = None
        next_collection = None
        
        for collection_name in collections:
            try:
                if not self.database.has_collection(collection_name):
                    continue
                    
                # Find earliest expiry time
                query = f"""
                FOR doc IN {collection_name}
                  FILTER HAS(doc, 'ttlExpireAt') AND doc.ttlExpireAt > @now
                  SORT doc.ttlExpireAt ASC
                  LIMIT 1
                  RETURN doc.ttlExpireAt
                """
                
                results = list(self.database.aql.execute(query, bind_vars={"now": time.time()}))
                if results:
                    expiry_time = results[0]
                    if next_expiry is None or expiry_time < next_expiry:
                        next_expiry = expiry_time
                        next_collection = collection_name
                        
            except Exception as e:
                print(f"[WARNING] Could not check expiry for {collection_name}: {e}")
        
        if next_expiry:
            return {
                "timestamp": next_expiry,
                "collection": next_collection,
                "seconds_remaining": next_expiry - time.time(),
                "datetime": datetime.datetime.fromtimestamp(next_expiry)
            }
        
        return None
    
    def display_ttl_status(self):
        """Display current TTL status with live updates."""
        print("\n" + "=" * 60)
        print("TTL AGING MONITOR")
        print("=" * 60)
        
        # Document counts
        counts = self.get_document_counts()
        print(f"\nDocument Counts:")
        for collection, count_info in counts.items():
            current = count_info["current"]
            historical = count_info["total_historical"]
            pending = count_info["historical_pending"] 
            expired = count_info["historical_expired"]
            
            print(f"  {collection}:")
            print(f"    Current (permanent): {current}")
            print(f"    Historical (TTL): {historical} total ({pending} pending, {expired} expired)")
        
        # Next expiry
        next_expiry = self.get_next_expiry_time()
        if next_expiry:
            remaining = next_expiry["seconds_remaining"]
            if remaining > 0:
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                print(f"\nNext TTL Expiry:")
                print(f"  Collection: {next_expiry['collection']}")
                print(f"  Time: {next_expiry['datetime'].strftime('%H:%M:%S')}")
                print(f"  Countdown: {minutes}m {seconds}s")
            else:
                print(f"\nNext TTL Expiry: Documents ready for cleanup")
        else:
            print(f"\nNext TTL Expiry: No historical documents found")
        
        print(f"\nTTL Configuration:")
        print(f"  TTL Interval: {TTLConstants.DEMO_TTL_EXPIRE_MINUTES} minutes")
        print(f"  Current Time: {datetime.datetime.now().strftime('%H:%M:%S')}")
    
    def monitor_live(self, duration_minutes: int = 15, refresh_seconds: int = 30):
        """Monitor TTL aging live for the specified duration."""
        print(f"\n[MONITOR] Starting live TTL monitoring for {duration_minutes} minutes...")
        print(f"[MONITOR] Refreshing every {refresh_seconds} seconds")
        print(f"[MONITOR] Press Ctrl+C to stop monitoring")
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        try:
            while time.time() < end_time:
                # Clear screen (works on most terminals)
                print("\033[2J\033[H", end="")
                
                self.display_ttl_status()
                
                remaining = end_time - time.time()
                if remaining > 0:
                    print(f"\n[MONITOR] Monitoring for {remaining/60:.1f} more minutes...")
                    time.sleep(refresh_seconds)
                else:
                    break
                    
        except KeyboardInterrupt:
            print(f"\n[STOPPED] TTL monitoring stopped by user")
        
        print(f"\n[DONE] TTL monitoring completed")


def main():
    """Run TTL monitor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor TTL aging during demo")
    parser.add_argument("--duration", type=int, default=15, 
                       help="Monitor duration in minutes (default: 15)")
    parser.add_argument("--refresh", type=int, default=30,
                       help="Refresh interval in seconds (default: 30)")
    parser.add_argument("--status-only", action="store_true",
                       help="Show current status only (no live monitoring)")
    
    args = parser.parse_args()
    
    monitor = TTLMonitor()
    
    if args.status_only:
        monitor.display_ttl_status()
    else:
        monitor.monitor_live(args.duration, args.refresh)


if __name__ == "__main__":
    main()
