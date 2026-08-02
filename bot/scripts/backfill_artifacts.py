#!/usr/bin/env python3
"""
Backfill script: Migrate remaining JSON data to MinIO artifacts.

This script ensures all backtest runs with non-empty JSON columns have
corresponding artifacts before we remove the columns.

Usage:
    python scripts/backfill_artifacts.py --dry-run
    python scripts/backfill_artifacts.py --execute
"""

import argparse
import json
from typing import Optional

from sqlalchemy import text

from src.infrastructure.database import db
from src.infrastructure.storage.minio_artifact_store import MinIOArtifactStore


def get_runs_with_missing_artifacts(session, limit: int = 1000) -> list:
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


def migrate_run_to_artifacts(session, store: MinIOArtifactStore, run: tuple) -> bool:
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


def validate_all_runs_have_artifacts(session) -> tuple:
    """Validate that all runs with JSON data have artifacts. Returns (total, missing, total_size_mb)."""
    query = text("""
        SELECT 
            COUNT(*) as total_runs,
            COUNT(CASE WHEN (jsonb_byte_length(trades_json) > 0 
                          OR jsonb_byte_length(position_snapshots_json) > 0
                          OR jsonb_byte_length(daily_pnl_json) > 0)
                       AND (artifact_reference IS NULL OR artifact_reference = '') 
                  THEN 1 END) as missing_artifacts,
            SUM(jsonb_byte_length(trades_json) + 
                jsonb_byte_length(position_snapshots_json) + 
                jsonb_byte_length(daily_pnl_json)) / (1024 * 1024) as total_size_mb
        FROM backtest_runtime_runs
        WHERE jsonb_byte_length(trades_json) > 0 
           OR jsonb_byte_length(position_snapshots_json) > 0
           OR jsonb_byte_length(daily_pnl_json) > 0
    """)
    result = session.execute(query)
    row = result.fetchone()
    if row:
        return int(row[0]), int(row[1]), float(row[2])
    return 0, 0, 0.0


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
        if args.dry_run:
            # First validate overall state
            total_runs, missing, total_size_mb = validate_all_runs_have_artifacts(session)
            print(f"Validation Results:")
            print(f"  Total runs with JSON data: {total_runs}")
            print(f"  Runs missing artifacts: {missing}")
            print(f"  Total data size: {total_size_mb:.2f} MB")

            if missing == 0:
                print("\nAll runs already have artifacts!")
                return 0

            # Show details for first N runs
            runs = get_runs_with_missing_artifacts(session, args.limit)
            print(f"\nFirst {len(runs)} runs to migrate:")
            for run in runs:
                run_id, _, trades, snapshots, pnl = run
                size_kb = (len(json.dumps(trades)) if trades else 0) + \
                          (len(json.dumps(snapshots)) if snapshots else 0) + \
                          (len(json.dumps(pnl)) if pnl else 0)
                print(f"  {run_id}: {size_kb / 1024:.2f} MB")
            return 0

        if args.execute:
            runs = get_runs_with_missing_artifacts(session, args.limit)
            print(f"Found {len(runs)} runs with JSON data but no artifacts")

            if len(runs) == 0:
                print("All runs already have artifacts!")
                return 0

            migrated = 0
            failed = 0
            skipped = 0

            for run in runs:
                try:
                    if migrate_run_to_artifacts(session, store, run):
                        migrated += 1
                        print(f"Migrated: {run[0]}")
                    else:
                        skipped += 1
                        print(f"Skipped (no data): {run[0]}")
                except Exception as e:
                    failed += 1
                    print(f"Failed: {run[0]}: {e}")
                    session.rollback()

            print(f"\nMigration complete: {migrated} migrated, {skipped} skipped, {failed} failed")

            # Re-validate
            total_runs, remaining, total_size_mb = validate_all_runs_have_artifacts(session)
            print(f"\nPost-migration validation:")
            print(f"  Total runs with JSON data: {total_runs}")
            print(f"  Runs still missing artifacts: {remaining}")

            return 0 if failed == 0 else 1

    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
