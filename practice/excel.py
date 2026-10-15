"""A small, safe Excel formula evaluator for practice tasks.

Supports cell and range references (``A1``, ``$B$2``, ``B2:C5``), numbers,
strings, booleans, the operators ``+ - * / ^ & = <> < > <= >=``, and the
functions analysts reach for first (SUM, AVERAGE, COUNTIF(S), SUMIF(S), IF,
IFERROR, VLOOKUP, XLOOKUP, INDEX, MATCH, text and date functions, UNIQUE...).
Nothing is executed: formulas are parsed into a tree and evaluated against a
read-only sheet.

:func:`shift` moves a formula's relative references the way Excel's fill-down
does, which is how a practice task checks ``$`` anchoring.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

Value = Any  # float | str | bool | dt.date | None | list (a range or array)


class ExcelError(Exception):
    """An Excel error value (#VALUE!, #N/A, #DIV/0!, #NAME?, #REF!)."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code} {detail}".strip())
        self.code = code


# ----------------------------------------------------------------- addresses
_REF = re.compile(r"(\$?)([A-Z]{1,2})(\$?)([0-9]+)")


def col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def col_letters(n: int) -> str:
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


@dataclass(frozen=True, slots=True)
class Sheet:
    """Cells keyed by address ("A1"); missing cells are blank (None)."""

    cells: dict[str, Value]

    def get(self, col: int, row: int) -> Value:
        return self.cells.get(f"{col_letters(col)}{row}")


# ------------------------------------------------------------------ tokenise
_TOKEN = re.compile(
    r"""\s*(?:
      (?P<str>"(?:[^"]|"")*")
    | (?P<range>\$?[A-Z]{1,2}\$?[0-9]+:\$?[A-Z]{1,2}\$?[0-9]+)
    | (?P<ref>\$?[A-Z]{1,2}\$?[0-9]+)(?![A-Z0-9_(])
    | (?P<num>[0-9]+(?:\.[0-9]+)?%?)
    | (?P<bool>TRUE|FALSE)(?![A-Z0-9_(])
    | (?P<func>[A-Z][A-Z0-9.]*)\s*\(
    | (?P<op><>|<=|>=|[-+*/^&=<>(),:])
    )""",
    re.VERBOSE,
)


def _tokens(src: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    text = src.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise ExcelError("#NAME?", f"can't read '{text[pos : pos + 12]}'")
        kind = m.lastgroup or ""
        out.append((kind, m.group(kind)))
        pos = m.end()
        while pos < len(text) and text[pos] == " ":
            pos += 1
    return out


# -------------------------------------------------------------------- parser
Node = tuple[Any, ...]


class _Parser:
    def __init__(self, toks: list[tuple[str, str]]) -> None:
        self.t = toks
        self.i = 0

    def peek(self) -> tuple[str, str] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise ExcelError("#VALUE!", "the formula ends too early")
        self.i += 1
        return tok

    def expect(self, val: str) -> None:
        tok = self.take()
        if tok[1] != val:
            raise ExcelError("#VALUE!", f"expected '{val}'")

    def parse(self) -> Node:
        node = self.compare()
        if self.peek() is not None:
            raise ExcelError("#VALUE!", f"unexpected '{self.peek()[1]}'")  # type: ignore[index]
        return node

    def compare(self) -> Node:
        node = self.concat()
        while (tok := self.peek()) and tok[1] in ("=", "<>", "<", ">", "<=", ">="):
            self.i += 1
            node = ("op", tok[1], node, self.concat())
        return node

    def concat(self) -> Node:
        node = self.additive()
        while (tok := self.peek()) and tok[1] == "&":
            self.i += 1
            node = ("op", "&", node, self.additive())
        return node

    def additive(self) -> Node:
        node = self.term()
        while (tok := self.peek()) and tok[1] in ("+", "-"):
            self.i += 1
            node = ("op", tok[1], node, self.term())
        return node

    def term(self) -> Node:
        node = self.power()
        while (tok := self.peek()) and tok[1] in ("*", "/"):
            self.i += 1
            node = ("op", tok[1], node, self.power())
        return node

    def power(self) -> Node:
        node = self.unary()
        while (tok := self.peek()) and tok[1] == "^":
            self.i += 1
            node = ("op", "^", node, self.unary())
        return node

    def unary(self) -> Node:
        tok = self.peek()
        if tok and tok[1] in ("-", "+"):
            self.i += 1
            inner = self.unary()
            return ("neg", inner) if tok[1] == "-" else inner
        return self.atom()

    def atom(self) -> Node:
        kind, val = self.take()
        if kind == "num":
            return ("num", float(val[:-1]) / 100 if val.endswith("%") else float(val))
        if kind == "str":
            return ("str", val[1:-1].replace('""', '"'))
        if kind == "bool":
            return ("bool", val == "TRUE")
        if kind == "ref":
            return ("ref", val)
        if kind == "range":
            return ("range", val)
        if kind == "func":
            args: list[Node] = []
            if self.peek() and self.peek()[1] == ")":  # type: ignore[index]
                self.i += 1
                return ("call", val, args)
            while True:
                if self.peek() and self.peek()[1] in (",", ")"):  # type: ignore[index]
                    args.append(("blank",))  # an omitted argument: VLOOKUP(a,b,2,)
                else:
                    args.append(self.compare())
                sep = self.take()[1]
                if sep == ")":
                    return ("call", val, args)
                if sep != ",":
                    raise ExcelError("#VALUE!", "expected ',' or ')'")
        if val == "(":
            node = self.compare()
            self.expect(")")
            return node
        raise ExcelError("#VALUE!", f"unexpected '{val}'")


def parse(formula: str) -> Node:
    src = formula.strip()
    if not src.startswith("="):
        raise ExcelError("#VALUE!", "a formula starts with =")
    return _Parser(_tokens(_upper(src[1:]))).parse()


def _upper(src: str) -> str:
    """Upper-case everything outside string literals (Excel is case-blind there)."""
    parts = re.split(r'("(?:[^"]|"")*")', src)
    return "".join(p if p.startswith('"') else p.upper() for p in parts)


# --------------------------------------------------------------- evaluation
def _cells(sheet: Sheet, rng: str) -> list[list[Value]]:
    a, b = rng.replace("$", "").split(":")
    ma, mb = _REF.fullmatch(a), _REF.fullmatch(b)
    if not ma or not mb:
        raise ExcelError("#REF!", rng)
    c1, r1, c2, r2 = (
        col_index(ma.group(2)),
        int(ma.group(4)),
        col_index(mb.group(2)),
        int(mb.group(4)),
    )
    return [
        [sheet.get(c, r) for c in range(min(c1, c2), max(c1, c2) + 1)]
        for r in range(min(r1, r2), max(r1, r2) + 1)
    ]


def _flat(v: Value) -> Iterator[Value]:
    if isinstance(v, list):
        for x in v:
            yield from _flat(x)
    else:
        yield v


def _num(v: Value) -> float:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dt.date):
        return float((v - dt.date(1899, 12, 30)).days)
    try:
        return float(str(v))
    except ValueError:
        raise ExcelError("#VALUE!", f"'{v}' is not a number") from None


def _text(v: Value) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v)


def _numbers(args: list[Value]) -> list[float]:
    """Numbers inside ranges count; text and blanks inside ranges are skipped."""
    out: list[float] = []
    for a in args:
        for v in _flat(a):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(float(v))
    return out


def _crit(c: Value) -> Callable[[Value], bool]:
    """COUNTIF-style criterion: 5, ">5", "<>East", "East", "E*"."""
    if isinstance(c, (int, float)) and not isinstance(c, bool):
        return lambda v: isinstance(v, (int, float)) and float(v) == float(c)
    s = _text(c)
    m = re.match(r"^(<=|>=|<>|<|>|=)?(.*)$", s)
    op, rhs = (m.group(1) or "="), m.group(2)  # type: ignore[union-attr]
    try:
        n = float(rhs)

        def numeric(v: Value) -> bool:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                return op == "<>"
            return {"=": v == n, "<>": v != n, "<": v < n, ">": v > n, "<=": v <= n, ">=": v >= n}[
                op
            ]

        return numeric
    except ValueError:
        pat = re.compile(
            "^" + re.escape(rhs.lower()).replace(r"\*", ".*").replace(r"\?", ".") + "$"
        )
        if op == "<>":
            return lambda v: not pat.match(_text(v).lower())
        return lambda v: bool(pat.match(_text(v).lower()))


def _match_pos(needle: Value, hay: list[Value], exact: bool) -> int:
    """1-based position; approximate mode = largest value <= needle in a sorted list."""
    if exact:
        for i, v in enumerate(hay):
            if _eq(v, needle):
                return i + 1
        raise ExcelError("#N/A", f"{_text(needle)} not found")
    best = 0
    for i, v in enumerate(hay):
        if v is None:
            continue
        try:
            if _cmp(v, needle) <= 0:
                best = i + 1
            else:
                break  # Excel's binary search assumes sorted data
        except ExcelError:
            continue
    if not best:
        raise ExcelError("#N/A", f"{_text(needle)} not found")
    return best


def _eq(a: Value, b: Value) -> bool:
    if isinstance(a, str) or isinstance(b, str):
        return _text(a).lower() == _text(b).lower()
    return _num(a) == _num(b)


def _cmp(a: Value, b: Value) -> int:
    if isinstance(a, str) and isinstance(b, str):
        x, y = a.lower(), b.lower()
        return (x > y) - (x < y)
    if isinstance(a, str) != isinstance(b, str):
        return 1 if isinstance(a, str) else -1  # text sorts after numbers
    x2, y2 = _num(a), _num(b)
    return (x2 > y2) - (x2 < y2)


def _col(v: Value) -> list[Value]:
    rows = v if isinstance(v, list) else [[v]]
    if len(rows) == 1:
        return list(rows[0])
    return [r[0] for r in rows]


def _date(v: Value) -> dt.date:
    if isinstance(v, dt.date):
        return v
    if isinstance(v, str):
        try:
            return dt.date.fromisoformat(v)
        except ValueError:
            pass
    return dt.date(1899, 12, 30) + dt.timedelta(days=int(_num(v)))


def _round(x: float, n: int) -> float:
    q = 10.0**n
    return math.floor(abs(x) * q + 0.5) / q * (1 if x >= 0 else -1)


def _call(name: str, raw: list[Node], sheet: Sheet) -> Value:
    if name == "IF":
        cond = _truthy(ev(raw[0], sheet))
        if cond:
            return ev(raw[1], sheet) if len(raw) > 1 else True
        return ev(raw[2], sheet) if len(raw) > 2 else False
    if name == "IFERROR":
        try:
            return ev(raw[0], sheet)
        except ExcelError:
            return ev(raw[1], sheet)
    args = [ev(a, sheet) for a in raw]
    nums = _numbers
    f: dict[str, Callable[[], Value]] = {
        "SUM": lambda: sum(nums(args)),
        "AVERAGE": lambda: _avg(nums(args)),
        "MIN": lambda: min(nums(args), default=0.0),
        "MAX": lambda: max(nums(args), default=0.0),
        "COUNT": lambda: float(len(nums(args))),
        "COUNTA": lambda: float(sum(1 for a in args for v in _flat(a) if v not in (None, ""))),
        "COUNTBLANK": lambda: float(sum(1 for a in args for v in _flat(a) if v in (None, ""))),
        "ROUND": lambda: _round(_num(args[0]), int(_num(args[1]))),
        "ABS": lambda: abs(_num(args[0])),
        "AND": lambda: all(_truthy(v) for a in args for v in _flat(a)),
        "OR": lambda: any(_truthy(v) for a in args for v in _flat(a)),
        "NOT": lambda: not _truthy(args[0]),
        "LEN": lambda: float(len(_text(args[0]))),
        "UPPER": lambda: _text(args[0]).upper(),
        "LOWER": lambda: _text(args[0]).lower(),
        "PROPER": lambda: _text(args[0]).title(),
        "TRIM": lambda: " ".join(_text(args[0]).split()),
        "LEFT": lambda: _text(args[0])[: int(_num(args[1])) if len(args) > 1 else 1],
        "RIGHT": lambda: _text(args[0])[-int(_num(args[1])) if len(args) > 1 else -1 :],
        "MID": lambda: _text(args[0])[
            int(_num(args[1])) - 1 : int(_num(args[1])) - 1 + int(_num(args[2]))
        ],
        "CONCAT": lambda: "".join(_text(v) for a in args for v in _flat(a)),
        "CONCATENATE": lambda: "".join(_text(v) for a in args for v in _flat(a)),
        "YEAR": lambda: float(_date(args[0]).year),
        "MONTH": lambda: float(_date(args[0]).month),
        "DAY": lambda: float(_date(args[0]).day),
        "SUMIF": lambda: _sumif(args),
        "COUNTIF": lambda: float(sum(1 for v in _flat(args[0]) if _crit(args[1])(v))),
        "AVERAGEIF": lambda: _avg(_ifvals(args[0], args[1], args[2] if len(args) > 2 else args[0])),
        "SUMIFS": lambda: sum(_multi(args[0], args[1:])),
        "COUNTIFS": lambda: float(len(_multi([[1.0]] * len(list(_flat(args[0]))), args))),
        "VLOOKUP": lambda: _vlookup(args),
        "XLOOKUP": lambda: _xlookup(args),
        "INDEX": lambda: _index(args),
        "MATCH": lambda: float(
            _match_pos(args[0], _col(args[1]), exact=len(args) > 2 and _num(args[2]) == 0)
        ),
        "UNIQUE": lambda: [[v] for v in dict.fromkeys(v for v in _flat(args[0]) if v is not None)],
    }
    if name not in f:
        raise ExcelError("#NAME?", f"{name} isn't supported here")
    try:
        return f[name]()
    except IndexError:
        raise ExcelError("#VALUE!", f"{name} is missing an argument") from None


def _avg(xs: list[float]) -> float:
    if not xs:
        raise ExcelError("#DIV/0!", "nothing to average")
    return sum(xs) / len(xs)


def _ifvals(rng: Value, crit: Value, vals: Value) -> list[float]:
    keys, data = list(_flat(rng)), list(_flat(vals))
    test = _crit(crit)
    return [float(d) for k, d in zip(keys, data) if test(k) and isinstance(d, (int, float))]


def _sumif(args: list[Value]) -> float:
    return sum(_ifvals(args[0], args[1], args[2] if len(args) > 2 else args[0]))


def _multi(vals: Value, pairs: list[Value]) -> list[float]:
    data = list(_flat(vals))
    keep = [True] * len(data)
    for k in range(0, len(pairs) - 1, 2):
        rng, test = list(_flat(pairs[k])), _crit(pairs[k + 1])
        if len(rng) != len(data):
            raise ExcelError("#VALUE!", "criteria ranges must be the same size")
        keep = [a and test(v) for a, v in zip(keep, rng)]
    return [float(d) for d, k in zip(data, keep) if k and isinstance(d, (int, float))]


def _vlookup(args: list[Value]) -> Value:
    table = args[1] if isinstance(args[1], list) else [[args[1]]]
    col = int(_num(args[2]))
    approx = len(args) < 4 or args[3] is None or _truthy(args[3])
    pos = _match_pos(args[0], [r[0] for r in table], exact=not approx)
    if col < 1 or col > len(table[0]):
        raise ExcelError("#REF!", "column index is outside the table")
    return table[pos - 1][col - 1]


def _xlookup(args: list[Value]) -> Value:
    keys, vals = _col(args[1]), _col(args[2])
    try:
        return vals[_match_pos(args[0], keys, exact=True) - 1]
    except ExcelError:
        if len(args) > 3:
            return args[3]
        raise


def _index(args: list[Value]) -> Value:
    table = args[0] if isinstance(args[0], list) else [[args[0]]]
    r = int(_num(args[1]))
    c = int(_num(args[2])) if len(args) > 2 else 1
    if len(table) == 1 and len(args) == 2:  # INDEX over a single row
        r, c = 1, r
    try:
        return table[r - 1][c - 1]
    except IndexError:
        raise ExcelError("#REF!", "INDEX is outside the range") from None


def _truthy(v: Value) -> bool:
    if isinstance(v, str):
        if v.upper() in ("TRUE", "FALSE"):
            return v.upper() == "TRUE"
        raise ExcelError("#VALUE!", f"'{v}' is not TRUE/FALSE")
    return bool(_num(v))


def ev(node: Node, sheet: Sheet) -> Value:
    kind = node[0]
    if kind in ("num", "str", "bool"):
        return node[1]
    if kind == "blank":
        return None
    if kind == "ref":
        m = _REF.fullmatch(node[1])
        if m is None:
            raise ExcelError("#REF!", node[1])
        return sheet.get(col_index(m.group(2)), int(m.group(4)))
    if kind == "range":
        return _cells(sheet, node[1])
    if kind == "neg":
        return -_num(ev(node[1], sheet))
    if kind == "call":
        return _call(node[1], node[2], sheet)
    op, a, b = node[1], ev(node[2], sheet), ev(node[3], sheet)
    if op == "&":
        return _text(a) + _text(b)
    if op in ("=", "<>", "<", ">", "<=", ">="):
        c = 0 if (op in ("=", "<>") and _eq(a, b)) else _cmp(a, b)
        return {"=": c == 0, "<>": c != 0, "<": c < 0, ">": c > 0, "<=": c <= 0, ">=": c >= 0}[op]
    x, y = _num(a), _num(b)
    if op == "+":
        return x + y
    if op == "-":
        return x - y
    if op == "*":
        return x * y
    if op == "/":
        if y == 0:
            raise ExcelError("#DIV/0!", "division by zero")
        return x / y
    return x**y


def evaluate(formula: str, sheet: Sheet) -> Value:
    """Evaluate ``formula`` (starting with ``=``); an array result keeps its shape."""
    return ev(parse(formula), sheet)


def shift(formula: str, rows: int) -> str:
    """The formula as Excel would write it after filling down ``rows`` rows:
    relative row numbers move, ``$``-anchored ones stay."""

    def move(m: re.Match[str]) -> str:
        cd, col, rd, row = m.groups()
        return f"{cd}{col}{rd}{row if rd else int(row) + rows}"

    parts = re.split(r'("(?:[^"]|"")*")', formula)
    return "".join(p if p.startswith('"') else _REF.sub(move, p.upper()) for p in parts)


def display(v: Value) -> str:
    """How a cell would show the value."""
    if isinstance(v, list):
        return ", ".join(display(x) for x in _flat(v))
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.4g}"
    if isinstance(v, dt.date):
        return v.isoformat()
    return "" if v is None else str(v)
