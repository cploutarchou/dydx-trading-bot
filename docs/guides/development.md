# Development Guide

This guide covers development workflows, testing procedures, contribution guidelines, and code standards for the dYdX Trading Bot.

## 🛠️ Development Environment Setup

### Prerequisites

- Python 3.12 or higher
- Git for version control
- Docker & Docker Compose (optional but recommended)
- VS Code or PyCharm (recommended IDEs)

### Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd dydx-trading-bot

# Set up virtual environment
make setup

# Install dependencies including dev tools
make install

# Create configuration
make config
# Edit app/config.yaml with your development settings

# Verify installation
make test
```

### Development Dependencies

The development environment includes additional tools:

```bash
# Code formatting and linting
black                 # Code formatter
isort                 # Import sorter
flake8                # Linting
pylint                # Advanced linting
mypy                  # Type checking
bandit                # Security analysis

# Testing
pytest                # Testing framework
pytest-cov            # Coverage reporting
pytest-asyncio        # Async test support

# Development utilities
pre-commit            # Git hooks
jupyter               # Notebooks for analysis
```

## 📋 Project Structure

```
dydx-trading-bot/
├── app/                          # Main application code
│   ├── main.py                   # Entry point and main loop
│   ├── config.py                 # Configuration management
│   ├── constants.py              # Configuration-derived constants
│   ├── func_connections.py       # dYdX client management
│   ├── func_cointegration.py     # Statistical analysis
│   ├── func_entry_pairs.py       # Trade entry logic
│   ├── func_exit_pairs.py        # Trade exit logic
│   ├── func_bot_agent.py         # Order execution state machine
│   ├── func_private.py           # Private API operations
│   ├── func_public.py            # Public API operations
│   ├── func_messaging.py         # Telegram notifications
│   ├── func_utils.py             # Utility functions
│   ├── logging_setup.py          # Logging configuration
│   ├── test.py                   # Manual testing script
│   └── config.yaml               # Configuration file
├── docs/                         # Documentation
│   ├── README.md                 # Documentation index
│   ├── architecture/             # System architecture docs
│   ├── api/                      # API documentation
│   ├── deployment/               # Deployment guides
│   ├── guides/                   # User guides
│   └── trading/                  # Trading strategy docs
├── scripts/                      # Utility scripts
│   ├── close_open_positions.py   # Emergency position closure
│   ├── fast_cointegration.py     # Quick cointegration scan
│   └── manage_bot.sh             # Bot management script
├── tests/                        # Test suite
│   ├── test_config.py            # Configuration tests
│   ├── test_cointegration.py     # Strategy tests
│   └── conftest.py               # Pytest configuration
├── .github/                      # GitHub workflows
│   ├── workflows/ci.yml          # CI/CD pipeline
│   └── copilot-instructions.md   # AI agent instructions
├── docker-compose.yml            # Docker orchestration
├── Dockerfile                    # Container image
├── Makefile                      # Development automation
├── requirements.txt              # Python dependencies
├── .gitignore                    # Git ignore patterns
├── .dockerignore                 # Docker ignore patterns
└── README.md                     # Project overview
```

## 🔧 Development Workflows

### Code Development Cycle

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Implement Changes**
   ```bash
   # Make your changes
   # Follow coding standards (see below)
   ```

3. **Test Changes**
   ```bash
   make test           # Run full test suite
   make lint           # Check code quality
   make format         # Auto-format code
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/new-feature
   # Create pull request on GitHub
   ```

### Available Make Commands

#### Development Commands
```bash
make setup          # Create virtual environment
make install        # Install dependencies + dev tools
make config         # Generate configuration template
make run            # Run the bot
make test           # Run test suite with coverage
make lint           # Run all linters (flake8, pylint, mypy, bandit)
make format         # Format code (black + isort)
make clean          # Remove generated files
```

#### Docker Commands
```bash
make docker-build         # Build production image
make docker-build-dev     # Build development image
make docker-run          # Run container
make docker-stop         # Stop container
make docker-logs         # View container logs
make docker-shell        # Interactive shell in container
make docker-dev          # Development container
make docker-test         # Run tests in container
make docker-clean        # Remove all Docker resources
```

#### Docker Compose Commands
```bash
make docker-up           # Start with docker-compose
make docker-up-dev       # Start development environment
make docker-up-logging   # Start with monitoring stack
make docker-down         # Stop all services
make docker-compose-logs # View all service logs
```

### Pre-commit Hooks

Set up pre-commit hooks for consistent code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## 🧪 Testing

### Test Structure

```
tests/
├── conftest.py                   # Pytest configuration and fixtures
├── test_config.py               # Configuration system tests
├── test_cointegration.py        # Statistical analysis tests
├── test_connections.py          # dYdX client tests (integration)
├── test_bot_agent.py           # Order execution tests
└── test_utils.py               # Utility function tests
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_config.py -v

# Run specific test function
pytest tests/test_config.py::test_load_config -v

# Run with coverage report
pytest --cov=app tests/ --cov-report=html

# Run tests in parallel
pytest -n auto tests/

# Run only fast tests (skip integration)
pytest -m "not integration" tests/
```

### Test Categories

#### Unit Tests
```python
# test_config.py - Configuration system
def test_load_valid_config():
    """Test loading valid YAML configuration."""
    
def test_invalid_config_raises_error():
    """Test that invalid config raises appropriate error."""

# test_cointegration.py - Statistical functions
def test_calculate_zscore():
    """Test Z-score calculation with known values."""
    
def test_cointegration_detection():
    """Test cointegration detection algorithm."""
```

#### Integration Tests
```python
# test_connections.py - dYdX API integration
@pytest.mark.integration
async def test_connect_dydx():
    """Test connecting to dYdX exchange."""
    
@pytest.mark.integration  
async def test_get_markets():
    """Test fetching market data from dYdX."""
```

#### Mock Tests
```python
# test_bot_agent.py - Order execution with mocking
@pytest.fixture
def mock_client():
    """Mock dYdX client for testing."""
    
def test_bot_agent_order_sequence(mock_client):
    """Test BotAgent order execution sequence."""
```

### Test Configuration

```python
# conftest.py - Pytest configuration
import pytest
import asyncio
from unittest.mock import MagicMock

@pytest.fixture
def mock_config():
    """Provide mock configuration for tests."""
    return {
        "is_testnet": True,
        "dydx": {
            "dydx_chain_address": "dydx1test...",
            "dydx_chain_secret": "test mnemonic..."
        }
    }

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()
```

### Testing Best Practices

1. **Test Isolation**: Each test should be independent
2. **Mock External Dependencies**: Use mocks for dYdX API calls
3. **Test Edge Cases**: Invalid inputs, network failures, etc.
4. **Async Testing**: Properly handle async/await patterns
5. **Coverage Goals**: Aim for >80% code coverage

## 📏 Code Standards

### Python Style Guide

The project follows PEP 8 with additional conventions:

#### Code Formatting
- **Line Length**: 88 characters (Black default)
- **Indentation**: 4 spaces (no tabs)
- **String Quotes**: Double quotes preferred
- **Import Organization**: isort with Black profile

#### Naming Conventions
```python
# Variables and functions: snake_case
user_account_balance = 100.0
async def calculate_zscore(spread_data):
    pass

# Classes: PascalCase
class BotAgent:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_POSITION_SIZE = 1000.0

# Private methods: leading underscore
def _validate_config(self, config):
    pass
```

#### Type Hints
```python
from typing import List, Dict, Optional, Union, Tuple
import asyncio

# Function signatures with type hints
async def get_account(client: Client) -> Dict[str, Any]:
    """Get account information from dYdX."""
    
def calculate_cointegration(
    series_1: List[float], 
    series_2: List[float]
) -> Tuple[int, float, float]:
    """Calculate cointegration between two series."""
```

### Documentation Standards

#### Docstring Format
```python
def calculate_zscore(spread: List[float]) -> pd.Series:
    """
    Calculate rolling Z-score for spread series.
    
    Args:
        spread: Price spread series for Z-score calculation
    
    Returns:
        pd.Series: Rolling Z-score values with configurable window
    
    Raises:
        ValueError: If spread data is insufficient for calculation
        
    Example:
        >>> spread = [1.0, 1.5, 0.8, 2.0, 1.2]
        >>> zscore = calculate_zscore(spread)
        >>> print(zscore.iloc[-1])  # Latest Z-score
    """
```

#### Code Comments
```python
# Business logic comments explain WHY
# Spread too high: short base, long quote (mean reversion expected)
if zscore > threshold:
    base_side = "SELL"
    quote_side = "BUY"

# Technical comments explain HOW for complex operations
# Use Engle-Granger two-step method for cointegration testing
coint_res = coint(series_1, series_2)
```

### Error Handling Patterns

#### Custom Exceptions
```python
class SmartError(Exception):
    """Custom exception for statistical calculation errors."""
    pass

class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass
```

#### Error Handling Best Practices
```python
async def robust_api_call(client, operation):
    """Example of robust error handling."""
    try:
        result = await operation(client)
        return result
    except HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.error("Geographic restriction detected")
            raise ConnectionError("Access prohibited") from e
        elif e.response.status_code == 429:
            logger.warning("Rate limit hit, waiting...")
            await asyncio.sleep(60)
            raise
        else:
            logger.exception("Unexpected HTTP error")
            raise
    except Exception as e:
        logger.exception("Unexpected error in API call")
        raise
```

### Logging Standards

```python
import logging

# Module-level logger
logger = logging.getLogger(__name__)

# Logging levels and usage
logger.debug("Detailed diagnostic information")
logger.info("General information about program execution")
logger.warning("Something unexpected but not critical")
logger.error("Error that caused operation to fail")
logger.critical("Serious error that may cause program to terminate")

# Structured logging with context
logger.info(
    "Trade executed successfully",
    extra={
        "market": "BTC-USD",
        "side": "BUY", 
        "size": 0.01,
        "price": 45000.0
    }
)
```

## 🔧 Code Quality Tools

### Linting Configuration

#### Flake8 (.flake8)
```ini
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = .git,__pycache__,.venv,build,dist
```

#### Pylint (.pylintrc)
```ini
[MESSAGES CONTROL]
disable = C0330, C0326, R0903, R0913

[FORMAT]
max-line-length = 88
```

#### MyPy (pyproject.toml)
```toml
[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
```

#### Bandit (for security)
```bash
# Check for security issues
bandit -r app/ -f json -o security_report.json
```

### Automated Code Formatting

#### Black Configuration
```toml
[tool.black]
line-length = 88
target-version = ['py312']
include = '\.pyi?$'
```

#### isort Configuration  
```toml
[tool.isort]
profile = "black"
line_length = 88
multi_line_output = 3
```

## 🤝 Contributing Guidelines

### Pull Request Process

1. **Fork and Branch**
   ```bash
   git checkout -b feature/descriptive-name
   ```

2. **Follow Standards**
   - Code follows style guide
   - Tests are included
   - Documentation is updated
   - Commit messages are descriptive

3. **Test Thoroughly**
   ```bash
   make test lint        # Ensure all checks pass
   make docker-test      # Test in container environment
   ```

4. **Create Pull Request**
   - Clear description of changes
   - Reference related issues
   - Include test results

5. **Review Process**
   - Code review by maintainers
   - CI/CD pipeline must pass
   - Documentation review

### Commit Message Format

```bash
# Format: type(scope): description
feat(config): add support for multiple dYdX environments
fix(bot-agent): handle partial order fills correctly
docs(readme): update quick start instructions
test(cointegration): add edge case tests for zero variance
refactor(connections): simplify client initialization
```

### Issue Reporting

#### Bug Reports
```markdown
## Bug Report

**Description**: Brief description of the bug

**Environment**:
- Python version: 3.12.x
- dYdX Trading Bot version: vX.X.X
- Operating System: Ubuntu 22.04

**Steps to Reproduce**:
1. Configure bot with...
2. Run command...
3. Observe error...

**Expected Behavior**: What should happen

**Actual Behavior**: What actually happens

**Logs**: Include relevant log excerpts

**Additional Context**: Any other relevant information
```

#### Feature Requests
```markdown
## Feature Request

**Summary**: Brief description of the feature

**Motivation**: Why is this feature needed?

**Detailed Description**: How should it work?

**Alternatives**: Other approaches considered

**Additional Context**: Implementation ideas, examples
```

### Code Review Guidelines

#### For Authors
- Keep changes focused and atomic
- Write clear commit messages
- Include comprehensive tests
- Update documentation
- Respond promptly to feedback

#### For Reviewers
- Focus on code quality and design
- Check for security issues
- Verify test coverage
- Ensure documentation accuracy
- Provide constructive feedback

## 🚀 Release Process

### Version Management

The project uses semantic versioning (SemVer):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. **Pre-release**
   ```bash
   # Update version numbers
   # Update CHANGELOG.md
   # Run full test suite
   make test lint
   make docker-test
   ```

2. **Create Release**
   ```bash
   git tag -a v1.2.3 -m "Release version 1.2.3"
   git push origin v1.2.3
   ```

3. **Build and Publish**
   ```bash
   # Build Docker images
   make docker-build
   
   # Tag for registry
   docker tag dydx-trading-bot:latest registry/dydx-trading-bot:v1.2.3
   
   # Push to registry
   docker push registry/dydx-trading-bot:v1.2.3
   ```

4. **Post-release**
   - Update documentation
   - Announce release
   - Monitor for issues

## 🔍 Debugging Workflows

### Local Debugging

#### VS Code Configuration (.vscode/launch.json)
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug dYdX Bot",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/app/main.py",
            "cwd": "${workspaceFolder}/app",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            },
            "console": "integratedTerminal"
        }
    ]
}
```

#### PyCharm Configuration
- Set working directory to `app/`
- Add `PYTHONPATH` environment variable
- Enable asyncio debugging

### Remote Debugging

#### Docker Debug Container
```bash
# Run development container with debug support
make docker-dev

# Inside container, install debug tools
pip install debugpy

# Start bot with debugger
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client main.py
```

#### Production Debugging
```bash
# Enable debug logging
# Update config.yaml:
logging:
  level: "DEBUG"

# Restart bot and collect logs
make docker-logs > debug.log
```

### Performance Profiling

```python
# Profile specific functions
import cProfile
import pstats

def profile_cointegration():
    pr = cProfile.Profile()
    pr.enable()
    
    # Run cointegration analysis
    result = store_cointegration_results(df)
    
    pr.disable()
    stats = pstats.Stats(pr)
    stats.sort_stats('cumulative')
    stats.print_stats(10)

# Memory profiling
import tracemalloc

tracemalloc.start()
# Run bot operations
current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
```

## 📊 Development Metrics

### Code Quality Metrics
- **Code Coverage**: Aim for >80%
- **Cyclomatic Complexity**: Keep functions under 10
- **Line Count**: Functions under 50 lines
- **Documentation Coverage**: All public APIs documented

### Performance Metrics
- **Startup Time**: < 30 seconds
- **Memory Usage**: < 512MB steady state
- **API Response Time**: < 5 seconds average
- **Error Rate**: < 1% of operations

### Monitoring During Development

```bash
# Monitor resource usage
top -p $(pgrep -f "python.*main.py")

# Check memory leaks
valgrind --tool=memcheck python app/main.py

# Network monitoring
netstat -an | grep -E "(dydx|indexer)"

# Log analysis
tail -f app/logs/*.log | grep -E "(ERROR|WARNING)"
```

This comprehensive development guide provides the foundation for contributing to and maintaining the dYdX Trading Bot effectively. Follow these guidelines to ensure code quality, consistency, and maintainability.