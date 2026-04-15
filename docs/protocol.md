# Cloud Runner Protocol

Cloud Runner executes short Python snippets through a remote Worker.

## Endpoint

```http
POST /run
Authorization: Bearer <RUNNER_TOKEN>
Content-Type: application/json
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

