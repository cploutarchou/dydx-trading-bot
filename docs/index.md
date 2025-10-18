# 📚 dYdX Trading Bot - Complete Documentation

Welcome to the comprehensive documentation for the dYdX Trading Bot project! This is your central hub for all development, deployment, architecture, and usage information.

## 🚀 Quick Navigation

### **Start Here**

- **[Getting Started](./getting-started.md)** - Setup and first run in 5 minutes
- **[Quick Start Guide](./guides/quick-start.md)** - Step-by-step for different environments

### **Development**

- **[Development Guide](./development.md)** - Local dev environment, testing, code style
- **[Architecture Overview](./architecture/system-overview.md)** - System design and data flow
- **[API Reference](./api/core-modules.md)** - Backend modules and API endpoints

### **Deployment & Operations**

- **[Deployment Guide](./deployment/docker-setup.md)** - Docker, Docker Compose, production setup
- **[Backend Setup](./backend-setup.md)** - FastAPI backend package configuration
- **[Configuration Guide](./guides/configuration.md)** - YAML configuration and environment variables

### **Project Details**

- **[Trading Strategy](./trading/strategy.md)** - Cointegration pairs trading logic
- **[System Architecture](./architecture/flow-diagrams.md)** - Data flow and state management
- **[Database & API](./DATABASE_API_INTEGRATION.md)** - Backend database and API integration
- **[Troubleshooting](./guides/troubleshooting.md)** - Common issues and solutions

---

## 📋 Documentation Structure

```
docs/
├── index.md                      # This file - Documentation hub
├── getting-started.md            # Setup and first run (5 min)
├── development.md                # Development environment and workflow
├── backend-setup.md              # Backend package configuration
│
├── api/
│   └── core-modules.md           # API reference and module documentation
│
├── architecture/
│   ├── system-overview.md        # System design and components
│   ├── flow-diagrams.md          # Data flow and state management
│   └── (flow diagrams and visuals)
│
├── deployment/
│   └── docker-setup.md           # Docker and production deployment
│
├── guides/
│   ├── quick-start.md            # Environment-specific setup
│   ├── configuration.md          # Config.yaml and environment setup
│   ├── development.md            # Dev workflow and best practices
│   └── troubleshooting.md        # Common issues and fixes
│
├── trading/
│   └── strategy.md               # Trading logic and pair strategy
│
├── DATABASE_API_INTEGRATION.md   # Database schema and API design
└── README.md                     # Docs overview
```

---

## 🎯 By Use Case

### **I want to...**

#### **Get the project running locally**

→ [Getting Started](./getting-started.md) (5 min)

#### **Set up for development**

→ [Development Guide](./development.md) + [Dev Container](./guides/quick-start.md#dev-container)

#### **Deploy to production**

→ [Deployment Guide](./deployment/docker-setup.md)

#### **Understand the system design**

→ [Architecture Overview](./architecture/system-overview.md) + [Flow Diagrams](./architecture/flow-diagrams.md)

#### **Configure the trading bot**

→ [Configuration Guide](./guides/configuration.md)

#### **Understand the trading strategy**

→ [Strategy Documentation](./trading/strategy.md)

#### **Debug an issue**

→ [Troubleshooting Guide](./guides/troubleshooting.md)

#### **Integrate with the backend API**

→ [API Reference](./api/core-modules.md) + [Database Integration](./DATABASE_API_INTEGRATION.md)

---

## 📊 Key Components

### **Core Modules**

- **Trading Bot** (`app/`) - Cointegration analysis, position management
- **Backend** (`backend/`) - FastAPI server, database, authentication
- **Frontend** (`frontend/`) - React dashboard for backtest visualization
- **Backtesting** (`app/func_backtesting.py`) - Historical simulation engine

### **Key Features**

✅ **Automated Cointegration Pairs Trading** - Identifies mean-reverting cryptocurrency pairs  
✅ **Statistical Analysis** - Z-score calculations, Johansen cointegration tests  
✅ **Atomic Position Management** - Paired orders executed atomically or rolled back  
✅ **Backtesting Engine** - Historical simulation with performance metrics  
✅ **REST API** - FastAPI backend with Swagger documentation  
✅ **Configuration-First** - All behavior controlled via YAML, no code changes needed  

### **Technology Stack**

- **Backend**: FastAPI 0.104.1, Uvicorn, SQLAlchemy 2.0
- **Frontend**: React 18, Vite 5, Tailwind CSS
- **Trading**: Python 3.12, scipy, statsmodels, pandas
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Deployment**: Docker, Docker Compose, Kubernetes-ready

---

## 🔄 Development Workflow

### **Standard Workflow**

```bash
# 1. Initial setup (one time)
make setup           # Create virtual environment
make install         # Install dependencies
make config          # Create configuration

# 2. Development
make backend-run     # Start backend on port 8000
make run             # Start trading bot

# 3. Testing & Quality
make test            # Run tests
make lint            # Check code quality
make format          # Auto-format code

# 4. Deployment
make docker-build    # Build Docker image
make docker-run      # Run in Docker
```

### **Dev Container Workflow**

```bash
make devcontainer    # Open in VS Code dev container
# Inside container:
make install         # Install all dependencies
make backend-run     # Terminal 1: Backend
make frontend-run    # Terminal 2: Frontend
```

---

## 🐳 Environment Options

| Environment | Setup Time | Use Case | Location |
|-------------|-----------|----------|----------|
| **Local** | 5 min | Quick testing, debugging | Local machine |
| **Dev Container** | 5-10 min | Full development, IDE integration | Docker container in VS Code |
| **Docker** | 3 min | Isolated testing, production-like | Docker container |
| **Docker Compose** | 5 min | Full stack (backend + frontend) | Multiple containers |

See [Quick Start Guide](./guides/quick-start.md) for environment-specific instructions.

---

## 📖 Reading Guide

### **New to the Project?**

1. Start with [Getting Started](./getting-started.md)
2. Read [Trading Strategy](./trading/strategy.md) to understand the bot
3. Explore [Architecture Overview](./architecture/system-overview.md)
4. Review your chosen [Deployment Option](./deployment/docker-setup.md)

### **Developers**

1. Read [Development Guide](./development.md)
2. Understand [System Architecture](./architecture/system-overview.md)
3. Check [API Reference](./api/core-modules.md)
4. Review [Configuration Guide](./guides/configuration.md)

### **DevOps/Deployment**

1. Check [Deployment Guide](./deployment/docker-setup.md)
2. Review [Backend Setup](./backend-setup.md)
3. Read [Configuration Guide](./guides/configuration.md)

### **Troubleshooting**

1. Check [Troubleshooting Guide](./guides/troubleshooting.md)
2. Review relevant section in [Configuration Guide](./guides/configuration.md)
3. Check [Development Guide](./development.md) for environment setup issues

---

## 🔗 External References

### **dYdX v4**

- [dYdX v4 Documentation](https://docs.dydx.trade/)
- [dYdX v4 Testnet](https://testnet.dydx.trade/)

### **Python Libraries**

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Pandas Documentation](https://pandas.pydata.org/)
- [SciPy Documentation](https://scipy.org/)

### **Tools**

- [Docker Documentation](https://docs.docker.com/)
- [VS Code Dev Containers](https://code.visualstudio.com/docs/remote/containers)
- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)

---

## 📝 Key Configuration Files

All configuration is managed through `app/config.yaml`:

```yaml
# Network settings
dydx:
  is_testnet: false
  dydx_chain_address: "..."
  dydx_secret_phrase: "..."

# Trading parameters
botSettings:
  ZScoreThreshold: 1.5
  statsWindow: 21
  usdPerTrade: 10.0
  manageExits: true

# Backtesting
backtesting:
  candleResolution: "1HOUR"
  startingBalance: 1000.0
  transactionFee: 0.0005

# Logging
logging:
  level: "INFO"
  loki:
    enabled: false
```

See [Configuration Guide](./guides/configuration.md) for complete details.

---

## ✅ Verification Checklist

After setup, verify everything works:

```bash
# Backend
curl http://localhost:8000/docs

# Trading Bot (if configured)
make run

# Tests
make test

# Code Quality
make lint
```

---

## 🆘 Need Help?

1. **Setup Issues?** → [Troubleshooting Guide](./guides/troubleshooting.md)
2. **Configuration Questions?** → [Configuration Guide](./guides/configuration.md)
3. **Development Help?** → [Development Guide](./development.md)
4. **Deployment Help?** → [Deployment Guide](./deployment/docker-setup.md)
5. **Strategy Questions?** → [Trading Strategy](./trading/strategy.md)

---

## 🤝 Contributing

This project welcomes contributions! Please:

1. Read the [Development Guide](./development.md)
2. Follow code style guidelines (see `make lint`, `make format`)
3. Add tests for new features
4. Update documentation as needed

---

## 📄 License

See [LICENSE](../LICENSE) file in project root.

---

## 📞 Support

For issues, questions, or contributions:

- Check [Troubleshooting Guide](./guides/troubleshooting.md)
- Review relevant documentation
- Open an issue on GitHub

---

**Last Updated**: October 18, 2025  
**Status**: Complete and Production-Ready ✅
