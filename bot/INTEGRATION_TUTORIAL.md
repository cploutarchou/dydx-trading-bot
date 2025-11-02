# Step-by-Step Integration Tutorial - Credentials Management

> **Detailed walkthrough for integrating dYdX Credentials Management into your bot**

**Estimated Time:** 30 minutes  
**Difficulty:** Intermediate  
**Prerequisites:** Python 3.8+, FastAPI, SQLAlchemy

---

## Step 1: Verify Prerequisites

### Check Python Version

```bash
python --version
# Should be 3.8 or higher
```

### Check FastAPI Installation

```bash
python -c "import fastapi; print(f'FastAPI {fastapi.__version__}')"
```

### Check SQLAlchemy

```bash
python -c "import sqlalchemy; print(f'SQLAlchemy {sqlalchemy.__version__}')"
```

### Check Required Packages

```bash
# You need these packages
pip list | grep -E "fastapi|sqlalchemy|pydantic|cryptography"

# If missing, install:
pip install fastapi sqlalchemy pydantic cryptography
```

---

## Step 2: Copy Source Files

### Create Credentials Directory (Optional)

```bash
# You can organize in a subdirectory if preferred
mkdir -p ./credentials_system
cd ./credentials_system
```

### Copy the Three Files

```bash
# Copy from the provided files to your project
cp models_dydx_credentials.py ./
cp service_dydx_credentials.py ./
cp routes_dydx_credentials.py ./

# Or if in main directory
cp models_dydx_credentials.py ../
cp service_dydx_credentials.py ../
cp routes_dydx_credentials.py ../
```

### Verify Files Exist

```bash
ls -la *.py | grep "models_dydx\|service_dydx\|routes_dydx"
```

---

## Step 3: Generate Encryption Key

### Generate New Key

```bash
# This command generates a new Fernet encryption key
python -c "from cryptography.fernet import Fernet; key = Fernet.generate_key().decode(); print('Your encryption key:'); print(key)"

# Example output:
# Your encryption key:
# Ks3cwz8HcEPsqT5nJ7vK2mL9pQ4rX6sY8zB1cD4eF_g3hI6jK9lM2nO5pQ8rT1uV
```

### Save Key Securely

```bash
# DO NOT commit this to Git!
# Save only in .env and .env.local (add to .gitignore)

# Copy the key from the output above
GENERATED_KEY="Ks3cwz8HcEPsqT5nJ7vK2mL9pQ4rX6sY8zB1cD4eF_g3hI6jK9lM2nO5pQ8rT1uV"
```

---

## Step 4: Update Environment Configuration

### Check if .env Exists

```bash
ls -la .env
# If not found, create one
```

### Create or Update .env File

```bash
# Open .env in your editor or use:
cat >> .env << EOF

# dYdX Credentials Management
CREDENTIALS_ENCRYPTION_KEY=Ks3cwz8HcEPsqT5nJ7vK2mL9pQ4rX6sY8zB1cD4eF_g3hI6jK9lM2nO5pQ8rT1uV

# Network selection
IS_TESTNET=true

# Database URL
DATABASE_URL=sqlite:///./bot_credentials.db
EOF
```

### Verify .env

```bash
grep CREDENTIALS_ENCRYPTION_KEY .env
# Should output your key
```

### Add .env to .gitignore

```bash
# Ensure .env is in .gitignore
if ! grep -q "^\.env$" .gitignore; then
    echo ".env" >> .gitignore
fi

# Verify
cat .gitignore | grep ".env"
```

---

## Step 5: Create Database Tables

### Option A: Using Alembic (Recommended)

#### Initialize Alembic (if not already done)

```bash
# If you haven't set up Alembic yet
alembic init migrations
```

#### Create Migration

```bash
# Generate a migration file for the new models
alembic revision --autogenerate -m "Add dydx credentials models"

# This creates a file like: migrations/versions/001_add_dydx_credentials_models.py
```

#### Review Generated Migration

```bash
# Open the generated file to review
cat migrations/versions/001_add_dydx_credentials_models.py

# Should contain:
# - DydxCredential table
# - DydxCredentialAudit table
# - DydxTestResult table
```

#### Apply Migration

```bash
# Run the migration
alembic upgrade head

# Verify tables created
sqlite3 bot_credentials.db ".tables" | grep dydx
```

### Option B: Create Tables Directly (Development Only)

```bash
# Create a temporary Python script
cat > create_tables.py << 'EOF'
from sqlalchemy import create_engine
from models_dydx_credentials import Base

# Create engine
engine = create_engine("sqlite:///./bot_credentials.db")

# Create all tables
Base.metadata.create_all(bind=engine)

print("✓ Tables created successfully!")
EOF

# Run it
python create_tables.py

# Clean up
rm create_tables.py
```

### Verify Database

```bash
# List tables
sqlite3 bot_credentials.db ".tables"

# Should show:
# dydx_credential dydx_credential_audit dydx_test_result

# View table structure
sqlite3 bot_credentials.db ".schema dydx_credential"
```

---

## Step 6: Import Models in Your Application

### Update Your Main Application File

#### Find Your Main File

```bash
# Usually one of these
ls -la main.py app.py server.py
```

#### Add Import (main.py)

```python
# At the top of main.py, add:
from models_dydx_credentials import (
    DydxCredential,
    DydxCredentialAudit,
    DydxTestResult,
    NetworkType
)
```

#### Verify Import Works

```bash
# Test that imports work
python -c "from models_dydx_credentials import DydxCredential; print('✓ Models import OK')"
```

---

## Step 7: Create Service Instance

### Add Service to Your Application

#### Create a Service Module (optional but recommended)

```bash
cat > credential_service_instance.py << 'EOF'
"""
Global credential service instance
Import this module to get the service
"""
import os
from service_dydx_credentials import DydxCredentialsService, CredentialEncryption
from sqlalchemy.orm import Session

# Initialize encryption
encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))

async def get_credential_service(db: Session) -> DydxCredentialsService:
    """Factory function to create service instance"""
    return DydxCredentialsService(db, encryption)
EOF
```

#### Or Add Directly to main.py

```python
import os
from service_dydx_credentials import DydxCredentialsService, CredentialEncryption

# Initialize encryption at app startup
encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))

async def get_credential_service(db: Session):
    """Dependency for credential service"""
    return DydxCredentialsService(db, encryption)
```

---

## Step 8: Integrate API Routes

### Update main.py

#### Option A: Include Router

```python
# In your main.py, after app creation:
from fastapi import FastAPI
from routes_dydx_credentials import router as credentials_router

app = FastAPI()

# Include the credentials routes
app.include_router(
    credentials_router,
    prefix="/api/v1",
    tags=["dYdX Credentials"]
)

# Other routes...
```

#### Option B: With Prefix (if using API versioning)

```python
# If your API already has versioning:
app.include_router(
    credentials_router,
    prefix="/api/v1",
    tags=["Credentials"]
)
```

### Verify Routes Are Registered

```bash
# Start your server
python main.py

# In another terminal, list all routes
curl http://localhost:8889/openapi.json | grep -i credentials

# Or check docs
curl http://localhost:8889/docs | grep credentials
```

---

## Step 9: Start Your Server

### Run FastAPI Server

```bash
# Using uvicorn directly
uvicorn main:app --reload --port 8889

# Or if you have a startup script
python main.py

# Expected output:
# INFO:     Uvicorn running on http://127.0.0.1:8889
# INFO:     Application startup complete
```

### Keep Server Running

```bash
# Keep this terminal open or run in background:
nohup uvicorn main:app --port 8889 > app.log 2>&1 &
```

---

## Step 10: Get Authentication Token

### Generate JWT Token (if using authentication)

#### If Using FastAPI Security

```python
# Create a test user and get token
# In a Python shell:
import requests

# Assuming you have a /login endpoint
response = requests.post(
    "http://localhost:8889/auth/login",
    json={"username": "testuser", "password": "testpass"}
)

token = response.json()['data']['access_token']
print(f"Your token: {token}")
```

#### Or Generate Token Directly

```bash
# Using JWT CLI (if installed)
jwt encode '{"user_id": 1}' 'your-secret-key' --algorithm HS256

# Or in Python:
python << 'EOF'
import jwt
import json

token = jwt.encode(
    {"user_id": 1, "username": "testuser"},
    "your-secret-key",
    algorithm="HS256"
)
print(f"Token: {token}")
EOF
```

#### Store Token

```bash
# Save for testing
export TOKEN="<your-token-here>"
```

---

## Step 11: Test Create Credential Endpoint

### Create Test Credential

#### Using curl

```bash
curl -X POST http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "network_type": "testnet",
    "address": "dydx1xyz123abc456def789ghi012jkl345mno678pqr",
    "mnemonic": "abandon about above abuse access accident account accuse achieve acid acoustic acknowledge",
    "name": "Test Wallet",
    "test_before_save": true
  }'
```

#### Expected Success Response

```json
{
  "success": true,
  "message": "Credential created successfully",
  "data": {
    "id": 1,
    "user_id": 1,
    "network_type": "testnet",
    "address_preview": "dydx1xyz123abc456",
    "name": "Test Wallet",
    "is_active": true,
    "is_test_valid": true,
    "created_at": "2025-11-02T10:30:00Z"
  }
}
```

#### If Test Fails

```bash
# Check response for error details
# Common issues:
# - Invalid address format
# - Mnemonic too short
# - Network connection issue
# - Wrong test network

# Re-verify your wallet details match testnet
```

---

## Step 12: Test List Credentials

### List All Credentials

```bash
curl -X GET "http://localhost:8889/api/v1/dydx/credentials?network_type=testnet&active_only=true" \
  -H "Authorization: Bearer $TOKEN"
```

### Expected Response

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Test Wallet",
      "network_type": "testnet",
      "address_preview": "dydx1xyz123abc456",
      "is_active": true,
      "is_test_valid": true
    }
  ]
}
```

---

## Step 13: Test Other Endpoints

### Get Single Credential

```bash
curl -X GET "http://localhost:8889/api/v1/dydx/credentials/1?decrypt=false" \
  -H "Authorization: Bearer $TOKEN"
```

### Test Credential Validity

```bash
curl -X POST http://localhost:8889/api/v1/dydx/credentials/1/test \
  -H "Authorization: Bearer $TOKEN"

# Response shows test result
```

### Update Credential

```bash
curl -X PUT http://localhost:8889/api/v1/dydx/credentials/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name", "is_active": true}'
```

### Get Credential Status

```bash
curl -X GET http://localhost:8889/api/v1/dydx/credentials/1/status \
  -H "Authorization: Bearer $TOKEN"
```

---

## Step 14: Integrate Credential Retrieval in Trading Code

### Update Your Trading Module

#### Create Helper Function

```python
# In your trading module
import os
from sqlalchemy.orm import Session
from service_dydx_credentials import DydxCredentialsService, CredentialEncryption
from models_dydx_credentials import NetworkType

async def get_trading_credential(db: Session, user_id: int):
    """Get active credential for trading"""
    
    encryption = CredentialEncryption(
        os.getenv('CREDENTIALS_ENCRYPTION_KEY')
    )
    service = DydxCredentialsService(db, encryption)
    
    # Get active testnet credential
    credential = await service.get_active_credential(
        user_id=user_id,
        network_type=NetworkType.TESTNET
    )
    
    if not credential:
        raise Exception("No active credential configured!")
    
    return credential
```

#### Use in Trading Logic

```python
async def start_trading(db: Session, user_id: int):
    """Start trading with stored credential"""
    
    # Get credential
    credential = await get_trading_credential(db, user_id)
    
    # Extract details
    address = credential['address']
    mnemonic = credential['mnemonic']
    
    # Initialize dYdX client
    client = DydxClient(
        address=address,
        mnemonic=mnemonic,
        network_id="testnet"
    )
    
    # Start trading...
    await client.connect()
```

---

## Step 15: Test Full Integration

### Create Test Script

```bash
cat > test_integration.py << 'EOF'
import asyncio
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models_dydx_credentials import Base
from service_dydx_credentials import DydxCredentialsService, CredentialEncryption
from models_dydx_credentials import NetworkType

async def test_integration():
    # Setup
    engine = create_engine("sqlite:///./bot_credentials.db")
    Base.metadata.create_all(bind=engine)
    
    db = Session(engine)
    encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
    service = DydxCredentialsService(db, encryption)
    
    try:
        # Test create
        print("1. Creating credential...")
        result = await service.create_credential(
            user_id=1,
            network_type=NetworkType.TESTNET,
            address="dydx1test123...",
            mnemonic="word1 word2 ... word12",
            name="Integration Test",
            test_before_save=False
        )
        print(f"   ✓ Created: {result['id']}")
        
        # Test list
        print("2. Listing credentials...")
        creds = await service.list_credentials(user_id=1)
        print(f"   ✓ Found: {len(creds)} credentials")
        
        # Test get
        print("3. Getting credential...")
        cred = await service.get_credential(result['id'], user_id=1)
        print(f"   ✓ Got: {cred['name']}")
        
        # Test update
        print("4. Updating credential...")
        await service.update_credential(
            result['id'], user_id=1, name="Updated"
        )
        print("   ✓ Updated")
        
        print("\n✅ Integration test passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_integration())
EOF

# Run test
python test_integration.py
```

---

## Step 16: Add to Deployment Checklist

### Pre-Deployment Verification

- [ ] Encryption key generated and in .env
- [ ] .env added to .gitignore
- [ ] Database tables created
- [ ] API server starts without errors
- [ ] Routes appear in /docs
- [ ] Create credential test passes
- [ ] List credentials test passes
- [ ] Test credential validity works
- [ ] Audit logs are created
- [ ] No secrets in logs or errors
- [ ] Authentication required for all endpoints

### Production Checklist

- [ ] Use HTTPS only
- [ ] Strong JWT secret (32+ characters)
- [ ] Rotate encryption keys periodically
- [ ] Monitor audit logs
- [ ] Backup database regularly
- [ ] Test disaster recovery
- [ ] Document runbook
- [ ] Set up alerts

---

## Troubleshooting

### Issue: ImportError for models_dydx_credentials

```bash
# Solution: Verify files are in Python path
python -c "from models_dydx_credentials import DydxCredential"

# If fails, add to path:
export PYTHONPATH="${PYTHONPATH}:/path/to/credentials/files"
```

### Issue: "Encryption key not found"

```bash
# Solution: Check .env
echo $CREDENTIALS_ENCRYPTION_KEY
# If empty, load .env:
source .env
```

### Issue: "Table does not exist"

```bash
# Solution: Create tables
python create_tables.py
# Or run migration:
alembic upgrade head
```

### Issue: 401 Unauthorized

```bash
# Solution: Check JWT token
# Verify token is valid and not expired
# Check Authorization header format: "Bearer TOKEN"
```

---

## Next Steps

1. **Configure Multiple Users**: Update credential access control
2. **Add Web UI**: Create forms for credential management
3. **Set Up Monitoring**: Add dashboard for credential health
4. **Implement Rotation**: Automated key rotation system
5. **Add Backup/Restore**: Data recovery procedures

---

## Summary

You have successfully integrated the dYdX Credentials Management System!

**What You Now Have:**

- ✅ Secure encrypted credential storage
- ✅ REST API for credential management
- ✅ Complete audit trail
- ✅ Database-backed persistence
- ✅ Ready for multi-user trading

**Files Integrated:**

- models_dydx_credentials.py (database models)
- service_dydx_credentials.py (business logic)
- routes_dydx_credentials.py (API endpoints)

**Next:** Read `DYDX_CREDENTIALS_API.md` for complete API documentation or `CREDENTIALS_QUICKSTART.md` for quick reference.

---

**Last Updated:** November 2, 2025  
**Version:** 1.0  
**Status:** ✅ Complete
