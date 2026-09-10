import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { catalogueFixture } from "../../test/handlers";
import { server } from "../../test/server";
import { renderApp } from "../../test/utils";
import { TeacherPage } from "./TeacherPage";

describe("TeacherPage", () => {
  it("re-solves under constraints and renders the Pareto front", async () => {
    const user = userEvent.setup();
    renderApp(<TeacherPage catalogue={catalogueFixture} />);

    await user.click(screen.getByRole("button", { name: /Re-solve under constraints/i }));

    expect(await screen.findByText("2 non-dominated")).toBeInTheDocument();
    // the selected path is inspected below the chart
    expect(await screen.findByText(/3 steps/)).toBeInTheDocument();
  });

  it("passes ban / force-order through to the request", async () => {
    let body: unknown;
    server.use(
      http.post("/recommend", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ paths: [], meta: { infeasible_reason: "banned everything" } });
      }),
    );
    const user = userEvent.setup();
    renderApp(<TeacherPage catalogue={catalogueFixture} />);

    const banGroup = screen.getByRole("group", { name: /Ban resources/i });
    await user.click(within(banGroup).getByRole("button", { name: "integers:lesson" }));
    await user.selectOptions(screen.getByLabelText("before"), "fractions");
    await user.selectOptions(screen.getByLabelText("after"), "linear_eq");
    await user.click(screen.getByRole("button", { name: /Re-solve under constraints/i }));

    await screen.findByText(/banned everything/i);
    expect(body).toMatchObject({
      ban: ["integers:lesson"],
      force_order: [["fractions", "linear_eq"]],
      mode: "pareto",
    });
  });

  it("shows the infeasible reason when no plan fits", async () => {
    server.use(
      http.post("/recommend", () =>
        HttpResponse.json({ paths: [], meta: { infeasible_reason: "budget too small" } }),
      ),
    );
    const user = userEvent.setup();
    renderApp(<TeacherPage catalogue={catalogueFixture} />);
    await user.click(screen.getByRole("button", { name: /Re-solve under constraints/i }));
    expect(await screen.findByText(/budget too small/i)).toBeInTheDocument();
  });

  it("reset clears the constraints", async () => {
    const user = userEvent.setup();
    renderApp(<TeacherPage catalogue={catalogueFixture} />);
    const lockGroup = screen.getByRole("group", { name: /Lock resources/i });
    await user.click(within(lockGroup).getByRole("button", { name: "fractions:lesson" }));
    expect(within(lockGroup).getByRole("button", { name: "fractions:lesson" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(screen.getByRole("button", { name: "Reset" }));
    expect(within(lockGroup).getByRole("button", { name: "fractions:lesson" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
