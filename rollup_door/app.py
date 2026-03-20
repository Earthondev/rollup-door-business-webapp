from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from .calculator import estimate_price, evaluate_margin
from .config import DEFAULT_CONFIG_PATH, load_config
from .constants import DEFAULT_STATUS
from .security import InMemoryRateLimiter, SecurityConfig, validate_request
from .sheets import (
    append_case_and_log,
    append_study_daily,
    append_study_event,
    append_study_task,
    append_study_weekly_review,
    build_weekly_review_id,
    get_sheets_service,
    initialize_rollup_sheet,
    list_study_daily_rows,
    list_study_tasks_by_daily_id,
    next_case_id,
    next_daily_id,
    next_study_event_id,
    next_task_id,
    read_table_rows,
    refresh_analytics_daily,
    search_knowledge,
    search_study_notes,
    summarize_cases,
)



def _to_float(value: Any, field_name: str, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid_{field_name}") from None
    if parsed < minimum:
        raise ValueError(f"invalid_{field_name}")
    return round(parsed, 2)



def _to_int(value: Any, field_name: str, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid_{field_name}") from None
    if parsed < minimum:
        raise ValueError(f"invalid_{field_name}")
    return parsed



def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    cleaned = str(value).strip()
    return cleaned or default



def _to_date(value: Any, field_name: str) -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"invalid_{field_name}") from None


def _is_https_url(value: str) -> bool:
    return value.startswith("https://")


def _validate_https_links(value: str, field_name: str) -> None:
    links = [item.strip() for item in value.split(",") if item.strip()]
    if not links:
        return
    if any(not _is_https_url(link) for link in links):
        raise ValueError(f"invalid_{field_name}")


def _optional_int_range(value: Any, field_name: str, minimum: int, maximum: int) -> int | None:
    if value in (None, ""):
        return None
    parsed = _to_int(value, field_name, minimum=minimum)
    if parsed > maximum:
        raise ValueError(f"invalid_{field_name}")
    return parsed


def create_app(config_path: str = str(DEFAULT_CONFIG_PATH)) -> Flask:
    cfg = load_config(config_path)
    rate_limiter = InMemoryRateLimiter(cfg.rate_limit_per_minute)
    security_cfg = SecurityConfig(
        access_key_id=cfg.access_key_id,
        access_key_secret=cfg.access_key_secret,
        timestamp_tolerance_seconds=cfg.timestamp_tolerance_seconds,
        rate_limit_per_minute=cfg.rate_limit_per_minute,
    )
    case_lock = threading.Lock()
    sheets_lock = threading.Lock()
    sheets_service: Any | None = None
    sheets_init_error = ""

    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["ROLLUP_CONFIG"] = cfg

    logs_dir = Path(cfg.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    def _get_sheets_service():
        nonlocal sheets_service, sheets_init_error
        if sheets_service is not None:
            return sheets_service

        with sheets_lock:
            if sheets_service is not None:
                return sheets_service
            if cfg.requires_service_account() and not cfg.has_google_credentials():
                sheets_init_error = "missing_google_credentials"
                raise RuntimeError(sheets_init_error)
            try:
                sheets_service = get_sheets_service(
                    token_path=cfg.token_path,
                    client_secrets_path=cfg.client_secrets_path,
                    oauth_token_json=cfg.oauth_token_json,
                    oauth_client_secrets_json=cfg.oauth_client_secrets_json,
                    service_account_json=cfg.google_service_account_json,
                    force_service_account=cfg.requires_service_account() and not cfg.has_oauth_credentials(),
                )
                if cfg.spreadsheet_id.strip():
                    initialize_rollup_sheet(sheets_service, cfg.spreadsheet_id)
                sheets_init_error = ""
                return sheets_service
            except Exception as exc:
                sheets_init_error = str(exc)
                raise RuntimeError(sheets_init_error) from exc

    def _service_unavailable_response():
        details = cfg.validate_runtime_requirements()
        if not details and sheets_init_error:
            details = [sheets_init_error]
        return jsonify({"ok": False, "error": "service_unavailable", "details": details}), 503

    @app.before_request
    def _api_guard():
        if not request.path.startswith("/api/"):
            return None
        if request.path == "/api/v1/health":
            return None

        raw = request.get_data(cache=True)
        error = validate_request(
            headers={k.lower(): v for k, v in request.headers.items()},
            method=request.method,
            path=request.path,
            body=raw,
            client_ip=(request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown").split(",")[0].strip(),
            config=security_cfg,
            limiter=rate_limiter,
        )
        if error:
            status_code = 429 if error == "rate_limit_exceeded" else 401
            return jsonify({"ok": False, "error": error}), status_code
        return None

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/manifest.webmanifest")
    def manifest():
        return send_from_directory(app.static_folder, "manifest.webmanifest")

    @app.get("/sw.js")
    def service_worker():
        return send_from_directory(app.static_folder, "sw.js")

    @app.post("/api/v1/calculator/estimate")
    def api_estimate():
        payload = request.get_json(silent=True) or {}
        try:
            material_cost = _to_float(payload.get("material_cost"), "material_cost")
            labor_cost = _to_float(payload.get("labor_cost"), "labor_cost")
            travel_cost = _to_float(payload.get("travel_cost"), "travel_cost")
            warranty_months = _to_int(payload.get("warranty_months", 12), "warranty_months")
            target_margin_pct = _to_float(payload.get("target_margin_pct", 30), "target_margin_pct", minimum=1)
        except ValueError as err:
            return jsonify({"ok": False, "error": str(err)}), 400

        risk_level = str(payload.get("risk_level", "medium") or "medium")
        estimate = estimate_price(
            material_cost=material_cost,
            labor_cost=labor_cost,
            travel_cost=travel_cost,
            risk_level=risk_level,
            warranty_months=warranty_months,
            target_margin_pct=target_margin_pct,
        )

        return jsonify(
            {
                "ok": True,
                "direct_cost": estimate.direct_cost,
                "suggested_price": estimate.suggested_price,
                "gross_profit": estimate.gross_profit,
                "gross_margin_pct": estimate.gross_margin_pct,
                "risk_buffer_cost": estimate.risk_buffer_cost,
                "warranty_buffer_cost": estimate.warranty_buffer_cost,
            }
        )

    @app.post("/api/v1/cases")
    def api_create_case():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        payload = request.get_json(silent=True) or {}
        required = [
            "creator_name",
            "district",
            "job_type",
            "site_type",
            "width_mm",
            "height_mm",
            "usage_per_day",
            "motor_type",
            "material_cost",
            "labor_cost",
            "travel_cost",
        ]
        missing = [field for field in required if payload.get(field) in (None, "")]
        if missing:
            return jsonify({"ok": False, "error": "missing_required_fields", "fields": missing}), 400

        try:
            width_mm = _to_float(payload.get("width_mm"), "width_mm")
            height_mm = _to_float(payload.get("height_mm"), "height_mm")
            usage_per_day = _to_int(payload.get("usage_per_day"), "usage_per_day")
            material_cost = _to_float(payload.get("material_cost"), "material_cost")
            labor_cost = _to_float(payload.get("labor_cost"), "labor_cost")
            travel_cost = _to_float(payload.get("travel_cost"), "travel_cost")
            target_margin_pct = _to_float(payload.get("target_margin_pct", 30), "target_margin_pct", minimum=1)
            warranty_months = _to_int(payload.get("warranty_months", 12), "warranty_months")
        except ValueError as err:
            return jsonify({"ok": False, "error": str(err)}), 400

        risk_level = str(payload.get("risk_level", "medium") or "medium")
        urgent_flag = _to_bool(payload.get("urgent_flag", False))

        estimate = estimate_price(
            material_cost=material_cost,
            labor_cost=labor_cost,
            travel_cost=travel_cost,
            risk_level=risk_level,
            warranty_months=warranty_months,
            target_margin_pct=target_margin_pct,
        )

        risk_buffer_cost = _to_float(payload.get("risk_buffer_cost", estimate.risk_buffer_cost), "risk_buffer_cost")
        warranty_buffer_cost = _to_float(
            payload.get("warranty_buffer_cost", estimate.warranty_buffer_cost),
            "warranty_buffer_cost",
        )

        direct_cost = round(material_cost + labor_cost + travel_cost + risk_buffer_cost + warranty_buffer_cost, 2)
        suggested_price = round(direct_cost / max(1 - (target_margin_pct / 100.0), 0.05), 2)

        final_price_raw = payload.get("final_price", "")
        final_price = suggested_price if final_price_raw in (None, "") else _to_float(final_price_raw, "final_price")
        gross_profit, gross_margin_pct = evaluate_margin(final_price=final_price, direct_cost=direct_cost)

        warnings: list[str] = []
        if gross_margin_pct < cfg.margin_threshold_pct:
            warnings.append("margin_below_threshold")
        if width_mm <= 0 or height_mm <= 0:
            warnings.append("invalid_dimensions")
        if usage_per_day >= 80:
            warnings.append("high_usage_heavy_duty_recommended")

        now = datetime.now()
        with case_lock:
            case_id = next_case_id(service, cfg.spreadsheet_id, now)

            case_row = {
                "case_id": case_id,
                "created_at": now.isoformat(timespec="seconds"),
                "creator_name": str(payload.get("creator_name", "")).strip(),
                "district": str(payload.get("district", "")).strip(),
                "job_type": str(payload.get("job_type", "")).strip(),
                "site_type": str(payload.get("site_type", "")).strip(),
                "width_mm": width_mm,
                "height_mm": height_mm,
                "usage_per_day": usage_per_day,
                "motor_type": str(payload.get("motor_type", "")).strip(),
                "urgent_flag": "TRUE" if urgent_flag else "FALSE",
                "risk_level": risk_level,
                "target_margin_pct": target_margin_pct,
                "material_cost": material_cost,
                "labor_cost": labor_cost,
                "travel_cost": travel_cost,
                "risk_buffer_cost": risk_buffer_cost,
                "warranty_buffer_cost": warranty_buffer_cost,
                "direct_cost": direct_cost,
                "suggested_price": suggested_price,
                "final_price": final_price,
                "gross_profit": gross_profit,
                "gross_margin_pct": gross_margin_pct,
                "status": str(payload.get("status", DEFAULT_STATUS) or DEFAULT_STATUS),
                "notes": str(payload.get("notes", "")).strip(),
            }

            calc_input = {
                "material_cost": material_cost,
                "labor_cost": labor_cost,
                "travel_cost": travel_cost,
                "risk_level": risk_level,
                "warranty_months": warranty_months,
                "target_margin_pct": target_margin_pct,
            }
            calc_output = {
                "direct_cost": direct_cost,
                "suggested_price": suggested_price,
                "gross_profit": gross_profit,
                "gross_margin_pct": gross_margin_pct,
            }

            append_case_and_log(
                service=service,
                spreadsheet_id=cfg.spreadsheet_id,
                case_row=case_row,
                calculator_input=calc_input,
                calculator_output=calc_output,
            )

        return jsonify(
            {
                "ok": True,
                "case_id": case_id,
                "suggested_price": suggested_price,
                "gross_margin_pct": gross_margin_pct,
                "warnings": warnings,
            }
        )

    @app.get("/api/v1/knowledge/search")
    def api_search_knowledge():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        q = request.args.get("q", "")
        tag = request.args.get("tag", "")
        results = search_knowledge(service, cfg.spreadsheet_id, query=q, tag=tag)
        return jsonify({"ok": True, "items": results, "count": len(results)})

    @app.get("/api/v1/analytics/summary")
    def api_summary():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        from_raw = request.args.get("from", "")
        to_raw = request.args.get("to", "")
        try:
            from_date = date.fromisoformat(from_raw) if from_raw else None
            to_date = date.fromisoformat(to_raw) if to_raw else None
        except ValueError:
            return jsonify({"ok": False, "error": "invalid_date_range"}), 400

        rows = read_table_rows(service, cfg.spreadsheet_id, "cases_raw")
        summary = summarize_cases(
            rows=rows,
            from_date=from_date,
            to_date=to_date,
            margin_threshold_pct=cfg.margin_threshold_pct,
        )

        return jsonify(
            {
                "ok": True,
                **summary,
                "date_range": {
                    "from": from_date.isoformat() if from_date else None,
                    "to": to_date.isoformat() if to_date else None,
                },
            }
        )

    @app.post("/api/v1/study/daily")
    def api_study_daily():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        payload = request.get_json(silent=True) or {}

        try:
            log_date_raw = _clean_text(payload.get("log_date"))
            log_date = _to_date(log_date_raw, "log_date") if log_date_raw else date.today()
            _validate_https_links(str(payload.get("photo_drive_links", "")).strip(), "photo_drive_links")
        except ValueError as err:
            return jsonify({"ok": False, "error": str(err)}), 400

        now = datetime.now()
        with case_lock:
            daily_id = next_daily_id(service, cfg.spreadsheet_id, log_date)
            row = {
                "daily_id": daily_id,
                "log_date": log_date.isoformat(),
                "owner_name": _clean_text(payload.get("owner_name"), "ผู้เรียน"),
                "mentor_name": _clean_text(payload.get("mentor_name")),
                "shop_or_site_name": _clean_text(payload.get("shop_or_site_name")),
                "district": _clean_text(payload.get("district")),
                "start_time": _clean_text(payload.get("start_time")),
                "end_time": _clean_text(payload.get("end_time")),
                "today_goal": _clean_text(payload.get("today_goal")),
                "job_types_seen": _clean_text(payload.get("job_types_seen")),
                "customer_types_seen": _clean_text(payload.get("customer_types_seen")),
                "safety_briefing_done": "TRUE" if _to_bool(payload.get("safety_briefing_done", False)) else "FALSE",
                "tools_prepared": _clean_text(payload.get("tools_prepared")),
                "questions_to_ask": _clean_text(payload.get("questions_to_ask")),
                "customer_problem": _clean_text(payload.get("customer_problem")),
                "price_signal": _clean_text(payload.get("price_signal")),
                "supplier_or_contact": _clean_text(payload.get("supplier_or_contact")),
                "lesson_summary": _clean_text(payload.get("lesson_summary")),
                "mistakes_or_risks_observed": _clean_text(payload.get("mistakes_or_risks_observed")),
                "next_day_focus": _clean_text(payload.get("next_day_focus")),
                "business_idea": _clean_text(payload.get("business_idea")),
                "follow_up_note": _clean_text(payload.get("follow_up_note")),
                "photo_drive_links": _clean_text(payload.get("photo_drive_links")),
                "created_at": now.isoformat(timespec="seconds"),
            }
            append_study_daily(service, cfg.spreadsheet_id, row)

        return jsonify({"ok": True, "daily_id": daily_id})

    @app.post("/api/v1/study/tasks")
    def api_study_tasks():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        payload = request.get_json(silent=True) or {}
        daily_id = _clean_text(payload.get("daily_id"))
        if daily_id:
            daily_rows = read_table_rows(service, cfg.spreadsheet_id, "study_daily")
            if not any(str(row.get("daily_id", "")).strip() == daily_id for row in daily_rows):
                return jsonify({"ok": False, "error": "daily_id_not_found"}), 400

        try:
            difficulty_score = _optional_int_range(payload.get("difficulty_score"), "difficulty_score", 1, 5)
            confidence_score = _optional_int_range(
                payload.get("confidence_after_task"),
                "confidence_after_task",
                1,
                5,
            )
            photo_drive_link = str(payload.get("photo_drive_link", "")).strip()
            if photo_drive_link and not _is_https_url(photo_drive_link):
                raise ValueError("invalid_photo_drive_link")
        except ValueError as err:
            return jsonify({"ok": False, "error": str(err)}), 400

        now = datetime.now()
        with case_lock:
            task_id = next_task_id(service, cfg.spreadsheet_id, now)
            row = {
                "task_id": task_id,
                "daily_id": daily_id,
                "task_time": _clean_text(payload.get("task_time")),
                "task_category": _clean_text(payload.get("task_category"), "บันทึกทั่วไป"),
                "job_mode": _clean_text(payload.get("job_mode"), "เรียนงาน"),
                "site_type": _clean_text(payload.get("site_type")),
                "symptom_or_requirement": _clean_text(payload.get("symptom_or_requirement")),
                "suspected_cause": _clean_text(payload.get("suspected_cause")),
                "materials_used": _clean_text(payload.get("materials_used")),
                "tools_used": _clean_text(payload.get("tools_used")),
                "step_notes": _clean_text(payload.get("step_notes")),
                "quality_check_points": _clean_text(payload.get("quality_check_points")),
                "safety_risks": _clean_text(payload.get("safety_risks")),
                "mentor_tip": _clean_text(payload.get("mentor_tip")),
                "customer_objection": _clean_text(payload.get("customer_objection")),
                "my_role": _clean_text(payload.get("my_role"), "ดูงาน"),
                "difficulty_score": difficulty_score if difficulty_score is not None else "",
                "confidence_after_task": confidence_score if confidence_score is not None else "",
                "open_question": _clean_text(payload.get("open_question")),
                "photo_drive_link": photo_drive_link,
                "time_spent_note": _clean_text(payload.get("time_spent_note")),
                "cost_or_price_note": _clean_text(payload.get("cost_or_price_note")),
                "supplier_name": _clean_text(payload.get("supplier_name")),
                "business_takeaway": _clean_text(payload.get("business_takeaway")),
                "created_at": now.isoformat(timespec="seconds"),
            }
            append_study_task(service, cfg.spreadsheet_id, row)

        return jsonify({"ok": True, "task_id": task_id})

    @app.post("/api/v1/study/weekly-review")
    def api_study_weekly_review():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        payload = request.get_json(silent=True) or {}
        try:
            today = date.today()
            default_from_date = today - timedelta(days=today.weekday())
            from_raw = _clean_text(payload.get("from_date"))
            to_raw = _clean_text(payload.get("to_date"))
            from_date = _to_date(from_raw, "from_date") if from_raw else default_from_date
            to_date = _to_date(to_raw, "to_date") if to_raw else today
            week_raw = _clean_text(payload.get("week_no"))
            week_no = _to_int(week_raw, "week_no", minimum=1) if week_raw else from_date.isocalendar().week
            if week_no > 53:
                raise ValueError("invalid_week_no")
        except ValueError as err:
            return jsonify({"ok": False, "error": str(err)}), 400

        if to_date < from_date:
            return jsonify({"ok": False, "error": "invalid_date_range"}), 400

        review_id = build_weekly_review_id(from_date=from_date, week_no=week_no)
        row = {
            "review_id": review_id,
            "week_no": week_no,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "top_lessons": _clean_text(payload.get("top_lessons")),
            "repeated_problems": _clean_text(payload.get("repeated_problems")),
            "skills_improved": _clean_text(payload.get("skills_improved")),
            "skills_need_practice": _clean_text(payload.get("skills_need_practice")),
            "next_week_plan": _clean_text(payload.get("next_week_plan")),
            "business_opportunities": _clean_text(payload.get("business_opportunities")),
            "process_to_standardize": _clean_text(payload.get("process_to_standardize")),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        append_study_weekly_review(service, cfg.spreadsheet_id, row)
        return jsonify({"ok": True, "review_id": review_id})

    @app.get("/api/v1/study/daily")
    def api_get_study_daily():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        from_raw = request.args.get("from", "")
        to_raw = request.args.get("to", "")
        try:
            from_date = _to_date(from_raw, "from") if from_raw else None
            to_date = _to_date(to_raw, "to") if to_raw else None
        except ValueError as err:
            return jsonify({"ok": False, "error": str(err)}), 400

        items = list_study_daily_rows(
            service=service,
            spreadsheet_id=cfg.spreadsheet_id,
            from_date=from_date,
            to_date=to_date,
        )
        return jsonify({"ok": True, "items": items, "count": len(items)})

    @app.get("/api/v1/study/tasks")
    def api_get_study_tasks():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        daily_id = request.args.get("daily_id", "")
        items = list_study_tasks_by_daily_id(service, cfg.spreadsheet_id, daily_id=daily_id)
        return jsonify({"ok": True, "items": items, "count": len(items)})

    @app.get("/api/v1/study/search")
    def api_study_search():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        q = request.args.get("q", "")
        items = search_study_notes(service, cfg.spreadsheet_id, query=q)
        return jsonify({"ok": True, "items": items, "count": len(items)})

    @app.post("/api/v1/events")
    def api_events():
        payload = request.get_json(silent=True) or {}
        now = datetime.now()
        event_line = {
            "created_at": now.isoformat(timespec="seconds"),
            "event_name": payload.get("event_name", "unknown"),
            "page": payload.get("page", ""),
            "metadata": payload.get("metadata", {}),
            "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        }

        log_file = logs_dir / f"rollup_webapp_events_{now.date().isoformat()}.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event_line, ensure_ascii=False) + "\n")

        try:
            with case_lock:
                service = _get_sheets_service()
                event_id = next_study_event_id(service, cfg.spreadsheet_id, now)
                append_study_event(
                    service,
                    cfg.spreadsheet_id,
                    {
                        "event_id": event_id,
                        "event_name": str(payload.get("event_name", "unknown")).strip(),
                        "page": str(payload.get("page", "")).strip(),
                        "metadata_json": payload.get("metadata", {}),
                        "created_at": now.isoformat(timespec="seconds"),
                    },
                )
        except Exception:
            # Logging telemetry must not block core actions.
            pass

        return jsonify({"ok": True})

    @app.post("/api/v1/analytics/refresh")
    def api_refresh_analytics():
        try:
            service = _get_sheets_service()
        except RuntimeError:
            return _service_unavailable_response()

        refreshed_days = refresh_analytics_daily(
            service=service,
            spreadsheet_id=cfg.spreadsheet_id,
            margin_threshold_pct=cfg.margin_threshold_pct,
        )
        return jsonify({"ok": True, "refreshed_days": refreshed_days})

    @app.get("/api/v1/health")
    def health():
        errors = cfg.validate_runtime_requirements()
        return jsonify(
            {
                "ok": len(errors) == 0,
                "service": "rollup-door-webapp",
                "environment": cfg.environment,
                "dependencies": {
                    "spreadsheet_id": bool(cfg.spreadsheet_id.strip()),
                    "google_service_account": bool(cfg.google_service_account_json.strip()),
                    "google_oauth": bool(cfg.has_oauth_credentials()),
                    "access_key_id": bool(
                        cfg.access_key_id.strip() and cfg.access_key_id != "change-me"
                    ),
                    "access_key_secret": bool(
                        cfg.access_key_secret.strip()
                        and cfg.access_key_secret != "change-me-secret"
                    ),
                    "sheets_client_initialized": sheets_service is not None,
                },
                "errors": errors,
                "sheets_init_error": sheets_init_error or None,
            }
        )

    return app
