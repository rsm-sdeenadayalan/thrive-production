import { afterEach, describe, expect, it, vi } from "vitest";

import { installStorage, uninstallStorage, type FakeStorage } from "$lib/testing/fakeStorage";
import type { ItemDraft } from "$lib/calendarAdd";

/**
 * Where each kind of added item lands.
 *
 * `AddItemForm` is a radio group and three inputs. The only thing in it that can
 * be wrong in a way nobody notices is the ROUTING -- and it fails silently in
 * both directions:
 *
 *   a to-do filed as a task   turns up on Home under a heading that says
 *                             "pulled from every source", which is then untrue
 *   a task filed as an event  cannot be ticked, so a deadline quietly stops
 *                             being a deadline
 *
 * Neither throws, neither fails a type check, and neither is visible on the day
 * it happens. It is visible a week later on a different page.
 *
 * ## Every case asserts an ABSENCE as well as a presence
 *
 * "The task store gained a key" is half a test: it stays green if the write went
 * to all three stores. So each case names the store it expects AND asserts that
 * the other two localStorage keys were never created. The absence is the half
 * that catches a mis-route.
 *
 * The three keys, once, so a rename cannot leave a case asserting against a
 * store that no longer exists:
 */
const TASK_KEY = "thrive:task-added";
const TODO_KEY = "thrive:quicklist";
const EVENT_KEY = "thrive:custom-events";
const LABEL_KEY = "thrive:item-labels";
const URGENT_KEY = "thrive:item-urgent";

const ALL_KEYS = [TASK_KEY, TODO_KEY, EVENT_KEY];

const DAY = "2026-08-17";

let storage: FakeStorage;

type CalendarAdd = typeof import("$lib/calendarAdd");

async function fresh(): Promise<CalendarAdd> {
	vi.resetModules();
	storage = installStorage();
	return await import("$lib/calendarAdd");
}

afterEach(() => {
	uninstallStorage();
});

function draft(over: Partial<ItemDraft> = {}): ItemDraft {
	return {
		dayKey: DAY,
		title: "Read the Kaggle write-up",
		time: "14:30",
		label: "",
		urgent: false,
		...over,
	};
}

/** What is actually sitting in one localStorage key, parsed. */
function stored(key: string): Record<string, unknown> | undefined {
	const raw = storage.dump()[key];
	return raw === undefined ? undefined : JSON.parse(raw);
}

/** The one store that gained anything, so "and nowhere else" is one assertion. */
function touched(): string[] {
	return ALL_KEYS.filter((key) => Object.keys(stored(key) ?? {}).length > 0);
}

describe("each kind lands in its own store and nowhere else", () => {
	it("a task goes to the added-tasks store", async () => {
		const add = await fresh();

		const itemId = add.addCalendarItem("task", draft());

		expect(touched()).toEqual([TASK_KEY]);
		const tasks = Object.values(stored(TASK_KEY)!) as { title: string; source: string }[];
		expect(tasks).toHaveLength(1);
		expect(tasks[0].title).toBe("Read the Kaggle write-up");
		// The calendar item id, which is what the annotation stores key on.
		expect(itemId).toMatch(/^task-own-\d+$/);
	});

	it("a to-do goes to the quick list", async () => {
		const add = await fresh();

		const itemId = add.addCalendarItem("todo", draft());

		expect(touched()).toEqual([TODO_KEY]);
		const todos = Object.values(stored(TODO_KEY)!) as { title: string; dueDate: string }[];
		expect(todos).toHaveLength(1);
		expect(itemId).toMatch(/^todo-q-/);
	});

	it("an event goes to the custom-events store", async () => {
		const add = await fresh();

		const itemId = add.addCalendarItem("event", draft());

		expect(touched()).toEqual([EVENT_KEY]);
		const events = Object.values(stored(EVENT_KEY)!) as { title: string; dayKey: string }[];
		expect(events).toHaveLength(1);
		expect(events[0].dayKey).toBe(DAY);
		// Doubly prefixed, because the event's own id already carries one. Pinned
		// rather than corrected: `deleteCustomEvent` agrees with it, and changing it
		// would strand every stored event for a cosmetic gain. MIGRATION.md §9 no. 14.
		expect(itemId).toMatch(/^custom-custom-\d+$/);
	});

	it("three adds in a row leave three stores holding one thing each", async () => {
		// The cases above each start from empty, so none of them would notice a
		// write that also went somewhere else on the SECOND call.
		const add = await fresh();

		add.addCalendarItem("task", draft({ title: "one" }));
		add.addCalendarItem("todo", draft({ title: "two" }));
		add.addCalendarItem("event", draft({ title: "three" }));

		expect(Object.keys(stored(TASK_KEY)!)).toHaveLength(1);
		expect(Object.keys(stored(TODO_KEY)!)).toHaveLength(1);
		expect(Object.keys(stored(EVENT_KEY)!)).toHaveLength(1);
	});
});

describe("what each kind does with the day and the time", () => {
	it("a task is due at the time given, on the day given", async () => {
		const add = await fresh();

		add.addCalendarItem("task", draft({ time: "14:30" }));

		const [task] = Object.values(stored(TASK_KEY)!) as { dueDate: string }[];
		const due = new Date(task.dueDate);
		// Local parts, because that is how the instant was built. Comparing the ISO
		// string would pin the runner's timezone instead of the behaviour.
		expect(due.getFullYear()).toBe(2026);
		expect(due.getMonth()).toBe(7);
		expect(due.getDate()).toBe(17);
		expect(due.getHours()).toBe(14);
		expect(due.getMinutes()).toBe(30);
	});

	it("a to-do lands on the day at midnight, ignoring the form's time", async () => {
		/*
		 * A quick-list item is all-day by design: the picker never offers a time and
		 * `todoToItem` renders every one of them "All day". Storing 14:30 would put a
		 * number in the store that nothing reads and that contradicts the row.
		 *
		 * The date still has to be the day chosen -- without a due date the to-do
		 * exists but lands in the agenda's "No date" bucket, which is not what
		 * pressing "add to this day" asked for.
		 */
		const add = await fresh();

		add.addCalendarItem("todo", draft({ time: "14:30" }));

		const [todo] = Object.values(stored(TODO_KEY)!) as { dueDate: string }[];
		const due = new Date(todo.dueDate);
		expect(due.getDate()).toBe(17);
		expect(due.getHours()).toBe(0);
		expect(due.getMinutes()).toBe(0);
	});

	it("an event keeps the wall clock, not an instant", async () => {
		// A custom event stores "HH:mm" and a day key. No timezone is involved, which
		// is what lets `customEventToItem` expand it safely anywhere.
		const add = await fresh();

		add.addCalendarItem("event", draft({ time: "14:30" }));

		const [event] = Object.values(stored(EVENT_KEY)!) as { time: string; dayKey: string }[];
		expect(event.time).toBe("14:30");
		expect(event.dayKey).toBe(DAY);
	});

	it("a task marked urgent is filed as high priority", async () => {
		// Not double storage: the urgent flag is a calendar annotation and priority
		// is a field Home's task row reads. Two surfaces, two readers.
		const add = await fresh();

		add.addCalendarItem("task", draft({ urgent: true }));

		const [task] = Object.values(stored(TASK_KEY)!) as { priority: string }[];
		expect(task.priority).toBe("high");
	});
});

describe("the annotations attach to the calendar item id", () => {
	it("a label is stored under the id the calendar will render", async () => {
		const add = await fresh();

		const itemId = add.addCalendarItem("event", draft({ label: "MGT 253" }));

		expect(stored(LABEL_KEY)).toEqual({ [itemId!]: "MGT 253" });
	});

	it("urgent is stored under the same id, for all three kinds alike", async () => {
		const add = await fresh();

		const taskId = add.addCalendarItem("task", draft({ urgent: true }));
		const todoId = add.addCalendarItem("todo", draft({ urgent: true }));
		const eventId = add.addCalendarItem("event", draft({ urgent: true }));

		expect(stored(URGENT_KEY)).toEqual({
			[taskId!]: true,
			[todoId!]: true,
			[eventId!]: true,
		});
	});

	it("does not write the flags onto the custom event itself", async () => {
		/*
		 * The Next version stored label and urgent BOTH on the event and in the
		 * annotation stores, and that was a live bug rather than mere redundancy:
		 * `mergedSchedule` resolves urgent as `override ?? item.urgent`, so clearing
		 * the flag in `ItemDetail` wrote `undefined` to the override and then fell
		 * straight back to the copy on the event. Un-marking an event you had marked
		 * urgent did nothing at all.
		 *
		 * One source, so clearing works.
		 */
		const add = await fresh();

		add.addCalendarItem("event", draft({ label: "MGT 253", urgent: true }));

		const [event] = Object.values(stored(EVENT_KEY)!) as {
			label?: string;
			urgent?: boolean;
		}[];
		expect(event.label).toBeUndefined();
		expect(event.urgent).toBeUndefined();
	});

	it("an empty label writes nothing at all", async () => {
		// An emptied label is a removed label, not a blank chip. Same rule
		// `setItemLabel` states; asserted here because the form always supplies the
		// field, so "" is the common case rather than an edge one.
		const add = await fresh();

		add.addCalendarItem("task", draft({ label: "   " }));

		expect(stored(LABEL_KEY)).toBeUndefined();
		expect(stored(URGENT_KEY)).toBeUndefined();
	});
});

describe("what it refuses", () => {
	it("returns null for a blank title and writes nothing", async () => {
		const add = await fresh();

		expect(add.addCalendarItem("task", draft({ title: "   " }))).toBeNull();
		expect(touched()).toEqual([]);
	});

	it("trims the title before storing it", async () => {
		const add = await fresh();

		add.addCalendarItem("todo", draft({ title: "  spaced out  " }));

		const [todo] = Object.values(stored(TODO_KEY)!) as { title: string }[];
		expect(todo.title).toBe("spaced out");
	});

	it("returns null on a day key that will not parse", async () => {
		// Not reachable from the form, which only ever passes `selectedKey`. Guarded
		// because a row minted onto an arbitrary date is worse than a refused add.
		const add = await fresh();

		expect(add.addCalendarItem("task", draft({ dayKey: "not-a-day" }))).toBeNull();
		expect(touched()).toEqual([]);
	});

	it("returns null on a time that will not parse", async () => {
		const add = await fresh();

		expect(add.addCalendarItem("task", draft({ time: "half nine" }))).toBeNull();
		expect(touched()).toEqual([]);
	});
});

describe("instantFor", () => {
	it("builds from local parts, so the day key never shifts", async () => {
		/*
		 * `new Date("2026-08-17T09:00Z")` is nine hours out in San Diego and
		 * `new Date("2026-08-17")` parses as UTC midnight, landing on the 16th
		 * anywhere behind it. The whole reason this goes through `fromDayKey`.
		 */
		const { instantFor } = await fresh();
		const { dayKeyOf } = await import("$lib/schedule");

		const iso = instantFor(DAY, "23:30")!;

		expect(dayKeyOf(iso)).toBe(DAY);
		expect(new Date(iso).getHours()).toBe(23);
	});

	it("zeroes seconds and milliseconds", async () => {
		const { instantFor } = await fresh();

		const iso = instantFor(DAY, "09:00")!;

		expect(new Date(iso).getSeconds()).toBe(0);
		expect(new Date(iso).getMilliseconds()).toBe(0);
	});
});
