import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  try {
    localStorage.clear();
  } catch {
    /* ignore */
  }
});
afterAll(() => server.close());

// recharts' ResponsiveContainer measures its parent - give jsdom a real size
class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= RO as unknown as typeof ResizeObserver;

for (const prop of ["offsetWidth", "clientWidth"] as const) {
  Object.defineProperty(HTMLElement.prototype, prop, { configurable: true, value: 640 });
}
for (const prop of ["offsetHeight", "clientHeight"] as const) {
  Object.defineProperty(HTMLElement.prototype, prop, { configurable: true, value: 320 });
}
HTMLElement.prototype.getBoundingClientRect = () =>
  ({ width: 640, height: 320, top: 0, left: 0, right: 640, bottom: 320, x: 0, y: 0, toJSON() {} }) as DOMRect;
