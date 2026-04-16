from __future__ import annotations

import json

from runner import DEFAULT_LIMITS, run_python

LATEST_PROTOCOL_VERSION = "2025-11-25"
DEFAULT_PROTOCOL_VERSION = "2025-03-26"
SUPPORTED_PROTOCOL_VERSIONS = {
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
}

SERVER_INFO = {
    "name": "cloud-runner-python",
    "title": "Cloud Runner",
    "version": "0.1.0",
    "websiteUrl": "https://github.com/clown145/cloud-runner",
}

SERVER_INSTRUCTIONS = (
    "Use run_python for short deterministic Python snippets. "
    "Use health_check or get_runner_limits before large tasks."
)

TOOLS = [
    {
        "name": "run_python",
        "title": "Run Python",
        "description": (
            "Execute a short Python snippet inside the Cloud Runner sandbox. "
            "Define main(input) or assign top-level result."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute.",
                },
                "input": {
                    "description": "JSON value passed to main(input).",
                },
            },
            "required": ["code"],
            "additionalProperties": False,
        },
        "annotations": {
            "title": "Run Python",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "health_check",
        "title": "Health Check",
        "description": "Return service health and the current runtime limits.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "service": {"type": "string"},
                "limits": {"type": "object"},
            },
            "required": ["ok", "service", "limits"],
        },
        "annotations": {
            "title": "Health Check",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "get_runner_limits",
        "title": "Get Runner Limits",
        "description": "Return the configured size and runtime limits for Cloud Runner.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "limits": {"type": "object"},
            },
            "required": ["limits"],
        },
        "annotations": {
            "title": "Get Runner Limits",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
]


def validate_protocol_version_header(header_value: str | None) -> str:
    if not header_value:
        return DEFAULT_PROTOCOL_VERSION
    if header_value not in SUPPORTED_PROTOCOL_VERSIONS:
        raise ValueError(f"unsupported MCP protocol version: {header_value}")
    return header_value


def handle_message(message: object, *, protocol_version: str = DEFAULT_PROTOCOL_VERSION):
    if not isinstance(message, dict):
        return 200, _error(None, -32600, "JSON-RPC message must be an object"), protocol_version

    if "method" not in message:
        return 202, None, protocol_version

    if message.get("jsonrpc") != "2.0":
        return 200, _error(message.get("id"), -32600, "jsonrpc must be 2.0"), protocol_version

    method = message.get("method")
    if not isinstance(method, str) or not method:
        return (
            200,
            _error(message.get("id"), -32600, "method must be a non-empty string"),
            protocol_version,
        )

    is_request = "id" in message
    params = message.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return 200, _error(message.get("id"), -32602, "params must be an object"), protocol_version

    if not is_request or method.startswith("notifications/"):
        return 202, None, protocol_version

    request_id = message.get("id")

    try:
        if method == "initialize":
            payload = _handle_initialize(params)
            return 200, _result(request_id, payload), payload["protocolVersion"]
        if method == "ping":
            return 200, _result(request_id, {}), protocol_version
        if method == "tools/list":
            return 200, _result(request_id, {"tools": TOOLS}), protocol_version
        if method == "tools/call":
            return 200, _result(request_id, _handle_tool_call(params)), protocol_version
        return 200, _error(request_id, -32601, f"method not found: {method}"), protocol_version
    except McpRequestError as exc:
        return 200, _error(request_id, exc.code, exc.message), protocol_version
    except Exception as exc:  # pragma: no cover - defensive guard
        return 200, _error(request_id, -32603, f"internal error: {exc}"), protocol_version


class McpRequestError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _handle_initialize(params: dict):
    requested_version = params.get("protocolVersion")
    if not isinstance(requested_version, str) or not requested_version:
        raise McpRequestError(-32602, "initialize requires protocolVersion")

    negotiated_version = (
        requested_version
        if requested_version in SUPPORTED_PROTOCOL_VERSIONS
        else LATEST_PROTOCOL_VERSION
    )

    return {
        "protocolVersion": negotiated_version,
        "capabilities": {
            "tools": {
                "listChanged": False,
            }
        },
        "serverInfo": SERVER_INFO,
        "instructions": SERVER_INSTRUCTIONS,
    }


def _handle_tool_call(params: dict):
    tool_name = params.get("name")
    arguments = params.get("arguments")

    if not isinstance(tool_name, str) or not tool_name:
        raise McpRequestError(-32602, "tools/call requires tool name")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise McpRequestError(-32602, "tools/call arguments must be an object")

    if tool_name == "run_python":
        payload = {
            "language": "python",
            "code": arguments.get("code"),
            "input": arguments.get("input", {}),
        }
        result = run_python(payload)
        return _tool_result(result, is_error=not result.get("ok"))

    if tool_name == "health_check":
        payload = {
            "ok": True,
            "service": SERVER_INFO["name"],
            "limits": DEFAULT_LIMITS.as_dict(),
        }
        return _tool_result(payload)

    if tool_name == "get_runner_limits":
        payload = {"limits": DEFAULT_LIMITS.as_dict()}
        return _tool_result(payload)

    raise McpRequestError(-32602, f"unknown tool: {tool_name}")


def _tool_result(payload: dict, *, is_error: bool = False):
    text = json.dumps(payload, ensure_ascii=False)
    result = {
        "content": [
            {
                "type": "text",
                "text": text,
            }
        ],
        "structuredContent": payload,
    }
    if is_error:
        result["isError"] = True
    return result


def _result(request_id, payload: dict):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": payload,
    }


def _error(request_id, code: int, message: str):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
