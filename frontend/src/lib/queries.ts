/** TanStack Query hooks - the only place components touch the network. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  api,
  type AssessState,
  type Band,
  type ObserveInput,
  type RecommendInput,
} from "./api";

export const keys = {
  catalogue: ["catalogue"] as const,
  recommend: (input: RecommendInput) => ["recommend", input] as const,
};

export function useCatalogue() {
  return useQuery({
    queryKey: keys.catalogue,
    queryFn: api.catalogue,
    staleTime: Infinity, // the curriculum doesn't change under us
  });
}

/**
 * `recommend` is a *query* keyed by its full input: identical requests are
 * cached and de-duped, and the previous plan stays on screen (via
 * `placeholderData`) while a changed input refetches.  `enabled` gates it on a
 * goal being chosen.
 */
export function useRecommend(input: RecommendInput, enabled: boolean) {
  return useQuery({
    queryKey: keys.recommend(input),
    queryFn: () => api.recommend(input),
    enabled: enabled && input.goals.length > 0,
    placeholderData: (prev) => prev,
  });
}

export function useObserve(learnerId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Omit<ObserveInput, "learner_id">) =>
      api.observe({ ...input, learner_id: learnerId }),
    onSuccess: () => {
      // the learner model moved -> every cached recommendation is now stale
      void qc.invalidateQueries({ queryKey: ["recommend"] });
    },
  });
}

export function useExplain() {
  return useMutation({
    mutationFn: ({ learnerId, resourceId }: { learnerId: string; resourceId: string }) =>
      api.explain(learnerId, resourceId),
  });
}

export function useResolve(goal: string) {
  return useQuery({
    queryKey: ["resolve", goal] as const,
    queryFn: () => api.resolve(goal),
    enabled: goal.trim().length > 1,
    staleTime: Infinity,
    retry: 0,
  });
}

export function useDiscover(conceptId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["discover", conceptId] as const,
    queryFn: () => api.discover(conceptId),
    enabled: enabled && conceptId.length > 0,
    staleTime: Infinity,
  });
}

/** Drives the adaptive diagnostic: `start` seeds it, `answer` advances it,
 *  and the running `state` (question + per-skill estimates) is kept locally. */
export function useAssessment(learnerId: string) {
  const qc = useQueryClient();
  const start = useMutation({
    mutationFn: ({ goals, band, goal }: { goals: string[]; band: Band; goal?: string }) =>
      api.assessStart(learnerId, goals, band, goal),
  });
  const answer = useMutation({
    mutationFn: ({ itemId, response }: { itemId: string; response: string }) =>
      api.assessAnswer(learnerId, itemId, response),
    onSuccess: (s: AssessState) => {
      if (s.done) void qc.invalidateQueries({ queryKey: ["recommend"] });
    },
  });
  return { start, answer };
}
