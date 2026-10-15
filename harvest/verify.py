"""Does a video actually teach its topic?  Semantic checks for the library.

    python velpo.py verify-videos            # -> harvest/data/video_checks.json

The harvester picks videos by search rank, channel and a title-keyword rule.
This pass reads what the video *says* and judges whether it teaches the topic it
was picked for, and where in the video that happens:

* **evidence**, best available per video (recorded with each verdict):
  1. the spoken **transcript** (when YouTube serves captions),
  2. else the creator's **description + chapter list** ("05:40 Window functions"),
  3. else the title alone (verdict marked low-evidence);
* **judge**:
  * ``claude`` - when ``ANTHROPIC_API_KEY`` is set and the ``anthropic`` package
    is installed: an LLM reads topic + evidence and answers in JSON;
  * ``local`` (default, offline, deterministic) - each topic of the skill gets a
    rich profile (its name, the skill-check questions and right answers, the
    practice tasks and hints).  A video *teaches* its topic when, by TF-IDF
    cosine similarity, the evidence is closer to that topic than to almost every
    other topic of the same skill (rank test), and not merely similar to all of
    them.  This is a discriminative check: "about SQL" is not enough, it has to
    be about *window functions*.
* **where**: the chapter (or transcript minute) that best matches the topic
  becomes a jump-to timestamp, so the player starts at the right moment.

Whole-skill courses get a coverage score instead: how many of the skill's
topics their chapters/transcript visibly cover.

Results are cached per video id; re-running only checks videos that are new or
were judged on weaker evidence (e.g. when captions become available).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from harvest.library import _get

DATA = Path(__file__).resolve().parent / "data"
CHECKS = DATA / "video_checks.json"
EVIDENCE_CACHE = (
    Path(__file__).resolve().parent / ".cache" / "evidence"
)  # raw evidence, not committed
LIBRARY = DATA / "library.json"
EVIDENCE_RANK = {"title": 0, "description": 1, "transcript": 2}
TOP_RANK = 3  # own topic must be among the 3 closest topics of the skill


# --------------------------------------------------------------------------- #
# evidence
# --------------------------------------------------------------------------- #
@dataclass
class Evidence:
    source: str  # transcript | description | title
    text: str
    segments: list[tuple[int, str]]  # (start second, text) - chapters or transcript windows


_TS = re.compile(r"(?:^|[\s(\[])((?:\d{1,2}:)?\d{1,2}:\d{2})(?:[)\]]|\s|$)")


def _seconds(ts: str) -> int:
    s = 0
    for p in ts.split(":"):
        s = s * 60 + int(p)
    return s


def parse_chapters(description: str) -> list[tuple[int, str]]:
    """Chapter list from a description: lines with a timestamp and a title."""
    out: list[tuple[int, str]] = []
    for line in description.splitlines():
        m = _TS.search(line)
        if not m:
            continue
        title = line[: m.start(1)] + line[m.end(1) :]
        title = re.sub(r"^\W+|[^\w)?!]+$", "", title.strip())  # bullets, emoji, dashes
        if len(title) >= 3:
            out.append((_seconds(m.group(1)), title))
    out.sort()
    # a real chapter list starts at 0:00 and has a few entries
    return out if len(out) >= 3 and out[0][0] <= 15 else []


def _transcript(video_id: str) -> list[tuple[int, str]] | None:
    """60-second transcript windows, or None when captions can't be had."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None
    try:
        snippets = list(YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-US", "en-GB"]))
    except Exception:
        return None
    windows: dict[int, list[str]] = {}
    for s in snippets:
        windows.setdefault(int(s.start) // 60 * 60, []).append(s.text)
    return [(k, " ".join(v)) for k, v in sorted(windows.items())]


def _watch_page(video_id: str) -> dict[str, Any]:
    html = _get(f"https://www.youtube.com/watch?v={video_id}&hl=en")
    m = re.search(r"var ytInitialPlayerResponse = (\{.*?\});(?:var|</script>)", html, re.S)
    if not m:
        return {}
    details: dict[str, Any] = json.loads(m.group(1)).get("videoDetails", {})
    return details


_BOILER = re.compile(
    r"https?://|www\.|#\w|subscribe|patreon|discord|instagram|twitter|facebook|tiktok|"
    r"linkedin|sponsor|affiliate|merch|newsletter|follow (me|us)|join (this|my)|"
    r"support (the|my)|coupon|discount",
    re.I,
)


def clean_description(desc: str) -> str:
    """Drop link / social / sponsor lines: they say nothing about the topic."""
    keep = [ln for ln in desc.splitlines() if ln.strip() and not _BOILER.search(ln)]
    return "\n".join(keep)


def evidence_text(title: str, body: str) -> str:
    """The title is the creator's own statement of the topic: weigh it 3x."""
    return f"{title}. {title}. {title}. {body}"


class Fetcher:
    """Gets evidence politely: one watch page per call, transcripts only until
    YouTube says no (then stops asking for the rest of the run).  Evidence is
    cached, so re-judging never needs the network."""

    def __init__(self, use_transcripts: bool = True, pause: float = 1.5) -> None:
        self.use_transcripts = use_transcripts
        self.pause = pause
        self.transcript_failures = 0

    def __call__(self, video: dict[str, Any]) -> Evidence:
        vid = video["video_id"]
        cached = EVIDENCE_CACHE / f"{vid}.json"
        if cached.exists():
            d = json.loads(cached.read_text(encoding="utf-8"))
            want_transcript = self.use_transcripts and self.transcript_failures < 3
            if d["source"] == "transcript" or not want_transcript:
                segs = [(int(a), str(b)) for a, b in d["segments"]]
                return Evidence(d["source"], d["text"], segs)
        ev = self._fetch(video)
        EVIDENCE_CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(asdict(ev), ensure_ascii=False), encoding="utf-8")
        return ev

    def _fetch(self, video: dict[str, Any]) -> Evidence:
        vid = video["video_id"]
        if self.use_transcripts and self.transcript_failures < 3:
            t = _transcript(vid)
            time.sleep(self.pause)
            if t:
                spoken = " ".join(x for _, x in t)
                return Evidence("transcript", evidence_text(video["title"], spoken), t)
            self.transcript_failures += 1
        try:
            details = _watch_page(vid)
        except Exception:
            details = {}
        time.sleep(self.pause)
        desc = str(details.get("shortDescription", ""))
        if desc.strip():
            body = clean_description(desc)
            return Evidence(
                "description", evidence_text(video["title"], body), parse_chapters(desc)
            )
        return Evidence("title", video["title"], [])


# --------------------------------------------------------------------------- #
# topic profiles
# --------------------------------------------------------------------------- #
def topic_profiles(domain: str) -> dict[str, str]:
    """concept -> a paragraph describing it: name, skill-check questions with
    their right answers, practice prompts and hints."""
    from assessment_bank import _seed_bank
    from domains import seed_graph
    from practice.catalogue import hints_for, tasks_for

    kg = seed_graph(domain)
    bank = _seed_bank(domain)
    mcq, task = bank if bank else ({}, {})
    out: dict[str, str] = {}
    for c in kg.concept_ids:
        parts = [kg.concepts[c].name] * 3  # the name counts most
        for stem, choices, right in mcq.get(c, []):
            parts += [stem, choices[right]]
        if c in task:
            parts.append(task[c][0])
        for t in tasks_for(c):
            parts.append(t.prompt)
            parts += [h for h in hints_for(t)[:1] if h]
        out[c] = " ".join(parts)
    return out


# --------------------------------------------------------------------------- #
# judges
# --------------------------------------------------------------------------- #
@dataclass
class Verdict:
    teaches: bool
    level: str  # verified | related | off-topic | covers (courses)
    score: float  # similarity to the own topic (local) or the LLM's confidence
    rank: int  # 1 = closest topic of the skill (local judge)
    start: int  # jump-to second (0 = from the start)
    chapter: str  # the matching chapter / transcript snippet
    reason: str
    judge: str
    source: str
    coverage: list[str]  # courses: topics the video covers
    checked: str


_STOP = set(
    "the a an and or of to in on for with is are be this that it as by at from you your we our i "  # noqa: SIM905
    "how what why when which can will use using into about learn tutorial course video full part "
    "beginners beginner guide step easy minutes min hour hours introduction intro explained".split()
)


def _tokens(text: str) -> str:
    """Lower-case, British -> American spelling, light stemming (sorting -> sort)."""
    from harvest.library import _norm, _stem

    words = re.findall(r"[a-z][a-z0-9_+#.]*", _norm(text))
    return " ".join(_stem(w.strip(".")) for w in words if w not in _STOP and len(w) > 1)


class LocalJudge:
    """TF-IDF over the skill's topic profiles; rank test + chapter matching."""

    name = "local"

    def __init__(self, profiles: dict[str, str]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.topics = list(profiles)
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)
        self.matrix = self.vec.fit_transform([_tokens(profiles[t]) for t in self.topics])

    def _sims(self, text: str) -> list[float]:
        from sklearn.metrics.pairwise import cosine_similarity

        v = self.vec.transform([_tokens(text)])
        return [float(x) for x in cosine_similarity(v, self.matrix)[0]]

    def lesson(self, topic: str, ev: Evidence, title: str = "") -> Verdict:
        sims = self._sims(ev.text)
        own = sims[self.topics.index(topic)]
        rank = 1 + sum(1 for s in sims if s > own)
        best_seg, best_s = (0, ""), -1.0
        for start, seg in ev.segments:
            s = self._sims(seg)[self.topics.index(topic)]
            if s > best_s:
                best_seg, best_s = (start, seg), s
        if own <= 0.0:
            level = "off-topic"
        elif rank == 1 or (rank <= TOP_RANK and best_s >= 0.2):
            level = "verified"
        elif rank <= TOP_RANK + 2:
            level = "related"
        else:
            level = "off-topic"
        closest = self.topics[max(range(len(sims)), key=sims.__getitem__)]
        reason = (
            f"Its {ev.source} is closest to this topic of all {len(sims)} topics of the skill."
            if rank == 1
            else f"Its {ev.source} ranks this topic #{rank} of {len(sims)}; closest is '{closest}'."
        )
        if level == "off-topic" and title:
            t_sims = self._sims(title)
            t_own = t_sims[self.topics.index(topic)]
            if t_own > 0 and all(t_own >= x for x in t_sims):
                level = "related"  # the title names exactly this topic; the rest is broader
                reason += " Its title names this topic, so it is kept as related."
        use_seg = best_s >= 0.1 and best_seg[0] > 0
        return Verdict(
            level != "off-topic", level, round(own, 3), rank,
            best_seg[0] if use_seg else 0, best_seg[1][:120] if use_seg else "",
            reason, self.name, ev.source, [], dt.date.today().isoformat(),
        )  # fmt: skip

    def course(self, ev: Evidence) -> Verdict:
        segs = ev.segments or [(0, ev.text)]
        covered: set[str] = set()
        for _start, seg in segs:
            sims = self._sims(seg)
            i = max(range(len(sims)), key=sims.__getitem__)
            if sims[i] >= 0.12:
                covered.add(self.topics[i])
        n = len(self.topics)
        return Verdict(
            bool(covered), "covers", round(len(covered) / n, 3), 0, 0, "",
            f"Covers {len(covered)} of the {n} topics of the skill (from its {ev.source}).",
            self.name, ev.source, sorted(covered), dt.date.today().isoformat(),
        )  # fmt: skip


class ClaudeJudge:
    """An LLM judge - used when ``ANTHROPIC_API_KEY`` is set."""

    name = "claude"
    PROMPT = (
        "You check whether a YouTube video teaches a specific data-skills topic well enough "
        "to recommend it for that topic.\n\nTopic: {topic}\nWhat the topic covers: {profile}\n\n"
        "Video title: {title}\nChannel: {channel}\nEvidence ({source}):\n{evidence}\n\n"
        'Answer with JSON only: {{"teaches": true|false, "confidence": 0..1, '
        '"start_seconds": <where the topic is taught, 0 if unknown>, "reason": "<one sentence>"}}'
    )

    def __init__(self, profiles: dict[str, str], names: dict[str, str], client: Any = None) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.profiles = profiles
        self.names = names
        self.model = os.environ.get("SYNTROPIX_JUDGE_MODEL", "claude-haiku-5-5")
        self.local = LocalJudge(profiles)  # courses + fallback

    def lesson(self, topic: str, ev: Evidence, video: dict[str, Any] | None = None) -> Verdict:
        video = video or {}
        evidence = ev.text[:6000]
        if ev.segments:
            evidence += "\nChapters/segments: " + "; ".join(
                f"{s}s {t[:80]}" for s, t in ev.segments[:40]
            )
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": self.PROMPT.format(
                topic=self.names.get(topic, topic), profile=self.profiles[topic][:1500],
                title=video.get("title", ""), channel=video.get("channel", ""),
                source=ev.source, evidence=evidence,
            )}],
        )  # fmt: skip
        raw = "".join(getattr(b, "text", "") for b in msg.content)
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return self.local.lesson(topic, ev)
        data = json.loads(m.group(0))
        ok = bool(data.get("teaches"))
        conf = float(data.get("confidence", 0.5))
        return Verdict(
            ok, "verified" if ok and conf >= 0.6 else "related" if ok else "off-topic",
            round(conf, 3), 0, int(data.get("start_seconds") or 0), "",
            str(data.get("reason", ""))[:300], self.name, ev.source, [],
            dt.date.today().isoformat(),
        )  # fmt: skip

    def course(self, ev: Evidence) -> Verdict:
        return self.local.course(ev)


def make_judge(profiles: dict[str, str], names: dict[str, str]) -> LocalJudge | ClaudeJudge:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return ClaudeJudge(profiles, names)
        except ImportError:
            pass
    return LocalJudge(profiles)


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #
def load_checks() -> dict[str, dict[str, Any]]:
    if not CHECKS.exists():
        return {}
    data: dict[str, dict[str, Any]] = json.loads(CHECKS.read_text(encoding="utf-8"))
    return data


def verify(
    library: dict[str, Any],
    fetch: Callable[[dict[str, Any]], Evidence],
    old: dict[str, dict[str, Any]] | None = None,
    *,
    redo: bool = False,
    judge_factory: Callable[[dict[str, str], dict[str, str]], Any] = make_judge,
) -> dict[str, dict[str, Any]]:
    """Check every library video; keep earlier verdicts unless ``redo`` or the
    earlier verdict rests on weaker evidence than the title-only fallback."""
    from domains import seed_graph

    checks = dict(old or {})
    judges: dict[str, Any] = {}
    for v in library["videos"]:
        prev = checks.get(v["video_id"])
        if prev and not redo and EVIDENCE_RANK.get(prev["source"], 0) > 0:
            continue
        d = v["domain"]
        if d not in judges:
            kg = seed_graph(d)
            judges[d] = judge_factory(
                topic_profiles(d), {c: kg.concepts[c].name for c in kg.concept_ids}
            )
        ev = fetch(v)
        j = judges[d]
        if v["kind"] == "course" or not v.get("concept"):
            verdict = j.course(ev)
        elif isinstance(j, ClaudeJudge):
            verdict = j.lesson(v["concept"], ev, v)
        else:
            verdict = j.lesson(v["concept"], ev, v.get("title", ""))
        checks[v["video_id"]] = asdict(verdict)
    return checks


def main(argv: list[str] | None = None) -> int:
    import sys

    args = sys.argv[1:] if argv is None else argv
    library = json.loads(LIBRARY.read_text(encoding="utf-8"))
    fetch = Fetcher(use_transcripts="--no-transcripts" not in args)
    checks = verify(library, fetch, load_checks(), redo="--redo" in args)
    CHECKS.write_text(json.dumps(checks, indent=1, ensure_ascii=False), encoding="utf-8")
    lessons = [
        c for v in library["videos"] if v["kind"] == "lesson" and (c := checks.get(v["video_id"]))
    ]
    by: dict[str, int] = {}
    src: dict[str, int] = {}
    for c in lessons:
        by[c["level"]] = by.get(c["level"], 0) + 1
        src[c["source"]] = src.get(c["source"], 0) + 1
    print(f"lessons: {by}  evidence: {src}  judge: {lessons[0]['judge'] if lessons else '-'}")
    print(f"written {CHECKS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
