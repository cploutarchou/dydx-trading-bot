# dYdX Trading Bot - API-Controlled Multi-Instance System

## 🎯 Overview

Successfully transformed the dYdX trading bot into a **multi-instance, API-controlled system** that allows:

- 🚀 **API Control**: Start/stop bots via REST API calls
- 🔄 **Multi-Instance Support**: Run multiple bots simultaneously with isolated configurations  
- ⚙️ **Dynamic Configuration**: Trading parameters sent via API payload (not stored in .env)
- 🌐 **Web Interface**: FastAPI server with automatic documentation
- 🏗️ **Proper Architecture**: Separated static vs dynamic configuration

## 📁 Project Structure

```
bot/
├── 📄 API System
│   ├── bot_api_server.py          # FastAPI server with REST endpoints
│   ├── bot_api_models.py          # Pydantic models for API validation
│   └── bot_instance_manager.py    # Multi-instance management
│
├── 🔧 Configuration
│   ├── .env                       # Static environment variables
│   ├── example.env               # Template with all variables
│   └── config.py                 # Configuration management
│
├── 🤖 Bot Core (Original Files)
│   ├── main.py                   # Original single-instance bot
│   ├── main_instance.py          # Instance-aware bot (WIP)
│   ├── func_*.py                # Trading logic functions
│   └── constants.py             # Trading constants
│
├── 🚀 Startup Scripts
│   ├── start_api.py             # API server startup
│   ├── run_api.sh              # Bash script to start API
│   └── requirements.txt         # Python dependencies
│
├── 📚 Documentation  
│   └── .github/copilot-instructions.md  # AI coding agent instructions
│
└── 📊 Runtime Data
    └── pair_history/           # Historical trading pair data
```

## 🔑 Key Features

### 1. JWT Authentication & Security

- **🔐 JWT-based Authentication** - Secure API access with Bearer tokens
- **🔑 2FA Support** - TOTP and email verification for enhanced security
- **👤 User Management** - Admin and user roles with proper access control
- **📧 Email Integration** - Mailgun/SMTP support for notifications and verification
- **🛡️ Password Security** - Secure password hashing and reset functionality
- **🚫 Rate Limiting** - Protection against brute force attacks

### 2. API-Controlled Bot Management

- **POST /bots** - Create new bot instance (🔒 Authenticated)
- **GET /bots** - List all bot instances (🔒 Authenticated)
- **GET /bots/{bot_id}** - Get specific bot status (🔒 Authenticated)
- **POST /bots/{bot_id}/start** - Start bot instance (🔒 Authenticated)
- **POST /bots/{bot_id}/stop** - Stop bot instance (🔒 Authenticated)
- **DELETE /bots/{bot_id}** - Remove bot instance (🔒 Authenticated)
- **POST /bots/quick-deploy** - One-click bot deployment (🔒 Authenticated)

### 3. Multi-Instance Architecture

- Each bot runs as separate process with unique ID
- Isolated state files: `bot_agents_{instance_id}.json`
- Independent configuration and logging
- Process-level isolation for stability

### 4. Configuration Management

**Static (.env file):**

```bash
# Authentication & Security
SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email Configuration (for 2FA and notifications)
EMAIL_PROVIDER=mailgun  # or 'smtp'
MAILGUN_API_KEY=your_mailgun_api_key
MAILGUN_DOMAIN=your_domain.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Telegram notifications
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Infrastructure settings  
LOG_LEVEL=INFO
LOG_FILE=bot_{instance_id}.log
```

**Dynamic (API payload):**

```json
{
  "credentials": {
    "stark_private_key": "0x...",
    "dydx_private_key": "0x...", 
    "wallet_address": "0x..."
  },
  "trading_params": {
    "is_testnet": true,
    "usd_per_trade": 100,
    "zscore_threshold": 1.5,
    "strategy": "statistical_arbitrage"
  },
  "bot_settings": {
    "abort_all_positions": false,
    "find_cointegrated_pairs": true,
    "manage_exits": true,
    "place_trades": true
  }
}
```

## 🚀 Quick Start

### 1. Set Up Authentication

```bash
# Initialize authentication database and create admin user
source venv/bin/activate
python init_auth_db.py
```

**Default Admin Credentials:**

- Username: `admin`
- Password: `admin123`
- Email: `admin@localhost`

⚠️ **Important:** Change the default password immediately after first login!

### 2. Start the API Server

```bash
# Method 1: Using the startup script
./run_api.sh

# Method 2: Manual activation
source venv/bin/activate
python start_api.py
```

### 3. Access the API

- **API Docs with Authentication**: <http://localhost:8000/docs>
- **Health Check (Public)**: <http://localhost:8000/health>

### 4. Authenticate in Swagger UI

1. Open <http://localhost:8000/docs>
2. Click **"Authorize"** button (🔒 icon)
3. Login using `/auth/login` endpoint with admin credentials
4. Copy the `access_token` from the response
5. In the authorization dialog, enter: `Bearer <your_access_token>`
6. Click "Authorize" - now all endpoints are accessible!

### 5. Deploy a Bot Instance

```bash
curl -X POST "http://localhost:8000/bots/quick-deploy" \
  -H "Content-Type: application/json" \
  -d '{
    "credentials": {
      "stark_private_key": "0x...",
      "dydx_private_key": "0x...",
      "wallet_address": "0x..."
    },
    "trading_params": {
      "is_testnet": true,
      "usd_per_trade": 100,
      "zscore_threshold": 1.5
    }
  }'
```

## 📊 API Endpoints Reference

### 🔐 Authentication Endpoints (Public)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login with username/password |
| POST | `/auth/logout` | Logout and invalidate token |
| POST | `/auth/register` | Register new user (admin only) |
| POST | `/auth/refresh` | Refresh access token |
| GET | `/auth/profile` | Get current user profile |
| PUT | `/auth/profile` | Update user profile |

### 🔑 Password & 2FA Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/change-password` | Change password (with 2FA) |
| POST | `/auth/forgot-password` | Request password reset |
| POST | `/auth/reset-password` | Reset password with token |
| POST | `/auth/2fa/setup` | Setup TOTP 2FA |
| POST | `/auth/2fa/verify` | Verify TOTP code |
| POST | `/auth/2fa/request-email-verification` | Request email verification |
| POST | `/auth/2fa/verify-email` | Verify email with code |

### 🤖 Bot Management (🔒 Authenticated)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/bots` | List all bot instances |
| POST | `/api/v1/bots` | Create new bot instance |
| GET | `/api/v1/bots/{bot_id}` | Get bot status |
| POST | `/api/v1/bots/{bot_id}/start` | Start specific bot |
| POST | `/api/v1/bots/{bot_id}/stop` | Stop specific bot |
| DELETE | `/api/v1/bots/{bot_id}` | Delete bot instance |

### ⚡ Quick Actions (🔒 Authenticated)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/bots/quick-deploy` | Deploy and start bot in one call |
| GET | `/api/v1/system/status` | Overall system status |

### 📊 Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | API server health check (Public) |
| GET | `/api/v1/bots/{bot_id}/history` | Get bot event history (🔒 Auth) |
| GET | `/api/v1/bots/{bot_id}/trades` | Get bot trades (🔒 Auth) |
| GET | `/api/v1/bots/{bot_id}/stats` | Get bot statistics (🔒 Auth) |

## 🔧 Environment Configuration

### Required Environment Variables

**Static Configuration (.env):**

```bash
# Telegram Settings (Optional)
TELEGRAM_TOKEN=              # Telegram bot token for notifications
TELEGRAM_CHAT_ID=           # Chat ID for notifications

# Logging Settings
LOG_LEVEL=INFO              # Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_FILE=bot_{instance_id}.log  # Log file pattern

# File Paths (Support {instance_id} placeholder)
BOT_AGENTS_FILE=bot_agents_{instance_id}.json
BOT_PAIRS_FILE=cointegrated_pairs_{instance_id}.json

# Database Settings (if using database)
DATABASE_URL=               # Database connection string
```

**Dynamic Configuration (API):**

```json
{
  "credentials": {
    "stark_private_key": "Required - dYdX Stark private key",
    "dydx_private_key": "Required - dYdX private key", 
    "wallet_address": "Required - Wallet address"
  },
  "trading_params": {
    "is_testnet": true,        // Use testnet (true) or mainnet (false)
    "usd_per_trade": 100,      // USD amount per trade
    "zscore_threshold": 1.5,   // Z-score threshold for entries
    "max_half_life": 24,       // Maximum cointegration half-life
    "strategy": "statistical_arbitrage"  // Trading strategy
  },
  "bot_settings": {
    "abort_all_positions": false,      // Close positions on startup
    "find_cointegrated_pairs": true,   // Run cointegration analysis
    "manage_exits": true,              // Manage existing positions
    "place_trades": true               // Place new trades
  }
}
```

## 🔄 Development Workflow

### Adding New Features

1. **API Changes**: Update `bot_api_models.py` and `bot_api_server.py`
2. **Bot Logic**: Modify functions in `func_*.py` files
3. **Configuration**: Add new settings to models
4. **Testing**: Use `/docs` endpoint for API testing

### Running Multiple Bots

```python
# Bot 1: Conservative strategy
{
  "trading_params": {
    "usd_per_trade": 50,
    "zscore_threshold": 2.0
  }
}

# Bot 2: Aggressive strategy  
{
  "trading_params": {
    "usd_per_trade": 200,
    "zscore_threshold": 1.0
  }
}
```

## 🛡️ Security Features

### 🔐 Authentication & Authorization

1. **JWT Security**: Industry-standard JWT tokens with configurable expiration
2. **Password Security**: bcrypt hashing with salt for password storage
3. **2FA Protection**: TOTP and email-based two-factor authentication
4. **Rate Limiting**: Built-in protection against brute force attacks
5. **Account Lockout**: Automatic lockout after failed login attempts
6. **Token Management**: Secure token blacklisting and refresh mechanisms

### 🔒 API Security

1. **Bearer Authentication**: All protected endpoints require valid JWT tokens
2. **Role-based Access**: Admin and user roles with appropriate permissions
3. **Request Validation**: Pydantic models ensure data validation
4. **CORS Configuration**: Configurable cross-origin resource sharing

### 📧 Email Security

1. **Email Verification**: Required for password resets and 2FA
2. **Secure Templates**: Professional HTML email templates
3. **Provider Support**: Mailgun API and SMTP support
4. **Rate Limiting**: Email sending rate limits to prevent abuse

### 🔑 Environment Security

1. **Credentials Management**: Secure storage of sensitive configuration
2. **Secret Key**: Configurable JWT secret key for token signing
3. **Environment Separation**: Different .env files for different environments
4. **Process Isolation**: Each bot runs in separate process for security

### ⚠️ Security Best Practices

1. **Change Default Password**: Immediately change admin password after setup
2. **Enable 2FA**: Always enable two-factor authentication for production
3. **Secure Secret Key**: Use a strong, unique SECRET_KEY in production
4. **HTTPS Only**: Always use HTTPS in production environments
5. **Regular Updates**: Keep dependencies updated for security patches

## 📈 Monitoring & Logging

- **Instance Logs**: Each bot has separate log file with instance ID
- **API Logs**: FastAPI server logs all requests  
- **Telegram Alerts**: Real-time notifications for bot events
- **Process Monitoring**: psutil integration for system resource monitoring

## 🔮 Future Enhancements

- [ ] Web-based dashboard UI
- [ ] Authentication and authorization
- [ ] Database integration for persistent storage
- [ ] Real-time WebSocket updates
- [ ] Performance metrics and analytics
- [ ] Automated scaling based on market conditions
- [ ] Strategy backtesting integration

## 📝 Notes

- **Type Safety**: Pydantic models ensure API data validation
- **Error Handling**: Comprehensive error handling with meaningful messages
- **Scalability**: Architecture supports horizontal scaling
- **Maintainability**: Clean separation of concerns and modular design

---

**🎉 Ready to run multiple dYdX trading bots simultaneously with full API control!**
