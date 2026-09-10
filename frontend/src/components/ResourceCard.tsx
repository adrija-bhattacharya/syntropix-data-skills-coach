import { useState } from "react";

import type { Step } from "../lib/api";
import { useExplain } from "../lib/queries";
import { Badge } from "./ui";

const KIND_ICON: Record<string, string> = {
  article: "\u{1F4C4}",
  book: "\u{1F4D8}",
  video: "▶",
  course: "\u{1F393}",
  paper: "\u{1F9EA}",
  docs: "\u{1F4DA}",
  lesson: "•",
  practice: "✎",
};

export function ResourceCard({ step, learnerId }: { step: Step; learnerId: string }) {
  const explain = useExplain();
  const [open, setOpen] = useState(false);
  const ring = Math.round((Math.min(step.difficulty, 5) / 5) * 100);

  return (
    <div className={step.review ? "rescard review" : "rescard"}>
      <div className="ring" style={{ ["--p" as string]: ring }} title={`difficulty ${step.difficulty}/5`}>
        <span>{step.difficulty ? step.difficulty.toFixed(1) : "•"}</span>
      </div>
      <div className="body">
        <div className="t">
          {step.url ? (
            <a href={step.url} target="_blank" rel="noreferrer">
              {step.title || step.resource_id} ↗
            </a>
          ) : (
            step.title || step.resource_id
          )}
        </div>
        <div className="meta">
          {step.source && (
            <span className="badge src" data-s={step.source}>
              {KIND_ICON[step.kind] ?? "•"} {step.source.replace("_", " ")}
            </span>
          )}
          {step.review && <Badge tone="good">spaced review</Badge>}
        </div>
        <div
          className="why"
          dangerouslySetInnerHTML={{ __html: mdBold(step.reason) }}
        />
        <button
          className="btn ghost"
          style={{ padding: "2px 6px", fontSize: 12, marginTop: 4 }}
          aria-expanded={open}
          onClick={() => {
            setOpen((v) => !v);
            if (!open && !explain.data)
              explain.mutate({ learnerId, resourceId: step.resource_id });
          }}
        >
          why this?
        </button>
        {open && (
          <div className="why" style={{ marginTop: 6, fontStyle: "italic" }}>
            {explain.isPending && "…"}
            {explain.error && <span style={{ color: "var(--warn)" }}>could not load</span>}
            {explain.data && (
              <span dangerouslySetInnerHTML={{ __html: mdBold(explain.data.reason) }} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function mdBold(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}
