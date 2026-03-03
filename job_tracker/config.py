from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TrackerConfig:
    timezone: str
    sources: list[str]
    queries: list[str]
    location_scope: str
    location_keywords: list[str]
    freshness_days: int
    target_count: int
    salary_floor: int
    allow_salary_unknown_fallback: bool
    max_queries_per_source: int
    spreadsheet_title: str
    spreadsheet_id: str
    token_path: str
    client_secrets_path: str
    logs_dir: str


DEFAULT_CONFIG_PATH = Path("config/job_tracker.yaml")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> TrackerConfig:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    raw: dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

    return TrackerConfig(
        timezone=raw.get("timezone", "Asia/Bangkok"),
        sources=list(raw.get("sources", ["jobthai", "jobsdb", "linkedin"])),
        queries=list(raw.get("queries", [])),
        location_scope=raw.get("location_scope", "bangkok"),
        location_keywords=list(raw.get("location_keywords", [])),
        freshness_days=int(raw.get("freshness_days", 14)),
        target_count=int(raw.get("target_count", 10)),
        salary_floor=int(raw.get("salary_floor", 30000)),
        allow_salary_unknown_fallback=bool(raw.get("allow_salary_unknown_fallback", True)),
        max_queries_per_source=int(raw.get("max_queries_per_source", 3)),
        spreadsheet_title=raw.get("spreadsheet_title", "Nattapart_Job_Tracker_2026"),
        spreadsheet_id=raw.get("spreadsheet_id", ""),
        token_path=raw.get("google", {}).get("token_path", "credentials/job_tracker_token.json"),
        client_secrets_path=raw.get("google", {}).get("client_secrets_path", "credentials/client_secrets.json"),
        logs_dir=raw.get("logs_dir", "logs"),
    )


def save_spreadsheet_id(path: str | Path, spreadsheet_id: str) -> None:
    cfg_path = Path(path)
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    raw["spreadsheet_id"] = spreadsheet_id
    cfg_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
