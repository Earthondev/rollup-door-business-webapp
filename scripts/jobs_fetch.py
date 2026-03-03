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
from job_tracker.constants import BANGKOK_NEARBY_KEYWORDS
from job_tracker.fetchers import collect_candidates
from job_tracker.selection import select_daily_jobs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch and rank jobs for Chemist + Data bridge profile")
    p.add_argument("--date", default=date.today().isoformat(), help="Run date (YYYY-MM-DD)")
    p.add_argument("--sources", default="jobthai,jobsdb,linkedin")
    p.add_argument("--location", default="Bangkok")
    p.add_argument("--freshness_days", type=int, default=None)
    p.add_argument("--target_count", type=int, default=None)
    p.add_argument("--salary_floor", type=int, default=None)
    p.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    p.add_argument("--output", default="tmp/jobs_selected.json")
    p.add_argument("--pool_output", default="tmp/jobs_pool.json")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    run_date = date.fromisoformat(args.date)
    sources = [x.strip() for x in args.sources.split(",") if x.strip()]

    freshness = args.freshness_days if args.freshness_days is not None else cfg.freshness_days
    target = args.target_count if args.target_count is not None else cfg.target_count
    salary_floor = args.salary_floor if args.salary_floor is not None else cfg.salary_floor

    rows = collect_candidates(
        run_date=run_date,
        sources=sources,
        queries=cfg.queries,
        location_scope=args.location,
        salary_floor=salary_floor,
        max_queries_per_source=cfg.max_queries_per_source,
    )

    selected = select_daily_jobs(
        rows,
        target_count=target,
        freshness_days=freshness,
        salary_floor=salary_floor,
        allow_salary_unknown_fallback=cfg.allow_salary_unknown_fallback,
        allowed_locations=cfg.location_keywords or BANGKOK_NEARBY_KEYWORDS,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")

    pool_path = Path(args.pool_output)
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    known = sum(1 for r in selected if r.get("salary_verified"))
    unknown = len(selected) - known

    print(f"pool={len(rows)} selected={len(selected)}")
    print(f"salary_known={known} salary_unknown={unknown}")
    print(f"output={out_path.resolve()}")


if __name__ == "__main__":
    main()
