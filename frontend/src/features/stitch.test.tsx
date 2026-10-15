/** The Stitch screens, each driven by the (mocked) Syntropix API. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "../App";
import { practiceFailFixture, practiceTasksFixture } from "../test/handlers";
import { server } from "../test/server";
import { renderApp } from "../test/utils";
import { AssessPage } from "./assess/AssessPage";
import { CalendarPage } from "./calendar/CalendarPage";
import { MapPage } from "./map/MapPage";
import { PlanPage } from "./plan/PlanPage";
import { RoadmapPage } from "./plan/RoadmapPage";
import { SessionPage } from "./plan/SessionPage";
import { PracticePage } from "./practice/PracticePage";

const goal = { goal: "quadratic equations" };

describe("Shell", () => {
  it("has the Stitch sidebar, the live API status and a command palette", async () => {
    const user = userEvent.setup();
    renderApp(<App />, { route: "/today" });
    const nav = screen.getByRole("navigation", { name: "Main" });
    for (const label of ["Today", "Roadmap", "Skill Map", "Learn (Videos)", "Practice", "Projects", "Interview Prep", "Certifications", "Progress", "Calendar"])
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    expect(await screen.findByText("Connected")).toBeInTheDocument();
    await user.keyboard("{Control>}k{/Control}");
    const dialog = await screen.findByRole("dialog", { name: /command palette/i });
    await user.click(within(dialog).getByRole("button", { name: /^Calendar/ }));
    expect(await screen.findByRole("heading", { name: /Set a goal first/ })).toBeInTheDocument();
  });

  it("design notes are off by default and the top-bar toggle shows them", async () => {
    const user = userEvent.setup();
    renderApp(<App />, { route: "/map" });
    expect(screen.queryByText("Design notes: skill map")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Design notes: off/ }));
    expect(screen.getByText("Design notes: skill map")).toBeInTheDocument();
  });
});

describe("Skill Map", () => {
  it("resolves a goal into the prerequisite graph and runs the recovery experiment", async () => {
    const user = userEvent.setup();
    renderApp(<MapPage />);
    await user.type(screen.getByLabelText(/what do you want to learn/i), "quadratic equations");
    await user.click(screen.getByRole("button", { name: /resolve goal/i }));
    expect(await screen.findByRole("heading", { name: "How the topics connect" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /prerequisite graph with 4 concepts/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Take the skill check/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Run the experiment/ }));
    expect(await screen.findByText("Hidden links found")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });
});

describe("Adaptive skill check", () => {
  it("1–4 picks, Enter confirms, and the result is saved for the plan", async () => {
    const user = userEvent.setup();
    renderApp(<AssessPage />, { track: goal });
    expect(await screen.findByText("Which is smallest?")).toBeInTheDocument();
    expect(screen.getByText(/(Easier|Medium|Harder) question/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How sure we are about each skill" })).toBeInTheDocument();
    await user.keyboard("1");
    expect(screen.getAllByRole("radio")[0]).toBeChecked();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("button", { name: /See my plan/ })).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("syntropix-track") ?? "{}").assessment).not.toBeNull();
  });

  it("“I don't know yet” records uncertainty instead of a guess", async () => {
    let sent: unknown = null;
    server.use(
      http.post("/assess/answer", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ done: true, band: "intermediate", answered: 1, progress: 1, style: null, question: null, estimates: [] });
      }),
    );
    const user = userEvent.setup();
    renderApp(<AssessPage />, { track: goal });
    await user.click(await screen.findByRole("button", { name: /I don't know yet/ }));
    expect(await screen.findByRole("button", { name: /See my plan/ })).toBeInTheDocument();
    expect(sent).toMatchObject({ response: "-1" });
  });
});

describe("Study plan", () => {
  it("shows sessions, typed steps and the planner's reason for a step", async () => {
    const user = userEvent.setup();
    renderApp(<PlanPage />, { track: goal });
    expect(await screen.findByText("Time left")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Session 01 · Today/ })).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getAllByText("Review").length).toBeGreaterThan(0);
    expect(screen.getByText("Do this next")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: /Why this now/ })[0]!);
    expect(await screen.findByText(/grounded in the graph/)).toBeInTheDocument();
    expect(document.querySelectorAll("[data-step]").length).toBe(3);
    await user.click(screen.getByRole("button", { name: /Repairs & Checks/ }));
    expect(document.querySelectorAll("[data-step]").length).toBe(0); // the mock plan has none
  });

  it("the roadmap tab draws the phases on a timeline", async () => {
    renderApp(<RoadmapPage />, { track: goal });
    expect(await screen.findByRole("heading", { name: "Your path, phase by phase" })).toBeInTheDocument();
    expect(screen.getByText(/YOU ARE HERE/)).toBeInTheDocument();
  });

  it("a session preview shows its lineage and steps", async () => {
    renderApp(
      <Routes>
        <Route path="/session/:n" element={<SessionPage />} />
      </Routes>,
      { route: "/session/1", track: goal },
    );
    expect(await screen.findByText("Before and after")).toBeInTheDocument();
    expect(screen.getByText(/SESSION 01 PREVIEW/)).toBeInTheDocument();
    expect(screen.getByText("Chance you pass")).toBeInTheDocument();
  });
});

describe("Calendar", () => {
  it("lays the plan on a calendar and simulates a missed session", async () => {
    let starts: (string | undefined)[] = [];
    server.use(
      http.post("/schedule", async ({ request }) => {
        const b = (await request.json()) as { start?: string; deadline: string };
        starts.push(b.start);
        const late = Boolean(b.start);
        return HttpResponse.json({
          calendar: {
            feasible: true,
            note: "",
            start: "2026-01-05",
            deadline: b.deadline,
            finish: "2026-01-20",
            slack_days: late ? 1 : 3,
            weeks: 3,
            hours_per_week: 5,
            hours_per_week_needed: 0,
            n_retention: 2,
            goal_mastery: { "Quadratic equations": 0.86 },
            reasons: ["On the deadline every goal skill is at or above 75%."],
            steps: [
              { day: late ? "2026-01-07" : "2026-01-05", weekday: 0, slot_index: 0, concept_id: "integers", concept: "Integers", resource_id: "r", title: "", url: "", source: "", kind: "teach", minutes: 30 },
            ],
          },
          meta: {},
        });
      }),
    );
    starts = [];
    const user = userEvent.setup();
    renderApp(<CalendarPage />, { track: { ...goal, deadline: "2026-01-26" } });
    expect(await screen.findByRole("grid", { name: /study calendar/i })).toBeInTheDocument();
    expect(screen.getAllByText("Spare days").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "+2d" }));
    expect(await screen.findByText(/No problem: your spare days go from 21 to 19/)).toBeInTheDocument();
    expect(starts.some(Boolean)).toBe(true);
  });
});

describe("SQL practice lab", () => {
  it("runs a query, shows the check suite, per-row status and the routed repair", async () => {
    const user = userEvent.setup();
    renderApp(<PracticePage />, { route: "/practice?target=outer_join" });
    expect(await screen.findByText(/customers with none show 0/)).toBeInTheDocument();
    expect(screen.getByText("Tables you can use")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your SQL"), "SELECT 1{Control>}{Enter}{/Control}");
    expect(await screen.findByText("1 of 2 passed")).toBeInTheDocument();
    expect(screen.getByText("What went wrong")).toBeInTheDocument();
    expect(screen.getByText("EXTRA")).toBeInTheDocument();
    expect(screen.getByText(/1 expected row is missing/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Fix NULL & three-valued logic first/ }));
    expect(await screen.findByText(/whose city is unknown/)).toBeInTheDocument();
  });

  it("hints unlock one level at a time", async () => {
    const user = userEvent.setup();
    renderApp(<PracticePage />, { route: "/practice?target=outer_join" });
    await screen.findByText(/customers with none show 0/);
    const shape = "SELECT …, COUNT(…) FROM … LEFT JOIN … ON … = … GROUP BY …";
    await user.click(screen.getByRole("button", { name: /Show hint 1/ }));
    expect(screen.getByText("Hint 1: the idea").parentElement).toHaveTextContent(/LEFT JOIN keeps every row/);
    expect(screen.queryByText(shape)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Show hint 2/ }));
    expect(screen.getByText(shape)).toBeInTheDocument();
  });
});

describe("practice lab beyond SQL", () => {
  const excelTask = {
    id: "xl_share",
    concept_id: "spreadsheets.abs_refs",
    concept: "Relative vs absolute references",
    kind: "excel",
    domain: "spreadsheets",
    prompt: "In G2, each sale's share of the total amount; it must still work when filled down.",
    ordered: false,
    minutes: 5,
    hints: ["Anchor the total's range with $."],
    cell: "G2",
    fill_down: true,
  };
  const choiceTask = {
    id: "tab_extract",
    concept_id: "tableau.tab_connect",
    concept: "Connecting data",
    kind: "value",
    domain: "tableau",
    prompt: "A Tableau extract is:",
    ordered: false,
    minutes: 3,
    options: ["A snapshot copy of the data that you refresh", "A live connection queried on every click"],
  };
  const tasks = (task: object) => ({
    ...practiceTasksFixture,
    start: (task as { id: string }).id,
    path: [(task as { concept_id: string }).concept_id],
    sheet: [["Region", "Amount"], ["North", "120"]],
    tasks: [task],
  });

  it("an Excel task shows the sheet and a formula bar, and sends the formula", async () => {
    let sent: { query?: string } = {};
    server.use(
      http.get("/practice/tasks", () => HttpResponse.json(tasks(excelTask))),
      http.post("/practice/submit", async ({ request }) => {
        sent = (await request.json()) as { query: string };
        return HttpResponse.json({
          ...practiceFailFixture,
          task_id: "xl_share",
          result: { ...practiceFailFixture.result, columns: ["G2", "G3 (copied down)"], rows: [["0.12", "#DIV/0!"]], row_status: ["extra"], missing_rows: 1, expected_rows: 1 },
          diagnoses: [{ code: "missing_anchor", concept_id: "spreadsheets.abs_refs", weight: 1, message: "Anchor the total's range with $." }],
        });
      }),
    );
    const user = userEvent.setup();
    renderApp(<PracticePage />, { route: "/practice?target=spreadsheets.abs_refs" });
    expect(await screen.findByText("Sheet1")).toBeInTheDocument();
    expect(screen.queryByText("Schema Inspection")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Formula for G2"), "=E2/SUM(E2:E11){Enter}");
    expect(await screen.findByText("WRONG")).toBeInTheDocument();
    expect(sent.query).toBe("=E2/SUM(E2:E11)");
    expect(screen.getAllByText("Missing $ anchor").length).toBeGreaterThan(0);
  });

  it("a multiple-choice task submits the picked option", async () => {
    let sent: { query?: string } = {};
    server.use(
      http.get("/practice/tasks", () => HttpResponse.json(tasks(choiceTask))),
      http.post("/practice/submit", async ({ request }) => {
        sent = (await request.json()) as { query: string };
        return HttpResponse.json({ ...practiceFailFixture, task_id: "tab_extract", correct: true, diagnoses: [] });
      }),
    );
    const user = userEvent.setup();
    renderApp(<PracticePage />, { route: "/practice?target=tableau.tab_connect" });
    await user.click(await screen.findByRole("radio", { name: /snapshot copy/ }));
    await user.click(screen.getByRole("button", { name: /Run and check/ }));
    expect(await screen.findByText(/Correct! /)).toBeInTheDocument();
    expect(sent.query).toBe("A snapshot copy of the data that you refresh");
  });
});
