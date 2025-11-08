# !/usr/bin/env python3
"""
Quick Start Guide - Integrate Credentials Management System

This script helps you quickly integrate the secure credentials management
system into your existing bot setup.

Steps:

1. Read this file carefully
2. Run setup steps in order
3. Test the system
4. Verify with your bot
"""

import sys

def print_section(title):
    print(f"\n{'='*70}")
    print(f"{title}")
    print(f"{'='*70}")

def print_step(number, title, description):
    print(f"\n[Step {number}] {title}")
    print(f"{'─'*70}")
    print(description)

# ============================================================================

# QUICK START GUIDE

# ============================================================================

print_section("🔐 SECURE dYdX CREDENTIALS MANAGEMENT - QUICK START")

print("""
This guide will help you integrate the secure credentials management system
into your dYdX trading bot in approximately 15 minutes.

BEFORE YOU START:
✓ You have Python 3.8+ installed
✓ You have access to your bot's database
✓ You have admin access to your API server
✓ You have read the documentation files

WHAT YOU'LL GET:
✓ Encrypted credential storage in database
✓ 7 REST endpoints for credential management
✓ Automatic credential testing
✓ Complete audit trail
✓ Multi-user support
""")

print_step(1, "Install Required Files", """
Copy these files to your bot directory:
  cp models_dydx_credentials.py <your-bot-dir>/
  cp service_dydx_credentials.py <your-bot-dir>/
  cp routes_dydx_credentials.py <your-bot-dir>/

Verify the files exist:
  ls -la models_dydx_credentials.py
  ls -la service_dydx_credentials.py
  ls -la routes_dydx_credentials.py
""")

print_step(2, "Generate Encryption Key", """
Generate a secure Fernet encryption key:
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Copy the output (it will look like: 'DUzq...sss8')

⚠️  IMPORTANT: Store this key securely!
    - Add to .env as: CREDENTIALS_ENCRYPTION_KEY=<your-key>
    - Never commit to version control
    - Never share with others
    - Keep a backup in secure location
""")

print_step(3, "Update .env File", """
Edit your .env file:

REMOVE these lines (deprecated):
  DYDX_TESTNET_ADDRESS=...
  DYDX_TESTNET_MNEMONIC=...
  DYDX_MAINNET_ADDRESS=...
  DYDX_MAINNET_MNEMONIC=...

ADD these lines:
  IS_TESTNET=true                              # or false for mainnet
  CREDENTIALS_ENCRYPTION_KEY=<your-generated-key>

Verify:
  grep CREDENTIALS_ENCRYPTION_KEY .env
  grep IS_TESTNET .env
""")

print_step(4, "Create Database Tables", """
Option A - Using Alembic (Recommended):
  alembic revision --autogenerate -m "Add dydx credentials models"
  alembic upgrade head

Option B - Direct SQL:
  Execute SQL from: models_dydx_credentials.py
  
Verify tables were created:
  psql -d your_database -c "\\dt" | grep dydx
  
You should see:
  public | dydx_credential_audit | table
  public | dydx_credentials | table
  public | dydx_test_results | table
""")

print_step(5, "Integrate API Routes", """
Edit your bot_api_server.py:

Add these imports:
  from routes_dydx_credentials import router as credentials_router

Add this line (after creating the FastAPI app):
  app.include_router(credentials_router)

Example:
  app = FastAPI()
  app.include_router(credentials_router)  # Add this line
  app.include_router(other_routers)

Restart your API server:
  python bot_api_server.py
""")

print_step(6, "Generate JWT Token", """
Get a valid JWT token from your authentication system:

Example (using your existing auth):
  curl -X POST <http://localhost:8889/api/v1/auth/token> \\
    -H "Content-Type: application/json" \\
    -d '{"username":"your_user","password":"your_password"}'

Save the token:
  TOKEN="eyJ0eXAiOiJKV1QiLCJhbG..."
""")

print_step(7, "Create Your First Credential", """
Test the API by creating a credential:

  curl -X POST <http://localhost:8889/api/v1/dydx/credentials> \\
    -H "Authorization: Bearer $TOKEN" \\
    -H "Content-Type: application/json" \\
    -d '{
      "network_type": "testnet",
      "address": "dydx1abc123def456...",
      "mnemonic": "word1 word2 word3 ... word12",
      "name": "My Testnet Wallet",
      "description": "Primary trading wallet",
      "test_before_save": true
    }'

Expected response (201 Created):
  {
    "id": 1,
    "network_type": "testnet",
    "address_preview": "dydx1abc...",
    "is_active": true,
    "test_result": {
      "success": true,
      "response_time_ms": 150
    },
    "created_at": "2025-11-02T12:00:00Z"
  }
""")

print_step(8, "List Your Credentials", """
See all your credentials:

  curl -X GET <http://localhost:8889/api/v1/dydx/credentials> \\
    -H "Authorization: Bearer $TOKEN"

Expected response (200 OK):
  [
    {
      "id": 1,
      "network_type": "testnet",
      "name": "My Testnet Wallet",
      "address_preview": "dydx1abc...",
      "is_active": true,
      "is_test_valid": true,
      "last_tested": "2025-11-02T12:05:00Z",
      "created_at": "2025-11-02T12:00:00Z"
    }
  ]
""")

print_step(9, "Test Credential Validity", """
Verify your credential works with dYdX:

  curl -X POST <http://localhost:8889/api/v1/dydx/credentials/1/test> \\
    -H "Authorization: Bearer $TOKEN"

Expected response (200 OK):
  {
    "success": true,
    "response_time_ms": 145,
    "balance": "[{'denom': 'uusdc', 'amount': '1000000'}]",
    "endpoint_used": "<https://indexer.v4testnet.dydx.exchange>",
    "tested_at": "2025-11-02T12:10:00Z"
  }

If test fails, check:

- Address format is correct
- Mnemonic is valid (12+ words)
- Network connectivity
- dYdX endpoint availability
""")

print_step(10, "Update Bot Code", """
Replace hardcoded credentials with database queries:

BEFORE (old way):
  address = os.getenv('DYDX_TESTNET_ADDRESS')
  mnemonic = os.getenv('DYDX_TESTNET_MNEMONIC')

AFTER (new way):
  from service_dydx_credentials import DydxCredentialsService, CredentialEncryption
  from models_dydx_credentials import NetworkType
  
  encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
  service = DydxCredentialsService(db_session, encryption)
  
  cred = await service.get_active_credential(
    user_id=1,  # Current user ID
    network_type=NetworkType.TESTNET
  )
  
  address = cred['address']
  mnemonic = cred['mnemonic']

Features:
  ✓ Credentials from database (encrypted)
  ✓ Automatic failover to other valid credentials
  ✓ No restart needed to change credentials
  ✓ Full audit trail of access
""")

print_section("✅ Integration Complete!")

print("""
You have successfully integrated the secure credentials management system!

NEXT STEPS:

1. ✓ Test all endpoints with your credentials
2. ✓ Update your bot code to use the new service
3. ✓ Monitor audit logs for operations
4. ✓ Train team on new credential management
5. ✓ Remove old .env credential variables

VERIFY EVERYTHING WORKS:
  • List credentials: GET /api/v1/dydx/credentials
  • Get credential details: GET /api/v1/dydx/credentials/1
  • Test credential: POST /api/v1/dydx/credentials/1/test
  • Check status: GET /api/v1/dydx/credentials/1/status

ADDITIONAL RESOURCES:

- DYDX_CREDENTIALS_API.md - Complete API reference
- DYDX_CREDENTIALS_IMPLEMENTATION.md - Implementation details
- CREDENTIALS_SYSTEM_SUMMARY.txt - System overview

SUPPORT:

- Check documentation files for troubleshooting
- Review database audit logs for operation history
- Test credentials manually via API
- Monitor bot logs for errors

SECURITY REMINDERS:
  ✓ Keep CREDENTIALS_ENCRYPTION_KEY secure
  ✓ Never commit keys to version control
  ✓ Rotate keys periodically
  ✓ Monitor audit logs for suspicious activity
  ✓ Use HTTPS in production
  ✓ Restrict API access with proper authentication

ESTIMATED TIME: ~15 minutes
DIFFICULTY: Easy to Medium
RESULT: Production-Grade Secure Credentials Management

Good luck! 🚀
""")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("To proceed with integration, follow each step above.")
    print("="*70 + "\n")
