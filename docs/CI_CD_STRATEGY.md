# CI/CD Strategy and Integration Confidence

This document outlines the comprehensive continuous integration, testing, and deployment strategy that ensures production readiness for the dYdX Trading Bot platform.

## Three-Layer CI Architecture

### Layer 1: Service Unit Testing
Each service runs independent CI pipelines on push/PR:

- **Backend** (`.github/workflows/ci.yml` in backend/):
  - Go linting (golangci-lint)
  - Unit tests with race detection and coverage reporting
  - WebSocket-specific smoke tests
  - Security scanning (gosec)
  - Docker build validation

- **Frontend** (frontend/.github/workflows/ci.yml):
  - ESLint code style validation
  - Contract guard tests (`npm run test:contracts`)
    - Verifies backend-only HTTP origin
    - Validates websocket routing to backend
    - Locks frontend API surface contract
  - Vite production build validation

- **Bot** (bot/.github/workflows/ci.yml):
  - Python linting (flake8, pylint, black)
  - Unit tests with pytest (catches crashes and basic logic errors)
  - Docker image build validation on main branches

### Layer 2: Contract Lock Testing
**Governance-and-Contract-Lock** workflow (`.github/workflows/governance-and-contract-lock.yml`):

Runs on every push to main/master and all PRs. Enforces:

- **Backend contracts**: `TestContractLock_*` suite validates:
  - All public routes preserve documented request/response schemas
  - Startup validation (database ownership, service readiness)
  - Error responses include proper status codes and error fields

- **Frontend contracts**: `npm run test:contracts` validates:
  - API client always uses backend origin (never direct bot)
  - WebSocket connections route through backend proxy
  - Auth token handling follows documented pattern
  - No dependency on bot-specific ports or assumptions

- **Task governance**: Validates task.md files are up-to-date with actual code

**Passed contract lock** = safe to merge; architectural boundaries protected.

### Layer 3: End-to-End Integration Tests
**E2E Integration Tests** workflow (`.github/workflows/e2e-integration.yml`):

Runs nightly (02:00 UTC) and on every push to develop/main/master. Orchestrates:

1. **Infrastructure startup**
   - PostgreSQL, Redis initialization
   - Health checks on data stores

2. **Stack deployment**
   - Full docker-compose stack from root Makefile
   - Wait for services to stabilize (15 seconds)

3. **Smoke test sequence**
   - **Backend readiness**: `/ready` endpoint returns 200 with database ownership and bot recovery diagnostics
   - **Backend liveness**: `/health` endpoint returns "healthy" with database stats, uptime, bot snapshot
   - **Metrics visibility**: `/metrics` endpoint exposes connection pool, wait stats, bot metrics
   - **Contract lock**: Strategy list endpoint returns 401 without token (proves backend contract)
   - **Database ownership**: Confirms separation state in diagnostics
   - **Bot recovery**: Confirms recovery state diagnostics available

4. **Failure handling**
   - Collect container logs (last 100 lines per service)
   - Dump docker-compose status and network inspection
   - Full cleanup (stack + infra)

**E2E pass** = platform can start, services communicate, observability available, contracts locked.

## Test Coverage Strategy

### Unit Test Targets (Per-Service)
- **Backend**: >80% coverage target on routes and critical business logic
- **Frontend**: 100% on contract guards + utility functions
- **Bot**: >60% coverage on core trading logic (API/strategy execution)

### Integration Test Targets (E2E)
- Backend readiness/liveness lifecycle
- Database ownership enforcement
- Cross-service health diagnostics
- WebSocket routing validation

### Manual Test Gates (Pre-Production)
- Live strategy launch with real credentials (testnet only)
- Backtest series execution and storage verification
- Long-tail recovery scenarios (kill containers, verify recovery)
- Load testing with multiple concurrent backtest runs

## CI/CD Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Developer pushes code                                            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
   ┌────▼─────┐              ┌────────▼────────┐
   │ Service  │              │ Contract Lock   │
   │ Unit CI  │              │ Governance      │
   │          │              │                 │
   │ - Lint   │              │ - Backend       │
   │ - Test   │              │ - Frontend      │
   │ - Build  │              │ - Task sync     │
   └────┬─────┘              └────────┬────────┘
        │ (pass)                      │ (pass)
        │                             │
        └──────────────┬──────────────┘
                       │
            ┌──────────▼──────────┐
            │ All CI Passed       │
            │ Safe to Merge / PR  │
            └──────────┬──────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
   ┌────▼─────────────┐      ┌────────▼────────────┐
   │ (Nightly) E2E    │      │ Manual Testing    │
   │ Integration      │      │ (Pre-Prod)        │
   │                  │      │                    │
   │ - Stack startup  │      │ - Live launch     │
   │ - Health checks  │      │ - Recovery test   │
   │ - Smoke tests    │      │ - Load test       │
   │ - Contract lock  │      └────────────────────┘
   └──────────────────┘
```

## Operational Best Practices

### For Developers
1. **Before pushing**: `make lint`, `make test` locally
2. **Contract changes**: Update corresponding contract guard test
3. **Cross-service changes**: Verify contract-lock tests pass
4. **Documentation**: Update `task.md` in PR (ci will validate)

### For Operators
1. **Production deployment**: Wait for all CI to pass (green checkmarks)
2. **Post-deploy health check**:
   ```bash
   curl https://prod.example.com/health | jq '.status'
   curl https://prod.example.com/ready | jq '.ready'
   curl https://prod.example.com/metrics | jq '.service.uptime_seconds'
   ```
3. **Incident debugging**: Use health/ready/metrics endpoints in order
4. **Regression detection**: Nightly E2E tests catch integration failures early

### Failure Response
- **Unit test failure**: Fix code + add test case
- **Contract lock failure**: Revert or fix contract violations (architectural boundary)
- **E2E smoke failure**: Check service logs, verify infrastructure, rerun
- **Production incident**: Use `/health` → `/ready` → `/metrics` → logs sequence

## Continuous Improvement

### Metrics to Track
- Unit test pass rate and coverage trend
- Contract lock failures (catch breaking changes early)
- E2E smoke test flakiness (identify stability issues)
- Mean time to production post-merge (deployment confidence)

### Planned Enhancements (Future)
- Distributed tracing (Jaeger) integration in E2E tests
- Performance regression detection (latency percentiles)
- Canary deployment validation (A/B testing in prod)
- Automated rollback on health check failure

## References
- [Backend README - Testing](/backend/README.md)
- [Frontend README - Testing](/frontend/README.md)
- [Bot README - Testing](/bot/README.md)
- [Operations Guide - Deployment Gates](/docs/OPERATIONS.md#Production-Readiness-Baseline)
