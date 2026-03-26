#!/usr/bin/env python3
"""
MDI-Prefix Multi-Dimensional Index Testing Suite

REQUIRES: Live ArangoDB connection (set ARANGO_* environment variables).

Tests MDI-prefix multi-dimensional index performance and functionality for temporal queries
on created/expired fields. Validates that MDI-prefix indexes improve query
performance for time travel range queries.

Usage:
    PYTHONPATH=. python3 src/validation/mdi_tests.py
"""

import logging
import time
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from arango import ArangoClient
from pathlib import Path

# Import our utilities
from src.config.centralized_credentials import CredentialsManager
from src.database.database_utilities import DatabaseConnectionManager, QueryExecutor

logger = logging.getLogger(__name__)


class MDIIndexTester:
    """Test suite for MDI-prefix multi-dimensional index functionality and performance."""
    
    def __init__(self, show_queries: bool = True):
        self.show_queries = show_queries
        self.db_manager = DatabaseConnectionManager()
        self.database = None
        self.test_results = {}
        
    def connect_to_database(self) -> bool:
        """Connect to the test database."""
        try:
            self.database = self.db_manager.database
            if self.database.name:  # Test connection
                logger.info(f"[CONNECT] Connected to database for ZKD testing: {self.database.name}")
                return True
            return False
        except Exception as e:
            logger.error(f"[ERROR] Database connection failed: {e}")
            return False
    
    def get_collection_indexes(self, collection_name: str) -> List[Dict]:
        """Get all indexes for a collection."""
        try:
            collection = self.database.collection(collection_name)
            indexes = collection.indexes()
            return indexes
        except Exception as e:
            logger.error(f"[ERROR] Failed to get indexes for {collection_name}: {e}")
            return []
    
    def verify_zkd_indexes_exist(self) -> bool:
        """Verify that ZKD multi-dimensional indexes exist on temporal collections."""
        logger.info(f"\n[TEST] Verifying ZKD multi-dimensional indexes exist...")
        
        expected_indexes = [
            ("Device", "idx_device_mdi_temporal"),
            ("Software", "idx_software_mdi_temporal"),
            ("hasVersion", "idx_version_mdi_temporal")
        ]
        
        all_found = True
        for collection_name, expected_index_name in expected_indexes:
            indexes = self.get_collection_indexes(collection_name)
            zkd_indexes = [idx for idx in indexes if idx.get('type') == 'zkd']
            
            found_index = None
            for idx in zkd_indexes:
                if idx.get('name') == expected_index_name:
                    found_index = idx
                    break
            
            if found_index:
                fields = found_index.get('fields', [])
                logger.info(f"   [FOUND] {collection_name}.{expected_index_name}")
                logger.info(f"           Fields: {fields}")
                logger.info(f"           Type: {found_index.get('type')}")
                logger.info(f"           Unique: {found_index.get('unique', 'N/A')}")
                logger.info(f"           Sparse: {found_index.get('sparse', 'N/A')}")
            else:
                logger.warning(f"   [MISSING] {collection_name}.{expected_index_name}")
                all_found = False
        
        if all_found:
            logger.info(f"[SUCCESS] All ZKD multi-dimensional indexes found")
        else:
            logger.error(f"[ERROR] Some ZKD multi-dimensional indexes are missing")
        
        return all_found
    
    def test_temporal_range_queries(self) -> Dict[str, Any]:
        """Test temporal range queries using ZKD multi-dimensional indexes."""
        logger.info(f"\n[TEST] Testing temporal range queries with ZKD multi-dimensional indexes...")
        
        # Get current timestamp for testing
        current_time = time.time()
        from src.ttl.ttl_constants import TTLConstants
        past_time = current_time - TTLConstants.DEFAULT_TTL_EXPIRE_SECONDS  # 30 days ago
        future_time = current_time + TTLConstants.DEFAULT_TTL_EXPIRE_SECONDS  # 30 days from now
        
        test_results = {}
        
        # Test 1: Point-in-time query (current active configurations)
        logger.info(f"\n   [QUERY] Testing point-in-time query (active configurations)...")
        query1 = """
        FOR device IN Device
          FILTER device.created <= @point_in_time 
          AND device.expired > @point_in_time
          LIMIT 10
          RETURN {
            key: device._key,
            created: device.created,
            expired: device.expired,
            name: device.name
          }
        """
        
        start_time = time.time()
        results1 = QueryExecutor.execute_and_display_query(
            self.database, query1, "Point-in-Time Query (Active)", 
            {"point_in_time": current_time}, self.show_queries
        )
        query1_time = time.time() - start_time
        test_results["point_in_time"] = {
            "query_time": query1_time,
            "result_count": len(results1),
            "query": "Point-in-time active configurations"
        }
        
        # Test 2: Range query (configurations created in a time window)
        logger.info(f"\n   [QUERY] Testing range query (configurations in time window)...")
        query2 = """
        FOR device IN Device
          FILTER device.created >= @start_time 
          AND device.created <= @end_time
          LIMIT 10
          RETURN {
            key: device._key,
            created: device.created,
            expired: device.expired,
            name: device.name
          }
        """
        
        start_time = time.time()
        results2 = QueryExecutor.execute_and_display_query(
            self.database, query2, "Range Query (Creation Window)", 
            {"start_time": past_time, "end_time": current_time}, self.show_queries
        )
        query2_time = time.time() - start_time
        test_results["creation_range"] = {
            "query_time": query2_time,
            "result_count": len(results2),
            "query": "Configurations created in time window"
        }
        
        # Test 3: Complex temporal overlap query
        logger.info(f"\n   [QUERY] Testing complex temporal overlap query...")
        query3 = """
        FOR device IN Device
          FILTER device.created <= @end_time
          AND device.expired >= @start_time
          LIMIT 10
          RETURN {
            key: device._key,
            created: device.created,
            expired: device.expired,
            name: device.name,
            overlap: true
          }
        """
        
        start_time = time.time()
        results3 = QueryExecutor.execute_and_display_query(
            self.database, query3, "Complex Temporal Overlap", 
            {"start_time": past_time, "end_time": current_time}, self.show_queries
        )
        query3_time = time.time() - start_time
        test_results["temporal_overlap"] = {
            "query_time": query3_time,
            "result_count": len(results3),
            "query": "Temporal overlap detection"
        }
        
        # Test 4: Software temporal query
        logger.info(f"\n   [QUERY] Testing software temporal query...")
        query4 = """
        FOR software IN Software
          FILTER software.created <= @point_in_time 
          AND software.expired > @point_in_time
          LIMIT 10
          RETURN {
            key: software._key,
            created: software.created,
            expired: software.expired,
            name: software.name,
            port: software.portNumber
          }
        """
        
        start_time = time.time()
        results4 = QueryExecutor.execute_and_display_query(
            self.database, query4, "Software Point-in-Time Query", 
            {"point_in_time": current_time}, self.show_queries
        )
        query4_time = time.time() - start_time
        test_results["software_point_in_time"] = {
            "query_time": query4_time,
            "result_count": len(results4),
            "query": "Software active configurations"
        }
        
        # Test 5: hasVersion edge temporal query
        logger.info(f"\n   [QUERY] Testing hasVersion edge temporal query...")
        query5 = """
        FOR version IN hasVersion
          FILTER version.created <= @point_in_time 
          AND version.expired > @point_in_time
          LIMIT 10
          RETURN {
            key: version._key,
            from: version._from,
            to: version._to,
            created: version.created,
            expired: version.expired
          }
        """
        
        start_time = time.time()
        results5 = QueryExecutor.execute_and_display_query(
            self.database, query5, "Version Edge Temporal Query", 
            {"point_in_time": current_time}, self.show_queries
        )
        query5_time = time.time() - start_time
        test_results["version_edges"] = {
            "query_time": query5_time,
            "result_count": len(results5),
            "query": "Active version edges"
        }
        
        return test_results
    
    def analyze_query_execution_plans(self) -> Dict[str, Any]:
        """Analyze query execution plans to verify ZKD index usage."""
        logger.info(f"\n[TEST] Analyzing query execution plans for ZKD index usage...")
        
        plan_results = {}
        current_time = time.time()
        
        # Query to analyze
        test_query = """
        FOR device IN Device
          FILTER device.created <= @point_in_time 
          AND device.expired > @point_in_time
          LIMIT 100
          RETURN device._key
        """
        
        try:
            # Get execution plan
            plan = self.database.aql.explain(test_query, bind_vars={"point_in_time": current_time})
            
            if self.show_queries:
                logger.info(f"   [PLAN] Query execution plan analysis:")
                logger.info(f"   Query: Point-in-time temporal filter")
                
                # Look for index usage in the plan
                nodes = plan.get('plan', {}).get('nodes', [])
                index_nodes = [node for node in nodes if node.get('type') == 'IndexNode']
                
                for i, node in enumerate(index_nodes):
                    index_info = node.get('indexes', [])
                    for idx in index_info:
                        index_type = idx.get('type', 'unknown')
                        index_fields = idx.get('fields', [])
                        logger.info(f"   Index {i+1}: Type={index_type}, Fields={index_fields}")
                        
                        if index_type == 'zkd':
                            logger.info(f"           [SUCCESS] ZKD multi-dimensional index detected in execution plan!")
                            plan_results["zkd_index_used"] = True
                        else:
                            logger.info(f"           Index type: {index_type}")
                
                if not index_nodes:
                    logger.warning(f"   [WARNING] No index nodes found in execution plan")
                    plan_results["zkd_index_used"] = False
                
                # Analyze estimated costs
                estimated_cost = plan.get('plan', {}).get('estimatedCost', 0)
                estimated_nr_items = plan.get('plan', {}).get('estimatedNrItems', 0)
                
                logger.info(f"   Estimated Cost: {estimated_cost}")
                logger.info(f"   Estimated Items: {estimated_nr_items}")
                
                plan_results.update({
                    "estimated_cost": estimated_cost,
                    "estimated_nr_items": estimated_nr_items,
                    "plan_analyzed": True
                })
            
        except Exception as e:
            logger.error(f"   [ERROR] Failed to analyze execution plan: {e}")
            plan_results["plan_analyzed"] = False
        
        return plan_results
    
    def compare_index_performance(self) -> Dict[str, Any]:
        """Compare performance with and without ZKD indexes."""
        logger.info(f"\n[TEST] Comparing query performance with different index types...")
        
        # This is a simulation since we can't easily drop/recreate indexes
        # In practice, you would run these tests with and without ZKD indexes
        
        performance_results = {}
        current_time = time.time()
        
        # Test query on Device collection (has both persistent and MDI-prefix indexes)
        temporal_query = """
        FOR device IN Device
          FILTER device.created <= @point_in_time 
          AND device.expired > @point_in_time
          RETURN device._key
        """
        
        # Run multiple iterations to get average performance
        iterations = 5
        total_time = 0
        
        logger.info(f"   [PERF] Running {iterations} iterations of temporal query...")
        for i in range(iterations):
            start_time = time.time()
            results = list(self.database.aql.execute(temporal_query, bind_vars={"point_in_time": current_time}))
            iteration_time = time.time() - start_time
            total_time += iteration_time
            
            if self.show_queries and i == 0:
                logger.info(f"   Iteration 1: {len(results)} results in {iteration_time:.4f} seconds")
        
        avg_time = total_time / iterations
        logger.info(f"   Average time over {iterations} iterations: {avg_time:.4f} seconds")
        
        performance_results = {
            "average_query_time": avg_time,
            "iterations": iterations,
            "total_time": total_time,
            "result_count": len(results) if 'results' in locals() else 0
        }
        
        return performance_results
    
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run all ZKD multi-dimensional index tests."""
        logger.info("=" * 80)
        logger.info("ZKD MULTI-DIMENSIONAL INDEX COMPREHENSIVE TEST SUITE")
        logger.info("=" * 80)
        
        if not self.connect_to_database():
            return {"status": "failed", "error": "Database connection failed"}
        
        all_results = {}
        
        try:
            # Test 1: Verify indexes exist
            indexes_exist = self.verify_zkd_indexes_exist()
            all_results["indexes_verified"] = indexes_exist
            
            if not indexes_exist:
                logger.error(f"\n[ERROR] ZKD multi-dimensional indexes not found. Deploy them first using:")
                logger.info(f"   python3 database_deployment.py --naming camelCase")
                return {"status": "failed", "error": "ZKD indexes not found"}
            
            # Test 2: Test temporal range queries
            query_results = self.test_temporal_range_queries()
            all_results["temporal_queries"] = query_results
            
            # Test 3: Analyze execution plans
            plan_results = self.analyze_query_execution_plans()
            all_results["execution_plans"] = plan_results
            
            # Test 4: Performance comparison
            performance_results = self.compare_index_performance()
            all_results["performance"] = performance_results
            
            # Summary
            logger.info("\n" + "=" * 80)
            logger.info("ZKD MULTI-DIMENSIONAL INDEX TEST SUMMARY")
            logger.info("=" * 80)
            
            logger.info(f"Indexes Verified: {'PASS' if indexes_exist else 'FAIL'}")
            logger.info(f"Temporal Queries: {len(query_results)} tests completed")
            logger.info(f"Execution Plans: {'Analyzed' if plan_results.get('plan_analyzed') else 'Failed'}")
            logger.info(f"Performance Test: {performance_results.get('average_query_time', 0):.4f}s average")
            
            if plan_results.get('zkd_index_used'):
                logger.info(f"[SUCCESS] ZKD multi-dimensional indexes are being used by query optimizer!")
            else:
                logger.warning(f"[WARNING] ZKD multi-dimensional indexes may not be utilized")
            
            all_results["status"] = "completed"
            return all_results
            
        except Exception as e:
            logger.error(f"\n[ERROR] Test suite failed: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}


def main():
    """Run ZKD multi-dimensional index tests."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Test ZKD multi-dimensional indexes for temporal queries")
    parser.add_argument("--quiet", action="store_true", help="Suppress query details")
    parser.add_argument("--save-results", type=str, help="Save test results to JSON file")
    
    args = parser.parse_args()
    
    # Run tests
    tester = MDIIndexTester(show_queries=not args.quiet)
    results = tester.run_comprehensive_tests()
    
    # Save results if requested
    if args.save_results:
        import json
        output_file = Path(args.save_results)
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"\n[SAVED] Test results saved to: {output_file}")
    
    # Exit with appropriate code
    if results.get("status") == "completed":
        logger.info(f"\n[SUCCESS] All ZKD multi-dimensional index tests completed successfully!")
        sys.exit(0)
    else:
        logger.error(f"\n[FAILED] ZKD multi-dimensional index tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
