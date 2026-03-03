#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_tracker.config import DEFAULT_CONFIG_PATH, load_config, save_spreadsheet_id
from job_tracker.sheets import create_spreadsheet, get_sheets_service


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create and initialize Google Sheet for job tracker")
    p.add_argument("--title", default="")
    p.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    p.add_argument("--save_to_config", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    service = get_sheets_service(cfg.token_path, cfg.client_secrets_path)

    title = args.title or cfg.spreadsheet_title
    spreadsheet_id, url = create_spreadsheet(service, title)

    if args.save_to_config:
        save_spreadsheet_id(args.config, spreadsheet_id)

    print(f"spreadsheet_id={spreadsheet_id}")
    print(f"sheet_url={url}")


if __name__ == "__main__":
    main()
