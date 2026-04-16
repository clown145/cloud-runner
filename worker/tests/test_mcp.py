import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp import (  # noqa: E402
    DEFAULT_PROTOCOL_VERSION,
    LATEST_PROTOCOL_VERSION,
    SERVER_INFO,
    handle_message,
    validate_protocol_version_header,
)


class McpTest(unittest.TestCase):
    def test_validate_protocol_header_defaults(self):
        self.assertEqual(validate_protocol_version_header(None), DEFAULT_PROTOCOL_VERSION)

    def test_validate_protocol_header_rejects_unknown_version(self):
        with self.assertRaises(ValueError):
            validate_protocol_version_header("2099-01-01")

    def test_initialize_negotiates_supported_version(self):
        status, body, response_protocol = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.1.0"},
                },
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(response_protocol, "2025-11-25")
        self.assertEqual(body["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(body["result"]["serverInfo"]["name"], SERVER_INFO["name"])

    def test_initialize_falls_back_to_latest_supported_version(self):
        status, body, response_protocol = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2099-01-01",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.1.0"},
                },
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(response_protocol, LATEST_PROTOCOL_VERSION)
        self.assertEqual(body["result"]["protocolVersion"], LATEST_PROTOCOL_VERSION)

    def test_tools_list_returns_expected_tools(self):
        status, body, response_protocol = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(response_protocol, DEFAULT_PROTOCOL_VERSION)
        tool_names = {tool["name"] for tool in body["result"]["tools"]}
        self.assertEqual(tool_names, {"run_python", "health_check", "get_runner_limits"})

    def test_run_python_tool_call_returns_structured_content(self):
        status, body, _ = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "run_python",
                    "arguments": {
                        "code": "def main(input):\n    return input['a'] + input['b']",
                        "input": {"a": 10, "b": 4},
                    },
                },
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(body["result"]["structuredContent"]["result"], 14)
        self.assertNotIn("isError", body["result"])

    def test_tool_errors_stay_in_call_result(self):
        status, body, _ = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "run_python",
                    "arguments": {
                        "code": "import os\nresult = os.listdir('.')",
                    },
                },
            }
        )

        self.assertEqual(status, 200)
        self.assertTrue(body["result"]["isError"])
        self.assertEqual(
            body["result"]["structuredContent"]["error"]["type"],
            "PermissionError",
        )

    def test_unknown_tool_returns_protocol_error(self):
        status, body, _ = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "does_not_exist",
                    "arguments": {},
                },
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(body["error"]["code"], -32602)

    def test_notifications_return_accepted_without_body(self):
        status, body, response_protocol = handle_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )

        self.assertEqual(status, 202)
        self.assertIsNone(body)
        self.assertEqual(response_protocol, DEFAULT_PROTOCOL_VERSION)


if __name__ == "__main__":
    unittest.main()
