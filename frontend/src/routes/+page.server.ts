import {
	getCourses,
	getDegreeProgress,
	getEvents,
	getProgramTimeline,
	getStudent,
	getTasks
} from '$lib/data';
import {
	describeDue,
	eventDateBlock,
	formatClockTime,
	formatLongDate,
	formatMeetingPattern,
	greetingFor,
	isWithinDays
} from '$lib/format';
import type { ClassRow, CourseRow, EventRowData, TaskRowData } from '$lib/homeView';
import type { PageServerLoad } from './$types';

/** How many events count toward the "this week" stat. */
const WEEK_WINDOW_DAYS = 7;

/**
 * Home's data, and every date decided here.
 *
 * ## One clock read, one place
 *
 * `new Date()` is called ONCE, at the top, and every classification and format
 * below measures against that same instant. Two calls would be two answers, and
 * a task classified against 11:59:59 while the next line reads 12:00:00 is a
 * task that is somehow both today and overdue.
 *
 * `nowISO` goes to the client so anything the student can edit reclassifies
 * against the server's instant rather than asking the browser what day it is.
 * Nothing consumes it in 6a -- editing is 6b -- but it is loaded now because the
 * shape of the payload should not change when the editing lands.
 *
 * CONVENTIONS.md states this rule and nothing enforces it: `describeDue`,
 * `formatLongDate` and `greetingFor` all default their `now` parameter to
 * `new Date()`, so a component calling one compiles, renders something
 * plausible, and is wrong in another timezone. Review is the enforcement.
 *
 * ## What is NOT computed here
 *
 * The overdue and due-today counts, and the count of events this week. Those see
 * the student's persisted ticks and ignores, which only exist in the browser.
 * Counting them here would freeze them at the fixture's answer and let the pills
 * contradict the cards directly beneath them. What goes down instead is the
 * classified rows -- the data to count, not the count. Each event row carries a
 * `thisWeek` flag, which is the date half of that question answered here so the
 * client only has to filter on a boolean.
 */
export const load: PageServerLoad = async () => {
	const [student, courses, tasks, events, degree, timeline] = await Promise.all([
		getStudent(),
		getCourses(),
		getTasks(),
		getEvents(),
		getDegreeProgress(),
		getProgramTimeline()
	]);

	const now = new Date();

	const taskItems: TaskRowData[] = tasks.map((task) => ({
		task,
		due: describeDue(task.dueDate, now)
	}));

	/*
	 * Today's classes only.
	 *
	 * This card used to carry a "Due today" list as well, which rendered the same
	 * tasks the Tasks card was already showing one column over. The two did not
	 * agree: ticking a task struck it through in one and left the other insisting
	 * it was due. Tasks live in exactly one place on Home.
	 */
	const todaysClasses: ClassRow[] = courses
		.flatMap((course) =>
			course.schedule
				.filter((meeting) => meeting.dayOfWeek === now.getDay())
				.map((meeting) => ({ course, meeting }))
		)
		.sort((a, b) => a.meeting.startTime.localeCompare(b.meeting.startTime))
		.map(({ course, meeting }) => ({
			// A course can meet twice in one day, so the key needs both parts.
			id: `${course.id}-${meeting.startTime}`,
			time: formatClockTime(meeting.startTime),
			title: `${course.code} · ${course.title}`,
			location: meeting.location
		}));

	const courseRows: CourseRow[] = courses.map((course) => ({
		course,
		nextDue: describeDue(course.nextAssignment.due, now),
		scheduleLabel: formatMeetingPattern(course.schedule)
	}));

	/*
	 * Every upcoming event, each one told whether it falls in the week window.
	 *
	 * The window is the date question, so it is answered here. What travels down
	 * is the classified rows, not a count and not a second list of ids: the pill
	 * counts `thisWeek` rows the student has not ignored, and the card renders
	 * from the same array. Two views of one list cannot contradict each other.
	 *
	 * `event.id` is a RAW `Event.id` and stays raw everywhere it goes. The ignore
	 * store is keyed on exactly this form and the client checks against it without
	 * stripping a prefix -- MIGRATION.md section 9 defect 12 is what happens when a
	 * second normaliser appears. There is nothing here to normalise.
	 */
	const eventRows: EventRowData[] = events.map((event) => ({
		event,
		dateBlock: eventDateBlock(event.start),
		thisWeek: isWithinDays(event.start, WEEK_WINDOW_DAYS, now)
	}));

	return {
		student,
		degree,
		timeline,
		taskItems,
		todaysClasses,
		courseRows,
		eventRows,
		/** Formatted here so no component calls `formatLongDate()` with no argument. */
		dateLabel: formatLongDate(now),
		greeting: greetingFor(now),
		/** The server's instant, for 6b's re-classification of edited due dates. */
		nowISO: now.toISOString()
	};
};
