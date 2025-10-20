# PyPI Publishing Guide for Binwalk3

## Prerequisites

✅ **Completed**:
- Package built successfully (`dist/binwalk3-3.1.0-py3-none-any.whl`)
- Source distribution created (`dist/binwalk3-3.1.0.tar.gz`)
- Both packages validated with twine (`PASSED`)
- Local installation tested and working
- Binary included and functional (8.9 MB, verified)

## Phase 10.1: Create PyPI Accounts

### TestPyPI Account (for testing)
1. Go to https://test.pypi.org/account/register/
2. Create account with email verification
3. Enable Two-Factor Authentication (recommended)
4. Generate API token:
   - Go to https://test.pypi.org/manage/account/token/
   - Token name: `binwalk3-upload`
   - Scope: "Entire account" (first upload) or "Project: binwalk3" (after first upload)
   - **Save the token** - you'll only see it once!

### Production PyPI Account
1. Go to https://pypi.org/account/register/
2. Create account with email verification
3. Enable Two-Factor Authentication (required for publishing)
4. Generate API token:
   - Go to https://pypi.org/manage/account/token/
   - Token name: `binwalk3-upload`
   - Scope: "Entire account" (first upload) or "Project: binwalk3" (after first upload)
   - **Save the token** - you'll only see it once!

## Phase 10.2: Configure Authentication

### Option 1: Use .pypirc file (Recommended)
Create or edit `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-AgENdGVzdC5weXBpLm9yZw...YOUR_PRODUCTION_TOKEN

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgENdGVzdC5weXBpLm9yZw...YOUR_TEST_TOKEN
```

**Security**: Set proper permissions:
```bash
chmod 600 ~/.pypirc
```

### Option 2: Environment Variables
```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-AgENdGVzdC5weXBpLm9yZw...YOUR_TOKEN
```

## Phase 10.3: Upload to TestPyPI (Testing)

### First, test on TestPyPI:
```bash
# Upload to TestPyPI
cd D:\Binwalk3
twine upload --repository testpypi dist/*

# Expected output:
# Uploading distributions to https://test.pypi.org/legacy/
# Uploading binwalk3-3.1.0-py3-none-any.whl
# Uploading binwalk3-3.1.0.tar.gz
# View at: https://test.pypi.org/project/binwalk3/3.1.0/
```

### Test Installation from TestPyPI:
```bash
# Create fresh environment
python -m venv test_pypi_install
source test_pypi_install/Scripts/activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ binwalk3

# Test it works
python -c "import binwalk; print(binwalk.__version__)"
python -c "import binwalk; print(f'Binary available: {binwalk.core.module.Modules().backend.available}')"

# Cleanup
deactivate
```

### Verify on TestPyPI Web:
1. Visit https://test.pypi.org/project/binwalk3/
2. Check that:
   - Version shows 3.1.0
   - README renders correctly
   - Metadata is accurate
   - Download files are present (wheel + source dist)

## Phase 10.4: Upload to Production PyPI

**⚠️ WARNING: This step is IRREVERSIBLE. You cannot delete or replace versions on PyPI.**

### Pre-flight checklist:
- [ ] Tested on TestPyPI successfully
- [ ] Version number is correct (3.1.0)
- [ ] README renders correctly on TestPyPI
- [ ] Binary is included in wheel (verified)
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Package installs and runs correctly
- [ ] No placeholder code or TODOs
- [ ] License is correct (MIT)
- [ ] Author information is accurate

### Upload to Production PyPI:
```bash
cd D:\Binwalk3

# Upload to production PyPI
twine upload dist/*

# Expected output:
# Uploading distributions to https://upload.pypi.org/legacy/
# Uploading binwalk3-3.1.0-py3-none-any.whl
# Uploading binwalk3-3.1.0.tar.gz
# View at: https://pypi.org/project/binwalk3/3.1.0/
```

## Phase 10.5: Verify Production Installation

### Test from PyPI:
```bash
# Create fresh environment
python -m venv test_production
source test_production/Scripts/activate

# Install from production PyPI
pip install binwalk3

# Comprehensive test
python -c "
import binwalk
print(f'✓ Package installed: binwalk3 {binwalk.__version__}')
print(f'✓ API version: {binwalk.__api_version__}')
backend = binwalk.core.module.Modules().backend
print(f'✓ Binary available: {backend.available}')
print(f'✓ Binary path: {backend.binary_path}')

# Test scan function exists
from binwalk import scan
print('✓ Scan function available')
"

# Cleanup
deactivate
```

### Verify on PyPI Web:
1. Visit https://pypi.org/project/binwalk3/
2. Check that:
   - Package appears in search results
   - README renders correctly
   - All metadata is correct
   - Download statistics start appearing
   - Wheels and source distribution are downloadable

## Post-Publication Tasks

### 1. Update Repository
Add GitHub repository link if not already done:
- Update `pyproject.toml` with correct GitHub URL
- Create GitHub repository at https://github.com/zacharyflint/binwalk3
- Push code to GitHub
- Add PyPI badge to README

### 2. Monitor Initial Usage
- Check download statistics (appears after ~24 hours)
- Watch for GitHub issues
- Monitor PyPI package page for any problems

### 3. Announce Release
Consider announcing on:
- GitHub Discussions
- Python packaging forums
- Security/firmware analysis communities
- Relevant subreddits (r/ReverseEngineering, r/netsec)

## Troubleshooting

### Common Issues:

**"File already exists"**
- Version already uploaded to PyPI
- Increment version in `pyproject.toml` and `binwalk/__version__.py`
- Rebuild with `python -m build`
- Upload new version

**"Invalid authentication credentials"**
- Check API token is correct
- Ensure using `__token__` as username
- Verify token hasn't expired
- Check `.pypirc` permissions (should be 600)

**"Distribution file is too large"**
- Binary makes package ~3.5 MB
- This is within PyPI limits (100 MB)
- Should not be an issue

**"Package metadata is invalid"**
- Run `twine check dist/*` to identify issues
- Fix in `pyproject.toml`
- Rebuild package

## Future Releases

### For version updates:
1. Update version in `binwalk/__version__.py`
2. Update version in `pyproject.toml`
3. Update `CHANGELOG.md` with changes
4. Run tests: `pytest tests/ -v`
5. Build: `python -m build`
6. Validate: `twine check dist/*`
7. Upload to TestPyPI for testing
8. Upload to production PyPI
9. Tag release in git: `git tag v3.1.1`
10. Push to GitHub: `git push && git push --tags`

### Version Numbering:
- Major (X.0.0): Breaking API changes
- Minor (3.X.0): New features, backward compatible
- Patch (3.1.X): Bug fixes only

## Security Considerations

1. **API Tokens**:
   - Never commit tokens to git
   - Use scoped tokens (project-specific when possible)
   - Rotate tokens periodically

2. **Binary Distribution**:
   - Binary is compiled from trusted binwalk v3 source
   - SHA256 hash documented in BUILD_NOTE.md
   - Users can verify binary integrity

3. **Two-Factor Authentication**:
   - Required for PyPI publishing
   - Strongly recommended for account security

## Resources

- PyPI Help: https://pypi.org/help/
- Packaging Guide: https://packaging.python.org/
- Twine Documentation: https://twine.readthedocs.io/
- TestPyPI: https://test.pypi.org/
- Python Packaging User Guide: https://packaging.python.org/guides/

## Status

- **Phase 10.1**: ⚠️ Pending - Create PyPI accounts
- **Phase 10.2**: ⚠️ Pending - Configure authentication
- **Phase 10.3**: ⚠️ Pending - Test on TestPyPI
- **Phase 10.4**: ⚠️ Pending - Upload to production PyPI
- **Phase 10.5**: ⚠️ Pending - Verify installation

**Ready to publish** - All prerequisites complete!
