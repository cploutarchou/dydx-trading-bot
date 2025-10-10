# Quick Start Guide

Get the dYdX Trading Bot up and running in minutes with this step-by-step guide.

## ⚡ 5-Minute Setup

### Step 1: Prerequisites
```bash
# Check Python version (3.12+ required)
python --version

# Install Git if not available
# Ubuntu: sudo apt install git
# macOS: brew install git
```

### Step 2: Clone and Setup
```bash
# Clone the repository
git clone <repository-url>
cd dydx-trading-bot

# Automated setup
make setup install
```

### Step 3: Configure
```bash
# Generate configuration template
make config

# Edit configuration (use your preferred editor)
nano app/config.yaml
# OR
code app/config.yaml
```

**Minimal Configuration:**
```yaml
is_testnet: true  # Start with testnet

dydx:
  dydx_chain_address: "your-dydx-address"
  dydx_chain_secret: "your twelve word mnemonic phrase here"

telegram:
  token: "your-telegram-bot-token"
  chat_id: "your-chat-id"

botSettings:
  findCointegratedPairs: true
  manageExits: true
  placeTrades: false  # Disable trading initially for testing
```

### Step 4: Test and Run
```bash
# Validate setup
make test

# Start the bot
make run
```

## 🎯 Essential Configuration

### Get dYdX Credentials

1. **Testnet Account** (recommended for first run):
   - Visit [dYdX v4 Testnet](https://v4.testnet.dydx.exchange/)
   - Create account and note your address
   - Save your mnemonic phrase securely

2. **Mainnet Account** (for live trading):
   - Visit [dYdX v4](https://dydx.exchange/)
   - Create account with funds
   - **⚠️ Start with small amounts**

### Get Telegram Credentials

1. **Create Telegram Bot**:
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow instructions
   - Save the bot token (format: `123456789:ABCDEF...`)

2. **Get Your Chat ID**:
   - Message [@userinfobot](https://t.me/userinfobot)
   - Note your chat ID (numeric value)

## 🐳 Docker Quick Start

### Option 1: Docker Compose (Recommended)
```bash
# Clone repository
git clone <repository-url>
cd dydx-trading-bot

# Create configuration
make config
# Edit app/config.yaml with your credentials

# Start with Docker Compose
make docker-up
```

### Option 2: Docker Build & Run
```bash
# Build image
make docker-build

# Run container
make docker-run

# View logs
make docker-logs
```

## 🧪 Testing Mode

Start in safe testing mode before live trading:

```yaml
# app/config.yaml - Safe testing configuration
is_testnet: true

botSettings:
  # Analysis and monitoring only
  findCointegratedPairs: true
  manageExits: true
  placeTrades: false  # DISABLE trading initially
  
  # Conservative parameters
  usdPerTrade: 5.0      # Small amounts for testing
  usdMinCollateral: 50.0
  ZScoreThreshold: 2.0  # Higher threshold (fewer signals)
```

### Testing Workflow

1. **Configuration Test**:
   ```bash
   python -c "from app.config import config; print('✅ Config valid:', config() is not None)"
   ```

2. **Connection Test**:
   ```bash
   cd app && python -c "import asyncio; from func_connections import connect_dydx; asyncio.run(connect_dydx())"
   ```

3. **Analysis Test**:
   ```bash
   # Run cointegration analysis only
   make run
   # Check generated cointegrated_pairs.csv
   ```

4. **Paper Trading Test**:
   ```yaml
   # Enable position monitoring without actual trading
   botSettings:
     placeTrades: false
     manageExits: true
   ```

## 📊 What to Expect

### First Run Output

```bash
Program started...
Connecting to Client...
✅ Configuration loaded successfully
✅ Is Testnet: True
✅ Bot Strategy: cointegration
✅ Telegram Chat ID: 123456789
Bot launch successful

Fetching token market prices, please allow around 5 minutes...
✅ Jurisdiction check succeeded for BTC-USD
Extracting prices for 1 of 45 tokens: BTC-USD
Extracting prices for 2 of 45 tokens: ETH-USD
...
Storing cointegrated pairs...
✅ Cointegrated pairs successfully saved

Managing exits...
✅ No bot_agents.json found; nothing to close

Finding trading opportunities...
✅ Loaded 12 cointegrated pairs
Manage open trades cycle complete
```

### Generated Files

After first run, you'll see:
```bash
ls app/
bot_agents.json         # Trading state (empty initially)
cointegrated_pairs.csv  # Statistical analysis results
config.yaml            # Your configuration
```

## 🎛️ Key Controls

### Behavior Flags

| Setting | Purpose | Safe Default |
|---------|---------|--------------|
| `findCointegratedPairs` | Run statistical analysis | `true` |
| `manageExits` | Monitor existing positions | `true` |
| `placeTrades` | Execute new trades | `false` (testing) |
| `abortAllPositions` | Close all on startup | `false` |

### Trading Parameters

| Parameter | Testing Value | Production Value |
|-----------|---------------|------------------|
| `usdPerTrade` | `5.0` | `10.0-50.0` |
| `ZScoreThreshold` | `2.0` | `1.5` |
| `usdMinCollateral` | `50.0` | `100.0+` |
| `is_testnet` | `true` | `false` |

## 🚨 Safety Checklist

### Before First Run
- [ ] Using testnet environment (`is_testnet: true`)
- [ ] Trading disabled (`placeTrades: false`)
- [ ] Small test amounts configured
- [ ] Telegram notifications working
- [ ] Configuration validated

### Before Live Trading
- [ ] Tested thoroughly on testnet
- [ ] Understood strategy and risks
- [ ] Set appropriate position limits
- [ ] Configured monitoring and alerts
- [ ] Have emergency stop procedures ready

## 📱 Monitoring Your Bot

### Telegram Notifications
You'll receive notifications for:
- ✅ Bot startup/shutdown
- 📈 New positions opened
- 📉 Positions closed
- ⚠️ Errors and warnings
- 🚨 Critical issues

### Log Monitoring
```bash
# Follow logs in real-time
tail -f app/logs/trading_bot.log

# Check for errors
grep -i error app/logs/trading_bot.log

# Monitor Docker logs
make docker-logs
```

### Key Metrics to Watch
- **Cointegrated pairs found**: Should be >5 for active trading
- **Position count**: Check `bot_agents.json` for active trades  
- **Account balance**: Ensure sufficient collateral
- **Error rates**: Should be minimal in normal operation

## 🔧 Common Quick Fixes

### "Configuration could not be loaded"
```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('app/config.yaml'))"

# Regenerate if corrupted
make config
```

### "Failed to connect to client"
```bash
# Test network connectivity
curl -s https://indexer.dydx.trade/v4/markets

# Check for geographic restrictions (HTTP 403)
# May need VPN for some regions
```

### "No cointegrated pairs found"
```bash
# Reduce threshold for more pairs
# In config.yaml:
botSettings:
  maxHalfLife: 48  # Increase from 24
  ZScoreThreshold: 1.0  # Decrease from 1.5
```

### "Insufficient collateral"
```bash
# Fund your testnet account
# Or reduce minimum requirement:
botSettings:
  usdMinCollateral: 25.0  # Reduce from 100.0
  usdPerTrade: 2.0        # Reduce from 10.0
```

## 🎓 Next Steps

### 1. Learn the Strategy
- Read [Trading Strategy Guide](../trading/strategy.md)
- Understand cointegration concepts
- Review risk management principles

### 2. Advanced Configuration
- Check [Configuration Guide](./configuration.md)
- Set up Grafana monitoring
- Configure production deployment

### 3. Production Deployment
- Follow [Docker Setup Guide](../deployment/docker-setup.md)
- Implement proper monitoring
- Set up backup procedures

### 4. Troubleshooting
- Refer to [Troubleshooting Guide](./troubleshooting.md)
- Monitor system health
- Join community channels

## 📚 Additional Resources

- **[Complete Documentation](../README.md)** - Full documentation index
- **[API Reference](../api/core-modules.md)** - Code documentation
- **[Architecture Overview](../architecture/system-overview.md)** - System design
- **[Flow Diagrams](../architecture/flow-diagrams.md)** - Visual workflows

## ⚠️ Important Reminders

- **Start with testnet** - Always test before using real funds
- **Understand risks** - Cryptocurrency trading involves substantial risk
- **Monitor actively** - Keep an eye on bot performance and market conditions
- **Stay updated** - Follow project updates and dYdX announcements
- **Backup configuration** - Keep secure copies of your settings

---

**You're now ready to start exploring automated cryptocurrency trading with the dYdX Trading Bot! 🚀**