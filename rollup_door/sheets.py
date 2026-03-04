from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .constants import (
    ANALYTICS_DAILY_HEADERS,
    CASES_HEADERS,
    DEFAULT_KNOWLEDGE,
    DEFAULT_LOOKUPS,
    DEFAULT_PRICING_REFERENCE,
    DEFAULT_STUDY_LOOKUPS,
    TAB_HEADERS,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _load_oauth_credentials(token_path: str, client_secrets_path: str) -> Credentials:
    creds: Credentials | None = None
    token_file = Path(token_path)

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if not Path(client_secrets_path).exists():
                raise FileNotFoundError(
                    "Google OAuth client secrets not found. "
                    f"Expected: {client_secrets_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            try:
                creds = flow.run_local_server(port=0)
            except Exception:
                creds = flow.run_console()

        _ensure_parent(token_path)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return creds


def get_sheets_service(
    token_path: str,
    client_secrets_path: str,
    oauth_token_json: str = "",
    oauth_client_secrets_json: str = "",
    service_account_json: str = "",
    force_service_account: bool = False,
):
    if service_account_json.strip():
        try:
            service_account_info = json.loads(service_account_json)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid_google_service_account_json") from exc
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=SCOPES,
        )
    else:
        if force_service_account:
            raise RuntimeError("missing_google_service_account")
        if oauth_token_json.strip():
            try:
                oauth_info = json.loads(oauth_token_json)
            except json.JSONDecodeError as exc:
                raise ValueError("invalid_google_oauth_token_json") from exc
            creds = Credentials.from_authorized_user_info(oauth_info, SCOPES)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
        elif oauth_client_secrets_json.strip():
            try:
                secrets_info = json.loads(oauth_client_secrets_json)
            except json.JSONDecodeError as exc:
                raise ValueError("invalid_google_client_secrets_json") from exc
            _ensure_parent(client_secrets_path)
            Path(client_secrets_path).write_text(
                json.dumps(secrets_info, ensure_ascii=False),
                encoding="utf-8",
            )
            creds = _load_oauth_credentials(token_path, client_secrets_path)
        else:
            creds = _load_oauth_credentials(token_path, client_secrets_path)

    return build("sheets", "v4", credentials=creds)



def _execute_with_retry(fn, retries: int = 3, sleep_seconds: float = 0.6):
    last_err = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:  # pragma: no cover - external API behavior
            last_err = exc
            if attempt == retries - 1:
                raise
            time.sleep(sleep_seconds * (attempt + 1))
    if last_err is not None:
        raise last_err



def _to_sheet_row(row: dict[str, Any], headers: list[str]) -> list[Any]:
    values: list[Any] = []
    for h in headers:
        value = row.get(h, "")
        if value is None:
            values.append("")
        elif isinstance(value, (dict, list, tuple)):
            values.append(json.dumps(value, ensure_ascii=False))
        else:
            values.append(value)
    return values



def _to_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0



def _safe_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        if "T" in cleaned:
            return datetime.fromisoformat(cleaned).date()
        return date.fromisoformat(cleaned)
    except ValueError:
        return None



def _sheet_metadata(service, spreadsheet_id: str) -> dict[str, Any]:
    return _execute_with_retry(lambda: service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute())



def _sheet_title_to_id(metadata: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        title = props.get("title")
        sheet_id = props.get("sheetId")
        if title is not None and sheet_id is not None:
            out[str(title)] = int(sheet_id)
    return out



def _column_letter(index: int) -> str:
    if index <= 0:
        raise ValueError("invalid_column_index")

    letters = []
    n = index
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def create_rollup_spreadsheet(service, title: str) -> tuple[str, str]:
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": tab}} for tab in TAB_HEADERS.keys()],
    }
    resp = _execute_with_retry(
        lambda: service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    )
    spreadsheet_id = resp["spreadsheetId"]
    initialize_rollup_sheet(service, spreadsheet_id)
    return spreadsheet_id, f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"



def initialize_rollup_sheet(service, spreadsheet_id: str) -> None:
    metadata = _sheet_metadata(service, spreadsheet_id)
    title_to_id = _sheet_title_to_id(metadata)

    add_requests = []
    for tab in TAB_HEADERS.keys():
        if tab not in title_to_id:
            add_requests.append({"addSheet": {"properties": {"title": tab}}})

    if add_requests:
        _execute_with_retry(
            lambda: service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": add_requests},
            ).execute()
        )
        metadata = _sheet_metadata(service, spreadsheet_id)
        title_to_id = _sheet_title_to_id(metadata)

    format_requests: list[dict[str, Any]] = []

    for tab, headers in TAB_HEADERS.items():
        _execute_with_retry(
            lambda tab=tab, headers=headers: service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{tab}!A1",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()
        )

        sheet_id = title_to_id.get(tab)
        if sheet_id is None:
            continue
        format_requests.extend(
            [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(headers),
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "backgroundColor": {
                                    "red": 0.88,
                                    "green": 0.92,
                                    "blue": 0.96,
                                },
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor)",
                    }
                },
            ]
        )

    if format_requests:
        _execute_with_retry(
            lambda: service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": format_requests},
            ).execute()
        )

    _seed_defaults_if_empty(service, spreadsheet_id)



def _seed_defaults_if_empty(service, spreadsheet_id: str) -> None:
    seeded = {
        "lookups": DEFAULT_LOOKUPS,
        "pricing_reference": DEFAULT_PRICING_REFERENCE,
        "knowledge_qna": DEFAULT_KNOWLEDGE,
        "study_lookups": DEFAULT_STUDY_LOOKUPS,
    }
    for tab, rows in seeded.items():
        current = read_table_rows(service, spreadsheet_id, tab)
        if current:
            continue
        _execute_with_retry(
            lambda tab=tab, rows=rows: service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{tab}!A2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            ).execute()
        )



def read_table_rows(service, spreadsheet_id: str, tab: str) -> list[dict[str, Any]]:
    headers = TAB_HEADERS[tab]
    end_column = _column_letter(len(headers))
    resp = _execute_with_retry(
        lambda: service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{tab}!A1:{end_column}",
        ).execute()
    )
    values = resp.get("values", [])
    if len(values) <= 1:
        return []

    out: list[dict[str, Any]] = []
    for raw in values[1:]:
        padded = raw + [""] * (len(headers) - len(raw))
        out.append(dict(zip(headers, padded)))
    return out



def append_row(service, spreadsheet_id: str, tab: str, row: dict[str, Any]) -> None:
    headers = TAB_HEADERS[tab]
    payload_row = _to_sheet_row(row, headers)
    _execute_with_retry(
        lambda: service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{tab}!A2",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [payload_row]},
        ).execute()
    )



def _extract_case_counter(case_id: str, prefix: str) -> int:
    if not case_id.startswith(prefix):
        return 0
    tail = case_id[len(prefix) :]
    if tail.isdigit():
        return int(tail)
    return 0



def next_case_id(service, spreadsheet_id: str, created_at: datetime) -> str:
    month_prefix = f"CASE-{created_at.strftime('%Y%m')}-"
    rows = read_table_rows(service, spreadsheet_id, "cases_raw")
    max_counter = 0
    for row in rows:
        max_counter = max(max_counter, _extract_case_counter(str(row.get("case_id", "")), month_prefix))
    return f"{month_prefix}{max_counter + 1:04d}"



def append_case_and_log(
    service,
    spreadsheet_id: str,
    case_row: dict[str, Any],
    calculator_input: dict[str, Any],
    calculator_output: dict[str, Any],
) -> None:
    append_row(service, spreadsheet_id, "cases_raw", case_row)

    calc_log = {
        "calc_id": f"CALC-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "case_id": case_row.get("case_id", ""),
        "input_json": calculator_input,
        "output_json": calculator_output,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    append_row(service, spreadsheet_id, "calculator_logs", calc_log)


def next_daily_id(service, spreadsheet_id: str, log_date: date) -> str:
    day_prefix = f"DAY-{log_date.strftime('%Y%m%d')}-"
    rows = read_table_rows(service, spreadsheet_id, "study_daily")
    max_counter = 0
    for row in rows:
        max_counter = max(max_counter, _extract_case_counter(str(row.get("daily_id", "")), day_prefix))
    return f"{day_prefix}{max_counter + 1:03d}"


def next_task_id(service, spreadsheet_id: str, created_at: datetime) -> str:
    month_prefix = f"TASK-{created_at.strftime('%Y%m')}-"
    rows = read_table_rows(service, spreadsheet_id, "study_tasks")
    max_counter = 0
    for row in rows:
        max_counter = max(max_counter, _extract_case_counter(str(row.get("task_id", "")), month_prefix))
    return f"{month_prefix}{max_counter + 1:04d}"


def build_weekly_review_id(from_date: date, week_no: int) -> str:
    return f"WEEK-{from_date.year}-{week_no:02d}"


def next_study_event_id(service, spreadsheet_id: str, created_at: datetime) -> str:
    month_prefix = f"EVT-{created_at.strftime('%Y%m')}-"
    rows = read_table_rows(service, spreadsheet_id, "study_events")
    max_counter = 0
    for row in rows:
        max_counter = max(max_counter, _extract_case_counter(str(row.get("event_id", "")), month_prefix))
    return f"{month_prefix}{max_counter + 1:04d}"


def append_study_daily(service, spreadsheet_id: str, daily_row: dict[str, Any]) -> None:
    append_row(service, spreadsheet_id, "study_daily", daily_row)


def append_study_task(service, spreadsheet_id: str, task_row: dict[str, Any]) -> None:
    append_row(service, spreadsheet_id, "study_tasks", task_row)


def append_study_weekly_review(service, spreadsheet_id: str, review_row: dict[str, Any]) -> None:
    append_row(service, spreadsheet_id, "study_weekly_review", review_row)


def append_study_event(service, spreadsheet_id: str, event_row: dict[str, Any]) -> None:
    append_row(service, spreadsheet_id, "study_events", event_row)


def list_study_daily_rows(
    service,
    spreadsheet_id: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict[str, Any]]:
    rows = read_table_rows(service, spreadsheet_id, "study_daily")
    filtered: list[dict[str, Any]] = []

    for row in rows:
        row_date = _safe_iso_date(str(row.get("log_date", ""))) or _safe_iso_date(str(row.get("created_at", "")))
        if from_date and (row_date is None or row_date < from_date):
            continue
        if to_date and (row_date is None or row_date > to_date):
            continue
        filtered.append(row)

    filtered.sort(key=lambda row: str(row.get("log_date", "")), reverse=True)
    return filtered


def list_study_tasks_by_daily_id(service, spreadsheet_id: str, daily_id: str = "") -> list[dict[str, Any]]:
    rows = read_table_rows(service, spreadsheet_id, "study_tasks")
    daily_id_clean = daily_id.strip()
    if not daily_id_clean:
        return rows
    return [row for row in rows if str(row.get("daily_id", "")).strip() == daily_id_clean]


def search_study_notes(service, spreadsheet_id: str, query: str) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []

    daily_rows = read_table_rows(service, spreadsheet_id, "study_daily")
    task_rows = read_table_rows(service, spreadsheet_id, "study_tasks")
    results: list[dict[str, Any]] = []

    for row in daily_rows:
        haystack = " ".join(
            [
                str(row.get("lesson_summary", "")),
                str(row.get("mistakes_or_risks_observed", "")),
                str(row.get("questions_to_ask", "")),
                str(row.get("today_goal", "")),
            ]
        ).lower()
        if q in haystack:
            results.append(
                {
                    "source": "study_daily",
                    "id": row.get("daily_id", ""),
                    "log_date": row.get("log_date", ""),
                    "lesson_summary": row.get("lesson_summary", ""),
                    "mistakes_or_risks_observed": row.get("mistakes_or_risks_observed", ""),
                    "question": row.get("questions_to_ask", ""),
                }
            )

    for row in task_rows:
        haystack = " ".join(
            [
                str(row.get("symptom_or_requirement", "")),
                str(row.get("mentor_tip", "")),
                str(row.get("open_question", "")),
                str(row.get("step_notes", "")),
            ]
        ).lower()
        if q in haystack:
            results.append(
                {
                    "source": "study_tasks",
                    "id": row.get("task_id", ""),
                    "daily_id": row.get("daily_id", ""),
                    "symptom_or_requirement": row.get("symptom_or_requirement", ""),
                    "mentor_tip": row.get("mentor_tip", ""),
                    "open_question": row.get("open_question", ""),
                }
            )

    return results


def search_knowledge(service, spreadsheet_id: str, query: str = "", tag: str = "") -> list[dict[str, Any]]:
    rows = read_table_rows(service, spreadsheet_id, "knowledge_qna")
    q = query.strip().lower()
    tg = tag.strip().lower()

    results: list[dict[str, Any]] = []
    for row in rows:
        haystack = " ".join(
            [
                str(row.get("topic", "")),
                str(row.get("question", "")),
                str(row.get("answer", "")),
                str(row.get("tags", "")),
            ]
        ).lower()
        tags = str(row.get("tags", "")).lower()

        if q and q not in haystack:
            continue
        if tg and tg not in tags:
            continue

        results.append(
            {
                "topic": row.get("topic", ""),
                "question": row.get("question", ""),
                "answer": row.get("answer", ""),
                "tags": row.get("tags", ""),
                "severity": row.get("severity", ""),
            }
        )
    return results



def summarize_cases(
    rows: list[dict[str, Any]],
    from_date: date | None,
    to_date: date | None,
    margin_threshold_pct: float,
) -> dict[str, Any]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        row_date = _safe_iso_date(str(row.get("created_at", "")))
        if from_date and (row_date is None or row_date < from_date):
            continue
        if to_date and (row_date is None or row_date > to_date):
            continue
        filtered.append(row)

    total_cases = len(filtered)
    if total_cases == 0:
        return {
            "total_cases": 0,
            "avg_margin_pct": 0.0,
            "loss_risk_cases": 0,
            "top_cost_drivers": [],
        }

    margins = [_to_float(r.get("gross_margin_pct")) for r in filtered]
    avg_margin_pct = round(sum(margins) / total_cases, 2)
    loss_risk_cases = sum(1 for margin in margins if margin < margin_threshold_pct)

    driver_sums = defaultdict(float)
    driver_map = {
        "material_cost": "วัสดุ",
        "labor_cost": "แรงงาน",
        "travel_cost": "เดินทาง",
        "risk_buffer_cost": "เผื่อความเสี่ยง",
        "warranty_buffer_cost": "เผื่อรับประกัน",
    }
    for row in filtered:
        for field, label in driver_map.items():
            driver_sums[label] += _to_float(row.get(field))

    top_cost_drivers = [
        {"driver": label, "amount": round(amount, 2)}
        for label, amount in sorted(driver_sums.items(), key=lambda x: x[1], reverse=True)
        if amount > 0
    ]

    return {
        "total_cases": total_cases,
        "avg_margin_pct": avg_margin_pct,
        "loss_risk_cases": loss_risk_cases,
        "top_cost_drivers": top_cost_drivers[:5],
    }



def refresh_analytics_daily(service, spreadsheet_id: str, margin_threshold_pct: float) -> int:
    rows = read_table_rows(service, spreadsheet_id, "cases_raw")
    grouped: dict[date, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        row_date = _safe_iso_date(str(row.get("created_at", "")))
        if row_date is None:
            continue
        grouped[row_date].append(row)

    daily_rows = []
    for day in sorted(grouped.keys()):
        group = grouped[day]
        margins = [_to_float(r.get("gross_margin_pct")) for r in group]
        avg_margin = round(sum(margins) / len(group), 2) if group else 0.0
        low_margin = sum(1 for margin in margins if margin < margin_threshold_pct)
        urgent_cases = sum(str(r.get("urgent_flag", "")).strip().lower() in {"true", "1", "yes"} for r in group)

        win_signal = 0
        if avg_margin >= margin_threshold_pct:
            win_signal += 50
        if low_margin <= max(len(group) * 0.3, 1):
            win_signal += 30
        if urgent_cases <= max(len(group) * 0.2, 1):
            win_signal += 20

        daily_rows.append(
            [
                day.isoformat(),
                len(group),
                avg_margin,
                low_margin,
                urgent_cases,
                min(win_signal, 100),
            ]
        )

    # Rewrite summary table (header + all daily rows)
    all_values = [ANALYTICS_DAILY_HEADERS] + daily_rows
    _execute_with_retry(
        lambda: service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="analytics_daily!A1",
            valueInputOption="RAW",
            body={"values": all_values},
        ).execute()
    )

    return len(daily_rows)



def export_tables_to_csv(service, spreadsheet_id: str, output_dir: str | Path) -> list[str]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []
    for tab, headers in TAB_HEADERS.items():
        rows = read_table_rows(service, spreadsheet_id, tab)
        path = out_dir / f"{tab}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({h: row.get(h, "") for h in headers})
        written_files.append(str(path))

    return written_files


__all__ = [
    "append_case_and_log",
    "append_study_daily",
    "append_study_event",
    "append_study_task",
    "append_study_weekly_review",
    "append_row",
    "build_weekly_review_id",
    "create_rollup_spreadsheet",
    "export_tables_to_csv",
    "get_sheets_service",
    "initialize_rollup_sheet",
    "list_study_daily_rows",
    "list_study_tasks_by_daily_id",
    "next_case_id",
    "next_daily_id",
    "next_study_event_id",
    "next_task_id",
    "read_table_rows",
    "refresh_analytics_daily",
    "search_knowledge",
    "search_study_notes",
    "summarize_cases",
]
