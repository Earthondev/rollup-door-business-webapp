#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rollup_door.config import DEFAULT_CONFIG_PATH, load_config, save_spreadsheet_id
from rollup_door.sheets import create_rollup_spreadsheet, get_sheets_service, initialize_rollup_sheet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Google Sheets for roll-up door business web app")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--title", default="")
    parser.add_argument("--sheet_id", default="", help="Initialize existing sheet by id")
    parser.add_argument("--save_to_config", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    service = get_sheets_service(
        token_path=cfg.token_path,
        client_secrets_path=cfg.client_secrets_path,
        service_account_json=cfg.google_service_account_json,
        force_service_account=cfg.requires_service_account(),
    )

    if args.sheet_id:
        initialize_rollup_sheet(service, args.sheet_id)
        spreadsheet_id = args.sheet_id
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    else:
        title = args.title or cfg.spreadsheet_title
        spreadsheet_id, url = create_rollup_spreadsheet(service, title)

    if args.save_to_config:
        save_spreadsheet_id(args.config, spreadsheet_id)

    print(f"spreadsheet_id={spreadsheet_id}")
    print(f"sheet_url={url}")


if __name__ == "__main__":
    main()
