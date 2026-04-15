from __future__ import annotations

import base64
import binascii
import bisect
import calendar
import collections
import contextlib
import copy
import csv
import dataclasses
import datetime as datetime_module
import decimal
import fractions
import functools
import hashlib
import heapq
import html
import io
import itertools
import json
import math
import operator
import random
import re
import statistics
import string
import textwrap
import time
import traceback
import types
import unicodedata
import uuid


@dataclasses.dataclass(frozen=True)
class RunnerLimits:
    code_bytes: int = 16 * 1024
    input_bytes: int = 64 * 1024
    output_bytes: int = 64 * 1024
    log_bytes: int = 8 * 1024

    def as_dict(self):
        return {
            "code_bytes": self.code_bytes,
            "input_bytes": self.input_bytes,
            "output_bytes": self.output_bytes,
            "log_bytes": self.log_bytes,
            "runtime": "cloudflare-python-worker",
        }


DEFAULT_LIMITS = RunnerLimits()


ALLOWED_MODULES = {
    "base64",
    "binascii",
    "bisect",
    "calendar",
    "collections",
    "copy",
    "csv",
    "datetime",
    "decimal",
    "fractions",
    "functools",
    "hashlib",
    "heapq",
    "html",
    "itertools",
    "json",
    "math",
    "operator",
    "random",
    "re",
    "statistics",
    "string",
    "textwrap",
    "unicodedata",
    "uuid",
}

BLOCKED_MODULES = {
    "asyncio",
    "builtins",
    "ctypes",
    "http",
    "importlib",
    "inspect",
    "io",
    "js",
    "multiprocessing",
    "os",
    "pathlib",
    "pkgutil",
    "platform",
    "pyodide",
    "requests",
    "shutil",
    "signal",
    "socket",
    "ssl",
    "subprocess",
    "sys",
    "threading",
    "time",
    "urllib",
    "webbrowser",
}


SAFE_BUILTINS = {
    "ArithmeticError": ArithmeticError,
    "AssertionError": AssertionError,
    "AttributeError": AttributeError,
    "BaseException": BaseException,
    "Exception": Exception,
    "False": False,
    "IndexError": IndexError,
    "KeyError": KeyError,
    "NameError": NameError,
    "None": None,
    "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
    "True": True,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "ZeroDivisionError": ZeroDivisionError,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "callable": callable,
    "chr": chr,
    "complex": complex,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "hash": hash,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "object": object,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


PRELOADED_GLOBALS = {
    "base64": base64,
    "binascii": binascii,
    "bisect": bisect,
    "calendar": calendar,
    "collections": collections,
    "copy": copy,
    "csv": csv,
    "datetime": datetime_module,
    "decimal": decimal,
    "fractions": fractions,
    "functools": functools,
    "hashlib": hashlib,
    "heapq": heapq,
    "html": html,
    "itertools": itertools,
    "json": json,
    "math": math,
    "operator": operator,
    "random": random,
    "re": re,
    "statistics": statistics,
    "string": string,
    "textwrap": textwrap,
    "unicodedata": unicodedata,
    "uuid": uuid,
}


def run_python(payload, limits: RunnerLimits = DEFAULT_LIMITS):
    started = time.perf_counter()
    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        code, input_data = _validate_payload(payload, limits)
        sandbox_globals = _new_sandbox_globals()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(compile(code, "<cloud-runner>", "exec"), sandbox_globals)

            main = sandbox_globals.get("main")
            if callable(main):
                result = main(input_data)
            elif "result" in sandbox_globals:
                result = sandbox_globals["result"]
            else:
                result = None

        normalized = _normalize_for_json(result)
        _ensure_json_size(normalized, limits.output_bytes, "output")

        return {
            "ok": True,
            "result": normalized,
            "logs": _collect_logs(stdout, stderr, limits.log_bytes),
            "duration_ms": _duration_ms(started),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": _short_traceback(exc),
            },
            "logs": _collect_logs(stdout, stderr, limits.log_bytes),
            "duration_ms": _duration_ms(started),
        }


def _validate_payload(payload, limits):
    if not isinstance(payload, dict):
        raise TypeError("request body must be a JSON object")

    language = payload.get("language", "python")
    if language != "python":
        raise ValueError("language must be python")

    code = payload.get("code")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code must be a non-empty string")

    _ensure_bytes(code, limits.code_bytes, "code")
    if "__" in code:
        raise PermissionError("dunder names are not allowed")

    input_data = payload.get("input")
    if input_data is None:
        input_data = {}

    _ensure_json_size(input_data, limits.input_bytes, "input")
    return code, input_data


def _new_sandbox_globals():
    builtins = dict(SAFE_BUILTINS)
    builtins["__import__"] = _safe_import

    sandbox_globals = {
        "__builtins__": builtins,
        "__name__": "__cloud_runner__",
        "__package__": None,
    }
    sandbox_globals.update(PRELOADED_GLOBALS)
    return sandbox_globals


def _safe_import(name, globals_=None, locals_=None, fromlist=(), level=0):
    del globals_, locals_

    if level != 0:
        raise ImportError("relative imports are not supported")

    root = name.split(".", 1)[0]
    if root in BLOCKED_MODULES or name in BLOCKED_MODULES:
        raise PermissionError(f"import blocked: {name}")

    if root not in ALLOWED_MODULES:
        raise PermissionError(f"import not allowed: {name}")

    return __import__(name, {}, {}, fromlist, level)


def _ensure_bytes(value, limit, field):
    size = len(value.encode("utf-8"))
    if size > limit:
        raise ValueError(f"{field} exceeds {limit} bytes")


def _ensure_json_size(value, limit, field):
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    _ensure_bytes(encoded, limit, field)


def _collect_logs(stdout, stderr, limit):
    chunks = []
    for stream_name, stream in (("stdout", stdout), ("stderr", stderr)):
        value = stream.getvalue()
        if value:
            chunks.append({"stream": stream_name, "text": _truncate(value, limit)})
    return chunks


def _truncate(value, limit):
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value
    clipped = encoded[:limit].decode("utf-8", errors="ignore")
    return f"{clipped}\n...[truncated]"


def _duration_ms(started):
    return max(0, int((time.perf_counter() - started) * 1000))


def _short_traceback(exc):
    lines = traceback.format_exception_only(type(exc), exc)
    return "".join(lines).strip()


def _normalize_for_json(value):
    if value is None or isinstance(value, bool | int | str):
        return value

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return value

    if isinstance(value, decimal.Decimal):
        return str(value)

    if isinstance(value, uuid.UUID):
        return str(value)

    if isinstance(value, datetime_module.datetime | datetime_module.date | datetime_module.time):
        return value.isoformat()

    if dataclasses.is_dataclass(value):
        return _normalize_for_json(dataclasses.asdict(value))

    if isinstance(value, collections.Counter):
        return [[_normalize_for_json(key), count] for key, count in value.most_common()]

    if isinstance(value, dict):
        return {str(key): _normalize_for_json(item) for key, item in value.items()}

    if isinstance(value, list | tuple):
        return [_normalize_for_json(item) for item in value]

    if isinstance(value, set | frozenset):
        return [_normalize_for_json(item) for item in sorted(value, key=repr)]

    if isinstance(value, types.GeneratorType):
        return [_normalize_for_json(item) for item in value]

    raise TypeError(f"result is not JSON-serializable: {type(value).__name__}")
