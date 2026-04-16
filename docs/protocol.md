# Cloud Runner Protocol

Cloud Runner executes short Python snippets through a remote Worker.

## Endpoint

```http
POST /run
Authorization: Bearer <RUNNER_TOKEN>
Content-Type: application/json
```

Remote MCP is available separately at:

```http
POST /mcp
Authorization: Bearer <RUNNER_TOKEN>
Content-Type: application/json
MCP-Protocol-Version: 2025-03-26
```

## Request

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

`language` is optional in the first implementation. If present, it must be `python`.

The code may either define `main(input)` or assign a top-level `result` variable.

## Response

```json
{
  "ok": true,
  "result": 3,
  "logs": [],
  "duration_ms": 1
}
```

Errors use the same envelope:

```json
{
  "ok": false,
  "error": {
    "type": "PermissionError",
    "message": "import blocked: os"
  },
  "logs": [],
  "duration_ms": 1
}
```

## Intended Scope

Use this protocol for small, deterministic Python calculations, text processing, JSON transforms,
and algorithm checks. It is not a full Linux shell and does not install dependencies.

## MCP Tools

The Worker also exposes a remote MCP endpoint with three tools:

- `run_python`
- `health_check`
- `get_runner_limits`

The `/mcp` endpoint is stateless JSON-response mode. It supports:

- `initialize`
- `ping`
- `tools/list`
- `tools/call`

It does not open SSE streams, so `GET /mcp` returns `405 Method Not Allowed`.
