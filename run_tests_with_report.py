"""
Automated test runner with Allure report generation and viewing.

This script:
1. Runs pytest with Allure results collection
2. Generates HTML Allure report
3. Automatically opens the report in your default browser

Usage:
    python run_tests_with_report.py              # Run all tests
    python run_tests_with_report.py unit         # Run only unit tests
    python run_tests_with_report.py api          # Run only API tests
    python run_tests_with_report.py integration  # Run integration tests
"""

import subprocess
import sys
import os
import platform
import shutil
import webbrowser
from pathlib import Path


def cleanup_old_results():
    """Remove old allure results and reports."""
    results_dir = Path("allure-results")
    report_dir = Path("allure-report")
    
    if results_dir.exists():
        print("[*] Cleaning up old Allure results...")
        shutil.rmtree(results_dir)
    
    if report_dir.exists():
        print("[*] Cleaning up old Allure report...")
        shutil.rmtree(report_dir)


def run_tests(test_type="all"):
    """Run pytest with Allure results collection."""
    print(f"[*] Running {test_type} tests...")

    # Build pytest command
    if test_type == "all":
        os.environ["RUN_INTEGRATION"] = "1"
        cmd = [
            "pytest",
            "tests/unit/",
            "tests/api/",
            "tests/integration/",
            "-v",
            "--cov=src",
            "--cov-report=term",
            "--alluredir=allure-results"
        ]
    elif test_type == "unit":
        cmd = [
            "pytest",
            "tests/unit/",
            "-v",
            "--alluredir=allure-results"
        ]
    elif test_type == "api":
        cmd = [
            "pytest",
            "tests/api/",
            "-v",
            "--alluredir=allure-results"
        ]
    elif test_type == "integration":
        os.environ["RUN_INTEGRATION"] = "1"
        cmd = [
            "pytest",
            "tests/integration/",
            "-v",
            "--alluredir=allure-results"
        ]
    else:
        print(f"❌ Unknown test type: {test_type}")
        print("   Valid options: all, unit, api, integration")
        sys.exit(1)
    
    # Run pytest
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print(f"[!] Some tests failed (exit code {result.returncode}), but continuing to generate report...")
    else:
        print("[+] All tests passed!")
    
    return result.returncode


def generate_allure_report():
    """Generate Allure HTML report from results."""
    print("\n[*] Generating Allure report...")
    
    # Add scoop paths to environment for Windows BEFORE checking if allure exists
    if platform.system() == "Windows":
        home = os.path.expanduser("~")
        scoop_shims = os.path.join(home, "scoop", "shims")
        java_home = os.path.join(home, "scoop", "apps", "temurin-lts-jdk", "current")
        java_bin = os.path.join(java_home, "bin")
        
        # Update PATH to include scoop and java
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{scoop_shims};{java_bin};{current_path}"
        os.environ["JAVA_HOME"] = java_home
    
    # Check if allure CLI is installed (after PATH setup)
    try:
        allure_check = subprocess.run(
            ["allure", "--version"], 
            capture_output=True, 
            text=True,
            shell=platform.system() == "Windows"  # Use shell on Windows
        )
        allure_installed = allure_check.returncode == 0
    except FileNotFoundError:
        allure_installed = False
    
    if not allure_installed:
        print("[!] Allure CLI is not installed!")
        print("\n[*] Install Allure CLI:")
        if platform.system() == "Windows":
            print("   Using Scoop: scoop install allure")
            print("   Or download from: https://github.com/allure-framework/allure2/releases")
        elif platform.system() == "Darwin":
            print("   Using Homebrew: brew install allure")
        else:
            print("   See: https://allurereport.org/docs/install/")
        sys.exit(1)
    
    # Generate report
    result = subprocess.run(
        ["allure", "generate", "allure-results", "--clean", "-o", "allure-report"],
        capture_output=True,
        text=True,
        shell=platform.system() == "Windows"  # Use shell on Windows
    )
    
    if result.returncode != 0:
        print(f"[!] Failed to generate Allure report:\n{result.stderr}")
        sys.exit(1)
    
    print("[+] Allure report generated successfully!")


def open_report():
    """Open the Allure report in default browser using Allure's built-in server."""
    print("\n[*] Opening Allure report in browser...")
    
    report_dir = Path("allure-report")
    
    if not report_dir.exists():
        print(f"[!] Report directory not found: {report_dir}")
        sys.exit(1)
    
    # Use Allure's built-in server to avoid CORS issues with file:// URLs
    print("[*] Starting Allure server (this will open automatically)...")
    print("    Press Ctrl+C to stop the server when you're done viewing the report")
    
    try:
        # allure open command starts a web server and opens the browser
        result = subprocess.run(
            ["allure", "open", "allure-report"],
            shell=platform.system() == "Windows"
        )
        if result.returncode != 0:
            print(f"[!] Allure server exited with code {result.returncode}")
    except KeyboardInterrupt:
        print("\n[+] Allure server stopped")
    except Exception as e:
        print(f"[!] Error starting Allure server: {e}")
        # Fallback: try to open directly (may not work in all browsers)
        print("   Trying to open report file directly...")
        report_index = report_dir / "index.html"
        webbrowser.open(f"file://{report_index.absolute()}")
        print(f"   If report doesn't load, run: allure open allure-report")


def create_environment_properties():
    """Create environment.properties file for Allure report."""
    print("\n[*] Adding environment information...")
    
    results_dir = Path("allure-results")
    results_dir.mkdir(exist_ok=True)
    
    env_file = results_dir / "environment.properties"
    
    # Get Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    # Get OS info
    os_info = f"{platform.system()} {platform.release()}"
    
    # Get current date/time (Windows compatible)
    from datetime import datetime
    execution_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(env_file, "w") as f:
        f.write(f"Python.Version={python_version}\n")
        f.write(f"Operating.System={os_info}\n")
        f.write(f"Environment=Local Development\n")
        f.write(f"App.Version=1.0.0\n")
        f.write(f"Test.Execution.Date={execution_date}\n")


def main():
    """Main execution flow."""
    print("=" * 60)
    print("Automated Test Runner with Allure Report")
    print("=" * 60)
    
    # Get test type from command line
    test_type = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    try:
        # Step 1: Cleanup
        cleanup_old_results()
        
        # Step 2: Run tests
        test_exit_code = run_tests(test_type)
        
        # Step 3: Create environment info
        create_environment_properties()
        
        # Step 4: Generate report
        generate_allure_report()
        
        # Step 5: Open report
        open_report()
        
        print("\n" + "=" * 60)
        print("[+] Done! Allure report is now open in your browser.")
        print("=" * 60)
        
        # Exit with original test exit code
        sys.exit(test_exit_code)
        
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
