# VELPO frontend

React 18 + TypeScript + Vite. Talks to the FastAPI service; the production build
lands in `../web/` and FastAPI serves it at `/`.

```bash
npm install
npm run dev      # http://localhost:5173  (proxies /catalogue etc. to :8000 - run `python velpo.py api`)
npm run test     # vitest + React Testing Library + MSW
npm run lint     # tsc --noEmit (strict)
npm run build    # -> ../web/
```

## Stack

| concern | choice |
|---|---|
| look | **Tailwind CSS** with the Google Stitch "DAG runtime" theme (`tailwind.config.js`), Material Symbols icons |
| server state | **TanStack Query** - caching, dedupe, mutation-driven invalidation |
| routing | **React Router** - one route per Stitch screen; the Teacher Console is code-split |
| runtime validation | **Zod** - every API response is parsed; a shape change fails in one place |
| app state | `TrackContext` (goal, level, hours, date, last skill check) and `LearnerContext`, both persisted |
| tests | **Vitest + @testing-library/react + MSW** - mock API, no backend needed |

## Layout

```
src/
  main.tsx              providers: QueryClient · Learner · Track · Router · ErrorBoundary
  App.tsx               route table inside the Stitch shell
  components/ Shell.tsx (sidebar, top bar, status footer, palette) · stitch.tsx (primitives) · ParetoChart
  context/    LearnerContext · TrackContext
  lib/        api.ts (zod client) · queries.ts · plan.ts (sessions, delta) · ics.ts · format.ts
  features/   map · assess · plan (study plan, roadmap, session) · calendar · practice · teacher
  test/       setup.ts · server.ts · handlers.ts · utils.tsx
```

## `npm audit`

The remaining advisories are all in **dev-only tooling** (the Vite dev server,
the Vitest runner, a React Router `<Link>` edge case we don't hit). None are in
`../web/`, the static bundle that ships.
