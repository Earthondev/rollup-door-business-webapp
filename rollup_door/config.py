from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RollupConfig:
    timezone: str
    environment: str
    spreadsheet_title: str
    spreadsheet_id: str
    token_path: str
    client_secrets_path: str
    oauth_token_json: str
    oauth_client_secrets_json: str
    google_service_account_json: str
    access_key_id: str
    access_key_secret: str
    timestamp_tolerance_seconds: int
    rate_limit_per_minute: int
    margin_threshold_pct: float
    host: str
    port: int
    debug: bool
    logs_dir: str
    backup_dir: str

    def requires_service_account(self) -> bool:
        return self.environment.lower() in {"production", "render", "staging"}

    def validate_runtime_requirements(self, require_service_account: bool | None = None) -> list[str]:
        require_sa = self.requires_service_account() if require_service_account is None else require_service_account

        errors: list[str] = []
        if not self.spreadsheet_id.strip():
            errors.append("missing_spreadsheet_id")
        if not self.access_key_id.strip() or self.access_key_id == "change-me":
            errors.append("missing_access_key_id")
        if not self.access_key_secret.strip() or self.access_key_secret == "change-me-secret":
            errors.append("missing_access_key_secret")
        if require_sa and not self.google_service_account_json.strip():
            errors.append("missing_google_service_account")

        return errors


DEFAULT_CONFIG_PATH = Path("config/rollup_door.yaml")


def _env(name: str, fallback: Any) -> Any:
    value = os.getenv(name)
    if value is None or value == "":
        return fallback
    return value


def _env_bool(name: str, fallback: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> RollupConfig:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    raw: dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    security = raw.get("security", {})
    google = raw.get("google", {})
    web = raw.get("web", {})

    return RollupConfig(
        timezone=_env("ROLLUP_TIMEZONE", raw.get("timezone", "Asia/Bangkok")),
        environment=_env("ROLLUP_ENV", raw.get("environment", "development")),
        spreadsheet_title=_env("ROLLUP_SPREADSHEET_TITLE", raw.get("spreadsheet_title", "Rollup_Door_Business_System")),
        spreadsheet_id=_env("ROLLUP_SPREADSHEET_ID", raw.get("spreadsheet_id", "")),
        token_path=_env("ROLLUP_GOOGLE_TOKEN_PATH", google.get("token_path", "credentials/job_tracker_token.json")),
        client_secrets_path=_env(
            "ROLLUP_GOOGLE_CLIENT_SECRETS_PATH",
            google.get("client_secrets_path", "credentials/client_secrets.json"),
        ),
        oauth_token_json=_env("GOOGLE_OAUTH_TOKEN_JSON", google.get("oauth_token_json", "")),
        oauth_client_secrets_json=_env(
            "GOOGLE_CLIENT_SECRETS_JSON",
            google.get("oauth_client_secrets_json", ""),
        ),
        google_service_account_json=_env(
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            google.get("service_account_json", ""),
        ),
        access_key_id=_env("ROLLUP_ACCESS_KEY_ID", security.get("access_key_id", "change-me")),
        access_key_secret=_env(
            "ROLLUP_ACCESS_KEY_SECRET",
            security.get("access_key_secret", "change-me-secret"),
        ),
        timestamp_tolerance_seconds=int(
            _env(
                "ROLLUP_TIMESTAMP_TOLERANCE_SECONDS",
                security.get("timestamp_tolerance_seconds", 300),
            )
        ),
        rate_limit_per_minute=int(
            _env(
                "ROLLUP_RATE_LIMIT_PER_MINUTE",
                security.get("rate_limit_per_minute", 180),
            )
        ),
        margin_threshold_pct=float(_env("ROLLUP_MARGIN_THRESHOLD_PCT", raw.get("margin_threshold_pct", 20.0))),
        host=_env("ROLLUP_HOST", web.get("host", "127.0.0.1")),
        port=int(_env("PORT", _env("ROLLUP_PORT", web.get("port", 8080)))),
        debug=_env_bool("ROLLUP_DEBUG", bool(web.get("debug", True))),
        logs_dir=_env("ROLLUP_LOGS_DIR", raw.get("logs_dir", "logs")),
        backup_dir=_env("ROLLUP_BACKUP_DIR", raw.get("backup_dir", "tmp/rollup_backups")),
    )


def save_spreadsheet_id(path: str | Path, spreadsheet_id: str) -> None:
    cfg_path = Path(path)
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    raw["spreadsheet_id"] = spreadsheet_id
    cfg_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
