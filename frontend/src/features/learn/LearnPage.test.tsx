import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../../test/server";
import { renderApp } from "../../test/utils";
import { LearnPage } from "./LearnPage";

const at = (goal: string) => ({ route: `/learn?goal=${encodeURIComponent(goal)}` });

describe("LearnPage — goal → assess → plan", () => {
  it("resolves the goal and shows the concept graph", async () => {
    renderApp(<LearnPage />, at("quadratic equations"));
    expect(await screen.findByText(/curated algebra graph/i)).toBeInTheDocument();
    expect(screen.getByText("Fractions")).toBeInTheDocument();
  });

  it("runs the adaptive quiz then shows the plan", async () => {
    const user = userEvent.setup();
    renderApp(<LearnPage />, at("quadratic equations"));

    await user.click(await screen.findByRole("button", { name: /2-minute assessment/i }));
    expect(await screen.findByText(/Which is smallest/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /-5/ }));
    await user.click(await screen.findByRole("button", { name: /see my plan/i }));

    expect(await screen.findByText("3 steps")).toBeInTheDocument();
    expect(screen.getByText(/quadratics — an open article/)).toBeInTheDocument();
    expect(screen.getAllByText(/wikipedia/).length).toBeGreaterThan(0);
  });

  it("skips assessment for a non-assessable domain", async () => {
    server.use(
      http.post("/resolve", () =>
        HttpResponse.json({
          goal: "binary search tree",
          domain: "dsa",
          source: "seed",
          assessable: false,
          goals: ["bst"],
          concepts: [{ id: "bst", name: "Binary search trees" }],
          prerequisites: [],
        }),
      ),
    );
    const user = userEvent.setup();
    renderApp(<LearnPage />, at("binary search tree"));

    expect(await screen.findByText(/No calibrated diagnostic/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /build my plan/i }));
    expect(await screen.findByText("3 steps")).toBeInTheDocument();
  });

  it("surfaces a resolve failure", async () => {
    renderApp(<LearnPage />, at("__boom__ nonsense"));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not resolve/i);
  });

  it("each plan step links out to a real resource", async () => {
    const user = userEvent.setup();
    renderApp(<LearnPage />, at("quadratic equations"));
    await user.click(await screen.findByRole("button", { name: /2-minute assessment/i }));
    await user.click(await screen.findByText("-5"));
    await user.click(await screen.findByRole("button", { name: /see my plan/i }));

    const links = await screen.findAllByRole("link");
    const wiki = links.filter((a) => a.getAttribute("href")?.includes("wikipedia.org"));
    expect(wiki.length).toBeGreaterThanOrEqual(3);
  });

  it("can ask why a step was chosen", async () => {
    const user = userEvent.setup();
    server.use(http.post("/resolve", () => HttpResponse.json({
      goal: "x", domain: "dsa", source: "seed", assessable: false,
      goals: ["bst"], concepts: [{ id: "bst", name: "BST" }], prerequisites: [],
    })));
    renderApp(<LearnPage />, at("bst"));
    await user.click(await screen.findByRole("button", { name: /build my plan/i }));
    const why = await screen.findAllByRole("button", { name: /why this/i });
    await user.click(why[0]!);
    expect(await screen.findByText(/grounded in the graph/i)).toBeInTheDocument();
  });
});

describe("command palette", () => {
  it("opens on ⌘K and navigates", async () => {
    const user = userEvent.setup();
    const { App } = await import("../../App");
    renderApp(<App />, { route: "/" });
    await user.keyboard("{Meta>}k{/Meta}");
    const dialog = await screen.findByRole("dialog", { name: /command palette/i });
    expect(within(dialog).getByText("Teacher console")).toBeInTheDocument();
  });
});
