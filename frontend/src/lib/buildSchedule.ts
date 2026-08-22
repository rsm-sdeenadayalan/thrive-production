import {
	getAdvisors,
	getAssignments,
	getCourses,
	getEvents,
	getMyAppointments
} from '$lib/data';
import {
	dayKeyOf,
	wallClockLabel,
	type DatedScheduleItem,
	type RecurringMeeting,
	type ScheduleData
} from '$lib/schedule';

/**
 * Assemble the calendar's data from the providers.
 *
 * ## Where this may be called from
 *
 * A server `load` function, and nowhere else. The formatting it does on the way
 * through IS the mechanism behind "components never see a raw timestamp": every
 * `toLocaleTimeString` and every `getHours()` in this file happens once, on the
 * server, against the server's own locale and timezone. A component that called
 * this itself would be asking the browser the questions this file exists to
 * answer for it. See CONVENTIONS.md.
 *
 * Ported in Phase 7a. Phase 2 shipped `todayKey()` alone because the five
 * providers did not exist yet; they all do now.
 *
 * ## What is NOT here, and will never be
 *
 * Tasks and quick-list to-dos. A task's due date can be MOVED by the student
 * and that edit lives only in `localStorage`, a student can ADD a task the
 * server has never seen, and a to-do has no server row at all. Merging any of
 * them here would render a date the student has already changed. That half is
 * `calendarSources.mergedSchedule()`, applied on the client after mount.
 *
 * ## Two shapes out, not one
 *
 * Classes stay as WEEKDAY RULES (`RecurringMeeting`: `dayOfWeek` plus a
 * wall-clock `startTime` plus a pre-rendered `timeLabel`) and are expanded onto
 * whichever days a view is showing. Everything else is pinned to one `dayKey`.
 *
 * That split is what lets the calendar move to any month without another round
 * trip. Pre-expanding classes would mean either choosing a horizon on the server
 * and having the grid go blank past it, or shipping every meeting of the term to
 * render one month. A wall-clock time carries no timezone, so expanding it is
 * safe wherever it happens.
 */
export async function buildScheduleData(): Promise<ScheduleData> {
	const [courses, assignments, events, appointments, advisors] = await Promise.all([
		getCourses(),
		getAssignments(),
		getEvents(),
		getMyAppointments(),
		getAdvisors()
	]);

	const courseById = new Map(courses.map((course) => [course.id, course]));
	const advisorById = new Map(advisors.map((advisor) => [advisor.id, advisor]));

	/** "9:30 AM" from a stored instant. Server-side, per the note above. */
	const timeOf = (iso: string) =>
		new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

	const minutesFrom = (iso: string) => {
		const date = new Date(iso);
		return date.getHours() * 60 + date.getMinutes();
	};

	const recurring: RecurringMeeting[] = courses.flatMap((course) =>
		course.schedule.map((meeting, index) => ({
			// A course can meet more than once a week, so the index is part of the
			// id. Without it two meetings of one course collide and `itemsForDay`
			// renders one row where there are two.
			id: `${course.id}-${index}`,
			dayOfWeek: meeting.dayOfWeek,
			title: `${course.code} · ${course.title}`,
			detail: meeting.location,
			startTime: meeting.startTime,
			timeLabel: wallClockLabel(meeting.startTime)
		}))
	);

	const datedAssignments: DatedScheduleItem[] = assignments.map((assignment) => ({
		id: `asg-${assignment.id}`,
		category: 'assignment',
		title: assignment.title,
		dayKey: dayKeyOf(assignment.dueDate),
		timeLabel: timeOf(assignment.dueDate),
		detail: courseById.get(assignment.courseId)?.code ?? '',
		sortMinutes: minutesFrom(assignment.dueDate),
		// Never all-day. A deadline has a time, and floating it to the top of the
		// day would put it above a class it is actually due after.
		allDay: false,
		startISO: assignment.dueDate,
		endISO: assignment.dueDate
	}));

	const datedEvents: DatedScheduleItem[] = events.map((event) => {
		// An event with no distinct end is a marker for the day rather than a slot
		// on it, so it sorts to the top as all-day.
		const allDay = !event.end || event.end === event.start;

		return {
			/*
			 * `evt-${event.id}` on an id that is ALREADY `evt-3-1`, so this reads
			 * `evt-evt-3-1`. Kept, deliberately.
			 *
			 * It looks like a bug and is not: every calendar item id carries a
			 * prefix naming its stream, and events are the one stream whose source
			 * ids happen to share that prefix. Dropping it here would make the
			 * calendar's id space non-uniform -- `asg-12`, `apt-3`, `task-7`,
			 * `todo-x`, `custom-…`, and then a bare `evt-3-1` -- and the label and
			 * urgent stores are keyed on exactly this space.
			 *
			 * What the double prefix DID cause is BUGS.md's HIGH ignore-store
			 * defect: `eventIdOf` strips one `evt-`, which recovers the raw id from
			 * a calendar item id and MANGLES a raw id passed in directly. That is
			 * fixed at the store, not here -- `ignoredEvents.ts` no longer strips
			 * ids it is handed, and `eventIdOf` is now only ever applied to a
			 * calendar item id. See MIGRATION.md section 9 defect 14 for the same
			 * pattern on custom events.
			 */
			id: `evt-${event.id}`,
			category: event.type,
			title: event.title,
			dayKey: dayKeyOf(event.start),
			timeLabel: allDay ? 'All day' : timeOf(event.start),
			detail: event.location,
			sortMinutes: allDay ? 0 : minutesFrom(event.start),
			allDay,
			startISO: event.start,
			endISO: event.end ?? event.start,
			relevantToGoal: event.relevantToGoal,
			description: event.description
		};
	});

	const datedAppointments: DatedScheduleItem[] = appointments.map((appointment) => {
		const advisor = advisorById.get(appointment.advisorId);

		return {
			id: `apt-${appointment.id}`,
			category: 'appointment',
			// The advisor is what makes an appointment legible -- "Appointment" on
			// its own tells a student nothing they did not already know from the
			// dot. The fallback is unreachable with current fixtures and exists so
			// a dangling advisorId cannot blank the row.
			title: advisor ? `${advisor.role} with ${advisor.name}` : 'Appointment',
			dayKey: dayKeyOf(appointment.start),
			timeLabel: timeOf(appointment.start),
			detail: appointment.mode === 'zoom' ? 'Zoom' : (advisor?.location ?? 'In person'),
			sortMinutes: minutesFrom(appointment.start),
			allDay: false,
			startISO: appointment.start,
			endISO: appointment.end
		};
	});

	return {
		dated: [...datedAssignments, ...datedEvents, ...datedAppointments],
		recurring
	};
}

/**
 * Today's day key, decided once on the server.
 *
 * Read the clock HERE, in a `load` function, and pass the result down as a
 * string. A component that computes its own "today" disagrees with the server
 * in another timezone and freezes at whatever moment it last rendered.
 */
export function todayKey(): string {
	return dayKeyOf(new Date());
}

/**
 * Minutes past midnight at a given instant.
 *
 * The calendar's "next up" line needs a "now" to measure against, and this is
 * where that number is produced: in a `load`, from the same `new Date()` that
 * decided `todayKey`, travelling to the client as a plain number.
 *
 * `calendarSources.nowMinutes()` is the client-side sibling and stays unused.
 * Both were available and the server one was chosen, because a `$derived`
 * calling the client one would run during SSR too: the server would render "next
 * up: 9:00 AM" and the browser would silently replace it a moment later, along
 * with which square carries the ring. That is the hydration-drift failure
 * CONVENTIONS.md calls "quieter, and worse" -- and the value freezes at page
 * load either way, so the client read buys nothing to pay for it with.
 */
export function nowMinutesAt(now: Date): number {
	return now.getHours() * 60 + now.getMinutes();
}
