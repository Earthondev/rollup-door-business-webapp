from __future__ import annotations

from datetime import date
from typing import Any

from .constants import ROLE_KEYWORDS
from .salary import meets_salary_floor

BLOCKED_ROLE_KEYWORDS = [
    "sales",
    "key account",
    "account manager",
    "customer service",
    "call center",
    "crm",
]

CORE_ROLE_TERMS = sorted(set(ROLE_KEYWORDS["chemist"] + ROLE_KEYWORDS["data"]))
CORE_ROLE_TERMS.extend(["quality", "qa", "qc", "iso", "laboratory", "lab", "analyst", "compliance"])


def location_allowed(location: str, allowed_keywords: list[str]) -> bool:
    if not location:
        return True
    low = location.lower()
    return any(k.lower() in low for k in allowed_keywords)


def select_daily_jobs(
    rows: list[dict[str, Any]],
    *,
    target_count: int,
    freshness_days: int,
    salary_floor: int,
    allow_salary_unknown_fallback: bool,
    allowed_locations: list[str],
) -> list[dict[str, Any]]:
    eligible = []
    for row in rows:
        role_text = f"{row.get('role_title', '')} {row.get('keywords_matched', '')}".lower()
        if any(blocked in role_text for blocked in BLOCKED_ROLE_KEYWORDS):
            continue
        if not any(term in role_text for term in CORE_ROLE_TERMS):
            continue
        if int(row.get("fit_score") or 0) < 10:
            continue
        if row.get("freshness_days", freshness_days + 1) > freshness_days:
            continue
        if not location_allowed(row.get("location", ""), allowed_locations):
            continue
        eligible.append(row)

    known_ok = [
        r
        for r in eligible
        if r.get("salary_verified")
        and meets_salary_floor(r.get("salary_min_thb"), r.get("salary_max_thb"), salary_floor)
    ]
    unknown = [r for r in eligible if not r.get("salary_verified")]

    def sort_key(r: dict[str, Any]):
        return (
            int(r.get("fit_score") or 0),
            int(r.get("data_analysis_exposure") or 0),
            -int(r.get("freshness_days") or 999),
        )

    known_ok.sort(key=sort_key, reverse=True)
    unknown.sort(key=sort_key, reverse=True)

    selected: list[dict[str, Any]] = known_ok[:target_count]
    if len(selected) < target_count and allow_salary_unknown_fallback:
        remaining = target_count - len(selected)
        for row in unknown[:remaining]:
            row = dict(row)
            row["notes"] = (row.get("notes") or "") + " | Fallback: salary unknown"
            selected.append(row)

    today = date.today().isoformat()
    for row in selected:
        row.setdefault("status", "New")
        row["last_seen_date"] = today
        row.setdefault("added_date", today)

    return selected
