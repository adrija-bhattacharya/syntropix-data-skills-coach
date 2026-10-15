"""Sandboxed execution of a learner's Python / pandas code.

The code must set a variable called ``result``.  It runs in a **separate
``python -I`` process** with a time limit, after an **AST check** that only
allows ``pandas``, ``numpy``, ``math``, ``statistics``, ``datetime`` and ``re``
imports and rejects anything that reaches files, the OS, the network or
interpreter internals (dunder attributes, ``open``, ``exec``/``eval``, ``to_csv``,
``read_csv``...).  The shop database is preloaded as DataFrames.

The result (DataFrame, Series, array, list, dict or scalar) is normalised to
``(columns, rows)`` so it can be compared row-for-row with the reference, the
same way SQL results are.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from practice.sandbox import ErrorKind, ExecResult
from practice.tasks import SHOP_DB

MAX_CODE_CHARS = 4000
TIMEOUT_S = 15.0

ALLOWED_IMPORTS = frozenset({"pandas", "numpy", "math", "statistics", "datetime", "re"})
BANNED_NAMES = frozenset({
    "open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "input", "breakpoint", "help", "exit", "quit",
    "memoryview", "os", "sys", "subprocess", "socket", "shutil", "pathlib",
    "importlib", "builtins", "io", "pickle", "ctypes",
})  # fmt: skip
BANNED_ATTRS = frozenset({
    "to_csv", "to_excel", "to_parquet", "to_pickle", "to_sql", "to_json", "to_html",
    "to_clipboard", "to_feather", "to_hdf", "to_stata", "to_orc", "to_xml",
    "read_csv", "read_excel", "read_parquet", "read_pickle", "read_sql", "read_json",
    "read_html", "read_clipboard", "read_table", "read_fwf", "read_feather", "read_xml",
    "load", "save", "savetxt", "loadtxt", "fromfile", "tofile", "genfromtxt", "memmap",
    "ctypeslib", "eval", "io", "system", "popen",
})  # fmt: skip


class SandboxRejected(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)


def check_code(code: str) -> None:
    """Reject code that could reach outside the sandbox (raises SandboxRejected)."""
    if len(code) > MAX_CODE_CHARS:
        raise SandboxRejected(f"code longer than {MAX_CODE_CHARS} characters")
    tree = ast.parse(code)  # SyntaxError propagates
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise SandboxRejected(f"import of '{a.name}' is not allowed here")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                raise SandboxRejected(f"import from '{node.module}' is not allowed here")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            raise SandboxRejected(f"'{node.id}' is not available in the practice sandbox")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise SandboxRejected("attributes starting with '_' are not available")
            if node.attr in BANNED_ATTRS:
                raise SandboxRejected(f"'.{node.attr}' reads or writes files - not available here")


# The same normaliser runs inside the sandbox (for the learner's result) and in
# this process (for the trusted reference), so both sides are shaped alike.
NORMALISE_SRC = r"""
import math as _m
def _cell(v):
    try:
        import numpy as _np
        if isinstance(v, _np.generic):
            v = v.item()
    except Exception:
        pass
    if hasattr(v, "isoformat") and not isinstance(v, str):
        try:
            midnight = hasattr(v, "date") and getattr(v, "hour", 0) == 0
            return v.date().isoformat() if midnight else v.isoformat()
        except Exception:
            return str(v)
    if isinstance(v, float):
        return None if _m.isnan(v) else round(v, 6)
    if v is None or isinstance(v, (bool, int, str)):
        return v
    return str(v)

def _table(v):
    import pandas as _pd, numpy as _np
    if isinstance(v, _pd.Series):
        if any(n is not None for n in v.index.names):
            v = v.reset_index()
        else:
            v = v.to_frame(name=v.name if v.name is not None else "value")
    if isinstance(v, _pd.DataFrame):
        if any(n is not None for n in v.index.names) or isinstance(v.index, _pd.MultiIndex):
            v = v.reset_index()
        cols = [str(c) for c in v.columns]
        rows = [[_cell(x) for x in r] for r in v.itertuples(index=False, name=None)]
        return cols, rows
    if isinstance(v, _np.ndarray):
        v = v.tolist()
    if isinstance(v, dict):
        return ["key", "value"], [[_cell(k), _cell(x)] for k, x in v.items()]
    if isinstance(v, (list, tuple, set)):
        rows = []
        for x in v:
            rows.append([_cell(y) for y in x] if isinstance(x, (list, tuple)) else [_cell(x)])
        return ["value"], rows
    return ["value"], [[_cell(v)]]
"""

RUNNER = (
    NORMALISE_SRC
    + r"""
import json, sys, sqlite3
import pandas as pd, numpy as np
req = json.loads(sys.stdin.read())
con = sqlite3.connect(":memory:")
con.executescript(req["db"])
env = {"pd": pd, "np": np}
for t in ("customers", "products", "orders", "order_items", "employees"):
    env[t] = pd.read_sql(f"SELECT * FROM {t}", con)
env.update(req.get("env", {}))
safe = {k: __builtins__.__dict__[k] if hasattr(__builtins__, "__dict__") else __builtins__[k]
        for k in ("abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int",
                  "isinstance", "len", "list", "map", "max", "min", "print", "range", "reversed",
                  "round", "set", "sorted", "str", "sum", "tuple", "zip", "ValueError", "KeyError",
                  "TypeError", "Exception", "ZeroDivisionError", "IndexError", "__import__")}
env["__builtins__"] = safe
try:
    exec(compile(req["code"], "<your code>", "exec"), env)
    if "result" not in env:
        out = {"error": "set a variable called result", "kind": "no_result"}
    else:
        cols, rows = _table(env["result"])
        out = {"columns": cols, "rows": rows}
except Exception as e:
    out = {"error": f"{type(e).__name__}: {e}", "kind": type(e).__name__}
sys.stdout.write(json.dumps(out))
"""
)

_KIND: dict[str, ErrorKind] = {
    "SyntaxError": "syntax",
    "NameError": "no_such_column",
    "KeyError": "no_such_column",
    "AttributeError": "no_such_column",
}


@dataclass(frozen=True, slots=True)
class PyResult:
    exec: ExecResult
    exc_type: str = ""  # Python exception class name, "" when it ran


def run_python(
    code: str, env: dict[str, Any] | None = None, *, timeout_s: float = TIMEOUT_S
) -> PyResult:
    """Run learner code in the sandbox; never raises for learner mistakes."""
    t0 = time.perf_counter()
    try:
        check_code(code)
    except SyntaxError as e:
        return PyResult(
            ExecResult((), (), f"SyntaxError: {e.msg} (line {e.lineno})", "syntax"), "SyntaxError"
        )
    except SandboxRejected as e:
        return PyResult(ExecResult((), (), str(e), "forbidden"), "Forbidden")
    payload = json.dumps({"code": code, "db": SHOP_DB, "env": env or {}})
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", RUNNER],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return PyResult(ExecResult((), (), "your code ran too long", "timeout"), "Timeout")
    ms = (time.perf_counter() - t0) * 1e3
    try:
        out = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return PyResult(
            ExecResult((), (), (proc.stderr or "the sandbox failed")[-400:], "other", ms=ms),
            "Crash",
        )
    if "error" in out:
        kind = _KIND.get(out.get("kind", ""), "other")
        return PyResult(ExecResult((), (), out["error"], kind, ms=ms), out.get("kind", ""))
    rows = tuple(tuple(r) for r in out["rows"][:500])
    return PyResult(
        ExecResult(tuple(out["columns"]), rows, truncated=len(out["rows"]) > 500, ms=ms)
    )


_REF_CACHE: dict[str, ExecResult] = {}


def run_reference(key: str, code: str, env: dict[str, Any] | None = None) -> ExecResult:
    """Run trusted reference code in-process (fast) and normalise its result."""
    if key in _REF_CACHE:
        return _REF_CACHE[key]
    import sqlite3

    import numpy as np
    import pandas as pd

    ns: dict[str, Any] = {}
    exec(NORMALISE_SRC, ns)
    con = sqlite3.connect(":memory:")
    con.executescript(SHOP_DB)
    g: dict[str, Any] = {"pd": pd, "np": np}
    for t in ("customers", "products", "orders", "order_items", "employees"):
        g[t] = pd.read_sql(f"SELECT * FROM {t}", con)
    g.update(env or {})
    exec(code, g)
    cols, rows = ns["_table"](g["result"])
    res = ExecResult(tuple(cols), tuple(tuple(r) for r in rows))
    _REF_CACHE[key] = res
    return res
