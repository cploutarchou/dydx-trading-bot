# Configuration Guide

This guide provides comprehensive documentation for configuring the dYdX Trading Bot using the YAML-based configuration system.

## 🎯 Overview

The dYdX Trading Bot uses a modern YAML-based configuration system that replaced the legacy `.env` file approach. The configuration is type-safe, validated at runtime, and supports both testnet and mainnet environments.

## 📁 Configuration Files

### Primary Configuration
- **Location**: `app/config.yaml`
- **Generation**: Run `make config` to create template
- **Format**: YAML with nested structure
- **Validation**: Runtime validation with detailed error messages

### Legacy Support
- **Location**: `.env` (deprecated)
- **Status**: Shows migration notice, redirects to YAML
- **Migration**: Automatic prompts guide users to new system

## 🏗️ Configuration Structure

### Complete Configuration Template

```yaml
# Environment Configuration
is_testnet: true  # false for mainnet trading
environment: "development"  # development, staging, production

# Unified dYdX Configuration (recommended)
dydx:
  dydx_chain_address: "dydx1abc..."
  dydx_chain_secret: "word1 word2 word3..."

# Alternative: Separate testnet/mainnet configs
# dydx_testnet:
#   dydx_chain_address: "dydx1testnet..."
#   dydx_chain_secret: "testnet mnemonic..."
# 
# dydx_mainnet:
#   dydx_chain_address: "dydx1mainnet..."
#   dydx_chain_secret: "mainnet mnemonic..."

# Telegram Notifications
telegram:
  token: "123456789:ABCDEF..."
  chat_id: "123456789"

# Bot Trading Settings
botSettings:
  abortAllPositions: false      # Close all positions on startup
  findCointegratedPairs: true   # Perform cointegration analysis
  manageExits: true            # Monitor and close positions
  placeTrades: true            # Execute new trades
  resolutionTimeframe: "1HOUR"  # Price data timeframe
  strategy: "cointegration"     # Trading strategy type
  
  # Statistical Parameters
  statsWindow: 21               # Rolling window for calculations
  maxHalfLife: 24              # Maximum half-life (hours)
  ZScoreThreshold: 1.5         # Entry/exit Z-score threshold
  
  # Position Management
  usdPerTrade: 10.0            # USD amount per trade
  usdMinCollateral: 100.0      # Minimum account collateral
  closeAtZscoreCross: true     # Close when Z-score crosses zero
  
  # API Endpoints
  indexer_endpoint:
    testnet: "https://indexer.v4testnet.dydx.exchange"
    mainnet: "https://indexer.dydx.trade"

# Logging Configuration
logging:
  level: "INFO"                # DEBUG, INFO, WARNING, ERROR, CRITICAL
  loki:
    enabled: false             # Enable Grafana Loki integration
    url: ""                    # Loki endpoint URL
    username: ""               # Basic auth username
    password: ""               # Basic auth password
    tenant_id: null            # Multi-tenant ID (optional)
    labels:
      app: "dydx-trading-bot"
      environment: "development"
```

## ⚙️ Configuration Parameters

### Environment Settings

| Parameter | Type | Description | Default | Required |
|-----------|------|-------------|---------|----------|
| `is_testnet` | boolean | Use testnet (true) or mainnet (false) | true | ✅ |
| `environment` | string | Environment identifier | "development" | ❌ |

### dYdX Connection

#### Unified Configuration (Recommended)
```yaml
dydx:
  dydx_chain_address: "dydx1..."
  dydx_chain_secret: "word1 word2..."
```

#### Separate Testnet/Mainnet Configuration
```yaml
dydx_testnet:
  dydx_chain_address: "dydx1testnet..."
  dydx_chain_secret: "testnet mnemonic..."

dydx_mainnet:
  dydx_chain_address: "dydx1mainnet..."
  dydx_chain_secret: "mainnet mnemonic..."
```

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `dydx_chain_address` | string | Your dYdX chain address | ✅ |
| `dydx_chain_secret` | string | BIP39 mnemonic phrase (12+ words) | ✅ |

### Telegram Notifications

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `token` | string | Telegram bot token from @BotFather | ✅ |
| `chat_id` | string | Your Telegram chat ID | ✅ |

**Getting Telegram Credentials:**
1. Message @BotFather on Telegram
2. Create new bot with `/newbot`
3. Save the token provided
4. Message @userinfobot to get your chat_id

### Bot Trading Settings

#### Behavior Flags

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `abortAllPositions` | boolean | Close all positions on startup | false |
| `findCointegratedPairs` | boolean | Perform cointegration analysis | true |
| `manageExits` | boolean | Monitor and close existing positions | true |
| `placeTrades` | boolean | Execute new trades | true |

#### Strategy Parameters

| Parameter | Type | Description | Default | Range |
|-----------|------|-------------|---------|-------|
| `resolutionTimeframe` | string | Price data timeframe | "1HOUR" | 1MIN, 5MIN, 15MIN, 30MIN, 1HOUR, 4HOUR, 1DAY |
| `strategy` | string | Trading strategy type | "cointegration" | Fixed value |
| `statsWindow` | integer | Rolling window for Z-score calculation | 21 | 5-100 |
| `maxHalfLife` | integer | Maximum half-life for mean reversion (hours) | 24 | 1-168 |
| `ZScoreThreshold` | float | Entry/exit Z-score threshold | 1.5 | 0.5-3.0 |

#### Position Management

| Parameter | Type | Description | Default | Range |
|-----------|------|-------------|---------|-------|
| `usdPerTrade` | float | USD amount per trade | 10.0 | 1.0-1000.0 |
| `usdMinCollateral` | float | Minimum account collateral required | 100.0 | 50.0-10000.0 |
| `closeAtZscoreCross` | boolean | Close positions when Z-score crosses zero | true | - |

### Logging Configuration

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `level` | string | Log level threshold | "INFO" |
| `loki.enabled` | boolean | Enable Grafana Loki integration | false |
| `loki.url` | string | Loki endpoint URL | "" |
| `loki.username` | string | Basic authentication username | "" |
| `loki.password` | string | Basic authentication password | "" |
| `loki.tenant_id` | string | Multi-tenant identifier (optional) | null |
| `loki.labels.app` | string | Application label for log streams | "dydx-trading-bot" |
| `loki.labels.environment` | string | Environment label for log streams | "development" |

## 🔧 Setup Instructions

### 1. Generate Configuration Template
```bash
make config
```

This creates `app/config.yaml` with default values.

### 2. Edit Configuration
```bash
# Edit with your preferred editor
nano app/config.yaml
# or
code app/config.yaml
```

### 3. Validate Configuration
```bash
# Test configuration loading
make run
```

The bot will validate configuration on startup and show detailed error messages for any issues.

### 4. Environment-Specific Configurations

#### Development Environment
```yaml
is_testnet: true
environment: "development"
botSettings:
  usdPerTrade: 10.0
  findCointegratedPairs: true
logging:
  level: "DEBUG"
```

#### Production Environment
```yaml
is_testnet: false
environment: "production"
botSettings:
  usdPerTrade: 50.0
  findCointegratedPairs: false  # Use pre-calculated pairs
logging:
  level: "INFO"
  loki:
    enabled: true
```

## 🔐 Security Best Practices

### Sensitive Data Protection
1. **Never commit secrets to version control**
2. **Use environment variables for CI/CD**
3. **Restrict file permissions**:
   ```bash
   chmod 600 app/config.yaml
   ```

### Environment Variables Override
The configuration system supports environment variable overrides for CI/CD:

```bash
export DYDX_ADDRESS="dydx1..."
export DYDX_SECRET="word1 word2..."
export TELEGRAM_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="123456"
```

### Docker Secrets
For Docker deployments, mount secrets as files:
```bash
docker run -v ./secrets/config.yaml:/app/config.yaml dydx-bot
```

## 🔄 Migration from Legacy .env

### Automatic Migration Helper
The system provides migration guidance when `.env` files are detected:

```bash
# If .env exists, you'll see:
⚠️  WARNING: .env configuration is deprecated
➡️  Please migrate to app/config.yaml using: make config
📖 Documentation: docs/guides/configuration.md
```

### Manual Migration Mapping

| Legacy .env Key | New YAML Path |
|----------------|---------------|
| `DYDX_ADDRESS` | `dydx.dydx_chain_address` |
| `SECRET_PHRASE` | `dydx.dydx_chain_secret` |
| `IS_TESTNET` | `is_testnet` |
| `TELEGRAM_TOKEN` | `telegram.token` |
| `TELEGRAM_CHAT_ID` | `telegram.chat_id` |

## ❌ Common Configuration Errors

### Invalid YAML Syntax
```yaml
# ❌ Wrong: Missing quotes for strings with special characters
telegram:
  token: 123456:ABC-DEF_GHI

# ✅ Correct: Quoted strings
telegram:
  token: "123456:ABC-DEF_GHI"
```

### Missing Required Fields
```yaml
# ❌ Wrong: Missing dydx_chain_secret
dydx:
  dydx_chain_address: "dydx1..."

# ✅ Correct: All required fields
dydx:
  dydx_chain_address: "dydx1..."
  dydx_chain_secret: "word1 word2 word3..."
```

### Invalid Boolean Values
```yaml
# ❌ Wrong: String instead of boolean
is_testnet: "true"

# ✅ Correct: Boolean value
is_testnet: true
```

### Out of Range Values
```yaml
# ❌ Wrong: Negative trade amount
botSettings:
  usdPerTrade: -10.0

# ✅ Correct: Positive trade amount
botSettings:
  usdPerTrade: 10.0
```

## 🧪 Testing Configuration

### Configuration Validation Script

```python
#!/usr/bin/env python3
# test_config.py
import sys

sys.path.append('.')

from backend.app.config import config

try:
    cfg = config()
    print("✅ Configuration loaded successfully")
    print(f"Environment: {cfg.environment}")
    print(f"Is testnet: {cfg.is_testnet}")
    print(f"Strategy: {cfg.botSettings.strategy}")
except Exception as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)
```

### Docker Configuration Test
```bash
# Test configuration in Docker environment
make docker-build
make docker-run
```

## 📚 Advanced Configuration

### Multiple Environment Files
```bash
# Development
cp app/config.yaml app/config.dev.yaml

# Production
cp app/config.yaml app/config.prod.yaml

# Use specific config
CONFIG_FILE=config.prod.yaml make run
```

### Configuration Validation Schema
The bot uses dataclasses with runtime validation:

```python
@dataclass
class BotSettings:
    usdPerTrade: float = 10.0
    
    def __post_init__(self):
        if self.usdPerTrade <= 0:
            raise ValueError("usdPerTrade must be positive")
```

This comprehensive configuration system ensures type safety, validation, and ease of use while maintaining compatibility with various deployment environments.