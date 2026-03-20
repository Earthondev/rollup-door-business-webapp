import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from rollup_door.app import create_app


class RollupAppRenderTests(unittest.TestCase):
    def _make_temp_config(
        self,
        *,
        environment: str = "production",
        spreadsheet_id: str = "sheet-123",
        access_key_id: str = "key-1",
        access_key_secret: str = "secret-1",
    ) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        config_path = root / "rollup_door.yaml"
        logs_dir = root / "logs"
        backup_dir = root / "backups"
        content = f"""
timezone: Asia/Bangkok
environment: {environment}
spreadsheet_title: Rollup_Door_Business_System
spreadsheet_id: "{spreadsheet_id}"
margin_threshold_pct: 20
logs_dir: "{logs_dir}"
backup_dir: "{backup_dir}"

google:
  token_path: "{root / 'credentials' / 'token.json'}"
  client_secrets_path: "{root / 'credentials' / 'client.json'}"
  service_account_json: ""

security:
  access_key_id: {access_key_id}
  access_key_secret: {access_key_secret}
  timestamp_tolerance_seconds: 300
  rate_limit_per_minute: 180

web:
  host: 127.0.0.1
  port: 8080
  debug: false
"""
        config_path.write_text(content, encoding="utf-8")
        return config_path

    def test_root_and_health_load_even_when_dependencies_are_missing(self):
        cfg_path = self._make_temp_config(
            spreadsheet_id="",
            access_key_id="change-me",
            access_key_secret="change-me-secret",
        )

        app = create_app(str(cfg_path))
        client = app.test_client()

        index_response = client.get("/")
        self.assertEqual(index_response.status_code, 200)
        index_response.close()

        health_response = client.get("/api/v1/health")
        self.assertEqual(health_response.status_code, 200)
        health_data = health_response.get_json()
        health_response.close()
        self.assertFalse(health_data["ok"])
        self.assertIn("missing_spreadsheet_id", health_data["errors"])
        self.assertIn("missing_access_key_id", health_data["errors"])
        self.assertIn("missing_access_key_secret", health_data["errors"])
        self.assertIn("missing_google_credentials", health_data["errors"])

    def test_service_endpoints_return_503_when_sheets_dependency_is_not_ready(self):
        cfg_path = self._make_temp_config()
        app = create_app(str(cfg_path))
        client = app.test_client()

        with patch("rollup_door.app.validate_request", return_value=None):
            response = client.get("/api/v1/study/search?q=test")

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        response.close()
        self.assertEqual(payload["error"], "service_unavailable")
        self.assertIn("missing_google_credentials", payload["details"])

        health_response = client.get("/api/v1/health")
        health_data = health_response.get_json()
        health_response.close()
        self.assertEqual(health_data["sheets_init_error"], "missing_google_credentials")
        self.assertFalse(health_data["dependencies"]["sheets_client_initialized"])

    def test_service_initializes_sheet_schema_when_google_oauth_is_available(self):
        cfg_path = self._make_temp_config()
        with (
            patch.dict(
                os.environ,
                {"GOOGLE_OAUTH_TOKEN_JSON": '{"type":"authorized_user","refresh_token":"token"}'},
                clear=False,
            ),
            patch("rollup_door.app.get_sheets_service", return_value=object()) as mock_get_service,
            patch("rollup_door.app.initialize_rollup_sheet") as mock_initialize,
            patch("rollup_door.app.search_study_notes", return_value=[]),
            patch("rollup_door.app.validate_request", return_value=None),
        ):
            app = create_app(str(cfg_path))
            client = app.test_client()
            response = client.get("/api/v1/study/search?q=test")
            payload = response.get_json()
            response.close()

        self.assertEqual(payload["ok"], True)
        mock_get_service.assert_called_once()
        mock_initialize.assert_called_once_with(mock_get_service.return_value, "sheet-123")

    def test_daily_entry_allows_minimal_optional_payload(self):
        cfg_path = self._make_temp_config()
        with (
            patch.dict(
                os.environ,
                {"GOOGLE_OAUTH_TOKEN_JSON": '{"type":"authorized_user","refresh_token":"token"}'},
                clear=False,
            ),
            patch("rollup_door.app.get_sheets_service", return_value=object()),
            patch("rollup_door.app.initialize_rollup_sheet"),
            patch("rollup_door.app.next_daily_id", return_value="DAY-20260321-001"),
            patch("rollup_door.app.append_study_daily") as mock_append,
            patch("rollup_door.app.validate_request", return_value=None),
        ):
            app = create_app(str(cfg_path))
            client = app.test_client()
            response = client.post("/api/v1/study/daily", json={"log_date": "2026-03-21"})
            payload = response.get_json()
            response.close()

        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["daily_id"], "DAY-20260321-001")
        appended_row = mock_append.call_args.args[2]
        self.assertEqual(appended_row["owner_name"], "ผู้เรียน")
        self.assertEqual(appended_row["lesson_summary"], "")
        self.assertEqual(appended_row["business_idea"], "")

    def test_task_entry_allows_standalone_business_note_without_daily_id(self):
        cfg_path = self._make_temp_config()
        with (
            patch.dict(
                os.environ,
                {"GOOGLE_OAUTH_TOKEN_JSON": '{"type":"authorized_user","refresh_token":"token"}'},
                clear=False,
            ),
            patch("rollup_door.app.get_sheets_service", return_value=object()),
            patch("rollup_door.app.initialize_rollup_sheet"),
            patch("rollup_door.app.next_task_id", return_value="TASK-202603-0001"),
            patch("rollup_door.app.append_study_task") as mock_append,
            patch("rollup_door.app.validate_request", return_value=None),
        ):
            app = create_app(str(cfg_path))
            client = app.test_client()
            response = client.post(
                "/api/v1/study/tasks",
                json={"cost_or_price_note": "ค่าอะไหล่ประมาณ 2,000", "business_takeaway": "ควรมีแพ็กเกจซ่อมด่วน"},
            )
            payload = response.get_json()
            response.close()

        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["task_id"], "TASK-202603-0001")
        appended_row = mock_append.call_args.args[2]
        self.assertEqual(appended_row["daily_id"], "")
        self.assertEqual(appended_row["task_category"], "บันทึกทั่วไป")
        self.assertEqual(appended_row["business_takeaway"], "ควรมีแพ็กเกจซ่อมด่วน")

    def test_weekly_review_can_auto_fill_dates_and_week(self):
        cfg_path = self._make_temp_config()
        with (
            patch.dict(
                os.environ,
                {"GOOGLE_OAUTH_TOKEN_JSON": '{"type":"authorized_user","refresh_token":"token"}'},
                clear=False,
            ),
            patch("rollup_door.app.get_sheets_service", return_value=object()),
            patch("rollup_door.app.initialize_rollup_sheet"),
            patch("rollup_door.app.append_study_weekly_review") as mock_append,
            patch("rollup_door.app.validate_request", return_value=None),
        ):
            app = create_app(str(cfg_path))
            client = app.test_client()
            response = client.post("/api/v1/study/weekly-review", json={"business_opportunities": "งานบำรุงรายเดือน"})
            payload = response.get_json()
            response.close()

        self.assertEqual(payload["ok"], True)
        appended_row = mock_append.call_args.args[2]
        self.assertTrue(1 <= int(appended_row["week_no"]) <= 53)
        self.assertEqual(appended_row["business_opportunities"], "งานบำรุงรายเดือน")
        self.assertLessEqual(date.fromisoformat(appended_row["from_date"]), date.fromisoformat(appended_row["to_date"]))


if __name__ == "__main__":
    unittest.main()
