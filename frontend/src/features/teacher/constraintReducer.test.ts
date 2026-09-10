import { describe, expect, it } from "vitest";

import {
  constraintReducer,
  initialConstraints,
  toRecommendInput,
} from "./constraintReducer";

describe("constraintReducer", () => {
  it("sets each field independently", () => {
    let s = constraintReducer(initialConstraints, { type: "setGoals", goals: ["quadratics"] });
    s = constraintReducer(s, { type: "setBudget", minutes: 200 });
    s = constraintReducer(s, { type: "setBan", ban: ["a:lesson"] });
    expect(s).toMatchObject({ goals: ["quadratics"], budgetMin: 200, ban: ["a:lesson"] });
  });

  it("merges the two halves of a force-order edge", () => {
    let s = constraintReducer(initialConstraints, { type: "setForce", before: "fractions" });
    expect(s.after).toBe("");
    s = constraintReducer(s, { type: "setForce", after: "linear_eq" });
    expect(s).toMatchObject({ before: "fractions", after: "linear_eq" });
  });

  it("reset returns the initial state", () => {
    const s = constraintReducer(
      { ...initialConstraints, goals: ["x"], budgetMin: 999 },
      { type: "reset" },
    );
    expect(s).toEqual(initialConstraints);
  });
});

describe("toRecommendInput", () => {
  it("emits a force_order pair only when both ends differ", () => {
    expect(toRecommendInput({ ...initialConstraints, before: "a", after: "a" }).force_order).toEqual(
      [],
    );
    expect(toRecommendInput({ ...initialConstraints, before: "a", after: "b" }).force_order).toEqual([
      ["a", "b"],
    ]);
  });

  it("always asks for the pareto front", () => {
    expect(toRecommendInput(initialConstraints).mode).toBe("pareto");
  });
});
