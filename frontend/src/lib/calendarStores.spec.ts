import { afterEach, describe, expect, it, vi } from "vitest";

import { installStorage, uninstallStorage, type FakeStorage } from "$lib/testing/fakeStorage";
import type { ScheduleItem } from "$lib/schedule";
import type { Task } from "$lib/data";

/**
 * The remaining persisted stores: calendar prefs, the quick list, the two
 * annotation stores plus custom events, and ignored events.
 *
 * Grouped in one file because each is thin on its own, and because the thing
 * most worth pinning cuts across them: THREE SEPARATE KEY SPACES that must not
 * merge. Task id in `userEdits`, calendar item id in `calendarItems`, and raw
 * `Event.id` in `ignoredEvents`. The last block below is about exactly that.
 */

let storage: FakeStorage;

async function fresh<T>(mod: () => Promise<T>, seed: Record<string, string> = {}): Promise<T> {
	vi.resetModules();
	storage = installStorage(seed);
	return await mod();
}

const prefsModule = () => import("$lib/calendarPrefs");
const quickModule = () => import("$lib/quickList");
const itemsModule = () => import("$lib/calendarItems");
const ignoredModule = () => import("$lib/ignoredEvents");

afterEach(() => {
	uninstallStorage();
});

// ---------------------------------------------------------------------------
// calendarPrefs -- the store half
// ---------------------------------------------------------------------------

describe("calendarPrefs store", () => {
	it("returns the defaults before hydration, not an empty object", async () => {
		// The un-personalised answer is a real, usable set of prefs: everything
		// visible, month view, done items shown. An empty calendar would be worse
		// than a default one.
		const prefs = await fresh(prefsModule, {
			"thrive:calendar-prefs": '{"value":{"view":"agenda"}}',
		});

		expect(prefs.calendarPrefs()).toEqual(prefs.DEFAULT_PREFS);
	});

	it("reads the student's prefs once hydrated", async () => {
		const prefs = await fresh(prefsModule, {
			"thrive:calendar-prefs": '{"value":{"view":"agenda","showDone":false}}',
		});
		const { hydrateStores } = await import("$lib/overrideStore.svelte");

		hydrateStores();

		expect(prefs.calendarPrefs().view).toBe("agenda");
		expect(prefs.calendarPrefs().showDone).toBe(false);
		// Fields the stored value never wrote still come back normalised.
		expect(prefs.calendarPrefs().groupBy).toBe("day");
	});

	it("normalises whatever is stored, so a corrupt value cannot empty the calendar", async () => {
		const prefs = await fresh(prefsModule, {
			"thrive:calendar-prefs": '{"value":{"hidden":"club","view":"timeline"}}',
		});
		const { hydrateStores } = await import("$lib/overrideStore.svelte");

		hydrateStores();

		expect(prefs.calendarPrefs().hidden).toEqual([]);
		expect(prefs.calendarPrefs().view).toBe("month");
	});

	it("merges a partial write over the current value", async () => {
		const prefs = await fresh(prefsModule);

		prefs.setCalendarPrefs({ view: "week" });
		prefs.setCalendarPrefs({ urgentOnly: true });

		expect(prefs.calendarPrefs().view).toBe("week");
		expect(prefs.calendarPrefs().urgentOnly).toBe(true);
	});

	it("toggleCategory adds then removes", async () => {
		const prefs = await fresh(prefsModule);

		prefs.toggleCategory("club");
		expect(prefs.calendarPrefs().hidden).toEqual(["club"]);

		prefs.toggleCategory("club");
		expect(prefs.calendarPrefs().hidden).toEqual([]);
	});

	it("toggleLabel works on its own dimension, leaving categories alone", async () => {
		const prefs = await fresh(prefsModule);

		prefs.toggleCategory("club");
		prefs.toggleLabel("thesis");

		expect(prefs.calendarPrefs().hidden).toEqual(["club"]);
		expect(prefs.calendarPrefs().hiddenLabels).toEqual(["thesis"]);
	});

	it("showAllCategories clears both dimensions", async () => {
		const prefs = await fresh(prefsModule);

		prefs.toggleCategory("club");
		prefs.toggleLabel("thesis");
		prefs.showAllCategories();

		expect(prefs.calendarPrefs().hidden).toEqual([]);
		expect(prefs.calendarPrefs().hiddenLabels).toEqual([]);
	});

	it("persists under one key, as one object", async () => {
		const prefs = await fresh(prefsModule);

		prefs.setCalendarPrefs({ view: "week" });

		const written = JSON.parse(storage.dump()["thrive:calendar-prefs"]);
		expect(written.value.view).toBe("week");
	});
});

// ---------------------------------------------------------------------------
// quickList
// ---------------------------------------------------------------------------

describe("quickList store", () => {
	it("is empty until hydrated", async () => {
		const quick = await fresh(quickModule, {
			"thrive:quicklist": '{"q1":{"id":"q1","title":"Email Amber","done":false,"createdAt":1}}',
		});

		expect(quick.quickItems()).toEqual([]);
	});

	it("adds an item and returns its id", async () => {
		const quick = await fresh(quickModule);

		const id = quick.addQuickItem("Email Amber");

		expect(id).not.toBeNull();
		expect(quick.quickItems()).toHaveLength(1);
		expect(quick.quickItems()[0].title).toBe("Email Amber");
		expect(quick.quickItems()[0].done).toBe(false);
	});

	it("refuses an empty title", async () => {
		const quick = await fresh(quickModule);

		expect(quick.addQuickItem("   ")).toBeNull();
		expect(quick.quickItems()).toEqual([]);
	});

	it("gives two items added in the same millisecond distinct ids", async () => {
		// The counter suffix. Not hypothetical when the second one comes from a
		// "copy" button.
		const quick = await fresh(quickModule);

		const first = quick.addQuickItem("one");
		const second = quick.addQuickItem("two");

		expect(first).not.toBe(second);
		expect(quick.quickItems()).toHaveLength(2);
	});

	it("sorts oldest first", async () => {
		const quick = await fresh(quickModule, {
			"thrive:quicklist": JSON.stringify({
				late: { id: "late", title: "later", done: false, createdAt: 200 },
				early: { id: "early", title: "earlier", done: false, createdAt: 100 },
			}),
		});
		const { hydrateStores } = await import("$lib/overrideStore.svelte");
		hydrateStores();

		expect(quick.quickItems().map((i) => i.id)).toEqual(["early", "late"]);
	});

	it("toggles, dates, notes and deletes", async () => {
		const quick = await fresh(quickModule);
		quick.addQuickItem("Email Amber");

		let item = quick.quickItems()[0];
		quick.toggleQuickItem(item);
		expect(quick.quickItems()[0].done).toBe(true);

		item = quick.quickItems()[0];
		const iso = new Date(2026, 7, 18, 9, 0).toISOString();
		quick.setQuickItemDue(item, iso);
		expect(quick.quickItems()[0].dueDate).toBe(iso);

		item = quick.quickItems()[0];
		quick.setQuickItemNote(item, "  ask about units  ");
		expect(quick.quickItems()[0].note).toBe("ask about units");

		// An emptied note is a deleted note.
		item = quick.quickItems()[0];
		quick.setQuickItemNote(item, "  ");
		expect(quick.quickItems()[0].note).toBeUndefined();

		quick.deleteQuickItem(quick.quickItems()[0].id);
		expect(quick.quickItems()).toEqual([]);
	});

	it("clears only the done items", async () => {
		const quick = await fresh(quickModule);
		quick.addQuickItem("keep");
		quick.addQuickItem("drop");

		quick.toggleQuickItem(quick.quickItems()[1]);
		quick.clearDoneQuickItems();

		expect(quick.quickItems().map((i) => i.title)).toEqual(["keep"]);
	});

	it("records provenance on a copied row without linking it", async () => {
		const quick = await fresh(quickModule);

		quick.addQuickItem("Submit peer review", { copiedFrom: "t1" });

		expect(quick.quickItems()[0].copiedFrom).toBe("t1");
	});

	it("keeps its panel geometry in a separate key from its items", async () => {
		const quick = await fresh(quickModule);

		quick.addQuickItem("an item");
		quick.setQuickListPanel({ ...quick.readQuickListPanel(), open: true });

		expect(storage.dump()["thrive:quicklist"]).toBeDefined();
		expect(storage.dump()["thrive:quicklist-panel"]).toBeDefined();
		expect(quick.quickListPanel().open).toBe(true);
	});
});

// ---------------------------------------------------------------------------
// calendarItems -- labels, urgent, custom events
// ---------------------------------------------------------------------------

describe("calendarItems stores", () => {
	it("labels an item and forgets an emptied label", async () => {
		const items = await fresh(itemsModule);

		items.setItemLabel("asg-12", "  thesis  ");
		expect(items.itemLabels()).toEqual({ "asg-12": "thesis" });

		items.setItemLabel("asg-12", "   ");
		expect(items.itemLabels()).toEqual({});
	});

	it("stores the absence rather than false for urgent", async () => {
		const items = await fresh(itemsModule);

		items.setItemUrgent("asg-12", true);
		expect(items.itemUrgent()).toEqual({ "asg-12": true });

		items.setItemUrgent("asg-12", false);
		expect(items.itemUrgent()).toEqual({});
	});

	it("can annotate a row the student does not own", async () => {
		// The reason these are keyed by calendar item id: an assignment and a
		// booked appointment have nowhere on the server to record either flag.
		const items = await fresh(itemsModule);

		items.setItemUrgent("asg-12", true);
		items.setItemLabel("apt-3", "advising");

		expect(items.itemUrgent()["asg-12"]).toBe(true);
		expect(items.itemLabels()["apt-3"]).toBe("advising");
	});

	it("adds a custom event with a derived id", async () => {
		const items = await fresh(itemsModule);

		const id = items.addCustomEvent({ title: "Coffee", dayKey: "2026-08-19" });

		expect(id).toMatch(/^custom-\d+$/);
		expect(items.customEvents()).toHaveLength(1);
		expect(items.customEvents()[0].title).toBe("Coffee");
	});

	it("updates a custom event and ignores an unknown id", async () => {
		const items = await fresh(itemsModule);
		const id = items.addCustomEvent({ title: "Coffee", dayKey: "2026-08-19" });

		items.updateCustomEvent(id, { title: "Coffee with Shankar" });
		expect(items.customEvents()[0].title).toBe("Coffee with Shankar");

		expect(() => items.updateCustomEvent("nope", { title: "x" })).not.toThrow();
		expect(items.customEvents()).toHaveLength(1);
	});

	it("deleting a custom event takes its label and urgent flag with it", async () => {
		/*
		 * Otherwise both overrides orphan against an id that no longer exists, and
		 * would silently reattach if the id were ever reused. Note the key: the
		 * annotation stores use the CALENDAR item id, which for a custom event is
		 * `custom-${event.id}`.
		 */
		const items = await fresh(itemsModule);
		const id = items.addCustomEvent({ title: "Coffee", dayKey: "2026-08-19" });

		items.setItemLabel(`custom-${id}`, "personal");
		items.setItemUrgent(`custom-${id}`, true);

		items.deleteCustomEvent(id);

		expect(items.customEvents()).toEqual([]);
		expect(items.itemLabels()).toEqual({});
		expect(items.itemUrgent()).toEqual({});
	});
});

// ---------------------------------------------------------------------------
// The annotations, applied over a real merge
// ---------------------------------------------------------------------------

describe("mergedSchedule applies the annotations over every row", () => {
	/** A server row the student does not own, so the annotations have to reach it. */
	function assignment(over: Partial<ScheduleItem> = {}) {
		return {
			id: "asg-12",
			category: "assignment" as const,
			title: "Case memo",
			dayKey: "2026-08-17",
			timeLabel: "11:59 PM",
			detail: "MGT 253",
			sortMinutes: 1439,
			allDay: false,
			...over,
		};
	}

	async function merge(row: ReturnType<typeof assignment>) {
		const { mergedSchedule } = await import("$lib/calendarSources");
		return mergedSchedule({ dated: [row], recurring: [] }, []).data.dated[0];
	}

	it("puts a label on a row the student does not own", async () => {
		const items = await fresh(itemsModule);
		items.setItemLabel("asg-12", "capstone");

		expect((await merge(assignment())).label).toBe("capstone");
	});

	it("puts urgent on one too", async () => {
		const items = await fresh(itemsModule);
		items.setItemUrgent("asg-12", true);

		expect((await merge(assignment())).urgent).toBe(true);
	});

	it("suppresses urgent on a done row", async () => {
		// A finished thing is not urgent, and a coral pill on a struck-through row
		// is the contradiction the reserved palette exists to prevent.
		const items = await fresh(itemsModule);
		items.setItemUrgent("asg-12", true);

		expect((await merge(assignment({ done: true }))).urgent).toBeUndefined();
	});

	it("suppresses urgent a row ARRIVED with, when that row is done", async () => {
		/*
		 * The case the old `if (!label && !isUrgent) return item` shortcut got wrong
		 * once the done-suppression moved into `urgentFor`: nothing is overridden, so
		 * both resolved values are falsy, so the row was returned untouched -- still
		 * carrying the flag the suppression exists to remove.
		 *
		 * Unreachable through today's mappers, since only custom events arrive
		 * carrying `urgent` and none of them is tickable. Pinned anyway, because
		 * that is a property of the mappers rather than of this function.
		 */
		await fresh(itemsModule);

		const result = await merge(assignment({ urgent: true, done: true }));

		expect(result.urgent).toBeUndefined();
	});

	it("returns the row itself when nothing was said about it", async () => {
		// The identity case, and the reason for the shortcut in the first place:
		// most rows on a day carry no annotation and should not be copied.
		await fresh(itemsModule);
		const row = assignment();

		expect(await merge(row)).toBe(row);
	});
});

// ---------------------------------------------------------------------------
// ignoredEvents -- the third key space
// ---------------------------------------------------------------------------

describe("ignoredEvents store", () => {
	it("keys on exactly the id it is handed, and normalises nothing", async () => {
		const ignored = await fresh(ignoredModule);

		// A raw `Event.id`, which is what Home holds. Stored verbatim: the store
		// used to strip a prefix here, turning this into "3-1".
		ignored.setEventIgnored("evt-3-1", true);

		expect(ignored.ignoredEvents()).toEqual({ "evt-3-1": true });
	});

	/*
	 * -----------------------------------------------------------------------
	 * THE CROSS-SURFACE TEST. Phase 7a, closing BUGS.md's HIGH defect.
	 *
	 * The bug this replaces hid behind TWO ONE-SIDED TESTS THAT BOTH PASSED:
	 * one asserted the map was keyed "3-1", the other fed `filterSchedule` ids
	 * keyed "evt-3-1". Each was true of its own surface. Together they could not
	 * both be right, and nothing was looking at both at once.
	 *
	 * So these cases deliberately do not test the store against itself. Each one
	 * writes through the path ONE surface really uses and reads through the path
	 * the OTHER really uses:
	 *
	 *   Home      writes `ignoreEvents.ignore(event.id)`  -- a raw Event.id
	 *             reads  `isEventIgnored(event.id, map)`
	 *   Calendar  writes `setEventIgnored(eventIdOf(item.id))` at its boundary
	 *             reads  `filterSchedule(data, { ignoredEventIds: keys })`
	 *
	 * A test that only round-trips one of those pairs cannot fail on a key-space
	 * split, however carefully it is written.
	 * -----------------------------------------------------------------------
	 */
	describe("one key space, asserted across BOTH surfaces", () => {
		/** The calendar item id for raw event `evt-3-1`. Doubly prefixed. */
		const ITEM_ID = "evt-evt-3-1";
		/** The raw `Event.id`, which is what Home holds. */
		const RAW_ID = "evt-3-1";

		/** The row the calendar renders for that event. */
		const row: ScheduleItem = {
			id: ITEM_ID,
			category: "club",
			title: "Product Club Mixer",
			timeLabel: "5:00 PM",
			detail: "Rady Commons",
			sortMinutes: 1020,
			allDay: false
		};

		/** Exactly what `CalendarView` does: keys straight into the filter. */
		async function calendarSeesIt(ignoredMap: Record<string, true>) {
			const { filterSchedule } = await import("$lib/schedule");
			const result = filterSchedule(
				{ dated: [{ ...row, dayKey: "2026-08-17" }], recurring: [] },
				{ hidden: [], showDone: true, ignoredEventIds: Object.keys(ignoredMap) }
			);
			return result.dated.length > 0;
		}

		it("Home ignoring an event hides it on the calendar", async () => {
			const ignored = await fresh(ignoredModule);
			const { ignoreEvents } = await import("$lib/ignoreUndo.svelte");

			expect(await calendarSeesIt(ignored.ignoredEvents())).toBe(true);

			// Home's real write path, with the raw id off an `Event`.
			ignoreEvents.ignore(RAW_ID, "Product Club Mixer");

			expect(await calendarSeesIt(ignored.ignoredEvents())).toBe(false);
			ignoreEvents.clear();
		});

		it("the calendar ignoring an event hides it on Home", async () => {
			const ignored = await fresh(ignoredModule);

			// The calendar's real write path: normalise the item id ONCE, at the
			// boundary, then store. This is the only sanctioned `eventIdOf` call.
			ignored.setEventIgnored(ignored.eventIdOf(ITEM_ID), true);

			// Home's real read path, with the raw id and no stripping.
			expect(ignored.isEventIgnored(RAW_ID, ignored.ignoredEvents())).toBe(true);
		});

		it("both surfaces write the SAME key, so undo on either reaches the other", async () => {
			const ignored = await fresh(ignoredModule);
			const { ignoreEvents } = await import("$lib/ignoreUndo.svelte");

			// Home ignores...
			ignoreEvents.ignore(RAW_ID, "Product Club Mixer");
			const fromHome = Object.keys(ignored.ignoredEvents());

			// ...and the calendar's un-ignore, built from the item id, clears it.
			// If the two keys differed this would leave the original behind.
			ignored.setEventIgnored(ignored.eventIdOf(ITEM_ID), false);

			expect(fromHome).toEqual([RAW_ID]);
			expect(ignored.ignoredEvents()).toEqual({});
			expect(await calendarSeesIt(ignored.ignoredEvents())).toBe(true);
			ignoreEvents.clear();
		});

		it("neither surface can write the mangled key the old code produced", async () => {
			const ignored = await fresh(ignoredModule);
			const { ignoreEvents } = await import("$lib/ignoreUndo.svelte");

			ignoreEvents.ignore(RAW_ID, "Product Club Mixer");
			ignored.setEventIgnored(ignored.eventIdOf(ITEM_ID), true);

			// One key, not two. "3-1" was Home's old key and is now unreachable.
			expect(Object.keys(ignored.ignoredEvents())).toEqual([RAW_ID]);
			ignoreEvents.clear();
		});
	});

	it("un-ignoring deletes rather than storing false", async () => {
		// Which is why undo restores a row to its original position: ordering was
		// never touched, only the presence of a key.
		const ignored = await fresh(ignoredModule);

		ignored.setEventIgnored("evt-3-1", true);
		ignored.setEventIgnored("evt-3-1", false);

		expect(ignored.ignoredEvents()).toEqual({});
	});

	it("counts and clears", async () => {
		const ignored = await fresh(ignoredModule);

		ignored.setEventIgnored("evt-1", true);
		ignored.setEventIgnored("evt-2", true);
		expect(ignored.ignoredCount(ignored.ignoredEvents())).toBe(2);

		ignored.clearIgnoredEvents();
		expect(ignored.ignoredEvents()).toEqual({});
		expect(ignored.ignoredCount(ignored.ignoredEvents())).toBe(0);
	});

	it("is empty until hydrated", async () => {
		const ignored = await fresh(ignoredModule, {
			"thrive:ignored-events": '{"3-1":true}',
		});

		expect(ignored.ignoredEvents()).toEqual({});
	});
});

describe("the three key spaces stay separate", () => {
	it("the same id in all three stores means three different things", async () => {
		/*
		 * `evt-3-1` as a task id, as a calendar item id, and as an event id are
		 * three unrelated facts. Merging any two of these stores is the exact
		 * shape of the bug the ignore store was refactored to avoid: two stores
		 * wearing one localStorage key.
		 */
		vi.resetModules();
		storage = installStorage();

		const edits = await import("$lib/userEdits.svelte");
		const items = await import("$lib/calendarItems");
		const ignored = await import("$lib/ignoredEvents");

		const task: Task = {
			id: "evt-3-1",
			title: "a task that happens to share the id",
			dueDate: new Date(2026, 7, 17, 9, 0).toISOString(),
			source: "admin",
			priority: "low",
			done: false,
			subtasks: [],
		};

		edits.setTaskDone(task, true);
		items.setItemLabel("evt-3-1", "a label on a calendar row");
		ignored.setEventIgnored("evt-3-1", true);

		expect(edits.taskDoneOverrides()).toEqual({ "evt-3-1": true });
		expect(items.itemLabels()).toEqual({ "evt-3-1": "a label on a calendar row" });
		expect(ignored.ignoredEvents()).toEqual({ "evt-3-1": true });

		/*
		 * All three now hold the identical STRING, and that is the point rather
		 * than a problem.
		 *
		 * This case used to lean on the ignore store's normaliser as the thing
		 * separating the spaces -- it asserted `{"3-1": true}` under the comment
		 * "normalised on the way in, which is what makes this a different space".
		 * That was the defect wearing the costume of a design. A key space is
		 * separate because it is a different localStorage key holding a different
		 * KIND of fact, not because one of the three mangles its input.
		 *
		 * What actually distinguishes the calendar's space from the event space is
		 * that ONE event yields two different strings -- `evt-evt-3-1` as a
		 * calendar item id, `evt-3-1` as a raw `Event.id` -- and the boundary
		 * converts between them exactly once. Asserted below.
		 */
		expect(ignored.eventIdOf("evt-evt-3-1")).toBe("evt-3-1");
		expect(items.itemLabels()["evt-evt-3-1"]).toBeUndefined();

		// Three distinct localStorage keys, no overlap.
		expect(Object.keys(storage.dump()).sort()).toEqual([
			"thrive:ignored-events",
			"thrive:item-labels",
			"thrive:task-done",
		]);
	});
});

// ---------------------------------------------------------------------------
// tickItem -- writing back through the attached source row
// ---------------------------------------------------------------------------

describe("tickItem writes to the store the row came from", () => {
	function scheduleItem(over: Partial<ScheduleItem> = {}): ScheduleItem {
		return {
			id: "x",
			category: "task",
			title: "Item",
			timeLabel: "9:30 AM",
			detail: "",
			sortMinutes: 570,
			allDay: false,
			...over,
		};
	}

	it("ticks a task through userEdits", async () => {
		vi.resetModules();
		storage = installStorage();
		const { tickItem } = await import("$lib/tickItem");
		const edits = await import("$lib/userEdits.svelte");

		const task: Task = {
			id: "t1",
			title: "Submit peer review",
			dueDate: new Date(2026, 7, 17, 14, 30).toISOString(),
			source: "class",
			priority: "high",
			done: false,
			subtasks: [],
		};

		tickItem(scheduleItem({ task }), true);

		expect(edits.taskDoneOverrides()).toEqual({ t1: true });
	});

	it("ticks a self-added task the server has never seen", async () => {
		// The bug that started all of this: an id-based lookup could never resolve
		// a task that is not in the server's array. The attached row makes
		// provenance irrelevant.
		vi.resetModules();
		storage = installStorage();
		const { tickItem } = await import("$lib/tickItem");
		const edits = await import("$lib/userEdits.svelte");

		const own: Task = {
			id: "own-1755300000000",
			title: "Mine",
			dueDate: new Date(2026, 7, 17, 9, 0).toISOString(),
			source: "admin",
			priority: "medium",
			done: false,
			subtasks: [],
		};
		edits.addTask(own);

		tickItem(scheduleItem({ task: own }), true);

		expect(edits.taskDoneOverrides()).toEqual({ "own-1755300000000": true });
	});

	it("ticks a to-do through quickList", async () => {
		vi.resetModules();
		storage = installStorage();
		const { tickItem } = await import("$lib/tickItem");
		const quick = await import("$lib/quickList");

		quick.addQuickItem("Email Amber");
		const quickItem = quick.quickItems()[0];

		tickItem(scheduleItem({ category: "todo", quickItem }), true);

		expect(quick.quickItems()[0].done).toBe(true);
	});

	it("does nothing when the state already matches", async () => {
		vi.resetModules();
		storage = installStorage();
		const { tickItem } = await import("$lib/tickItem");
		const quick = await import("$lib/quickList");

		quick.addQuickItem("Email Amber");
		const quickItem = quick.quickItems()[0];

		tickItem(scheduleItem({ category: "todo", quickItem }), false);

		expect(quick.quickItems()[0].done).toBe(false);
	});

	it("is a no-op for a row with no source attached", async () => {
		vi.resetModules();
		storage = installStorage();
		const { tickItem } = await import("$lib/tickItem");
		const edits = await import("$lib/userEdits.svelte");

		expect(() => tickItem(scheduleItem({ category: "class" }), true)).not.toThrow();
		expect(edits.taskDoneOverrides()).toEqual({});
	});
});
