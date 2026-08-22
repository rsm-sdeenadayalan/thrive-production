import type { CourseMeeting, Standing } from "$lib/data";

/**
 * Formatting helpers shared across the UI.
 *
 * Anything time-aware here is called on the server and passed down as a
 * plain string. Computing "Good morning" inside a client component would
 * risk a hydration mismatch when the server and browser disagree about the
 * hour, and it would freeze at whatever the bundle was built with.
 */

/** "Good morning" / "Good afternoon" / "Good evening" for a given moment. */
export function greetingFor(date: Date = new Date()): string {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/** "Monday, August 11" */
export function formatLongDate(date: Date = new Date()): string {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

/** "Aug 11" */
export function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

/**
 * "Tue, Aug 12"
 *
 * `formatShortDate`'s sibling, with the weekday. A booking is a commitment to
 * be somewhere at an hour, and a student reads the weekday to know whether that
 * collides with a class -- "Aug 12" alone does not answer that.
 */
export function formatWeekdayDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

/** "9:30 AM" */
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Avatar initials: "Amber Hanna" -> "AH", "Merna" -> "M".
 *
 * A single name yields a single letter rather than its first two, because
 * "Merna" would otherwise render as "ME" -- which reads as the word "me" in a
 * circle instead of as initials.
 */
export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

/** Human-readable label for a status value. */
export const standingLabel: Record<Standing, string> = {
  onTrack: "On track",
  watch: "Watch",
  needsHelp: "Needs help",
};

// ---------------------------------------------------------------------------
// Due dates
// ---------------------------------------------------------------------------

/**
 * How urgent a REAL deadline is. Three values, because a date that exists is
 * always one of these three things relative to today.
 *
 * Deliberately does not include the unparseable case. "How urgent is it" has no
 * answer for a date that does not exist, and folding one in here would make
 * every `Record<DueUrgency, Tone>` map in the UI owe a colour to a non-status.
 * That case is a separate variant of the descriptor instead -- see below.
 */
export type DueUrgency = "overdue" | "today" | "upcoming";

/** What every descriptor carries, whether or not the date parsed. */
interface DueDescriptorShared {
  /** Short human label, e.g. "Overdue", "Today", "Fri". */
  label: string;
  /**
   * Friendly relative timer: "in 3 days", "tomorrow", "2 days ago".
   *
   * Deliberately words rather than a signed number -- "-84d" is a diff, not
   * something a student reads at a glance.
   */
  countdown: string;
  /** Full text for tooltips and screen readers. */
  fullLabel: string;
}

/** A due date that parsed, reduced to what the UI actually renders. */
export interface KnownDueDescriptor extends DueDescriptorShared {
  urgency: DueUrgency;
  /** Whole calendar days from now. Negative once overdue. */
  days: number;
}

/**
 * A due date that did not parse.
 *
 * `days` is `null` rather than `NaN` on purpose. NaN is a number as far as the
 * type system is concerned, so it flows into `a.days - b.days` and into
 * `days <= 7` and quietly poisons both; null does not typecheck there at all,
 * which turns a silent runtime hole into a compile error the caller has to
 * answer for.
 */
export interface UnknownDueDescriptor extends DueDescriptorShared {
  urgency: "unknown";
  days: null;
}

/**
 * A due date reduced to what the UI actually renders.
 *
 * A discriminated union rather than one interface, so `urgency` is the single
 * thing a caller checks and narrowing on it is what unlocks `days`.
 */
export type DueDescriptor = KnownDueDescriptor | UnknownDueDescriptor;

/**
 * Whole days as a phrase a person would say.
 *
 * Weeks take over past a fortnight, because "in 34 days" is a number to be
 * decoded where "in 5 weeks" is a fact.
 */
function countdownPhrase(days: number): string {
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days === -1) return "yesterday";

  const magnitude = Math.abs(days);
  const amount =
    magnitude < 14
      ? `${magnitude} days`
      : magnitude < 60
        ? `${Math.round(magnitude / 7)} weeks`
        : `${Math.round(magnitude / 30)} months`;

  return days < 0 ? `${amount} ago` : `in ${amount}`;
}

/** Whole days between two dates, ignoring the time of day. */
function calendarDaysBetween(from: Date, to: Date): number {
  const a = new Date(from);
  const b = new Date(to);
  a.setHours(0, 0, 0, 0);
  b.setHours(0, 0, 0, 0);
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
}

/**
 * Classify and label a due date.
 *
 * Call this on the server and pass the result into client components. If a
 * client computed it, a browser in a different timezone from the server could
 * disagree about what "today" is and blow up hydration -- and the answer would
 * then be frozen at whatever moment the component last rendered.
 */
export function describeDue(
  iso: string,
  now: Date = new Date(),
): DueDescriptor {
  const due = new Date(iso);

  /*
   * An unparseable date is its own outcome, not a deadline.
   *
   * Without this guard every NaN comparison below is false, so a broken date
   * fell past `days < 0`, `days === 0` and `days === 1` into the final branch
   * and came back as `upcoming` -- carrying the literal strings "Invalid Date"
   * and "in NaN months" into the UI. Worse than the strings: `upcoming` meant
   * it never appeared in the overdue group, so a student never saw the deadline
   * at all. Invisible is worse than wrong.
   *
   * Every sibling mapper already guards this way -- `taskToItem`, `todoToItem`
   * and `customEventToItem` all test `Number.isNaN(date.getTime())` and return
   * null. This function was the exception. It cannot return null, because a
   * descriptor is what the row renders from, so it returns the fourth state.
   */
  if (Number.isNaN(due.getTime())) {
    return {
      urgency: "unknown",
      label: "No date",
      countdown: "",
      days: null,
      fullLabel: "Due date unavailable",
    };
  }

  const days = calendarDaysBetween(now, due);

  const fullLabel = due.toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
  });

  const countdown = countdownPhrase(days);

  // "Overdue" alone, now that the countdown carries the number -- the old
  // label said "Overdue by 3 days" right next to "3 days ago".
  if (days < 0) {
    return {
      urgency: "overdue",
      label: "Overdue",
      countdown,
      days,
      fullLabel: `Was due ${fullLabel}`,
    };
  }

  if (days === 0) {
    return {
      urgency: "today",
      label: "Today",
      countdown,
      days,
      fullLabel: "Due today",
    };
  }

  if (days === 1) {
    return {
      urgency: "upcoming",
      label: "Tomorrow",
      countdown,
      days,
      fullLabel: "Due tomorrow",
    };
  }

  // Inside the coming week a weekday name is easier to place than a date.
  const label =
    days < 7
      ? due.toLocaleDateString("en-US", { weekday: "short" })
      : formatShortDate(iso);

  return {
    urgency: "upcoming",
    label,
    countdown,
    days,
    fullLabel: `Due ${fullLabel}`,
  };
}

/*
 * `localDayKey(iso)` USED TO LIVE HERE. It was collapsed into
 * `dayKeyOf(value: Date | string)` in `$lib/schedule` during the SvelteKit
 * port.
 *
 * The two functions produced the identical "YYYY-MM-DD" from local parts and
 * differed only in whether they took a Date or an ISO string. Two functions
 * computing the same string is how the two of them eventually disagree, so
 * there is now exactly one place the local-parts rule lives.
 *
 * The rule itself is unchanged and still load-bearing: build the key from
 * local parts, never `toISOString().slice(0, 10)`, which would shift an
 * evening appointment onto the next day in any timezone behind UTC.
 *
 * Call `dayKeyOf(iso)` where this used to be called.
 */

/** True when `iso` falls on today's calendar date. */
export function isToday(iso: string, now: Date = new Date()): boolean {
  return calendarDaysBetween(now, new Date(iso)) === 0;
}

/** True when `iso` falls within the next `days` calendar days (inclusive). */
export function isWithinDays(
  iso: string,
  days: number,
  now: Date = new Date(),
): boolean {
  const delta = calendarDaysBetween(now, new Date(iso));
  return delta >= 0 && delta <= days;
}

// ---------------------------------------------------------------------------
// Schedules and events
// ---------------------------------------------------------------------------

const WEEKDAY_ABBREV = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/**
 * What a malformed wall-clock string renders as.
 *
 * Visible and obviously not a time, so a bad `CourseMeeting` shows up on the
 * page instead of reaching a student as "NaN:undefined PM". Matches the shape
 * of `formatMeetingPattern`'s "Schedule TBD": the schedule says plainly that it
 * does not know rather than inventing something.
 */
const UNKNOWN_CLOCK_TIME = "--:--";

/**
 * "HH:mm", one or two digits of hour and exactly two of minute.
 *
 * The hour is left lenient because "9:30" already formatted correctly and is a
 * reasonable thing to hold; the minute is strict because "9:5" is not a time,
 * and the old implementation passed that half through unparsed and emitted
 * "9:5 AM".
 */
const WALL_CLOCK = /^(\d{1,2}):(\d{2})$/;

/**
 * "09:30" -> "9:30 AM". Wall-clock strings, so no timezone is involved.
 *
 * Validates the shape rather than trusting it. `Number("abc")` is NaN, and the
 * old version did no checking, so a malformed value produced
 * "NaN:undefined PM" -- every part of which reached the DOM. No caller passes
 * anything but a well-formed `CourseMeeting.startTime` today, so this was
 * latent rather than live, but it was reachable.
 */
export function formatClockTime(hhmm: string): string {
  const match = WALL_CLOCK.exec(hhmm);
  if (!match) return UNKNOWN_CLOCK_TIME;

  const hour = Number(match[1]);
  const minute = Number(match[2]);
  // `\d` cannot be negative, so only the upper bounds need testing.
  if (hour > 23 || minute > 59) return UNKNOWN_CLOCK_TIME;

  const suffix = hour < 12 ? "AM" : "PM";
  const displayHour = hour % 12 === 0 ? 12 : hour % 12;
  // The minute text as written, not re-formatted from the number, so a valid
  // "09:00" still renders "9:00 AM".
  return `${displayHour}:${match[2]} ${suffix}`;
}

/**
 * "Mon/Wed 9:30 AM" for a recurring course.
 *
 * Assumes every meeting starts at the same time, which is true of all four
 * courses. If that stops holding, each distinct time gets its own segment.
 */
export function formatMeetingPattern(schedule: CourseMeeting[]): string {
  if (schedule.length === 0) return "Schedule TBD";

  const byTime = new Map<string, number[]>();
  for (const meeting of schedule) {
    const days = byTime.get(meeting.startTime) ?? [];
    days.push(meeting.dayOfWeek);
    byTime.set(meeting.startTime, days);
  }

  return Array.from(byTime.entries())
    .map(
      ([time, days]) =>
        `${days.map((d) => WEEKDAY_ABBREV[d]).join("/")} ${formatClockTime(time)}`,
    )
    .join(", ");
}

/** The three strings an EventRow's date block renders. */
export function eventDateBlock(iso: string): {
  month: string;
  day: string;
  time: string;
} {
  const date = new Date(iso);
  return {
    month: date.toLocaleDateString("en-US", { month: "short" }),
    day: `${date.getDate()}`,
    time: date.toLocaleString("en-US", {
      weekday: "short",
      hour: "numeric",
      minute: "2-digit",
    }),
  };
}
