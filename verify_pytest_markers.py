#!/usr/bin/env python3
"""Verify pytest markers are correctly added to all test files."""

import os
import re
from pathlib import Path
import sys

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_pytest_marker(file_path, expected_marker=None):
    """Check if a file has pytest marker."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Look for pytestmark pattern
    if 'pytestmark' in content:
        # Extract the marker line
        match = re.search(r'pytestmark\s*=\s*(.+?)(?:\n|$)', content, re.MULTILINE)
        if match:
            return True, match.group(1).strip()[:60]  # First 60 chars
    return False, "No marker found"

def main():
    """Main verification function."""
    test_dir = Path('tests')
    
    results = {
        'unit': [],
        'api': [],
        'integration': []
    }
    
    # Check all test files
    for test_file in test_dir.rglob('test_*.py'):
        rel_path = test_file.relative_to('.')
        category = str(test_file.parent.name)
        
        has_marker, marker_info = check_pytest_marker(test_file)
        
        if category in results:
            results[category].append({
                'file': str(rel_path),
                'has_marker': has_marker,
                'marker': marker_info
            })
    
    # Print results
    print("\nPYTEST MARKER VERIFICATION")
    print("=" * 70)
    
    for category, files in results.items():
        print(f"\n{category.upper()} TESTS ({len(files)} files):")
        print("-" * 70)
        for file_info in files:
            status = "[OK]" if file_info['has_marker'] else "[FAIL]"
            print(f"{status} {file_info['file']:<50} {file_info['marker']}")
    
    # Summary
    total_with_markers = sum(
        1 for files in results.values() 
        for f in files 
        if f['has_marker']
    )
    total_files = sum(len(files) for files in results.values())
    
    print("\n" + "=" * 70)
    print(f"SUMMARY: {total_with_markers}/{total_files} files have pytest markers")
    
    if total_with_markers == total_files:
        print("[OK] All test files have pytest markers!")
    else:
        print(f"[FAIL] {total_files - total_with_markers} files missing markers")
    
    # Check fixture scopes
    print("\n" + "=" * 70)
    print("\nFIXTURE SCOPE VERIFICATION (tests/conftest.py)")
    print("-" * 70)
    
    conftest_path = Path('tests/conftest.py')
    if conftest_path.exists():
        with open(conftest_path, 'r') as f:
            content = f.read()
        
        # Count scope specifications
        session_fixtures = len(re.findall(r'@pytest.fixture\(scope="session"\)', content))
        module_fixtures = len(re.findall(r'@pytest.fixture\(scope="module"\)', content))
        function_fixtures = len(re.findall(r'@pytest.fixture\(scope="function"\)', content))
        
        print(f"Session-scoped fixtures: {session_fixtures}")
        print(f"Module-scoped fixtures: {module_fixtures}")
        print(f"Function-scoped fixtures: {function_fixtures}")
        
        if session_fixtures > 0 and module_fixtures > 0:
            print("\n[OK] Fixture scopes properly optimized!")
        else:
            print("\n[WARN] Some fixture scopes may need optimization")

if __name__ == '__main__':
    main()
