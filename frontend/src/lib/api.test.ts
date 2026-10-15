import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { ApiError, api } from "./api";

describe("api client", () => {
  it("parses and returns a valid catalogue", async () => {
    const cat = await api.catalogue();
    expect(cat.concepts.length).toBeGreaterThan(0);
    expect(cat.goals).toContain("quadratics");
  });

  it("throws ApiError with the server detail on a 4xx", async () => {
    await expect(
      api.recommend({ learner_id: "u", goals: ["__boom__"], time_budget_min: 60 }),
    ).rejects.toMatchObject({ name: "ApiError", status: 422 });
  });

  it("throws a schema ApiError when the shape is wrong", async () => {
    server.use(http.get("/catalogue", () => HttpResponse.json({ concepts: "nope" })));
    await expect(api.catalogue()).rejects.toBeInstanceOf(ApiError);
  });

  it("reports an unreachable API", async () => {
    server.use(http.get("/catalogue", () => HttpResponse.error()));
    await expect(api.catalogue()).rejects.toMatchObject({ status: 0 });
  });
});
