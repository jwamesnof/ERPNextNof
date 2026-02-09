# Allure Test Reports Guide

This guide explains how to automatically generate and view Allure test reports both locally and in GitHub.

## 📊 What is Allure?

Allure is a powerful test reporting framework that provides:
- **Interactive HTML reports** with graphs and trends
- **Test history tracking** across multiple runs
- **Detailed test execution data** (duration, steps, attachments)
- **Categorization and filtering** of test results

---

## 🖥️ Local Usage

### Prerequisites

**1. Install Allure CLI:**

**Windows (using Scoop):**
```bash
scoop install allure
```

**Windows (manual):**
- Download from https://github.com/allure-framework/allure2/releases
- Extract to `C:\allure`
- Add `C:\allure\bin` to your PATH

**macOS:**
```bash
brew install allure
```

**Linux:**
```bash
sudo apt-add-repository ppa:qameta/allure
sudo apt-get update
sudo apt-get install allure
```

**Verify installation:**
```bash
allure --version
```

### Automated Script Usage

**Quick Run (Recommended):**
```bash
# Run all tests and open report automatically
python run_tests_with_report.py

# Run specific test types
python run_tests_with_report.py unit
python run_tests_with_report.py api
python run_tests_with_report.py integration
```

**What the script does:**
1. ✨ Cleans up old reports
2. 🧪 Runs your selected tests
3. 📝 Adds environment information
4. 📊 Generates HTML report
5. 🌐 Opens report in your browser automatically

### Manual Usage

If you prefer step-by-step control:

```bash
# Step 1: Run tests with Allure results collection
pytest tests/unit/ tests/api/ -v --alluredir=allure-results

# Step 2: Generate HTML report
allure generate allure-results --clean -o allure-report

# Step 3: Open report in browser
allure open allure-report
```

### Report Location

- **Results data**: `allure-results/` (JSON files)
- **HTML report**: `allure-report/index.html`
- **Direct access**: Open `file:///path/to/ERPNextNof/allure-report/index.html` in browser

---

## 🌐 GitHub Actions Usage

### Automatic Report Generation

Every pull request automatically:
1. ✅ Runs all unit and API tests
2. 📊 Generates Allure report
3. 🌐 Publishes to GitHub Pages
4. 💬 Posts comment with report link in PR

### Viewing Reports on GitHub

**Method 1: PR Comment (Easiest)**
- Open any Pull Request
- Find the automated comment "📊 Allure Test Report"
- Click the report link (available 2-3 minutes after workflow completes)

**Method 2: GitHub Pages Direct Access**
```
https://<username>.github.io/<repository-name>/<run-number>/
```

**Method 3: Actions Artifacts**
- Go to **Actions** tab
- Click on the workflow run
- Download `allure-results` artifact
- Generate report locally: `allure generate allure-results`

### Enable GitHub Pages (One-Time Setup)

If reports don't open, enable GitHub Pages:

1. Go to **Settings** → **Pages**
2. **Source**: Deploy from a branch
3. **Branch**: `gh-pages` / `root`
4. Click **Save**
5. Wait 2-3 minutes for deployment

---

## 📋 Report Features

### What You'll See

**Overview Page:**
- Total tests: passed/failed/skipped
- Success rate percentage
- Test duration trends
- Categories and suites

**Detailed Test Information:**
- Execution time per test
- Test steps and assertions
- Error messages and stack traces
- Test history (across multiple runs)

**Advanced Features:**
- Severity categorization (critical, normal, minor)
- Test grouping by features/stories
- Environment information
- Attachments (logs, screenshots)

### Environment Information

Each report includes environment data:
- Python version
- Operating System
- Test execution date
- Test type (unit/API/integration)
- CI workflow name (GitHub only)

---

## 🔧 Customization

### Adding Test Metadata

Add decorators to your tests for better reporting:

```python
import allure
from allure import severity_level

@allure.severity(severity_level.CRITICAL)
@allure.feature('Order Promise')
@allure.story('Promise Calculation')
@allure.title('Calculate promise for in-stock item')
def test_calculate_promise_in_stock():
    """Test promise calculation when item is in stock"""
    # test code here
    pass
```

### Adding Test Steps

```python
import allure

def test_complete_workflow():
    with allure.step("Step 1: Prepare test data"):
        # setup code
        pass
    
    with allure.step("Step 2: Calculate promise"):
        # calculation code
        pass
    
    with allure.step("Step 3: Verify results"):
        # assertions
        pass
```

### Adding Attachments

```python
import allure

def test_with_attachment():
    response = client.get("/api/items/stock")
    allure.attach(
        response.text,
        name="API Response",
        attachment_type=allure.attachment_type.JSON
    )
```

---

## 🐛 Troubleshooting

### Local Issues

**Problem: "allure: command not found"**
- Solution: Install Allure CLI (see Prerequisites)

**Problem: Report doesn't open automatically**
- Solution: Manually open `allure-report/index.html` in browser

**Problem: Empty report**
- Solution: Ensure tests ran successfully and created `allure-results/` directory

### GitHub Issues

**Problem: Report link returns 404**
- Solution: Enable GitHub Pages (see "Enable GitHub Pages" section)
- Wait 2-3 minutes after enabling

**Problem: No PR comment posted**
- Solution: Check workflow permissions include `pull-requests: write`

**Problem: Old reports not visible**
- Solution: Reports are kept for last 20 runs (configurable in `keep_reports` setting)

---

## 📁 File Structure

```
ERPNextNof/
├── allure-results/           # Test results (JSON files)
│   ├── environment.properties
│   ├── *-result.json
│   └── *-container.json
│
├── allure-report/            # Generated HTML report
│   ├── index.html
│   ├── data/
│   └── widgets/
│
├── run_tests_with_report.py  # Automated script
├── pytest.ini                # Pytest config (includes --alluredir)
└── requirements.txt          # Includes allure-pytest
```

---

## 🚀 Quick Reference

**Local Commands:**
```bash
# All tests with auto-open
python run_tests_with_report.py

# Unit tests only
python run_tests_with_report.py unit

# Manual generation
allure generate allure-results -o allure-report
allure open allure-report
```

**GitHub:**
- Reports auto-publish to PR comments
- Direct URL: `https://<user>.github.io/<repo>/<run>/`
- Enable Pages: Settings → Pages → gh-pages branch

**Customization:**
```python
@allure.severity(severity_level.CRITICAL)
@allure.feature('Feature Name')
@allure.story('User Story')
```

---

## 📚 Additional Resources

- **Allure Documentation**: https://allurereport.org/docs/
- **Pytest Integration**: https://allurereport.org/docs/pytest/
- **GitHub Actions Plugin**: https://github.com/peaceiris/actions-gh-pages
- **Examples**: See `tests/` directory for decorated test examples

---

## ✨ Tips

1. **Run locally before pushing**: Catch issues early with immediate feedback
2. **Use severity markers**: Help prioritize test failures
3. **Add descriptive titles**: Makes reports easier to navigate
4. **Include environment info**: Helps reproduce issues
5. **Check trends**: Monitor test duration and flakiness over time

---

**Need Help?** 
- Check the troubleshooting section above
- Review the Allure documentation
- Ensure all prerequisites are installed
