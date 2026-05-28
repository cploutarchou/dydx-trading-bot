---
name: "defi-observability-metrics"
description: "Design, implement, and troubleshoot observability for the dYdX trading bot: Prometheus metrics, structured logging, dashboards, health monitoring, alerts, and operational dashboards. Use when: adding metrics to trading code, setting up Grafana dashboards, debugging operator visibility, configuring alerting rules, analyzing performance, or improving system observability."
argument-hint: "Describe the observable component (bot, backend, backtest), the metric goal, and the target audience (developers, operators, traders)."
user-invocable: true
disable-model-invocation: false
---

# DeFi Observability & Metrics

Design and maintain production-grade observability for the dYdX trading bot platform: metrics, logging, dashboards, and alerting that enable operators to see system health, trading performance, and runtime diagnostics in real time.

## Scope

This skill owns:

- **Prometheus metrics**: `arbitrage_observability.py` counters, performance metrics, rejection reasons
- **Structured logging**: Log levels, contextual logging, error tracking
- **Grafana dashboards**: Visual monitoring of bot performance, trading activity, system health
- **Health endpoints**: `/metrics`, readiness/liveness probes, service health
- **Alerting rules**: Thresholds for operator alerting, anomaly detection
- **Operator dashboards**: Frontend visibility into bot state, strategy performance, live metrics
- **WebSocket telemetry**: Real-time metrics pushed to connected clients
- **Observability contracts**: What metrics are guaranteed to exist, how to interpret them

## When to Use

Use this skill when you need to:

- Add new metrics to trading or runtime code (e.g., `arbitrage_scan_cycles_total`)
- Design a new Grafana dashboard for operators
- Troubleshoot why metrics are missing or incorrect
- Implement alerting thresholds for trading risk
- Set up centralized logging aggregation (e.g., Loki)
- Design operator-facing health/status pages
- Debug why the `/metrics` endpoint shows unexpected values
- Create performance baselines for backtests
- Instrument async tasks for observability

## Operating Principles

1. **Metrics enable action**: Every metric should answer an operator question or enable an operational decision. No vanity metrics.

2. **Levels matter**: Distinguish between real-time operator dashboards, engineer debug logs, and audit trails. Keep each at appropriate verbosity.

3. **Performance is non-negotiable**: Observability code must not slow down trading execution. Use sampling, async writes, and bounded buffers where needed.

4. **Observability contracts are sacred**: If an operator or integration depends on a metric existing and having a certain meaning, document that promise explicitly.

5. **Separate concerns**: Do not embed business logic (risk checks, trading decisions) inside observability code. Observability reports; logic decides.

6. **Retrospective visibility**: Logs and metrics should enable post-incident investigation. Include enough context (backtest ID, instance ID, pair, timestamp) to reconstruct events.

## Quality Checklist

- [ ] New metrics have clear, durable names (e.g., `arbitrage_opportunities_executed_total` not `op_exec`)
- [ ] Metric units are explicit (seconds, bytes, count, ratio) in comments
- [ ] Metrics are thread-safe or protected by locks (not racy in multithreaded/async context)
- [ ] High-cardinality tags (e.g., pair names) are not unbounded; use aggregation or sampling
- [ ] Operator dashboards show both live and aggregated views (e.g., 1m, 5m, 1h windows)
- [ ] Critical operator decisions have corresponding alerting thresholds
- [ ] Logs include trace IDs, instance IDs, or request context for correlation
- [ ] Sensitive data (keys, balances, exact PnL) is never emitted to metrics/logs
- [ ] Observability impact on latency/throughput is measured and acceptable
- [ ] Grafana dashboards have runbooks or operator guides for common alerts

## Related Docs

- `bot/src/trading/arbitrage_observability.py` — Metrics counter implementation
- `bot/src/api/server.py` — `/metrics` endpoint and health checks
- `frontend/src/components/SyncHealthPanel.tsx` — Operator health dashboard
- `README.md` — KPI review guidance for operators
- Backend service health routes (dashboards, status endpoints)

## Common Workflows

### Add a New Trading Metric

1. Identify the event and cardinality (e.g., "pairs rejected per scan")
2. Add counter or histogram to `arbitrage_observability.py` or relevant module
3. Call metric function at the right point in code (e.g., `increment_metric("pair_candidates_skipped_total")`)
4. Update operator runbook to explain what the metric means and when it's abnormal
5. Wire to Grafana dashboard if it's an operator-facing metric
6. Test metric appears in `/metrics` endpoint after running bot

### Debug Missing Metrics

1. Verify metric name is correct and matches code being executed
2. Check if metric counter is initialized (not all paths may increment it)
3. Confirm bot/backend service has `/metrics` endpoint configured
4. Verify Prometheus scrape config targets the service
5. Check if metric is bounded by sample size or aggregation window
6. Look for exceptions in metric increment code (silent failures)

### Set Up Operator Alerting

1. Identify the operator decision: "What must be acted on immediately?"
2. Map to specific metric(s) that indicate when action is needed
3. Define threshold or anomaly rule (e.g., `rejection_ratio > 0.2 for 5m`)
4. Configure alerting rule in Prometheus or service health endpoint
5. Route alert to operator channel (email, Telegram, dashboard panel)
6. Document runbook: "Alert fired for X, check Y, then do Z"
7. Test alert with synthetic data or staging environment

### Create Operator Dashboard

1. Define operator role: trader, risk manager, platform SRE?
2. Identify key decisions they need to make (e.g., "Should I rebalance?" "Is the bot healthy?")
3. Collect metrics that answer those questions
4. Design Grafana panels with appropriate time ranges and aggregations
5. Add threshold lines or zones for anomaly visibility
6. Annotate panels with runbook links and explanations
7. Test with live bot traffic; adjust based on operator feedback

## Observability Contract Examples

### Arbitrage Efficiency Metrics

```
arbitrage_scan_cycles_total         # Total scan iterations
exchange_api_calls_total            # All API calls made
exchange_api_calls_saved_total      # Calls avoided via caching
pair_candidates_skipped_total       # Pairs rejected before execution
opportunities_executed_total        # Trades placed
```

**Operator interpretation**: `(api_calls_saved / total_calls)` = efficiency gain. If trending down, caching is stale or market is changing rapidly.

### Rejection Reason Buckets

```
rejection_reason{reason="min_order_size"} = 42
rejection_reason{reason="market_already_open"} = 15
rejection_reason{reason="insufficient_collateral"} = 8
```

**Operator interpretation**: Top rejection reason tells you where to optimize next (e.g., if min order size is blocking, lower capital allocation or find bigger pairs).

## Performance Guidance

- Metric updates should be `O(1)` operations (no loops, no DB queries)
- Use thread-local or atomic counters; avoid global locks if possible
- Bounded buffers for high-volume events (e.g., only sample 1% of candle updates)
- Async metric writes if reporting to external system (don't block trading)
- Metric retention: balance data volume with operator needs (e.g., 15-day Prometheus retention)

## Validation

After implementing observability, verify:

- Metrics appear in `/metrics` endpoint or Prometheus scrape
- Metric names and units are documented
- Operator dashboards update in real time without lag
- Alerts fire at expected thresholds
- Metrics do not introduce measurable latency to trading paths
- Sensitive data is not exposed
- Logs are queryable and correlate with metrics
