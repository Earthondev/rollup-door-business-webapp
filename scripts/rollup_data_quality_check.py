#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rollup_door.config import DEFAULT_CONFIG_PATH, load_config
from rollup_door.constants import CASES_HEADERS
from rollup_door.sheets import get_sheets_service, read_table_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check missing-field quality for cases_raw")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--target_missing_pct", type=float, default=10.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    if not cfg.spreadsheet_id:
        raise SystemExit("spreadsheet_id is required in config/rollup_door.yaml")

    service = get_sheets_service(
        token_path=cfg.token_path,
        client_secrets_path=cfg.client_secrets_path,
        oauth_token_json=cfg.oauth_token_json,
        oauth_client_secrets_json=cfg.oauth_client_secrets_json,
        service_account_json=cfg.google_service_account_json,
        force_service_account=cfg.requires_service_account(),
    )
    rows = read_table_rows(service, cfg.spreadsheet_id, "cases_raw")
    if not rows:
        print("cases_count=0")
        print("missing_pct=0.0")
        print("quality_ok=true")
        return

    tracked_fields = [h for h in CASES_HEADERS if h not in {"notes"}]
    total_cells = len(rows) * len(tracked_fields)
    missing_cells = 0

    for row in rows:
        for field in tracked_fields:
            if str(row.get(field, "")).strip() == "":
                missing_cells += 1

    missing_pct = (missing_cells / total_cells) * 100 if total_cells else 0.0
    quality_ok = missing_pct <= args.target_missing_pct

    print(f"cases_count={len(rows)}")
    print(f"missing_cells={missing_cells}")
    print(f"total_cells={total_cells}")
    print(f"missing_pct={missing_pct:.2f}")
    print(f"quality_ok={'true' if quality_ok else 'false'}")


if __name__ == "__main__":
    main()
