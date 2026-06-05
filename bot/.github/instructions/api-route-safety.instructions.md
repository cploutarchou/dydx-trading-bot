---
name: "API Route Safety and Contract Stability"
description: "Use when adding or modifying API endpoints, request validation, error responses, or authentication. Enforces request validation, response envelope consistency, auth strictness, and backwards compatibility."
applyTo: "src/api/**/*.py"
---

# API Route Safety and Contract Stability

Apply these rules for all new or modified API routes.

## Request Validation (Input Gating)

Every route must validate and normalize inputs before processing.

### 1. Explicit Schema Validation

```python
from pydantic import BaseModel, Field, validator

class BacktestRequest(BaseModel):
    """Backtest request with strict validation."""

    strategy_id: str = Field(..., min_length=1, max_length=255)
    start_date: datetime = Field(..., description="Start date for backtest")
    end_date: datetime = Field(..., description="End date for backtest")
    initial_balance: float = Field(..., gt=0, description="Must be positive")
    leverage: float = Field(default=1.0, ge=1.0, le=20.0)

    @validator("end_date")
    def end_date_must_be_after_start(cls, v, values):
        if "start_date" in values and v <= values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "strategy_id": "arb-v2-dydx",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "initial_balance": 10000.0,
                "leverage": 2.0,
            }
        }
```

### 2. Auth Validation at Route Entry

```python
from fastapi import Depends, HTTPException, status

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Extract and validate bearer token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except JWTError:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = await fetch_user(user_id)
    if user is None:
        raise credentials_exception

    return user

@router.post("/api/v1/backtests")
async def create_backtest(
    request: BacktestRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a new backtest (auth required)."""
    # Auth already validated by dependency; safe to proceed
    ...
```

### 3. Enum Validation for State Transitions

```python
from enum import Enum

class BotStatus(str, Enum):
    """Valid bot instance states."""
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

class BotStartRequest(BaseModel):
    instance_id: str
    environment: Literal["testnet", "mainnet"]  # Strict enum
    strategy: str

    @validator("environment")
    def validate_environment(cls, v):
        if v not in ["testnet", "mainnet"]:
            raise ValueError("environment must be 'testnet' or 'mainnet'")
        return v
```

## Response Envelope (Output Consistency)

All responses must use the standardized envelope from `src/api/server.py`.

### 1. Standard Response Wrapper

```python
def api_response(
    data: Any = None,
    status: str = "success",
    message: str = None,
    error: str = None,
    trace_id: str = None,
    meta: Dict = None,
) -> Dict:
    """
    Standardized API response envelope.

    All routes must return this structure (wrapped by FastAPI response).
    """
    return {
        "status": status,  # "success", "error", "partial"
        "data": data,
        "message": message,
        "error": error,
        "trace_id": trace_id or get_current_trace_id(),
        "meta": meta or {},
    }

# Usage in routes:
@router.get("/api/v1/health")
async def health_check():
    return api_response(
        data={"status": "healthy", "timestamp": datetime.utcnow()},
        status="success",
    )

@router.get("/api/v1/ready")
async def readiness():
    bot_manager = get_bot_manager()
    if not bot_manager.is_available():
        # Strict: 503 if manager unavailable
        raise HTTPException(status_code=503, detail="Bot manager unavailable")
    return api_response(
        data={"ready": True},
        status="success",
    )
```

### 2. Error Responses (Predictable Structure)

```python
@router.post("/api/v1/backtests")
async def create_backtest(request: BacktestRequest):
    try:
        # Validate strategy exists
        if not strategy_exists(request.strategy_id):
            return api_response(
                status="error",
                error=f"Strategy '{request.strategy_id}' not found",
                data=None,
            ), 404

        # Create backtest
        backtest = await backtest_service.create(request)

        return api_response(
            data=backtest.to_dict(),
            status="success",
            message="Backtest created successfully",
        ), 201

    except ValidationError as e:
        return api_response(
            status="error",
            error="Validation failed",
            data={"details": e.errors()},
        ), 400

    except Exception as e:
        logger.error("Backtest creation failed", exc_info=e)
        return api_response(
            status="error",
            error="Internal server error",
            trace_id=get_current_trace_id(),
        ), 500
```

## Authentication Contracts

### 1. Service Token Overlap Support

Keep support for token rotation during deployment:

```python
def authenticate_bearer_token(token: str) -> TokenPayload:
    """
    Validate bearer token against multiple sources.

    Supports gradual token rotation:
    - BOT_API_TOKEN: current active token
    - BOT_API_TOKEN_PREVIOUS: previous token (for overlap during rotation)
    - BOT_API_TOKENS: comma-separated list of valid tokens
    """
    valid_tokens = set()

    # Current token
    current = os.getenv("BOT_API_TOKEN")
    if current:
        valid_tokens.add(current)

    # Previous token (for overlap)
    previous = os.getenv("BOT_API_TOKEN_PREVIOUS")
    if previous:
        valid_tokens.add(previous)

    # Token list
    token_list = os.getenv("BOT_API_TOKENS", "")
    if token_list:
        valid_tokens.update(t.strip() for t in token_list.split(","))

    if not valid_tokens:
        raise AuthenticationError("No valid tokens configured")

    if token not in valid_tokens:
        raise AuthenticationError("Invalid authentication token")

    return TokenPayload(authenticated=True, source="bearer_token")
```

### 2. Bypass for Development Only

```python
def is_auth_bypassed() -> bool:
    """Check if auth bypass is enabled (dev only)."""
    bypass = os.getenv("API_BYPASS_AUTH", "false").lower()
    if bypass == "true":
        logger.warning("WARNING: API_BYPASS_AUTH is enabled; this is dev-only")
        return True
    return False

@router.post("/api/v1/backtests")
async def create_backtest(
    request: BacktestRequest,
    current_user: User = Depends(get_current_user),
):
    """Create backtest with auth enforcement."""
    if is_auth_bypassed():
        logger.warning("Bypassing auth check (dev mode)")
    # Even with bypass, log it explicitly
    ...
```

## WebSocket Contracts

### 1. Strategy Status Snapshot on Connect

```python
async def websocket_strategy_runtime(websocket: WebSocket):
    """WebSocket endpoint for strategy runtime events."""
    await websocket.accept()

    try:
        # REQUIRED: Send snapshot on connect
        snapshot = await strategy_runtime.get_status_snapshot()
        await websocket.send_json({
            "type": "strategy_status_snapshot",
            "data": snapshot,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Then stream lifecycle updates
        async for event in strategy_runtime.stream_events():
            await websocket.send_json({
                "type": "strategy_status_update",
                "data": event,
                "timestamp": datetime.utcnow().isoformat(),
            })

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error("WebSocket error", exc_info=e)
        await websocket.close(code=1011)
```

## Backwards Compatibility

### 1. Deprecation Path for API Changes

```python
@router.get("/api/v1/runtime/strategy-resolution-metrics")
async def get_strategy_resolution_metrics():
    """Get strategy resolution metrics (primary endpoint)."""
    return api_response(data=metrics_service.get_metrics())

@router.get("/api/v1/admin/runtime/strategy-resolution-metrics")
async def get_strategy_resolution_metrics_admin():
    """
    Admin alias for backwards compatibility.

    DEPRECATED: Use /api/v1/runtime/strategy-resolution-metrics instead.
    This endpoint will be removed in v2.0.
    """
    return await get_strategy_resolution_metrics()
```

### 2. Field Aliases for Renamed Fields

```python
class BacktestResponse(BaseModel):
    """Backtest response with backwards compatibility."""

    status: str = Field(..., description="Backtest status")
    # New name
    progress_percent: float = Field(..., ge=0, le=100)
    # Alias for backwards compatibility
    progress: float = Field(alias="progress_percent")

    class Config:
        populate_by_name = True  # Allow both field name and alias
```

## Testing Expectations

For every new endpoint:

1. **Auth tests**: Verify bearer token validation
2. **Validation tests**: Test boundary conditions and invalid inputs
3. **Response tests**: Verify response envelope and structure
4. **Error tests**: Verify error responses include trace IDs
5. **Backwards compatibility**: Test that old clients still work

```python
def test_create_backtest_auth_required():
    """Verify endpoint requires auth."""
    response = client.post("/api/v1/backtests", json={})
    assert response.status_code == 401

def test_create_backtest_validation():
    """Verify invalid inputs are rejected."""
    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "", "start_date": "invalid"},
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 400
    assert "status" in response.json()
    assert response.json()["status"] == "error"

def test_create_backtest_success():
    """Verify successful backtest creation."""
    response = client.post(
        "/api/v1/backtests",
        json={
            "strategy_id": "arb-v2",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_balance": 10000.0,
        },
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "trace_id" in data
```

## Documentation Requirements

For every new endpoint, update:

- **openapi.json**: Auto-generated from route docstrings and Pydantic models
- **README.md**: High-level API overview and example curl commands
- **OPERATIONS.md**: Operational considerations (rate limits, auth, common errors)

Example docstring for auto-doc:

````python
@router.post(
    "/api/v1/backtests",
    response_model=BacktestResponse,
    status_code=201,
    summary="Create a new backtest",
    description="Create and schedule a new backtest run.",
    responses={
        400: {"description": "Invalid request parameters"},
        401: {"description": "Missing or invalid authentication"},
        500: {"description": "Server error"},
    },
)
async def create_backtest(
    request: BacktestRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create a new backtest with the specified strategy and parameters.

    **Authentication**: Requires valid bearer token in `Authorization` header.

    **Example**:
    ```
    curl -X POST http://localhost:8889/api/v1/backtests \
      -H "Authorization: Bearer YOUR_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "strategy_id": "arb-v2-dydx",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "initial_balance": 10000.0
      }'
    ```
    """
    ...
````
