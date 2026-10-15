"""Study-context telemetry: when and how each practice attempt went.

One small JSON file per learner under ``state/telemetry`` (outside git), used to
learn the learner's best study times (claim G4) and focus span (claim G5).
Only what those need is kept: local time, whether the answer was right, what the
model expected, and the minutes already spent in the current session.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

STATE = Path(__file__).resolve().parent / "state" / "telemetry"
KEEP = 3000  # most recent attempts per learner
SESSION_GAP_MIN = 30.0  # a pause longer than this starts a new session


@dataclass(frozen=True, slots=True)
class Event:
    at: str  # local ISO time of the answer
    hour: int
    weekday: int  # 0 = Monday
    correct: bool
    expected: float  # the model's P(correct) before the answer
    session_min: float  # minutes since this session's first attempt
    concept: str


def _path(learner_id: str) -> Path:
    return STATE / f"{hashlib.sha1(learner_id.encode()).hexdigest()[:16]}.json"


def load(learner_id: str) -> list[Event]:
    p = _path(learner_id)
    if not p.exists():
        return []
    return [Event(**e) for e in json.loads(p.read_text(encoding="utf-8"))]


def record(
    learner_id: str, *, correct: bool, expected: float, concept: str, now: datetime | None = None
) -> Event:
    """Append one attempt; the session clock restarts after a long pause."""
    now = now or datetime.now()
    events = load(learner_id)
    session_min = 0.0
    if events:
        last = datetime.fromisoformat(events[-1].at)
        gap = (now - last).total_seconds() / 60
        if 0 <= gap <= SESSION_GAP_MIN:
            session_min = events[-1].session_min + gap
    ev = Event(
        now.isoformat(timespec="seconds"), now.hour, now.weekday(), correct,
        round(expected, 4), round(session_min, 2), concept,
    )  # fmt: skip
    events = [*events, ev][-KEEP:]
    STATE.mkdir(parents=True, exist_ok=True)
    _path(learner_id).write_text(json.dumps([asdict(e) for e in events]), encoding="utf-8")
    return ev
