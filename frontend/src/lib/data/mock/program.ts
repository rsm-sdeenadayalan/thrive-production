import type {
  PhaseId,
  PhaseStatus,
  ProgramPhase,
  ProgramTimeline,
  Track,
} from "../types";

/**
 * The MSBA program timeline.
 *
 * Nothing here is hardcoded about where the student *is*. Given a start date
 * and a track, the phases, the current phase, the finish line, and the percent
 * complete are all computed from today. Switching track moves the finish line
 * and therefore the percentage, with no other edit.
 */

/**
 * Quarter windows as [monthIndex, day], relative to the program's start year.
 * `yearOffset` is 0 for the first academic term and 1 for everything after
 * the new calendar year.
 */
interface PhaseSpec {
  id: PhaseId;
  label: string;
  season: string;
  start: [number, number];
  end: [number, number];
  yearOffset: 0 | 1;
  optional: boolean;
}

const PHASE_SPECS: PhaseSpec[] = [
  /*
   * The opening term. Its start is replaced by the real programStart below, so
   * it stretches back to whenever the student actually began.
   *
   * It carries a season now. It used to have none, which fell through to a
   * month-year term ("August 2026") and left one segment of the timeline named
   * differently from the other five. Orientation is folded into this term
   * rather than standing alone: it is the first weeks of Summer, not a seventh
   * phase, and naming it after the quarter keeps the six segments reading as
   * one sequence of terms.
   */
  {
    id: "orientation",
    label: "Summer Quarter",
    season: "Summer",
    start: [8, 22],
    end: [9, 1],
    yearOffset: 0,
    optional: false,
  },
  {
    id: "fall",
    label: "Fall Quarter",
    season: "Fall",
    start: [9, 2],
    end: [11, 12],
    yearOffset: 0,
    optional: false,
  },
  {
    id: "winter",
    label: "Winter Quarter",
    season: "Winter",
    start: [0, 5],
    end: [2, 20],
    yearOffset: 1,
    optional: false,
  },
  {
    id: "spring",
    label: "Spring Quarter",
    season: "Spring",
    start: [2, 30],
    end: [5, 12],
    yearOffset: 1,
    optional: false,
  },
  {
    id: "summer",
    label: "Summer Quarter",
    season: "Summer",
    start: [5, 22],
    end: [7, 28],
    yearOffset: 1,
    optional: false,
  },
  {
    id: "optional-fall",
    label: "Optional Fall Quarter",
    season: "Fall",
    start: [8, 21],
    end: [11, 11],
    yearOffset: 1,
    optional: true,
  },
];

/**
 * Which phase each track finishes on. This is the only place the two tracks
 * differ, and it is what makes the finish line derived rather than stored.
 */
const FINAL_PHASE: Record<Track, PhaseId> = {
  "11 month": "summer",
  "17 month": "optional-fall",
};

/** Local-midnight Date from "YYYY-MM-DD". Built from parts: see `dayKeyOf`. */
function parseDay(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function toISODate(date: Date): string {
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/**
 * Build the timeline for a start date and track.
 *
 * Pure and fully parameterised, including `now`, so the same inputs always
 * give the same answer and both tracks can be checked side by side.
 */
export function buildProgramTimeline(
  programStart: string,
  track: Track,
  now: Date = new Date(),
): ProgramTimeline {
  const startDate = parseDay(programStart);
  const startYear = startDate.getFullYear();

  const dated = PHASE_SPECS.map((spec) => {
    const year = startYear + spec.yearOffset;
    const start =
      spec.id === "orientation"
        ? startDate
        : new Date(year, spec.start[0], spec.start[1]);
    const end = new Date(year, spec.end[0], spec.end[1]);

    return {
      spec,
      start,
      end,
      term: spec.season
        ? `${spec.season} ${year}`
        : start.toLocaleDateString("en-US", { month: "long", year: "numeric" }),
    };
  });

  const finalId = FINAL_PHASE[track];
  const finalPhase = dated.find((p) => p.spec.id === finalId)!;
  const programEnd = finalPhase.end;

  const today = new Date(now);
  today.setHours(0, 0, 0, 0);

  const phases: ProgramPhase[] = dated.map((p) => {
    let status: PhaseStatus;
    if (today > p.end) status = "complete";
    else if (today >= p.start) status = "current";
    else status = "upcoming";

    return {
      id: p.spec.id,
      label: p.spec.label,
      term: p.term,
      start: toISODate(p.start),
      end: toISODate(p.end),
      // A phase is optional when this track does not require it. On the 17
      // month track the final Fall is required, so the tag disappears.
      optional: p.spec.optional && p.spec.id !== finalId,
      status,
    };
  });

  const current = phases.find((phase) => phase.status === "current") ?? null;

  const totalMs = programEnd.getTime() - startDate.getTime();
  const elapsedMs = today.getTime() - startDate.getTime();
  const percentComplete =
    totalMs <= 0
      ? 0
      : Math.max(0, Math.min(100, Math.round((elapsedMs / totalMs) * 100)));

  return {
    phases,
    currentPhaseId: current?.id ?? null,
    percentComplete,
    programStart: toISODate(startDate),
    programEnd: toISODate(programEnd),
    expectedFinishTerm: finalPhase.term,
    track,
  };
}
