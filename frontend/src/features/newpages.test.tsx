/** The pages added with the Syntropix rebuild: opening page, Today, Learn,
 * problem sets, Interview, Certifications, Progress, Projects. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { http, HttpResponse } from "msw";

import { portfolioFixture } from "../test/handlers";
import { server } from "../test/server";
import { renderApp } from "../test/utils";
import { FeedbackLoop } from "./calendar/FeedbackLoop";
import { CertificationsPage } from "./certifications/CertificationsPage";
import { InterviewPage } from "./interview/InterviewPage";
import { PortfolioPage } from "./portfolio/PortfolioPage";
import { LearnPage } from "./learn/LearnPage";
import { ProblemSets } from "./practice/ProblemSets";
import { ProgressPage } from "./progress/ProgressPage";
import { ProjectsPage } from "./projects/ProjectsPage";
import { TodayPage } from "./today/TodayPage";
import { WelcomePage } from "./welcome/WelcomePage";

const goal = { goal: "quadratic equations" };

describe("opening page", () => {
  it("shows the animated logo and fills the set-up steps from real calls", async () => {
    renderApp(<WelcomePage />, { track: goal });
    expect(screen.getByRole("img", { name: /Syntropix logo/ })).toBeInTheDocument();
    expect(await screen.findByText(/4 topics and 5 lessons ready/)).toBeInTheDocument();
    expect(await screen.findByText(/195 videos, 230 LeetCode \+ 252 HackerRank problems/)).toBeInTheDocument();
    expect(screen.getByText(/Not measured yet: take the 10-minute skill check/)).toBeInTheDocument();
    expect(screen.getByLabelText("Start-up log")).toHaveTextContent("[READY]");
  });

  it("a quick goal sets the track", async () => {
    const user = userEvent.setup();
    renderApp(<WelcomePage />);
    await user.click(screen.getByRole("button", { name: /Data Analyst/ }));
    expect(JSON.parse(localStorage.getItem("syntropix-track") ?? "{}").goal).toBe("data analyst");
  });
});

describe("Learn (Videos)", () => {
  it("plays the first unwatched video inside the app and ticks it off", async () => {
    const user = userEvent.setup();
    renderApp(<LearnPage />, { track: goal });
    const frame = await screen.findByTitle("Video course00001");
    expect(frame.getAttribute("src")).toContain("youtube-nocookie.com/embed/course00001");
    expect(screen.getByText("0 / 2 watched")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Mark as watched/ }));
    expect(screen.getByText("1 / 2 watched")).toBeInTheDocument();
  });
});

describe("Problem sets", () => {
  it("lists LeetCode and HackerRank problems by week and by topic, with a pace switch", async () => {
    const user = userEvent.setup();
    renderApp(<ProblemSets />, { track: goal });
    expect(await screen.findByRole("heading", { name: "Week 1" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Big Countries" })).toHaveAttribute("target", "_blank");
    await user.click(screen.getByRole("tab", { name: /Topic by topic/ }));
    expect(screen.getByRole("link", { name: "Revising the Select Query" })).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: /Mark "Big Countries" as solved/ }));
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Fast" }));
    expect(await screen.findByText(/Your pace: Fast/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Stretch/ }));
    expect(screen.getByRole("link", { name: "Hard One" })).toBeInTheDocument();
  });
});

describe("Today, interview, certificates, progress, projects", () => {
  it("Today shows the current session, the next video and problems", async () => {
    renderApp(<TodayPage />, { track: goal });
    expect(await screen.findByRole("heading", { name: /Session 1/ })).toBeInTheDocument();
    expect(await screen.findByText(/^Video (course|lesson)00001$/)).toBeInTheDocument(); // the first one not yet watched
    expect(screen.getByRole("link", { name: /See all problems/ })).toBeInTheDocument();
  });

  it("Interview prep builds a timed mock from built-in tasks", async () => {
    renderApp(<InterviewPage />, { track: goal });
    expect(await screen.findByRole("heading", { name: /Mock interview/ })).toBeInTheDocument();
    expect((await screen.findAllByRole("link", { name: "Solve" })).length).toBeGreaterThan(0);
    expect(screen.getByText("30:00")).toBeInTheDocument();
  });

  it("Certifications groups by level and can filter to free ones", async () => {
    const user = userEvent.setup();
    renderApp(<CertificationsPage />, { track: goal });
    expect(await screen.findByText("Microsoft PL-300")).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: /Free only/ }));
    expect(screen.queryByText("Microsoft PL-300")).not.toBeInTheDocument();
    expect(screen.getByText("HackerRank SQL (Basic)")).toBeInTheDocument();
  });

  it("Progress adds up topics, videos and problems", async () => {
    renderApp(<ProgressPage />, { track: goal });
    expect(await screen.findByText("Topics known")).toBeInTheDocument();
    expect(screen.getByText("0 / 1")).toBeInTheDocument();
  });

  it("Projects link to real datasets", () => {
    renderApp(<ProjectsPage />, { track: goal });
    const card = screen.getByRole("heading", { name: "Music store questions with SQL" }).closest("article")!;
    expect(within(card).getByRole("link", { name: /Get the data/ })).toHaveAttribute("href", "https://github.com/lerocha/chinook-database");
  });
});

describe("calendar feedback loop", () => {
  it("reads back a missed session and shows the re-plan", async () => {
    const user = userEvent.setup();
    renderApp(<FeedbackLoop learnerId="demo" goal="quadratic equations" goals={["quadratics"]} deadline="2099-02-01" hoursPerWeek={5} speed="normal" domain="sql" />);
    expect(await screen.findByRole("heading", { name: /Your week, re-planned/ })).toBeInTheDocument();
    expect(await screen.findByText("Not measured yet")).toBeInTheDocument();
    await user.click(within(screen.getByRole("group", { name: /How .* went/ })).getByRole("button", { name: "Missed" }));
    expect(await screen.findByText("65% of planned time")).toBeInTheDocument();
    expect(screen.getByText(/planned as 300 minutes/)).toBeInTheDocument();
    expect(screen.getByText(/clash with events/)).toBeInTheDocument();
    expect(screen.getByRole("list", { name: /Study blocks/ })).toBeInTheDocument();
    expect(screen.getByText(/80% sure by .* 83% chance by the deadline/)).toBeInTheDocument();
    expect(screen.getByText("1.6× the lesson time")).toBeInTheDocument();
    expect(screen.getByText("50% of the lesson time")).toBeInTheDocument();
    // G1 self-check, G2 slowdown, G4/G5 study context, G3 what fits
    expect(screen.getByText(/held 3 of 5 times for you, so your dates are widened/)).toBeInTheDocument();
    expect(screen.getByText(/at 30% of the speed/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Practise NULL/ })).toBeInTheDocument();
    expect(screen.getByText("Weekend mornings")).toBeInTheDocument();
    expect(screen.getByText("25-minute blocks")).toBeInTheDocument();
    expect(await screen.findByText(/Window functions \(later\)/)).toBeInTheDocument();
    expect(screen.getByText(/to fit everything at this confidence: 8 h a week/)).toBeInTheDocument();
  });
});

describe("portfolio", () => {
  it("shows re-checked solves, publishes on consent and adds a project from the Projects page", async () => {
    const user = userEvent.setup();
    renderApp(<PortfolioPage />, { route: "/portfolio?project=sql-music" });
    expect(await screen.findByText("Passes when re-run")).toBeInTheDocument();
    expect(screen.getByText("SELECT name, price FROM products")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Open my public page/ })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Name/), "Ada");
    await user.click(screen.getByRole("checkbox", { name: /Make my page public/ }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("link", { name: /Open my public page/ })).toHaveAttribute("href", "/p/ada");
    // the project form is prefilled from the Projects page
    expect(screen.getByLabelText(/Project name/)).toHaveValue("Music store questions with SQL");
    await user.type(screen.getByLabelText(/Link to your code/), "https://github.com/ada/chinook");
    await user.click(screen.getByRole("button", { name: "Add to portfolio" }));
    expect(await screen.findByText("link working")).toBeInTheDocument();
  });
});

describe("today feeds the calendar loop", () => {
  it("asks how the last session went and shows the next block", async () => {
    const user = userEvent.setup();
    renderApp(<TodayPage />, { track: { ...goal, deadline: "2099-02-01" } });
    const ask = await screen.findByText(/How did .* go\?/);
    expect(screen.getByText(/Next: .* at 19:00/)).toBeInTheDocument();
    await user.click(within(screen.getByRole("group", { name: /How .* went/ })).getByRole("button", { name: "Missed" }));
    expect(await screen.findByText(/You manage about 65% of planned time/)).toBeInTheDocument();
    expect(screen.getByText(/likely done .* \(80% by/)).toBeInTheDocument();
    expect(ask).not.toBeInTheDocument();
  });
});

describe("portfolio edit key", () => {
  it("keeps the key it is given and sends it with every change", async () => {
    let sent: string | null = null;
    server.use(
      http.get("/portfolio/:id", () => HttpResponse.json({ ...portfolioFixture, edit_key: "k-123" })),
      http.put("/portfolio/:id/profile", ({ request }) => {
        sent = request.headers.get("x-portfolio-key");
        return HttpResponse.json(portfolioFixture);
      }),
    );
    const user = userEvent.setup();
    renderApp(<PortfolioPage />);
    await screen.findByText("Passes when re-run");
    expect(localStorage.getItem("syntropix-portfolio-key:demo")).toBe("k-123");
    expect(screen.getByRole("link", { name: /Download as a web page/ })).toHaveAttribute("href", "/portfolio/demo/export.html?key=k-123");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Saved");
    expect(sent).toBe("k-123");
  });

  it("explains a protected portfolio in plain words", async () => {
    server.use(http.get("/portfolio/:id", () => HttpResponse.json({ detail: "This portfolio is protected." }, { status: 403 })));
    renderApp(<PortfolioPage />);
    expect(await screen.findByText(/belongs to another browser/)).toBeInTheDocument();
  });
});
