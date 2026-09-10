# harvest — open-resource discovery

Turns a concept into **real, open, level-matched** learning resources, replacing
the hand-authored `curriculum.py` catalogue.

```
sources.py    one adapter per source, each  search_*(query) -> [RawResource]
level.py      RawResource -> difficulty 1-5  (Flesch-Kincaid + jargon + title cues + source priors)
catalogue.py  discover_for_concept / discover_catalogue  -> KnowledgeGraph
http.py       stdlib GET + 14-day on-disk cache  (VELPO_HARVEST_OFFLINE=1 = cache only)
model.py      RawResource
```

## Sources (all keyless except YouTube)

| source | what | key |
|---|---|---|
| Wikipedia | canonical article (redirects followed) + search hits | — |
| Wikibooks | open textbook chapters | — |
| MDN | web-platform reference (web domain) | — |
| MIT Learn | OCW courses + video lectures | — |
| arXiv | papers (science / cs domains) | — |
| YouTube | tutorial videos, ranked by like-ratio | `YOUTUBE_API_KEY` env var; skipped if absent |

`sources_for_domain("math" | "cs" | "web" | "science" | "general")` routes to the
sources that actually carry good material for that domain.

## Level estimation

`estimate_level(raw)` → `LevelEstimate(difficulty, quality, fk_grade, signals)`:

* **readability** — Flesch-Kincaid grade of the summary (pure-Python syllable heuristic)
* **jargon density** — fraction of ≥3-syllable words
* **title cues** — "introduction / basics / 101" ↓, "advanced / internals / graduate" ↑
* **source & kind priors** — an arXiv paper starts harder than a Wikipedia intro

`quality` (source authority, video like-ratio, summary completeness) is used only
to rank candidates, never for difficulty.

## Offline

`harvest/data/algebra_catalogue.json` is a committed real harvest of the algebra
curriculum — tests and `--catalogue discovered` run from it with no network.
`python velpo.py harvest --refresh` re-harvests and rewrites it.
