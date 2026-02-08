#!/bin/bash
# Quick test runner with Allure report for Linux/macOS
# Usage: ./run_tests.sh [test_type]
# Examples:
#   ./run_tests.sh          (runs all tests)
#   ./run_tests.sh unit     (runs unit tests only)
#   ./run_tests.sh api      (runs API tests only)

set -e

echo "========================================"
echo "Test Runner with Allure Report"
echo "========================================"
echo ""

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Run the Python script
python run_tests_with_report.py "$@"
