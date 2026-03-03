# Job Discovery + Google Sheet Tracker

Daily job discovery pipeline for **Chemist + Data Analysis bridge** roles in Bangkok and nearby areas.

## Features
- Pulls candidates from `JobThai`, `JobsDB`, and `LinkedIn` via web discovery.
- Scores and ranks jobs using role/skill/data-exposure/recency logic.
- Enforces salary preference `>= 30,000 THB`, with fallback to salary-unknown high-fit roles.
- Selects exactly 10 jobs/day (with fallback rule) when possible.
- Upserts into Google Sheets by `job_uid` (dedup safe).
- Preserves status workflow:
  `New -> Shortlisted -> Applied -> Interview -> Offer/Reject`
- Maintains dashboard summary tab.

## Project Structure
- `config/job_tracker.yaml` - runtime config
- `scripts/jobs_fetch.py` - fetch + rank + select (JSON output)
- `scripts/sheet_sync.py` - upsert selected jobs to Google Sheet
- `scripts/status_update.py` - update a single job status
- `scripts/create_sheet.py` - create and initialize new Google Sheet
- `scripts/pipeline_daily.py` - end-to-end daily run
- `scripts/install_scheduler.py` - install macOS launchd daily scheduler (08:30)

## Setup
```bash
cd "/Users/earthondev/Desktop/untitled folder"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Google OAuth Setup
1. Create OAuth Desktop client in Google Cloud Console.
2. Download `client_secrets.json` and place it at:
   `credentials/client_secrets.json`
3. First authenticated command will open browser login and create:
   `credentials/job_tracker_token.json`

## Create New Tracker Sheet
```bash
source .venv/bin/activate
python scripts/create_sheet.py --save_to_config
```

This prints the new Google Sheet URL and saves the `spreadsheet_id` into `config/job_tracker.yaml`.

## CLI Usage

### 1) Fetch + Rank + Select
```bash
python scripts/jobs_fetch.py \
  --date 2026-02-27 \
  --sources jobthai,jobsdb,linkedin \
  --location bangkok \
  --freshness_days 14 \
  --target_count 10 \
  --salary_floor 30000 \
  --output tmp/jobs_selected.json
```

### 2) Sync to Google Sheet
```bash
python scripts/sheet_sync.py \
  --sheet_id <SPREADSHEET_ID> \
  --input tmp/jobs_selected.json \
  --mode upsert
```

### 3) Update Application Status
```bash
python scripts/status_update.py \
  --sheet_id <SPREADSHEET_ID> \
  --job_uid <JOB_UID> \
  --status Applied \
  --note "Applied via company site"
```

### 4) Run Daily Pipeline
```bash
python scripts/pipeline_daily.py
```

Logs are written to `logs/job_tracker_YYYY-MM-DD.log`.

## Install Daily Schedule (08:30 ICT)
```bash
python scripts/install_scheduler.py
launchctl unload ~/Library/LaunchAgents/com.nattapart.jobtracker.daily.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.nattapart.jobtracker.daily.plist
```

## Run Fully in GitHub Actions (No Need to Keep Computer On)
This repo includes a workflow at:
`/.github/workflows/job_tracker_daily.yml`

Schedule:
- Runs every day at `08:30 Asia/Bangkok` (`01:30 UTC`)
- Also supports manual run via `workflow_dispatch`

### One-time GitHub setup
1. Push this project to a GitHub repository.
2. In GitHub repo settings, add these **Actions secrets**:
   - `GOOGLE_CLIENT_SECRETS_JSON`
   - `GOOGLE_TOKEN_JSON`
3. Secret values should be the exact raw JSON content from:
   - `credentials/client_secrets.json` -> `GOOGLE_CLIENT_SECRETS_JSON`
   - `credentials/job_tracker_token.json` -> `GOOGLE_TOKEN_JSON`
4. Ensure `config/job_tracker.yaml` in the repo has a valid `spreadsheet_id`.
5. In GitHub Actions tab, run `Job Tracker Daily` once manually to verify.

After this, daily runs happen in GitHub cloud even if your computer is off.

## Notes
- This system does **not** auto-apply to jobs.
- If salary-known `>= 30k` jobs are insufficient on a given day, it fills with salary-unknown high-fit jobs and flags them in notes.

## Rollup Door Business Web App (New)
This repo also contains a separate mobile-first web app for roll-up door business operations:

- Config: `config/rollup_door.yaml`
- Run server: `python scripts/rollup_webapp.py`
- Create business sheet schema: `python scripts/rollup_create_sheet.py --save_to_config`
- Refresh analytics: `python scripts/rollup_refresh_analytics.py`
- Export CSV backup: `python scripts/rollup_export_csv.py`
- Check data quality: `python scripts/rollup_data_quality_check.py --target_missing_pct 10`
- Deploy blueprint: `render.yaml`
- Production deploy guide (TH): `business_kit_rollup_door/RENDER_DEPLOY_TH.md`

Detailed Thai setup guide:
- `business_kit_rollup_door/WEBAPP_SETUP_TH.md`
