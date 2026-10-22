"""The shareable proof-of-skill page: one self-contained HTML file (no scripts,
no external assets) built from :func:`portfolio.public_view`.

Served live (``live=True``), it carries a plain form that asks the server to
re-test every answer on new data (claim H2); the downloaded copy shows the last
signed result instead."""

from __future__ import annotations

from html import escape
from typing import Any

SKILL = {
    "sql": "SQL",
    "spreadsheets": "Excel",
    "python": "Python",
    "python_data": "pandas & NumPy",
    "stats": "Statistics",
    "dataviz": "Data visualisation",
    "powerbi": "Power BI",
    "tableau": "Tableau",
    "data_eng": "Data engineering",
    "git": "Git",
}
LANG = {"sql": "SQL", "python": "Python", "excel": "Excel formula", "value": "Answer"}

CSS = """
:root{--bg:#f7f7fb;--card:#fff;--ink:#16161d;--muted:#5b5b6b;--line:#e3e3ec;--accent:#5b3fd6;--ok:#13804a;--okbg:#e5f6ec;--code:#f1f0f7}
@media (prefers-color-scheme:dark){:root{--bg:#0f1016;--card:#181a22;--ink:#e6e6ef;--muted:#a3a1b3;--line:#2a2c36;--accent:#b7a8ff;--ok:#4de082;--okbg:#0f2a1b;--code:#11131a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:920px;margin:0 auto;padding:40px 16px 64px}
header{display:flex;gap:20px;align-items:center;flex-wrap:wrap;margin-bottom:28px}
.mark{width:56px;height:56px;border-radius:14px;background:linear-gradient(135deg,#22d3ee,#a78bfa,#e879f9);display:grid;place-items:center;color:#fff;font-weight:800;font-size:22px}
h1{font-size:30px;margin:0}h2{font-size:20px;margin:36px 0 12px}h3{font-size:16px;margin:0 0 6px}
.muted{color:var(--muted)}a{color:var(--accent)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.stat b{display:block;font-size:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:10px 0}
.badge{display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:600;padding:2px 8px;border-radius:99px;background:var(--okbg);color:var(--ok)}
.badge.warn{background:#fdecec;color:#b42318}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}.tag{font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--muted)}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto;font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;margin:8px 0}
table{border-collapse:collapse;font-size:13px;margin-top:6px}td,th{border:1px solid var(--line);padding:3px 8px;text-align:left}
details summary{cursor:pointer;color:var(--accent);font-size:14px}
footer{margin-top:48px;font-size:13px;color:var(--muted)}
.btn{font:inherit;font-weight:600;padding:8px 14px;border-radius:8px;border:0;background:var(--accent);color:#fff;cursor:pointer}
.proof{font-size:13px;margin-top:6px}code{font:12px ui-monospace,Consolas,monospace;word-break:break-all}
.bar{height:6px;border-radius:6px;background:var(--line);overflow:hidden}.bar i{display:block;height:100%;background:var(--accent)}
"""


def _link(url: str, label: str) -> str:
    return f'<a href="{escape(url, quote=True)}" rel="noopener">{escape(label)}</a>' if url else ""


def _proof(p: dict[str, Any] | None) -> tuple[str, str]:
    """(badge, details) for one answer's latest fresh-data test."""
    if not p:
        return "", ""
    pl = p["payload"]
    when = escape(pl["at"][:16].replace("T", " "))
    if pl["passed"]:
        badge = f"<span class='badge'>✓ passed on {pl['datasets']} new datasets</span>"
    else:
        badge = "<span class='badge warn'>failed on new data</span>"
    detail = (
        f"<div class='proof muted'>Re-tested {when} on database variants "
        f"{', '.join(str(x) for x in pl['seeds'])} (anyone can rebuild them from these numbers). "
        f"Signature <code>{escape(p['sig'][:16])}…</code></div>"
    )
    return badge, detail


def render(view: dict[str, Any], *, base_url: str = "", live: bool = False) -> str:
    name = escape(view["name"])
    links = " · ".join(
        x for x in (_link(view["github"], "GitHub"), _link(view["linkedin"], "LinkedIn")) if x
    )
    initials = "".join(w[0] for w in view["name"].split()[:2]).upper() or "S"
    skills = view["skills"]
    out = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{name} · Proof of skill</title><style>{CSS}</style></head><body><main>",
        f"<header><div class='mark'>{escape(initials)}</div><div><h1>{name}</h1>",
        f"<div class='muted'>{escape(view['headline'])}</div><div>{links}</div></div></header>",
        "<p>Every answer below was <b>run and checked automatically</b> by Syntropix when it was solved, "
        "and <b>re-run when this page was built</b>. The badge shows the result of that re-check.</p>",
        "<div class='stats'>",
        f"<div class='stat'><b>{view['solved']}</b><span class='muted'>problems solved</span></div>",
        f"<div class='stat'><b>{view['rechecked_ok']}/{view['solved']}</b><span class='muted'>pass when re-run today</span></div>",
        f"<div class='stat'><b>{view.get('fresh_ok', 0)}/{view.get('fresh_testable', 0)}</b><span class='muted'>pass on new data</span></div>",
        f"<div class='stat'><b>{len(skills)}</b><span class='muted'>skills</span></div>",
        f"<div class='stat'><b>{len(view['projects'])}</b><span class='muted'>projects</span></div>",
        "</div>",
    ]
    if view.get("fresh_testable"):
        out.append(
            "<div class='card' id='proof'><h3>Re-test on data it has never seen</h3>"
            "<p class='muted' style='margin:4px 0 10px'>SQL and pandas answers can be run on a newly generated "
            "version of the practice database: more rows, new values, new edge cases. An answer that was memorised "
            "or only worked on the practice rows fails there.</p>"
        )
        if live:
            out.append(
                f"<form method='post' action='/p/{escape(view['slug'], quote=True)}/retest'>"
                "<button class='btn' type='submit'>Re-test now on new data</button></form>"
            )
        out.append("</div>")
    if view["projects"]:
        out.append("<h2>Projects</h2>")
        for p in view["projects"]:
            tags = "".join(
                f"<span class='tag'>{escape(SKILL.get(s, s))}</span>" for s in p["skills"]
            )
            ok = (
                "<span class='badge'>✓ link working</span>"
                if p.get("link_ok")
                else "<span class='badge warn'>link not reachable when added</span>"
                if p.get("link_ok") is False
                else ""
            )
            out.append(
                f"<div class='card'><h3>{escape(p['title'])} {ok}</h3><div class='tags'>{tags}</div>"
                f"<p>{escape(p['summary'])}</p>"
                f"<div>{' · '.join(x for x in (_link(p['repo_url'], 'Code'), _link(p['demo_url'], 'Live demo')) if x)}</div></div>"
            )
    if skills:
        out.append("<h2>Solved and verified</h2>")
    for domain, solves in sorted(skills.items(), key=lambda kv: -len(kv[1])):
        out.append(
            f"<h2 style='font-size:17px'>{escape(SKILL.get(domain, domain))} <span class='muted'>· {len(solves)}</span></h2>"
        )
        for s in solves:
            badge = (
                "<span class='badge'>✓ passes when re-run</span>"
                if s["rechecked"]
                else "<span class='badge warn'>no longer passes</span>"
            )
            fresh_badge, fresh_detail = _proof(s.get("proof"))
            badge += " " + fresh_badge
            checks = ", ".join(escape(c) for c in s["checks"])
            table = ""
            if s["columns"] and s["result_preview"] and s["kind"] in ("sql", "python"):
                head = "".join(f"<th>{escape(str(c))}</th>" for c in s["columns"])
                rows = "".join(
                    "<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in r) + "</tr>"
                    for r in s["result_preview"]
                )
                table = f"<table><tr>{head}</tr>{rows}</table>"
            out.append(
                f"<div class='card'><h3>{escape(s['concept_name'])} {badge}</h3>"
                f"<div class='muted'>{escape(s['prompt'])}</div>"
                f"<pre>{escape(s['answer'])}</pre>{fresh_detail}"
                f"<details><summary>{escape(LANG.get(s['kind'], s['kind']))} · checks passed: {checks or '—'} · "
                f"solved {escape(s['solved_at'][:10])}</summary>{table}</details></div>"
            )
    if view["mastery"]:
        top = sorted(view["mastery"].items(), key=lambda kv: -kv[1])[:12]
        out.append("<h2>Strongest topics</h2>")
        for k, v in top:
            out.append(
                f"<div style='margin:6px 0'><div style='display:flex;justify-content:space-between'><span>{escape(k)}</span>"
                f"<span class='muted'>{round(v * 100)}%</span></div><div class='bar'><i style='width:{round(v * 100)}%'></i></div></div>"
            )
    where = f" · {_link(base_url, base_url)}" if base_url else ""
    out.append(
        f"<footer>Built {escape(view['built'])} with Syntropix{where}. Answers are graded by running them "
        "(SQL in a read-only database, Python in a sandbox, Excel formulas in an evaluator), not by AI judgement.</footer>"
    )
    out.append("</main></body></html>")
    return "".join(out)
