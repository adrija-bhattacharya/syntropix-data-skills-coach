import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../../components/ui";

const EXAMPLES = [
  "become a data analyst",
  "learn SQL",
  "pandas & data cleaning",
  "A/B testing & hypothesis testing",
  "data visualisation with Python",
  "I'm a complete beginner",
];

export function HomePage() {
  const [goal, setGoal] = useState("");
  const nav = useNavigate();

  const submit = (g: string) => {
    const t = g.trim();
    if (t.length > 1) nav(`/learn?goal=${encodeURIComponent(t)}`);
  };

  return (
    <div className="hero">
      <h1>
        Learn anything,
        <br />
        <span className="grad">in the right order.</span>
      </h1>
      <p>
        Tell VELPO a data-analytics goal or a target role. It measures where you are with a short
        adaptive test, finds the best open resources, and sequences them into a provably-optimal
        plan — from zero if that's where you are.
      </p>

      <form
        className="goalbar"
        onSubmit={(e) => {
          e.preventDefault();
          submit(goal);
        }}
      >
        <input
          className="input"
          autoFocus
          placeholder="What do you want to learn?"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          aria-label="Learning goal"
        />
        <Button variant="primary" className="big" type="submit" disabled={goal.trim().length < 2}>
          Start →
        </Button>
      </form>

      <div className="examples">
        {EXAMPLES.map((e) => (
          <button key={e} type="button" className="chip" onClick={() => submit(e)}>
            {e}
          </button>
        ))}
      </div>
    </div>
  );
}
