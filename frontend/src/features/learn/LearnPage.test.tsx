import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../../test/server";
import { renderApp } from "../../test/utils";
import { LearnPage } from "./LearnPage";

const at = (goal: string) => ({ route: `/learn?goal=${encodeURIComponent(goal)}` });

/** The plan page opens on the roadmap tab; switch to the sequenced study plan. */
async function toStudyPlan(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("tab", { name: /study plan/i }));
}

describe("LearnPage — goal → assess → plan", () => {
  it("resolves the goal and shows the concept graph", async () => {
    renderApp(<LearnPage />, at("quadratic equations"));
    expect(await screen.findByText(/curated algebra graph/i)).toBeInTheDocument();
    expect(screen.getByText("Fractions")).toBeInTheDocument();
  });

  it("asks the level band, then runs the adaptive quiz, then shows the plan", async () => {
    const user = userEvent.setup();
    renderApp(<LearnPage />, at("quadratic equations"));

    await user.click(await screen.findByRole("button", { name: /^Continue/i }));
    expect(await screen.findByText(/How much do you already know/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Intermediate/ }));

    expect(await screen.findByText(/Which is smallest/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /-5/ }));
    await user.click(await screen.findByRole("button", { name: /see my plan/i }));

    // the roadmap is shown first
    expect(await screen.findByText(/Roadmap —/i)).toBeInTheDocument();
    expect(screen.getByText(/Certifications for this track/i)).toBeInTheDocument();

    await toStudyPlan(user);
    expect(await screen.findByText("3 steps")).toBeInTheDocument();
    expect(screen.getByText(/quadratics — an open article/)).toBeInTheDocument();
    expect(screen.getAllByText(/wikipedia/).length).toBeGreaterThan(0);
  });

  it("a beginner mostly keeps their self-assessment", async () => {
    const user = userEvent.setup();
    renderApp(<LearnPage />, at("quadratic equations"));
    await user.click(await screen.findByRole("button", { name: /^Continue/i }));
    await user.click(await screen.findByRole("button", { name: /Beginner/ }));
    await user.click(screen.getByRole("button", { name: /-5/ }));
    expect(await screen.findByText(/Starting from the basics/i)).toBeInTheDocument();
    expect(screen.getByText(/mostly going by what you told us/i)).toBeInTheDocument();
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
    await toStudyPlan(user);
    expect(await screen.findByText("3 steps")).toBeInTheDocument();
  });

  it("surfaces a resolve failure", async () => {
    renderApp(<LearnPage />, at("__boom__ nonsense"));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not resolve/i);
  });

  it("places the plan on a calendar when a deadline is given", async () => {
    const user = userEvent.setup();
    renderApp(<LearnPage />, at("quadratic equations"));

    await user.click(await screen.findByText(/Have a deadline\?/i));
    const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
    await user.type(dateInput, "2026-03-01");

    await user.click(screen.getByRole("button", { name: /^Continue/i }));
    await user.click(await screen.findByRole("button", { name: /Intermediate/ }));
    await user.click(await screen.findByText("-5"));
    await user.click(await screen.findByRole("button", { name: /see my plan/i }));

    await toStudyPlan(user);
    expect(await screen.findByText(/on track/i)).toBeInTheDocument();
    expect(screen.getByText(/every goal skill ≥ 75%/i)).toBeInTheDocument();
    expect(screen.getAllByText(/reinforce/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/3 d slack/i)).toBeInTheDocument();
  });

  it("shows the personalised roadmap with phases and certifications", async () => {
    const user = userEvent.setup();
    renderApp(<LearnPage />, at("quadratic equations"));
    await user.click(await screen.findByRole("button", { name: /^Continue/i }));
    await user.click(await screen.findByRole("button", { name: /Intermediate/ }));
    await user.click(await screen.findByText("-5"));
    await user.click(await screen.findByRole("button", { name: /see my plan/i }));

    expect(await screen.findByText(/Foundations of algebra/i)).toBeInTheDocument();
    expect(screen.getByText(/Applying algebra/i)).toBeInTheDocument();
    expect(screen.getAllByText(/pace/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Intro to SQL \+ Advanced SQL/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Ready to sit:/i)).toBeInTheDocument();
    // profile-matched resource recommendations
    expect(screen.getByText(/Start here — matched to your profile/i)).toBeInTheDocument();
    const yt = screen
      .getAllByRole("link")
      .filter((a) => a.getAttribute("href")?.includes("youtube.com/watch"));
    expect(yt.length).toBeGreaterThan(0);
  });

  it("shows the hiring-readiness meter for a role goal", async () => {
    server.use(
      http.post("/resolve", () =>
        HttpResponse.json({
          goal: "become a data analyst",
          domain: "data analyst",
          source: "role",
          assessable: false,
          goals: ["sql.window_functions"],
          concepts: [{ id: "sql.window_functions", name: "Window functions" }],
          prerequisites: [],
        }),
      ),
      http.post("/recommend", () =>
        HttpResponse.json({
          paths: [
            {
              feasible: true,
              note: "",
              total_minutes: 60,
              objective: { neg_gain: -1, seconds: 3600, load: 1, diff_jump: 2, neg_review: 0 },
              steps: [
                {
                  resource_id: "sql.select:l",
                  concept_id: "sql.select",
                  reason: "Builds **SELECT**.",
                },
              ],
              sessions: [],
            },
          ],
          meta: {
            role: true,
            domain: "data analyst",
            method: "greedy",
            readiness: 0.62,
            readiness_before: 0.1,
            readiness_curve: [
              [0, 0.1],
              [60, 0.62],
            ],
          },
        }),
      ),
    );
    const user = userEvent.setup();
    renderApp(<LearnPage />, at("become a data analyst"));
    await user.click(await screen.findByRole("button", { name: /build my plan/i }));
    await toStudyPlan(user);
    expect(await screen.findByText(/hiring readiness/i)).toBeInTheDocument();
    expect(screen.getByText(/10% →/)).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
  });

  it("each plan step links out to a real resource", async () => {
    const user = userEvent.setup();
    renderApp(<LearnPage />, at("quadratic equations"));
    await user.click(await screen.findByRole("button", { name: /^Continue/i }));
    await user.click(await screen.findByRole("button", { name: /Intermediate/ }));
    await user.click(await screen.findByText("-5"));
    await user.click(await screen.findByRole("button", { name: /see my plan/i }));
    await toStudyPlan(user);

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
    await toStudyPlan(user);
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
