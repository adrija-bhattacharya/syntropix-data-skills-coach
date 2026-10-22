"""Export each library video's chapters (start second, title) to a small data file.

The evidence cache (``harvest/.cache/evidence``) holds whatever the verifier
read for each video - transcript windows, or the creator's chapter list - and
stays out of git.  The mistake-to-moment matcher only needs the chapter starts
and titles, so they are copied to ``harvest/data/video_segments.json``, which
ships with the app.

    python velpo.py segments [--cache DIR]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from harvest.verify import EVIDENCE_CACHE

DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "video_segments.json"
MAX_TITLE = 120


def export(cache: Path = EVIDENCE_CACHE, out: Path = OUT) -> dict[str, Any]:
    library = json.loads((DATA / "library.json").read_text(encoding="utf-8"))
    videos: dict[str, Any] = {}
    for v in library["videos"]:
        f = cache / f"{v['video_id']}.json"
        if not f.exists():
            continue
        ev = json.loads(f.read_text(encoding="utf-8"))
        segs = [
            [int(s), str(t).strip()[:MAX_TITLE]]
            for s, t in ev.get("segments", [])
            if str(t).strip()
        ]
        if len(segs) < 2:  # one "chapter" from 0:00 says nothing about where a topic is
            continue
        videos[v["video_id"]] = {
            "source": ev["source"],
            "seconds": round(v["minutes"] * 60),
            "segments": segs,
        }
    data = {"videos": videos}
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=EVIDENCE_CACHE)
    a = ap.parse_args(argv)
    data = export(a.cache)
    n = sum(len(v["segments"]) for v in data["videos"].values())
    print(f"{len(data['videos'])} videos with chapters, {n} chapters -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
