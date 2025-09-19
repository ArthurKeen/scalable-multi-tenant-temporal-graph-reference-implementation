#!/usr/bin/env python3
"""
Demo Launcher Script

Provides easy access to different demonstration modes for the multi-tenant
network asset management system.

Author: Network Asset Management Demo
"""

import sys
import os
from pathlib import Path


def print_banner():
    """Print the demo launcher banner."""
    print("=" * 80)
    print("MULTI-TENANT NETWORK ASSET MANAGEMENT DEMO LAUNCHER")
    print("=" * 80)
    print()


def print_demo_options():
    """Print available demo options."""
    print("Available Demo Options:")
    print()
    print("1. Automated Walkthrough (Interactive) 🎯 PRESENTATION MODE")
    print("   → Clean, demo-friendly output with validation sections SKIPPED")
    print("   → Perfect for live presentations - no information overload")
    print("   → Add --verbose for detailed technical output + validation")
    print()
    print("2. Automated Walkthrough (Auto-Advance) 🎯 PRESENTATION MODE")
    print("   → Clean, continuous demonstration with validation sections SKIPPED")
    print("   → Add --verbose for detailed technical output + validation")
    print()
    print("3. Comprehensive Demo (Fast)")
    print("   → Complete system demonstration without walkthrough")
    print("   → Best for testing and validation")
    print()
    print("4. Individual Components")
    print("   → Run specific parts of the demonstration")
    print("   → Best for focused testing")
    print()
    print("5. Validation Only")
    print("   → Run comprehensive validation suite")
    print("   → Best for system verification")
    print()
    print("0. Exit")
    print()


def run_automated_walkthrough_interactive():
    """Run the automated walkthrough in interactive mode."""
    print("Starting Automated Walkthrough (Interactive Mode)")
    print("   → Press Enter at each pause to continue")
    print("   → Press Ctrl+C to exit at any time")
    print()
    
    verbose = input("Enable verbose mode? (y/N): ").strip().lower()
    verbose_flag = " --verbose" if verbose in ['y', 'yes'] else ""
    
    input("Press Enter to begin...")
    
    os.system(f"python3 automated_demo_walkthrough.py --interactive{verbose_flag}")


def run_automated_walkthrough_auto():
    """Run the automated walkthrough in auto-advance mode."""
    print("Starting Automated Walkthrough (Auto-Advance Mode)")
    print("   → Demonstration will advance automatically")
    print("   → Press Ctrl+C to exit at any time")
    print()
    
    try:
        pause_duration = input("Enter pause duration in seconds (default: 3): ").strip()
        if not pause_duration:
            pause_duration = "3"
        
        pause_duration = int(pause_duration)
        
    except ValueError:
        print("[ERROR] Invalid duration, using default of 3 seconds")
        pause_duration = 3
    
    verbose = input("Enable verbose mode? (y/N): ").strip().lower()
    verbose_flag = " --verbose" if verbose in ['y', 'yes'] else ""
    
    os.system(f"python3 automated_demo_walkthrough.py --auto-advance --pause-duration {pause_duration}{verbose_flag}")


def run_comprehensive_demo():
    """Run the comprehensive demo with interactive walkthrough."""
    print("Starting Comprehensive Demo - Interactive Walkthrough")
    print("   → Complete system demonstration with guided explanations")
    print("   → Professional presentation mode with pauses")
    print()
    
    print("Launching interactive demo walkthrough...")
    os.system("python3 automated_demo_walkthrough.py --interactive")


def run_individual_components():
    """Run individual demonstration components."""
    print("Individual Component Demo")
    print()
    print("Available Components:")
    print("1. Data Generation")
    print("2. Database Deployment")
    print("3. Transaction Simulation")
    print("4. TTL Demonstration")
    print("5. Scale-Out Demo")
    print("6. Validation Suite")
    print("0. ← Back to Main Menu")
    print()
    
    try:
        choice = int(input("Select component (0-6): "))
        
        if choice == 0:
            return
        elif choice == 1:
            tenants = input("Number of tenants (default: 4): ").strip() or "4"
            naming = input("Naming convention (camelCase/snake_case) [camelCase]: ").strip() or "camelCase"
            os.system(f"python3 asset_generator.py --tenants {tenants} --naming {naming} --environment development")
        elif choice == 2:
            naming = input("Naming convention (camelCase/snake_case) [camelCase]: ").strip() or "camelCase"
            os.system(f"python3 database_deployment.py --naming {naming}")
        elif choice == 3:
            naming = input("Naming convention (camelCase/snake_case) [camelCase]: ").strip() or "camelCase"
            devices = input("Number of device changes (default: 5): ").strip() or "5"
            software = input("Number of software changes (default: 3): ").strip() or "3"
            os.system(f"python3 transaction_simulator.py --naming {naming} --devices {devices} --software {software}")
        elif choice == 4:
            naming = input("Naming convention (camelCase/snake_case) [camelCase]: ").strip() or "camelCase"
            os.system(f"python3 ttl_demo_scenarios.py --naming {naming}")
        elif choice == 5:
            naming = input("Naming convention (camelCase/snake_case) [camelCase]: ").strip() or "camelCase"
            save_report = input("Save report? (y/N): ").strip().lower()
            report_flag = "--save-report" if save_report.startswith('y') else ""
            os.system(f"python3 scale_out_demo.py --naming {naming} {report_flag}")
        elif choice == 6:
            os.system("python3 validation_suite.py")
        else:
            print("[ERROR] Invalid choice")
            
    except ValueError:
        print("[ERROR] Invalid input")
    except KeyboardInterrupt:
        print("\n[STOP] Component demo interrupted")


def run_validation_only():
    """Run only the validation suite."""
    print("Starting Validation Suite")
    print("   → Comprehensive system validation")
    print("   → No data generation or changes")
    print()
    
    os.system("python3 validation_suite.py")


def main():
    """Main demo launcher function."""
    while True:
        try:
            print_banner()
            print_demo_options()
            
            choice = input("Select demo option (0-5): ").strip()
            
            if choice == "0":
                print("Thank you for using the demo system!")
                sys.exit(0)
            elif choice == "1":
                run_automated_walkthrough_interactive()
            elif choice == "2":
                run_automated_walkthrough_auto()
            elif choice == "3":
                run_comprehensive_demo()
            elif choice == "4":
                run_individual_components()
            elif choice == "5":
                run_validation_only()
            else:
                print("[ERROR] Invalid choice. Please select 0-5.")
            
            print("\n" + "="*80)
            input("Press Enter to return to main menu...")
            
        except KeyboardInterrupt:
            print("\n\nDemo launcher interrupted. Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERROR] Demo launcher error: {e}")
            input("Press Enter to continue...")


if __name__ == "__main__":
    main()