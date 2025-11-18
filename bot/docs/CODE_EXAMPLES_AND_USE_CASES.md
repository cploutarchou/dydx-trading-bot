# Code Examples & Use Cases - dYdX Credentials Management

> **Real-world usage patterns and code examples**

---

## Use Case 1: Single Bot with Single Wallet

**Scenario:** Basic trading bot with one wallet

### Implementation

```python
# trading_bot.py
import os
from sqlalchemy.orm import Session
from fastapi import Depends
from internal.domain.models_dydx_credentials import NetworkType
from internal.service.service_dydx_credentials import DydxCredentialsService, CredentialEncryption


async def initialize_trading_bot(db: Session):
    """Initialize bot with stored credential"""

    # Setup encryption and service
    encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
    service = DydxCredentialsService(db, encryption)

    # Get active credential for current user
    credential = await service.get_active_credential(
        user_id=1,  # Bot's user ID
        network_type=NetworkType.TESTNET
    )

    if not credential:
        raise Exception("No active credential found! Add one via API.")

    # Use credential for trading
    return {
        'address': credential['address'],
        'mnemonic': credential['mnemonic'],
        'network': 'testnet'
    }
```

### Adding Credential via API

```bash
# 1. Get JWT token
TOKEN=$(curl -X POST http://localhost:8889/auth/login \
  -d "username=bot&password=botpass" | jq '.data.access_token')

# 2. Add credential
curl -X POST http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "network_type": "testnet",
    "address": "dydx1abc123...",
    "mnemonic": "word1 word2 ... word12",
    "name": "Main Trading Wallet",
    "test_before_save": true
  }'

# 3. Start bot - it will use the stored credential
python trading_bot.py
```

---

## Use Case 2: Multi-Wallet Trading (Rotation)

**Scenario:** Trading bot that rotates between multiple wallets for risk distribution

### Implementation

```python
# multi_wallet_bot.py
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from internal.domain.models_dydx_credentials import NetworkType
from internal.service.service_dydx_credentials import DydxCredentialsService, CredentialEncryption


class MultiWalletBot:
    def __init__(self, db: Session, user_id: int, service: DydxCredentialsService):
        self.db = db
        self.user_id = user_id
        self.service = service
        self.current_wallet_index = 0

    async def get_all_wallets(self) -> List[Dict[str, Any]]:
        """Get all active wallets"""
        return await self.service.list_credentials(
            user_id=self.user_id,
            network_type=NetworkType.TESTNET,
            active_only=True
        )

    async def get_next_wallet(self) -> Dict[str, Any]:
        """Get next wallet in rotation"""
        wallets = await self.get_all_wallets()

        if not wallets:
            raise Exception("No wallets available!")

        wallet = wallets[self.current_wallet_index % len(wallets)]
        self.current_wallet_index += 1

        return wallet

    async def execute_trade(self, pair: str, size: float):
        """Execute trade with rotated wallet"""
        wallet = await self.get_next_wallet()

        print(f"Executing trade on {wallet['name']}")
        print(f"Address: {wallet['address_preview']}")

        # Use wallet for trading
        address = wallet['address']
        mnemonic = wallet['mnemonic']

        # Initialize dYdX client and trade
        # ... trading logic ...


# Usage
async def main():
    encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
    service = DydxCredentialsService(db, encryption)

    bot = MultiWalletBot(db, user_id=1, service=service)

    # Add multiple wallets via API first
    # Then run trades:
    for _ in range(10):
        await bot.execute_trade("BTC-USD", 1000)
```

### Adding Multiple Wallets

```bash
# Add Wallet 1
curl -X POST http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"network_type":"testnet","address":"dydx1aaa...","mnemonic":"...","name":"Wallet 1"}'

# Add Wallet 2
curl -X POST http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"network_type":"testnet","address":"dydx1bbb...","mnemonic":"...","name":"Wallet 2"}'

# Add Wallet 3
curl -X POST http://localhost:8889/api/v1/dydx/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"network_type":"testnet","address":"dydx1ccc...","mnemonic":"...","name":"Wallet 3"}'

# All trades now rotate between these wallets
```

---

## Use Case 3: Multi-User Trading Platform

**Scenario:** SaaS platform where each user manages their own trading wallet

### Implementation

```python
# trading_service.py
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from internal.domain.models_dydx_credentials import NetworkType
from internal.service.service_dydx_credentials import DydxCredentialsService


class UserTradingService:
    def __init__(self, db: Session, service: DydxCredentialsService):
        self.db = db
        self.service = service

    async def setup_user_wallet(
            self,
            user_id: int,
            address: str,
            mnemonic: str,
            name: str
    ) -> Dict[str, Any]:
        """Setup wallet for a user"""

        # Create credential
        result = await self.service.create_credential(
            user_id=user_id,
            network_type=NetworkType.TESTNET,
            address=address,
            mnemonic=mnemonic,
            name=name,
            test_before_save=True
        )

        if not result.get('is_test_valid'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wallet test failed - check credentials"
            )

        return result

    async def get_user_wallet(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's active wallet"""
        return await self.service.get_active_credential(
            user_id=user_id,
            network_type=NetworkType.TESTNET
        )

    async def start_trading_for_user(self, user_id: int):
        """Start trading with user's wallet"""
        wallet = await self.get_user_wallet(user_id)

        if not wallet:
            raise Exception(f"User {user_id} has no configured wallet")

        # Initialize trading with wallet
        return {
            'user_id': user_id,
            'wallet_name': wallet['name'],
            'address': wallet['address']
        }

    async def list_user_wallets(self, user_id: int) -> list:
        """List all user's wallets"""
        return await self.service.list_credentials(
            user_id=user_id,
            active_only=False
        )

    async def switch_wallet(self, user_id: int, new_wallet_id: int):
        """Switch user's active wallet"""

        # Get all user wallets
        wallets = await self.service.list_credentials(user_id=user_id)

        # Disable all
        for wallet in wallets:
            await self.service.update_credential(
                credential_id=wallet['id'],
                user_id=user_id,
                is_active=False
            )

        # Enable new one
        await self.service.update_credential(
            credential_id=new_wallet_id,
            user_id=user_id,
            is_active=True
        )


# FastAPI endpoints
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["User Trading"])


class SetupWalletRequest(BaseModel):
    address: str
    mnemonic: str
    name: str


@router.post("/{user_id}/wallet/setup")
async def setup_user_wallet(
        user_id: int,
        request: SetupWalletRequest,
        service: UserTradingService = Depends()
):
    """Setup wallet for user"""
    return await service.setup_user_wallet(
        user_id=user_id,
        address=request.address,
        mnemonic=request.mnemonic,
        name=request.name
    )


@router.get("/{user_id}/wallet")
async def get_user_wallet(
        user_id: int,
        service: UserTradingService = Depends()
):
    """Get user's active wallet"""
    wallet = await service.get_user_wallet(user_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="No wallet found")
    return wallet


@router.post("/{user_id}/trading/start")
async def start_trading(
        user_id: int,
        service: UserTradingService = Depends()
):
    """Start trading with user's wallet"""
    return await service.start_trading_for_user(user_id)


@router.get("/{user_id}/wallets")
async def list_user_wallets(
        user_id: int,
        service: UserTradingService = Depends()
):
    """List user's wallets"""
    return await service.list_user_wallets(user_id)


@router.put("/{user_id}/wallet/switch/{wallet_id}")
async def switch_wallet(
        user_id: int,
        wallet_id: int,
        service: UserTradingService = Depends()
):
    """Switch user's active wallet"""
    await service.switch_wallet(user_id, wallet_id)
    return {"status": "switched"}
```

---

## Use Case 4: Credential Health Monitoring

**Scenario:** Periodically test credentials and alert if they become invalid

### Implementation

```python
# credential_monitor.py
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from internal.domain.models_dydx_credentials import DydxCredential, DydxTestResult
from internal.service.service_dydx_credentials import DydxCredentialsService


class CredentialMonitor:
    def __init__(self, db: Session, service: DydxCredentialsService):
        self.db = db
        self.service = service
        self.test_interval = timedelta(hours=1)  # Test every hour

    async def get_credentials_needing_test(self) -> list:
        """Get credentials that haven't been tested recently"""
        cutoff_time = datetime.utcnow() - self.test_interval

        credentials = self.db.query(DydxCredential).filter(
            DydxCredential.is_active == True,
            (DydxCredential.last_tested < cutoff_time) |
            (DydxCredential.last_tested == None)
        ).all()

        return credentials

    async def test_all_credentials(self) -> dict:
        """Test all active credentials and report status"""

        credentials = await self.get_credentials_needing_test()
        results = {
            'total': len(credentials),
            'passed': 0,
            'failed': 0,
            'details': []
        }

        for credential in credentials:
            result = await self.service.test_credential(credential.id)

            if result['success']:
                results['passed'] += 1
                status = "✅ PASS"
            else:
                results['failed'] += 1
                status = "❌ FAIL"

            results['details'].append({
                'id': credential.id,
                'name': credential.name,
                'address': credential.address_preview,
                'status': status,
                'error': result.get('error_message')
            })

        return results

    async def alert_on_failures(self, results: dict) -> None:
        """Send alerts if credentials fail"""

        if results['failed'] > 0:
            # Send email/Slack alert
            failed_creds = [
                d for d in results['details'] if '❌' in d['status']
            ]

            message = f"⚠️ {results['failed']} credentials failed test:\n"
            for cred in failed_creds:
                message += f"\n- {cred['name']} ({cred['address']})"
                message += f"\n  Error: {cred['error']}"

            # TODO: Send alert via email/Slack/etc
            print(message)

    async def run_continuous_monitoring(self):
        """Run monitoring in background"""

        while True:
            try:
                results = await self.test_all_credentials()
                await self.alert_on_failures(results)

                print(f"Monitor: {results['passed']}/{results['total']} passed")

                # Wait before next test
                await asyncio.sleep(3600)  # 1 hour

            except Exception as e:
                print(f"Monitoring error: {e}")
                await asyncio.sleep(60)


# Usage in FastAPI app
from contextlib import asynccontextmanager

monitor = None


@asynccontextmanager
async def lifespan(app):
    # Startup
    global monitor
    encryption = CredentialEncryption(os.getenv('CREDENTIALS_ENCRYPTION_KEY'))
    service = DydxCredentialsService(db, encryption)
    monitor = CredentialMonitor(db, service)

    # Start monitoring in background
    asyncio.create_task(monitor.run_continuous_monitoring())

    yield

    # Shutdown


app = FastAPI(lifespan=lifespan)
```

---

## Use Case 5: Disaster Recovery & Backup

**Scenario:** Backup and restore credentials safely

### Implementation

```python
# backup_restore.py
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session
from internal.domain.models_dydx_credentials import DydxCredential
from internal.service.service_dydx_credentials import DydxCredentialsService


class CredentialBackup:
    def __init__(self, db: Session, service: DydxCredentialsService):
        self.db = db
        self.service = service

    async def backup_all_credentials(self, backup_dir: str = "./backups") -> str:
        """Backup all credentials to encrypted JSON file"""

        os.makedirs(backup_dir, exist_ok=True)

        # Get all credentials
        credentials = self.db.query(DydxCredential).all()

        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0',
            'credentials': []
        }

        for cred in credentials:
            backup_data['credentials'].append({
                'id': cred.id,
                'user_id': cred.user_id,
                'network_type': cred.network_type,
                'address': cred.address,  # Already encrypted
                'mnemonic': cred.mnemonic,  # Already encrypted
                'name': cred.name,
                'is_active': cred.is_active,
                'created_at': cred.created_at.isoformat()
            })

        # Save to file
        filename = f"{backup_dir}/credentials_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(backup_data, f, indent=2)

        print(f"✓ Backed up {len(credentials)} credentials to {filename}")
        return filename

    async def restore_from_backup(self, backup_file: str) -> dict:
        """Restore credentials from backup file"""

        with open(backup_file, 'r') as f:
            backup_data = json.load(f)

        results = {'restored': 0, 'skipped': 0, 'errors': []}

        for cred_data in backup_data['credentials']:
            try:
                # Check if already exists
                existing = self.db.query(DydxCredential).filter_by(
                    id=cred_data['id'],
                    user_id=cred_data['user_id']
                ).first()

                if existing:
                    results['skipped'] += 1
                    continue

                # Create new credential from backup
                new_cred = DydxCredential(
                    id=cred_data['id'],
                    user_id=cred_data['user_id'],
                    network_type=cred_data['network_type'],
                    address=cred_data['address'],
                    mnemonic=cred_data['mnemonic'],
                    name=cred_data['name'],
                    is_active=cred_data['is_active']
                )

                self.db.add(new_cred)
                results['restored'] += 1

            except Exception as e:
                results['errors'].append(f"Error restoring {cred_data['id']}: {e}")

        self.db.commit()
        print(f"✓ Restored {results['restored']}, skipped {results['skipped']}")

        return results

    def list_backups(self, backup_dir: str = "./backups") -> list:
        """List available backup files"""

        if not os.path.exists(backup_dir):
            return []

        backups = []
        for filename in os.listdir(backup_dir):
            if filename.startswith('credentials_backup_'):
                filepath = os.path.join(backup_dir, filename)
                size = os.path.getsize(filepath)
                mtime = os.path.getmtime(filepath)

                backups.append({
                    'filename': filename,
                    'path': filepath,
                    'size': size,
                    'timestamp': datetime.fromtimestamp(mtime)
                })

        return sorted(backups, key=lambda x: x['timestamp'], reverse=True)


# Usage
async def daily_backup():
    """Run daily backup"""
    backup = CredentialBackup(db, service)
    await backup.backup_all_credentials()


async def restore_from_latest():
    """Restore from latest backup"""
    backup = CredentialBackup(db, service)
    backups = backup.list_backups()

    if backups:
        latest = backups[0]
        await backup.restore_from_backup(latest['path'])
```

---

## Use Case 6: Audit Trail Analysis

**Scenario:** Analyze credential usage patterns and security events

### Implementation

```python
# audit_analysis.py
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from internal.domain.models_dydx_credentials import DydxCredentialAudit


class AuditAnalysis:
    def __init__(self, db: Session):
        self.db = db

    def get_recent_activity(self, hours: int = 24) -> list:
        """Get audit activity from last N hours"""

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        audits = self.db.query(DydxCredentialAudit).filter(
            DydxCredentialAudit.created_at >= cutoff
        ).order_by(DydxCredentialAudit.created_at.desc()).all()

        return [
            {
                'timestamp': audit.created_at,
                'operation': audit.operation,
                'user': audit.user_id,
                'credential': audit.credential_id,
                'success': audit.success,
                'details': audit.details
            }
            for audit in audits
        ]

    def get_failed_operations(self, days: int = 7) -> dict:
        """Get failed operations from last N days"""

        cutoff = datetime.utcnow() - timedelta(days=days)

        failed = self.db.query(
            DydxCredentialAudit.operation,
            func.count(DydxCredentialAudit.id).label('count')
        ).filter(
            DydxCredentialAudit.success == False,
            DydxCredentialAudit.created_at >= cutoff
        ).group_by(DydxCredentialAudit.operation).all()

        return {op: count for op, count in failed}

    def get_most_accessed_credentials(self, limit: int = 10) -> list:
        """Get most frequently accessed credentials"""

        most_accessed = self.db.query(
            DydxCredentialAudit.credential_id,
            func.count(DydxCredentialAudit.id).label('access_count')
        ).group_by(DydxCredentialAudit.credential_id).order_by(
            func.count(DydxCredentialAudit.id).desc()
        ).limit(limit).all()

        return [
            {'credential_id': cred_id, 'access_count': count}
            for cred_id, count in most_accessed
        ]

    def get_user_activity(self, user_id: int, days: int = 30) -> dict:
        """Get activity summary for specific user"""

        cutoff = datetime.utcnow() - timedelta(days=days)

        audits = self.db.query(DydxCredentialAudit).filter(
            DydxCredentialAudit.user_id == user_id,
            DydxCredentialAudit.created_at >= cutoff
        ).all()

        operations = {}
        for audit in audits:
            ops = operations.setdefault(audit.operation, {
                'success': 0, 'failed': 0
            })
            if audit.success:
                ops['success'] += 1
            else:
                ops['failed'] += 1

        return {
            'user_id': user_id,
            'total_operations': len(audits),
            'operations': operations
        }


# FastAPI endpoints for audit
from fastapi import APIRouter

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/activity/recent")
async def get_recent_activity(
        hours: int = 24,
        analysis: AuditAnalysis = Depends()
):
    """Get recent audit activity"""
    return analysis.get_recent_activity(hours)


@router.get("/failed-operations")
async def get_failed_operations(
        days: int = 7,
        analysis: AuditAnalysis = Depends()
):
    """Get failed operations"""
    return analysis.get_failed_operations(days)


@router.get("/top-credentials")
async def get_top_credentials(
        limit: int = 10,
        analysis: AuditAnalysis = Depends()
):
    """Get most accessed credentials"""
    return analysis.get_most_accessed_credentials(limit)


@router.get("/user/{user_id}/activity")
async def get_user_activity(
        user_id: int,
        days: int = 30,
        analysis: AuditAnalysis = Depends()
):
    """Get user activity"""
    return analysis.get_user_activity(user_id, days)
```

---

## Summary of Use Cases

| Use Case | Complexity | Users | Wallets | Key Feature |
|----------|-----------|-------|---------|------------|
| Single Bot, Single Wallet | Low | 1 | 1 | Simple setup |
| Multi-Wallet Rotation | Medium | 1 | N | Risk distribution |
| Multi-User Platform | High | N | N | User isolation |
| Health Monitoring | Medium | Any | Any | Automated testing |
| Disaster Recovery | Medium | Any | Any | Backup/restore |
| Audit Analysis | Medium | Any | Any | Security insights |

---

**Last Updated:** November 2, 2025  
**Version:** 1.0  
**Status:** ✅ Complete
