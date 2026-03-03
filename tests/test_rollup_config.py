import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rollup_door.config import load_config


class RollupConfigTests(unittest.TestCase):
    def _make_temp_config(self) -> Path:
        content = """
timezone: Asia/Bangkok
environment: development
spreadsheet_title: Rollup_Door_Business_System
spreadsheet_id: "sheet-123"
margin_threshold_pct: 20
logs_dir: logs
backup_dir: tmp/rollup_backups

google:
  token_path: credentials/token.json
  client_secrets_path: credentials/client.json
  service_account_json: ""

security:
  access_key_id: key-1
  access_key_secret: secret-1
  timestamp_tolerance_seconds: 300
  rate_limit_per_minute: 180

web:
  host: 127.0.0.1
  port: 8080
  debug: true
"""
        fd, path = tempfile.mkstemp(suffix=".yaml")
        os.close(fd)
        Path(path).write_text(content, encoding="utf-8")
        return Path(path)

    def test_env_overrides_yaml(self):
        cfg_path = self._make_temp_config()
        with patch.dict(
            os.environ,
            {
                "ROLLUP_ENV": "production",
                "ROLLUP_SPREADSHEET_ID": "env-sheet",
                "ROLLUP_ACCESS_KEY_ID": "env-key",
                "ROLLUP_ACCESS_KEY_SECRET": "env-secret",
                "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type":"service_account"}',
                "PORT": "10001",
            },
            clear=False,
        ):
            cfg = load_config(cfg_path)

        self.assertEqual(cfg.environment, "production")
        self.assertEqual(cfg.spreadsheet_id, "env-sheet")
        self.assertEqual(cfg.access_key_id, "env-key")
        self.assertEqual(cfg.access_key_secret, "env-secret")
        self.assertEqual(cfg.port, 10001)

    def test_runtime_validation_requires_service_account_in_production(self):
        cfg_path = self._make_temp_config()
        with patch.dict(os.environ, {"ROLLUP_ENV": "production", "GOOGLE_SERVICE_ACCOUNT_JSON": ""}, clear=False):
            cfg = load_config(cfg_path)

        errors = cfg.validate_runtime_requirements()
        self.assertIn("missing_google_service_account", errors)


if __name__ == "__main__":
    unittest.main()
