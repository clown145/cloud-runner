#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_URL = "https://cloud-runner-python.clown145.workers.dev"
DEFAULT_CONFIG = Path("~/.config/cloud-runner/config.json").expanduser()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a short Python snippet with Cloud Runner."
    )
    parser.add_argument(
        "--code", help="Python code string. Use '-' to read code from stdin."
    )
    parser.add_argument("--code-file", help="Read Python code from a file.")
    parser.add_argument(
        "--input", default="{}", help="JSON input value. Defaults to {}."
    )
    parser.add_argument("--input-file", help="Read JSON input from a file.")
    parser.add_argument(
        "--url", help="Runner base URL. Defaults to env, config, then skill default."
    )
    parser.add_argument(
        "--token", help="Runner bearer token. Defaults to env or config."
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("CLOUD_RUNNER_CONFIG", str(DEFAULT_CONFIG)),
        help="Config path. Defaults to ~/.config/cloud-runner/config.json.",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    args = parser.parse_args()

    try:
        config = load_config(Path(args.config).expanduser())
        url = resolve_url(args.url, config)
        token = resolve_token(args.token, config)
        code = read_code(args)
        input_value = read_input(args)
        response = run_python(url, token, code, input_value)
    except CloudRunnerError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.pretty:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))

    return 0 if response.get("ok") else 1


class CloudRunnerError(RuntimeError):
    pass


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CloudRunnerError(f"invalid config JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CloudRunnerError(f"invalid config at {path}: expected JSON object")
    return value


def resolve_url(cli_url: str | None, config: dict) -> str:
    url = (
        cli_url
        or os.environ.get("CLOUD_RUNNER_URL")
        or config.get("url")
        or DEFAULT_URL
    )
    if not isinstance(url, str) or not url.strip():
        raise CloudRunnerError("missing Cloud Runner URL")
    return url.rstrip("/")


def resolve_token(cli_token: str | None, config: dict) -> str:
    token = cli_token or os.environ.get("CLOUD_RUNNER_TOKEN") or config.get("token")
    if not isinstance(token, str) or not token.strip():
        raise CloudRunnerError(
            "missing Cloud Runner token; set CLOUD_RUNNER_TOKEN or run scripts/configure.py"
        )
    return token.strip()


def read_code(args: argparse.Namespace) -> str:
    if args.code and args.code_file:
        raise CloudRunnerError("use only one of --code or --code-file")
    if args.code_file:
        return Path(args.code_file).read_text(encoding="utf-8")
    if args.code == "-":
        return sys.stdin.read()
    if args.code:
        return args.code
    raise CloudRunnerError("missing code; pass --code, --code-file, or --code -")


def read_input(args: argparse.Namespace):
    if args.input_file:
        raw = Path(args.input_file).read_text(encoding="utf-8")
    else:
        raw = args.input
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CloudRunnerError(f"invalid JSON input: {exc}") from exc


def run_python(url: str, token: str, code: str, input_value):
    payload = json.dumps(
        {
            "language": "python",
            "code": code,
            "input": input_value,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{url}/run",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "cloud-runner-skill/0.1",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise CloudRunnerError(f"request failed: {exc}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise CloudRunnerError(
            f"runner returned non-JSON response: {body[:500]}"
        ) from exc


if __name__ == "__main__":
    raise SystemExit(main())
