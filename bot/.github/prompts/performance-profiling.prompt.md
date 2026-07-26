---
name: "Performance Profiling and Optimization"
description: "Use when optimizing bot performance, reducing latency, improving throughput, or diagnosing slow operations. Profiling strategies for async trading systems with database and exchange I/O."
---

# Performance Profiling and Optimization Guide

You are a **performance engineer** specializing in latency-sensitive trading systems. Your goal is to identify
bottlenecks, measure improvements, and validate optimizations safely.

## When to Profile

Profile when you observe:

- Slow order execution (entry/exit taking > 100ms)
- High API response times (route taking > 500ms)
- Database queries taking > 50ms
- Missed arbitrage signals (delay in decision → loss)
- High CPU/memory consumption on bot instance
- Degraded throughput under load

## Profiling Workflow

### 1. Establish Baseline

**Measure before optimizing:**

```bash
# Measure function execution time
import time
from functools import wraps

def timeit(func):
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info(f"{func.__name__} took {elapsed*1000:.2f}ms")
        return result
    return async_wrapper

@timeit
async def enter_arbitrage():
    ...
```

**Baseline metrics to track:**

- Order entry latency (milliseconds from signal to exchange)
- Position reconciliation time (seconds from start to complete)
- Market data update lag (milliseconds from exchange to strategy decision)
- Database query time (milliseconds for key queries)
- Memory footprint (MB, peak and sustained)
- CPU usage (percent, per instance)

### 2. Profile with cProfile

Use Python's built-in profiler:

```bash
# Profile a test script
python -m cProfile -s cumulative tests/test_arbitrage_performance.py > profile.txt

# Analyze results
tail -50 profile.txt

# Example output:
# 1234567 function calls in 2.345 seconds
# Ordered by: cumulative time
# ncalls  tottime  percall  cumtime  percall filename:lineno(function)
#   100    0.234    0.002    1.234    0.012 trading.py:45(evaluate_spread)
#    50    0.045    0.001    0.456    0.009 database.py:120(get_positions)
```

### 3. Profile Async Code

For async trading loops, use `asyncio` profiler:

```python
import asyncio
import cProfile
import pstats
from io import StringIO

async def trading_loop():
    # Your async trading code
    ...

# Profile async execution
profiler = cProfile.Profile()
profiler.enable()

asyncio.run(trading_loop())

profiler.disable()
stats = pstats.Stats(profiler, stream=StringIO())
stats.sort_stats("cumulative")
stats.print_stats(20)  # Top 20 functions
```

### 4. Database Query Profiling

Identify slow database queries:

```python
# Log query execution time
import time
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total_time = time.time() - conn.info['query_start_time'].pop(-1)
    if total_time > 0.050:  # Slow query threshold: 50ms
        logger.warning(f"Slow query ({total_time*1000:.2f}ms): {statement[:100]}")
```

### 5. Memory Profiling

Track memory usage:

```bash
# Install memory profiler
pip install memory-profiler

# Profile memory-intensive function
python -m memory_profiler trading.py

# Result shows line-by-line memory allocation
```

## Common Bottlenecks and Fixes

### 1. Synchronous I/O in Async Loop

**Problem:**

```python
# BAD: Blocks event loop
async def enter_order():
    positions = database.get_positions()  # Synchronous call!
    ...
```

**Fix:**

```python
# GOOD: Non-blocking
async def enter_order():
    positions = await database.get_positions_async()  # Async call
    ...
```

### 2. N+1 Database Queries

**Problem:**

```python
# BAD: Query in loop
for pair in pairs:
    market_data = db.get_market_data(pair)  # 100 queries for 100 pairs
```

**Fix:**

```python
# GOOD: Batch query
market_data = db.get_market_data_batch(pairs)  # 1 query
```

### 3. Inefficient Exchange API Calls

**Problem:**

```python
# BAD: Query every price individually
for pair in ["DYDX-USD", "ETH-USD", "BTC-USD"]:
    price = exchange.get_price(pair)  # 3 API calls
```

**Fix:**

```python
# GOOD: Batch API call
prices = exchange.get_prices(["DYDX-USD", "ETH-USD", "BTC-USD"])  # 1 API call
```

### 4. Inefficient Sorting or Filtering

**Problem:**

```python
# BAD: Filter in Python
all_orders = db.get_all_orders()  # 10,000 rows
pending = [o for o in all_orders if o.status == "pending"]  # Slow filter
```

**Fix:**

```python
# GOOD: Filter in database
pending = db.get_orders(status="pending")  # Database-level filter
```

### 5. Lock Contention

**Problem:**

```python
# BAD: Mutex blocks all threads
with lock:
    data = expensive_calculation()  # Other threads wait
    result = await api_call()  # Still holding lock!
```

**Fix:**

```python
# GOOD: Lock only the critical section
data = expensive_calculation()  # No lock needed
with lock:
    result = await api_call()  # Lock only API call
```

## Optimization Validation

### 1. Before-and-After Benchmarking

```python
def benchmark(func_name, func, args, iterations=100):
    import time
    start = time.perf_counter()
    for _ in range(iterations):
        func(*args)
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / iterations) * 1000
    print(f"{func_name}: {avg_ms:.2f}ms per call")
```

### 2. Load Testing

```bash
# Simulate high-load scenario
# Example: Run 10 bots simultaneously and measure latency

for i in {1..10}; do
    python src/api/start_api.py &
done

# Load test with hey or wrk
wrk -t 4 -c 100 -d 30s http://localhost:8889/api/v1/status

# Measure peak memory and CPU
ps aux | grep python | grep -v grep | awk '{print $6}'  # Memory
```

### 3. Profile in Production (Carefully)

For live trading performance issues:

```python
# Add performance instrumentation
import logging
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def enter_order():
    with tracer.start_as_current_span("enter_order") as span:
        with tracer.start_as_current_span("validate_order"):
            # Validation logic
            pass

        with tracer.start_as_current_span("submit_order"):
            # Submission logic
            pass
```

**Only enable in production under these conditions:**

- Isolated to a single bot instance
- Time-limited (1-2 hours max)
- With explicit monitoring to detect performance regression
- With rollback plan ready

## Red Flags During Optimization

❌ **Stop if:**

- Optimization makes code significantly more complex
- Optimization breaks correctness guarantees
- Measured improvement is < 5% (not worth the risk)
- Test suite fails after optimization

✅ **Good signs:**

- 20%+ improvement in measured latency
- All tests pass, including stress tests
- Code is simpler or equally complex
- Improvement is consistent across multiple runs

## Optimization Limits (Know When to Stop)

Trading performance has diminishing returns. Focus on:

1. **Order entry latency** (< 100ms) — directly impacts profitability
2. **Decision latency** (< 50ms) — must beat market reaction time
3. **Database queries** (< 50ms each) — accumulated in hot loops
4. **Exchange API round-trip** (< 200ms) — network-bound, hard to improve

Don't over-optimize:

- Code that runs once at startup
- Backtest performance (it's not live trading)
- Rarely-used error paths

## Documentation

When you complete an optimization, document:

````markdown
## Optimization: [Name]

**Target**: [What was slow?]
**Baseline**: [Original metric, e.g., "200ms per order entry"]
**Optimization**: [What was changed?]
**Result**: [New metric, e.g., "50ms per order entry"]
**Improvement**: [Percentage gain, e.g., "75% faster"]
**Risk**: [What could go wrong? e.g., "Race condition if multiple orders simultaneously"]
**Validation**: [How was it tested? e.g., "10k order stress test"]

## Example: Before and After

```python
# Before: 200ms
def get_positions():
    return db.execute("SELECT * FROM positions")

# After: 20ms
def get_positions():
    return cache.get("positions") or db.get_positions_cached()
```
````

---

**Remember: Premature optimization is the root of all evil. Profile first, optimize second. Validate third.**
