from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .scoring import score_job
from .salary import meets_salary_floor, parse_salary_text
from .utils import build_job_uid, canonical_url, parse_iso_date, to_iso_date

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

SOURCE_DOMAINS = {
    "jobthai": "jobthai.com",
    "jobsdb": "jobsdb.com",
    "linkedin": "linkedin.com/jobs",
}

DEFAULT_FALLBACK_FILES = [
    Path("tmp/selected_jobs.json"),
    Path("/Users/earthondev/Desktop/Misc/untitled folder/tmp/selected_jobs.json"),
]

TH_MONTHS = {
    "ม.ค.": 1,
    "ก.พ.": 2,
    "มี.ค.": 3,
    "เม.ย.": 4,
    "พ.ค.": 5,
    "มิ.ย.": 6,
    "ก.ค.": 7,
    "ส.ค.": 8,
    "ก.ย.": 9,
    "ต.ค.": 10,
    "พ.ย.": 11,
    "ธ.ค.": 12,
}


# -------------------- Generic helpers --------------------

def _decode_ddg_link(raw_url: str) -> str:
    if not raw_url:
        return ""
    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url
    if raw_url.startswith("/") and "uddg=" in raw_url:
        parsed = urlparse("https://duckduckgo.com" + raw_url)
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        return uddg
    parsed = urlparse(raw_url)
    if parsed.netloc.endswith("duckduckgo.com"):
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        if uddg:
            return uddg
    return raw_url


def _guess_source_from_url(url: str) -> str:
    low = url.lower()
    if "jobthai" in low:
        return "jobthai"
    if "jobsdb" in low:
        return "jobsdb"
    if "linkedin.com/jobs" in low:
        return "linkedin"
    return "unknown"


def _extract_company(title: str) -> str:
    parts = re.split(r"\s[-|–]\s", title)
    if len(parts) >= 2:
        return parts[-1].strip()
    return ""


def _extract_salary_text(text: str) -> str:
    match = re.search(
        r"(\d{1,3}(?:,\d{3})+\s*(?:-|–|to|ถึง)\s*\d{1,3}(?:,\d{3})+\s*(?:บาท|thb)?)",
        text,
        flags=re.I,
    )
    if match:
        return match.group(1)
    for marker in ["ตามตกลง", "negotiable", "ตามประสบการณ์", "ตามโครงสร้าง"]:
        if marker in text.lower() or marker in text:
            return marker
    return ""


def _extract_location(text: str) -> str:
    patterns = [
        r"(Bangkok(?:[^\n,.|;]*)?)",
        r"(กรุงเทพ[^\n,.|;]*)",
        r"(นนทบุรี[^\n,.|;]*)",
        r"(ปทุม[^\n,.|;]*)",
        r"(สมุทรปราการ[^\n,.|;]*)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return m.group(1).strip()
    return ""


def _extract_date_and_freshness(text: str, run_date: date) -> tuple[str, int]:
    low = text.lower()

    iso = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if iso:
        d = parse_iso_date(iso.group(1))
        if d:
            return d.isoformat(), max(0, (run_date - d).days)

    rel = re.search(r"(\d{1,2})\s*(day|days|d)\s*ago", low)
    if rel:
        days = int(rel.group(1))
        d = run_date.fromordinal(run_date.toordinal() - days)
        return d.isoformat(), days

    rel_th = re.search(r"(\d{1,2})\s*วัน", text)
    if rel_th and "ที่ผ่านมา" in text:
        days = int(rel_th.group(1))
        d = run_date.fromordinal(run_date.toordinal() - days)
        return d.isoformat(), days

    return run_date.isoformat(), 0


def _freshness_from_relative(text: str, run_date: date) -> tuple[str, int]:
    t = (text or "").strip().lower()
    if not t:
        return run_date.isoformat(), 0

    m = re.search(r"(\d+)\s*day", t)
    if m:
        days = int(m.group(1))
        d = run_date.fromordinal(run_date.toordinal() - days)
        return d.isoformat(), days

    m = re.search(r"(\d+)\s*week", t)
    if m:
        days = int(m.group(1)) * 7
        d = run_date.fromordinal(run_date.toordinal() - days)
        return d.isoformat(), days

    m = re.search(r"(\d+)\s*month", t)
    if m:
        days = int(m.group(1)) * 30
        d = run_date.fromordinal(run_date.toordinal() - days)
        return d.isoformat(), days

    m = re.search(r"(\d+)\s*ชั่วโมง", t)
    if m:
        return run_date.isoformat(), 0

    m = re.search(r"(\d+)\s*วัน", t)
    if m:
        days = int(m.group(1))
        d = run_date.fromordinal(run_date.toordinal() - days)
        return d.isoformat(), days

    return run_date.isoformat(), 0


def _extract_jobsdb_state(html: str) -> dict[str, Any] | None:
    key = "window.SEEK_REDUX_DATA = "
    start = html.find(key)
    if start == -1:
        return None

    i = start + len(key)
    begin = None
    depth = 0
    in_str = False
    esc = False
    end = None

    for idx, ch in enumerate(html[i:], start=i):
        if begin is None:
            if ch == "{":
                begin = idx
                depth = 1
            continue

        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break

    if begin is None or end is None:
        return None

    try:
        return json.loads(html[begin:end])
    except json.JSONDecodeError:
        return None


def _find_jobsdb_jobs(x: Any) -> list[dict[str, Any]]:
    if isinstance(x, dict):
        for _, v in x.items():
            if (
                isinstance(v, list)
                and v
                and isinstance(v[0], dict)
                and "title" in v[0]
                and "companyName" in v[0]
                and "id" in v[0]
            ):
                return v
            found = _find_jobsdb_jobs(v)
            if found:
                return found
    elif isinstance(x, list):
        for it in x:
            found = _find_jobsdb_jobs(it)
            if found:
                return found
    return []


def _parse_jobthai_posted(text: str, run_date: date) -> tuple[str, int]:
    m = re.search(r"(\d{1,2})\s*(ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)\s*(\d{2})", text)
    if not m:
        return run_date.isoformat(), 0

    day = int(m.group(1))
    month = TH_MONTHS.get(m.group(2), run_date.month)
    yy = int(m.group(3))
    year = 1957 + yy  # Thai BE short year to CE (e.g. 69 -> 2026)

    try:
        d = date(year, month, day)
    except ValueError:
        return run_date.isoformat(), 0

    freshness = max(0, (run_date - d).days)
    return d.isoformat(), freshness


# -------------------- Source-specific fetchers --------------------

def fetch_jobthai_source(
    queries: list[str],
    location: str,
    run_date: date,
    *,
    max_queries: int = 3,
) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    out: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for q in queries[:max_queries]:
        url = (
            "https://www.jobthai.com/th/jobs?"
            f"keyword={quote_plus(q)}&location={quote_plus(location)}"
        )
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select('a[href*="/th/company/job/"]'):
            href = a.get("href", "")
            job_url = canonical_url(urljoin("https://www.jobthai.com", href))
            if not job_url or job_url in seen_urls:
                continue

            title_el = a.select_one('[id^="job-card-item-"]') or a.select_one("h2")
            company_el = a.select_one('[id^="job-list-company-name-"]')
            location_el = a.select_one("#location-text")
            salary_el = a.select_one("#salary-text")

            title = title_el.get_text(" ", strip=True) if title_el else a.get_text(" ", strip=True)[:140]
            company = company_el.get_text(" ", strip=True) if company_el else ""
            location_text = location_el.get_text(" ", strip=True) if location_el else ""
            salary_text = salary_el.get_text(" ", strip=True) if salary_el else ""

            card_text = a.get_text(" ", strip=True)
            posted_date, freshness_days = _parse_jobthai_posted(card_text, run_date)

            out.append(
                {
                    "source": "jobthai",
                    "role_title": title,
                    "company": company,
                    "job_url": job_url,
                    "location": location_text,
                    "work_mode": "Onsite",
                    "salary_text_raw": salary_text,
                    "posted_date": posted_date,
                    "freshness_days": freshness_days,
                    "notes": f"query={q}",
                }
            )
            seen_urls.add(job_url)

    return out


def fetch_jobsdb_source(
    queries: list[str],
    run_date: date,
    *,
    max_queries: int = 3,
) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for q in queries[:max_queries]:
        slug = quote_plus(q).replace("+", "-")
        url = f"https://th.jobsdb.com/th/{slug}-jobs/in-Bangkok"
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            continue

        state = _extract_jobsdb_state(resp.text)
        if not state:
            continue

        jobs = _find_jobsdb_jobs(state)
        for job in jobs:
            job_id = str(job.get("id", "")).strip()
            if not job_id or job_id in seen_ids:
                continue

            listing_iso = to_iso_date(job.get("listingDate"), fallback=run_date)
            listed = parse_iso_date(listing_iso) or run_date
            freshness = max(0, (run_date - listed).days)

            loc = ""
            locations = job.get("locations") or []
            if locations and isinstance(locations[0], dict):
                loc = locations[0].get("label", "")

            work_mode = "Unknown"
            work_arr = job.get("workArrangements") or {}
            if isinstance(work_arr, dict):
                data = work_arr.get("data") or []
                if data and isinstance(data[0], dict):
                    work_mode = data[0].get("label", "Unknown")

            out.append(
                {
                    "source": "jobsdb",
                    "role_title": job.get("title", ""),
                    "company": job.get("companyName", ""),
                    "job_url": canonical_url(f"https://th.jobsdb.com/th/job/{job_id}"),
                    "location": loc,
                    "work_mode": work_mode,
                    "salary_text_raw": job.get("salaryLabel", ""),
                    "posted_date": listing_iso,
                    "freshness_days": freshness,
                    "notes": f"query={q}; listing={job.get('listingDateDisplay', '')}",
                }
            )
            seen_ids.add(job_id)

    return out


def fetch_linkedin_source(
    queries: list[str],
    location: str,
    run_date: date,
    *,
    max_queries: int = 3,
) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    out: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for q in queries[:max_queries]:
        url = (
            "https://www.linkedin.com/jobs/search/?"
            f"keywords={quote_plus(q)}&location={quote_plus(location)}"
        )
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("li"):
            a = card.select_one("a.base-card__full-link")
            if not a:
                continue

            job_url = canonical_url(a.get("href", ""))
            if not job_url or job_url in seen_urls:
                continue

            title = a.get_text(" ", strip=True)
            company_el = card.select_one("h4.base-search-card__subtitle")
            location_el = card.select_one("span.job-search-card__location")
            time_el = card.select_one("time")

            company = company_el.get_text(" ", strip=True) if company_el else ""
            location_text = location_el.get_text(" ", strip=True) if location_el else ""

            posted_date = run_date.isoformat()
            freshness = 0
            if time_el and time_el.get("datetime"):
                posted_date = to_iso_date(time_el.get("datetime"), fallback=run_date)
                d = parse_iso_date(posted_date) or run_date
                freshness = max(0, (run_date - d).days)
            elif time_el:
                posted_date, freshness = _freshness_from_relative(time_el.get_text(" ", strip=True), run_date)

            out.append(
                {
                    "source": "linkedin",
                    "role_title": title,
                    "company": company,
                    "job_url": job_url,
                    "location": location_text,
                    "work_mode": "Unknown",
                    "salary_text_raw": "",
                    "posted_date": posted_date,
                    "freshness_days": freshness,
                    "notes": f"query={q}",
                }
            )
            seen_urls.add(job_url)

    return out


# -------------------- Optional search-engine fallback --------------------

def fetch_duckduckgo_source(
    source: str, queries: list[str], location: str, *, max_queries: int = 2
) -> list[dict[str, Any]]:
    domain = SOURCE_DOMAINS[source]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    out: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for q in queries[:max_queries]:
        full_query = f'site:{domain} "{q}" "{location}"'
        url = f"https://duckduckgo.com/html/?q={quote_plus(full_query)}"
        try:
            resp = session.get(url, timeout=8)
            resp.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for result in soup.select(".result"):
            a = result.select_one(".result__a")
            if not a:
                continue
            raw_url = a.get("href", "")
            decoded = canonical_url(_decode_ddg_link(raw_url))
            if not decoded or decoded in seen_urls:
                continue
            if source not in _guess_source_from_url(decoded):
                continue

            title = a.get_text(" ", strip=True)
            snippet_el = result.select_one(".result__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            out.append(
                {
                    "source": source,
                    "role_title": title,
                    "company": _extract_company(title),
                    "job_url": decoded,
                    "location": _extract_location(snippet),
                    "work_mode": "Unknown",
                    "salary_text_raw": _extract_salary_text(snippet),
                    "posted_date": "",
                    "freshness_days": None,
                    "notes": f"query={q}; snippet={snippet[:220]}",
                }
            )
            seen_urls.add(decoded)

    return out


def fetch_bing_source(
    source: str, queries: list[str], location: str, *, max_queries: int = 2
) -> list[dict[str, Any]]:
    domain = SOURCE_DOMAINS[source]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    out: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for q in queries[:max_queries]:
        full_query = f'site:{domain} "{q}" "{location}"'
        url = f"https://www.bing.com/search?q={quote_plus(full_query)}&count=15"
        try:
            resp = session.get(url, timeout=8)
            resp.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for result in soup.select("li.b_algo"):
            a = result.select_one("h2 a")
            if not a:
                continue
            decoded = canonical_url(a.get("href", ""))
            if not decoded or decoded in seen_urls:
                continue
            if source not in _guess_source_from_url(decoded):
                continue

            title = a.get_text(" ", strip=True)
            snippet_el = result.select_one(".b_caption p")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            out.append(
                {
                    "source": source,
                    "role_title": title,
                    "company": _extract_company(title),
                    "job_url": decoded,
                    "location": _extract_location(snippet),
                    "work_mode": "Unknown",
                    "salary_text_raw": _extract_salary_text(snippet),
                    "posted_date": "",
                    "freshness_days": None,
                    "notes": f"query={q}; snippet={snippet[:220]}",
                }
            )
            seen_urls.add(decoded)

    return out


# -------------------- Enrichment + normalization --------------------

def enrich_job_page(raw: dict[str, Any], run_date: date) -> dict[str, Any]:
    url = raw.get("job_url", "")
    if not url:
        return raw

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    try:
        resp = session.get(url, timeout=8, allow_redirects=True)
        if resp.status_code >= 400:
            return raw
        text = resp.text
    except requests.RequestException:
        return raw

    soup = BeautifulSoup(text, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    if not raw.get("salary_text_raw"):
        raw["salary_text_raw"] = _extract_salary_text(page_text)
    if not raw.get("location"):
        raw["location"] = _extract_location(page_text)
    if not raw.get("posted_date"):
        posted_date, freshness = _extract_date_and_freshness(page_text, run_date)
        raw["posted_date"] = posted_date
        raw["freshness_days"] = freshness

    return raw


def load_fallback_rows() -> list[dict[str, Any]]:
    for path in DEFAULT_FALLBACK_FILES:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
    return []


def _normalize_row(row: dict[str, Any], run_date: date, salary_floor: int) -> dict[str, Any]:
    posted = parse_iso_date(row.get("posted_date")) or run_date
    freshness = row.get("freshness_days")
    if freshness is None:
        freshness = max(0, (run_date - posted).days)

    salary_raw = row.get("salary_text_raw") or row.get("salary_text") or ""
    parsed = parse_salary_text(salary_raw)

    score, data_exposure, fit_reason, matches = score_job(
        role_title=row.get("role_title") or row.get("role") or "",
        company=row.get("company", ""),
        location=row.get("location", ""),
        notes=row.get("description", ""),
        freshness_days=int(freshness),
        salary_known=parsed.verified,
        salary_ok=meets_salary_floor(parsed.min_thb, parsed.max_thb, salary_floor),
    )

    source = row.get("source", "unknown")
    job_url = row.get("job_url", "")
    role_title = row.get("role_title") or row.get("role") or "Untitled Role"

    return {
        "job_uid": build_job_uid(source, row.get("company", ""), role_title, job_url),
        "role_title": role_title,
        "company": row.get("company", ""),
        "source": source,
        "job_url": job_url,
        "location": row.get("location", ""),
        "work_mode": row.get("work_mode", "Unknown"),
        "posted_date": to_iso_date(posted),
        "freshness_days": int(freshness),
        "salary_min_thb": parsed.min_thb,
        "salary_max_thb": parsed.max_thb,
        "salary_text_raw": salary_raw,
        "salary_verified": bool(parsed.verified),
        "fit_score": score,
        "fit_reason": fit_reason,
        "data_analysis_exposure": data_exposure,
        "keywords_matched": ", ".join(matches),
        "status": row.get("status", "New"),
        "last_seen_date": run_date.isoformat(),
        "added_date": row.get("added_date") or run_date.isoformat(),
        "notes": row.get("notes", ""),
    }


def collect_candidates(
    *,
    run_date: date,
    sources: list[str],
    queries: list[str],
    location_scope: str,
    salary_floor: int,
    enrich_limit: int = 10,
    max_queries_per_source: int = 3,
    max_runtime_seconds: int = 45,
) -> list[dict[str, Any]]:
    raw_rows: list[dict[str, Any]] = []
    started = time.monotonic()

    for source in sources:
        if time.monotonic() - started > max_runtime_seconds:
            break

        if source == "jobthai":
            raw_rows.extend(
                fetch_jobthai_source(
                    queries,
                    location_scope,
                    run_date,
                    max_queries=max_queries_per_source,
                )
            )
        elif source == "jobsdb":
            raw_rows.extend(
                fetch_jobsdb_source(
                    queries,
                    run_date,
                    max_queries=max_queries_per_source,
                )
            )
        elif source == "linkedin":
            raw_rows.extend(
                fetch_linkedin_source(
                    queries,
                    location_scope,
                    run_date,
                    max_queries=max_queries_per_source,
                )
            )

    # Search-engine fallback only when direct source parsing yields too few rows.
    if len(raw_rows) < 15:
        for source in sources:
            raw_rows.extend(fetch_duckduckgo_source(source, queries, location_scope, max_queries=2))
            if len(raw_rows) >= 20:
                break
            raw_rows.extend(fetch_bing_source(source, queries, location_scope, max_queries=2))
            if len(raw_rows) >= 20:
                break

    # Optional enrichment for rows missing critical fields.
    enrich_candidates = [r for r in raw_rows if not r.get("salary_text_raw") or not r.get("location")]
    for row in enrich_candidates[:enrich_limit]:
        enrich_job_page(row, run_date)

    # Fallback seed data when sources are unavailable.
    if len(raw_rows) < 10:
        for row in load_fallback_rows():
            source = row.get("source", "")
            if "jobthai" not in source.lower() and "jobsdb" not in source.lower() and "linkedin" not in source.lower():
                continue
            raw_rows.append(
                {
                    "source": "jobthai" if "jobthai" in source.lower() else "jobsdb" if "jobsdb" in source.lower() else "linkedin",
                    "role_title": row.get("role", ""),
                    "company": row.get("company", ""),
                    "job_url": row.get("job_url", ""),
                    "location": row.get("location", ""),
                    "work_mode": row.get("work_mode", "Unknown"),
                    "salary_text_raw": row.get("salary_text", ""),
                    "posted_date": row.get("posted_date", ""),
                    "freshness_days": row.get("freshness_days"),
                    "notes": row.get("notes", ""),
                }
            )

    out: list[dict[str, Any]] = []
    seen_uid: set[str] = set()
    for row in raw_rows:
        normalized = _normalize_row(row, run_date, salary_floor)
        uid = normalized["job_uid"]
        if uid in seen_uid:
            continue
        seen_uid.add(uid)
        out.append(normalized)

    return out
