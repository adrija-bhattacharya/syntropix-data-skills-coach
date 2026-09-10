import { lazy, Suspense } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { ThemeToggle } from "./components/ThemeToggle";
import { Callout, Empty, Spinner } from "./components/ui";
import { useCatalogue } from "./lib/queries";
import type { Catalogue } from "./lib/api";

const LearnerPage = lazy(() =>
  import("./features/learner/LearnerPage").then((m) => ({ default: m.LearnerPage })),
);
const TeacherPage = lazy(() =>
  import("./features/teacher/TeacherPage").then((m) => ({ default: m.TeacherPage })),
);

export function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <b>VELPO</b>
          <span>Personalised Learning-Path Optimiser</span>
        </div>
        <nav className="tabs">
          <NavLink to="/learner" className={({ isActive }) => (isActive ? "active" : "")}>
            Learner
          </NavLink>
          <NavLink to="/teacher" className={({ isActive }) => (isActive ? "active" : "")}>
            Teacher console
          </NavLink>
        </nav>
        <span className="spacer" />
        <ThemeToggle />
      </header>

      <ErrorBoundary>
        <CatalogueGate>
          {(catalogue) => (
            <Suspense fallback={<Empty>Loading view…</Empty>}>
              <Routes>
                <Route path="/" element={<Navigate to="/learner" replace />} />
                <Route path="/learner" element={<LearnerPage catalogue={catalogue} />} />
                <Route path="/teacher" element={<TeacherPage catalogue={catalogue} />} />
                <Route path="*" element={<Navigate to="/learner" replace />} />
              </Routes>
            </Suspense>
          )}
        </CatalogueGate>
      </ErrorBoundary>

      <footer className="foot">
        Every path is prerequisite-valid and budget-bounded <em>by construction</em>; the optimal
        solver is provably globally optimal in <code>O(V·R·B)</code>. Anytime A* re-plans in{" "}
        <code>&lt;1&nbsp;ms</code>.
      </footer>
    </div>
  );
}

function CatalogueGate({ children }: { children: (c: Catalogue) => React.ReactNode }) {
  const { data, isPending, isError, error, refetch } = useCatalogue();
  if (isPending)
    return (
      <div style={{ marginTop: 40 }}>
        <Spinner label="Loading curriculum…" />
      </div>
    );
  if (isError)
    return (
      <div style={{ marginTop: 24 }}>
        <Callout tone="warn">
          {error.message}
          <div style={{ marginTop: 10 }}>
            <button className="btn" onClick={() => void refetch()}>
              Retry
            </button>
          </div>
        </Callout>
      </div>
    );
  return <>{children(data)}</>;
}
