---
name: cloud-runner
description: Remote code execution workflow for AI clients that need to run short deterministic Python snippets on a Cloud Runner HTTP endpoint. Use when the user asks to calculate, transform JSON/text, validate a small generated algorithm, or execute lightweight Python remotely because local execution is unavailable, inappropriate, or explicitly avoided.
---

# Cloud Runner

Use Cloud Runner to run small Python tasks through a remote endpoint. Treat it as a short-lived
calculation service, not a shell, package manager, or project test runner.

The installed skill includes a runnable client:

```bash
python3 scripts/run_python.py --code 'def main(input): return input["a"] + input["b"]' --input '{"a":1,"b":2}'
```

The client defaults to `https://cloud-runner-python.clown145.workers.dev` and reads authentication
from `CLOUD_RUNNER_TOKEN` or `~/.config/cloud-runner/config.json`.

## Workflow

1. Prefer `scripts/run_python.py` instead of hand-written `curl`.
2. If the token is missing, ask the user to configure it with `scripts/configure.py` or set
   `CLOUD_RUNNER_TOKEN`. Do not ask the user to paste the token into chat unless there is no other
   option.
3. Use `CLOUD_RUNNER_URL` only when the user wants a non-default endpoint.
4. Write code as a pure Python snippet that either defines `main(input)` or assigns top-level
   `result`.
5. Keep inputs and outputs JSON-serializable. Do not send secrets, local files, repository content,
   credentials, or private data unless the user explicitly asks.
6. If the runner returns an error, fix the snippet and retry once when the failure is a code issue.
   Surface quota, auth, timeout, or platform-limit failures directly to the user.

## Local Configuration

Configure once:

```bash
python3 scripts/configure.py --token "$CLOUD_RUNNER_TOKEN"
```

The config file is written to `~/.config/cloud-runner/config.json` with owner-only permissions.
Supported configuration sources, highest priority first:

1. CLI flags: `--url`, `--token`
2. Environment variables: `CLOUD_RUNNER_URL`, `CLOUD_RUNNER_TOKEN`
3. Config file: `~/.config/cloud-runner/config.json`
4. Default URL: `https://cloud-runner-python.clown145.workers.dev`

## Running Code

Use inline code:

```bash
python3 scripts/run_python.py \
  --code 'def main(input): return input["a"] + input["b"]' \
  --input '{"a":1,"b":2}'
```

Use a code file:

```bash
python3 scripts/run_python.py --code-file /path/to/snippet.py --input-file /path/to/input.json
```

Use stdin:

```bash
printf '%s\n' 'def main(input): return sum(input)' \
  | python3 scripts/run_python.py --code - --input '[1,2,3]'
```

The script prints the Worker JSON response to stdout.

## Code Shape

Prefer this form:

```python
def main(input):
    items = input["items"]
    return sum(item["price"] * item["count"] for item in items)
```

Fallback form:

```python
result = sum([1, 2, 3])
```

Avoid long loops, dependency installs, filesystem assumptions, network calls, subprocesses, and
anything that needs state across requests. Do not use dunder names such as `__class__`,
`__dict__`, or `__import__`; the worker rejects them.

## Direct API

For the complete request and response contract, read `references/protocol.md` when implementing a
client, MCP tool, or debugging response handling.

Minimal request:

```json
{
  "language": "python",
  "code": "def main(input):\n    return input['a'] + input['b']",
  "input": {
    "a": 1,
    "b": 2
  }
}
```

Expected success:

```json
{
  "ok": true,
  "result": 3,
  "logs": [],
  "duration_ms": 1
}
```

## Safety Rules

- Never print, log, or persist `CLOUD_RUNNER_TOKEN`.
- Do not pass Worker bindings, API keys, database URLs, or local environment variables into code.
- Prefer small inputs; summarize or pre-filter large local data before remote execution.
- Treat the runner as convenience execution, not a hardened sandbox for hostile code.
- Use local tools or a real container sandbox for full projects, `pip install`, tests, browsers, or
  long-running jobs.
