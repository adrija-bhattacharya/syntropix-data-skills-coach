import { useState } from "react";

import { useLearner } from "../context/LearnerContext";
import { useTrack } from "../context/TrackContext";
import { useLibrary } from "./queries";

export type Pace = "auto" | "deliberate" | "steady" | "fast";

export const PACE_LABEL: Record<string, string> = {
  auto: "Match my speed",
  deliberate: "Careful",
  steady: "Steady",
  fast: "Fast",
};

export const SKILL_NAME: Record<string, string> = {
  sql: "SQL",
  spreadsheets: "Excel",
  python: "Python",
  python_data: "pandas & NumPy",
  stats: "Statistics",
  dataviz: "Data visualisation",
  powerbi: "Power BI",
  tableau: "Tableau",
  data_eng: "Data engineering",
  git: "Git",
};

/** The current track's library, with a pace the learner can override. */
export function useTrackLibrary() {
  const { track } = useTrack();
  const { learnerId } = useLearner();
  const [pace, setPace] = useState<Pace>("auto");
  const q = useLibrary({
    goal: track.goal,
    learner_id: learnerId,
    speed: track.speed,
    pace,
    hours_per_week: track.hoursPerWeek,
  });
  return { q, pace, setPace, track };
}

export const embed = (videoId: string, start = 0) =>
  `https://www.youtube-nocookie.com/embed/${videoId}?rel=0&modestbranding=1${start > 0 ? `&start=${start}` : ""}`;

export const clock = (s: number) =>
  s >= 3600 ? `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

const SOURCE_WORD: Record<string, string> = { transcript: "what it says", description: "its description and chapters", title: "its title only" };

/** A plain-English line for a video's semantic check. */
export function checkLine(check: { level: string; source: string; judge: string; reason: string; coverage: string[] } | null, topics?: number): string | null {
  if (!check) return null;
  const by = check.judge === "claude" ? "an AI reviewer" : "Syntropix";
  if (check.level === "covers") return `Checked by ${by} from ${SOURCE_WORD[check.source] ?? check.source}: covers ${check.coverage.length}${topics ? ` of ${topics}` : ""} topic${check.coverage.length === 1 ? "" : "s"} in its chapters.`;
  if (check.level === "verified") return `Checked by ${by} from ${SOURCE_WORD[check.source] ?? check.source}: teaches this topic.`;
  if (check.level === "related") return `Checked by ${by} from ${SOURCE_WORD[check.source] ?? check.source}: related, not a perfect match.`;
  return null;
}

export const DIFF_TONE: Record<string, "tertiary" | "warn" | "error" | "neutral"> = {
  Easy: "tertiary",
  Medium: "warn",
  Hard: "error",
};
