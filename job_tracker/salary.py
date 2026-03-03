from __future__ import annotations

import re
from dataclasses import dataclass


_UNKNOWN_MARKERS = [
    "negotiable",
    "ตามตกลง",
    "ตามโครงสร้าง",
    "ตามประสบการณ์",
    "as experience",
    "not specified",
    "n/a",
    "ขึ้นอยู่กับ",
]


@dataclass
class SalaryParseResult:
    min_thb: int | None
    max_thb: int | None
    verified: bool


def _to_int(num: str) -> int:
    return int(num.replace(",", ""))


def parse_salary_text(raw: str | None) -> SalaryParseResult:
    text = (raw or "").strip()
    if not text:
        return SalaryParseResult(None, None, False)

    lower = text.lower()
    if any(marker in lower for marker in _UNKNOWN_MARKERS):
        return SalaryParseResult(None, None, False)

    nums = re.findall(r"\d{1,3}(?:,\d{3})+|\d{4,6}", text)
    values = [_to_int(n) for n in nums if 5000 <= _to_int(n) <= 500000]

    if not values:
        return SalaryParseResult(None, None, False)

    range_match = re.search(
        r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*(?:-|–|ถึง|to)\s*(\d{1,3}(?:,\d{3})+|\d{4,6})",
        lower,
    )
    if range_match:
        lo = _to_int(range_match.group(1))
        hi = _to_int(range_match.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return SalaryParseResult(lo, hi, True)

    if len(values) >= 2:
        lo, hi = min(values), max(values)
        if lo != hi:
            return SalaryParseResult(lo, hi, True)

    return SalaryParseResult(values[0], None, True)


def meets_salary_floor(min_thb: int | None, max_thb: int | None, floor: int) -> bool:
    if min_thb is None and max_thb is None:
        return False
    return (min_thb or 0) >= floor or (max_thb or 0) >= floor
