import { useState } from "react";

import { Ms, Pill } from "../../components/stitch";
import type { FixClip as Clip } from "../../lib/api";
import { clock, embed } from "../../lib/library";

/** Claim H1: a wrong answer opens the exact stretch of a checked video that
 * explains its mistake - not the whole lesson for the task's topic. */
export function FixClip({ clip }: { clip: Clip }) {
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const m = clip.moments[i];
  if (!m) return null;
  const minutes = Math.max(1, Math.round((m.end - m.start) / 60));
  return (
    <section aria-label="Watch the fix" className="flex flex-col gap-space-sm p-space-md rounded-xl bg-primary-container/10 border border-primary/30">
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <span className="flex items-center gap-space-xs font-body-strong text-body-sm">
          <Ms name="smart_display" className="text-primary" /> Watch the fix: {clip.concept}
        </span>
        <Pill tone="neutral" icon="schedule">about {minutes} min</Pill>
      </div>
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        {m.kind === "chapter" ? (
          <>
            The part of <b className="text-on-surface">{m.title}</b> that explains this mistake: chapter <b className="text-on-surface">“{m.chapter}”</b>,{" "}
            {clock(m.start)}–{clock(m.end)}.
          </>
        ) : (
          <>
            No chapter matches this exact mistake yet, so here is a checked lesson on {clip.concept}: <b className="text-on-surface">{m.title}</b>
            {m.start > 0 ? `, from ${clock(m.start)}` : ""}.
          </>
        )}
      </p>
      {playing ? (
        <div className="aspect-video w-full max-w-2xl rounded-lg overflow-hidden bg-black">
          <iframe
            title={`Fix clip ${m.video_id}`}
            src={`${embed(m.video_id, m.start, m.end)}&autoplay=1`}
            className="w-full h-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setPlaying(true)}
          className="self-start px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center gap-1.5"
        >
          <Ms name="play_arrow" size={18} /> Play {clock(m.start)}–{clock(m.end)}
        </button>
      )}
      {clip.moments.length > 1 && (
        <button
          type="button"
          onClick={() => {
            setI((i + 1) % clip.moments.length);
            setPlaying(false);
          }}
          className="self-start font-label-annotation text-label-annotation text-outline underline hover:text-on-surface"
        >
          Try another explanation ({m.channel ? `this one is by ${m.channel}` : "different video"})
        </button>
      )}
    </section>
  );
}
