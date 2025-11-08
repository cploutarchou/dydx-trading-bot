# Troubleshooting & FAQ - dYdX Credentials Management

> **Common issues, questions, and solutions**

---

## Frequently Asked Questions

### General Questions

#### Q: What exactly does this credentials system do?

**A:** It securely stores your dYdX wallet credentials (address and mnemonic) in an encrypted database instead of plaintext .env files. This provides:

- Encryption at rest (Fernet AES-128)
- Multi-user support
- Complete audit trail
- API-based credential management
- No need to restart bot to change wallets

#### Q: Why is this better than storing credentials in .env?

**A:**

- .env files are plaintext (visible in code/logs)
- Can't change credentials without restarting
- No audit trail
- Not suitable for multi-user/multi-wallet
- Credentials exposed if .env leaked

This system provides encryption, audit logs, and dynamic management.

#### Q: Do I have to use this system?

**A:** No, it's optional. You can continue using .env if you prefer. But for production deployments, this is strongly recommended.

#### Q: What if I lose my encryption key?

**A:** Your credentials become unrecoverable. Store keys securely:

- In .env file only
- NOT in code
- NOT in version control
- Back up securely

#### Q: Can multiple bots share credentials?

**A:** Yes, as long as they have the same user_id. Multiple bots can reference the same credential.

---

## Common Issues

### Encryption & Keys

#### Issue: "Encryption key not found"

**Error Message:**

```
KeyError: CREDENTIALS_ENCRYPTION_KEY
or
cryptography.fernet.InvalidToken
```

**Causes:**

- CREDENTIALS_ENCRYPTION_KEY not in .env
- .env file not loaded
- Environment variable not set

**Solutions:**

1. **Verify .env exists:**

   ```bash
   ls -la .env
   ```

2. **Verify key is in .env:**

   ```bash
   grep CREDENTIALS_ENCRYPTION_KEY .env
   ```

3. **Generate new key if missing:**

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

4. **Add to .env:**

   ```bash
   echo "CREDENTIALS_ENCRYPTION_KEY=<your_key>" >> .env
   ```

5. **Load .env in Python:**

   ```python
   import os
   from dotenv import load_dotenv
   load_dotenv()  # Load .env file
   key = os.getenv('CREDENTIALS_ENCRYPTION_KEY')
   print(f"Key loaded: {key is not None}")
   ```

#### Issue: "InvalidToken: Token has incorrect format"

**Error Message:**

```
cryptography.fernet.InvalidToken
```

**Causes:**

- Key format is invalid
- Key was corrupted
- Using wrong key
- Data was corrupted

**Solutions:**

1. **Verify key format:**

   ```python
   from cryptography.fernet import Fernet
   key = os.getenv('CREDENTIALS_ENCRYPTION_KEY')
   try:
       Fernet(key)
       print("✓ Key is valid")
   except:
       print("✗ Invalid key format")
   ```

2. **Generate new key:**

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

3. **Rotate key:**
   - Back up database
   - Decrypt all credentials with old key
   - Encrypt with new key
   - Update .env with new key

#### Issue: "How do I rotate the encryption key?"

**Process:**

1. **Backup database:**

   ```bash
   cp bot_credentials.db bot_credentials.db.backup
   ```

2. **Export all credentials with old key:**

   ```python
   from models_dydx_credentials import DydxCredential
   from sqlalchemy.orm import Session
   
   credentials = session.query(DydxCredential).all()
   export_data = [
       {
           "id": c.id,
           "address": encryption.decrypt(c.address),
           "mnemonic": encryption.decrypt(c.mnemonic),
       }
       for c in credentials
   ]
   ```

3. **Generate new key:**

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

4. **Update .env:**

   ```bash
   echo "CREDENTIALS_ENCRYPTION_KEY=<new_key>" >> .env
   ```

5. **Re-encrypt with new key:**

   ```python
   new_encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
   for cred in credentials:
       cred.address = new_encryption.encrypt(export_data[...]['address'])
       cred.mnemonic = new_encryption.encrypt(export_data[...]['mnemonic'])
   session.commit()
   ```

---

### Database Issues

#### Issue: "Table dydx_credential does not exist"

**Error Message:**

```
OperationalError: no such table: dydx_credential
SQLAlchemy.exc.ProgrammingError: table "dydx_credential" does not exist
```

**Causes:**

- Database tables not created
- Wrong database URL
- Migration not run

**Solutions:**

1. **Create tables with Alembic:**

   ```bash
   alembic upgrade head
   ```

2. **Or create manually:**

   ```python
   from sqlalchemy import create_engine
   from models_dydx_credentials import Base
   
   engine = create_engine("sqlite:///./bot_credentials.db")
   Base.metadata.create_all(bind=engine)
   print("✓ Tables created")
   ```

3. **Verify tables exist:**

   ```bash
   sqlite3 bot_credentials.db ".tables" | grep dydx
   ```

#### Issue: "Database is locked"

**Error Message:**

```
sqlite3.OperationalError: database is locked
```

**Causes:**

- Multiple processes accessing simultaneously
- Transaction not committed
- Corrupted database

**Solutions:**

1. **Wait and retry:**

   ```python
   import time
   time.sleep(1)  # Wait for lock to release
   # Try again
   ```

2. **Check for open connections:**

   ```bash
   lsof bot_credentials.db
   ```

3. **Close all connections:**

   ```python
   session.close()
   engine.dispose()
   ```

4. **Use WAL mode (SQLite only):**

   ```bash
   sqlite3 bot_credentials.db "PRAGMA journal_mode=WAL;"
   ```

5. **Repair database:**

   ```bash
   # Backup first
   cp bot_credentials.db bot_credentials.db.corrupt
   
   # Vacuum and repair
   sqlite3 bot_credentials.db "VACUUM;"
   ```

#### Issue: "Integrity constraint violated"

**Error Message:**

```
IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed
```

**Causes:**

- Duplicate entry
- Foreign key violation
- Constraint mismatch

**Solutions:**

1. **Check for duplicates:**

   ```python
   from models_dydx_credentials import DydxCredential
   duplicates = session.query(DydxCredential).filter_by(
       user_id=1, network_type="testnet"
   ).all()
   print(f"Found {len(duplicates)} with same user_id/network")
   ```

2. **Delete duplicates:**

   ```python
   # Keep only most recent
   to_delete = duplicates[:-1]
   for cred in to_delete:
       session.delete(cred)
   session.commit()
   ```

---

### API Issues

#### Issue: "401 Unauthorized"

**Error Message:**

```json
{
  "detail": "Not authenticated"
}
```

**Causes:**

- Missing Authorization header
- Invalid token
- Expired token
- Wrong token format

**Solutions:**

1. **Verify token in request:**

   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
        http://localhost:8889/api/v1/dydx/credentials
   ```

2. **Check token format:**

   ```bash
   # Should be: "Bearer <token>"
   # Not: "Bearer: <token>" or just "<token>"
   ```

3. **Verify token is not expired:**

   ```python
   import jwt
   token = "your_token"
   try:
       decoded = jwt.decode(token, "secret_key", algorithms=["HS256"])
       print("✓ Token is valid")
   except jwt.ExpiredSignatureError:
       print("✗ Token expired")
   ```

4. **Get new token:**

   ```bash
   curl -X POST http://localhost:8889/auth/login \
        -d "username=user&password=pass"
   ```

#### Issue: "404 Not Found"

**Error Message:**

```json
{
  "detail": "Not found"
}
```

**Causes:**

- Wrong endpoint URL
- Credential doesn't exist
- API not registered

**Solutions:**

1. **Verify endpoint exists:**

   ```bash
   curl http://localhost:8889/openapi.json | grep dydx
   ```

2. **Check credential ID:**

   ```bash
   curl http://localhost:8889/api/v1/dydx/credentials \
        -H "Authorization: Bearer $TOKEN"
   ```

3. **Verify routes are registered:**

   ```python
   # In main.py
   from routes_dydx_credentials import router
   app.include_router(router, prefix="/api/v1")
   ```

#### Issue: "422 Unprocessable Entity"

**Error Message:**

```json
{
  "detail": [
    {
      "loc": ["body", "address"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Causes:**

- Missing required fields
- Invalid field types
- Invalid values

**Solutions:**

1. **Check request body:**

   ```python
   # Ensure all required fields present:
   {
       "network_type": "testnet",      # Required
       "address": "dydx1...",          # Required
       "mnemonic": "word1 word2...",   # Required
       "name": "My Wallet"             # Optional
   }
   ```

2. **Validate field types:**

   ```bash
   # network_type must be "testnet" or "mainnet"
   # address must be string starting with "dydx1"
   # mnemonic must be 12+ space-separated words
   ```

3. **Check required fields:**

   ```bash
   curl -X POST http://localhost:8889/api/v1/dydx/credentials \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{
          "network_type": "testnet",
          "address": "dydx1abc...",
          "mnemonic": "word1 word2 ... word12",
          "name": "Test"
        }'
   ```

#### Issue: "500 Internal Server Error"

**Error Message:**

```json
{
  "detail": "Internal server error"
}
```

**Causes:**

- Unhandled exception
- Database error
- Configuration error
- Service initialization failed

**Solutions:**

1. **Check server logs:**

   ```bash
   tail -f app.log
   # Or check console output
   ```

2. **Enable debug mode:**

   ```python
   app = FastAPI(debug=True)
   ```

3. **Test service directly:**

   ```python
   from service_dydx_credentials import DydxCredentialsService
   service = DydxCredentialsService(db, encryption)
   # Try operations directly
   ```

4. **Verify all dependencies:**

   ```bash
   python -c "import fastapi, sqlalchemy, cryptography; print('All OK')"
   ```

#### Issue: "Connection refused on localhost:8889"

**Error Message:**

```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Causes:**

- Server not running
- Wrong port
- Firewall blocking
- Server crashed

**Solutions:**

1. **Start server:**

   ```bash
   uvicorn main:app --port 8889
   ```

2. **Verify server running:**

   ```bash
   curl http://localhost:8889/docs
   ```

3. **Check port is available:**

   ```bash
   lsof -i :8889
   ```

4. **Use different port:**

   ```bash
   uvicorn main:app --port 8890
   ```

---

### Credential Issues

#### Issue: "Credential test failed: Invalid address"

**Error Message:**

```json
{
  "success": false,
  "error_message": "Invalid dYdX address format"
}
```

**Causes:**

- Address doesn't start with "dydx1"
- Address is malformed
- Copy/paste error

**Solutions:**

1. **Verify address format:**

   ```bash
   # Valid: dydx1abc123...
   # Invalid: dydx2abc123...
   # Invalid: abc123...
   ```

2. **Get correct address from wallet:**

   ```python
   # From dYdX v4 testnet
   address = "dydx1..."  # From your wallet export
   print(f"Address starts with 'dydx1': {address.startswith('dydx1')}")
   ```

#### Issue: "Credential test failed: Invalid mnemonic"

**Error Message:**

```json
{
  "success": false,
  "error_message": "Invalid mnemonic phrase"
}
```

**Causes:**

- Mnemonic too short (less than 12 words)
- Invalid words
- Extra spaces
- Typos

**Solutions:**

1. **Verify word count:**

   ```python
   mnemonic = "word1 word2 ... wordN"
   words = mnemonic.split()
   print(f"Word count: {len(words)}")  # Should be 12+
   ```

2. **Verify word list:**

   ```python
   # All words must be from BIP39 word list
   # Check: https://github.com/trezor/python-mnemonic
   from mnemonic import Mnemonic
   m = Mnemonic("english")
   valid = m.check(mnemonic)
   print(f"Valid BIP39: {valid}")
   ```

3. **Check for typos:**

   ```bash
   # Compare with original mnemonic carefully
   # Common issues: "the" vs "that", "a" vs "an"
   ```

#### Issue: "Credential test failed: Connection timeout"

**Error Message:**

```json
{
  "success": false,
  "error_message": "Connection to dYdX failed: timeout"
}
```

**Causes:**

- Network issue
- dYdX API down
- Firewall blocking
- Slow connection

**Solutions:**

1. **Test dYdX API directly:**

   ```bash
   curl https://dydx-testnet-api.allthatnode.com/
   ```

2. **Check network connection:**

   ```bash
   ping google.com
   ```

3. **Check firewall:**

   ```bash
   # Allow outbound to dYdX API
   iptables -L | grep ACCEPT
   ```

4. **Try again later:**

   ```bash
   # dYdX API might be temporarily down
   sleep 60
   curl -X POST /api/v1/dydx/credentials/1/test ...
   ```

#### Issue: "Credential test failed: Insufficient balance"

**Error Message:**

```json
{
  "success": false,
  "error_message": "Account balance insufficient"
}
```

**Causes:**

- Wallet has no funds
- Funds on wrong network
- Network mismatch

**Solutions:**

1. **Verify network:**

   ```python
   # Check if testing on testnet
   # If testnet, fund from testnet faucet
   # If mainnet, fund from exchange
   ```

2. **Fund testnet wallet:**

   ```bash
   # Get faucet from: https://faucet.dydx.trade/
   # Or transfer from exchange
   ```

3. **Check balance:**

   ```bash
   # Use dYdX explorer to check wallet balance
   # https://mintscan.io/dydx/address/dydx1...
   ```

---

### Performance Issues

#### Issue: "API responses are slow"

**Symptoms:**

- Requests taking >5 seconds
- High CPU usage
- Database queries slow

**Solutions:**

1. **Enable connection pooling:**

   ```python
   from sqlalchemy.pool import QueuePool
   engine = create_engine(
       "sqlite:///bot_credentials.db",
       poolclass=QueuePool,
       pool_size=5,
       max_overflow=10
   )
   ```

2. **Add database indexes:**

   ```python
   # In models_dydx_credentials.py
   class DydxCredential(Base):
       __tablename__ = "dydx_credential"
       
       user_id = Column(Integer, index=True)
       network_type = Column(String, index=True)
       is_active = Column(Boolean, index=True)
   ```

3. **Cache credentials:**

   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=128)
   async def get_cached_credential(cred_id: int):
       return await service.get_credential(cred_id)
   ```

#### Issue: "High database disk usage"

**Symptoms:**

- bot_credentials.db growing rapidly
- Slow queries

**Solutions:**

1. **Clean old audit logs:**

   ```python
   from datetime import datetime, timedelta
   cutoff = datetime.utcnow() - timedelta(days=30)
   old_audits = session.query(DydxCredentialAudit).filter(
       DydxCredentialAudit.created_at < cutoff
   ).delete()
   session.commit()
   ```

2. **Vacuum database:**

   ```bash
   sqlite3 bot_credentials.db "VACUUM;"
   ```

3. **Archive old data:**

   ```bash
   # Export old data
   sqlite3 bot_credentials.db ".dump" > archive.sql
   # Delete from current DB
   ```

---

## Advanced Troubleshooting

### Debug Mode

#### Enable Full Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In service_dydx_credentials.py
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
```

#### Print Debug Info

```python
import os
import sys

print("Python version:", sys.version)
print("Encryption key exists:", bool(os.getenv('CREDENTIALS_ENCRYPTION_KEY')))
print("Database URL:", os.getenv('DATABASE_URL'))
print("Network type:", os.getenv('IS_TESTNET'))
```

### Database Inspection

#### Query Credentials Directly

```bash
# Using sqlite3 CLI
sqlite3 bot_credentials.db

# List all credentials
SELECT id, user_id, network_type, is_active FROM dydx_credential;

# Count by network
SELECT network_type, COUNT(*) FROM dydx_credential GROUP BY network_type;

# Show audit log
SELECT * FROM dydx_credential_audit ORDER BY created_at DESC LIMIT 10;
```

#### Export Data

```bash
# Export to CSV
sqlite3 bot_credentials.db ".mode csv" ".output credentials.csv" \
"SELECT * FROM dydx_credential;"
```

### Testing Procedures

#### Unit Test Service

```bash
cat > test_service.py << 'EOF'
import asyncio
import os
from service_dydx_credentials import DydxCredentialsService, CredentialEncryption

async def test():
    encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
    
    # Test encryption
    original = "test_secret_123"
    encrypted = encryption.encrypt(original)
    decrypted = encryption.decrypt(encrypted)
    
    assert original == decrypted, "Encryption/decryption failed"
    print("✓ Encryption test passed")

asyncio.run(test())
EOF

python test_service.py
```

---

## Support Resources

### Documentation Files

- `DYDX_CREDENTIALS_API.md` - Complete API documentation
- `DYDX_CREDENTIALS_IMPLEMENTATION.md` - Implementation details
- `CREDENTIALS_QUICKSTART.md` - Quick start guide
- `INTEGRATION_TUTORIAL.md` - Step-by-step integration
- `CREDENTIALS_QUICK_REFERENCE.md` - Quick reference

### External Resources

- [dYdX Docs](https://docs.dydx.trade)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org)
- [Cryptography Docs](https://cryptography.io)

### Getting Help

1. Check this FAQ first
2. Review relevant documentation
3. Check logs and error messages
4. Run debug procedures above
5. Search similar issues

---

**Last Updated:** November 2, 2025  
**Version:** 1.0  
**Status:** ✅ Complete
