# dYdX Trading Bot - Setup & Deployment Guide

**Version:** 1.0.0  
**Last Updated:** November 2025  
**Status:** Production Ready

> **🔒 NEW:** This bot now includes **JWT Authentication** system. See [AUTHENTICATION_GUIDE.md](AUTHENTICATION_GUIDE.md) for complete security setup.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Authentication Setup](#authentication-setup)
4. [Configuration](#configuration)
5. [API Server Setup](#api-server-setup)
6. [Starting Your First Bot](#starting-your-first-bot)
7. [Backtesting Workflow](#backtesting-workflow)
8. [Production Deployment](#production-deployment)
9. [Security Best Practices](#security-best-practices)
10. [Monitoring & Maintenance](#monitoring--maintenance)

---

## System Requirements

### Minimum Hardware

- **CPU:** 2 cores
- **RAM:** 4 GB
- **Storage:** 10 GB SSD
- **Network:** Stable internet connection (critical for dYdX connection)

### Software Requirements

- **Python:** 3.10 or higher
- **Database:** SQLite (default) or PostgreSQL
- **OS:** Linux, macOS, or Windows with WSL2

### Verify Requirements

```bash
# Check Python version
python3 --version
# Expected: Python 3.10.0 or higher

# Check pip
pip3 --version

# Check available disk space
df -h /home/chris/workspace/dydx-trading-bot/bot
# Should show at least 10 GB available
```

---

## Installation

### Step 1: Clone and Navigate

```bash
# Navigate to bot directory
cd /home/chris/workspace/dydx-trading-bot/bot

# Verify directory structure
ls -la

# Expected files:
# - bot_api_server.py
# - func_bot_agent.py
# - config.py
# - requirements.txt
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# On Windows (WSL):
# source venv/Scripts/activate

# Verify activation (you should see (venv) in prompt)
which python
# Should show: /path/to/bot/venv/bin/python
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install required packages
pip install -r requirements.txt

# Key packages installed:
# - fastapi==0.120.4
# - uvicorn==0.38.0
# - sqlalchemy==2.0.24
# - pydantic==2.12.3
# - pandas
# - requests
# - websockets
# - python-dotenv

# Verify installation
pip list | grep -E "fastapi|sqlalchemy|pandas"
```

### Step 4: Set Environment Variables

```bash
# Create .env file
cat > .env << 'EOF'
# Database Configuration
DB_TYPE=sqlite
DB_SQLITE_PATH=./trading_bot.db

# Or for PostgreSQL:
# DB_TYPE=postgresql
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=trading_bot
# DB_USER=trading_bot
# DB_PASSWORD=your_password

# API Configuration
API_HOST=0.0.0.0
API_PORT=8889
API_DEBUG=false

# dYdX Configuration
# Set in config.py or via environment
DYDX_NETWORK=testnet
# or mainnet for production

# Telegram (Optional)
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# Logging
LOG_LEVEL=INFO
LOG_FILE=bot.log
EOF

# Verify .env file
cat .env
```

### Step 5: Initialize Database

```bash
# Run Alembic migrations
alembic upgrade head

# Verify database created
ls -lh trading_bot.db

# Check tables
sqlite3 trading_bot.db ".tables"

# Expected tables:
# bot_instances, live_position, live_market_data, etc.
```

---

## Authentication Setup

### Step 1: Initialize Authentication Database

The bot now includes a comprehensive JWT authentication system. Initialize it first:

```bash
# Initialize authentication database and create admin user
python init_auth_db.py
```

Expected output:

```text
============================================================
dYdX Trading Bot - Authentication Database Setup
============================================================
INFO: 🚀 Starting database initialization...
INFO: ✅ Database tables created successfully
INFO: 👤 Creating default admin user...
INFO: ✅ Default admin user created:
INFO:    Username: admin
INFO:    Password: admin123
INFO:    Email: admin@localhost
INFO: ⚠️  IMPORTANT: Change the default password after first login!
============================================================
🎉 SETUP COMPLETE!
============================================================
```

### Step 2: Configure Authentication Environment

Add authentication settings to your `.env` file:

```bash
# Add to .env file
cat >> .env << 'EOF'

# JWT Authentication Configuration
SECRET_KEY=your_super_secure_secret_key_here_32_chars_minimum
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Password & Security
PASSWORD_RESET_TOKEN_EXPIRE_HOURS=1
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=15

# Email Configuration (for 2FA and password reset)
EMAIL_PROVIDER=mailgun
MAILGUN_API_KEY=key-your-mailgun-api-key
MAILGUN_DOMAIN=your-domain.com
MAILGUN_FROM_EMAIL=noreply@your-domain.com

# Alternative: SMTP Configuration
# EMAIL_PROVIDER=smtp
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
# SMTP_FROM_EMAIL=your-email@gmail.com
# SMTP_USE_TLS=true
EOF
```

### Step 3: Generate Secure Secret Key

```bash
# Generate a secure secret key for JWT signing
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# Update your .env file with the generated key
```

### Step 4: Test Authentication Setup

```bash
# Start API server
python start_api.py &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Test login with default credentials
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'

# Should return JWT tokens
# Stop test server
kill $SERVER_PID
```

**⚠️ IMPORTANT SECURITY NOTES:**

1. **Change the default password** immediately after setup
2. **Enable 2FA** for all production users
3. **Use a strong SECRET_KEY** (32+ characters)
4. **Configure email provider** for password reset functionality
5. **Use HTTPS** in production environments

For complete authentication documentation, see [AUTHENTICATION_GUIDE.md](AUTHENTICATION_GUIDE.md).

---

## Configuration

### config.py - Main Configuration

Edit `config.py` to set your trading parameters:

```python
# config.py structure

class BotSettings:
    strategy = "cointegration"              # Trading strategy
    statsWindow = 21                        # Analysis window (days)
    maxHalfLife = 24                        # Max mean reversion (hours)
    zScoreThreshold = 1.5                   # Entry signal threshold
    usdPerTrade = 25.0                      # Position size (USD)
    usdMinCollateral = 100.0                # Min account balance (USD)
    closeAtZScoreCross = True               # Exit on mean reversion

class EnvironmentVariables:
    is_testnet = True                       # Use testnet (True) or mainnet (False)
    abort_all_positions = False             # Close all positions on startup
    find_cointegrated_pairs = True          # Run analysis
    manage_exits = True                     # Monitor positions
    place_trades = True                     # Execute trades

class TelegramNotifications:
    enabled = True
    chat_id = "your_chat_id"
    bot_token = "your_bot_token"
```

### constants.py - Feature Flags

```python
# constants.py - Control bot behavior

ABORT_ALL_POSITIONS = False        # Set True to close all positions on start
FIND_COINTEGRATED = True           # Analyze for pairs
MANAGE_EXITS = True                # Monitor and close positions
PLACE_TRADES = True                # Place new trades
```

### Example Configuration for Different Scenarios

**Conservative Strategy (Low Risk):**

```python
# config.py
statsWindow = 30
zScoreThreshold = 2.0              # Higher threshold = fewer trades
usdPerTrade = 10.0                 # Smaller positions
closeAtZScoreCross = True
```

**Aggressive Strategy (High Volume):**

```python
# config.py
statsWindow = 14
zScoreThreshold = 1.0              # Lower threshold = more trades
usdPerTrade = 100.0                # Larger positions
closeAtZScoreCross = True
```

**Paper Trading (Backtest/Testnet):**

```python
# config.py
is_testnet = True                  # Always use testnet
usdPerTrade = 5.0                  # Minimal size for learning
```

---

## API Server Setup

### Step 1: Start the API Server

```bash
# Navigate to bot directory
cd /home/chris/workspace/dydx-trading-bot/bot

# Activate virtual environment
source venv/bin/activate

# Option 1: Run in foreground (for testing)
python bot_api_server.py

# Expected output:
# INFO:     Uvicorn running on http://0.0.0.0:8889
# INFO:     Application startup complete

# Option 2: Run in background (for production)
nohup python bot_api_server.py > api.log 2>&1 &

# Option 3: Use systemd (recommended for production)
# See "Production Deployment" section
```

### Step 2: Verify API Server

```bash
# Test health endpoint
curl http://localhost:8889/health

# Expected response:
# {"success": true, "message": "API Server is healthy", ...}

# Check system status
curl http://localhost:8889/api/v1/system/status

# List bots (empty initially)
curl http://localhost:8889/api/v1/bots
```

### Step 3: Access API Documentation

Open in browser:

- **Swagger UI:** <http://localhost:8889/docs>
- **ReDoc:** <http://localhost:8889/redoc>

---

## Starting Your First Bot

### Scenario 1: Testnet Trading Bot

**Step 1: Prepare Credentials**

```bash
# You need:
# 1. dYdX testnet address (dydx1...)
# 2. Mnemonic phrase (12-24 words)
# 3. Testnet funds (~$1000 USDC recommended)

# Get testnet funds:
# 1. Go to https://testnet.dydx.trade/
# 2. Sign in with wallet
# 3. Request testnet funds via faucet
```

**Step 2: Create Bot Instance**

```bash
# Save credentials securely
export DYDX_ADDRESS="dydx1a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9"
export DYDX_MNEMONIC="word1 word2 word3 ... word12"

# Create bot via API
curl -X POST http://localhost:8889/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "testnet-bot-01",
    "instance_name": "My First Testnet Bot",
    "credentials": {
      "address": "'"${DYDX_ADDRESS}"'",
      "mnemonic": "'"${DYDX_MNEMONIC}"'"
    },
    "trading_params": {
      "is_testnet": true,
      "zscore_threshold": 1.5,
      "usd_per_trade": 10.0,
      "find_cointegrated_pairs": true,
      "manage_exits": true,
      "place_trades": true
    }
  }'

# Expected response: Bot created with status "stopped"
```

**Step 3: Start Bot**

```bash
# Start trading
curl -X POST http://localhost:8889/api/v1/bots/testnet-bot-01/start

# Check status (should transition: starting -> running)
curl http://localhost:8889/api/v1/bots/testnet-bot-01

# Monitor logs (if running in foreground):
# Watch for messages about:
# - Connecting to dYdX
# - Finding cointegrated pairs
# - Placing trades
```

**Step 4: Monitor Live**

```bash
# Get real-time stats
curl http://localhost:8889/api/v1/bots/testnet-bot-01/stats

# Get trade history
curl http://localhost:8889/api/v1/bots/testnet-bot-01/trades

# Connect to WebSocket for real-time updates
# See API_USAGE_GUIDE.md for WebSocket examples
```

**Step 5: Stop Bot**

```bash
# When ready to stop
curl -X POST http://localhost:8889/api/v1/bots/testnet-bot-01/stop

# Verify stopped
curl http://localhost:8889/api/v1/bots/testnet-bot-01
# status should be "stopped"
```

### Scenario 2: Multiple Bots

```bash
# Create multiple bot instances for different strategies

# Bot 1: Conservative
curl -X POST http://localhost:8889/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "conservative-01",
    "instance_name": "Conservative Strategy",
    "credentials": { "address": "...", "mnemonic": "..." },
    "trading_params": {
      "zscore_threshold": 2.0,
      "usd_per_trade": 10.0,
      "is_testnet": true
    }
  }'

# Bot 2: Aggressive
curl -X POST http://localhost:8889/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "aggressive-01",
    "instance_name": "Aggressive Strategy",
    "credentials": { "address": "...", "mnemonic": "..." },
    "trading_params": {
      "zscore_threshold": 1.0,
      "usd_per_trade": 50.0,
      "is_testnet": true
    }
  }'

# Start both
curl -X POST http://localhost:8889/api/v1/bots/conservative-01/start
curl -X POST http://localhost:8889/api/v1/bots/aggressive-01/start

# Monitor all
curl http://localhost:8889/api/v1/bots
```

---

## Backtesting Workflow

### Step 1: Run Backtest

```bash
# Run backtest for September-October 2025
curl -X POST http://localhost:8889/api/v1/bots/quick-deploy \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "backtest-btc-eth-sep-oct",
    "instance_name": "BTC-ETH Backtest Sep-Oct",
    "strategy_params": {
      "zscore_threshold": 1.5,
      "usd_per_trade": 50.0,
      "stats_window": 21,
      "resolution_timeframe": "1HOUR"
    },
    "backtest_config": {
      "start_date": "2025-09-01",
      "end_date": "2025-10-31",
      "historical_days": 60
    }
  }'
```

### Step 2: Analyze Results

```bash
# Get backtest results
curl http://localhost:8889/api/v1/bots/backtest-btc-eth-sep-oct/stats

# Look for:
# - Win rate > 60%
# - Sharpe ratio > 1.0
# - Max drawdown < -15%
# - Positive total P&L
```

### Step 3: Optimize Parameters

```bash
# Test different threshold
curl -X POST http://localhost:8889/api/v1/bots/quick-deploy \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "backtest-zscore-2",
    "instance_name": "Z-Score 2.0 Test",
    "strategy_params": {
      "zscore_threshold": 2.0,  # Try higher threshold
      "usd_per_trade": 50.0
    },
    "backtest_config": {
      "start_date": "2025-09-01",
      "end_date": "2025-10-31"
    }
  }'

# Compare with previous results and choose best
```

### Step 4: Deploy Best Params

```bash
# Once confident, create live bot with optimized params
curl -X POST http://localhost:8889/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "live-optimized-01",
    "instance_name": "Live Bot - Optimized Params",
    "credentials": { "address": "...", "mnemonic": "..." },
    "trading_params": {
      "is_testnet": true,
      "zscore_threshold": 1.5,    # Your optimized value
      "usd_per_trade": 25.0       # Start smaller for live
    }
  }'
```

---

## Production Deployment

### Step 1: Use systemd for Auto-Start

```bash
# Create systemd service file
sudo tee /etc/systemd/system/dydx-bot.service > /dev/null << 'EOF'
[Unit]
Description=dYdX Trading Bot API
After=network.target

[Service]
Type=simple
User=chris
WorkingDirectory=/home/chris/workspace/dydx-trading-bot/bot
Environment="PATH=/home/chris/workspace/dydx-trading-bot/bot/venv/bin"
ExecStart=/home/chris/workspace/dydx-trading-bot/bot/venv/bin/python bot_api_server.py
Restart=always
RestartSec=10

# Resource limits
MemoryLimit=2G
CPUQuota=80%

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable dydx-bot

# Start service
sudo systemctl start dydx-bot

# Check status
sudo systemctl status dydx-bot

# View logs
sudo journalctl -u dydx-bot -f
```

### Step 2: Configure Reverse Proxy (Nginx)

```bash
# Create Nginx configuration
sudo tee /etc/nginx/sites-available/dydx-bot > /dev/null << 'EOF'
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8889;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/dydx-bot /etc/nginx/sites-enabled/

# Test Nginx config
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### Step 3: Set Up SSL/TLS (Let's Encrypt)

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal (already set up by certbot)
sudo systemctl enable certbot.timer
```

### Step 4: Database Backup

```bash
# Create backup script
cat > backup_db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/chris/workspace/dydx-trading-bot/backups"
mkdir -p $BACKUP_DIR
cp /home/chris/workspace/dydx-trading-bot/bot/trading_bot.db \
   $BACKUP_DIR/trading_bot_$(date +%Y%m%d_%H%M%S).db
# Keep only last 30 days
find $BACKUP_DIR -name "trading_bot_*.db" -mtime +30 -delete
EOF

chmod +x backup_db.sh

# Schedule daily backups
(crontab -l 2>/dev/null; echo "0 2 * * * /home/chris/workspace/dydx-trading-bot/bot/backup_db.sh") | crontab -
```

### Step 5: Monitoring & Alerts

```bash
# Create monitoring script
cat > monitor_bot.py << 'EOF'
import requests
import time

API_URL = "http://localhost:8889"

while True:
    try:
        # Check API health
        health = requests.get(f"{API_URL}/health")
        
        # Check bot status
        bots = requests.get(f"{API_URL}/api/v1/bots")
        
        if health.status_code != 200 or bots.status_code != 200:
            print("ERROR: API not responding")
            # Send alert
        else:
            print(f"✓ API healthy | Bots: {len(bots.json()['data']['instances'])}")
        
        time.sleep(60)  # Check every minute
    
    except Exception as e:
        print(f"Error monitoring bot: {e}")
        time.sleep(60)
EOF

# Run monitoring in background
nohup python3 monitor_bot.py > monitor.log 2>&1 &
```

---

## Security Best Practices

### Authentication Security

**🔐 Change Default Credentials:**

```bash
# Login with default credentials
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Change password immediately
export TOKEN="your_access_token_here"

curl -X POST "http://localhost:8000/auth/change-password" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "admin123",
    "new_password": "your_secure_password_here"
  }'
```

**🔒 Enable Two-Factor Authentication:**

```bash
# Setup 2FA for admin user
curl -X POST "http://localhost:8000/auth/2fa/setup" \
  -H "Authorization: Bearer $TOKEN"

# Scan QR code with authenticator app and verify
curl -X POST "http://localhost:8000/auth/2fa/verify" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"totp_code": "123456"}'
```

**🔑 Secure Environment Variables:**

```bash
# Set restrictive permissions on .env file
chmod 600 .env

# Verify permissions
ls -la .env
# Should show: -rw------- (600)

# For production, use environment variables instead of .env file
export SECRET_KEY="$(openssl rand -hex 32)"
export MAILGUN_API_KEY="key-your-secure-key"
```

### Network Security

**🌐 Use HTTPS in Production:**

```bash
# Generate SSL certificate (Let's Encrypt)
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com

# Update start_api.py to use HTTPS
# Add SSL configuration to uvicorn.run()
```

**🔥 Configure Firewall:**

```bash
# UFW firewall setup
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 443/tcp  # HTTPS
sudo ufw deny 8000/tcp  # Block direct API access from outside
sudo ufw status
```

**🛡️ Reverse Proxy with Nginx:**

```nginx
# /etc/nginx/sites-available/trading-bot
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Rate limiting for auth endpoints
    location /auth/ {
        limit_req zone=auth burst=5 nodelay;
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Database Security

**💾 Database Backup & Encryption:**

```bash
# SQLite backup with encryption
sqlite3 trading_bot.db ".backup trading_bot_backup.db"
gpg --symmetric --cipher-algo AES256 trading_bot_backup.db

# PostgreSQL backup with encryption
pg_dump -U trading_bot trading_bot | gpg --symmetric --cipher-algo AES256 > trading_bot_backup.sql.gpg
```

**🔐 Database Access Control:**

```bash
# SQLite permissions
chmod 600 trading_bot.db
chown www-data:www-data trading_bot.db

# PostgreSQL user permissions
sudo -u postgres psql
CREATE USER trading_bot WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE trading_bot TO trading_bot;
REVOKE ALL ON DATABASE trading_bot FROM PUBLIC;
```

### Monitoring & Alerts

**📊 Security Event Monitoring:**

```bash
# Create security monitoring script
cat > security_monitor.py << 'EOF'
#!/usr/bin/env python3
import requests
import time
import json
from datetime import datetime

def check_auth_logs():
    """Monitor authentication events"""
    try:
        # Check for failed login attempts
        response = requests.get("http://localhost:8000/auth/audit-log",
                              headers={"Authorization": f"Bearer {admin_token}"})
        
        if response.status_code == 200:
            events = response.json()
            failed_logins = [e for e in events if e['event_type'] == 'failed_login']
            
            # Alert if more than 5 failed attempts in last hour
            recent_fails = len([e for e in failed_logins 
                              if e['timestamp'] > datetime.now().timestamp() - 3600])
            
            if recent_fails > 5:
                print(f"SECURITY ALERT: {recent_fails} failed login attempts in last hour")
                # Send alert notification here
                
    except Exception as e:
        print(f"Security monitoring error: {e}")

if __name__ == "__main__":
    admin_token = "your_admin_token_here"
    while True:
        check_auth_logs()
        time.sleep(300)  # Check every 5 minutes
EOF

chmod +x security_monitor.py
```

### Production Checklist

Before deploying to production:

- [ ] **Change default admin password**
- [ ] **Generate secure SECRET_KEY (32+ characters)**
- [ ] **Enable 2FA for all users**
- [ ] **Configure email provider (Mailgun/SMTP)**
- [ ] **Set up HTTPS with valid SSL certificates**
- [ ] **Configure firewall rules**
- [ ] **Set up Nginx reverse proxy**
- [ ] **Enable database backups**
- [ ] **Set up security monitoring**
- [ ] **Test disaster recovery procedures**
- [ ] **Document all credentials securely**

---

## Monitoring & Maintenance

### Daily Checks

```bash
# Check bot status
curl http://localhost:8889/api/v1/bots

# Check for errors
tail -f bot.log | grep ERROR

# Monitor P&L
curl http://localhost:8889/api/v1/bots/testnet-bot-01/stats
```

### Weekly Maintenance

```bash
# Backup database
cp trading_bot.db trading_bot_backup_$(date +%Y%m%d).db

# Check database size
du -h trading_bot.db

# Review backtest results for strategy optimization
```

### Performance Optimization

```bash
# If API is slow, increase memory
# Edit systemd service:
# MemoryLimit=4G

# If database is large, consider PostgreSQL:
# - Better for large datasets
# - Better concurrency
# - Better query optimization

# Clean old data (keep last 90 days):
# DELETE FROM trades WHERE created_at < datetime('now', '-90 days');
```

### Troubleshooting

**API Server Won't Start:**

```bash
# Check if port 8889 is in use
lsof -i :8889

# Check error logs
cat nohup.out

# Verify Python installation
python --version
pip list
```

**Bot Won't Connect to dYdX:**

```bash
# Test dYdX connection
curl https://dydx-testnet.allthatnode.com:1317/health

# Verify network setting (testnet vs mainnet)
grep "is_testnet" config.py

# Check credentials
# Ensure address and mnemonic are correct
```

**Database Locked:**

```bash
# SQLite can get locked, restart service:
sudo systemctl restart dydx-bot

# Or switch to PostgreSQL for production
```

---

## Quick Reference

### File Locations

```
/home/chris/workspace/dydx-trading-bot/bot/
├── bot_api_server.py          # Main API server
├── config.py                  # Configuration file
├── constants.py               # Feature flags
├── trading_bot.db             # SQLite database
├── bot.log                    # Bot activity logs
├── api.log                    # API server logs
└── .env                       # Environment variables
```

### Useful Commands

```bash
# Start API
python bot_api_server.py

# List all bots
curl http://localhost:8889/api/v1/bots

# Start specific bot
curl -X POST http://localhost:8889/api/v1/bots/{instance_id}/start

# Stop specific bot
curl -X POST http://localhost:8889/api/v1/bots/{instance_id}/stop

# Get bot stats
curl http://localhost:8889/api/v1/bots/{instance_id}/stats

# Access API docs
# Open http://localhost:8889/docs in browser
```

### Environment Variables

```bash
# In .env file
API_HOST=0.0.0.0
API_PORT=8889
DB_TYPE=sqlite
DB_SQLITE_PATH=./trading_bot.db
DYDX_NETWORK=testnet
LOG_LEVEL=INFO
```

---

## Next Steps

1. **Complete Setup:** Follow "Starting Your First Bot" section
2. **Explore API:** Visit <http://localhost:8889/docs>
3. **Run Backtest:** Test strategy before live trading
4. **Monitor Bot:** Use WebSocket or stats endpoints
5. **Optimize:** Adjust parameters based on results
6. **Deploy:** Use systemd for production

---

## Support

- **API Documentation:** See `API_USAGE_GUIDE.md`
- **Real-Time Data:** See `REALTIME_SYSTEM.md`
- **Troubleshooting:** See section above

**Last Updated:** November 2, 2025  
**Ready to start?** Follow the "Starting Your First Bot" section!
