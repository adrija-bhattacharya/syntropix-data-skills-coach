"""Tiny stdlib HTTP with an on-disk cache - no ``requests`` dependency.

Every GET is cached under ``harvest/.cache/<sha1(url)>.json`` so a second run
(and the whole test suite) is offline and instant.  ``VELPO_HARVEST_OFFLINE=1``
forces cache-only (a miss raises ``OfflineError``).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_CACHE = Path(__file__).resolve().parent / ".cache"
_TTL_S = 14 * 24 * 3600
_UA = "VELPO/1.0 (learning-path optimiser; educational project)"


class OfflineError(RuntimeError):
    pass


def _offline() -> bool:
    return os.environ.get("VELPO_HARVEST_OFFLINE") == "1"


def _path(url: str) -> Path:
    return _CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".json")


def _cached_body(cache: Path) -> str:
    return str(json.loads(cache.read_text())["body"])


def get(url: str, *, refresh: bool = False, timeout: float = 20.0, delay: float = 0.1) -> str:
    cache = _path(url)
    if not refresh and cache.exists() and (time.time() - cache.stat().st_mtime) < _TTL_S:
        return _cached_body(cache)
    if _offline():
        if cache.exists():
            return _cached_body(cache)
        raise OfflineError(f"offline and no cache for {url}")
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    body = ""
    last: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
            break
        except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
            last = exc
            time.sleep(1.0 * 2**attempt)  # 1, 2, 4, 8, 16s - ride out 429s
    else:
        if cache.exists():
            return _cached_body(cache)
        raise OfflineError(f"fetch failed for {url}: {last}")
    time.sleep(delay)  # be polite to the free APIs
    _CACHE.mkdir(exist_ok=True)
    cache.write_text(json.dumps({"url": url, "body": body}))
    return body


def get_json(url: str, *, refresh: bool = False, delay: float = 0.1) -> Any:
    return json.loads(get(url, refresh=refresh, delay=delay))
