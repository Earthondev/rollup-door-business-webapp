#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rollup_door.app import create_app
from rollup_door.config import DEFAULT_CONFIG_PATH, load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run roll-up door business mobile web app")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    app = create_app(args.config)
    host = args.host or cfg.host
    port = args.port or cfg.port
    debug = True if args.debug else cfg.debug
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
