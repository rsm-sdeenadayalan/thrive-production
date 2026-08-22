import type { EventType, Task } from "$lib/data";
// Type-only, so it is erased at build and this module stays usable from the
// server despite `quickList` being a client module.
import type { QuickItem } from "$lib/quickList";
/*
 * Also type-only, and also erased -- which is what makes it safe despite
 * `calendarItems` importing back from here. A value import either way round
 * would be a real cycle and would drag a store into a server-rendered module;
 * this one leaves nothing behind at build time.
 *
 * The local name shadows the DOM's `CustomEvent` inside this file. Deliberate:
 * nothing in `schedule.ts` touches a DOM event, and renaming the domain type to
 * avoid a global it never meets would be the wrong thing to bend.
 */
import type { CustomEvent } from "$lib/calendarItems";

/**
 * The merge layer behind the mini calendar.
 *
 * Nothing here invents a data source. The page loads courses, assignments,
 * events, and appointments through the existing providers and flattens them
 * into one shape; this module owns that shape and the rules for combining it.
 *
 * Dated items arrive pre-formatted from the server. Recurring class meetings
 * arrive as weekday plus wall-clock time and are expanded on the client, so
 * navigating to any month works without another round trip.
 */

/** What a dot or tag stands for. Events keep their own type. */
export type ScheduleCategory =
  | "class"
  | "assignment"
  | "task"
  | "appointment"
  | "todo"
  | "custom"
  | EventType;

/**
 * Category colors.
 *
 * Coral is deliberately absent. It is reserved for overdue and urgent across
 * the rest of THRIVE, and a month grid dotted coral on every assignment day
 * would drain that meaning. Assignments take amber instead, which already
 * means "due soon" on a DueChip.
 *
 * This is the one place hues are used categorically rather than as status.
 * Eight distinct dots is more than the reserved palette supplies, which is why
 * the categorical `civic` plum and the neutral `later` slate exist. Every dot
 * is paired with a written label in the legend and in the day list, so no
 * meaning here rests on colour alone.
 *
 * The old map used two blues for appointment and career, which stopped reading
 * apart at dot size; appointment now takes the sage accent.
 */
export const categoryDot: Record<ScheduleCategory, string> = {
  class: "bg-ink",
  assignment: "bg-watch",
  // A task and an assignment are the same kind of thing to a student -- work
  // with a deadline -- so they share amber rather than spending a ninth hue.
  // The label distinguishes them where it matters.
  task: "bg-watch",
  appointment: "bg-primary",
  // To-dos are the student's own scratch items. Neutral slate on purpose: they
  // are not a status and they are not program-issued.
  todo: "bg-later",
  // Student-created. Indigo is RESERVED for "you are here", so custom takes
  // the neutral muted grey: it is the student's own note, not programme truth.
  custom: "bg-muted-ink",
  career: "bg-on-track",
  rady: "bg-needs-help",
  club: "bg-civic",
  sandiego: "bg-later",
  ucsd: "bg-muted-ink",
};

/**
 * Tag styling for the day list, where there is room for a label.
 *
 * Solid fills with white text, matching `Tag`. The previous tint-on-tint set
 * put `sandiego` at 4.24:1 -- under AA for label text -- and read faint beside
 * the heavier borders and type this pass introduced. Every pairing below was
 * measured: watch 5.34, primary 5.72, on-track 5.12, needs-help 5.42,
 * civic 5.10, later 4.76. `class` and `ucsd` stay neutral on purpose, so the
 * two most common categories do not make every row shout.
 */
export const categoryTag: Record<ScheduleCategory, string> = {
  class: "bg-ink text-surface",
  assignment: "bg-watch text-white",
  task: "bg-watch text-white",
  appointment: "bg-primary text-on-primary",
  todo: "bg-later text-white",
  custom: "bg-muted-ink text-white",
  career: "bg-on-track text-white",
  rady: "bg-needs-help text-white",
  club: "bg-civic text-white",
  sandiego: "bg-later text-white",
  ucsd: "bg-surface text-body border border-line",
};

export const categoryLabel: Record<ScheduleCategory, string> = {
  class: "Class",
  assignment: "Assignment",
  task: "Task",
  appointment: "Appointment",
  todo: "To-do",
  custom: "Mine",
  career: "Career",
  rady: "Rady",
  club: "Club",
  sandiego: "San Diego",
  ucsd: "UCSD",
};

/** Legend and filter order: commitments, then personal, then event origins. */
export const legendOrder: ScheduleCategory[] = [
  "class",
  "assignment",
  "appointment",
  "task",
  "todo",
  "custom",
  "career",
  "rady",
  "club",
  "sandiego",
  "ucsd",
];

export interface ScheduleItem {
  id: string;
  category: ScheduleCategory;
  title: string;
  /** "9:30 AM", or "All day". */
  timeLabel: string;
  /** Location, meeting mode, or course code. May be empty. */
  detail: string;
  /** Minutes past midnight, for sorting. Ignored when allDay. */
  sortMinutes: number;
  allDay: boolean;
  /** ISO bounds, on dated items only. Used to build an .ics file. */
  startISO?: string;
  endISO?: string;
  /** Events only: matches the student's stated goal. */
  relevantToGoal?: boolean;
  /** Events only: longer blurb for the register card. */
  description?: string;
  /** Tasks and to-dos only. Absent means "not a tickable thing". */
  done?: boolean;
  /** Tasks only. Drives the priority eyebrow, never a colour on its own. */
  priority?: "low" | "medium" | "high";
  /** Tasks only, when the task came from a course. Used by group-by-course. */
  courseCode?: string;
  /** Free-text label the student attached. Also a filter dimension. */
  label?: string;
  /** Student-flagged "act now". Reserved coral, and suppressed once done. */
  urgent?: boolean;
  /** True when the student created this item themselves. */
  custom?: boolean;
  /**
   * The row this item was built from, attached at merge time.
   *
   * Exactly one of these is present on a tickable row, and neither is present
   * on anything else. Carrying the resolved object means writing a tick back
   * needs no lookup and no id parsing: `tickItem` reads whichever one is here
   * and calls the matching store.
   *
   * The previous design sliced a prefix off `id` and searched an array, which
   * silently missed every task the student had added themselves (those live in
   * `addedStore`, not in the server's rows) and every undated to-do in the
   * agenda (whose synthetic item id was never prefixed at all). Both failed
   * the same way: the guard found nothing and returned, so the checkbox
   * appeared to tick and reverted on the next render.
   */
  task?: Task;
  quickItem?: QuickItem;
  /**
   * The custom event this row was built from, attached the same way and for the
   * same reason as the two above.
   *
   * Not a tickable source -- `isTickable` asks only about `task` and
   * `quickItem`, and a student-created event is a thing that happens rather than
   * a thing you complete. This one exists so DELETING it does not have to parse
   * `custom-` off the front of an id, which is doubly hazardous here because the
   * prefix genuinely appears twice.
   */
  customEvent?: CustomEvent;
}

/**
 * The three groups the Calendar page renders as separate sections.
 *
 * "Your schedule" is what the student is already committed to and cannot
 * simply decide not to do. "Your list" is what they set themselves -- tasks
 * and scratch to-dos, both tickable. "Happening" is what they could opt into.
 *
 * Splitting on category here means no section has to know another's rules.
 */
export const SCHEDULE_CATEGORIES: ScheduleCategory[] = [
  "class",
  "assignment",
  "appointment",
];

/**
 * Tickable, student-owned, and NOT on the server in the same way the rest is:
 * task due dates can be overridden client-side and to-dos live only in
 * localStorage. See `calendarSources.ts` for why that matters.
 */
export const PERSONAL_CATEGORIES: ScheduleCategory[] = [
  "task",
  "todo",
  "custom",
];

export const EVENT_CATEGORIES: ScheduleCategory[] = [
  "career",
  "rady",
  "club",
  "sandiego",
  "ucsd",
];

export function isEventCategory(category: ScheduleCategory): boolean {
  return EVENT_CATEGORIES.includes(category);
}

export function isPersonalCategory(category: ScheduleCategory): boolean {
  return PERSONAL_CATEGORIES.includes(category);
}

export function isCommitmentCategory(category: ScheduleCategory): boolean {
  return SCHEDULE_CATEGORIES.includes(category);
}

/** A dated item, already pinned to one calendar day by the server. */
export interface DatedScheduleItem extends ScheduleItem {
  /** Local calendar day, "YYYY-MM-DD". */
  dayKey: string;
}

/** A class meeting, expanded onto whichever days the calendar shows. */
export interface RecurringMeeting {
  id: string;
  /** 0 = Sunday ... 6 = Saturday. */
  dayOfWeek: number;
  title: string;
  detail: string;
  /** Wall clock "HH:mm" -- no timezone, so expanding it is safe anywhere. */
  startTime: string;
  timeLabel: string;
}

export interface ScheduleData {
  dated: DatedScheduleItem[];
  recurring: RecurringMeeting[];
}

// ---------------------------------------------------------------------------
// Day keys and month math
// ---------------------------------------------------------------------------

/** "YYYY-MM-DD" from local date parts. */
export function toDayKey(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/**
 * A local calendar day key, "YYYY-MM-DD", from either a Date or an ISO string.
 *
 * THE ONE COLLAPSE IN THE SVELTEKIT PORT. This absorbed `localDayKey(iso)`
 * from `format.ts`, which produced the identical string from the identical
 * local parts and differed only in what it accepted. Two functions computing
 * one string is how the two of them eventually disagree about a timezone edge,
 * so the local-parts rule now lives in exactly one place.
 *
 * The union is what lets both original call sites stay clean: `dayKeyOf(new
 * Date())` for the clock, `dayKeyOf(assignment.dueDate)` for a stored instant,
 * with no caller wrapping a string in a Date just to satisfy a signature.
 *
 * Built from local parts on purpose. `toISOString().slice(0, 10)` would shift
 * an evening appointment onto the next day in any timezone behind UTC.
 */
export function dayKeyOf(value: Date | string): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return toDayKey(date.getFullYear(), date.getMonth(), date.getDate());
}

/**
 * Parse a day key back into a local Date at midnight.
 *
 * `new Date("2026-08-17")` would parse as UTC and land on the 16th in any
 * timezone behind it, so the parts are passed to the constructor instead.
 */
export function fromDayKey(key: string): Date {
  const [year, month, day] = key.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function addDays(key: string, days: number): string {
  const date = fromDayKey(key);
  date.setDate(date.getDate() + days);
  return dayKeyOf(date);
}

export function minutesOf(hhmm: string): number {
  const [hour, minute] = hhmm.split(":").map(Number);
  return hour * 60 + minute;
}

/** "9:30 AM" from a wall-clock "HH:mm". No timezone involved. */
export function wallClockLabel(hhmm: string): string {
  const [hour, minute] = hhmm.split(":").map(Number);
  const suffix = hour < 12 ? "AM" : "PM";
  const display = hour % 12 === 0 ? 12 : hour % 12;
  return `${display}:${String(minute).padStart(2, "0")} ${suffix}`;
}

// ---------------------------------------------------------------------------
// The merge
// ---------------------------------------------------------------------------

/**
 * Everything happening on one day, all-day items first and then by time.
 *
 * Recurring meetings are expanded here rather than pre-generated, which is
 * what lets the calendar move to any month without asking the server again.
 */
export function itemsForDay(
  data: ScheduleData,
  dayKey: string,
): ScheduleItem[] {
  const weekday = fromDayKey(dayKey).getDay();

  const classes: ScheduleItem[] = data.recurring
    .filter((meeting) => meeting.dayOfWeek === weekday)
    .map((meeting) => ({
      id: `${meeting.id}-${dayKey}`,
      category: "class" as const,
      title: meeting.title,
      timeLabel: meeting.timeLabel,
      detail: meeting.detail,
      sortMinutes: minutesOf(meeting.startTime),
      allDay: false,
    }));

  const dated = data.dated.filter((item) => item.dayKey === dayKey);

  return [...classes, ...dated].sort((a, b) => {
    if (a.allDay !== b.allDay) return a.allDay ? -1 : 1;
    if (a.sortMinutes !== b.sortMinutes) return a.sortMinutes - b.sortMinutes;
    return a.title.localeCompare(b.title);
  });
}

/**
 * A day's commitments: classes, work due, and booked appointments.
 *
 * Assignments are included even though they are deadlines rather than
 * meetings. Leaving them out would put a dot on the month calendar with no
 * corresponding row underneath it, which reads as a bug.
 */
export function scheduleItemsForDay(
  data: ScheduleData,
  dayKey: string,
): ScheduleItem[] {
  return itemsForDay(data, dayKey).filter((item) =>
    isCommitmentCategory(item.category),
  );
}

/** A day's tickable, student-owned items: tasks and scratch to-dos. */
export function personalItemsForDay(
  data: ScheduleData,
  dayKey: string,
): ScheduleItem[] {
  return itemsForDay(data, dayKey).filter((item) =>
    isPersonalCategory(item.category),
  );
}

/** A day's optional, registerable events. */
export function eventItemsForDay(
  data: ScheduleData,
  dayKey: string,
): ScheduleItem[] {
  return itemsForDay(data, dayKey).filter((item) =>
    isEventCategory(item.category),
  );
}

/**
 * Distinct categories on a day, in legend order, for the dots. Order is fixed
 * rather than by time so a day's dots don't reshuffle as items are added.
 */
export function categoriesForDay(
  data: ScheduleData,
  dayKey: string,
): ScheduleCategory[] {
  const present = new Set(
    itemsForDay(data, dayKey).map((item) => item.category),
  );
  return legendOrder.filter((category) => present.has(category));
}

/** The 6-week grid a month is drawn on, starting Sunday. */
export function monthGrid(year: number, month: number): string[] {
  const first = new Date(year, month, 1);
  const start = new Date(first);
  start.setDate(start.getDate() - first.getDay());

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start);
    date.setDate(date.getDate() + index);
    return dayKeyOf(date);
  });
}

/** The seven day keys of the week containing `dayKey`, starting Sunday. */
export function weekGrid(dayKey: string): string[] {
  const date = fromDayKey(dayKey);
  const sunday = new Date(date);
  sunday.setDate(sunday.getDate() - date.getDay());

  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(sunday);
    day.setDate(day.getDate() + index);
    return dayKeyOf(day);
  });
}

// ---------------------------------------------------------------------------
// Filtering, next-up, grouping
//
// All pure and all exported, because they are the parts most worth testing and
// the parts most likely to quietly disagree with each other. The rule that
// matters: the month dots and the day lists must be filtered by the SAME
// function, or the grid will promise something the list does not deliver.
// ---------------------------------------------------------------------------

export interface ScheduleFilter {
  /** Categories the student has switched off. */
  hidden: readonly ScheduleCategory[];
  /** Labels the student has switched off. */
  hiddenLabels?: readonly string[];
  /** When false, ticked tasks and to-dos disappear from dots and lists alike. */
  showDone: boolean;
  /** When true, only items flagged urgent survive. */
  urgentOnly?: boolean;
  /**
   * Raw `Event.id`s the student has ignored, and whether to show them anyway.
   *
   * Applied ONLY to event categories. An ignored id can never hide a class, an
   * assignment, an appointment, a task or a to-do, because those are things the
   * student is committed to rather than things they opted into.
   */
  ignoredEventIds?: readonly string[];
  showIgnored?: boolean;
}

export const ALL_VISIBLE: ScheduleFilter = { hidden: [], showDone: false };

export function isVisible(
  item: ScheduleItem,
  filter: ScheduleFilter,
): boolean {
  if (filter.hidden.includes(item.category)) return false;
  // `done` is only present on tickable items, so a class is never hidden by it.
  if (!filter.showDone && item.done === true) return false;
  if (filter.urgentOnly && item.urgent !== true) return false;
  /*
   * Ignored events, hidden unless asked for.
   *
   * The `isEventCategory` guard is load-bearing, not defensive: without it a
   * stale or hand-edited id in the store could hide a class. Only opt-in events
   * are ever eligible.
   */
  if (
    !filter.showIgnored &&
    isEventCategory(item.category) &&
    filter.ignoredEventIds?.includes(item.id.replace(/^evt-/, ""))
  ) {
    return false;
  }
  // Only labelled items can be hidden by a label. An unlabelled row is never
  // caught by a label filter -- it has nothing to match on, and hiding it would
  // make "filter by label" silently mean "hide everything else".
  if (item.label && filter.hiddenLabels?.includes(item.label)) return false;
  return true;
}

/** Every distinct label in use, sorted, for the key to render. */
export function allLabels(data: ScheduleData): string[] {
  return [
    ...new Set(
      data.dated
        .map((item) => item.label)
        .filter((label): label is string => Boolean(label)),
    ),
  ].sort();
}

/**
 * Apply a filter to whole `ScheduleData`, so every consumer sees one truth.
 *
 * Recurring classes need their own branch because they are not `ScheduleItem`s
 * yet -- they are weekday rules expanded later. Two things drop them:
 *
 *   - `class` being hidden, obviously
 *   - `urgentOnly`, because a class can never carry an urgent flag. Without
 *     this, "urgent only" left every class on screen and read as broken.
 */
export function filterSchedule(
  data: ScheduleData,
  filter: ScheduleFilter,
): ScheduleData {
  const dropClasses = filter.hidden.includes("class") || filter.urgentOnly;

  return {
    dated: data.dated.filter((item) => isVisible(item, filter)),
    recurring: dropClasses ? [] : data.recurring,
  };
}

/**
 * The next thing coming up on a day, for the header's "next up:" line.
 *
 * Skips anything already ticked and anything all-day -- "next up: All day" is
 * not information. Returns null on an empty or fully-past day rather than
 * inventing something, so the header can simply omit the line.
 *
 * `nowMinutes` is passed in rather than read from a clock, so this is testable
 * and so the caller decides what "now" means. On a day that is not today the
 * caller should pass 0, which yields the first timed item.
 */
export function nextUpItem(
  items: ScheduleItem[],
  nowMinutes: number,
): ScheduleItem | null {
  const upcoming = items
    .filter((item) => !item.allDay && item.done !== true)
    .filter((item) => item.sortMinutes >= nowMinutes)
    .sort((a, b) => a.sortMinutes - b.sortMinutes);

  return upcoming[0] ?? null;
}

export type GroupMode = "day" | "category" | "course";

/** How the selected day's non-event items are arranged. */
export type DayGroupMode = "time" | "type";

/**
 * The day's type groups, in the order a student actually plans against.
 *
 * Not `legendOrder`. That list is for the filter row, where categories are
 * grouped by where they come from. This one is ordered by *kind of
 * obligation*, which is the order the day gets planned in:
 *
 *   what I have to attend  ->  what is due  ->  what I set myself  ->  booked time
 *
 * Events are deliberately absent. They keep their own section with register
 * buttons, a description and the "for you" badge; folding them into a generic
 * group would throw all of that away to gain consistency nobody asked for.
 */
export const DAY_GROUPS: { key: string; heading: string; categories: ScheduleCategory[] }[] = [
  { key: "classes", heading: "Classes", categories: ["class"] },
  { key: "due", heading: "Assignments due", categories: ["assignment"] },
  { key: "tasks", heading: "Tasks", categories: ["task"] },
  { key: "todos", heading: "To-dos", categories: ["todo"] },
  { key: "mine", heading: "Added by you", categories: ["custom"] },
  { key: "appointments", heading: "Appointments", categories: ["appointment"] },
];

/**
 * Split a day's non-event items into the fixed type groups.
 *
 * Empty groups are dropped rather than rendered as headings over nothing: a day
 * with no appointments should not have to say so five times.
 */
export function groupDayItems(items: ScheduleItem[]): AgendaGroup[] {
  return DAY_GROUPS.map((group) => ({
    key: group.key,
    heading: group.heading,
    items: items.filter((item) =>
      group.categories.includes(item.category),
    ) as DatedScheduleItem[],
  })).filter((group) => group.items.length > 0);
}

export interface AgendaGroup {
  key: string;
  heading: string;
  items: DatedScheduleItem[];
}

/**
 * Flatten a date range into grouped rows for the agenda view.
 *
 * Recurring classes are expanded across the range here, the same way
 * `itemsForDay` expands them for one day, so the agenda cannot silently omit
 * the thing a student attends most often.
 */
export function groupAgenda(
  data: ScheduleData,
  dayKeys: string[],
  mode: GroupMode,
): AgendaGroup[] {
  const rows: DatedScheduleItem[] = dayKeys.flatMap((dayKey) =>
    itemsForDay(data, dayKey).map((item) => ({ ...item, dayKey })),
  );

  if (mode === "day") {
    return dayKeys
      .map((dayKey) => ({
        key: dayKey,
        heading: fromDayKey(dayKey).toLocaleDateString("en-US", {
          weekday: "long",
          month: "long",
          day: "numeric",
        }),
        items: rows.filter((row) => row.dayKey === dayKey),
      }))
      .filter((group) => group.items.length > 0);
  }

  if (mode === "category") {
    return legendOrder
      .map((category) => ({
        key: category,
        heading: categoryLabel[category],
        items: rows.filter((row) => row.category === category),
      }))
      .filter((group) => group.items.length > 0);
  }

  // Group by course. Anything with no course -- events, appointments, scratch
  // to-dos -- lands in one bucket, sorted last rather than dropped.
  const courses = [
    ...new Set(rows.map((row) => row.courseCode ?? "").filter(Boolean)),
  ].sort();

  const grouped = courses.map((code) => ({
    key: code,
    heading: code,
    items: rows.filter((row) => row.courseCode === code),
  }));

  const rest = rows.filter((row) => !row.courseCode);
  if (rest.length > 0) {
    grouped.push({ key: "__none", heading: "No course", items: rest });
  }

  return grouped;
}
