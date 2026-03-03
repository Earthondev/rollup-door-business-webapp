#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_tracker.config import DEFAULT_CONFIG_PATH, load_config
from job_tracker.sheets import get_sheets_service, update_job_status


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Update status for a job row by job_uid")
    p.add_argument("--sheet_id", default="")
    p.add_argument("--job_uid", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    sheet_id = args.sheet_id or cfg.spreadsheet_id
    if not sheet_id:
        raise SystemExit("sheet_id is required (or set spreadsheet_id in config)")

    service = get_sheets_service(cfg.token_path, cfg.client_secrets_path)
    update_job_status(service, sheet_id, args.job_uid, args.status, args.note)
    print(f"updated job_uid={args.job_uid} status={args.status}")


if __name__ == "__main__":
    main()
