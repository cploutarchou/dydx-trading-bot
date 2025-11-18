# dYdX Credentials Management - Developer Quick Reference

> **Fast lookup guide for developers integrating the credentials system**

## 🚀 Installation (5 minutes)

### 1. Copy Files

```bash
# Copy the three credential management files to your project
cp models_dydx_credentials.py service_dydx_credentials.py routes_dydx_credentials.py /your-bot-dir/
```

### 2. Generate Encryption Key

```bash
# Generate a new Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Output example:
# Ks3cwz8HcEPsqT5nJ7vK2mL9pQ4rX6sY8zB1cD4eF
```

### 3. Update .env

```env
# Add to your .env file
CREDENTIALS_ENCRYPTION_KEY=<your_generated_key_from_step_2>
IS_TESTNET=true
DATABASE_URL=sqlite:///./bot_credentials.db
```

### 4. Create Database Tables

```bash
# Use your existing migrations system
alembic revision --autogenerate -m "Add dydx credentials models"
alembic upgrade head
```

### 5. Integrate FastAPI Routes

```python
# In your main.py or app initialization
from routes.dydx_credentials import router as credentials_router

# Include the router
app.include_router(credentials_router)
# Endpoints will be available at /api/v1/dydx/credentials/*
```

---

## 🌐 API Endpoints - Quick Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/dydx/credentials` | Create new credential |
| `GET` | `/api/v1/dydx/credentials` | List all credentials |
| `GET` | `/api/v1/dydx/credentials/{id}` | Get specific credential |
| `PUT` | `/api/v1/dydx/credentials/{id}` | Update credential |
| `DELETE` | `/api/v1/dydx/credentials/{id}` | Delete credential |
| `POST` | `/api/v1/dydx/credentials/{id}/test` | Test credential validity |
| `GET` | `/api/v1/dydx/credentials/{id}/status` | Get credential status |

---

## 📋 API Examples

### Create Credential

```bash
curl -X POST http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "network_type": "testnet",
    "address": "dydx1abcdef123456...",
    "mnemonic": "word1 word2 word3 ... word12",
    "name": "Trading Wallet",
    "test_before_save": true
  }'
```

**Response:**

```json
{
  "success": true,
  "data": {
    "id": 1,
    "user_id": 123,
    "network_type": "testnet",
    "address_preview": "dydx1abcdef1234",
    "name": "Trading Wallet",
    "is_active": true,
    "is_test_valid": true,
    "created_at": "2025-11-02T10:30:00Z"
  }
}
```

### List Credentials

```bash
curl -X GET "http://localhost:8889/api/v1/dydx/credentials?network_type=testnet&active_only=true" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Get Credential (Encrypted)

```bash
curl -X GET http://localhost:8889/api/v1/dydx/credentials/1 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Get Credential (Decrypted Data)

```bash
curl -X GET "http://localhost:8889/api/v1/dydx/credentials/1?decrypt=true" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Test Credential

```bash
curl -X POST http://localhost:8889/api/v1/dydx/credentials/1/test \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response shows test result
{
  "success": true,
  "data": {
    "connection_valid": true,
    "response_time_ms": 145,
    "balance": 500.50,
    "test_timestamp": "2025-11-02T10:35:00Z"
  }
}
```

### Update Credential

```bash
curl -X PUT http://localhost:8889/api/v1/dydx/credentials/1 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Wallet Name",
    "is_active": true
  }'
```

### Delete Credential

```bash
curl -X DELETE http://localhost:8889/api/v1/dydx/credentials/1 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## 🐍 Python Code Examples

### Initialize Service

```python
import os
from sqlalchemy.orm import Session
from internal.service.service_dydx_credentials import DydxCredentialsService, CredentialEncryption
from internal.domain.models_dydx_credentials import NetworkType

# Initialize encryption
encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))

# Initialize service with DB session
service = DydxCredentialsService(db_session, encryption)
```

### Create Credential

```python
from internal.domain.models_dydx_credentials import NetworkType

result = await service.create_credential(
    user_id=1,
    network_type=NetworkType.TESTNET,
    address="dydx1abcdef123456...",
    mnemonic="word1 word2 word3 ... word12",
    name="My Trading Wallet",
    test_before_save=True
)

print(f"Created credential ID: {result['id']}")
print(f"Test result: {result['is_test_valid']}")
```

### Get Active Credential for Trading

```python
from internal.domain.models_dydx_credentials import NetworkType

# Get the active credential for testnet
cred = await service.get_active_credential(
    user_id=1,
    network_type=NetworkType.TESTNET
)

if cred:
    address = cred['address']
    mnemonic = cred['mnemonic']
    print(f"Using wallet: {address}")
    # Use these for trading...
else:
    print("No active credential configured!")
```

### List All Credentials

```python
from internal.domain.models_dydx_credentials import NetworkType

credentials = await service.list_credentials(
    user_id=1,
    network_type=NetworkType.TESTNET,
    active_only=True
)

for cred in credentials:
    status = "✅" if cred['is_test_valid'] else "❌"
    print(f"{status} {cred['name']}: {cred['address_preview']}")
```

### Test Credential Validity

```python
result = await service.test_credential(credential_id=1)

if result['success']:
    print(f"✅ Connection OK ({result['response_time_ms']}ms)")
    print(f"   Balance: ${result['balance']:.2f}")
else:
    print(f"❌ Test failed: {result['error_message']}")
```

### Update Credential

```python
await service.update_credential(
    credential_id=1,
    user_id=1,
    name="New Wallet Name",
    is_active=True
)
```

### Delete Credential

```python
# Soft delete (marks as inactive, doesn't remove data)
await service.delete_credential(
    credential_id=1,
    user_id=1
)
```

---

## 🔑 Core Classes Reference

### CredentialEncryption

```python
from internal.service.service_dydx_credentials import CredentialEncryption

# Initialize with key from environment
encryption = CredentialEncryption(
    key=os.getenv('CREDENTIALS_ENCRYPTION_KEY')
)

# Encrypt data
encrypted_text = encryption.encrypt("secret_data")

# Decrypt data
decrypted_text = encryption.decrypt(encrypted_text)
```

### DydxCredentialsService

```python
service = DydxCredentialsService(db_session, encryption)

# Available methods:
await service.create_credential(...)         # Create
await service.get_credential(...)            # Read single
await service.list_credentials(...)          # Read multiple
await service.update_credential(...)         # Update
await service.delete_credential(...)         # Delete
await service.test_credential(...)           # Test connection
await service.get_active_credential(...)     # Get active for trading
```

---

## 📊 Database Schema

### DydxCredential Table

```
id                    INTEGER PRIMARY KEY
user_id              INTEGER (Foreign Key)
network_type         ENUM (testnet, mainnet)
address              TEXT (encrypted)
mnemonic             TEXT (encrypted)
is_active            BOOLEAN
is_test_valid        BOOLEAN
last_tested          DATETIME
created_at           DATETIME
updated_at           DATETIME
created_by           INTEGER
updated_by           INTEGER
name                 TEXT
description          TEXT
error_message        TEXT
```

### DydxCredentialAudit Table

```
id                   INTEGER PRIMARY KEY
credential_id        INTEGER (Foreign Key)
user_id              INTEGER
operation            TEXT (create/read/update/delete/test)
network_type         ENUM (testnet, mainnet)
address_preview      TEXT (first 20 chars)
success              BOOLEAN
details              TEXT
created_at           DATETIME
```

### DydxTestResult Table

```
id                   INTEGER PRIMARY KEY
credential_id        INTEGER (Foreign Key)
tested_at            DATETIME
network_type         ENUM
success              BOOLEAN
response_time_ms     INTEGER
balance              DECIMAL
error_message        TEXT
endpoint_used        TEXT
test_type            TEXT
```

---

## 🧪 Testing Checklist

Use this checklist to verify integration:

- [ ] Encryption key generated and added to .env
- [ ] Database tables created with migrations
- [ ] API server started
- [ ] JWT token obtained
- [ ] Create credential via POST endpoint
- [ ] List credentials via GET endpoint
- [ ] Get single credential details
- [ ] Decrypt credential data
- [ ] Test credential validity
- [ ] Update credential name/status
- [ ] Delete credential
- [ ] Verify audit logs recorded

---

## ❌ Common Issues & Solutions

### Issue: "Encryption key not found"

```python
# Error: cryptography.fernet.InvalidToken or KeyError

# Solution: Verify CREDENTIALS_ENCRYPTION_KEY in .env
# In .env file:
CREDENTIALS_ENCRYPTION_KEY=your_key_here

# Verify in Python:
import os
key = os.getenv('CREDENTIALS_ENCRYPTION_KEY')
print(f"Key exists: {key is not None}")
```

### Issue: "Table does not exist"

```bash
# Error: OperationalError (no such table: dydx_credential)

# Solution: Run migrations
alembic upgrade head

# Or create manually:
# from models_dydx_credentials import Base
# Base.metadata.create_all(bind=engine)
```

### Issue: "Permission denied - cannot access credential"

```python
# Error: User tries to access credential belonging to another user

# Solution: Verify user_id matches
# The service validates:
# - Only owner can view decrypted data
# - Only owner can modify or delete
# - Use correct user_id when calling service methods

await service.get_credential(
    credential_id=1,
    user_id=current_user.id  # Must match credential owner
)
```

### Issue: "Credential test failed"

```
Error: Connection test returned False

Verify:
- Wallet address format is correct (starts with "dydx1")
- Mnemonic has correct 12+ words
- Network type (testnet/mainnet) matches
- Internet connection to dYdX API
- No typos in address/mnemonic
```

### Issue: "InvalidToken when decrypting"

```python
# Error: Decryption returns corrupted data

# Likely cause: Wrong encryption key used
# Solution: Verify key matches one used for encryption
# Check if key was rotated without migrating data
# Use audit logs to identify when data was encrypted
```

---

## 🔒 Security Best Practices

✅ **DO:**

- Store `CREDENTIALS_ENCRYPTION_KEY` in `.env` only (never in code)
- Use HTTPS in production
- Restrict API with authentication (JWT tokens)
- Rotate encryption keys periodically
- Monitor audit logs for suspicious activity
- Use strong JWT secrets (32+ chars)
- Log all credential access
- Use TESTNET for development

❌ **DON'T:**

- Commit encryption key to Git
- Store keys in code or config files
- Print decrypted credentials to logs
- Share encryption keys with developers
- Use same key across environments
- Store plaintext mnemonics
- Expose credentials in error messages
- Log decrypted sensitive data

---

## 🔄 Workflow Examples

### Workflow 1: Add a New Wallet

```bash
# 1. Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Add to .env
echo "CREDENTIALS_ENCRYPTION_KEY=<key>" >> .env

# 3. Create credential via API
curl -X POST http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"network_type":"testnet","address":"dydx1...","mnemonic":"word1 word2...","name":"New Wallet"}'

# 4. Verify it works
curl -X POST http://localhost:8889/api/v1/dydx/credentials/1/test \
  -H "Authorization: Bearer $TOKEN"
```

### Workflow 2: Switch Between Multiple Wallets

```python
# Disable old wallet
await service.update_credential(old_id, user_id, is_active=False)

# Enable new wallet
await service.update_credential(new_id, user_id, is_active=True)

# Get active credential for trading
active = await service.get_active_credential(user_id, NetworkType.TESTNET)
```

### Workflow 3: Monitor Wallet Health

```python
# Get all wallets
wallets = await service.list_credentials(user_id, NetworkType.TESTNET)

# Test each
for wallet in wallets:
    result = await service.test_credential(wallet['id'])
    status = "✅" if result['success'] else "❌"
    print(f"{status} {wallet['name']}")
```

### Workflow 4: Emergency Disable Wallet

```python
# Quick disable without full delete
await service.update_credential(
    credential_id=compromised_id,
    user_id=current_user_id,
    is_active=False
)

# Audit trail preserves history
```

---

## 📚 File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `models_dydx_credentials.py` | ~160 | 3 SQLAlchemy database models |
| `service_dydx_credentials.py` | ~500 | Encryption + CRUD service layer |
| `routes_dydx_credentials.py` | ~350 | 7 FastAPI endpoints |
| `DYDX_CREDENTIALS_API.md` | ~400 | Complete API documentation |
| `DYDX_CREDENTIALS_IMPLEMENTATION.md` | ~600 | Implementation guide |
| `CREDENTIALS_QUICKSTART.md` | ~400 | 10-step integration guide |

---

## 🚀 One-Liner Commands

```bash
# Generate key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Copy files
cp models_dydx_credentials.py service_dydx_credentials.py routes_dydx_credentials.py .

# Create tables
alembic upgrade head

# Start API (if not already running)
uvicorn main:app --reload --port 8889
```

---

## 💡 Quick Integration Template

```python
# your_trading_bot.py
import os
from sqlalchemy.orm import Session
from internal.domain.models_dydx_credentials import NetworkType
from internal.service.service_dydx_credentials import DydxCredentialsService, CredentialEncryption


async def get_trading_credential(db: Session, user_id: int):
    """Get credential for trading"""
    encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
    service = DydxCredentialsService(db, encryption)

    # Get active testnet credential
    credential = await service.get_active_credential(
        user_id=user_id,
        network_type=NetworkType.TESTNET
    )

    return credential


# In your trading logic
credential = await get_trading_credential(db, user_id=1)
if credential:
    address = credential['address']
    mnemonic = credential['mnemonic']
    # Use for trading...
else:
    raise Exception("No credential configured!")
```

---

## 📞 Need Help?

- **Full API Docs**: See `DYDX_CREDENTIALS_API.md`
- **Implementation Details**: See `DYDX_CREDENTIALS_IMPLEMENTATION.md`
- **Step-by-Step Guide**: See `CREDENTIALS_QUICKSTART.md`
- **System Overview**: See `CREDENTIALS_SYSTEM_SUMMARY.txt`

---

**Last Updated:** November 2, 2025  
**Version:** 1.0  
**Status:** ✅ Production Ready
