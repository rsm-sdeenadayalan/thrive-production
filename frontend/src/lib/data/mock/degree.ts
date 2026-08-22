import type { DegreeProgress } from "../types";

/**
 * Degree audit numbers.
 *
 * There is deliberately no `expectedCompletion` here. The Next fixture carried
 * a hardcoded "Spring 2027" while `buildProgramTimeline` derived Fall 2027 for
 * the same student -- two answers to one question, with nothing on screen to
 * reveal the disagreement because the field rendered nowhere. See MIGRATION.md
 * section 9 defect 9. The finish term is derived: read
 * `ProgramTimeline.expectedFinishTerm`.
 */
export const mockDegreeProgress: DegreeProgress = {
  unitsCompleted: 38,
  unitsRequired: 52,
  coreDone: 7,
  coreRequired: 9,
  electiveDone: 2,
  electiveRequired: 4,
  track: "11 month",
  gaps: [
    {
      id: "gap-001",
      label: "Two electives still unplanned",
      detail:
        "Fall registration opens soon. Two elective slots are open and neither is chosen yet.",
      severity: "watch",
    },
    {
      id: "gap-002",
      label: "Capstone deliverable not yet scheduled",
      detail:
        "The sponsor presentation date has not been confirmed with the team.",
      severity: "onTrack",
    },
  ],
};
