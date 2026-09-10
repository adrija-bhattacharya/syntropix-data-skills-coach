"""The FastAPI app serves the built React SPA (or a friendly hint)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import api
from curriculum import build_curriculum
from engine import Engine, MemoryStore


def test_root_serves_spa_or_hint() -> None:
    api.engine = Engine(build_curriculum(), store=MemoryStore())
    c = TestClient(api.app)
    r = c.get("/")
    assert r.status_code == 200
    if (api._WEB / "index.html").exists():
        assert "text/html" in r.headers["content-type"]
        assert '<div id="root">' in r.text
        # a client-side route falls back to index.html, not 404
        assert c.get("/teacher").status_code == 200
    else:
        assert "npm run build" in r.json()["message"]


def test_docs_still_reachable() -> None:
    c = TestClient(api.app)
    assert c.get("/openapi.json").status_code == 200
