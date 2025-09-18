#!/usr/bin/env python3
"""
Database Reset Script

Standalone script to reset the ArangoDB database to a clean state
before running demos. This ensures the demo starts with exactly 
4 tenants instead of leftover data from previous runs.

Usage:
    python3 reset_database.py
"""

import sys
from automated_demo_walkthrough import AutomatedDemoWalkthrough

def main():
    """Reset the database to clean state."""
    print("=" * 60)
    print("DATABASE RESET UTILITY")
    print("=" * 60)
    print("This will clear all existing tenant data and graphs")
    print("to ensure a clean start for the demo.")
    print()
    
    response = input("Are you sure you want to reset the database? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("Reset cancelled.")
        return 0
    
    print("\nStarting database reset...")
    demo = AutomatedDemoWalkthrough(interactive=False)
    
    if demo.reset_database():
        print("\n" + "=" * 60)
        print("DATABASE RESET COMPLETE")
        print("=" * 60)
        print("The database is now clean and ready for a fresh demo.")
        print("You can now run:")
        print("  python3 automated_demo_walkthrough.py --interactive")
        print("  python3 demo_launcher.py")
        return 0
    else:
        print("\n" + "=" * 60)
        print("DATABASE RESET FAILED")
        print("=" * 60)
        print("Please check your database connection and try again.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
