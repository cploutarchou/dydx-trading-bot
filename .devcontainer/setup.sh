#!/bin/bash

# dYdX Trading Bot - Development Container Setup Script
# This script sets up the complete development environment

set -e

echo "🚀 Setting up dYdX Trading Bot development environment..."

# First, fix permissions if running as root
if [ "$EUID" -eq 0 ] && [ -f ".devcontainer/fix-permissions.sh" ]; then
    echo "🔧 Fixing permissions for dev container..."
    chmod +x .devcontainer/fix-permissions.sh
    ./.devcontainer/fix-permissions.sh "$(pwd)" vscode
fi

# Update system packages
echo "📦 Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Install additional system dependencies
echo "🔧 Installing system dependencies..."
sudo apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    vim \
    tree \
    htop \
    jq \
    make \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev

# Python Development Tools
echo "🐍 Setting up Python development tools..."

# Upgrade pip and install wheel
pip install --upgrade pip setuptools wheel

# Install development requirements
if [ -f "requirements-dev.txt" ]; then
    echo "📋 Installing development requirements..."
    pip install -r requirements-dev.txt
else
    echo "⚠️  requirements-dev.txt not found, installing basic dev tools..."
    pip install pytest black flake8 mypy isort pylint bandit ipython
fi

# Install main project requirements
if [ -f "requirements.txt" ]; then
    echo "📋 Installing project requirements..."
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt not found, skipping project dependencies..."
fi

# Setup pre-commit hooks (if available)
if command -v pre-commit &> /dev/null; then
    echo "🎣 Setting up pre-commit hooks..."
    if [ -f ".pre-commit-config.yaml" ]; then
        pre-commit install
    else
        echo "⚠️  .pre-commit-config.yaml not found, skipping pre-commit setup..."
    fi
fi

# Setup Git configuration
echo "📝 Setting up Git configuration..."
git config --global core.editor "code --wait"
git config --global init.defaultBranch main
git config --global pull.rebase false

# Create useful aliases
echo "⚡ Setting up development aliases..."
cat >> ~/.bashrc << 'EOF'

# dYdX Trading Bot Development Aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

# Python Development
alias py='python'
alias pip='python -m pip'
alias pytest='python -m pytest'
alias black='python -m black'
alias isort='python -m isort'
alias flake8='python -m flake8'
alias mypy='python -m mypy'

# dYdX Bot Specific
alias bot='cd /workspaces/dydx-trading-bot'
alias botrun='cd /workspaces/dydx-trading-bot && python app/main.py'
alias bottest='cd /workspaces/dydx-trading-bot && python -m pytest tests/'
alias botlint='cd /workspaces/dydx-trading-bot && make lint'
alias botformat='cd /workspaces/dydx-trading-bot && make format'

# Docker helpers
alias dps='docker ps'
alias dimg='docker images'
alias dlogs='docker logs'

EOF

# Create development workspace structure
echo "📁 Setting up workspace structure..."
mkdir -p /workspaces/dydx-trading-bot/{.vscode,docs,scripts,tests,logs}

# Setup VS Code workspace settings (if not exists)
if [ ! -f ".vscode/settings.json" ]; then
    echo "⚙️  Creating VS Code workspace settings..."
    mkdir -p .vscode
    cat > .vscode/settings.json << 'EOF'
{
    "python.defaultInterpreterPath": "/usr/local/bin/python",
    "python.analysis.typeCheckingMode": "strict",
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.linting.flake8Enabled": true,
    "python.testing.pytestEnabled": true,
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        "**/node_modules": true,
        "**/.git": false
    }
}
EOF
fi

# Setup launch configuration for debugging
if [ ! -f ".vscode/launch.json" ]; then
    echo "🐛 Creating VS Code debug configuration..."
    cat > .vscode/launch.json << 'EOF'
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "dYdX Trading Bot",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/app/main.py",
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            },
            "justMyCode": true
        },
        {
            "name": "Run Tests",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "args": ["tests/", "-v"],
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}",
            "justMyCode": false
        },
        {
            "name": "Fast Cointegration Script",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/scripts/fast_cointegration.py",
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}",
            "args": ["--n", "50"]
        }
    ]
}
EOF
fi

# Create useful development scripts
echo "📜 Creating development helper scripts..."

# Quick setup script
cat > /usr/local/bin/bot-setup << 'EOF'
#!/bin/bash
echo "🔧 dYdX Bot Quick Setup"
cd /workspaces/dydx-trading-bot
if [ -f "Makefile" ]; then
    make setup install config
else
    echo "⚠️  Makefile not found, running manual setup..."
    pip install -r requirements.txt
    python -c "
import yaml, os
config_template = {
    'botSettings': {
        'ZScoreThreshold': 1.5,
        'statsWindow': 21,
        'maxHalfLife': 24,
        'usdPerTrade': 10.0,
        'usdMinCollateral': 100.0,
        'closeAtZscoreCross': True,
        'abortAllPositions': False,
        'findCointegratedPairs': True,
        'manageExits': True,
        'placeTrades': False
    },
    'dydx': {
        'account_address': 'YOUR_ACCOUNT_ADDRESS_HERE',
        'mnemonic': 'YOUR_MNEMONIC_PHRASE_HERE'
    },
    'telegram': {
        'token': 'YOUR_BOT_TOKEN_HERE',
        'channel': 'YOUR_CHANNEL_ID_HERE',
        'enabled': False
    },
    'logging': {
        'level': 'INFO',
        'loki_url': '',
        'loki_username': '',
        'loki_password': ''
    },
    'is_testnet': True,
    'environment': 'development'
}
with open('app/config.yaml', 'w') as f:
    yaml.dump(config_template, f, default_flow_style=False)
print('✅ Created config.yaml template')
"
fi
echo "✅ Setup complete!"
EOF
chmod +x /usr/local/bin/bot-setup

# Development status checker
cat > /usr/local/bin/bot-status << 'EOF'
#!/bin/bash
echo "📊 dYdX Trading Bot - Development Status"
echo "========================================"

cd /workspaces/dydx-trading-bot

echo "🐍 Python Environment:"
python --version
pip --version
echo

echo "📦 Installed Packages (key ones):"
pip list | grep -E "(dydx|pytest|black|flake8|mypy)" || echo "  No key packages found"
echo

echo "📁 Project Structure:"
tree -L 2 -I "__pycache__|*.pyc" . 2>/dev/null || ls -la
echo

echo "🧪 Test Status:"
if [ -d "tests" ]; then
    echo "  Tests directory: ✅ Found"
    test_count=$(find tests -name "*.py" -not -name "__init__.py" | wc -l)
    echo "  Test files: $test_count"
else
    echo "  Tests directory: ❌ Not found"
fi

echo

echo "⚙️  Configuration:"
if [ -f "app/config.yaml" ]; then
    echo "  config.yaml: ✅ Found"
else
    echo "  config.yaml: ❌ Not found (run 'bot-setup')"
fi

if [ -f "requirements.txt" ]; then
    echo "  requirements.txt: ✅ Found"
else
    echo "  requirements.txt: ❌ Not found"
fi

echo

echo "🔧 Available Commands:"
echo "  bot-setup     - Quick project setup"
echo "  bot-status    - Show this status"
echo "  make run      - Start the trading bot"
echo "  make test     - Run test suite"
echo "  make lint     - Run linting"
echo "  make format   - Format code"
EOF
chmod +x /usr/local/bin/bot-status

# Create development environment info
echo "📋 Creating environment info..."
cat > /workspaces/dydx-trading-bot/DEV_ENVIRONMENT.md << 'EOF'
# dYdX Trading Bot - Development Environment

## 🛠️ Installed Tools

### Core Development
- **Python**: 3.12+ with pip, setuptools, wheel
- **Git**: Version control with GitHub CLI
- **Docker**: Container support with Docker-in-Docker
- **Node.js**: 18.x for additional tooling

### Python Development Tools
- **Testing**: pytest, pytest-cov, pytest-mock, pytest-asyncio
- **Code Quality**: black, isort, flake8, pylint, mypy, bandit
- **Debugging**: ipython, ipdb
- **Documentation**: sphinx, markdown support
- **Jupyter**: For data analysis and research

### VS Code Extensions
- Python extension pack (Python, Pylint, Black, etc.)
- Jupyter notebooks support
- GitLens for enhanced Git integration
- Docker extension for container management
- GitHub Copilot for AI assistance

## 🚀 Quick Start Commands

```bash
# Setup the project
bot-setup

# Check environment status
bot-status

# Start development
cd /workspaces/dydx-trading-bot
make setup install config

# Run the bot
make run

# Run tests
make test

# Code formatting & linting
make format
make lint
```

## 📁 Container Features

- **Persistent storage**: Your workspace is mounted and preserved
- **Port forwarding**: Development servers (8000, 8080, 9000, 3100)
- **Git integration**: Pre-configured with GitHub CLI
- **Docker support**: Build and run containers from within the container
- **Python environment**: Optimized for Python 3.12 development

## 🔧 Development Workflow

1. **Code**: Use VS Code with full IntelliSense and debugging
2. **Test**: Run `pytest` with coverage reporting
3. **Format**: Auto-format with Black and isort on save
4. **Lint**: Check code quality with flake8, pylint, mypy
5. **Commit**: Git integration with GitLens
6. **Deploy**: Docker support for containerized deployment

## 📊 Available Aliases

```bash
# Navigation
ll, la, l          # Enhanced ls commands
.., ...           # Directory navigation

# Python
py                # python
pytest            # python -m pytest  
black, isort      # Code formatters
flake8, mypy      # Linters

# dYdX Bot Specific
bot               # cd to project directory
botrun            # Run the trading bot
bottest           # Run test suite
botlint           # Run linting
botformat         # Format code

# Docker
dps               # docker ps
dimg              # docker images
dlogs             # docker logs
```

## 🐛 Debugging

The container includes VS Code launch configurations for:
- **dYdX Trading Bot**: Debug the main application
- **Run Tests**: Debug test suite
- **Fast Cointegration**: Debug analysis scripts

## 📝 Notes

- All Python packages are installed in the container
- The workspace is mounted to `/workspaces/dydx-trading-bot`
- Git credentials are inherited from your host system
- Container user is `vscode` with sudo privileges
EOF

echo
echo "✅ Development container setup complete!"
echo
echo "🎉 dYdX Trading Bot Development Environment Ready!"
echo
echo "📚 Next Steps:"
echo "   1. Run 'bot-setup' to configure the project"
echo "   2. Run 'bot-status' to check the environment"
echo "   3. Open VS Code and start developing!"
echo
echo "🔗 Useful Commands:"
echo "   • bot-setup     - Quick project setup"
echo "   • bot-status    - Environment status check"
echo "   • make run      - Start the trading bot"
echo "   • make test     - Run tests"
echo
echo "Happy coding! 🚀"