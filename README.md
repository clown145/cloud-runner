# cloud-runner

Remote code execution helper for AI clients.

This repository starts as a monorepo because the skill and the worker are tightly coupled during early design:

- `skill/` contains the Codex skill instructions and usage policy.
- `worker/` contains the remote execution service implementation.
- `docs/` contains architecture notes and protocol drafts.

The worker can be split into a separate repository later if it needs independent deployment, releases, or ownership.

## Current Shape

The first implementation is a Cloudflare Python Worker:

- `POST /run` executes short Python snippets.
- Requests use `Authorization: Bearer <RUNNER_TOKEN>`.
- Code should define `main(input)` or assign top-level `result`.
- The Worker has no KV, D1, R2, Queue, database, or API bindings by default.

The skill includes a ready-to-run client:

```bash
skill/cloud-runner/scripts/run_python.py \
  --code 'def main(input): return input["a"] + input["b"]' \
  --input '{"a":1,"b":2}'
```

It defaults to `https://cloud-runner-python.clown145.workers.dev` and reads the token from
`CLOUD_RUNNER_TOKEN` or `~/.config/cloud-runner/config.json`.

Install the skill locally:

```bash
mkdir -p ~/.codex/skills
cp -R skill/cloud-runner ~/.codex/skills/
```

Configure the token once:

```bash
skill/cloud-runner/scripts/configure.py --token-file worker/.dev.vars
```

## Worker Development

```bash
cd worker
cp .dev.vars.example .dev.vars
UV_LINK_MODE=copy uv run pywrangler dev
```

For deployment:

```bash
cd worker
npx wrangler secret put RUNNER_TOKEN
UV_LINK_MODE=copy uv run pywrangler deploy
```

`UV_LINK_MODE=copy` avoids hardlink-copy issues when deploying from `proot-distro`.

## Example Request

```bash
curl -sS "$CLOUD_RUNNER_URL/run" \
  -H "Authorization: Bearer $CLOUD_RUNNER_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"language":"python","code":"def main(input):\n    return input[\"a\"] + input[\"b\"]","input":{"a":1,"b":2}}'
```

Expected response:

```json
{
  "ok": true,
  "result": 3,
  "logs": [],
  "duration_ms": 1
}
```
