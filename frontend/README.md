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
| server state | **TanStack Query** - caching, dedupe, `placeholderData`, mutation-driven invalidation |
| routing | **React Router** - `/learner` and `/teacher`, both `React.lazy` code-split |
| runtime validation | **Zod** - every API response is parsed; a shape change fails in one place |
| charts | **Recharts** - difficulty line per plan, Pareto scatter (bubble = cognitive load) |
| local state | `useReducer` for the teacher constraint builder; `Context` for the shared learner id |
| theming | light / dark / system, persisted to `localStorage` |
| tests | **Vitest + @testing-library/react + MSW** - 19 tests, mock API, no backend needed |
| resilience | an `ErrorBoundary` at the root and around the routed views; explicit loading / error / empty states |

## Layout

```
src/
  main.tsx                providers: QueryClient · Router · Theme · Learner · ErrorBoundary
  App.tsx                 shell, nav, route table, catalogue gate
  index.css               design tokens + light/dark
  lib/        api.ts (zod client) · queries.ts (hooks) · format.ts · theme.tsx
  context/    LearnerContext.tsx
  components/ ui.tsx · ChipSelect · PathCard · ParetoChart · ThemeToggle · ErrorBoundary
  features/
    learner/  LearnerPage · RecommendForm · ObservePanel
    teacher/  TeacherPage · ConstraintBuilder · constraintReducer(.test)
  test/       setup.ts · server.ts · handlers.ts · utils.tsx
```

## `npm audit`

The remaining advisories are all in **dev-only tooling** (the Vite dev server,
the Vitest runner, a React Router `<Link>` edge case we don't hit). None are in
`../web/`, the static bundle that ships.
