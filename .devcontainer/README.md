# 🐳 dYdX Trading Bot - Development Container

This development container provides a complete Python development environment for the dYdX Trading Bot with all necessary tools, extensions, and configurations.

## 🚀 Quick Start

### Option 1: VS Code Dev Containers (Recommended)

1. **Prerequisites:**
   - Install [VS Code](https://code.visualstudio.com/)
   - Install [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
   - Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

2. **Launch Development Environment:**
   ```bash
   # Clone the repository
   git clone https://github.com/cploutarchou/dydx-trading-bot.git
   cd dydx-trading-bot
   
   # Open in VS Code
   code .
   
   # VS Code will prompt to "Reopen in Container" - click it!
   # Or use Ctrl/Cmd+Shift+P → "Dev Containers: Rebuild and Reopen in Container"
   ```

3. **First Setup:**
   ```bash
   # Inside the dev container terminal
   bot-setup
   bot-status
   ```

### Option 2: Docker Compose

```bash
# Build and run the development environment
cd .devcontainer
docker-compose up -d devcontainer

# Access the container
docker-compose exec devcontainer bash

# Setup the project
bot-setup
```

### Option 3: Standalone Docker

```bash
# Build the development image
docker build -f .devcontainer/Dockerfile -t dydx-trading-bot-dev .

# Run the container
docker run -it -v $(pwd):/workspace -p 8000:8000 dydx-trading-bot-dev

# Setup inside container
bot-setup
```

## 🛠️ What's Included

### Core Development Tools
- **Python 3.12** - Latest stable Python with pip, setuptools, wheel
- **Git** - Version control with GitHub CLI integration
- **Docker** - Container support with Docker-in-Docker capability
- **Node.js 18** - For additional tooling and package management

### Python Development Stack
```bash
# Testing Framework
pytest>=7.4.0          # Main testing framework
pytest-cov>=4.1.0      # Coverage reporting
pytest-mock>=3.11.1    # Mocking utilities
pytest-asyncio>=0.21.0 # Async testing support

# Code Quality Tools
black>=23.7.0           # Code formatter
isort>=5.12.0          # Import sorter
flake8>=6.0.0          # Linting
pylint>=2.17.0         # Advanced linting
mypy>=1.5.0            # Static type checking
bandit>=1.7.5          # Security analysis

# Development Utilities
ipython>=8.14.0        # Enhanced Python shell
ipdb>=0.13.13          # Debugging
pre-commit>=3.3.0      # Git hooks
```

### VS Code Extensions (Auto-installed)
- **Python Extension Pack** - Complete Python development suite
- **Jupyter** - Notebook support for data analysis
- **GitLens** - Enhanced Git integration
- **GitHub Copilot** - AI-powered code assistance
- **Docker** - Container management
- **Pylint, Black, isort** - Code quality tools
- **Test Explorer** - Visual test running
- **Markdown** - Documentation support

### Pre-configured Features
- **Auto-formatting** on save (Black + isort)
- **Linting** with flake8, pylint, mypy, bandit
- **Testing** with pytest and coverage reporting
- **Debugging** with VS Code integrated debugger
- **Git hooks** with pre-commit for code quality
- **IntelliSense** with type checking and auto-completion

## 📁 Container Structure

```
/workspaces/dydx-trading-bot/     # Your project (mounted from host)
├── .devcontainer/                # Container configuration
├── .vscode/                      # VS Code settings & launch configs
├── app/                          # Main application code
├── tests/                        # Test suite
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
└── .pre-commit-config.yaml      # Code quality hooks
```

## 🔧 Available Commands

### Quick Setup & Status
```bash
bot-setup      # Quick project configuration
bot-status     # Show development environment status
```

### Development Workflow
```bash
# Project management
make setup install config    # Full project setup
make run                     # Start the trading bot
make test                    # Run test suite with coverage
make lint                    # Run all linting tools
make format                  # Format code with Black + isort

# Testing & Quality
pytest tests/               # Run tests
pytest --cov=app           # Run with coverage
black .                    # Format code
isort .                    # Sort imports
flake8 .                   # Lint code
mypy app/                  # Type checking
bandit -r app/             # Security scanning

# Git workflow
pre-commit run --all-files # Run pre-commit hooks
git add . && git commit    # Auto-formatting on commit
```

### Python Development Aliases
```bash
# Navigation
ll, la, l      # Enhanced directory listings
.., ...        # Quick directory navigation

# Python shortcuts
py             # python
pytest         # python -m pytest
black          # python -m black
isort          # python -m isort

# dYdX Bot specific
bot            # cd to project directory
botrun         # Run the trading bot
bottest        # Run test suite
botlint        # Run linting
botformat      # Format code

# Docker helpers  
dps            # docker ps
dimg           # docker images
dlogs          # docker logs
```

## 🐛 Debugging

### VS Code Debug Configurations
The container includes pre-configured launch settings:

1. **dYdX Trading Bot** - Debug the main application
2. **Run Tests** - Debug the test suite  
3. **Fast Cointegration** - Debug analysis scripts

### Interactive Debugging
```bash
# Use ipdb for debugging
import ipdb; ipdb.set_trace()

# Or use VS Code breakpoints
# Set breakpoints in the editor and use F5 to start debugging
```

## 🧪 Testing Environment

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v tests/

# Run tests in parallel
pytest -n auto tests/
```

### Test Coverage
- HTML reports generated in `htmlcov/`
- Terminal coverage summary displayed
- Coverage badges available for README

## 📊 Optional Services

The Docker Compose setup includes optional services for advanced development:

### Database (PostgreSQL)
```bash
# Enable database service
docker-compose --profile with-db up -d postgres-dev

# Access: localhost:5432
# User: dydx_user / Password: dev_password
```

### Caching (Redis)
```bash
# Enable Redis service  
docker-compose --profile with-redis up -d redis-dev

# Access: localhost:6379
```

### Monitoring Stack
```bash
# Enable monitoring services
docker-compose --profile with-monitoring up -d grafana-dev loki-dev

# Grafana: http://localhost:3000 (admin/dev123)
# Loki: http://localhost:3100
```

## 🔐 Security Features

### Pre-commit Security Scanning
- **Bandit** - Python security linting
- **Safety** - Dependency vulnerability scanning
- **Secret detection** - Prevents committing secrets

### Container Security
- **Non-root user** - Container runs as `vscode` user
- **Sudo access** - Available for system administration
- **Isolated network** - Services run in dedicated Docker network

## 🌐 Port Forwarding

The development container exposes these ports:
- **8000** - Development server
- **8080** - Alternative web server
- **3000** - Grafana dashboard (optional)
- **3100** - Loki logs (optional)
- **5432** - PostgreSQL (optional)
- **6379** - Redis (optional)

## 📝 Configuration Files

### Container Configuration
- **`.devcontainer/devcontainer.json`** - Main container configuration
- **`.devcontainer/Dockerfile`** - Custom container image
- **`.devcontainer/docker-compose.yml`** - Multi-service setup

### Development Configuration
- **`.vscode/settings.json`** - VS Code workspace settings
- **`.vscode/launch.json`** - Debug configurations
- **`.pre-commit-config.yaml`** - Git hooks configuration
- **`requirements-dev.txt`** - Development dependencies

## 🔄 Workflow Integration

### Git Integration
- **GitLens** - Enhanced Git visualization
- **GitHub CLI** - Command-line GitHub operations
- **Pre-commit hooks** - Automatic code quality checks
- **Commit message templates** - Consistent commit formatting

### CI/CD Ready
The development environment mirrors production:
- Same Python version and dependencies
- Same linting and testing tools  
- Same code formatting standards
- Docker containerization support

## 🆘 Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check Docker is running
docker info

# Rebuild container
docker-compose build --no-cache devcontainer
```

**Python packages not found:**
```bash
# Reinstall dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Check Python path
echo $PYTHONPATH
```

**VS Code extensions not working:**
```bash
# Reload window
Ctrl/Cmd+Shift+P → "Developer: Reload Window"

# Rebuild container  
Ctrl/Cmd+Shift+P → "Dev Containers: Rebuild Container"
```

**Permission issues / Unable to write file:**
```bash
# Fix file permissions automatically
sudo .devcontainer/fix-permissions.sh $(pwd) vscode

# Or manually fix permissions
sudo chown -R vscode:vscode /workspaces/dydx-trading-bot
sudo chmod -R 755 /workspaces/dydx-trading-bot

# Switch to vscode user if needed
su - vscode
cd /workspaces/dydx-trading-bot
```

**"Unable to write file 'vscode-remote://...' errors:**
This typically happens when VS Code is running as a different user than expected.
```bash
# Run the permission fix script
sudo .devcontainer/fix-permissions.sh $(pwd) vscode

# Reload VS Code window
# Ctrl/Cmd+Shift+P → "Developer: Reload Window"

# Or restart the dev container
# Ctrl/Cmd+Shift+P → "Dev Containers: Rebuild Container"
```

### Getting Help
- Check `bot-status` for environment information
- Review container logs: `docker-compose logs devcontainer`
- VS Code command palette: `Ctrl/Cmd+Shift+P`
- Container terminal: `Ctrl+Shift+`` (backtick)

## 🎯 Next Steps

1. **Start Development:**
   ```bash
   bot-setup              # Configure the project
   make setup install     # Install dependencies  
   make config           # Create configuration
   ```

2. **Run the Bot:**
   ```bash
   make run              # Start trading bot
   ```

3. **Development Workflow:**
   ```bash
   # Make changes to code
   make test             # Run tests
   make lint             # Check code quality
   git add . && git commit   # Auto-format and commit
   ```

4. **Advanced Features:**
   ```bash
   # Enable monitoring
   docker-compose --profile with-monitoring up -d
   
   # Open Grafana dashboard
   open http://localhost:3000
   ```

## 🎉 Happy Coding!

Your complete dYdX Trading Bot development environment is ready! The container provides everything you need for professional Python development with automated testing, linting, formatting, and debugging capabilities.

**Key Features:**
- ✅ **Complete Python 3.12 environment**
- ✅ **All development tools pre-installed**  
- ✅ **VS Code fully configured**
- ✅ **Automated code quality checks**
- ✅ **Integrated testing and debugging**
- ✅ **Docker containerization support**
- ✅ **Git workflow integration**

Start coding and let the container handle the development environment! 🚀