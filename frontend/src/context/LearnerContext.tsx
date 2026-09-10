import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/**
 * The learner identity is shared state: the "get a path" form and the "log an
 * attempt" panel must target the same learner, and it should survive a reload
 * and a route change.
 */
interface LearnerCtx {
  learnerId: string;
  setLearnerId: (id: string) => void;
}
const Ctx = createContext<LearnerCtx | null>(null);
const KEY = "velpo-learner-id";

export function LearnerProvider({ children }: { children: ReactNode }) {
  const [learnerId, setLearnerId] = useState<string>(() => {
    try {
      return localStorage.getItem(KEY) || "demo";
    } catch {
      return "demo";
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(KEY, learnerId);
    } catch {
      /* ignore */
    }
  }, [learnerId]);

  const value = useMemo<LearnerCtx>(() => ({ learnerId, setLearnerId }), [learnerId]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLearner(): LearnerCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLearner must be used inside <LearnerProvider>");
  return ctx;
}
