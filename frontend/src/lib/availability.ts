import type { MeetingMode } from "$lib/data";
import type { OpenByDay, SlotView } from "$lib/appointmentsView";

/**
 * What an advisor has open, as arithmetic.
 *
 * All pure, all clock-free. Nothing here takes "today" any more, and that is the
 * shape of what changed: for one phase this module owned a one-calendar-month
 * BOOKING WINDOW, separate from the fixture, because a month grid could show days
 * the fixture had not published and needed telling which of them to refuse.
 *
 * The chip strip is the picker again, so the window IS the published set --
 * `bookingDays()` emits five business days and the strip shows those five. With
 * the two the same thing there is nothing for them to disagree about, so
 * `bookingWindowEnd`, `isBookableDay` and `openCountInWindow` are gone rather
 * than kept as a rule with no second opinion to arbitrate.
 *
 * What survived is the part that was never about the window: the two count maps.
 */

export type ModeFilter = MeetingMode | "any";

/**
 * How many slots each day still has open.
 *
 * Only `available` slots count. A day whose every slot is taken is absent from
 * the result rather than present as zero, so "is anything open here" is one
 * lookup with no second spelling of nothing.
 */
export function availabilityByDay(slots: readonly SlotView[]): OpenByDay {
  const open: Record<string, number> = {};

  for (const slot of slots) {
    if (!slot.available) continue;
    open[slot.dayKey] = (open[slot.dayKey] ?? 0) + 1;
  }

  return open;
}

/**
 * How many slots each day publishes AT ALL, taken or not.
 *
 * The companion to `availabilityByDay`, and the two together are what let a chip
 * say "fully booked" rather than just going quiet. Open alone cannot tell that
 * from "not a day this advisor works": both are zero.
 *
 * It is also what decides WHICH chips exist. A day absent from this map is not a
 * day the advisor works, so it is not offered — which is why the strip never
 * shows a Saturday with nothing in it.
 */
export function publishedByDay(slots: readonly SlotView[]): OpenByDay {
  const published: Record<string, number> = {};

  for (const slot of slots) {
    published[slot.dayKey] = (published[slot.dayKey] ?? 0) + 1;
  }

  return published;
}

/**
 * The days this advisor works, ascending.
 *
 * Day keys sort correctly as STRINGS — "YYYY-MM-DD" is zero-padded and
 * big-endian, so lexicographic order is chronological order. No parsing, and no
 * timezone can get between the comparison and the answer.
 */
export function orderedDayKeys(published: OpenByDay): string[] {
  return Object.keys(published).sort();
}

/** Every slot still free, for the count on a service card. */
export function openSlotCount(slots: readonly SlotView[]): number {
  return slots.filter((slot) => slot.available).length;
}

/**
 * The day the panel should open on: the soonest one with something free.
 *
 * Not simply the first chip. Today is frequently the first chip and frequently
 * has nothing left — slots that have already passed are gone from `available` by
 * mid-afternoon — so opening there would show an empty times list beside a strip
 * of days that do have room, which reads as broken rather than as "not today".
 *
 * Null when every published day is full, so the caller can say so instead of
 * pointing at a day it cannot serve.
 */
export function firstBookableDay(
  dayKeys: readonly string[],
  openByDay: OpenByDay,
): string | null {
  return dayKeys.find((dayKey) => (openByDay[dayKey] ?? 0) > 0) ?? null;
}

/**
 * One day's slots, narrowed by meeting type.
 *
 * Taken slots are KEPT. The panel renders them struck through and disabled,
 * because "10:30 is gone" is information a student uses to read the shape of an
 * advisor's day, and silently omitting them makes a busy morning look like an
 * advisor who simply does not work mornings.
 */
export function slotsForDay(
  slots: readonly SlotView[],
  dayKey: string,
  mode: ModeFilter,
): SlotView[] {
  return slots.filter(
    (slot) => slot.dayKey === dayKey && (mode === "any" || slot.mode === mode),
  );
}
