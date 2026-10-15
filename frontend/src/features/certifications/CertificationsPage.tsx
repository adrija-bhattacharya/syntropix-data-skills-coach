import { useState } from "react";

import { ErrorBox, Loading, Ms, Pill } from "../../components/stitch";
import { useTrack } from "../../context/TrackContext";
import { useCertifications } from "../../lib/queries";
import { NeedGoal } from "../plan/NeedGoal";

const LEVELS = ["entry", "associate", "professional"] as const;
const LEVEL_WORD: Record<string, string> = { entry: "Start here", associate: "Next step", professional: "Stand out" };
const LEVEL_PLAIN: Record<string, string> = { entry: "beginner", associate: "intermediate", professional: "advanced" };

/** Real certificates that match the goal, from free badges to paid exams. */
export function CertificationsPage() {
  const { track } = useTrack();
  const q = useCertifications(track.goal);
  const [freeOnly, setFreeOnly] = useState(false);

  if (!track.goal) return <NeedGoal />;
  if (q.isPending) return <Loading label="Finding certificates…" />;
  if (q.isError) return <ErrorBox>{q.error.message}</ErrorBox>;
  const certs = q.data.certifications.filter((c) => !freeOnly || c.free);

  return (
    <div className="flex flex-col gap-space-lg">
      <header className="flex flex-wrap items-end justify-between gap-space-sm">
        <div className="flex flex-col gap-space-xs">
          <h1 className="font-headline-md text-headline-md">Certifications</h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
            Certificates that match your goal, from free skill badges to industry exams. Start with a free one, then pick one
            exam that employers in your area ask for.
          </p>
        </div>
        <label className="flex items-center gap-space-xs font-body-sm text-body-sm">
          <input type="checkbox" checked={freeOnly} onChange={(e) => setFreeOnly(e.target.checked)} className="w-4 h-4 accent-[#4de082]" />
          Free only
        </label>
      </header>
      {LEVELS.map((lv) => {
        const list = certs.filter((c) => c.level === lv);
        if (!list.length) return null;
        return (
          <section key={lv} className="flex flex-col gap-space-sm">
            <h2 className="font-headline-sm text-headline-sm">{LEVEL_WORD[lv]} <span className="font-body-sm text-body-sm text-outline">({LEVEL_PLAIN[lv]})</span></h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-space-md">
              {list.map((c) => (
                <article key={c.id} className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
                  <div className="flex flex-wrap items-center gap-space-xs">
                    <Pill tone={c.free ? "tertiary" : "neutral"}>{c.free ? "Free" : c.price_note || "Paid"}</Pill>
                    {c.hours ? <Pill tone="neutral" icon="schedule">about {c.hours} h</Pill> : null}
                    <span className="font-label-annotation text-label-annotation text-outline">{c.provider}</span>
                  </div>
                  <h3 className="font-body-strong text-body-md">{c.name}</h3>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">{c.blurb}</p>
                  <a href={c.url} target="_blank" rel="noreferrer" className="mt-auto w-fit px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center gap-1.5">
                    <Ms name="open_in_new" size={16} /> See the official page
                  </a>
                </article>
              ))}
            </div>
          </section>
        );
      })}
      {!certs.length && <ErrorBox>No certificates match this filter.</ErrorBox>}
    </div>
  );
}
