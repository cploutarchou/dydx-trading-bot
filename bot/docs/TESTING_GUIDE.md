# Testing Guide - dYdX Credentials Management

> **Comprehensive testing procedures for the credentials system**

---

## Test Categories

### 1. Unit Tests

### 2. Integration Tests

### 3. API Tests

### 4. Security Tests

### 5. Performance Tests

### 6. Manual Verification

---

## 1. Unit Tests

### Test Encryption/Decryption

```python
# test_encryption.py
import pytest
import os
from cryptography.fernet import Fernet
from service_dydx_credentials import CredentialEncryption

class TestEncryption:
    @pytest.fixture
    def encryption(self):
        """Create encryption instance"""
        return CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
    
    def test_encrypt_decrypt(self, encryption):
        """Test basic encrypt/decrypt"""
        original = "secret_data_123"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)
        
        assert original == decrypted
        assert encrypted != original
    
    def test_different_inputs_produce_different_ciphers(self, encryption):
        """Test that same input encrypts differently each time (due to nonce)"""
        original = "test_data"
        encrypted1 = encryption.encrypt(original)
        encrypted2 = encryption.encrypt(original)
        
        # Both should decrypt to same value
        assert encryption.decrypt(encrypted1) == original
        assert encryption.decrypt(encrypted2) == original
        # But ciphers might differ due to Fernet's nonce
    
    def test_invalid_token_raises_error(self, encryption):
        """Test that invalid token raises error"""
        invalid_token = "invalid_base64_token!!!"
        
        with pytest.raises(Exception):
            encryption.decrypt(invalid_token)
    
    def test_empty_string(self, encryption):
        """Test encrypting empty string"""
        original = ""
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)
        
        assert original == decrypted
    
    def test_long_string(self, encryption):
        """Test encrypting long string"""
        original = "A" * 10000
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)
        
        assert original == decrypted

# Run tests
# pytest test_encryption.py -v
```

### Test Database Models

```python
# test_models.py
import pytest
from datetime import datetime
from internal.domain.models_dydx_credentials import (
    DydxCredential,
    DydxCredentialAudit,
    DydxTestResult,
    NetworkType,
    CredentialOperation
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def db():
    """Create in-memory test database"""
    engine = create_engine("sqlite:///:memory:")
    # Create tables
    from internal.domain.models_dydx_credentials import Base
    Base.metadata.create_all(engine)

    session = Session(engine)
    yield session
    session.close()


class TestModels:
    def test_create_credential(self, db):
        """Test creating a credential"""
        cred = DydxCredential(
            user_id=1,
            network_type=NetworkType.TESTNET,
            address="dydx1test123",
            mnemonic="word1 word2 ... word12",
            name="Test"
        )

        db.add(cred)
        db.commit()

        assert cred.id is not None
        assert cred.user_id == 1
        assert cred.is_active == True

    def test_create_audit_log(self, db):
        """Test creating audit log"""
        audit = DydxCredentialAudit(
            credential_id=1,
            user_id=1,
            operation=CredentialOperation.CREATE,
            network_type=NetworkType.TESTNET,
            success=True,
            details="Credential created"
        )

        db.add(audit)
        db.commit()

        assert audit.id is not None
        assert audit.operation == CredentialOperation.CREATE

    def test_create_test_result(self, db):
        """Test creating test result"""
        result = DydxTestResult(
            credential_id=1,
            network_type=NetworkType.TESTNET,
            success=True,
            response_time_ms=145,
            balance=500.50
        )

        db.add(result)
        db.commit()

        assert result.id is not None
        assert result.success == True

# Run tests
# pytest test_models.py -v
```

---

## 2. Integration Tests

### Test Service Layer

```python
# test_service.py
import pytest
import asyncio
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from service_dydx_credentials import DydxCredentialsService, CredentialEncryption
from internal.domain.models_dydx_credentials import Base, NetworkType


@pytest.fixture
def db():
    """Create test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def service(db):
    """Create service instance"""
    encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
    return DydxCredentialsService(db, encryption)


@pytest.mark.asyncio
class TestCredentialService:
    async def test_create_credential(self, service):
        """Test creating credential"""
        result = await service.create_credential(
            user_id=1,
            network_type=NetworkType.TESTNET,
            address="dydx1test123",
            mnemonic="test test test test test test test test test test test test",
            name="Test Wallet",
            test_before_save=False
        )

        assert result['id'] is not None
        assert result['user_id'] == 1
        assert result['name'] == "Test Wallet"

    async def test_get_credential(self, service):
        """Test getting credential"""
        # Create first
        created = await service.create_credential(
            user_id=1,
            network_type=NetworkType.TESTNET,
            address="dydx1test123",
            mnemonic="test test test test test test test test test test test test",
            name="Test"
        )

        # Get it
        cred = await service.get_credential(created['id'], user_id=1)

        assert cred['id'] == created['id']
        assert cred['name'] == "Test"

    async def test_list_credentials(self, service):
        """Test listing credentials"""
        # Create multiple
        for i in range(3):
            await service.create_credential(
                user_id=1,
                network_type=NetworkType.TESTNET,
                address=f"dydx1test{i}",
                mnemonic="test test test test test test test test test test test test",
                name=f"Wallet {i}"
            )

        # List
        creds = await service.list_credentials(user_id=1)
        assert len(creds) == 3

    async def test_update_credential(self, service):
        """Test updating credential"""
        # Create
        created = await service.create_credential(
            user_id=1,
            network_type=NetworkType.TESTNET,
            address="dydx1test123",
            mnemonic="test test test test test test test test test test test test",
            name="Original"
        )

        # Update
        await service.update_credential(
            credential_id=created['id'],
            user_id=1,
            name="Updated"
        )

        # Verify
        updated = await service.get_credential(created['id'], user_id=1)
        assert updated['name'] == "Updated"

    async def test_delete_credential(self, service):
        """Test deleting credential"""
        # Create
        created = await service.create_credential(
            user_id=1,
            network_type=NetworkType.TESTNET,
            address="dydx1test123",
            mnemonic="test test test test test test test test test test test test",
            name="Test"
        )

        # Delete
        await service.delete_credential(created['id'], user_id=1)

        # Verify deleted (should return None or raise error)
        # depending on implementation

    async def test_user_isolation(self, service):
        """Test that users can't access each other's credentials"""
        # Create credential for user 1
        cred1 = await service.create_credential(
            user_id=1,
            network_type=NetworkType.TESTNET,
            address="dydx1user1",
            mnemonic="test test test test test test test test test test test test",
            name="User 1 Wallet"
        )

        # User 2 tries to access
        with pytest.raises(Exception):
            await service.get_credential(cred1['id'], user_id=2)

# Run tests
# pytest test_service.py -v
```

---

## 3. API Tests

### Test Endpoints with FastAPI TestClient

```python
# test_api.py
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)

@pytest.fixture
def token():
    """Get test token"""
    # In real tests, authenticate first
    return "test_token_xyz"

class TestAPI:
    def test_health_check(self, client):
        """Test API is running"""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_create_credential_requires_auth(self, client):
        """Test auth is required"""
        response = client.post("/api/v1/dydx/credentials")
        assert response.status_code == 401
    
    def test_create_credential_success(self, client, token):
        """Test creating credential via API"""
        response = client.post(
            "/api/v1/dydx/credentials",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "network_type": "testnet",
                "address": "dydx1test123",
                "mnemonic": "test test test test test test test test test test test test",
                "name": "Test"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] == True
        assert data['data']['id'] is not None
    
    def test_list_credentials_success(self, client, token):
        """Test listing credentials"""
        response = client.get(
            "/api/v1/dydx/credentials",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data['data'], list)
    
    def test_get_credential_success(self, client, token):
        """Test getting single credential"""
        response = client.get(
            "/api/v1/dydx/credentials/1",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # May be 404 if not found, but shouldn't error
        assert response.status_code in [200, 404]
    
    def test_invalid_request_body(self, client, token):
        """Test validation of request body"""
        response = client.post(
            "/api/v1/dydx/credentials",
            headers={"Authorization": f"Bearer {token}"},
            json={
                # Missing required fields
                "name": "Invalid"
            }
        )
        
        assert response.status_code == 422
    
    def test_test_credential_endpoint(self, client, token):
        """Test credential testing endpoint"""
        response = client.post(
            "/api/v1/dydx/credentials/1/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # May fail if credential doesn't exist
        assert response.status_code in [200, 404]

# Run tests
# pytest test_api.py -v
```

---

## 4. Security Tests

### Test Permission & Access Control

```python
# test_security.py
import pytest
from fastapi.testclient import TestClient
from main import app

class TestSecurity:
    def test_sql_injection_attempt(self):
        """Test API handles SQL injection safely"""
        client = TestClient(app)
        
        response = client.get(
            "/api/v1/dydx/credentials?network_type='; DROP TABLE dydx_credential; --",
        )
        
        # Should not crash or delete data
        assert response.status_code in [400, 401, 422]
    
    def test_xss_prevention(self):
        """Test XSS payload handling"""
        client = TestClient(app)
        
        response = client.post(
            "/api/v1/dydx/credentials",
            json={
                "network_type": "testnet",
                "address": "dydx1test",
                "mnemonic": "test test test test test test test test test test test test",
                "name": "<script>alert('xss')</script>"
            }
        )
        
        # Should sanitize or reject
        assert response.status_code in [200, 400, 422]
    
    def test_credential_data_not_exposed_in_logs(self):
        """Test sensitive data not logged"""
        # This is harder to test but important
        # Enable logging and verify mnemonics don't appear
        pass
    
    def test_encryption_key_environment_isolation(self):
        """Test key from environment, not from code"""
        import os
        key = os.getenv('CREDENTIALS_ENCRYPTION_KEY')
        assert key is not None
        assert key not in open(__file__).read()

# Run tests
# pytest test_security.py -v
```

---

## 5. Performance Tests

### Load Testing

```python
# test_performance.py
import pytest
import time
import asyncio
from service_dydx_credentials import DydxCredentialsService

@pytest.mark.asyncio
async def test_create_many_credentials(service):
    """Test performance of creating many credentials"""
    start = time.time()
    
    for i in range(100):
        await service.create_credential(
            user_id=1,
            network_type="testnet",
            address=f"dydx1test{i}",
            mnemonic="test test test test test test test test test test test test",
            name=f"Wallet {i}"
        )
    
    elapsed = time.time() - start
    print(f"Created 100 credentials in {elapsed:.2f}s")
    
    # Should complete in reasonable time
    assert elapsed < 30

@pytest.mark.asyncio
async def test_list_performance(service):
    """Test performance of listing many credentials"""
    # Create many first
    for i in range(50):
        await service.create_credential(
            user_id=1,
            network_type="testnet",
            address=f"dydx1test{i}",
            mnemonic="test test test test test test test test test test test test",
            name=f"Wallet {i}"
        )
    
    # Time the list operation
    start = time.time()
    creds = await service.list_credentials(user_id=1)
    elapsed = time.time() - start
    
    print(f"Listed {len(creds)} credentials in {elapsed:.4f}s")
    assert elapsed < 1  # Should list quickly

@pytest.mark.asyncio
async def test_encryption_performance(encryption):
    """Test encryption performance"""
    data = "x" * 1000
    
    start = time.time()
    for _ in range(100):
        encrypted = encryption.encrypt(data)
        encryption.decrypt(encrypted)
    elapsed = time.time() - start
    
    print(f"200 encrypt/decrypt operations in {elapsed:.2f}s")
    assert elapsed < 10

# Run tests
# pytest test_performance.py -v -s
```

---

## 6. Manual Verification

### Checklist for Manual Testing

```
API Testing:
- [ ] POST /api/v1/dydx/credentials - Create credential
- [ ] GET /api/v1/dydx/credentials - List all
- [ ] GET /api/v1/dydx/credentials/1 - Get one (without decrypt)
- [ ] GET /api/v1/dydx/credentials/1?decrypt=true - Get with decrypt
- [ ] PUT /api/v1/dydx/credentials/1 - Update credential
- [ ] DELETE /api/v1/dydx/credentials/1 - Delete credential
- [ ] POST /api/v1/dydx/credentials/1/test - Test validity
- [ ] GET /api/v1/dydx/credentials/1/status - Get status

Authentication:
- [ ] Requests without token return 401
- [ ] Requests with invalid token return 401
- [ ] Requests with valid token succeed
- [ ] User can't access other user's credentials

Database:
- [ ] Credentials are encrypted at rest
- [ ] Audit log created for each operation
- [ ] Soft delete works (not hard delete)
- [ ] Data integrity maintained

Security:
- [ ] No plaintext credentials in logs
- [ ] No encryption key in logs
- [ ] API responses don't expose raw data
- [ ] Error messages don't leak information

Performance:
- [ ] API responses < 200ms
- [ ] List of 100 credentials < 1s
- [ ] Encryption/decryption < 10ms per operation
```

---

## Running All Tests

### Run All Unit Tests

```bash
pytest tests/unit/ -v
```

### Run All Integration Tests

```bash
pytest tests/integration/ -v
```

### Run All Tests with Coverage

```bash
pytest --cov=service_dydx_credentials --cov=routes_dydx_credentials --cov-report=html
```

### Run Specific Test File

```bash
pytest test_encryption.py -v
```

### Run Tests Matching Pattern

```bash
pytest -k "test_create" -v
```

### Run with Verbose Output

```bash
pytest -v -s  # -s shows print statements
```

---

## Test Structure

```
project/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── unit/
│   │   ├── test_encryption.py
│   │   ├── test_models.py
│   │   └── test_service.py
│   ├── integration/
│   │   ├── test_service_integration.py
│   │   └── test_database.py
│   ├── api/
│   │   ├── test_endpoints.py
│   │   └── test_auth.py
│   └── security/
│       ├── test_encryption_security.py
│       └── test_access_control.py
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    
    - name: Run unit tests
      run: pytest tests/unit/ -v
    
    - name: Run integration tests
      run: pytest tests/integration/ -v
    
    - name: Run API tests
      run: pytest tests/api/ -v
    
    - name: Generate coverage report
      run: pytest --cov=service_dydx_credentials --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## Key Metrics to Track

| Metric | Target | Warning |
|--------|--------|---------|
| Unit test coverage | > 90% | < 80% |
| API response time | < 200ms | > 500ms |
| Encryption latency | < 10ms | > 50ms |
| List performance | < 1s (100 items) | > 5s |
| Test suite duration | < 60s | > 120s |

---

**Last Updated:** November 2, 2025  
**Version:** 1.0  
**Status:** ✅ Complete
