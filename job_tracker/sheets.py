from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .constants import JOB_HEADERS, STATUS_FLOW

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def get_credentials(token_path: str, client_secrets_path: str) -> Credentials:
    creds = None
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
                # Terminal-friendly fallback when local browser flow is unavailable.
                creds = flow.run_console()
        _ensure_parent(token_path)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return creds


def get_sheets_service(token_path: str, client_secrets_path: str):
    creds = get_credentials(token_path, client_secrets_path)
    return build("sheets", "v4", credentials=creds)


def _get_sheet_id(metadata: dict[str, Any], title: str) -> int | None:
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == title:
            return int(props["sheetId"])
    return None


def create_spreadsheet(service, title: str) -> tuple[str, str]:
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": "jobs"}}, {"properties": {"title": "dashboard"}}],
    }
    resp = service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    sheet_id = resp["spreadsheetId"]
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    initialize_sheet(service, sheet_id)
    return sheet_id, url


def initialize_sheet(service, spreadsheet_id: str) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="jobs!A1:U1",
        valueInputOption="RAW",
        body={"values": [JOB_HEADERS]},
    ).execute()

    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    jobs_sheet_id = _get_sheet_id(metadata, "jobs")

    requests: list[dict[str, Any]] = []
    if jobs_sheet_id is not None:
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": jobs_sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": jobs_sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(JOB_HEADERS),
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.92, "green": 0.96, "blue": 0.94},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            }
        )
        requests.append(
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": jobs_sheet_id,
                        "startRowIndex": 1,
                        "startColumnIndex": 17,
                        "endColumnIndex": 18,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [{"userEnteredValue": x} for x in STATUS_FLOW],
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            }
        )

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="dashboard!A1",
        valueInputOption="RAW",
        body={"values": [["Nattapart Job Tracker Dashboard"]]},
    ).execute()


def _rows_from_sheet(service, spreadsheet_id: str) -> tuple[list[str], list[dict[str, Any]]]:
    resp = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="jobs!A1:U",
    ).execute()
    values = resp.get("values", [])
    if not values:
        return JOB_HEADERS, []

    headers = values[0]
    rows = []
    for raw in values[1:]:
        padded = raw + [""] * (len(headers) - len(raw))
        rows.append(dict(zip(headers, padded)))
    return headers, rows


def _to_sheet_row(row: dict[str, Any], headers: list[str]) -> list[Any]:
    out = []
    for h in headers:
        v = row.get(h, "")
        if isinstance(v, bool):
            out.append("TRUE" if v else "FALSE")
        elif isinstance(v, (dict, list, tuple)):
            # Google Sheets values API only accepts scalar-like values.
            out.append(json.dumps(v, ensure_ascii=False))
        elif v is None:
            out.append("")
        else:
            out.append(v)
    return out


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def upsert_jobs(service, spreadsheet_id: str, incoming: list[dict[str, Any]], run_date: date) -> int:
    headers, existing_rows = _rows_from_sheet(service, spreadsheet_id)
    if headers != JOB_HEADERS:
        headers = JOB_HEADERS

    existing_by_uid = {r.get("job_uid"): r for r in existing_rows if r.get("job_uid")}
    existing_order = [r.get("job_uid") for r in existing_rows if r.get("job_uid")]

    new_ids: list[str] = []

    for row in incoming:
        uid = row["job_uid"]
        if uid in existing_by_uid:
            prev = existing_by_uid[uid]
            merged = dict(prev)
            for key in JOB_HEADERS:
                if key in {"status", "added_date"}:
                    continue
                new_val = row.get(key)
                if new_val not in (None, ""):
                    merged[key] = new_val
            merged["status"] = prev.get("status") or row.get("status") or "New"
            merged["added_date"] = prev.get("added_date") or run_date.isoformat()
            merged["last_seen_date"] = run_date.isoformat()
            if not merged.get("notes"):
                merged["notes"] = row.get("notes", "")
            existing_by_uid[uid] = merged
        else:
            new_row = dict(row)
            new_row["status"] = row.get("status") or "New"
            new_row["added_date"] = row.get("added_date") or run_date.isoformat()
            new_row["last_seen_date"] = run_date.isoformat()
            existing_by_uid[uid] = new_row
            new_ids.append(uid)

    final_order = new_ids + existing_order
    final_rows = [existing_by_uid[uid] for uid in final_order if uid in existing_by_uid]

    sheet_values = [headers] + [_to_sheet_row(r, headers) for r in final_rows]

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="jobs!A1",
        valueInputOption="RAW",
        body={"values": sheet_values},
    ).execute()

    refresh_dashboard(service, spreadsheet_id, final_rows)
    return len(new_ids)


def refresh_dashboard(service, spreadsheet_id: str, rows: list[dict[str, Any]]) -> None:
    status_counts = Counter(r.get("status", "New") or "New" for r in rows)
    source_counts = Counter((r.get("source") or "unknown") for r in rows)

    salary_known = sum(1 for r in rows if _parse_bool(r.get("salary_verified")))
    salary_unknown = len(rows) - salary_known

    pending = [
        r
        for r in rows
        if (r.get("status") == "New") and int(float(r.get("fit_score") or 0)) >= 80
    ]
    pending.sort(
        key=lambda r: (
            int(float(r.get("freshness_days") or 0)),
            int(float(r.get("fit_score") or 0)),
        ),
        reverse=True,
    )

    values: list[list[Any]] = []
    values.append(["Nattapart Job Tracker Dashboard", "", "", "", "", "", ""])
    values.append(["Total Jobs", len(rows), "", "", "", "", ""])
    values.append(["Updated On", date.today().isoformat(), "", "", "", "", ""])
    values.append(["", "", "", "", "", "", ""])

    values.append(["Status", "Count", "", "Source", "Count", "", ""])
    max_len = max(len(STATUS_FLOW), len(source_counts))
    sources_sorted = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
    for i in range(max_len):
        s = STATUS_FLOW[i] if i < len(STATUS_FLOW) else ""
        s_count = status_counts.get(s, 0) if s else ""
        src = sources_sorted[i][0] if i < len(sources_sorted) else ""
        src_count = sources_sorted[i][1] if i < len(sources_sorted) else ""
        values.append([s, s_count, "", src, src_count, "", ""])

    values.append(["", "", "", "", "", "", ""])
    values.append(["Salary Verified", salary_known, "", "Salary Unknown", salary_unknown, "", ""])
    values.append(["", "", "", "", "", "", ""])
    values.append(["High-Fit Pending (status=New, fit>=80)", "", "", "", "", "", ""])
    values.append(["Role", "Company", "Freshness(days)", "Fit", "Source", "Location", "URL"])

    for row in pending[:20]:
        values.append(
            [
                row.get("role_title", ""),
                row.get("company", ""),
                row.get("freshness_days", ""),
                row.get("fit_score", ""),
                row.get("source", ""),
                row.get("location", ""),
                row.get("job_url", ""),
            ]
        )

    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range="dashboard!A1:G200",
        body={},
    ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="dashboard!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def update_job_status(
    service,
    spreadsheet_id: str,
    job_uid: str,
    status: str,
    note: str | None,
) -> None:
    if status not in STATUS_FLOW:
        raise ValueError(f"Invalid status: {status}. Allowed: {', '.join(STATUS_FLOW)}")

    headers, rows = _rows_from_sheet(service, spreadsheet_id)
    if headers != JOB_HEADERS:
        headers = JOB_HEADERS

    found = False
    today = date.today().isoformat()
    for row in rows:
        if row.get("job_uid") == job_uid:
            row["status"] = status
            row["last_seen_date"] = today
            if note:
                prev = (row.get("notes") or "").strip()
                row["notes"] = f"{prev} | {note}" if prev else note
            found = True
            break

    if not found:
        raise KeyError(f"job_uid not found: {job_uid}")

    sheet_values = [headers] + [_to_sheet_row(r, headers) for r in rows]
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="jobs!A1",
        valueInputOption="RAW",
        body={"values": sheet_values},
    ).execute()

    refresh_dashboard(service, spreadsheet_id, rows)
