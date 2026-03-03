from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from urllib.parse import urlparse, urlunparse


def canonical_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    parsed = parsed._replace(query="", fragment="")
    netloc = parsed.netloc.lower().replace("www.", "")
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    return urlunparse((parsed.scheme or "https", netloc, path, "", "", ""))


def build_job_uid(source: str, company: str, role_title: str, job_url: str) -> str:
    material = "|".join(
        [
            (source or "unknown").strip().lower(),
            (company or "").strip().lower(),
            (role_title or "").strip().lower(),
            canonical_url(job_url),
        ]
    )
    digest = hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]
    return f"{source.upper()}-{digest}"


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def to_iso_date(value: date | datetime | str | None, fallback: date | None = None) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = parse_iso_date(value) if isinstance(value, str) else None
    if parsed:
        return parsed.isoformat()
    return (fallback or date.today()).isoformat()
