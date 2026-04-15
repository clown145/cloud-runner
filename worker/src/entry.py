import json
from urllib.parse import urlparse

from workers import Response, WorkerEntrypoint

from runner import DEFAULT_LIMITS, run_python

JSON_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
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

        if request.method != "POST" or url.path != "/run":
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
