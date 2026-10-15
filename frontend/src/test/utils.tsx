import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";

import { LearnerProvider } from "../context/LearnerContext";
import { TrackProvider, type Track } from "../context/TrackContext";

export function renderApp(
  ui: ReactElement,
  { route = "/", track, ...options }: RenderOptions & { route?: string; track?: Partial<Track> } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <LearnerProvider>
          <TrackProvider initial={track}>
            <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
          </TrackProvider>
        </LearnerProvider>
      </QueryClientProvider>
    );
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) };
}
