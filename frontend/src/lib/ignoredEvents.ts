import { createOverrideStore } from "$lib/overrideStore.svelte";
import { isEventCategory, type ScheduleItem } from "$lib/schedule";

/**
 * Events the student has said they are not interested in.
 *
 * ONE store, read by both surfaces. Ignore something on Home and it is gone
 * from the calendar; ignore it on the calendar and it is gone from Home. The
 * two surfaces differ in what they do with that fact, not in what they know:
 * Home hides it permanently because Home is a recommendation feed, while the
 * calendar can show it again because the calendar is the record of what exists.
 *
 * ## Only opt-in events are ignorable
 *
 * `EventType` is a closed union of the five opt-in origins (career, rady, club,
 * sandiego, ucsd) and `EVENT_CATEGORIES` is exactly that set, so
 * `isEventCategory` is a reliable guard. Classes, assignments and appointments
 * are `SCHEDULE_CATEGORIES`; tasks, to-dos and student-created events are
 * `PERSONAL_CATEGORIES`. Nothing in either of those groups can be ignored, and
 * `canIgnore` below is the one place that decision lives.
 *
 * ## The id this is keyed on
 *
 * The RAW `Event.id`, not the calendar's item id. `evt-3-1`, never `evt-evt-3-1`
 * and never `3-1`.
 *
 * The two surfaces name the same event differently. Home holds an `Event` and
 * uses `event.id`, which in the fixtures already looks like `evt-3-1`. The
 * calendar prefixes it again in `buildSchedule`, so the same event arrives as
 * `evt-evt-3-1`. So exactly one of the two has a prefix to shed, and it is the
 * calendar.
 *
 * This is the third of three deliberate key spaces -- task id, calendar item
 * id, raw `Event.id`.
 *
 * ## What changed in Phase 7a, and why it was a HIGH defect
 *
 * These setters used to normalise through `eventIdOf` themselves, and that is
 * what broke the module's own headline.
 *
 * `eventIdOf` strips exactly one leading `evt-`. Given a calendar item id that
 * recovers the raw id. Given a RAW id, which already starts with `evt-`, it
 * mangles it -- so Home's write to `evt-3-1` landed under `3-1` while the
 * calendar's write to `evt-evt-3-1` landed under `evt-3-1`. Each surface was
 * self-consistent and neither could see the other: ignoring an event on Home
 * left it showing on the calendar and the reverse. Two stores wearing one name.
 *
 * The normaliser could not tell its input cases apart because raw event ids are
 * `evt-`-prefixed by construction, so no amount of care at the call sites would
 * have fixed it. **The store no longer normalises anything it is handed.** It
 * keys on precisely the string given, and the ONE surface holding a prefixed id
 * -- the calendar -- sheds it at its own boundary by calling `eventIdOf`.
 *
 * `filterSchedule` was already in this space: `isVisible` strips one `evt-` off
 * a calendar item id and matches against `ignoredEventIds`, which is the raw
 * form. So the fix moved Home into the space the filter had always expected.
 *
 * Old keys written under the previous shape stay in `localStorage` and are inert
 * -- an event ignored on Home before this change reappears once. Accepted rather
 * than migrated: absence means "never touched" here, so a stale key is harmless
 * rather than corrupt. See BUGS.md.
 */

const store = createOverrideStore<true>("thrive:ignored-events");

export type IgnoredMap = Readonly<Record<string, true>>;

/** Every ignored id, reactive. Was `useIgnoredEvents()`. */
export const ignoredEvents = () => store.values;

/** Read outside a reactive context. */
export const readIgnoredEvents = () => store.read();

/**
 * The raw `Event.id` behind a CALENDAR ITEM id.
 *
 * `evt-evt-3-1` -> `evt-3-1`. `buildSchedule` builds event item ids as
 * `evt-${event.id}`, and stripping exactly one leading `evt-` recovers the
 * original.
 *
 * ## Its input is a calendar item id. Only ever that.
 *
 * The signature says `itemId` and means it. This function CANNOT tell a calendar
 * item id from a raw `Event.id`, because a raw event id starts with `evt-` too
 * -- so handing it one strips a prefix that was never a prefix and produces
 * `3-1`, a key nothing else in the app uses. That is not a hypothetical: it is
 * BUGS.md's HIGH ignore-store defect, and it happened because these very
 * setters called this function on ids that were already raw.
 *
 * The old doc comment claimed "passing a raw id through twice is safe". It is
 * not, and the claim is what allowed the bug to be written twice.
 *
 * The single normaliser, with one documented sibling: `isVisible` in
 * `schedule.ts` strips the same prefix inline, because importing this module
 * would drag a store into a file the server renders through. Same rule, stated
 * in both places, and MIGRATION.md section 9 defect 12 is the record of what
 * happens when a THIRD copy appears.
 */
export function eventIdOf(itemId: string): string {
	return itemId.startsWith("evt-") ? itemId.slice("evt-".length) : itemId;
}

/**
 * Can this row be ignored at all?
 *
 * The guard, not a suggestion. A class or a deadline is something the student
 * is already committed to, and offering to hide it would be offering to hide an
 * obligation.
 */
export function canIgnore(item: ScheduleItem): boolean {
	return isEventCategory(item.category);
}

/**
 * Is this event ignored? Takes a RAW `Event.id` and looks it up unchanged.
 *
 * No normalising here, deliberately. A caller holding a calendar item id calls
 * `eventIdOf` first, at its own boundary, where it is the only party that knows
 * which kind of id it has.
 */
export function isEventIgnored(eventId: string, ignored: IgnoredMap): boolean {
	return ignored[eventId] === true;
}

/**
 * Ignore or un-ignore an event, by RAW `Event.id`. See the note above.
 *
 * Not-ignored is the default, so the absence is stored rather than `false`.
 * That keeps the map small and makes un-ignoring a delete rather than a second
 * kind of truth -- which is also why undo restores a row to its original
 * position: ordering was never touched.
 */
export function setEventIgnored(eventId: string, ignored: boolean) {
	store.set(eventId, ignored ? true : undefined);
}

/** The way back from an empty Home feed. */
export function clearIgnoredEvents() {
	for (const id of Object.keys(store.read())) store.set(id, undefined);
}

export function ignoredCount(ignored: IgnoredMap): number {
	return Object.keys(ignored).length;
}
