"""One adapter per open source.  Each ``search_*(query) -> list[RawResource]``.

All keyless except YouTube, which reads ``YOUTUBE_API_KEY`` from the environment
and quietly returns ``[]`` when it is absent.
"""

from __future__ import annotations

import html
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence

from harvest.http import OfflineError, get, get_json
from harvest.model import RawResource

Source = Callable[[str], list[RawResource]]

_WIKI_API = "https://{host}/w/api.php"
_REST_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


def _q(s: str) -> str:
    return urllib.parse.quote(s)


def _safe(fn: Source, query: str) -> list[RawResource]:
    try:
        return fn(query)
    except OfflineError:
        return []
    except Exception:  # a flaky source must not sink the whole harvest
        return []


# --------------------------------------------------------------------------- #
def search_wikipedia(query: str, *, limit: int = 3) -> list[RawResource]:
    out: list[RawResource] = []
    canon = _wikipedia_canonical(query)
    if canon is not None:
        out.append(canon)
    for r in _mediawiki("en.wikipedia.org", "wikipedia", "article", query, limit):
        if r.key() != (canon.key() if canon else ""):
            out.append(r)
    return out


def _wikipedia_canonical(query: str) -> RawResource | None:
    """The article the concept name resolves to (redirects followed).  This is
    almost always *the* right article, so it bypasses the relevance gate."""
    try:
        s = get_json(_REST_SUMMARY.format(title=_q(query.replace(" ", "_"))))
    except Exception:
        return None
    if s.get("type") == "disambiguation" or not s.get("extract"):
        return None
    page = s.get("titles", {}).get("canonical") or s["title"].replace(" ", "_")
    return RawResource(
        source="wikipedia",
        kind="article",
        title=s["title"],
        url=f"https://en.wikipedia.org/wiki/{_q(page)}",
        summary=s.get("extract", ""),
        minutes=12.0,
        metadata={"canonical": True},
    )


def search_wikibooks(query: str, *, limit: int = 2) -> list[RawResource]:
    return _mediawiki("en.wikibooks.org", "wikibooks", "book", query, limit)


def _mediawiki(host: str, source: str, kind: str, query: str, limit: int) -> list[RawResource]:
    url = _WIKI_API.format(host=host) + (
        f"?action=query&list=search&srsearch={_q(query)}&srlimit={limit}&format=json"
    )
    hits = get_json(url).get("query", {}).get("search", [])
    out: list[RawResource] = []
    for h in hits:
        title = h["title"]
        page = title.replace(" ", "_")
        summary = _strip(h.get("snippet", ""))
        words = int(h.get("wordcount", 400))
        if host == "en.wikipedia.org":
            try:
                s = get_json(_REST_SUMMARY.format(title=_q(page)))
                summary = s.get("extract", summary)
            except Exception:
                pass
        out.append(
            RawResource(
                source=source,
                kind=kind,
                title=title,
                url=f"https://{host}/wiki/{page}",
                summary=summary,
                minutes=round(min(45.0, 3.0 + words / 180.0), 1),
                metadata={"word_count": words},
            )
        )
    return out


# --------------------------------------------------------------------------- #
def search_mdn(query: str, *, limit: int = 3) -> list[RawResource]:
    url = f"https://developer.mozilla.org/api/v1/search?q={_q(query)}&locale=en-US"
    docs = get_json(url).get("documents", [])[:limit]
    return [
        RawResource(
            source="mdn",
            kind="docs",
            title=d.get("title", ""),
            url="https://developer.mozilla.org" + d.get("mdn_url", ""),
            summary=_strip(d.get("summary", "")),
            minutes=14.0,
            metadata={"popularity": d.get("popularity", 0.0)},
        )
        for d in docs
        if d.get("mdn_url")
    ]


# --------------------------------------------------------------------------- #
def search_mit_learn(query: str, *, limit: int = 3) -> list[RawResource]:
    url = (
        "https://api.learn.mit.edu/api/v1/learning_resources/"
        f"?q={_q(query)}&limit={limit + 4}&resource_type=course,video"
    )
    results = get_json(url).get("results", [])
    out: list[RawResource] = []
    qterms = {t for t in re.findall(r"[a-z]+", query.lower()) if len(t) > 3}
    for r in results:
        title = r.get("title", "")
        desc = _strip(r.get("description", "") or "")
        hay = (title + " " + desc).lower()
        if qterms and not any(t in hay for t in qterms):
            continue  # MIT Learn's text search is loose - keep only on-topic hits
        rtype = r.get("resource_type", "course")
        out.append(
            RawResource(
                source="mit_learn",
                kind="video" if rtype == "video" else "course",
                title=title,
                url=r.get("url") or r.get("learning_path") or "",
                summary=desc,
                minutes=25.0 if rtype == "video" else 40.0,
                metadata={"platform": (r.get("platform") or {})},
            )
        )
        if len(out) >= limit:
            break
    return [r for r in out if r.url]


# --------------------------------------------------------------------------- #
def search_arxiv(query: str, *, limit: int = 2) -> list[RawResource]:
    url = (
        "http://export.arxiv.org/api/query"
        f"?search_query=all:{_q(query)}&start=0&max_results={limit}"
        "&sortBy=relevance"
    )
    feed = ET.fromstring(get(url))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out: list[RawResource] = []
    for e in feed.findall("a:entry", ns):
        title = " ".join((e.findtext("a:title", "", ns) or "").split())
        summ = " ".join((e.findtext("a:summary", "", ns) or "").split())
        link = ""
        for ln in e.findall("a:link", ns):
            if ln.get("type") == "text/html":
                link = ln.get("href", "")
        out.append(
            RawResource(
                source="arxiv",
                kind="paper",
                title=title,
                url=link,
                summary=summ,
                minutes=40.0,
                metadata={"published": e.findtext("a:published", "", ns)},
            )
        )
    return out


# --------------------------------------------------------------------------- #
def search_youtube(query: str, *, limit: int = 3) -> list[RawResource]:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    s = get_json(
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&maxResults={limit}&q={_q(query + ' tutorial')}&key={key}"
    )
    ids = [it["id"]["videoId"] for it in s.get("items", []) if it.get("id", {}).get("videoId")]
    if not ids:
        return []
    v = get_json(
        "https://www.googleapis.com/youtube/v3/videos"
        f"?part=snippet,contentDetails,statistics&id={','.join(ids)}&key={key}"
    )
    out: list[RawResource] = []
    for it in v.get("items", []):
        sn, st = it.get("snippet", {}), it.get("statistics", {})
        secs = _iso8601_seconds(it.get("contentDetails", {}).get("duration", "PT0S"))
        out.append(
            RawResource(
                source="youtube",
                kind="video",
                title=sn.get("title", ""),
                url=f"https://www.youtube.com/watch?v={it['id']}",
                summary=_strip(sn.get("description", ""))[:600],
                minutes=round(max(3.0, secs / 60.0), 1),
                metadata={
                    "channel": sn.get("channelTitle", ""),
                    "views": int(st.get("viewCount", 0) or 0),
                    "likes": int(st.get("likeCount", 0) or 0),
                    "seconds": secs,
                },
            )
        )
    return out


def _iso8601_seconds(d: str) -> float:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0.0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return float(h * 3600 + mi * 60 + s)


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


ALL_SOURCES: tuple[Source, ...] = (
    search_wikipedia,
    search_wikibooks,
    search_mdn,
    search_mit_learn,
    search_arxiv,
    search_youtube,
)

# which sources actually carry good material for a domain
_DOMAIN_SOURCES: dict[str, tuple[Source, ...]] = {
    "math": (search_wikipedia, search_wikibooks, search_mit_learn, search_youtube),
    "science": (search_wikipedia, search_wikibooks, search_mit_learn, search_arxiv, search_youtube),
    "cs": (search_wikipedia, search_wikibooks, search_mit_learn, search_arxiv, search_youtube),
    "web": (search_mdn, search_wikipedia, search_mit_learn, search_youtube),
    "general": ALL_SOURCES,
}


def sources_for_domain(domain: str) -> Sequence[Source]:
    return _DOMAIN_SOURCES.get(domain, ALL_SOURCES)


def search_all(query: str, *, sources: Sequence[Source] = ALL_SOURCES) -> list[RawResource]:
    out: list[RawResource] = []
    for fn in sources:
        out.extend(_safe(fn, query))
    return out
