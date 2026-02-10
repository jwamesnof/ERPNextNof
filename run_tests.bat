@echo off
REM Quick test runner with Allure report for Windows
REM Usage: run_tests.bat [test_type]
REM Examples:
REM   run_tests.bat          (runs all tests)
REM   run_tests.bat unit     (runs unit tests only)
REM   run_tests.bat api      (runs API tests only)

echo ========================================
echo Test Runner with Allure Report
echo ========================================
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Run the Python script
python run_tests_with_report.py %*

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo Press any key to exit...
    pause > nul
)
