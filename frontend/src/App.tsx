import { lazy, Suspense } from "react";
import { Link, NavLink, Route, Routes } from "react-router-dom";

import { CommandPalette } from "./components/CommandPalette";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ThemeToggle } from "./components/ThemeToggle";
import { Callout, Empty, Spinner } from "./components/ui";
import type { Catalogue } from "./lib/api";
import { useCatalogue } from "./lib/queries";
import { HomePage } from "./features/home/HomePage";
import { LearnPage } from "./features/learn/LearnPage";

const TeacherPage = lazy(() =>
  import("./features/teacher/TeacherPage").then((m) => ({ default: m.TeacherPage })),
);

export function App() {
  return (
    <div className="shell">
      <CommandPalette />
      <header className="topbar">
        <Link to="/" className="wordmark">
          VELPO
        </Link>
        <span className="spacer" />
        <NavLink to="/teacher" className={({ isActive }) => `navlink ${isActive ? "active" : ""}`}>
          Teacher console
        </NavLink>
        <span className="kbd">⌘K</span>
        <ThemeToggle />
      </header>

      <ErrorBoundary>
        <Suspense fallback={<Empty>Loading…</Empty>}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/learn" element={<LearnPage />} />
            <Route
              path="/teacher"
              element={
                <CatalogueGate>{(cat) => <TeacherPage catalogue={cat} />}</CatalogueGate>
              }
            />
            <Route path="*" element={<HomePage />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>

      <footer className="foot">
        Every path is a linear extension of the prerequisite poset — valid <em>by construction</em>.
        The sequencing DP is provably optimal; the adaptive test is 2-parameter IRT; resources are
        real and open.
      </footer>
    </div>
  );
}

function CatalogueGate({ children }: { children: (c: Catalogue) => React.ReactNode }) {
  const { data, isPending, isError, error, refetch } = useCatalogue();
  if (isPending) return <Spinner label="Loading…" />;
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
