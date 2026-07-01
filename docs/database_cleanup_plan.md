# PostgreSQL Cleanup Migration Plan

## Overview

This document describes the planned PostgreSQL schema cleanup for Phase 3 of the FINAL_APPLICATION_IMPROVEMENT_PLAN. The cleanup addresses legacy JSON-heavy columns that are no longer needed after the MinIO artifact storage and ClickHouse analytics migrations are complete.

## Current State

### Legacy Columns Still Present

The following columns exist in the bot's PostgreSQL schema but are no longer used for new writes:

| Table | Column | Current Usage | Target State |
|-------|--------|---------------|--------------|
| `backtest_runtime_runs` | `request_json` | Still persisted | Remove after backfill |
| `backtest_runtime_runs` | `trades_json` | New writes set to `[]` | Remove after backfill |
| `backtest_runtime_runs` | `position_snapshots_json` | New writes set to `[]` | Remove after backfill |
| `backtest_runtime_runs` | `daily_pnl_json` | New writes set to `[]` | Remove after backfill |
| `backtest_run_requests` | `request_json` | Still persisted | Remove after backfill |

### New Storage Model

- **Artifacts**: Large result arrays (`trades_json`, `position_snapshots_json`, `daily_pnl_json`) are now stored in MinIO with references in PostgreSQL
- **Analytics**: Aggregated data is written to ClickHouse for analytical queries
- **Requests**: `request_json` contains the original backtest request parameters (not the large results)

## Migration Strategy

### Principle: Safe and Reversible

1. **Do not drop columns until all data is migrated**
2. **Create backfill scripts before schema changes**
3. **Test on staging with production-like data volume**
4. **Have rollback plan for each migration**

### Phase 3A: Data Migration (Required Before Schema Changes)

#### Step 1: Backfill request_json to Artifacts (Optional)

`request_json` contains the original backtest request. This is relatively small and can remain in PostgreSQL. However, for consistency with the artifact-based architecture:

- Create a new table `backtest_request_artifacts` (or extend existing artifact reference tables)
- Migrate existing `request_json` data to MinIO artifacts
- Update all code paths to read from artifacts instead of `request_json`

**Decision**: Defer this step. `request_json` is small (typically < 1KB) and doesn't cause the same bloat issues as the result arrays. It can remain in PostgreSQL.

#### Step 2: Validate All Backtests Can Be Rehydrated from Artifacts

Before removing any columns, verify that:

1. Every backtest run with non-empty `trades_json`, `position_snapshots_json`, or `daily_pnl_json` has a corresponding artifact in MinIO
2. The artifact contains the complete data
3. The read path can successfully rehydrate the data from artifacts

**Validation Query**:

```sql
-- Find backtest runs with large JSON but no artifact reference
SELECT 
    run_id,
    jsonb_byte_length(trades_json) as trades_size,
    jsonb_byte_length(position_snapshots_json) as snapshots_size,
    jsonb_byte_length(daily_pnl_json) as pnl_size
FROM backtest_runtime_runs
WHERE 
    (jsonb_byte_length(trades_json) > 1000 
     OR jsonb_byte_length(position_snapshots_json) > 1000
     OR jsonb_byte_length(daily_pnl_json) > 1000)
    AND (artifact_reference IS NULL OR artifact_reference = '')
ORDER BY (jsonb_byte_length(trades_json) + 
          jsonb_byte_length(position_snapshots_json) + 
          jsonb_byte_length(daily_pnl_json)) DESC;
```

#### Step 3: Create Data Migration Script

Create a Python script to migrate remaining JSON data to artifacts:

```python
#!/usr/bin/env python3
"""
Backfill script: Migrate remaining JSON data to MinIO artifacts.

This script ensures all backtest runs with non-empty JSON columns have
corresponding artifacts before we remove the columns.

Usage:
    python backfill_artifacts.py --dry-run
    python backfill_artifacts.py --execute
"""

import argparse
import json
from typing import Optional
from datetime import datetime

from sqlalchemy import text, select, update
from sqlalchemy.orm import Session

from bot.src.infrastructure.database import db
from bot.src.infrastructure.storage.minio_artifact_store import MinIOArtifactStore


def get_runs_with_missing_artifacts(session: Session, limit: int = 1000) -> list:
    """Find backtest runs with JSON data but no artifact reference."""
    query = text("""
        SELECT run_id, request_json, trades_json, position_snapshots_json, daily_pnl_json
        FROM backtest_runtime_runs
        WHERE 
            (jsonb_byte_length(trades_json) > 0 
             OR jsonb_byte_length(position_snapshots_json) > 0
             OR jsonb_byte_length(daily_pnl_json) > 0)
            AND (artifact_reference IS NULL OR artifact_reference = '')
        LIMIT :limit
    """)
    result = session.execute(query, {"limit": limit})
    return result.fetchall()


def create_artifact_from_json(
    store: MinIOArtifactStore,
    run_id: str,
    data: dict,
    artifact_type: str
) -> Optional[str]:
    """Create an artifact from JSON data and return the reference."""
    try:
        key = f"backtest/{run_id}/{artifact_type}.json"
        content = json.dumps(data).encode('utf-8')
        store.write(key, content)
        return key
    except Exception as e:
        print(f"Failed to create artifact for {run_id}/{artifact_type}: {e}")
        return None


def migrate_run_to_artifacts(session: Session, store: MinIOArtifactStore, run: tuple) -> bool:
    """Migrate a single run's JSON data to artifacts."""
    run_id, request_json, trades_json, snapshots_json, pnl_json = run
    
    artifacts = {}
    
    # Migrate trades
    if trades_json and len(trades_json) > 0:
        key = create_artifact_from_json(store, run_id, trades_json, "trades")
        if key:
            artifacts["trades"] = key
    
    # Migrate position snapshots
    if snapshots_json and len(snapshots_json) > 0:
        key = create_artifact_from_json(store, run_id, snapshots_json, "position_snapshots")
        if key:
            artifacts["position_snapshots"] = key
    
    # Migrate daily PnL
    if pnl_json and len(pnl_json) > 0:
        key = create_artifact_from_json(store, run_id, pnl_json, "daily_pnl")
        if key:
            artifacts["daily_pnl"] = key
    
    if not artifacts:
        return False
    
    # Update the run with artifact references
    artifact_ref = json.dumps(artifacts)
    update_query = text("""
        UPDATE backtest_runtime_runs
        SET artifact_reference = :artifact_ref
        WHERE run_id = :run_id
    """)
    session.execute(update_query, {"artifact_ref": artifact_ref, "run_id": run_id})
    session.commit()
    return True


def main():
    parser = argparse.ArgumentParser(description="Backfill artifacts for backtest runs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without making changes")
    parser.add_argument("--execute", action="store_true", help="Execute the migration")
    parser.add_argument("--limit", type=int, default=1000, help="Max runs to process")
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        parser.error("Must specify either --dry-run or --execute")
    
    store = MinIOArtifactStore()
    if not store.is_available():
        print("MinIO artifact store is not available")
        return 1
    
    session = db.get_session()
    try:
        runs = get_runs_with_missing_artifacts(session, args.limit)
        print(f"Found {len(runs)} runs with JSON data but no artifacts")
        
        if args.dry_run:
            total_size = 0
            for run in runs:
                _, _, trades, snapshots, pnl = run
                size = (len(json.dumps(trades)) if trades else 0) + \
                       (len(json.dumps(snapshots)) if snapshots else 0) + \
                       (len(json.dumps(pnl)) if pnl else 0)
                total_size += size
                print(f"  {run[0]}: {size / 1024 / 1024:.2f} MB")
            print(f"Total data to migrate: {total_size / 1024 / 1024:.2f} MB")
            return 0
        
        if args.execute:
            migrated = 0
            failed = 0
            for run in runs:
                try:
                    if migrate_run_to_artifacts(session, store, run):
                        migrated += 1
                        print(f"Migrated: {run[0]}")
                    else:
                        print(f"Skipped (no data): {run[0]}")
                except Exception as e:
                    failed += 1
                    print(f"Failed: {run[0]}: {e}")
                    session.rollback()
            
            print(f"\nMigration complete: {migrated} migrated, {failed} failed")
            return 0
    
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

### Phase 3B: Schema Cleanup (After Data Migration)

#### Step 4: Create Migration to Drop Legacy Columns

After validating that all data is safely migrated to artifacts:

```sql
-- Migration: 0000XX_drop_legacy_json_columns_from_backtest_runs.up.sql

-- First, verify no runs have non-empty legacy JSON columns
DO $$
BEGIN
    -- This will raise an exception if any non-empty JSON columns exist
    PERFORM 1 FROM backtest_runtime_runs 
    WHERE jsonb_byte_length(trades_json) > 0 
       OR jsonb_byte_length(position_snapshots_json) > 0 
       OR jsonb_byte_length(daily_pnl_json) > 0;
    
    IF FOUND THEN
        RAISE EXCEPTION 'Legacy JSON columns still contain data. Run backfill script first.';
    END IF;
END $$;

-- Drop the legacy JSON columns
ALTER TABLE backtest_runtime_runs 
    DROP COLUMN IF EXISTS trades_json,
    DROP COLUMN IF EXISTS position_snapshots_json,
    DROP COLUMN IF EXISTS daily_pnl_json;

-- Similarly for backtest_run_requests
ALTER TABLE backtest_run_requests 
    DROP COLUMN IF EXISTS request_json;
```

**Note**: The above migration will fail if any data remains, ensuring safety.

#### Step 5: Create Migration to Clean Up request_json

For `request_json`, we have two options:

**Option A: Keep it** (Recommended)
- `request_json` is relatively small (typically < 1KB)
- It contains useful information for debugging
- Removing it provides minimal storage benefit

**Option B: Migrate to Artifacts**
- Consistent with the artifact-based architecture
- All request data in one place
- Slightly more complex to access

**Decision**: Keep `request_json` in PostgreSQL for now. It doesn't cause the bloat issues that the result arrays caused.

## Rollback Plan

### If Migration Fails

1. **During data migration**: No schema changes, just run the backfill again
2. **During schema migration**: The migration will fail if data exists, preventing the DROP
3. **After schema migration**: Restore from backup

### Rollback SQL

```sql
-- To rollback after dropping columns:
-- 1. Restore from backup, OR
-- 2. Re-add the columns and restore data from artifacts

ALTER TABLE backtest_runtime_runs 
    ADD COLUMN trades_json JSONB DEFAULT '[]',
    ADD COLUMN position_snapshots_json JSONB DEFAULT '[]',
    ADD COLUMN daily_pnl_json JSONB DEFAULT '[]';

-- Then run a reverse migration script to populate from artifacts
```

## Validation Plan

### Pre-Migration Validation

1. Run the validation query to confirm all large JSON has artifacts
2. Run the backfill script in dry-run mode
3. Verify MinIO has sufficient capacity
4. Schedule maintenance window (for production)

### Post-Migration Validation

1. Verify all backtests can still be read and displayed
2. Verify artifact download works for all backtests
3. Run analytics queries to ensure no data loss
4. Monitor application logs for errors

## Execution Timeline

| Phase | Task | Estimated Time | Dependencies |
|-------|------|----------------|--------------|
| 3A-1 | Create validation queries | 2 hours | None |
| 3A-2 | Create backfill script | 4 hours | MinIO available |
| 3A-3 | Test backfill on staging | 8 hours | Staging data |
| 3A-4 | Run backfill on production | 24-48 hours | Maintenance window |
| 3B-1 | Create schema migration | 2 hours | Backfill complete |
| 3B-2 | Test migration on staging | 4 hours | Staging DB |
| 3B-3 | Apply migration to production | 2 hours | Maintenance window |

## Files to Create

1. `bot/scripts/backfill_artifacts.py` - Data migration script
2. `bot/migrations/versions/000XX_drop_legacy_json_columns_from_backtest_runs.py` - Alembic migration
3. `bot/migrations/versions/000YY_drop_request_json_from_backtest_requests.py` - Optional migration

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Backfill script fails | Medium | High | Test on staging first, run in batches |
| Data loss during migration | Low | Critical | Validate before dropping columns |
| Downtime during migration | Medium | Medium | Run during maintenance window |
| Artifact storage runs out of space | Low | Medium | Verify capacity before migration |
| Read path breaks after column removal | Medium | High | Test read paths before production migration |

## Decision Record

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-01 | Defer request_json migration | Small size, high debug value, low benefit |
| 2026-07-01 | Require validation before schema changes | Prevents data loss |
| 2026-07-01 | Use backfill script approach | Safer than direct migration |

## Next Steps

1. Implement the validation query
2. Implement and test the backfill script on staging
3. Run validation on production to assess data volume
4. Schedule and execute backfill on production
5. Create and test schema migrations on staging
6. Apply schema migrations to production

---

*Document Version: 1.0*
*Last Updated: 2026-07-01*
*Owner: Platform Team*
