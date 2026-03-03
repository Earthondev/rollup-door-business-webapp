from __future__ import annotations

import json
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from .calculator import estimate_price, evaluate_margin
from .config import DEFAULT_CONFIG_PATH, load_config
from .constants import DEFAULT_STATUS
from .security import InMemoryRateLimiter, SecurityConfig, validate_request
from .sheets import (
    append_case_and_log,
    get_sheets_service,
    next_case_id,
    read_table_rows,
    refresh_analytics_daily,
    search_knowledge,
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



def create_app(config_path: str = str(DEFAULT_CONFIG_PATH)) -> Flask:
    cfg = load_config(config_path)
    startup_errors = cfg.validate_runtime_requirements()
    if startup_errors:
        raise RuntimeError("config_validation_failed:" + ",".join(startup_errors))

    service = get_sheets_service(
        token_path=cfg.token_path,
        client_secrets_path=cfg.client_secrets_path,
        service_account_json=cfg.google_service_account_json,
        force_service_account=cfg.requires_service_account(),
    )
    rate_limiter = InMemoryRateLimiter(cfg.rate_limit_per_minute)
    security_cfg = SecurityConfig(
        access_key_id=cfg.access_key_id,
        access_key_secret=cfg.access_key_secret,
        timestamp_tolerance_seconds=cfg.timestamp_tolerance_seconds,
        rate_limit_per_minute=cfg.rate_limit_per_minute,
    )
    case_lock = threading.Lock()

    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["ROLLUP_CONFIG"] = cfg

    logs_dir = Path(cfg.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

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
        q = request.args.get("q", "")
        tag = request.args.get("tag", "")
        results = search_knowledge(service, cfg.spreadsheet_id, query=q, tag=tag)
        return jsonify({"ok": True, "items": results, "count": len(results)})

    @app.get("/api/v1/analytics/summary")
    def api_summary():
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

    @app.post("/api/v1/events")
    def api_events():
        payload = request.get_json(silent=True) or {}
        event_line = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "event_name": payload.get("event_name", "unknown"),
            "page": payload.get("page", ""),
            "metadata": payload.get("metadata", {}),
            "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        }

        log_file = logs_dir / f"rollup_webapp_events_{datetime.now().date().isoformat()}.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event_line, ensure_ascii=False) + "\n")

        return jsonify({"ok": True})

    @app.post("/api/v1/analytics/refresh")
    def api_refresh_analytics():
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
                    "access_key_id": bool(
                        cfg.access_key_id.strip() and cfg.access_key_id != "change-me"
                    ),
                    "access_key_secret": bool(
                        cfg.access_key_secret.strip()
                        and cfg.access_key_secret != "change-me-secret"
                    ),
                },
                "errors": errors,
            }
        )

    return app
