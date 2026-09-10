import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { LearnerProvider } from "./context/LearnerContext";
import { ThemeProvider } from "./lib/theme";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, staleTime: 15_000, retry: 1 },
  },
});

const DevtoolsLazy = React.lazy(() =>
  import("@tanstack/react-query-devtools").then((m) => ({ default: m.ReactQueryDevtools })),
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <LearnerProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </LearnerProvider>
        </ThemeProvider>
        {import.meta.env.DEV && (
          <React.Suspense fallback={null}>
            <DevtoolsLazy initialIsOpen={false} />
          </React.Suspense>
        )}
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
