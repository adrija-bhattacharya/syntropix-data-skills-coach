import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";

import { LearnerProvider } from "../context/LearnerContext";
import { ThemeProvider } from "../lib/theme";

export function renderApp(
  ui: ReactElement,
  { route = "/", ...options }: RenderOptions & { route?: string } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <LearnerProvider>
            <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
          </LearnerProvider>
        </ThemeProvider>
      </QueryClientProvider>
    );
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) };
}
