import type { Student } from "../types";

export const mockStudent: Student = {
  id: "stu-001",
  name: "Merna",
  goal: "Data Scientist",
  track: "17 month",
  program: "MSBA",
  standing: "onTrack",
  standingSummary:
    "On pace overall. Data Visualization has slipped and is worth your attention this week.",
  currentTerm: "Fall 2026",
  /*
   * Start date, not finish date: the finish term and the percentage are both
   * derived from this plus `track` (see mock/program.ts), so neither is stored
   * anywhere and switching track moves both with no other edit.
   *
   * Why early August. The optional Fall sits at `yearOffset: 1`, so a Fall 2027
   * finish pins the start year to 2026. Every other phase window is a fixed
   * quarter date, and none of them contains mid-August -- only Orientation can,
   * because its start is the one the program start replaces. That is also the
   * honest answer: 17 months ending December 2027 begins around now, so Merna
   * is at the very start of the program rather than the end of it.
   */
  programStart: "2026-08-03",
  consent: {
    calendarRead: true,
    lmsRead: true,
    careerRecommendations: true,
    advisorSharing: false,
  },
};
