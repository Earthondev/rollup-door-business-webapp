#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

PLIST_PATH = Path.home() / "Library/LaunchAgents/com.nattapart.jobtracker.daily.plist"


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    venv_python = project_root / ".venv" / "bin" / "python3"
    python_bin = str(venv_python) if venv_python.exists() else "/usr/bin/python3"
    script_path = project_root / "scripts" / "pipeline_daily.py"

    plist = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
  <key>Label</key>
  <string>com.nattapart.jobtracker.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python_bin}</string>
    <string>{script_path}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{project_root}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>{project_root / 'logs' / 'launchd.out.log'}</string>
  <key>StandardErrorPath</key>
  <string>{project_root / 'logs' / 'launchd.err.log'}</string>
</dict>
</plist>
"""

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist, encoding="utf-8")

    print(f"plist_written={PLIST_PATH}")
    print("next_steps:")
    print(f"  launchctl unload {PLIST_PATH} 2>/dev/null || true")
    print(f"  launchctl load {PLIST_PATH}")
    print(f"  launchctl start com.nattapart.jobtracker.daily")


if __name__ == "__main__":
    main()
