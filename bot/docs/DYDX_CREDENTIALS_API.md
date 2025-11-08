# dYdX Credentials Management API

## Overview

The dYdX Credentials Management System moves wallet credentials from static `.env` files to a secure, encrypted database with comprehensive API endpoints. This enables:

- 🔐 **Encrypted Storage** - Credentials stored with Fernet encryption
- 🔄 **Dynamic Management** - Add, update, delete credentials without restarting
- ✅ **Validation** - Automatic and manual credential testing against dYdX network
- 📊 **Audit Trail** - Complete logging of all credential operations
- 👤 **Multi-User Support** - Each user can manage their own credentials
- 🌍 **Network Switching** - Support for both testnet and mainnet credentials

## Architecture

### Database Models

#### DydxCredential

Stores encrypted wallet credentials with metadata:

```python
- id: int (Primary Key)
- user_id: int (Foreign Key)
- network_type: enum (testnet/mainnet)
- address: str (Encrypted)
- mnemonic: str (Encrypted)
- is_active: bool
- is_test_valid: bool (Last validation result)
- last_tested: datetime
- created_at: datetime
- updated_at: datetime
- created_by: int
- updated_by: int
- name: str (Friendly name)
- description: str (Optional notes)
- error_message: str (Last error if failed)
```

#### DydxCredentialAudit

Audit log for all operations:

```python
- id: int
- credential_id: int
- user_id: int
- operation: str (create, read, update, delete, test)
- network_type: enum
- address_preview: str (First 20 chars)
- success: bool
- details: str (Error or info)
- created_at: datetime
```

#### DydxTestResult

Detailed test result history:

```python
- id: int
- credential_id: int
- tested_at: datetime
- network_type: enum
- success: bool
- response_time_ms: int
- balance: str (Account balance if successful)
- error_message: str
- endpoint_used: str
- test_type: str (Type of test performed)
```

### Service Layer (DydxCredentialsService)

#### CredentialEncryption

```python
class CredentialEncryption:
    def __init__(encryption_key: Optional[str] = None)
    def encrypt(data: str) -> str
    def decrypt(encrypted_data: str) -> str
    def get_key() -> str
```

#### DydxCredentialsService

Main service class with methods:

```python
async def create_credential(
    user_id, network_type, address, mnemonic, 
    name=None, description=None, test_before_save=True
) -> Dict

async def update_credential(
    credential_id, user_id, address=None, mnemonic=None,
    name=None, description=None, is_active=None
) -> Dict

async def delete_credential(credential_id, user_id) -> Dict

async def get_credential(
    credential_id, user_id, decrypt=False
) -> Optional[Dict]

async def list_credentials(
    user_id, network_type=None, active_only=True
) -> List[Dict]

async def test_credential(credential_id) -> Dict

async def get_active_credential(
    user_id, network_type
) -> Optional[Dict]
```

## API Endpoints

### Authentication

All endpoints require JWT authentication in the `Authorization: Bearer <token>` header.

### Endpoints

#### 1. Create Credential

```http
POST /api/v1/dydx/credentials
Authorization: Bearer <token>
Content-Type: application/json

{
  "network_type": "testnet",
  "address": "dydx1abc123def456...",
  "mnemonic": "word1 word2 word3 ... word12",
  "name": "My Trading Wallet",
  "description": "Primary testnet wallet",
  "test_before_save": true
}
```

**Response (201 Created):**

```json
{
  "id": 1,
  "network_type": "testnet",
  "address_preview": "dydx1abc...",
  "is_active": true,
  "test_result": {
    "success": true,
    "response_time_ms": 145,
    "balance": "[...]"
  },
  "created_at": "2025-11-02T10:00:00Z"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid address or mnemonic format
- `503 Service Unavailable` - Connection test failed (if test_before_save=true)

#### 2. List Credentials

```http
GET /api/v1/dydx/credentials?network_type=testnet&active_only=true
Authorization: Bearer <token>
```

**Response (200 OK):**

```json
[
  {
    "id": 1,
    "network_type": "testnet",
    "name": "My Trading Wallet",
    "address_preview": "dydx1abc...",
    "is_active": true,
    "is_test_valid": true,
    "last_tested": "2025-11-02T10:30:00Z",
    "created_at": "2025-11-02T10:00:00Z",
    "updated_at": "2025-11-02T10:30:00Z"
  }
]
```

**Query Parameters:**

- `network_type` (optional) - Filter by testnet or mainnet
- `active_only` (optional, default=true) - Only show active credentials

#### 3. Get Credential Details

```http
GET /api/v1/dydx/credentials/{id}?decrypt=false
Authorization: Bearer <token>
```

**Response (200 OK):**

```json
{
  "id": 1,
  "network_type": "testnet",
  "name": "My Trading Wallet",
  "address_preview": "dydx1abc...",
  "is_active": true,
  "is_test_valid": true,
  "last_tested": "2025-11-02T10:30:00Z",
  "created_at": "2025-11-02T10:00:00Z",
  "updated_at": "2025-11-02T10:30:00Z"
}
```

**With `decrypt=true` (returns full address and mnemonic):**

```json
{
  "id": 1,
  "network_type": "testnet",
  "name": "My Trading Wallet",
  "address": "dydx1abc123def456...",
  "mnemonic": "word1 word2 word3 ... word12",
  "is_active": true,
  "is_test_valid": true,
  "last_tested": "2025-11-02T10:30:00Z",
  "created_at": "2025-11-02T10:00:00Z",
  "updated_at": "2025-11-02T10:30:00Z"
}
```

**Query Parameters:**

- `decrypt` (optional, default=false) - Return encrypted data

#### 4. Update Credential

```http
PUT /api/v1/dydx/credentials/{id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Updated Wallet Name",
  "description": "Updated description",
  "is_active": true
}
```

**Response (200 OK):**

```json
{
  "id": 1,
  "updated_at": "2025-11-02T11:00:00Z",
  "message": "Credential updated successfully"
}
```

#### 5. Delete Credential

```http
DELETE /api/v1/dydx/credentials/{id}
Authorization: Bearer <token>
```

**Response (204 No Content)** - Empty body

#### 6. Test Credential

```http
POST /api/v1/dydx/credentials/{id}/test
Authorization: Bearer <token>
```

**Response (200 OK):**

```json
{
  "success": true,
  "response_time_ms": 145,
  "balance": "[{'denom': 'uusdc', 'amount': '1000000'}]",
  "endpoint_used": "https://indexer.v4testnet.dydx.exchange",
  "tested_at": "2025-11-02T11:00:00Z"
}
```

**Error Response (503):**

```json
{
  "detail": "Credential test failed: Invalid address or network error"
}
```

#### 7. Get Credential Status

```http
GET /api/v1/dydx/credentials/{id}/status
Authorization: Bearer <token>
```

**Response (200 OK):**

```json
{
  "id": 1,
  "is_active": true,
  "is_test_valid": true,
  "last_tested": "2025-11-02T10:30:00Z",
  "error_message": null,
  "can_be_used": true
}
```

## Security Features

### 1. Encryption

- **Algorithm**: Fernet (AES-128 in CBC mode)
- **Key Management**: Stored securely in environment
- **Data**: Address and mnemonic always encrypted at rest

### 2. Access Control

- **Authentication**: JWT required for all endpoints
- **Authorization**: Users can only access their own credentials
- **Audit Trail**: Every operation is logged with user ID and timestamp

### 3. Sensitive Data Handling

- **Address Preview**: Only first 10 + last 4 characters shown by default
- **Mnemonic**: Never returned unless explicitly decrypted
- **Audit Logs**: Store address preview, never full address

### 4. Testing

- Credentials tested with dYdX before being marked valid
- Test results stored with response time and error details
- Failed tests logged with specific error messages

## Integration with Bot

### Replacing .env Configuration

**Before:**

```env
IS_TESTNET=true
DYDX_TESTNET_ADDRESS=dydx1...
DYDX_TESTNET_MNEMONIC=word1 word2 ...
```

**After:**
Create credentials via API:

```bash
curl -X POST http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "network_type": "testnet",
    "address": "dydx1...",
    "mnemonic": "word1 word2 ...",
    "name": "Testnet Wallet"
  }'
```

### Fetching Credentials in Bot Code

```python
from service_dydx_credentials import DydxCredentialsService, CredentialEncryption
from models_dydx_credentials import NetworkType
from sqlalchemy.orm import Session

async def get_trading_credentials(
    user_id: int, 
    network_type: NetworkType,
    db: Session
):
    encryption = CredentialEncryption()
    service = DydxCredentialsService(db, encryption)
    
    # Get active, tested credential
    cred = await service.get_active_credential(user_id, network_type)
    
    if not cred:
        raise ValueError(f"No valid credential for {network_type.value}")
    
    return cred  # {"credential_id": ..., "address": ..., "mnemonic": ...}
```

## Migration Steps

1. **Database Setup**

   ```bash
   # Add new tables to database
   alembic upgrade head
   ```

2. **Create Credentials**

   ```bash
   # Use API or admin panel to add credentials
   curl -X POST http://localhost:8889/api/v1/dydx/credentials ...
   ```

3. **Verify Credentials**

   ```bash
   # Test each credential
   curl -X POST http://localhost:8889/api/v1/dydx/credentials/{id}/test ...
   ```

4. **Update .env**

   ```bash
   # Remove DYDX_TESTNET_ADDRESS and DYDX_TESTNET_MNEMONIC
   # Keep only IS_TESTNET for network selection
   ```

5. **Update Bot Code**

   ```python
   # Replace hardcoded credential loading with database queries
   cred = await service.get_active_credential(user_id, network_type)
   ```

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 400 | Invalid request format | Check address/mnemonic format |
| 401 | Not authenticated | Provide valid JWT token |
| 403 | Permission denied | Can only access own credentials |
| 404 | Credential not found | Check credential ID |
| 503 | Credential test failed | Network connection or invalid credential |
| 500 | Server error | Check server logs |

## Best Practices

1. **Never commit credentials** - Always manage via API
2. **Test before using** - Always test credentials before relying on them
3. **Monitor audit logs** - Review who accessed what and when
4. **Rotate credentials** - Periodically update credentials
5. **Use meaningful names** - Name credentials by purpose/wallet
6. **Keep backups** - Export mnemonics securely outside the system
7. **Set active wisely** - Only one credential per network should be active for bot

## Example Workflows

### Setup New Trading Wallet

```bash
# 1. Create credential
RESP=$(curl -X POST http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "network_type": "testnet",
    "address": "dydx1...",
    "mnemonic": "word1 word2 ...",
    "name": "Production Testnet Wallet",
    "test_before_save": true
  }')

CRED_ID=$(echo $RESP | jq '.id')
echo "Created credential: $CRED_ID"

# 2. Verify status
curl -X GET http://localhost:8889/api/v1/dydx/credentials/$CRED_ID/status \
  -H "Authorization: Bearer $TOKEN"

# 3. List all credentials
curl -X GET http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer $TOKEN"
```

### Rotate Credentials

```bash
# 1. Create new credential
# ... (same as above)

# 2. Deactivate old credential
curl -X PUT http://localhost:8889/api/v1/dydx/credentials/{old_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# 3. Test new credential
curl -X POST http://localhost:8889/api/v1/dydx/credentials/{new_id}/test \
  -H "Authorization: Bearer $TOKEN"

# 4. Delete old credential
curl -X DELETE http://localhost:8889/api/v1/dydx/credentials/{old_id} \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

### Credential Test Fails

1. Check network connectivity
2. Verify address format is correct
3. Verify mnemonic phrase is correct (12+ words)
4. Check if address is valid on specified network
5. Review error_message in credential details

### Can't Access Credential

1. Verify JWT token is valid
2. Check that credential belongs to current user
3. Verify credential is marked as active

### Performance Issues

1. Consider indexing on `user_id`, `network_type`, `is_active`
2. Implement credential caching in bot
3. Batch test operations during off-hours
