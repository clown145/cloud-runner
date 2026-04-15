# Cloud Runner Protocol

Use this reference when implementing a client, MCP server, or worker adapter for `$cloud-runner`.

## Endpoint

```http
POST /run
Authorization: Bearer <token>
Content-Type: application/json
```

## Request Body

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

Fields:

- `language`: Optional for the first worker; if provided, use `python`.
- `code`: Python code. Prefer `def main(input): ...`.
- `input`: JSON value passed to `main(input)`. Defaults to `{}` when omitted.

The first worker rejects code containing dunder names (`__...__`) to reduce common Python sandbox
escape paths.

## Response Body

Success:

```json
{
  "ok": true,
  "result": 3,
  "logs": [],
  "duration_ms": 1
}
```

Failure:

```json
{
  "ok": false,
  "error": {
    "type": "ValueError",
    "message": "code must be a non-empty string",
    "traceback": "ValueError: code must be a non-empty string"
  },
  "logs": [],
  "duration_ms": 0
}
```

## Default Limits

- Code: 16 KiB
- Input JSON: 64 KiB
- Output JSON: 64 KiB
- Captured logs: 8 KiB per stream

Cloudflare platform limits still apply. On the Workers Free plan, CPU time is tight, so the skill
should keep snippets short and deterministic.
