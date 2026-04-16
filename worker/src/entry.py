import json
from urllib.parse import urlparse

from workers import Response, WorkerEntrypoint

from mcp import handle_message, validate_protocol_version_header
from runner import DEFAULT_LIMITS, run_python

JSON_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": (
        "Content-Type, Authorization, Accept, MCP-Protocol-Version, MCP-Session-Id, Last-Event-ID"
    ),
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Expose-Headers": "MCP-Protocol-Version, MCP-Session-Id",
}


def _json_response(payload, status=200):
    return Response(json.dumps(payload, ensure_ascii=False), status=status, headers=JSON_HEADERS)


def _to_python(value):
    if hasattr(value, "to_py"):
        return value.to_py()
    return value


def _get_secret(env, name):
    try:
        return getattr(env, name)
    except Exception:
        return None


def _origin_is_allowed(request, env):
    origin = request.headers.get("Origin")
    if not origin:
        return True

    allowed = _get_secret(env, "ALLOWED_ORIGINS")
    if allowed:
        allowed_origins = {item.strip() for item in str(allowed).split(",") if item.strip()}
        if "*" in allowed_origins or origin in allowed_origins:
            return True

    request_origin = f"{urlparse(request.url).scheme}://{urlparse(request.url).netloc}"
    return origin == request_origin


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = urlparse(request.url)

        if request.method == "GET" and url.path in {"/", "/health"}:
            return _json_response(
                {
                    "ok": True,
                    "service": "cloud-runner-python",
                    "limits": DEFAULT_LIMITS.as_dict(),
                }
            )

        if request.method == "OPTIONS" and url.path == "/mcp":
            return Response(None, status=204, headers=JSON_HEADERS)

        if request.method == "GET" and url.path == "/mcp":
            headers = dict(JSON_HEADERS)
            headers["Allow"] = "POST, OPTIONS"
            return Response(None, status=405, headers=headers)

        if request.method == "DELETE" and url.path == "/mcp":
            headers = dict(JSON_HEADERS)
            headers["Allow"] = "POST, OPTIONS"
            return Response(None, status=405, headers=headers)

        if request.method != "POST" or url.path != "/run":
            if request.method == "POST" and url.path == "/mcp":
                if not _origin_is_allowed(request, self.env):
                    return _json_response({"ok": False, "error": "forbidden origin"}, status=403)

                try:
                    protocol_version = validate_protocol_version_header(
                        request.headers.get("MCP-Protocol-Version")
                    )
                except ValueError as exc:
                    return _json_response({"ok": False, "error": str(exc)}, status=400)

                try:
                    payload = _to_python(await request.json())
                except Exception as exc:
                    return _json_response(
                        {"ok": False, "error": f"invalid JSON request body: {exc}"},
                        status=400,
                    )

                token = _get_secret(self.env, "RUNNER_TOKEN")
                if not token:
                    return _json_response(
                        {"ok": False, "error": "RUNNER_TOKEN is not configured"},
                        status=500,
                    )

                authorization = request.headers.get("Authorization")
                if authorization != f"Bearer {token}":
                    return _json_response({"ok": False, "error": "unauthorized"}, status=401)

                status, body, response_protocol_version = handle_message(
                    payload,
                    protocol_version=protocol_version,
                )
                headers = dict(JSON_HEADERS)
                headers["MCP-Protocol-Version"] = response_protocol_version
                if body is None:
                    return Response(None, status=status, headers=headers)
                return Response(
                    json.dumps(body, ensure_ascii=False),
                    status=status,
                    headers=headers,
                )

            return _json_response({"ok": False, "error": "not found"}, status=404)

        token = _get_secret(self.env, "RUNNER_TOKEN")
        if not token:
            return _json_response(
                {"ok": False, "error": "RUNNER_TOKEN is not configured"},
                status=500,
            )

        authorization = request.headers.get("Authorization")
        if authorization != f"Bearer {token}":
            return _json_response({"ok": False, "error": "unauthorized"}, status=401)

        try:
            payload = _to_python(await request.json())
        except Exception as exc:
            return _json_response(
                {"ok": False, "error": f"invalid JSON request body: {exc}"},
                status=400,
            )

        result = run_python(payload)
        return _json_response(result, status=200 if result["ok"] else 400)
