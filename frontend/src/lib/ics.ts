import type { Event } from "$lib/data";
import type { ScheduleItem } from "$lib/schedule";

/**
 * Minimal iCalendar (.ics) export.
 *
 * This produces a FILE the student downloads and chooses to import. THRIVE
 * still never writes to anyone's calendar -- there is no calendar API call
 * here, nothing leaves the browser, and nobody is notified.
 *
 * ## The clock is a parameter
 *
 * `DTSTAMP` is "when this file was made", so building one needs the current
 * instant. The Next version read `new Date()` inside `buildIcs`, which made the
 * whole builder untestable without faking a global and put a clock read in a
 * module a server render can reach.
 *
 * Here the instant is an argument. `buildIcs` is pure and its output is
 * assertable byte for byte; `downloadIcs` reads the clock at the boundary,
 * inside a click handler, which is where CONVENTIONS.md allows it. Same shape as
 * `describeDue(iso, now)` and `nextUpItem(items, now)`.
 */

export interface IcsEvent {
	/** Stable identifier; becomes the UID so re-importing updates rather than duplicates. */
	id: string;
	title: string;
	start: string;
	end: string;
	location?: string;
	description?: string;
}

/** iCalendar wants UTC basic format: 20260814T180000Z */
function toIcsStamp(iso: string): string {
	return new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

/** Commas, semicolons, and newlines are structural in iCalendar text values. */
function escapeText(value: string): string {
	return value
		.replace(/\\/g, "\\\\")
		.replace(/;/g, "\\;")
		.replace(/,/g, "\\,")
		.replace(/\r?\n/g, "\\n");
}

/**
 * The calendar row as one exportable event, or null when it has no instant.
 *
 * ONE mapper, called by both surfaces that offer the download. The Next tree
 * wrote this object literal twice -- once in `ItemDetail` and once in
 * `DayEventsSection` -- which is two places for the `endISO ?? startISO`
 * fallback to be got wrong independently.
 *
 * Null rather than a partial event: a recurring class meeting carries no
 * `startISO` (it is a weekday RULE, not an instant), and an .ics with no DTSTART
 * is not a shorter calendar file, it is an invalid one.
 */
export function icsFromItem(item: ScheduleItem): IcsEvent | null {
	if (!item.startISO) return null;

	return {
		id: item.id,
		title: item.title,
		start: item.startISO,
		end: item.endISO ?? item.startISO,
		location: item.detail || undefined,
		description: item.description,
	};
}

/**
 * The same, from an `Event` — which is what HOME holds.
 *
 * A second mapper rather than a shared one, and that is deliberate. The two
 * inputs are genuinely different shapes: a `ScheduleItem` carries a `detail`
 * string that is a location on an event row and a course code on a task, and
 * `startISO` is OPTIONAL on it because a recurring class is a weekday rule. An
 * `Event` has a real `location` field and its `start` is required, so this one
 * cannot fail and does not return null.
 *
 * Collapsing them would mean widening `ScheduleItem` or narrowing `Event` to a
 * lowest common shape, and the fallback each needs is different. Two five-line
 * mappers over one function with a discriminant.
 */
export function icsFromEvent(event: Event): IcsEvent {
	return {
		id: event.id,
		title: event.title,
		start: event.start,
		// The one rule they DO share: an event with no distinct end is a marker at
		// its start rather than an event of unknown length.
		end: event.end ?? event.start,
		location: event.location || undefined,
		description: event.description,
	};
}

/**
 * The same, from a booked appointment. The appointments page's path.
 *
 * A third mapper, on the same reasoning as the second: an `AppointmentView`
 * carries a REQUIRED `endISO` -- a slot is thirty minutes by construction -- so
 * unlike `icsFromItem` there is no missing-instant case to return null for, and
 * unlike `icsFromEvent` there is no `end ?? start` fallback to get wrong. What
 * it does have that neither other source does is a `mode`: a Zoom meeting's
 * LOCATION is the word "Zoom", not the advisor's office, and putting the office
 * on a remote booking would send the student across campus.
 *
 * The title is passed in rather than built here. It is user-facing copy and
 * lives in `messages.ts` with the rest; this module is imported by the calendar
 * too and has no business holding a sentence.
 */
export function icsFromAppointment(
	appointment: {
		id: string;
		startISO: string;
		endISO: string;
		location: string;
		reason: string;
	},
	title: string,
): IcsEvent {
	return {
		// The appointment id, so re-importing the same booking updates the entry
		// rather than adding a second one to the student's real calendar.
		id: appointment.id,
		title,
		start: appointment.startISO,
		end: appointment.endISO,
		location: appointment.location || undefined,
		description: appointment.reason || undefined,
	};
}

/**
 * The file's text.
 *
 * `stampISO` is the DTSTAMP instant -- when this file was produced. Passed in
 * rather than read, see the note at the top.
 */
export function buildIcs(events: IcsEvent[], stampISO: string): string {
	const lines: string[] = [
		"BEGIN:VCALENDAR",
		"VERSION:2.0",
		"PRODID:-//THRIVE//MSBA prototype//EN",
		"CALSCALE:GREGORIAN",
		"METHOD:PUBLISH",
	];

	for (const event of events) {
		lines.push(
			"BEGIN:VEVENT",
			`UID:${event.id}@thrive.local`,
			`DTSTAMP:${toIcsStamp(stampISO)}`,
			`DTSTART:${toIcsStamp(event.start)}`,
			`DTEND:${toIcsStamp(event.end)}`,
			`SUMMARY:${escapeText(event.title)}`,
		);
		if (event.location) lines.push(`LOCATION:${escapeText(event.location)}`);
		if (event.description) {
			lines.push(`DESCRIPTION:${escapeText(event.description)}`);
		}
		lines.push("END:VEVENT");
	}

	lines.push("END:VCALENDAR");
	// iCalendar requires CRLF line endings.
	return lines.join("\r\n");
}

/** A filename with exactly one `.ics` on the end. */
export function icsFilename(name: string): string {
	return name.endsWith(".ics") ? name : `${name}.ics`;
}

/**
 * Trigger a download of these events as one .ics file.
 *
 * CLIENT ONLY, and the one clock read in this module. Called from a click
 * handler, never during a render -- there is no `document` on the server, so a
 * server-render call would throw rather than quietly produce a wrong file.
 */
export function downloadIcs(filename: string, events: IcsEvent[]): void {
	const blob = new Blob([buildIcs(events, new Date().toISOString())], {
		type: "text/calendar;charset=utf-8",
	});
	const url = URL.createObjectURL(blob);
	const anchor = document.createElement("a");
	anchor.href = url;
	anchor.download = icsFilename(filename);
	anchor.click();
	URL.revokeObjectURL(url);
}

/** The whole download, from a calendar row. Returns false when there is nothing to export. */
export function downloadItemIcs(item: ScheduleItem): boolean {
	const event = icsFromItem(item);
	if (!event) return false;
	downloadIcs(item.id, [event]);
	return true;
}

/**
 * The whole download, from an `Event`. Home's path.
 *
 * No boolean, because there is no failure case: an `Event` always has a start.
 * The calendar's version needs one because a class meeting has no instant.
 */
export function downloadEventIcs(event: Event): void {
	downloadIcs(event.id, [icsFromEvent(event)]);
}
