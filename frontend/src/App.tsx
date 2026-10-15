import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { Shell } from "./components/Shell";
import { ErrorBox, Loading } from "./components/stitch";
import { AssessPage } from "./features/assess/AssessPage";
import { CalendarPage } from "./features/calendar/CalendarPage";
import { CertificationsPage } from "./features/certifications/CertificationsPage";
import { InterviewPage } from "./features/interview/InterviewPage";
import { LearnPage } from "./features/learn/LearnPage";
import { MapPage } from "./features/map/MapPage";
import { PlanPage } from "./features/plan/PlanPage";
import { PortfolioPage } from "./features/portfolio/PortfolioPage";
import { RoadmapPage } from "./features/plan/RoadmapPage";
import { SessionPage } from "./features/plan/SessionPage";
import { PracticeHub } from "./features/practice/PracticeHub";
import { ProgressPage } from "./features/progress/ProgressPage";
import { ProjectsPage } from "./features/projects/ProjectsPage";
import { TodayPage } from "./features/today/TodayPage";
import { WelcomePage } from "./features/welcome/WelcomePage";
import { useCatalogue } from "./lib/queries";

// recharts lives only here - keep it out of the main bundle
const TeacherPage = lazy(() => import("./features/teacher/TeacherPage").then((m) => ({ default: m.TeacherPage })));

export function App() {
  return (
    <Shell>
      <ErrorBoundary>
        <Suspense fallback={<Loading label="Loading…" />}>
          <Routes>
            <Route path="/" element={<WelcomePage />} />
            <Route path="/today" element={<TodayPage />} />
            <Route path="/roadmap" element={<RoadmapPage />} />
            <Route path="/plan" element={<PlanPage />} />
            <Route path="/session/:n" element={<SessionPage />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/learn" element={<LearnPage />} />
            <Route path="/practice" element={<PracticeHub />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/interview" element={<InterviewPage />} />
            <Route path="/certifications" element={<CertificationsPage />} />
            <Route path="/progress" element={<ProgressPage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/assess" element={<AssessPage />} />
            <Route path="/teacher" element={<Teacher />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </Shell>
  );
}

function Teacher() {
  const cat = useCatalogue();
  if (cat.isPending) return <Loading label="Loading the course catalogue…" />;
  if (cat.isError) return <ErrorBox>{cat.error.message}</ErrorBox>;
  return <TeacherPage catalogue={cat.data} />;
}
