#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_tracker.config import DEFAULT_CONFIG_PATH, load_config
from job_tracker.sheets import (
    create_spreadsheet,
    get_sheets_service,
    initialize_sheet,
    upsert_jobs,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync selected jobs into Google Sheets")
    p.add_argument("--sheet_id", default="", help="Target Google Spreadsheet ID")
    p.add_argument("--input", default="tmp/jobs_selected.json", help="Selected jobs JSON")
    p.add_argument("--mode", default="upsert", choices=["upsert"])
    p.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    p.add_argument("--create_if_missing", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    service = get_sheets_service(cfg.token_path, cfg.client_secrets_path)

    spreadsheet_id = args.sheet_id or cfg.spreadsheet_id
    if not spreadsheet_id:
        if not args.create_if_missing:
            raise SystemExit("sheet_id is required (or set spreadsheet_id in config)")
        spreadsheet_id, url = create_spreadsheet(service, cfg.spreadsheet_title)
        print(f"created_sheet_id={spreadsheet_id}")
        print(f"sheet_url={url}")
    else:
        initialize_sheet(service, spreadsheet_id)

    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    inserted = upsert_jobs(service, spreadsheet_id, rows, run_date=date.today())

    print(f"sheet_id={spreadsheet_id}")
    print(f"new_rows={inserted}")
    print(f"sheet_url=https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")


if __name__ == "__main__":
    main()
