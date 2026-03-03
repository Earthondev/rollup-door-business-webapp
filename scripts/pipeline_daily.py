#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_tracker.config import DEFAULT_CONFIG_PATH, load_config, save_spreadsheet_id
from job_tracker.fetchers import collect_candidates
from job_tracker.selection import select_daily_jobs
from job_tracker.sheets import create_spreadsheet, get_sheets_service, upsert_jobs


def setup_logger(logs_dir: str) -> logging.Logger:
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(logs_dir) / f"job_tracker_{date.today().isoformat()}.log"

    logger = logging.getLogger("job_tracker")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, encoding="utf-8")
    sh = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def main() -> None:
    cfg_path = DEFAULT_CONFIG_PATH
    cfg = load_config(cfg_path)
    logger = setup_logger(cfg.logs_dir)

    run_date = date.today()
    logger.info("Daily pipeline started")

    candidates = collect_candidates(
        run_date=run_date,
        sources=cfg.sources,
        queries=cfg.queries,
        location_scope=cfg.location_scope,
        salary_floor=cfg.salary_floor,
        max_queries_per_source=cfg.max_queries_per_source,
    )
    logger.info("Collected candidates: %s", len(candidates))

    selected = select_daily_jobs(
        candidates,
        target_count=cfg.target_count,
        freshness_days=cfg.freshness_days,
        salary_floor=cfg.salary_floor,
        allow_salary_unknown_fallback=cfg.allow_salary_unknown_fallback,
        allowed_locations=cfg.location_keywords,
    )
    logger.info("Selected jobs: %s", len(selected))

    Path("tmp").mkdir(exist_ok=True)
    Path("tmp/jobs_selected.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    service = get_sheets_service(cfg.token_path, cfg.client_secrets_path)
    spreadsheet_id = cfg.spreadsheet_id
    if not spreadsheet_id:
        spreadsheet_id, url = create_spreadsheet(service, cfg.spreadsheet_title)
        save_spreadsheet_id(cfg_path, spreadsheet_id)
        logger.info("Created spreadsheet: %s", url)

    new_rows = upsert_jobs(service, spreadsheet_id, selected, run_date=run_date)
    logger.info("Sheet updated: spreadsheet_id=%s new_rows=%s", spreadsheet_id, new_rows)
    logger.info("Done")


if __name__ == "__main__":
    main()
