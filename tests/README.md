# UmukoziHR Resume Tailor - Test Suite

This directory contains comprehensive tests for the UmukoziHR Resume Tailor v1.2 backend system.

## Test Files

### Core Test Suite
- **`test_components.py`** - Unit tests for individual components (models, auth, validation, etc.)
- **`test_system.py`** - Database and core system integration tests
- **`full_api_test.py`** - Comprehensive API endpoint testing with authentication flow

### Development Tests  
- **`test_api.py`** - Basic API endpoint tests
- **`simple_test.py`** - Simple health check test

### Utilities
- **`test_components.bat`** - Windows batch script for component testing

## Running Tests

### Prerequisites
Make sure the server environment is set up:
```bash
cd server
source venv/Scripts/activate  # or venv\Scripts\activate.bat on Windows
pip install -r requirements.txt
```

### Individual Test Execution

#### Component Tests (No server required)
```bash
python tests/test_components.py
```
Tests: Models, Authentication, Validation, LaTeX templates, Core logic

#### System Tests (No server required)  
```bash
python tests/test_system.py
```
Tests: Database connections, Models, Auth system, Basic API endpoints

#### Full API Tests (Server required)
```bash
# Terminal 1: Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Run tests
python tests/full_api_test.py
```
Tests: Complete authentication flow, Profile management, Document generation

### Using pytest (Future)
```bash
pip install pytest
python -m pytest tests/
```

## Test Coverage

| Component | Unit Tests | Integration Tests | API Tests |
|-----------|------------|-------------------|-----------|
| Models | ✅ | ✅ | ✅ |
| Authentication | ✅ | ✅ | ✅ |
| Database | ✅ | ✅ | ✅ |
| Core Logic | ✅ | ✅ | ✅ |
| LaTeX Templates | ✅ | ✅ | ✅ |
| API Endpoints | ✅ | ✅ | ✅ |
| Document Generation | ✅ | ✅ | ✅ |

## Test Results Interpretation

### ✅ Pass Indicators
- All components working correctly
- Server responding to requests
- Database connections successful
- Authentication flow complete
- Document generation working

### ❌ Fail Indicators  
- Component import errors
- Database connection issues
- Authentication failures
- API endpoint errors
- LaTeX compilation problems

## Troubleshooting

### Common Issues

#### bcrypt Installation (Windows)
```bash
pip install bcrypt
```
If bcrypt fails, the system will fallback to SHA256 hashing.

#### Server Not Starting
```bash
# Check database
python migrate.py

# Verify environment
source venv/Scripts/activate
python -c "from app.main import app; print('OK')"
```

#### LaTeX Compilation Errors
LaTeX compilation is optional. The system will generate .tex files even if PDF compilation fails.

#### API Connection Refused
Ensure the server is running on port 8000:
```bash
curl http://localhost:8000/health
```

## Adding New Tests

### Component Tests
Add new test functions to `test_components.py` following the pattern:
```python
def test_new_component():
    print("🔄 Testing New Component...")
    try:
        # Test logic here
        print("✅ New component working!")
        return True
    except Exception as e:
        print(f"❌ New component test failed: {e}")
        return False
```

### API Tests
Add new endpoints to `full_api_test.py` following the pattern:
```python
def test_new_endpoint():
    print_test("New Endpoint")
    try:
        response = requests.post(f"{BASE_URL}/api/v1/new", json=data)
        if response.status_code == 200:
            print("✅ New endpoint working!")
            return True
        else:
            print(f"❌ New endpoint failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ New endpoint error: {e}")
        return False
```

---

**Last Updated**: 2025-01-29  
**Test Suite Version**: v1.2  
**Maintainer**: CTO Team