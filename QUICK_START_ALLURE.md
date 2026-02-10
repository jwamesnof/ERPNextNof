# 🎯 Quick Start: View Allure Reports

## ✅ Setup Complete!

Your project now has automatic Allure report generation and viewing for both local and GitHub environments.

---

## 🖥️ LOCAL: View Reports (3 Ways)

### Option 1: Automated Script (Easiest) ⭐
```bash
# Windows - Just double-click:
run_tests.bat

# Or from command line:
python run_tests_with_report.py
```

**What happens:**
1. ✨ Cleans old reports
2. 🧪 Runs all tests
3. 📊 Generates Allure report
4. 🌐 **Opens browser automatically!**

**Run specific tests:**
```bash
python run_tests_with_report.py unit         # Unit tests only
python run_tests_with_report.py api          # API tests only
python run_tests_with_report.py integration  # Integration tests
```

### Option 2: Manual Steps
```bash
# Step 1: Run tests
pytest tests/unit/ tests/api/ -v --alluredir=allure-results

# Step 2: Generate and open report
allure generate allure-results --clean -o allure-report
allure open allure-report
```

### Option 3: Direct Browser Access
After generating report:
```
file:///C:/Users/NofJawamis/Desktop/ERPNextNof/allure-report/index.html
```

---

## 🌐 GITHUB: View Reports (2 Ways)

### Option 1: PR Comments (Automatic) ⭐
1. Create/update any Pull Request
2. Wait for CI workflow to complete (~2-3 minutes)
3. Find automated comment: "📊 Allure Test Report"
4. Click the report link

**Example comment:**
```
📊 Allure Test Report

Your test report is ready! 🎉

🔗 [View Interactive Allure Report](https://username.github.io/repo/123/)
```

### Option 2: GitHub Pages Direct
```
https://<your-username>.github.io/<repo-name>/<run-number>/
```

---

## 🚀 Try It Now!

### Test Locally:
```bash
# Make sure you're in the project directory
cd C:\Users\NofJawamis\Desktop\ERPNextNof

# Activate virtual environment (if not already)
.venv\Scripts\activate

# Run with auto-open (Windows)
run_tests.bat

# Or Python script
python run_tests_with_report.py unit
```

### Test on GitHub:
1. Make a small change (e.g., edit this file)
2. Commit and push to a new branch
3. Create Pull Request
4. Watch for the Allure report comment!

---

## 📋 What You'll See in Reports

### Overview Dashboard
- ✅ Total tests passed/failed
- 📊 Success rate percentage  
- ⏱️ Execution time
- 📈 Test trends

### Test Details
- Individual test results
- Execution duration
- Error messages and stack traces
- Test history across runs

### Environment Info
- Python version
- Operating system
- Test type (unit/API/integration)
- Execution timestamp

---

## 🔧 Troubleshooting

### Local: "allure: command not found"
**Install Allure CLI:**

Windows (Scoop):
```bash
scoop install allure
```

Windows (Manual):
1. Download: https://github.com/allure-framework/allure2/releases
2. Extract to `C:\allure`
3. Add `C:\allure\bin` to PATH

Verify:
```bash
allure --version
```

### GitHub: Report link returns 404
**Enable GitHub Pages (one-time):**
1. Go to: Settings → Pages
2. Source: `gh-pages` branch
3. Save and wait 2-3 minutes

### Local: Browser doesn't open automatically
**Fallback:**
```bash
# Generate report
allure generate allure-results --clean -o allure-report

# Open manually
start allure-report\index.html  # Windows
```

---

## 📚 Full Documentation

For advanced features, customization, and detailed guides:
- 📖 [ALLURE_REPORTS_GUIDE.md](ALLURE_REPORTS_GUIDE.md) - Complete guide
- 📊 [Official Allure Docs](https://allurereport.org/docs/)
- 🧪 [Pytest Integration](https://allurereport.org/docs/pytest/)

---

## ✨ Quick Reference

| Action | Command |
|--------|---------|
| 🖥️ Run all tests locally + open report | `run_tests.bat` or `python run_tests_with_report.py` |
| 🧪 Run unit tests only | `python run_tests_with_report.py unit` |
| 🔌 Run API tests only | `python run_tests_with_report.py api` |
| 🌐 View GitHub report | Check PR comment for link |
| 📁 Manual report location | `allure-report/index.html` |

---

**Ready to go!** 🚀 Try running `run_tests.bat` now to see your Allure report in action!
