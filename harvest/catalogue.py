"""Assemble a :class:`KnowledgeGraph` whose resources are *discovered* open
material, level-estimated, keeping a seed graph's concepts + prerequisite edges.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from harvest.level import LevelEstimate, estimate_level
from harvest.model import RawResource
from harvest.sources import search_all, sources_for_domain
from model.knowledge_graph import Concept, KnowledgeGraph, Resource

_DATA = Path(__file__).resolve().parent / "data"
Scored = tuple[RawResource, LevelEstimate]

_STOP = {
    "and",
    "or",
    "the",
    "of",
    "to",
    "in",
    "a",
    "an",
    "for",
    "with",
    "on",
    "notation",
    "using",
    "into",
    "intro",
    "introduction",
    "basic",
    "basics",
    "problems",
    "modelling",
}

# curated search grounding for the seed algebra curriculum - the concept *label*
# is not always an article title.  (Phase 3 builds this dynamically for new goals.)
CONCEPT_QUERY: dict[str, str] = {
    "integers": "Integer",
    "fractions": "Fraction",
    "decimals": "Decimal",
    "exponents": "Exponentiation",
    "roots": "Nth root",
    "order_ops": "Order of operations",
    "expressions": "Algebraic expression",
    "linear_eq": "Linear equation",
    "inequalities": "Inequality (mathematics)",
    "systems": "System of linear equations",
    "quadratics": "Quadratic equation",
    "functions": "Function (mathematics)",
    "graphing": "Graph of a function",
    "word_problems": "Word problem (mathematics education)",
}


def _stem(w: str) -> str:
    if w.endswith("ies") and len(w) > 5:
        return w[:-3] + "y"
    for suf in ("es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _terms(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in _STOP}


# titles that clearly belong to another domain than the one we asked for
_OFF_DOMAIN = {
    "math": {
        "javascript",
        "python",
        "php",
        "java",
        "css",
        "html",
        "sql",
        "programming",
        "circuit",
        "compiler",
        "software",
        "api",
        "typescript",
        "rust",
        "regex",
        "sharp",
        "keyword",
        "dewey",
        "sexuality",
        "gender",
        "ada",
        "library",
        "libraries",
        "chemistry",
        "biology",
        "fractionation",
        "distillation",
        "architecture",
        "leadership",
    },
    "web": {"biology", "chemistry", "geology", "anatomy"},
}
_MATH_SHELVES = (
    "math",
    "algebra",
    "calculus",
    "arithmetic",
    "geometry",
    "trigonometry",
    "number",
    "statistics",
    "a-level",
    "linear",
    "sat ",
    "gcse",
)


def _off_domain(domain: str, r: RawResource) -> bool:
    bad = _OFF_DOMAIN.get(domain, set())
    if bad and (bad & _terms(r.title) or len(bad & _terms(r.summary)) >= 2):
        return True
    if domain == "math" and r.source == "wikibooks":
        shelf = r.title.split("/", 1)[0].lower()
        return not any(s in shelf for s in _MATH_SHELVES)
    return False


def _relevance(concept_name: str, r: RawResource) -> float:
    if r.metadata.get("canonical"):
        return 6.0
    want = _terms(concept_name)
    if not want:
        return 1.0
    primary = _stem(re.findall(r"[a-z]+", concept_name.lower())[0])
    title_t, summ_t = _terms(r.title), _terms(r.summary)
    if primary not in title_t and primary not in summ_t:
        return 0.0  # the concept's head word must appear somewhere
    title_hits = len(want & title_t)
    summ_hits = len(want & summ_t)
    return 3.0 * title_hits + min(summ_hits, len(want))


# --------------------------------------------------------------------------- #
def _clean_concept(name: str) -> str:
    """A curriculum label -> a searchable phrase: 'Functions & notation' -> 'Functions'."""
    head = re.split(r"[&(/,]", name)[0].strip()
    return head or name


def discover_for_concept(
    concept_name: str, *, domain: str = "general", k: int = 6, extra_query: str = ""
) -> list[Scored]:
    query = f"{_clean_concept(concept_name)} {extra_query}".strip()
    raws = search_all(query, sources=sources_for_domain(domain))

    seen: set[str] = set()
    scored: list[tuple[float, Scored]] = []
    for r in raws:
        key = r.key()
        if not r.title or not r.url or key in seen:
            continue
        seen.add(key)
        if not r.metadata.get("canonical") and _off_domain(domain, r):
            continue
        rel = _relevance(concept_name, r)
        if rel < 1.0:  # off-topic keyword collision - drop it
            continue
        lvl = estimate_level(r)
        rank = 0.55 * min(rel, 6.0) / 6.0 + 0.45 * lvl.quality
        scored.append((rank, (r, lvl)))

    scored.sort(key=lambda s: -s[0])
    return _diverse_top([pair for _, pair in scored], k)


def _diverse_top(scored: list[Scored], k: int) -> list[Scored]:
    """Keep the best k, but don't return six items of identical difficulty or all
    from one source - the sequencing DP needs a genuine easy/medium/hard choice."""
    out: list[Scored] = []
    per_source: dict[str, int] = {}
    for r, lvl in scored:
        if len(out) >= k:
            break
        if per_source.get(r.source, 0) >= 3:
            continue
        if sum(1 for _, l2 in out if abs(l2.difficulty - lvl.difficulty) < 0.4) >= 3:
            continue
        out.append((r, lvl))
        per_source[r.source] = per_source.get(r.source, 0) + 1
    for pair in scored:  # top up if the diversity filter left us short
        if len(out) >= k:
            break
        if pair not in out:
            out.append(pair)
    return out


# --------------------------------------------------------------------------- #
def discover_catalogue(
    seed: KnowledgeGraph,
    *,
    snapshot: str | None = "algebra",
    per_concept: int = 6,
    domain: str = "math",
    refresh: bool = False,
) -> KnowledgeGraph:
    """A KnowledgeGraph with the seed's concepts + prereq edges but *discovered*
    resources.  Uses the committed snapshot when present and ``refresh`` is off."""
    snap_path = _DATA / f"{snapshot}_catalogue.json" if snapshot else None
    if snap_path and snap_path.exists() and not refresh:
        per_concept_raw = json.loads(snap_path.read_text())["concepts"]
    else:
        per_concept_raw = _harvest_all(seed, per_concept, domain)
        if snap_path is not None:
            snap_path.parent.mkdir(exist_ok=True)
            snap_path.write_text(
                json.dumps({"domain": domain, "concepts": per_concept_raw}, indent=1)
            )

    resources: list[Resource] = []
    for cid, items in per_concept_raw.items():
        for n, it in enumerate(items):
            resources.append(
                Resource(
                    id=f"{cid}::{it['source']}:{n}",
                    concepts=(cid,),
                    difficulty=float(it["difficulty"]),
                    minutes=float(it["minutes"]),
                    kind=it["kind"],
                    title=it["title"],
                    url=it["url"],
                    source=it["source"],
                )
            )
        if not items:  # offline with nothing cached -> keep the graph solvable
            resources.append(Resource(f"{cid}::fallback:0", (cid,), 2.0, 12.0, "lesson"))

    concepts = [Concept(c, seed.concepts[c].name) for c in seed.concept_ids]
    edges = list(seed.prereq.edges())
    return KnowledgeGraph.build(concepts, edges, resources)


def _harvest_all(
    seed: KnowledgeGraph, per_concept: int, domain: str
) -> dict[str, list[dict[str, object]]]:
    out: dict[str, list[dict[str, object]]] = {}
    for cid in seed.concept_ids:
        out[cid] = _harvest_one(seed, cid, per_concept, domain)
    # a second, unhurried pass for anything a transient failure left empty
    for cid in [c for c, v in out.items() if not v]:
        out[cid] = _harvest_one(seed, cid, per_concept, domain)
    return out


def _harvest_one(
    seed: KnowledgeGraph, cid: str, per_concept: int, domain: str
) -> list[dict[str, object]]:
    name = CONCEPT_QUERY.get(cid, seed.concepts[cid].name)
    scored = discover_for_concept(name, domain=domain, k=per_concept)
    return [
        {
            "source": r.source,
            "kind": r.kind,
            "title": r.title,
            "url": r.url,
            "minutes": r.minutes,
            "difficulty": lvl.difficulty,
            "quality": lvl.quality,
            "fk_grade": lvl.fk_grade,
            "summary": r.summary[:280],
        }
        for r, lvl in scored
    ]


def raw_to_dict(r: RawResource, lvl: LevelEstimate) -> dict[str, object]:
    return {**asdict(r), "level": asdict(lvl)}


def algebra_catalogue(*, refresh: bool = False) -> KnowledgeGraph:
    """The algebra seed graph with *discovered* open resources (bundled snapshot)."""
    from curriculum import build_curriculum

    return discover_catalogue(
        build_curriculum(), snapshot="algebra", domain="math", refresh=refresh
    )
