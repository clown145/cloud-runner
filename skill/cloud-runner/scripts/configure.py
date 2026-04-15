#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


DEFAULT_URL = "https://cloud-runner-python.clown145.workers.dev"
DEFAULT_CONFIG = Path("~/.config/cloud-runner/config.json").expanduser()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure the Cloud Runner skill client."
    )
    parser.add_argument(
        "--url", default=os.environ.get("CLOUD_RUNNER_URL", DEFAULT_URL)
    )
    parser.add_argument("--token", default=os.environ.get("CLOUD_RUNNER_TOKEN"))
    parser.add_argument(
        "--token-file", help="Read token from a raw token file or RUNNER_TOKEN= file."
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("CLOUD_RUNNER_CONFIG", str(DEFAULT_CONFIG)),
        help="Config path. Defaults to ~/.config/cloud-runner/config.json.",
    )
    args = parser.parse_args()

    token = args.token
    if args.token_file:
        token = read_token_file(Path(args.token_file).expanduser())

    if not token:
        parser.error("missing token; pass --token, --token-file, or CLOUD_RUNNER_TOKEN")

    config_path = Path(args.config).expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "url": args.url.rstrip("/"),
        "token": token.strip(),
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    config_path.chmod(0o600)

    print(f"Wrote Cloud Runner config to {config_path}")
    return 0


def read_token_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("RUNNER_TOKEN="):
            return line.split("=", 1)[1].strip()
        if line.startswith("CLOUD_RUNNER_TOKEN="):
            return line.split("=", 1)[1].strip()
    return text


if __name__ == "__main__":
    raise SystemExit(main())
