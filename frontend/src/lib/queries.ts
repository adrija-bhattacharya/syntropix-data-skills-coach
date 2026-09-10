/** TanStack Query hooks - the only place components touch the network. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ObserveInput, type RecommendInput } from "./api";

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
