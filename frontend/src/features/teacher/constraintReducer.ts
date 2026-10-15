/** Teacher constraint builder state - a reducer so every edit is an explicit,
 *  testable action and the "re-solve" payload is derived in one place. */

export interface ConstraintState {
  goals: string[];
  budgetMin: number;
  ban: string[];
  lock: string[];
  before: string; // concept that must come first
  after: string; // ...before this one
  nPaths: number;
}

export type ConstraintAction =
  | { type: "setGoals"; goals: string[] }
  | { type: "setBudget"; minutes: number }
  | { type: "setBan"; ban: string[] }
  | { type: "setLock"; lock: string[] }
  | { type: "setForce"; before?: string; after?: string }
  | { type: "setNPaths"; n: number }
  | { type: "reset" };

export const initialConstraints: ConstraintState = {
  goals: [],
  budgetMin: 150,
  ban: [],
  lock: [],
  before: "",
  after: "",
  nPaths: 12,
};

export function constraintReducer(
  state: ConstraintState,
  action: ConstraintAction,
): ConstraintState {
  switch (action.type) {
    case "setGoals":
      return { ...state, goals: action.goals };
    case "setBudget":
      return { ...state, budgetMin: action.minutes };
    case "setBan":
      return { ...state, ban: action.ban };
    case "setLock":
      return { ...state, lock: action.lock };
    case "setForce":
      return {
        ...state,
        before: action.before ?? state.before,
        after: action.after ?? state.after,
      };
    case "setNPaths":
      return { ...state, nPaths: action.n };
    case "reset":
      return initialConstraints;
    default:
      return state;
  }
}

/** Turn the builder state into a `/recommend` request body. */
export function toRecommendInput(s: ConstraintState) {
  const force_order: [string, string][] =
    s.before && s.after && s.before !== s.after ? [[s.before, s.after]] : [];
  return {
    learner_id: "teacher",
    goals: s.goals,
    time_budget_min: s.budgetMin,
    mode: "pareto" as const,
    n_paths: s.nPaths,
    ban: s.ban,
    lock: s.lock,
    force_order,
  };
}
