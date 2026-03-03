#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rollup_door.config import DEFAULT_CONFIG_PATH, load_config
from rollup_door.sheets import export_tables_to_csv, get_sheets_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export roll-up sheet tabs to CSV backup files")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output_dir", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    if not cfg.spreadsheet_id:
        raise SystemExit("spreadsheet_id is required in config/rollup_door.yaml")

    output_dir = args.output_dir or str(Path(cfg.backup_dir) / datetime.now().strftime("%Y%m%d_%H%M%S"))
    service = get_sheets_service(
        token_path=cfg.token_path,
        client_secrets_path=cfg.client_secrets_path,
        oauth_token_json=cfg.oauth_token_json,
        oauth_client_secrets_json=cfg.oauth_client_secrets_json,
        service_account_json=cfg.google_service_account_json,
        force_service_account=cfg.requires_service_account(),
    )
    files = export_tables_to_csv(service, cfg.spreadsheet_id, output_dir)

    print(f"output_dir={output_dir}")
    for f in files:
        print(f"csv={f}")


if __name__ == "__main__":
    main()
