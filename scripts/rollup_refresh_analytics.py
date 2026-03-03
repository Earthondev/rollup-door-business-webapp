#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rollup_door.config import DEFAULT_CONFIG_PATH, load_config
from rollup_door.sheets import get_sheets_service, refresh_analytics_daily


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh analytics_daily from cases_raw")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    if not cfg.spreadsheet_id:
        raise SystemExit("spreadsheet_id is required in config/rollup_door.yaml")

    service = get_sheets_service(
        token_path=cfg.token_path,
        client_secrets_path=cfg.client_secrets_path,
        service_account_json=cfg.google_service_account_json,
        force_service_account=cfg.requires_service_account(),
    )
    refreshed_days = refresh_analytics_daily(
        service=service,
        spreadsheet_id=cfg.spreadsheet_id,
        margin_threshold_pct=cfg.margin_threshold_pct,
    )
    print(f"refreshed_days={refreshed_days}")
    print(f"sheet_url=https://docs.google.com/spreadsheets/d/{cfg.spreadsheet_id}/edit")


if __name__ == "__main__":
    main()
