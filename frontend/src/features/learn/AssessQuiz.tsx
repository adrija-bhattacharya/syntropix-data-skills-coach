import { useEffect, useMemo, useState } from "react";

import { Button, Callout, Spinner } from "../../components/ui";
import { useLearner } from "../../context/LearnerContext";
import type { AssessState } from "../../lib/api";
import { useAssessment } from "../../lib/queries";

/** One-question-at-a-time adaptive diagnostic with a live per-skill ability meter. */
export function AssessQuiz({
  goals,
  skillNames,
  onDone,
}: {
  goals: string[];
  skillNames: Record<string, string>;
  onDone: () => void;
}) {
  const { learnerId } = useLearner();
  const { start, answer } = useAssessment(learnerId);
  const [state, setState] = useState<AssessState | null>(null);
  const [text, setText] = useState("");

  const goalKey = useMemo(() => goals.join(","), [goals]);
  useEffect(() => {
    setState(null);
    start.mutate(goals, { onSuccess: setState });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goalKey]);

  if (start.isPending || (!state && !start.isError)) return <Spinner label="Building your diagnostic…" />;
  if (start.isError) return <Callout tone="warn">{start.error.message}</Callout>;
  if (!state) return null;

  if (state.done) {
    return (
      <div className="quiz">
        <div className="quiz-card">
          <h2 style={{ fontSize: 22, marginBottom: 8 }}>Your level, measured.</h2>
          <p className="hint" style={{ marginBottom: 4 }}>
            {state.answered} adaptive questions — no self-rating.
          </p>
          <Meters state={state} skillNames={skillNames} />
          <Button variant="primary" className="big" style={{ marginTop: 22 }} onClick={onDone}>
            See my plan →
          </Button>
        </div>
      </div>
    );
  }

  const q = state.question!;
  const submit = (response: string) => {
    setText("");
    answer.mutate({ itemId: q.item_id, response }, { onSuccess: setState });
  };

  return (
    <div className="quiz">
      <div className="meter" style={{ gridTemplateColumns: "1fr 42px", marginBottom: 14 }}>
        <div className="track">
          <div className="fill" style={{ width: `${Math.round(state.progress * 100)}%` }} />
        </div>
        <span className="pct">{state.answered}</span>
      </div>

      <div className="quiz-card" key={q.item_id}>
        <span className="skill">{skillNames[q.skill] ?? q.skill}</span>
        <div className="stem">{q.stem}</div>

        {q.kind === "mcq" ? (
          <div className="choices">
            {q.choices.map((c, i) => (
              <button
                key={i}
                className="choice"
                disabled={answer.isPending}
                onClick={() => submit(String(i))}
              >
                <span className="mk">{String.fromCharCode(65 + i)}</span>
                {c}
              </button>
            ))}
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) submit(text.trim());
            }}
          >
            <input
              className="input"
              autoFocus
              placeholder="Type your answer"
              value={text}
              onChange={(e) => setText(e.target.value)}
              aria-label="Your answer"
            />
            <Button
              variant="primary"
              type="submit"
              style={{ marginTop: 10 }}
              disabled={answer.isPending || !text.trim()}
            >
              Submit
            </Button>
          </form>
        )}
        {answer.isError && (
          <div style={{ marginTop: 10 }}>
            <Callout tone="warn">{answer.error.message}</Callout>
          </div>
        )}
      </div>

      <Meters state={state} skillNames={skillNames} />
    </div>
  );
}

function Meters({ state, skillNames }: { state: AssessState; skillNames: Record<string, string> }) {
  return (
    <div className="meters">
      {state.estimates.map((e) => (
        <div className="meter" key={e.skill}>
          <span style={{ color: "var(--ink-2)" }}>{skillNames[e.skill] ?? e.skill}</span>
          <div className="track">
            <div className="fill" style={{ width: `${Math.round(e.mastery * 100)}%` }} />
          </div>
          <span className="pct">{e.n_items ? `${Math.round(e.mastery * 100)}%` : "—"}</span>
        </div>
      ))}
    </div>
  );
}
