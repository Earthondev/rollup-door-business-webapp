from __future__ import annotations

from typing import Iterable

from .constants import DATA_EXPOSURE_KEYWORDS, ROLE_KEYWORDS, SKILL_KEYWORDS


def _lower_join(parts: Iterable[str | None]) -> str:
    return " ".join((p or "") for p in parts).lower()


def keyword_hits(text: str, keywords: list[str]) -> list[str]:
    hits = []
    for kw in keywords:
        if kw in text:
            hits.append(kw)
    return sorted(set(hits))


def score_job(
    *,
    role_title: str,
    company: str,
    location: str,
    notes: str,
    freshness_days: int,
    salary_known: bool,
    salary_ok: bool,
) -> tuple[int, int, str, list[str]]:
    text = _lower_join([role_title, company, location, notes])

    chem_hits = keyword_hits(text, ROLE_KEYWORDS["chemist"])
    data_hits = keyword_hits(text, ROLE_KEYWORDS["data"])
    skill_hits = keyword_hits(text, SKILL_KEYWORDS)
    exposure_hits = keyword_hits(text, DATA_EXPOSURE_KEYWORDS)

    role_match = min(40, len(chem_hits) * 5 + len(data_hits) * 3)
    skill_match = min(30, len(skill_hits) * 4)
    data_exposure = min(100, len(exposure_hits) * 8)
    data_score = min(20, int(data_exposure * 0.2))

    freshness = max(0, min(10, int(round((14 - freshness_days) * 10 / 14))))

    score = role_match + skill_match + data_score + freshness
    if salary_known and not salary_ok:
        score -= 15

    score = max(0, min(100, score))

    reason = (
        f"role_match={role_match}, skill_match={skill_match}, "
        f"data_exposure={data_exposure}, freshness={freshness}"
    )
    matches = sorted(set(chem_hits + data_hits + skill_hits))
    return score, data_exposure, reason, matches
