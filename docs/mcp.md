# Cloud Runner MCP

Cloud Runner exposes a remote MCP endpoint at:

```text
https://cloud-runner-python.clown145.workers.dev/mcp
```

Use bearer auth with the same token as `/run`.

## Tools

- `run_python`
- `health_check`
- `get_runner_limits`

## Example Config

```json
{
  "mcpServers": {
    "cloud-runner": {
      "type": "http",
      "url": "https://cloud-runner-python.clown145.workers.dev/mcp",
      "headers": {
        "Authorization": "Bearer ${CLOUD_RUNNER_TOKEN}"
      }
    }
  }
}
```

## Notes

- `GET /mcp` returns `405` because this server uses stateless JSON-response mode instead of SSE.
- For browser-based inspectors, configure `ALLOWED_ORIGINS` in the Worker if you need cross-origin
  access.
