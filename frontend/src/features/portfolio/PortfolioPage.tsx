import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ErrorBox, Loading, Ms, Pill } from "../../components/stitch";
import { useLearner } from "../../context/LearnerContext";
import { api, type PortfolioView, type ProfileInput, type ProjectInput } from "../../lib/api";
import { SKILL_NAME } from "../../lib/library";
import { PROJECTS } from "../projects/ProjectsPage";

/** Proof of skill: what you solved (re-checked by running it again), your
 * projects, and a page you can hand to recruiters. */
export function PortfolioPage() {
  const { learnerId } = useLearner();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["portfolio", learnerId], queryFn: () => api.portfolio(learnerId) });
  const set = (data: PortfolioView) => qc.setQueryData(["portfolio", learnerId], data);

  if (q.isPending) return <Loading label="Re-checking your solved problems…" />;
  if (q.isError)
    return (
      <ErrorBox>
        {q.error.message.includes("protected")
          ? "This portfolio belongs to another browser: its private key is kept where it was first opened. Open Syntropix there, or switch to your own name (top-right)."
          : q.error.message}
      </ErrorBox>
    );
  const v = q.data;
  const shareUrl = `${window.location.origin}${v.share_path}`;

  return (
    <div className="flex flex-col gap-space-lg">
      <header className="flex flex-wrap items-end justify-between gap-space-sm">
        <div className="flex flex-col gap-space-xs max-w-3xl">
          <h1 className="font-headline-md text-headline-md">Your portfolio</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Every practice problem you solve here is saved with your answer. When someone opens your page, each answer is
            <b> run again</b> and marked as passing, so recruiters see real, working proof rather than a badge.
          </p>
        </div>
        <div className="flex flex-wrap gap-space-xs">
          <a href={api.portfolioExportUrl(learnerId)} className="px-space-md py-2 rounded-lg bg-surface-container-high hover:bg-surface-container-highest font-body-strong text-body-sm flex items-center gap-1.5">
            <Ms name="download" size={16} /> Download as a web page
          </a>
          {v.public && (
            <a href={v.share_path} target="_blank" rel="noreferrer" className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center gap-1.5">
              <Ms name="open_in_new" size={16} /> Open my public page
            </a>
          )}
        </div>
      </header>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-space-sm">
        <Stat icon="task_alt" label="Problems solved" value={String(v.solved)} />
        <Stat icon="verified" label="Still pass when re-run" value={`${v.rechecked_ok} / ${v.solved}`} />
        <Stat icon="school" label="Skills shown" value={String(Object.keys(v.skills).length)} />
        <Stat icon="folder_special" label="Projects" value={String(v.projects.length)} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-space-lg items-start">
        <Profile v={v} learnerId={learnerId} onSaved={set} shareUrl={shareUrl} />
        <Projects v={v} learnerId={learnerId} onSaved={set} />
      </div>

      <section className="flex flex-col gap-space-sm">
        <h2 className="font-headline-sm text-headline-sm">Solved and verified</h2>
        {v.solved === 0 ? (
          <div className="p-space-lg rounded-xl bg-surface-container-low flex flex-wrap items-center justify-between gap-space-sm">
            <span className="font-body-sm text-body-sm text-on-surface-variant">Nothing yet. Solve a problem in Practice and it appears here automatically.</span>
            <Link to="/practice" className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm">Go to Practice</Link>
          </div>
        ) : (
          Object.entries(v.skills).map(([domain, solves]) => (
            <details key={domain} open className="p-space-md rounded-xl bg-surface-container-low">
              <summary className="cursor-pointer font-body-strong text-body-md">
                {SKILL_NAME[domain] ?? domain} <span className="text-outline font-body-sm text-body-sm">· {solves.length}</span>
              </summary>
              <div className="flex flex-col gap-space-sm pt-space-sm">
                {solves.map((s) => (
                  <article key={s.task_id} className="p-space-md rounded-lg bg-surface-container flex flex-col gap-1">
                    <div className="flex flex-wrap items-center justify-between gap-space-xs">
                      <span className="font-body-strong text-body-sm">{s.concept_name}</span>
                      <span className="flex items-center gap-space-xs">
                        <Pill tone={s.rechecked ? "tertiary" : "error"} icon={s.rechecked ? "verified" : "error"}>
                          {s.rechecked ? "Passes when re-run" : "No longer passes"}
                        </Pill>
                        <RemoveButton label={`Remove ${s.concept_name} from portfolio`} onClick={() => api.portfolioRemove(learnerId, "solves", s.task_id).then(set)} />
                      </span>
                    </div>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">{s.prompt}</span>
                    <pre className="p-space-sm rounded bg-surface-container-lowest font-code-sm text-code-sm overflow-x-auto whitespace-pre-wrap">{s.answer}</pre>
                    <span className="font-label-annotation text-label-annotation text-outline">
                      {s.checks.join(" · ") || "checked"} · solved {s.solved_at.slice(0, 10)} · {s.attempts} attempt{s.attempts === 1 ? "" : "s"}
                    </span>
                  </article>
                ))}
              </div>
            </details>
          ))
        )}
      </section>
    </div>
  );
}

function Profile({ v, learnerId, onSaved, shareUrl }: { v: PortfolioView; learnerId: string; onSaved: (d: PortfolioView) => void; shareUrl: string }) {
  const [form, setForm] = useState<ProfileInput>({ name: v.name === "A Syntropix learner" ? "" : v.name, headline: v.headline, github: v.github, linkedin: v.linkedin, public: v.public });
  const [copied, setCopied] = useState(false);
  const save = useMutation({ mutationFn: (f: ProfileInput) => api.portfolioProfile(learnerId, f), onSuccess: onSaved });
  const field = (k: keyof ProfileInput, label: string, placeholder: string) => (
    <label className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
      {label}
      <input
        value={form[k] as string}
        onChange={(e) => setForm({ ...form, [k]: e.target.value })}
        placeholder={placeholder}
        className="px-space-sm py-1.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm text-on-surface normal-case"
      />
    </label>
  );
  return (
    <section className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
      <h2 className="font-headline-sm text-headline-sm">Your public page</h2>
      <form
        className="flex flex-col gap-space-sm"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate(form);
        }}
      >
        {field("name", "Name", "e.g. Priya Sharma")}
        {field("headline", "Headline", "e.g. Aspiring data analyst · SQL, Excel, Power BI")}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
          {field("github", "GitHub link", "https://github.com/…")}
          {field("linkedin", "LinkedIn link", "https://www.linkedin.com/in/…")}
        </div>
        <label className="flex items-start gap-space-sm font-body-sm text-body-sm">
          <input type="checkbox" checked={form.public} onChange={(e) => setForm({ ...form, public: e.target.checked })} className="mt-1 w-4 h-4 accent-[#4de082]" />
          <span>
            <b>Make my page public</b>
            <span className="block text-on-surface-variant">Anyone with the link can see your name, links, solved problems (with your answers) and projects. Off by default.</span>
          </span>
        </label>
        <div className="flex flex-wrap items-center gap-space-sm">
          <button type="submit" disabled={save.isPending} className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm disabled:opacity-50">
            {save.isPending ? "Saving…" : "Save"}
          </button>
          {save.isSuccess && <span className="font-label-annotation text-label-annotation text-tertiary">Saved</span>}
        </div>
        {save.isError && <ErrorBox>{save.error.message}</ErrorBox>}
      </form>
      {v.public && (
        <div className="flex items-center gap-space-xs p-space-sm rounded-lg bg-surface-container">
          <code className="flex-1 truncate font-code-sm text-code-sm">{shareUrl}</code>
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard?.writeText(shareUrl).then(() => setCopied(true));
            }}
            className="px-space-sm py-1 rounded bg-surface-container-high hover:bg-surface-container-highest font-label-badge text-label-badge"
          >
            {copied ? "Copied" : "Copy link"}
          </button>
        </div>
      )}
      <p className="font-label-annotation text-label-annotation text-outline">
        The link works while this Syntropix server is reachable. To share it anywhere, download the page and host it, e.g. on GitHub Pages (see the Projects page).
      </p>
    </section>
  );
}

function Projects({ v, learnerId, onSaved }: { v: PortfolioView; learnerId: string; onSaved: (d: PortfolioView) => void }) {
  const [params, setParams] = useSearchParams();
  const fromProjects = PROJECTS.find((p) => p.id === params.get("project"));
  const blank: ProjectInput = { project_id: "", title: "", summary: "", skills: [], repo_url: "", demo_url: "" };
  const [form, setForm] = useState<ProjectInput>(blank);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (fromProjects) {
      setForm({ ...blank, project_id: fromProjects.id, title: fromProjects.title, skills: fromProjects.skills });
      setOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromProjects?.id]);
  const save = useMutation({
    mutationFn: (f: ProjectInput) => api.portfolioProject(learnerId, { ...f, project_id: f.project_id || `own-${Date.now()}` }),
    onSuccess: (d) => {
      onSaved(d);
      setForm(blank);
      setOpen(false);
      setParams({});
    },
  });
  return (
    <section className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-headline-sm text-headline-sm">Projects</h2>
        {!open && (
          <button type="button" onClick={() => setOpen(true)} className="px-space-md py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest font-body-sm text-body-sm flex items-center gap-1">
            <Ms name="add" size={16} /> Add a project
          </button>
        )}
      </div>
      {open && (
        <form
          className="flex flex-col gap-space-sm p-space-md rounded-lg bg-surface-container"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate(form);
          }}
        >
          {(
            [
              ["title", "Project name", "e.g. Music store questions with SQL"],
              ["repo_url", "Link to your code", "https://github.com/you/project"],
              ["demo_url", "Link to a live demo (optional)", "https://public.tableau.com/…"],
            ] as const
          ).map(([k, label, ph]) => (
            <label key={k} className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
              {label}
              <input required={k === "title"} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} placeholder={ph} className="px-space-sm py-1.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm text-on-surface normal-case" />
            </label>
          ))}
          <label className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
            What you did and found (2–3 sentences)
            <textarea rows={3} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} className="px-space-sm py-1.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm text-on-surface normal-case" />
          </label>
          <div className="flex flex-wrap gap-1">
            {Object.entries(SKILL_NAME).map(([k, label]) => (
              <button
                key={k}
                type="button"
                aria-pressed={form.skills.includes(k)}
                onClick={() => setForm({ ...form, skills: form.skills.includes(k) ? form.skills.filter((x) => x !== k) : [...form.skills, k] })}
                className={`px-space-sm py-0.5 rounded-full font-label-badge text-label-badge ${form.skills.includes(k) ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex gap-space-xs">
            <button type="submit" disabled={save.isPending} className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm disabled:opacity-50">
              {save.isPending ? "Checking the link…" : "Add to portfolio"}
            </button>
            <button type="button" onClick={() => { setOpen(false); setParams({}); }} className="px-space-md py-2 rounded-lg bg-surface-container-high font-body-sm text-body-sm">
              Cancel
            </button>
          </div>
          {save.isError && <ErrorBox>{save.error.message}</ErrorBox>}
        </form>
      )}
      {v.projects.length === 0 && !open && (
        <span className="font-body-sm text-body-sm text-on-surface-variant">
          Finished one of the <Link to="/projects" className="underline hover:text-primary">projects</Link>? Add it with a link to your code.
        </span>
      )}
      {v.projects.map((p) => (
        <article key={p.project_id} className="p-space-md rounded-lg bg-surface-container flex flex-col gap-1">
          <div className="flex items-center justify-between gap-space-xs">
            <span className="font-body-strong text-body-sm">{p.title}</span>
            <span className="flex items-center gap-space-xs">
              {p.link_ok === true && <Pill tone="tertiary" icon="link">link working</Pill>}
              {p.link_ok === false && <Pill tone="error" icon="link_off">link didn't open</Pill>}
              <RemoveButton label={`Remove ${p.title}`} onClick={() => api.portfolioRemove(learnerId, "projects", p.project_id).then(onSaved)} />
            </span>
          </div>
          {p.summary && <p className="font-body-sm text-body-sm text-on-surface-variant">{p.summary}</p>}
          <div className="flex flex-wrap gap-space-sm font-body-sm text-body-sm">
            {p.repo_url && <a href={p.repo_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">Code</a>}
            {p.demo_url && <a href={p.demo_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">Live demo</a>}
            {p.skills.map((s) => <Pill key={s} tone="neutral">{SKILL_NAME[s] ?? s}</Pill>)}
          </div>
        </article>
      ))}
    </section>
  );
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} className="p-1 rounded hover:bg-surface-container-highest text-outline hover:text-error">
      <Ms name="delete" size={16} />
    </button>
  );
}

function Stat({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-1">
      <span className="font-label-annotation text-label-annotation text-outline uppercase flex items-center gap-1"><Ms name={icon} size={14} /> {label}</span>
      <span className="font-headline-sm text-headline-sm">{value}</span>
    </div>
  );
}
