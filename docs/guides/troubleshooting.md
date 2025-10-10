# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the dYdX Trading Bot.

## 🚨 Quick Diagnostics

### Health Check Commands

```bash
# 1. Check configuration
python app/test_config.py

# 2. Test dYdX connectivity
cd app && python -c "import asyncio; from func_connections import connect_dydx; asyncio.run(connect_dydx())"

# 3. Verify account access
cd app && python -c "import asyncio; from func_private import get_account; from func_connections import connect_dydx; asyncio.run(get_account(await connect_dydx()))"

# 4. Check log files
tail -f app/logs/trading_bot.log  # if logging to file

# 5. Validate state files
ls -la app/bot_agents.json app/cointegrated_pairs.csv
```

### System Status

```bash
# Check system requirements
python --version    # Should be 3.12+
pip list | grep -E "(dydx|pandas|numpy|statsmodels)"

# Check disk space
df -h .

# Check network connectivity  
curl -s https://indexer.dydx.trade/v4/markets | jq .
```

## ❌ Common Errors

### Configuration Errors

#### Error: "Configuration could not be loaded"
```
RuntimeError: Configuration could not be loaded
```

**Causes & Solutions:**

1. **Missing config.yaml**
   ```bash
   # Solution: Generate configuration template
   make config
   # Then edit app/config.yaml with your settings
   ```

2. **Invalid YAML syntax**
   ```bash
   # Check YAML syntax
   python -c "import yaml; print(yaml.safe_load(open('app/config.yaml')))"
   
   # Common issues:
   # - Missing quotes around tokens with special characters
   # - Incorrect indentation (use spaces, not tabs)
   # - Unescaped colons in values
   ```

3. **Missing required fields**
   ```yaml
   # Ensure all required fields are present:
   dydx:
     dydx_chain_address: "dydx1..."  # Required
     dydx_chain_secret: "word1 word2..."  # Required
   telegram:
     token: "123456:ABC..."  # Required
     chat_id: "123456"  # Required
   ```

#### Error: "dydx_testnet configuration is missing"
```
RuntimeError: dydx_testnet configuration is missing
```

**Solutions:**

1. **Use unified configuration (recommended)**:
   ```yaml
   is_testnet: true
   dydx:
     dydx_chain_address: "your-address"
     dydx_chain_secret: "your-mnemonic"
   ```

2. **Or use separate testnet configuration**:
   ```yaml
   is_testnet: true
   dydx_testnet:
     dydx_chain_address: "testnet-address"
     dydx_chain_secret: "testnet-mnemonic"
   ```

### Connection Errors

#### Error: "Failed to connect to client"
```
Error connecting to client: HTTPStatusError('403 Client Error: Forbidden')
```

**Causes & Solutions:**

1. **Geographic Restriction (HTTP 403)**
   ```
   FAILED: LOCATION ACCESS LIKELY PROHIBITED
   DYDX likely prohibits use from your country
   ```
   
   **Solutions:**
   - Check dYdX's [supported regions](https://dydx.exchange/terms)
   - For educational purposes only, consider VPN usage (not financial advice)
   - Use testnet which may have different restrictions

2. **Network Connectivity Issues**
   ```bash
   # Test basic connectivity
   curl -v https://indexer.dydx.trade/v4/markets
   
   # Check DNS resolution
   nslookup indexer.dydx.trade
   
   # Test with different endpoint
   curl -v https://indexer.v4testnet.dydx.exchange/v4/markets
   ```

3. **API Rate Limiting**
   ```
   HTTPStatusError('429 Too Many Requests')
   ```
   
   **Solutions:**
   - Wait 60 seconds before retrying
   - Check if multiple bot instances are running
   - Verify API call delays in code (should be 0.2-0.5s)

#### Error: "Wallet derivation failed"
```
Failed to derive wallet for address dydx1...
```

**Causes & Solutions:**

1. **Invalid Mnemonic Phrase**
   ```bash
   # Verify mnemonic has 12-24 words
   echo "word1 word2 word3..." | wc -w
   
   # Check for typos in mnemonic
   # Ensure proper spacing between words
   # No extra characters or punctuation
   ```

2. **Address Mismatch**
   ```bash
   # Verify address corresponds to mnemonic
   # Check if using testnet vs mainnet address format
   # Testnet addresses should start with 'dydx1'
   ```

3. **Network Configuration**
   ```yaml
   # Ensure network settings match your account
   is_testnet: true  # for testnet addresses
   # or
   is_testnet: false  # for mainnet addresses
   ```

### Trading Errors

#### Error: "No cointegrated pairs found"
```
INFO: Cointegrated pairs successfully saved
INFO: Loaded 0 cointegrated pairs
```

**Causes & Solutions:**

1. **Insufficient Price Data**
   ```bash
   # Check if markets are active
   cd app && python -c "
   import asyncio
   from func_public import get_markets, connect_dydx
   async def check():
       client = await connect_dydx()
       markets = await get_markets(client)
       active = [k for k,v in markets['markets'].items() if v['status'] == 'ACTIVE']
       print(f'Active markets: {len(active)}')
   asyncio.run(check())
   "
   ```

2. **Statistical Criteria Too Strict**
   ```yaml
   # Relax cointegration parameters
   botSettings:
     maxHalfLife: 48  # Increase from 24 hours
     ZScoreThreshold: 1.0  # Decrease from 1.5
   ```

3. **Market Conditions**
   ```bash
   # Check recent market volatility
   # High correlation periods may reduce cointegration opportunities
   # Try running analysis during different market sessions
   ```

#### Error: "Insufficient collateral"
```
Account balance below minimum required
```

**Solutions:**

1. **Check Account Balance**
   ```bash
   cd app && python -c "
   import asyncio
   from func_private import get_account
   from func_connections import connect_dydx
   async def check():
       client = await connect_dydx()
       account = await get_account(client)
       print(f'Account balance: {account}')
   asyncio.run(check())
   "
   ```

2. **Adjust Minimum Collateral**
   ```yaml
   botSettings:
     usdMinCollateral: 50.0  # Reduce from 100.0
     usdPerTrade: 5.0  # Reduce from 10.0
   ```

3. **Fund Account**
   - Testnet: Use faucet to get test tokens
   - Mainnet: Deposit funds to your dYdX account

#### Error: "Order failed to fill"
```
Market 1 BTC-USD failed to fill
```

**Causes & Solutions:**

1. **Price Movement During Execution**
   ```yaml
   # Market orders with bounds may fail in volatile conditions
   # This is protective behavior to prevent bad fills
   ```

2. **Insufficient Liquidity**
   ```bash
   # Check market depth
   # Avoid trading very small or illiquid markets
   # Consider increasing position sizes for better fills
   ```

3. **Exchange Issues**
   ```bash
   # Check dYdX status page
   # Wait and retry during normal market conditions
   # Monitor dYdX Discord/Twitter for known issues
   ```

### State Management Errors

#### Error: "Position mismatch detected"
```
Position exists locally but not on exchange
```

**Solutions:**

1. **State Reconciliation**
   ```bash
   # The bot automatically reconciles differences
   # Check logs for reconciliation actions
   # Verify bot_agents.json reflects current state
   ```

2. **Manual State Reset**
   ```bash
   # Backup current state
   cp app/bot_agents.json app/bot_agents.json.backup
   
   # Clear state (bot will reconcile on restart)
   echo "[]" > app/bot_agents.json
   
   # Restart bot to reconcile with exchange
   ```

3. **Force Close All Positions**
   ```yaml
   # Emergency position closure
   botSettings:
     abortAllPositions: true
   ```

#### Error: "Cannot write to bot_agents.json"
```
PermissionError: [Errno 13] Permission denied: 'bot_agents.json'
```

**Solutions:**

1. **File Permissions**
   ```bash
   # Fix file permissions
   chmod 644 app/bot_agents.json
   chown $USER app/bot_agents.json
   ```

2. **Directory Permissions**
   ```bash
   # Ensure app directory is writable
   chmod 755 app/
   cd app && ls -la bot_agents.json
   ```

3. **File Lock Issues**
   ```bash
   # Check if file is locked by another process
   lsof app/bot_agents.json
   
   # Kill any zombie processes
   pkill -f "python.*main.py"
   ```

## 🔍 Debugging Workflows

### Enable Debug Logging

```yaml
# app/config.yaml
logging:
  level: "DEBUG"  # Change from INFO
```

### Step-by-Step Debugging

1. **Isolate the Problem**
   ```bash
   # Test each component individually
   
   # 1. Configuration
   python -c "from app.config import config; print('Config:', config())"
   
   # 2. Connection
   cd app && python -c "import asyncio; from func_connections import connect_dydx; asyncio.run(connect_dydx())"
   
   # 3. Market data
   cd app && python -c "
   import asyncio
   from func_connections import connect_dydx
   from func_public import get_markets
   async def test():
       client = await connect_dydx()
       markets = await get_markets(client)
       print(f'Markets: {len(markets[\"markets\"])}')
   asyncio.run(test())
   "
   
   # 4. Account access
   cd app && python -c "
   import asyncio
   from func_connections import connect_dydx
   from func_private import get_account
   async def test():
       client = await connect_dydx()
       account = await get_account(client)
       print(f'Account: {account}')
   asyncio.run(test())
   "
   ```

2. **Cointegration Analysis Debug**
   ```bash
   # Run cointegration analysis separately
   cd app && python -c "
   import asyncio
   from func_connections import connect_dydx
   from func_public import construct_market_prices
   from func_cointegration import store_cointegration_results
   
   async def debug_coint():
       client = await connect_dydx()
       print('Fetching market prices...')
       df = await construct_market_prices(client)
       print(f'Price matrix shape: {df.shape}')
       
       print('Running cointegration analysis...')
       result = store_cointegration_results(df)
       print(f'Result: {result}')
       
       # Check results
       import pandas as pd
       try:
           pairs = pd.read_csv('cointegrated_pairs.csv')
           print(f'Found {len(pairs)} cointegrated pairs')
           if len(pairs) > 0:
               print(pairs.head())
       except FileNotFoundError:
           print('No cointegrated_pairs.csv found')
   
   asyncio.run(debug_coint())
   "
   ```

3. **Order Execution Debug**
   ```bash
   # Test order placement (use small amounts!)
   cd app && python test.py
   ```

### Log Analysis

#### Extract Specific Errors
```bash
# Search for error patterns
grep -i "error\|exception\|failed" app/logs/*.log

# Check connection issues
grep -i "connection\|403\|timeout" app/logs/*.log

# Monitor real-time logs
tail -f app/logs/trading_bot.log | grep -E "(ERROR|CRITICAL|WARNING)"
```

#### Performance Analysis
```bash
# Check execution times
grep -i "took\|duration\|seconds" app/logs/*.log

# Memory usage patterns
grep -i "memory\|ram\|allocation" app/logs/*.log
```

## 🛠️ System Diagnostics

### Performance Issues

#### High CPU Usage
```bash
# Monitor Python processes
top -p $(pgrep -f "python.*main.py")

# Check for infinite loops
strace -p $(pgrep -f "python.*main.py") -e trace=all

# Profile the application
python -m cProfile app/main.py > profile.txt
```

#### Memory Leaks
```bash
# Monitor memory usage over time
while true; do
    ps aux --pid=$(pgrep -f "python.*main.py") --format=pid,pcpu,pmem,comm
    sleep 60
done

# Check for large DataFrames in memory
# Review cointegration analysis for memory cleanup
```

#### Network Issues
```bash
# Monitor network connections
netstat -an | grep -E "(dydx|indexer)"

# Check DNS resolution
dig indexer.dydx.trade
dig indexer.v4testnet.dydx.exchange

# Test with different DNS servers
nslookup indexer.dydx.trade 8.8.8.8
```

### Environment Issues

#### Python Environment
```bash
# Check Python version and packages
python --version
pip list | grep -E "(dydx|pandas|numpy|scipy|statsmodels)"

# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Virtual environment issues
deactivate && source .venv/bin/activate
```

#### System Dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-dev build-essential

# macOS
xcode-select --install
brew install python@3.12

# Check for missing system libraries
ldd $(python -c "import numpy; print(numpy.__file__)")
```

## 🔧 Recovery Procedures

### Emergency Stop

```bash
# Method 1: Graceful shutdown
pkill -SIGTERM -f "python.*main.py"

# Method 2: Force stop
pkill -SIGKILL -f "python.*main.py"

# Method 3: Emergency position closure
cd app && python -c "
import asyncio
from func_connections import connect_dydx
from func_private import abort_all_positions

async def emergency_stop():
    client = await connect_dydx()
    await abort_all_positions(client)
    print('All positions closed')

asyncio.run(emergency_stop())
"
```

### State Recovery

#### Reset Trading State
```bash
# Backup existing state
cp app/bot_agents.json app/bot_agents.json.$(date +%Y%m%d_%H%M%S)

# Reset to empty state
echo "[]" > app/bot_agents.json

# Clear cointegration results (will regenerate)
rm -f app/cointegrated_pairs.csv
```

#### Restore from Backup
```bash
# List available backups
ls -la app/bot_agents.json.*

# Restore specific backup
cp app/bot_agents.json.20241009_120000 app/bot_agents.json
```

### Configuration Recovery

#### Reset Configuration
```bash
# Backup current config
cp app/config.yaml app/config.yaml.backup

# Generate fresh template
make config

# Merge settings from backup
# Edit app/config.yaml with your specific values
```

#### Validate Configuration
```bash
# Test configuration loading
python -c "
from app.config import config
try:
    cfg = config()
    print('✅ Configuration valid')
    print(f'Environment: {cfg.environment}')
    print(f'Is testnet: {cfg.is_testnet}')
except Exception as e:
    print(f'❌ Configuration error: {e}')
"
```

## 📞 Getting Help

### Information to Collect

When seeking help, provide:

1. **Error Messages**
   ```bash
   # Collect recent logs
   tail -100 app/logs/trading_bot.log > error_logs.txt
   ```

2. **System Information**
   ```bash
   # System details
   uname -a
   python --version
   pip list | grep -E "(dydx|pandas|numpy)" > package_versions.txt
   ```

3. **Configuration (sanitized)**
   ```bash
   # Remove sensitive data before sharing
   cp app/config.yaml config_sanitized.yaml
   # Edit config_sanitized.yaml to remove secrets
   ```

4. **State Information**
   ```bash
   # Current state
   ls -la app/bot_agents.json app/cointegrated_pairs.csv
   wc -l app/bot_agents.json app/cointegrated_pairs.csv
   ```

### Community Resources

- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check latest docs for updates
- **Discord/Telegram**: Community support channels
- **dYdX Official**: Check status pages and announcements

### Professional Support

For production deployments:
- Consider professional monitoring services
- Implement automated alerting systems
- Regular backup and disaster recovery procedures
- Performance monitoring and optimization

## 🔄 Maintenance Procedures

### Regular Health Checks

```bash
#!/bin/bash
# health_check.sh - Run daily

echo "=== dYdX Bot Health Check ===" 
echo "Date: $(date)"

# Check if bot is running
if pgrep -f "python.*main.py" > /dev/null; then
    echo "✅ Bot is running"
else
    echo "❌ Bot is not running"
fi

# Check log file size
LOG_SIZE=$(du -h app/logs/trading_bot.log 2>/dev/null | cut -f1)
echo "Log file size: ${LOG_SIZE:-'No log file'}"

# Check state files
if [ -f "app/bot_agents.json" ]; then
    POSITIONS=$(jq length app/bot_agents.json 2>/dev/null || echo "invalid")
    echo "Active positions: $POSITIONS"
else
    echo "No bot_agents.json found"
fi

# Check configuration
if python -c "from app.config import config; config()" 2>/dev/null; then
    echo "✅ Configuration valid"
else
    echo "❌ Configuration invalid"
fi

echo "=========================="
```

### Log Rotation

```bash
# Rotate logs to prevent disk space issues
logrotate_config="
/path/to/dydx-trading-bot/app/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 $(whoami) $(whoami)
}
"

# Add to system logrotate
echo "$logrotate_config" | sudo tee /etc/logrotate.d/dydx-bot
```

This comprehensive troubleshooting guide covers the most common issues and provides systematic approaches to diagnosing and resolving problems with the dYdX Trading Bot.