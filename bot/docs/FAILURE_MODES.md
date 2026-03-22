# Failure Modes and Recovery Guide

This document lists known high-impact failure paths, expected symptoms, and operator actions.

## FM-001: Jurisdiction / access blocked

- **Where**: `src/trading/dydx_client.py` (`check_jurisdiction`)
- **Symptom**: client init fails and exception propagates to instance entrypoint
- **Impact**: bot instance unavailable
- **Operator action**:
  1. Confirm network endpoint and credentials are correct
  2. Validate region/access restrictions with the exchange
  3. Keep instance stopped until access is valid

## FM-002: Order resolution ambiguity

- **Where**: `src/trading/account_manager.py` (latest order detection)
- **Symptom**: unable to map placed order to exchange order id
- **Impact**: unsafe state; fail-closed exception path
- **Operator action**:
  1. Inspect recent exchange orders directly
  2. Confirm whether trade was filled/partial/canceled
  3. Reconcile local state file before restart

## FM-003: Exchange/local position mismatch

- **Where**: `src/trading/position_manager.py`
- **Symptom**: market/size/side mismatch between local and exchange state
- **Impact**: bot fails closed via exception to prevent unmanaged risk
- **Operator action**:
  1. Pause instance
  2. Manually verify and close/reduce mismatched positions
  3. Clean or rebuild local state file entries

## FM-004: Event-loop stall risk from blocking sleeps

- **Where**: async paths in trading/runtime modules
- **Symptom**: delayed loop responsiveness, sluggish shutdown/recovery
- **Impact**: missed timing windows and delayed risk controls
- **Operator action**:
  1. Reduce concurrent operational load
  2. Restart impacted instance if loop appears stalled
  3. Track remediation to replace blocking sleeps with async sleeps

## FM-005: Placeholder API surfaces

- **Where**:
  - `src/api/v1/auth/password_2fa.py`
  - `src/api/v1/auth/__init__.py` (`/register`)
  - `src/infrastructure/persistence/repository_backtest.py`
- **Symptom**: endpoint exists but returns non-production placeholder behavior
- **Impact**: partial product capability
- **Operator action**:
  1. Do not rely on these paths for production controls
  2. Use documented supported endpoints only
  3. Track status in `docs/FEATURE_STATUS.md`

## FM-006: Interpreter drift across launch paths

- **Where**: shells/tasks/process-manager launch commands
- **Symptom**: module import failures or inconsistent runtime behavior
- **Impact**: failed startup or non-reproducible incidents
- **Operator action**:
  1. Ensure `.venv` interpreter is used consistently
  2. Validate task/make/runtime launcher alignment

## Escalation policy

Escalate immediately when:

- Any position is open but not represented reliably in local state
- Repeated startup failures occur across multiple instances
- Emergency close attempts fail or partially complete
