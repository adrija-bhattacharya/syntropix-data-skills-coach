"""Proof-of-skill portfolio.

Every practice answer the app *runs and checks correct* is recorded for the
learner, with the code, the checks it passed and the topic.  Finished projects
(repo / demo links + a summary) are added by the learner.  The public page
re-runs every recorded answer through the same grader when it is built, so the
proof is the work itself, re-checked, not a badge anyone could claim.

Storage: one JSON file per learner under ``state/portfolio`` (outside git).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STATE = Path(__file__).resolve().parent / "state" / "portfolio"
_SLUG = re.compile(r"[^a-z0-9]+")
_URL = re.compile(r"^https://[^\s<>\"']{3,300}$")


@dataclass
class Solve:
    task_id: str
    concept: str  # graph id
    concept_name: str
    domain: str
    kind: str  # sql | python | excel | value
    prompt: str
    answer: str
    checks: list[str]
    result_preview: list[list[Any]]
    columns: list[str]
    solved_at: str
    attempts: int


@dataclass
class Project:
    project_id: str
    title: str
    summary: str
    skills: list[str]
    repo_url: str
    demo_url: str
    added_at: str
    link_ok: bool | None = None  # repo answered when added (None = not checked)


@dataclass
class Portfolio:
    learner_id: str
    slug: str
    name: str = ""
    headline: str = ""
    github: str = ""
    linkedin: str = ""
    public: bool = False
    solves: list[Solve] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    mastery: dict[str, float] = field(default_factory=dict)  # concept name -> latest mastery
    key_hash: str = ""  # sha256 of the owner's edit key ("" = not claimed yet)


def _path(learner_id: str) -> Path:
    safe = hashlib.sha1(learner_id.encode()).hexdigest()[:16]
    return STATE / f"{safe}.json"


def slugify(name: str) -> str:
    s = _SLUG.sub("-", name.lower()).strip("-")[:40]
    return s or "learner"


def load(learner_id: str) -> Portfolio:
    p = _path(learner_id)
    if not p.exists():
        return Portfolio(learner_id, f"learner-{secrets.token_hex(3)}")
    d = json.loads(p.read_text(encoding="utf-8"))
    return Portfolio(
        **{k: v for k, v in d.items() if k not in ("solves", "projects")},
        solves=[Solve(**s) for s in d.get("solves", [])],
        projects=[Project(**x) for x in d.get("projects", [])],
    )


def save(pf: Portfolio) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    _path(pf.learner_id).write_text(
        json.dumps(asdict(pf), indent=1, ensure_ascii=False), encoding="utf-8"
    )


def by_slug(slug: str) -> Portfolio | None:
    if not STATE.exists():
        return None
    for p in STATE.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("slug") == slug:
            return load(d["learner_id"])
    return None


def record_solve(learner_id: str, solve: Solve, mastery: dict[str, float]) -> Portfolio:
    """Keep the learner's latest correct answer per task."""
    pf = load(learner_id)
    pf.solves = [s for s in pf.solves if s.task_id != solve.task_id] + [solve]
    pf.mastery.update({k: round(v, 3) for k, v in mastery.items()})
    save(pf)
    return pf


def set_profile(
    learner_id: str, *, name: str, headline: str, github: str, linkedin: str, public: bool
) -> Portfolio:
    pf = load(learner_id)
    for url in (github, linkedin):
        if url and not _URL.match(url):
            raise ValueError(f"links must start with https:// ({url!r})")
    if name and name != pf.name:
        wanted = slugify(name)
        other = by_slug(wanted)
        pf.slug = (
            wanted
            if other is None or other.learner_id == learner_id
            else f"{wanted}-{secrets.token_hex(2)}"
        )
    pf.name, pf.headline, pf.github, pf.linkedin, pf.public = (
        name,
        headline,
        github,
        linkedin,
        public,
    )
    save(pf)
    return pf


def add_project(learner_id: str, project: Project) -> Portfolio:
    for url in (project.repo_url, project.demo_url):
        if url and not _URL.match(url):
            raise ValueError(f"links must start with https:// ({url!r})")
    if not project.repo_url and not project.demo_url:
        raise ValueError("add a link to your repo or demo")
    pf = load(learner_id)
    pf.projects = [p for p in pf.projects if p.project_id != project.project_id] + [project]
    save(pf)
    return pf


def remove(
    learner_id: str, *, task_id: str | None = None, project_id: str | None = None
) -> Portfolio:
    pf = load(learner_id)
    pf.solves = [s for s in pf.solves if s.task_id != task_id]
    pf.projects = [p for p in pf.projects if p.project_id != project_id]
    save(pf)
    return pf


def check_link(url: str) -> bool | None:
    """Does the link answer?  None when we couldn't tell (offline)."""
    import urllib.request

    try:
        req = urllib.request.Request(
            url, method="GET", headers={"User-Agent": "Mozilla/5.0 Syntropix"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return bool(200 <= r.status < 400)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# ownership: an edit key, issued once, kept by the owner's browser
# --------------------------------------------------------------------------- #
def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def claim(learner_id: str) -> str | None:
    """Issue the edit key the first time; None when the portfolio already has one."""
    pf = load(learner_id)
    if pf.key_hash:
        return None
    key = secrets.token_urlsafe(24)
    pf.key_hash = _hash(key)
    save(pf)
    return key


def owns(learner_id: str, key: str | None) -> bool:
    """True when ``key`` opens this portfolio (or it hasn't been claimed yet)."""
    import hmac

    pf = load(learner_id)
    if not pf.key_hash:
        return True
    return bool(key) and hmac.compare_digest(_hash(key or ""), pf.key_hash)


# --------------------------------------------------------------------------- #
# re-verification: run every recorded answer through the grader again
# --------------------------------------------------------------------------- #
_RECHECK: dict[str, bool] = {}


def recheck(solve: Solve) -> bool:
    """True when the recorded answer still passes the task today."""
    from practice.catalogue import BY_ID, grade_task

    key = hashlib.sha256(f"{solve.task_id}\n{solve.answer}".encode()).hexdigest()
    if key not in _RECHECK:
        task = BY_ID.get(solve.task_id)
        _RECHECK[key] = bool(task and grade_task(task, solve.answer).correct)
    return _RECHECK[key]


def public_view(pf: Portfolio) -> dict[str, Any]:
    """What the shareable page shows: profile, re-checked solves per skill, projects."""
    skills: dict[str, list[dict[str, Any]]] = {}
    for s in sorted(pf.solves, key=lambda s: s.solved_at, reverse=True):
        skills.setdefault(s.domain, []).append({**asdict(s), "rechecked": recheck(s)})
    return {
        "name": pf.name or "A Syntropix learner",
        "headline": pf.headline,
        "github": pf.github,
        "linkedin": pf.linkedin,
        "slug": pf.slug,
        "public": pf.public,
        "skills": skills,
        "projects": [
            asdict(p) for p in sorted(pf.projects, key=lambda p: p.added_at, reverse=True)
        ],
        "solved": len(pf.solves),
        "rechecked_ok": sum(1 for s in pf.solves if recheck(s)),
        "mastery": pf.mastery,
        "built": dt.datetime.now().strftime("%d %b %Y, %H:%M"),
    }
