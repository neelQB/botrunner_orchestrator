# Publishing BotRunner as a Pip Package

Complete guide to building, testing, and publishing the BotRunner package to PyPI.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Building the Package](#building-the-package)
- [Testing Locally](#testing-locally)
- [Publishing to PyPI](#publishing-to-pypi)
- [Version Management](#version-management)
- [Distribution Methods](#distribution-methods)
- [Troubleshooting](#troubleshooting)

---

## Overview

BotRunner is configured as a pip-installable package using Poetry. The package metadata is defined in `pyproject.toml` and can be built, distributed, and published to PyPI.

**Current Package Info:**
- **Name:** botrunner
- **Version:** 2.0.0
- **Built Packages:** `dist/botrunner-2.0.0-py3-none-any.whl` and `dist/botrunner-2.0.0.tar.gz`

---

## Prerequisites

### 1. Conda Environment

```powershell
# Activate environment
conda activate botenv

# Verify Poetry is installed
poetry --version
# Output: Poetry (version 1.4.0)
```

### 2. PyPI Account (for publishing)

- Create account at https://pypi.org/account/register/
- Verify email address
- Enable 2FA (recommended)

### 3. PyPI API Token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name it (e.g., "botrunner-publish")
4. Set scope to "Entire account" or specific project
5. Copy the token (starts with `pypi-`)

⚠️ **Save the token immediately** - you cannot view it again

---

## Building the Package

### Step 1: Update Package Metadata

Edit `pyproject.toml` to update placeholder information:

```toml
[tool.poetry]
name = "botrunner"
version = "2.0.0"
description = "Enterprise Multi-Agent Sales Bot Framework"
authors = ["Your Name <your.email@example.com>"]  # ← Update this
homepage = "https://github.com/yourusername/botrunner"  # ← Update this
repository = "https://github.com/yourusername/botrunner"  # ← Update this
```

### Step 2: Build the Package

```powershell
# Clean old builds (optional but recommended)
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue

# Build new package
poetry build
```

**Output:**
```
Building botrunner (2.0.0)
  - Building sdist
  - Built botrunner-2.0.0.tar.gz
  - Building wheel
  - Built botrunner-2.0.0-py3-none-any.whl
```

**Files created in `dist/`:**
- `botrunner-2.0.0-py3-none-any.whl` - Wheel (binary distribution)
- `botrunner-2.0.0.tar.gz` - Source distribution

---

## Testing Locally

### Test 1: Install from Wheel

```powershell
# Create test environment
conda create -n test-botrunner python=3.11
conda activate test-botrunner

# Install from local wheel
pip install dist/botrunner-2.0.0-py3-none-any.whl

# Test import
python -c "import app; print(f'BotRunner v{app.__version__}')"

# Clean up
conda deactivate
conda env remove -n test-botrunner
```

### Test 2: Check Package Metadata

```powershell
# After installation
pip show botrunner
```

**Expected output:**
```
Name: botrunner
Version: 2.0.0
Summary: Enterprise Multi-Agent Sales Bot Framework
Home-page: https://github.com/yourusername/botrunner
Author: Your Name
Author-email: your.email@example.com
License: MIT
Location: ...
Requires:
Required-by:
```

### Test 3: Verify Package Contents

```powershell
# List files in wheel
python -m zipfile -l dist/botrunner-2.0.0-py3-none-any.whl

# Or extract to inspect
python -m zipfile -e dist/botrunner-2.0.0-py3-none-any.whl temp_extract
```

---

## Publishing to PyPI

### Step 1: Configure Poetry with PyPI Token

```powershell
# Add PyPI token (one-time setup)
poetry config pypi-token.pypi pypi-AgEIcHlwaS5vcmcC...

# Verify configuration
poetry config --list | Select-String "pypi-token"
```

### Step 2: Test on TestPyPI (Recommended)

TestPyPI is a sandbox for testing package uploads.

**Get TestPyPI token:**
1. Register at https://test.pypi.org/account/register/
2. Create API token at https://test.pypi.org/manage/account/token/

**Configure and publish:**

```powershell
# Add TestPyPI repository
poetry config repositories.testpypi https://test.pypi.org/legacy/

# Add TestPyPI token
poetry config pypi-token.testpypi pypi-AgEIcHl...

# Publish to TestPyPI
poetry publish --repository testpypi
```

**Test installation from TestPyPI:**

```powershell
pip install --index-url https://test.pypi.org/simple/ botrunner
```

### Step 3: Publish to Production PyPI

⚠️ **Warning:** Once published, you cannot delete or replace a version!

```powershell
# Final check
poetry build
pip show botrunner  # Verify local version

# Publish to PyPI
poetry publish

# You'll see:
# Publishing botrunner (2.0.0) to PyPI
#  - Uploading botrunner-2.0.0-py3-none-any.whl ... done
#  - Uploading botrunner-2.0.0.tar.gz ... done
```

### Step 4: Verify on PyPI

1. Visit https://pypi.org/project/botrunner/
2. Check package page displays correctly
3. Test installation:

```powershell
pip install botrunner
```

---

## Version Management

### Semantic Versioning

BotRunner follows [SemVer](https://semver.org/): `MAJOR.MINOR.PATCH`

- **MAJOR** (3.0.0): Breaking changes
- **MINOR** (2.1.0): New features, backward compatible
- **PATCH** (2.0.1): Bug fixes

### Bump Version with Poetry

```powershell
# Patch version (2.0.0 → 2.0.1)
poetry version patch

# Minor version (2.0.0 → 2.1.0)
poetry version minor

# Major version (2.0.0 → 3.0.0)
poetry version major

# Pre-release versions
poetry version prepatch   # 2.0.0 → 2.0.1-alpha.0
poetry version preminor   # 2.0.0 → 2.1.0-alpha.0
poetry version premajor   # 2.0.0 → 3.0.0-alpha.0

# Specific version
poetry version 2.5.3
```

### Release Workflow

```powershell
# 1. Update version
poetry version patch

# 2. Update CHANGELOG.md
# Add release notes

# 3. Commit version bump
git add pyproject.toml CHANGELOG.md
git commit -m "Release v2.0.1"

# 4. Create git tag
git tag v2.0.1
git push origin v2.0.1

# 5. Build and publish
poetry build
poetry publish

# 6. Push changes
git push origin main
```

---

## Distribution Methods

### Method 1: PyPI (Public Registry)

**Best for:** Open-source projects, public packages

```powershell
poetry publish
```

**Installation:**
```bash
pip install botrunner
```

**Pros:** ✅ Easy discovery, automatic versioning, pip native  
**Cons:** ⚠️ Public, cannot delete versions

---

### Method 2: Private PyPI Server

**Best for:** Enterprise, proprietary code

**Setup private repository:**

```powershell
# Configure repository
poetry config repositories.private https://pypi.yourcompany.com

# Add authentication
poetry config http-basic.private username password

# Publish
poetry publish --repository private
```

**Installation:**
```bash
pip install botrunner --index-url https://pypi.yourcompany.com/simple/
```

---

### Method 3: Git Repository

**Best for:** Private projects, direct from source

**Installation from Git:**
```bash
# Install from main branch
pip install git+https://github.com/yourusername/botrunner.git

# Install from specific branch
pip install git+https://github.com/yourusername/botrunner.git@feature-branch

# Install from tag/release
pip install git+https://github.com/yourusername/botrunner.git@v2.0.0
```

**In requirements.txt:**
```
botrunner @ git+https://github.com/yourusername/botrunner.git@v2.0.0
```

---

### Method 4: Wheel File Distribution

**Best for:** Internal distribution, no internet access

**Share the wheel:**
```powershell
# Copy wheel file to shared location
Copy-Item dist/botrunner-2.0.0-py3-none-any.whl \\shared\packages\
```

**Installation:**
```bash
pip install botrunner-2.0.0-py3-none-any.whl
```

---

### Method 5: Artifact Repository (Nexus, Artifactory)

**Best for:** Enterprise CI/CD pipelines

Example with Nexus:

```powershell
# Configure Nexus repository
poetry config repositories.nexus https://nexus.yourcompany.com/repository/pypi-hosted/

# Upload
poetry publish --repository nexus --username admin --password secret
```

---

## Troubleshooting

### Issue: "Repository not found"

**Cause:** Poetry not configured with PyPI token.

**Solution:**
```powershell
poetry config pypi-token.pypi YOUR_TOKEN_HERE
```

---

### Issue: "File already exists"

**Cause:** Version already published to PyPI.

**Solution:**
```powershell
# Bump version
poetry version patch

# Rebuild
poetry build

# Publish new version
poetry publish
```

**Note:** You cannot overwrite existing versions on PyPI!

---

### Issue: "Package is empty" or "No files found"

**Cause:** `packages` not configured correctly in `pyproject.toml`.

**Solution:**

Check `pyproject.toml` has:
```toml
[tool.poetry]
packages = [{include = "app"}]
```

---

### Issue: "Invalid token"

**Cause:** Expired or incorrect API token.

**Solution:**
```powershell
# Generate new token on PyPI
# Update token
poetry config pypi-token.pypi NEW_TOKEN_HERE
```

---

### Issue: Build fails with missing files

**Cause:** Required files not included in `MANIFEST.in`.

**Solution:**

Update `MANIFEST.in`:
```
include README.md
include LICENSE
include requirements*.txt
recursive-include app *.py
recursive-exclude * __pycache__
recursive-exclude * *.pyc
```

Rebuild:
```powershell
poetry build
```

---

### Issue: Dependencies not installed with package

**Cause:** Dependencies not listed in `pyproject.toml` `[tool.poetry.dependencies]`.

**Solution:**

This project uses a hybrid approach where dependencies are in `requirements.txt`. Users must install dependencies separately:

```bash
pip install botrunner
pip install -r requirements-docker.txt
```

Or add core dependencies to `pyproject.toml` if you want them auto-installed.

---

## Best Practices

### ✅ Do's

1. **Always test locally** before publishing
2. **Use TestPyPI** for first-time publishing
3. **Follow SemVer** for versioning
4. **Update CHANGELOG.md** with each release
5. **Tag releases** in git
6. **Keep pyproject.toml updated** with accurate metadata
7. **Test installation** in clean environment

### ❌ Don'ts

1. **Never publish** without testing
2. **Never reuse** version numbers
3. **Never include secrets** in package
4. **Never publish** with placeholder author/URLs
5. **Avoid breaking changes** in minor/patch versions

---

## Quick Reference

### Publishing Checklist

- [ ] Update version: `poetry version patch`
- [ ] Update CHANGELOG.md
- [ ] Test locally: `pip install dist/*.whl`
- [ ] Clean build: `Remove-Item -Recurse dist`
- [ ] Build: `poetry build`
- [ ] Test on TestPyPI: `poetry publish --repository testpypi`
- [ ] Test installation from TestPyPI
- [ ] Publish to PyPI: `poetry publish`
- [ ] Verify on pypi.org
- [ ] Create git tag: `git tag v2.0.1`
- [ ] Push: `git push --tags`

### Essential Commands

```powershell
# Version management
poetry version patch|minor|major

# Build
poetry build

# Publish to TestPyPI
poetry publish --repository testpypi

# Publish to PyPI
poetry publish

# Check package
pip show botrunner

# Install from PyPI
pip install botrunner

# Install from local wheel
pip install dist/botrunner-2.0.0-py3-none-any.whl
```

---

## Additional Resources

- **Poetry Documentation:** https://python-poetry.org/docs/
- **PyPI Publishing Guide:** https://python-poetry.org/docs/libraries/#publishing-to-pypi
- **Python Packaging Guide:** https://packaging.python.org/
- **SemVer Specification:** https://semver.org/
- **TestPyPI:** https://test.pypi.org/

---

## Summary

✅ **Package Setup:** Complete  
✅ **Built Packages:** In `dist/` directory  
✅ **Metadata:** Configured in `pyproject.toml`  
✅ **Ready to Publish:** Yes  

**Next:** Update metadata → test locally → publish to TestPyPI → publish to PyPI

For general Poetry usage, see [POETRY.md](POETRY.md).
