# Core Modules API Documentation

This document provides comprehensive API documentation for all core modules in the dYdX Trading Bot.

## 📋 Module Overview

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `config.py` | Configuration management | `ConfigurationManager`, `BotSettings` |
| `constants.py` | Global constants | Configuration-derived constants |
| `func_connections.py` | dYdX client management | `Client`, `connect_dydx()` |
| `func_cointegration.py` | Statistical analysis | `calculate_cointegration()`, `calculate_zscore()` |
| `func_entry_pairs.py` | Trade entry logic | `open_positions()` |
| `func_exit_pairs.py` | Trade exit logic | `manage_trade_exits()` |
| `func_bot_agent.py` | Order execution | `BotAgent` |
| `func_private.py` | Private API operations | Order management functions |
| `func_public.py` | Public API operations | Market data functions |
| `func_messaging.py` | Notifications | `send_message()` |
| `func_utils.py` | Utility functions | Helper functions |
| `logging_setup.py` | Logging configuration | `setup_logging()` |
| `main.py` | Main execution | `main()` |

---

## 🔧 config.py

### ConfigurationManager
Singleton configuration manager with type-safe dataclass hierarchy.

```python
class ConfigurationManager:
    """Singleton configuration manager for YAML-based configuration."""
    
    def __init__(self, config_file: str = "config.yaml"):
        """Initialize configuration manager."""
    
    def load_config(self) -> Configuration:
        """Load and validate configuration from YAML file."""
    
    def _validate_config(self, config: Configuration) -> None:
        """Validate configuration constraints and requirements."""
```

### Configuration Dataclasses

```python
@dataclass
class TelegramSettings:
    token: str = ""
    chat_id: str = ""

@dataclass
class DydxSettings:
    dydx_chain_address: str = ""
    dydx_chain_secret: str = ""

@dataclass
class BotSettings:
    abortAllPositions: bool = False
    findCointegratedPairs: bool = False
    manageExits: bool = False
    placeTrades: bool = False
    resolutionTimeframe: str = "1HOUR"
    strategy: str = "cointegration"
    statsWindow: int = 21
    maxHalfLife: int = 24
    ZScoreThreshold: float = 1.5
    usdPerTrade: float = 10.0
    usdMinCollateral: float = 100.0
    closeAtZscoreCross: bool = True
    indexer_endpoint: IndexerEndpoint = field(default_factory=lambda: IndexerEndpoint())
```

### Usage Example
```python
from config import config

# Get configuration instance
cfg = config()

# Access configuration values
is_testnet = cfg.is_testnet
trade_amount = cfg.botSettings.usdPerTrade
telegram_token = cfg.telegram.token
```

---

## 🌐 func_connections.py

### Client Class
Wrapper class for dYdX v4 client components.

```python
class Client:
    """Wrapper for dYdX v4 client components."""
    
    def __init__(self, indexer, indexer_account, node, wallet):
        self.indexer = indexer          # Market data client
        self.indexer_account = indexer_account  # Account data client
        self.node = node                # Order submission client
        self.wallet = wallet            # Wallet for signing
```

### Connection Functions

```python
async def connect_dydx() -> Client:
    """
    Initialize and connect all dYdX client components.
    
    Returns:
        Client: Connected client instance with all components
    
    Raises:
        ConnectionError: If any client fails to initialize
        Exception: For jurisdiction or configuration errors
    """

async def check_juristiction(client: Client, market: str) -> None:
    """
    Verify geographical access to dYdX services.
    
    Args:
        client: dYdX client instance
        market: Market to test (e.g., "BTC-USD")
    
    Raises:
        SystemExit: If access is prohibited (HTTP 403)
    """
```

### Usage Example
```python
from func_connections import connect_dydx

# Connect to dYdX
client = await connect_dydx()

# Use client components
markets = await client.indexer.markets.get_perpetual_markets()
account = await client.indexer_account.account.get_subaccount(address, 0)
```

---

## 📊 func_cointegration.py

### Statistical Analysis Functions

```python
def calculate_cointegration(series_1: List[float], series_2: List[float]) -> Tuple[int, float, float]:
    """
    Perform cointegration test on two price series.
    
    Args:
        series_1: First price series (numpy array compatible)
        series_2: Second price series (numpy array compatible)
    
    Returns:
        Tuple[int, float, float]: (cointegration_flag, hedge_ratio, half_life)
        - cointegration_flag: 1 if cointegrated, 0 if not
        - hedge_ratio: Optimal hedge ratio between series
        - half_life: Mean reversion half-life in hours
    
    Raises:
        SmartError: For invalid input data or calculation failures
    """

def calculate_zscore(spread: List[float]) -> pd.Series:
    """
    Calculate rolling Z-score for spread series.
    
    Args:
        spread: Price spread series
    
    Returns:
        pd.Series: Rolling Z-score values
    """

def half_life_mean_reversion(series: List[float]) -> float:
    """
    Calculate mean reversion half-life using linear regression.
    
    Args:
        series: Time series for half-life calculation
    
    Returns:
        float: Half-life in periods (hours for hourly data)
    
    Raises:
        SmartError: For invalid input or regression failures
    """

def store_cointegration_results(df_market_prices: pd.DataFrame) -> str:
    """
    Analyze all market pairs for cointegration and save results.
    
    Args:
        df_market_prices: DataFrame with market prices as columns
    
    Returns:
        str: "saved" if successful
    
    Side Effects:
        Creates 'cointegrated_pairs.csv' with analysis results
    """
```

### Usage Example
```python
from func_cointegration import calculate_cointegration, calculate_zscore

# Test cointegration between two assets
series_1 = [100, 101, 99, 102, 98]  # BTC prices
series_2 = [50, 51, 49, 52, 48]     # ETH prices

coint_flag, hedge_ratio, half_life = calculate_cointegration(series_1, series_2)

if coint_flag:
    spread = np.array(series_1) - hedge_ratio * np.array(series_2)
    zscore = calculate_zscore(spread)
    print(f"Current Z-score: {zscore.iloc[-1]}")
```

---

## 📈 func_entry_pairs.py

### Entry Management Functions

```python
async def open_positions(client: Client) -> str:
    """
    Analyze cointegrated pairs and open new positions when signals trigger.
    
    Process:
    1. Load cointegrated pairs from CSV
    2. Calculate current Z-scores for each pair
    3. Check entry conditions (|Z-score| >= threshold)
    4. Validate account balance and position limits
    5. Execute paired trades via BotAgent
    6. Update bot_agents.json with new positions
    
    Args:
        client: Connected dYdX client instance
    
    Returns:
        str: "complete" when analysis finished
    
    Side Effects:
        - Updates bot_agents.json with new positions
        - Places market orders on dYdX exchange
        - Logs trading decisions and executions
    """

def _calculate_trade_sizes(base_market: str, quote_market: str, 
                          markets: dict, hedge_ratio: float) -> Tuple[float, float]:
    """
    Calculate optimal position sizes for paired trade.
    
    Args:
        base_market: First market symbol
        quote_market: Second market symbol  
        markets: Market information dictionary
        hedge_ratio: Calculated hedge ratio between assets
    
    Returns:
        Tuple[float, float]: (base_size, quote_size) in native units
    """

def _determine_trade_sides(zscore: float) -> Tuple[str, str]:
    """
    Determine BUY/SELL sides based on Z-score direction.
    
    Args:
        zscore: Current Z-score value
    
    Returns:
        Tuple[str, str]: (base_side, quote_side) - "BUY" or "SELL"
    
    Logic:
        - Positive Z-score: Spread too high → SHORT base, LONG quote
        - Negative Z-score: Spread too low → LONG base, SHORT quote
    """
```

### Usage Example
```python
from func_entry_pairs import open_positions

# Analyze and execute entry opportunities
result = await open_positions(client)
print(f"Entry analysis complete: {result}")
```

---

## 📉 func_exit_pairs.py

### Exit Management Functions

```python
async def manage_trade_exits(client: Client) -> str:
    """
    Monitor existing positions and close when exit conditions are met.
    
    Process:
    1. Load active positions from bot_agents.json
    2. Get current exchange positions for validation
    3. Calculate current Z-scores for each active pair
    4. Check exit conditions (Z-score crosses zero or force close)
    5. Execute closing orders
    6. Update bot_agents.json removing closed positions
    
    Args:
        client: Connected dYdX client instance
    
    Returns:
        str: "complete" when exit management finished
    
    Exit Conditions:
        - Z-score crosses zero (mean reversion)
        - Position exists locally but not on exchange
        - Manual force close conditions
        - Emergency abort mode
    """

def _should_close_position(bot_agent: dict, current_zscore: float, 
                         close_at_cross: bool) -> bool:
    """
    Determine if position should be closed based on current conditions.
    
    Args:
        bot_agent: Position data from bot_agents.json
        current_zscore: Current calculated Z-score
        close_at_cross: Whether to close on zero-cross
    
    Returns:
        bool: True if position should be closed
    """

def _validate_exchange_position(client: Client, bot_agent: dict) -> bool:
    """
    Verify position exists on exchange matching local records.
    
    Args:
        client: dYdX client instance
        bot_agent: Local position record
    
    Returns:
        bool: True if position exists on exchange
    """
```

### Usage Example
```python
from func_exit_pairs import manage_trade_exits

# Monitor and close positions
result = await manage_trade_exits(client)
print(f"Exit management complete: {result}")
```

---

## 🤖 func_bot_agent.py

### BotAgent Class
State machine for managing atomic paired trade execution.

```python
class BotAgent:
    """
    Manages atomic execution of paired trades with comprehensive state tracking.
    
    State Flow:
        INITIALIZING → PLACING_FIRST → CHECKING_FIRST → PLACING_SECOND → 
        CHECKING_SECOND → LIVE → CLOSING → CLOSED
    
    Error States:
        FAILED: Unrecoverable error, trade aborted
        ERROR: Requires intervention, may be recoverable
    """
    
    def __init__(self, client: Client, market_1: str, market_2: str,
                 base_side: str, base_size: float, base_price: float,
                 quote_side: str, quote_size: float, quote_price: float,
                 accept_failsafe_base_price: float, z_score: float,
                 half_life: float, hedge_ratio: float):
        """
        Initialize BotAgent with trade parameters.
        
        Args:
            client: dYdX client instance
            market_1: First market symbol (e.g., "BTC-USD")
            market_2: Second market symbol (e.g., "ETH-USD")
            base_side: First order side ("BUY" or "SELL")
            base_size: First order size in native units
            base_price: First order price with slippage protection
            quote_side: Second order side ("BUY" or "SELL") 
            quote_size: Second order size in native units
            quote_price: Second order price with slippage protection
            accept_failsafe_base_price: Failsafe close price
            z_score: Entry Z-score value
            half_life: Pair's mean reversion half-life
            hedge_ratio: Calculated hedge ratio
        """
    
    async def open_trades(self) -> dict:
        """
        Execute the complete paired trade sequence.
        
        Returns:
            dict: Order dictionary with execution results and state
            
        State Updates:
            - Sets pair_status: "LIVE", "FAILED", or "ERROR"
            - Records order IDs, timestamps, and execution details
            - Handles failsafe closure on partial fills
        
        Process:
            1. Place first market order
            2. Verify first order execution (status = "live")
            3. Place second market order
            4. Verify second order execution
            5. Handle failures with automatic cleanup
        """
    
    async def check_order_status_by_id(self, order_id: str) -> str:
        """
        Check order execution status by ID.
        
        Args:
            order_id: dYdX order identifier
        
        Returns:
            str: Order status ("live", "canceled", "filled", etc.)
        """
```

### Order Dictionary Structure
```python
order_dict = {
    "market_1": "BTC-USD",           # First market symbol
    "market_2": "ETH-USD",           # Second market symbol
    "hedge_ratio": 0.065,            # Calculated hedge ratio
    "z_score": 1.75,                 # Entry Z-score
    "half_life": 18.5,               # Mean reversion half-life
    "order_id_m1": "abc123",         # First order ID
    "order_m1_size": "0.01",         # First order size
    "order_m1_side": "BUY",          # First order side
    "order_time_m1": "2024-01-01T12:00:00", # First order timestamp
    "order_id_m2": "def456",         # Second order ID
    "order_m2_size": "0.65",         # Second order size
    "order_m2_side": "SELL",         # Second order side
    "order_time_m2": "2024-01-01T12:00:05", # Second order timestamp
    "pair_status": "LIVE",           # Overall pair status
    "comments": ""                   # Error messages or notes
}
```

### Usage Example
```python
from func_bot_agent import BotAgent

# Create and execute paired trade
bot_agent = BotAgent(
    client=client,
    market_1="BTC-USD",
    market_2="ETH-USD", 
    base_side="BUY",
    base_size=0.01,
    base_price=45000.0,
    quote_side="SELL",
    quote_size=0.65,
    quote_price=3000.0,
    accept_failsafe_base_price=44000.0,
    z_score=1.75,
    half_life=18.5,
    hedge_ratio=0.065
)

# Execute the trade
result = await bot_agent.open_trades()
print(f"Trade status: {result['pair_status']}")
```

---

## 🔐 func_private.py

### Account Management Functions

```python
async def get_account(client: Client) -> dict:
    """
    Retrieve account information and balances.
    
    Args:
        client: dYdX client instance
    
    Returns:
        dict: Account data including balances and positions
    """

async def get_open_positions(client: Client) -> dict:
    """
    Get all open perpetual positions from exchange.
    
    Args:
        client: dYdX client instance
    
    Returns:
        dict: Open positions keyed by market symbol
        
    Handles:
        - Fresh testnet accounts (404 errors)
        - Wallet address fallback logic
        - Empty position responses
    """

async def is_open_positions(client: Client, market: str) -> bool:
    """
    Check if specific market has open position.
    
    Args:
        client: dYdX client instance
        market: Market symbol to check
    
    Returns:
        bool: True if position exists
    """
```

### Order Management Functions

```python
async def place_market_order(client: Client, market: str, side: str, 
                           size: float, price: float, reduce_only: bool) -> Tuple[dict, str]:
    """
    Place market order with comprehensive error handling.
    
    Args:
        client: dYdX client instance
        market: Market symbol (e.g., "BTC-USD")
        side: Order side ("BUY" or "SELL")
        size: Order size in native market units
        price: Limit price for market order bounds
        reduce_only: Whether order can only reduce existing position
    
    Returns:
        Tuple[dict, str]: (order_response, order_id)
    
    Features:
        - Automatic order ID extraction from recent orders
        - Market order with price bounds for protection
        - Rate limiting with 1.5s delay for order confirmation
        - Comprehensive error logging and validation
    
    Raises:
        SystemExit: If order ID cannot be determined
    """

async def cancel_order(client: Client, order_id: str) -> None:
    """
    Cancel existing order by ID.
    
    Args:
        client: dYdX client instance
        order_id: Order to cancel
    
    Side Effects:
        - Submits cancellation request to exchange
        - Logs cancellation confirmation
        - Warns user to verify on dashboard
    """

async def check_order_status(client: Client, order_id: str) -> str:
    """
    Check order execution status.
    
    Args:
        client: dYdX client instance
        order_id: Order to check
    
    Returns:
        str: Order status or "FAILED"
    """

async def abort_all_positions(client: Client) -> None:
    """
    Emergency function to close all open positions.
    
    Args:
        client: dYdX client instance
    
    Process:
        1. Get all open positions
        2. Calculate closing sizes and sides
        3. Place market orders to close each position
        4. Log all closure attempts
    
    Use Cases:
        - Emergency shutdown
        - Risk management
        - Account cleanup
    """
```

### Usage Example
```python
from func_private import place_market_order, get_open_positions

# Place a market order
order, order_id = await place_market_order(
    client=client,
    market="BTC-USD",
    side="BUY", 
    size=0.01,
    price=45000.0,
    reduce_only=False
)

# Check positions
positions = await get_open_positions(client)
print(f"Open positions: {list(positions.keys())}")
```

---

## 🌍 func_public.py

### Market Data Functions

```python
async def get_candles_recent(client: Client, market: str) -> np.ndarray:
    """
    Get recent price candles for market analysis.
    
    Args:
        client: dYdX client instance
        market: Market symbol
    
    Returns:
        np.ndarray: Array of close prices (most recent first)
    
    Features:
        - Automatic rate limiting (0.2s delay)
        - Price series reversal for chronological order
        - Type conversion to float64 for numerical stability
    """

async def get_candles_historical(client: Client, market: str) -> List[dict]:
    """
    Get historical price data across multiple timeframes.
    
    Args:
        client: dYdX client instance
        market: Market symbol
    
    Returns:
        List[dict]: Price data with datetime and market columns
    
    Features:
        - Multi-timeframe data aggregation
        - ISO timestamp handling
        - Configurable time windows via func_utils.get_ISO_times()
    """

async def get_markets(client: Client) -> dict:
    """
    Get all available perpetual markets and metadata.
    
    Args:
        client: dYdX client instance
    
    Returns:
        dict: Market information including tick sizes, step sizes, status
    """

async def construct_market_prices(client: Client) -> pd.DataFrame:
    """
    Build comprehensive price matrix for all active markets.
    
    Args:
        client: dYdX client instance
    
    Returns:
        pd.DataFrame: Price matrix with datetime index and market columns
    
    Process:
        1. Filter active markets from exchange
        2. Fetch historical data for each market
        3. Merge into unified DataFrame with outer join
        4. Clean NaN values and validate data integrity
    
    Features:
        - Progress logging for long operations
        - Automatic NaN column removal
        - Memory-efficient DataFrame operations
        - Error handling for individual market failures
    """
```

### Usage Example
```python
from func_public import construct_market_prices, get_markets

# Get market information
markets = await get_markets(client)
print(f"Available markets: {len(markets['markets'])}")

# Build price matrix for cointegration analysis  
price_df = await construct_market_prices(client)
print(f"Price matrix shape: {price_df.shape}")
```

---

## 💬 func_messaging.py

### Notification Functions

```python
def send_message(message: str) -> None:
    """
    Send notification message via Telegram.
    
    Args:
        message: Text message to send
    
    Features:
        - Automatic configuration loading
        - HTML formatting support
        - Error handling for failed sends
        - Rate limiting protection
    
    Configuration Required:
        - telegram.token: Bot token from @BotFather
        - telegram.chat_id: Target chat identifier
    """
```

### Usage Example
```python
from func_messaging import send_message

# Send notifications
send_message("Bot started successfully")
send_message("⚠️ Position closed due to Z-score reversion")
send_message("🚨 Critical error: Connection failed")
```

---

## 🛠️ func_utils.py

### Utility Functions

```python
def format_number(number: float, precision: int) -> str:
    """
    Format number to specified decimal precision.
    
    Args:
        number: Number to format
        precision: Decimal places
    
    Returns:
        str: Formatted number string
    """

def get_ISO_times() -> dict:
    """
    Generate ISO timestamp ranges for historical data queries.
    
    Returns:
        dict: Timeframe mappings with from_iso and to_iso values
    
    Purpose:
        - Supports historical price data collection
        - Provides consistent time window definitions
        - Handles timezone-aware timestamp generation
    """
```

---

## 📝 logging_setup.py

### Logging Configuration

```python
def setup_logging() -> None:
    """
    Initialize comprehensive logging system.
    
    Features:
        - Console handler with formatted output
        - Optional Grafana Loki integration
        - Log level configuration from config.yaml
        - Stream labels for Grafana filtering
        - Custom Loki handler with HTTP direct requests
    
    Configuration:
        - logging.level: Log level threshold
        - logging.loki.enabled: Enable/disable Loki integration
        - logging.loki.url: Loki endpoint URL
        - logging.loki.labels: Stream labels for log categorization
    """

class LokiHandler(logging.Handler):
    """
    Custom Loki handler for reliable log shipping.
    
    Features:
        - Direct HTTP requests to Loki API
        - Stream labels sent as HTTP headers
        - Authentication support (basic auth)
        - Error handling for failed shipments
        - Tenant ID support for multi-tenant deployments
    """
```

### Usage Example
```python
from logging_setup import setup_logging
import logging

# Initialize logging (call once at startup)
setup_logging()

# Use logging throughout application
logger = logging.getLogger(__name__)
logger.info("Bot operation completed successfully")
logger.error("Failed to process trade", extra={"market": "BTC-USD"})
```

---

## 🚀 main.py

### Main Execution Functions

```python
async def main() -> None:
    """
    Main bot execution loop with comprehensive error handling.
    
    Execution Flow:
        1. Initialize logging system
        2. Load and validate configuration
        3. Send startup notification
        4. Connect to dYdX exchange
        5. Optional: Close all existing positions
        6. Optional: Perform cointegration analysis
        7. Enter continuous trading loop:
           - Manage position exits
           - Find new entry opportunities
           - Execute trades via BotAgent
        
    Features:
        - Signal handlers for graceful shutdown (SIGINT, SIGTERM)
        - Configuration validation with detailed error messages
        - Telegram notifications for startup and critical errors
        - Continuous operation with exception handling
        - Proper asyncio lifecycle management
    
    Error Handling:
        - Configuration errors: Exit with status 1
        - Connection errors: Alert and exit
        - Trading errors: Alert and exit
        - Keyboard interrupt: Graceful shutdown
    """

def signal_handler(signum: int, frame) -> None:
    """
    Handle shutdown signals gracefully.
    
    Args:
        signum: Signal number (SIGINT=2, SIGTERM=15)
        frame: Current stack frame
    
    Actions:
        - Log shutdown reason
        - Send notification
        - Exit with status 0
    """
```

### Usage Example
```python
import asyncio
from main import main

# Run the trading bot
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot interrupted during startup")
```

---

## 🔗 Module Dependencies

### Import Graph
```
main.py
├── logging_setup.py
├── config.py
├── constants.py
├── func_connections.py
├── func_cointegration.py
├── func_entry_pairs.py
│   ├── func_bot_agent.py
│   ├── func_private.py
│   └── func_public.py
├── func_exit_pairs.py
│   ├── func_private.py
│   └── func_public.py
├── func_messaging.py
└── func_utils.py
```

### External Dependencies
- `dydx-v4-client`: Official dYdX Python SDK
- `pandas`: Data manipulation and analysis
- `numpy`: Numerical computing
- `statsmodels`: Statistical analysis (cointegration)
- `scipy`: Scientific computing (regression)
- `aiohttp`: Async HTTP client (Loki logging)
- `pyyaml`: YAML configuration parsing

This API documentation provides comprehensive coverage of all core modules, enabling developers to understand, extend, and maintain the dYdX Trading Bot effectively.