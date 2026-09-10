import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { catalogueFixture } from "../../test/handlers";
import { server } from "../../test/server";
import { renderApp } from "../../test/utils";
import { LearnerPage } from "./LearnerPage";

describe("LearnerPage", () => {
  it("recommends a plan and shows the steps + objective", async () => {
    const user = userEvent.setup();
    renderApp(<LearnerPage catalogue={catalogueFixture} />);

    expect(screen.getByText(/Pick goal concepts/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Recommend" }));

    const plan = (await screen.findByText("2 steps")).closest("section")!;
    expect(within(plan).getByText("quadratics:lesson")).toBeInTheDocument();
    expect(within(plan).getByText("Mastery gain ↑")).toBeInTheDocument();
  });

  it("sends the selected learning speed and reflects it in the header", async () => {
    const seen: string[] = [];
    server.use(
      http.post("/recommend", async ({ request }) => {
        const body = (await request.json()) as { speed?: string };
        seen.push(body.speed ?? "normal");
        return HttpResponse.json({
          paths: [
            {
              feasible: true,
              note: "",
              total_minutes: 30,
              objective: { neg_gain: -2, seconds: 1800, load: 1, diff_jump: 3, neg_review: 0 },
              steps: [
                { resource_id: "integers:lesson", concept_id: "integers", reason: "Builds **Integers**." },
              ],
            },
          ],
          meta: { speed: body.speed ?? "normal" },
        });
      }),
    );

    const user = userEvent.setup();
    renderApp(<LearnerPage catalogue={catalogueFixture} />);
    await user.selectOptions(screen.getByLabelText(/Learning speed/i), "fast");
    await user.click(screen.getByRole("button", { name: "Recommend" }));

    await waitFor(() => expect(seen).toContain("fast"));
    expect(await screen.findByText(/speed: fast/i)).toBeInTheDocument();
  });

  it("surfaces an API error instead of a blank panel", async () => {
    server.use(
      http.post("/recommend", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    const user = userEvent.setup();
    renderApp(<LearnerPage catalogue={catalogueFixture} />);
    await user.click(screen.getByRole("button", { name: "Recommend" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/boom/);
  });

  it("logs an attempt and re-solves the plan", async () => {
    const user = userEvent.setup();
    renderApp(<LearnerPage catalogue={catalogueFixture} />);
    await user.click(screen.getByRole("button", { name: "Recommend" }));
    await screen.findByText("2 steps");

    await user.click(screen.getByRole("button", { name: /Submit attempt/i }));
    expect(await screen.findByText(/interaction\(s\)/i)).toBeInTheDocument();
  });

  it("can ask why a step was chosen (on-demand /explain)", async () => {
    const user = userEvent.setup();
    renderApp(<LearnerPage catalogue={catalogueFixture} />);
    await user.click(screen.getByRole("button", { name: "Recommend" }));
    await screen.findByText("2 steps");

    const firstStep = screen.getAllByRole("button", { name: "why?" })[0]!;
    await user.click(firstStep);
    expect(await screen.findByText(/grounded in the graph/i)).toBeInTheDocument();
  });

  it("does not offer goals that aren't in the catalogue", () => {
    renderApp(<LearnerPage catalogue={catalogueFixture} />);
    const group = screen.getByRole("group", { name: /Goal concepts/i });
    expect(within(group).queryByText("Nonexistent")).not.toBeInTheDocument();
  });
});
