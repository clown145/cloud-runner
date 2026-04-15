import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from runner import RunnerLimits, run_python  # noqa: E402


class RunnerTest(unittest.TestCase):
    def test_runs_main_function(self):
        response = run_python(
            {
                "code": "def main(input):\n    return input['a'] + input['b']",
                "input": {"a": 2, "b": 5},
            }
        )

        self.assertTrue(response["ok"])
        self.assertEqual(response["result"], 7)

    def test_supports_result_variable(self):
        response = run_python({"code": "result = {'value': sum([1, 2, 3])}"})

        self.assertTrue(response["ok"])
        self.assertEqual(response["result"], {"value": 6})

    def test_captures_stdout(self):
        response = run_python({"code": "def main(input):\n    print('hello')\n    return 1"})

        self.assertTrue(response["ok"])
        self.assertEqual(response["logs"], [{"stream": "stdout", "text": "hello\n"}])

    def test_blocks_dangerous_imports(self):
        response = run_python({"code": "import os\nresult = os.listdir('.')"})

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["type"], "PermissionError")

    def test_blocks_dunder_escape_surface(self):
        response = run_python({"code": "result = ().__class__"})

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["type"], "PermissionError")

    def test_allows_common_stdlib(self):
        response = run_python(
            {
                "code": (
                    "from collections import Counter\n"
                    "def main(input):\n"
                    "    return Counter(input['words']).most_common(2)"
                ),
                "input": {"words": ["a", "b", "a"]},
            }
        )

        self.assertTrue(response["ok"])
        self.assertEqual(response["result"], [["a", 2], ["b", 1]])

    def test_rejects_large_code(self):
        response = run_python(
            {"code": "x = 1\n" * 10},
            limits=RunnerLimits(code_bytes=8),
        )

        self.assertFalse(response["ok"])
        self.assertIn("code exceeds", response["error"]["message"])


if __name__ == "__main__":
    unittest.main()
