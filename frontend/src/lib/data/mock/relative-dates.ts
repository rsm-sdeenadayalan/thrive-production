/**
 * Mock fixtures are dated relative to "now" so the prototype always looks
 * live -- there is never a stale demo where everything is overdue.
 *
 * These run when a provider is called (server side), not at module load, so
 * the values stay fresh across requests during a long dev session.
 */

/** Local midnight today. */
export function startOfToday(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

/**
 * An ISO timestamp `days` from today at local `hour`:`minute`.
 * Negative `days` reaches into the past.
 */
export function at(days: number, hour = 9, minute = 0): string {
  const d = startOfToday();
  d.setDate(d.getDate() + days);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

/** An ISO calendar date (YYYY-MM-DD) `days` from today. */
export function onDay(days: number): string {
  const d = startOfToday();
  d.setDate(d.getDate() + days);
  // Format from local parts; toISOString() would shift across the date line.
  const month = `${d.getMonth() + 1}`.padStart(2, "0");
  const day = `${d.getDate()}`.padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

/** How many days ahead the next `dayOfWeek` falls. Today counts as 7, not 0. */
function daysUntilWeekday(dayOfWeek: number): number {
  const delta = (dayOfWeek - startOfToday().getDay() + 7) % 7;
  return delta === 0 ? 7 : delta;
}

/**
 * The next occurrence of a weekday, strictly in the future.
 *
 * `weeksAhead` pushes it a further week out, which is what "next Wednesday"
 * means on a Tuesday -- the Wednesday after tomorrow's, not tomorrow.
 *
 * 0 = Sunday ... 6 = Saturday.
 */
export function upcomingWeekday(
  dayOfWeek: number,
  { hour = 9, minute = 0, weeksAhead = 0 } = {},
): string {
  return at(daysUntilWeekday(dayOfWeek) + weeksAhead * 7, hour, minute);
}

/** Weekday numbers, so fixtures read as days rather than magic integers. */
export const SUN = 0;
export const MON = 1;
export const TUE = 2;
export const WED = 3;
export const THU = 4;
export const FRI = 5;
export const SAT = 6;
