---
name: cloud-runner
description: Remote code execution workflow for AI clients that need to run short deterministic Python snippets on a Cloud Runner HTTP endpoint. Use when the user asks to calculate, transform JSON/text, validate a small generated algorithm, or execute lightweight Python remotely because local execution is unavailable, inappropriate, or explicitly avoided.
---

# Cloud Runner

Use Cloud Runner to run small Python tasks through a remote endpoint. Treat it as a short-lived
calculation service, not a shell, package manager, or project test runner.

## Workflow

1. Confirm the endpoint and token source before calling the runner. Prefer `CLOUD_RUNNER_URL` and
   `CLOUD_RUNNER_TOKEN` if present; otherwise use values explicitly provided by the user.
2. Write code as a pure Python snippet that either defines `main(input)` or assigns top-level
   `result`.
3. Keep inputs and outputs JSON-serializable. Do not send secrets, local files, repository content,
   credentials, or private data unless the user explicitly asks.
4. Call `POST /run` with bearer authentication and a JSON body.
5. If the runner returns an error, fix the snippet and retry once when the failure is a code issue.
   Surface quota, auth, timeout, or platform-limit failures directly to the user.

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

## API

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
