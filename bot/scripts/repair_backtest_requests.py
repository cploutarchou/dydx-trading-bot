#!/usr/bin/env python3
"""Repair legacy backtest rows that are missing restartable request payloads."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src.shared.env_loader import load_repo_env

load_repo_env(__file__)

from src.infrastructure.database import db
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.use_cases.service_backtest import BacktestService


def _parse_run_ids(values: Iterable[str] | None) -> List[str]:
    if not values:
        return []
    run_ids: List[str] = []
    for raw in values:
        cleaned = str(raw or "").strip()
        if cleaned:
            run_ids.append(cleaned)
    return run_ids


def _should_repair(run_data: Dict[str, Any]) -> bool:
    request = run_data.get("request")
    if isinstance(request, dict) and request:
        return False
    reconstructed = BacktestService._reconstruct_restart_request_payload(run_data)
    return bool(reconstructed)


def _repair_run(
    repository: BacktestRepository, run_data: Dict[str, Any]
) -> tuple[bool, str]:
    run_id = str(run_data.get("run_id") or "").strip()
    if not run_id:
        return False, "missing run_id"

    reconstructed = BacktestService._reconstruct_restart_request_payload(run_data)
    if not reconstructed:
        return False, "insufficient fields to reconstruct request"

    request_payload = dict(run_data.get("request") or {})
    if request_payload:
        return False, "request already present"

    updated = dict(run_data)
    updated["request"] = reconstructed
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()
    repository.save_run(updated)
    return True, "repaired"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing restart request payloads for legacy backtest runs"
    )
    parser.add_argument(
        "--run-id",
        action="append",
        dest="run_ids",
        help="Repair only the specified backtest run id (repeatable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be repaired without writing changes",
    )
    parser.add_argument(
        "--status",
        default=None,
        help="Optional status filter when scanning all runs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_ids = _parse_run_ids(args.run_ids)

    session = db.get_session()
    try:
        repository = BacktestRepository(session)
        if run_ids:
            candidates = []
            for run_id in run_ids:
                run_data = repository.get_run(run_id)
                if run_data is None:
                    print(json.dumps({"run_id": run_id, "status": "missing"}))
                    continue
                candidates.append(run_data)
        else:
            candidates = repository.list_runs(
                limit=None, offset=0, status_filter=args.status
            )

        repaired = 0
        skipped = 0
        inspected = 0

        for run_data in candidates:
            inspected += 1
            run_id = str(run_data.get("run_id") or "").strip()
            if not run_id:
                skipped += 1
                print(
                    json.dumps(
                        {
                            "run_id": None,
                            "status": "skipped",
                            "reason": "missing run_id",
                        }
                    )
                )
                continue

            if not _should_repair(run_data):
                skipped += 1
                print(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "status": "skipped",
                            "reason": "request already present",
                        }
                    )
                )
                continue

            if args.dry_run:
                reconstructed = BacktestService._reconstruct_restart_request_payload(
                    run_data
                )
                print(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "status": "dry_run_repairable",
                            "selected_pairs": reconstructed.get("selected_pairs", []),
                            "pair_count": len(reconstructed.get("pairs", []) or []),
                        }
                    )
                )
                repaired += 1
                continue

            ok, detail = _repair_run(repository, run_data)
            if ok:
                repaired += 1
                print(json.dumps({"run_id": run_id, "status": "repaired"}))
            else:
                skipped += 1
                print(
                    json.dumps(
                        {"run_id": run_id, "status": "skipped", "reason": detail}
                    )
                )

        print(
            json.dumps(
                {
                    "inspected": inspected,
                    "repaired": repaired,
                    "skipped": skipped,
                    "dry_run": bool(args.dry_run),
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
