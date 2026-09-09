import { useEffect, useMemo, useState } from "react";
import { api, type Catalogue, type Path } from "./api";
import { ChipSelect } from "./components/ChipSelect";
import { ParetoPlot } from "./components/ParetoPlot";
import { PathCard } from "./components/PathCard";

type Tab = "learner" | "teacher";

export function App() {
  const [cat, setCat] = useState<Catalogue | null>(null);
  const [tab, setTab] = useState<Tab>("learner");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.catalogue().then(setCat).catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="app">
      <header>
        <h1>VELPO</h1>
        <span className="sub">Personalised Learning-Path Optimiser</span>
        <nav>
          <button className={tab === "learner" ? "on" : ""} onClick={() => setTab("learner")}>
            Learner
          </button>
          <button className={tab === "teacher" ? "on" : ""} onClick={() => setTab("teacher")}>
            Teacher console
          </button>
        </nav>
      </header>

      {err && <div className="card warn">Cannot reach the API: {err}</div>}
      {!cat && !err && <div className="empty">Loading curriculum&hellip;</div>}
      {cat && tab === "learner" && <Learner cat={cat} />}
      {cat && tab === "teacher" && <Teacher cat={cat} />}

      <footer>
        Every path is prerequisite-valid and budget-bounded <em>by construction</em>; the
        optimal solver is provably globally optimal in <code>O(V&middot;R&middot;B)</code>.
      </footer>
    </div>
  );
}

// --------------------------------------------------------------------- Learner
function Learner({ cat }: { cat: Catalogue }) {
  const conceptOpts = useMemo(
    () => cat.concepts.map((c) => ({ value: c.id, label: c.name })),
    [cat],
  );
  const [learnerId, setLearnerId] = useState("demo");
  const [goals, setGoals] = useState<string[]>(cat.goals.slice(0, 1));
  const [budget, setBudget] = useState(120);
  const [mode, setMode] = useState<"optimal" | "interactive">("optimal");
  const [path, setPath] = useState<Path | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [res, setRes] = useState(cat.resources[0]?.id ?? "");
  const [ok, setOk] = useState(true);
  const [mins, setMins] = useState(8);
  const [obs, setObs] = useState<string | null>(null);

  const recommend = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.recommend({
        learner_id: learnerId || "demo",
        goals,
        time_budget_min: budget,
        mode,
      });
      setPath(r.paths[0] ?? null);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    setObs(null);
    try {
      const s = await api.observe({
        learner_id: learnerId || "demo",
        resource_id: res,
        correct: ok,
        minutes: mins,
      });
      setObs(`Recorded - ${s.n_interactions} interaction(s), mean velocity ${s.mean_velocity}.`);
    } catch (e) {
      setObs(String(e));
    }
  };

  return (
    <div className="grid">
      <section className="panel">
        <h2>Get a path</h2>
        <div className="field">
          <label>Learner id</label>
          <input value={learnerId} onChange={(e) => setLearnerId(e.target.value)} />
        </div>
        <ChipSelect label="Goal concepts" options={conceptOpts} selected={goals} onChange={setGoals} />
        <div className="field">
          <label>Time budget: {budget} min</label>
          <input
            type="range"
            min={20}
            max={300}
            step={5}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label>Solver</label>
          <select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
            <option value="optimal">optimal (dynamic programming)</option>
            <option value="interactive">interactive (A* anytime)</option>
          </select>
        </div>
        <button className="primary" onClick={recommend} disabled={busy || goals.length === 0}>
          {busy ? "solving…" : "Recommend"}
        </button>
        {err && <div className="card warn">{err}</div>}

        <h2 style={{ marginTop: 28 }}>Log an attempt</h2>
        <div className="field">
          <label>Resource</label>
          <select value={res} onChange={(e) => setRes(e.target.value)}>
            {cat.resources.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id}
              </option>
            ))}
          </select>
        </div>
        <label className="inline">
          <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} /> answered
          correctly
        </label>
        <div className="field">
          <label>Minutes: {mins}</label>
          <input
            type="range"
            min={1}
            max={30}
            value={mins}
            onChange={(e) => setMins(Number(e.target.value))}
          />
        </div>
        <button onClick={submit}>Submit attempt</button>
        {obs && <div className="note">{obs}</div>}
      </section>

      <section className="panel">
        <h2>Plan</h2>
        {path ? (
          <PathCard path={path} catalogue={cat} />
        ) : (
          <div className="empty">Pick goal concepts and press Recommend.</div>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------- Teacher
function Teacher({ cat }: { cat: Catalogue }) {
  const conceptOpts = cat.concepts.map((c) => ({ value: c.id, label: c.name }));
  const resourceOpts = cat.resources.map((r) => ({ value: r.id, label: r.id }));
  const [goals, setGoals] = useState<string[]>(cat.goals.slice(0, 1));
  const [budget, setBudget] = useState(150);
  const [ban, setBan] = useState<string[]>([]);
  const [lock, setLock] = useState<string[]>([]);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [paths, setPaths] = useState<Path[]>([]);
  const [sel, setSel] = useState(0);
  const [meta, setMeta] = useState<Record<string, string | number>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const solve = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.recommend({
        learner_id: "teacher",
        goals,
        time_budget_min: budget,
        mode: "pareto",
        n_paths: 12,
        ban,
        lock,
        force_order: a && b ? [[a, b]] : [],
      });
      setPaths(r.paths);
      setMeta(r.meta);
      setSel(0);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid">
      <section className="panel">
        <h2>Constraints</h2>
        <ChipSelect label="Goal concepts" options={conceptOpts} selected={goals} onChange={setGoals} />
        <div className="field">
          <label>Time budget: {budget} min</label>
          <input
            type="range"
            min={20}
            max={360}
            step={5}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
          />
        </div>
        <ChipSelect label="Ban resources" options={resourceOpts} selected={ban} onChange={setBan} />
        <ChipSelect label="Lock resources" options={resourceOpts} selected={lock} onChange={setLock} />
        <div className="field">
          <label>Force order (A before B)</label>
          <div className="row">
            <select value={a} onChange={(e) => setA(e.target.value)}>
              <option value="">&mdash;</option>
              {conceptOpts.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <span>before</span>
            <select value={b} onChange={(e) => setB(e.target.value)}>
              <option value="">&mdash;</option>
              {conceptOpts.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button className="primary" onClick={solve} disabled={busy || goals.length === 0}>
          {busy ? "re-solving…" : "Re-solve under constraints"}
        </button>
        {err && <div className="card warn">{err}</div>}
        {Object.keys(meta).length > 0 && (
          <div className="note">
            {Object.entries(meta).map(([k, v]) => (
              <div key={k}>
                {k}: {String(v)}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Pareto front {paths.length > 0 && `(${paths.length} non-dominated)`}</h2>
        {paths.length > 0 ? (
          <>
            <ParetoPlot paths={paths} selected={sel} onSelect={setSel} />
            <p className="hint">Click a point to inspect that path.</p>
            <PathCard path={paths[sel]} catalogue={cat} />
          </>
        ) : (
          <div className="empty">Set constraints and re-solve to see the trade-off front.</div>
        )}
      </section>
    </div>
  );
}
