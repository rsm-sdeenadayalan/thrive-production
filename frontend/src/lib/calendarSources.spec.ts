import { describe, expect, it } from "vitest";

import { taskToItem, todoToItem } from "$lib/calendarSources";
import type { QuickItem } from "$lib/quickList";
import type { ScheduleItem } from "$lib/schedule";
import { isTickable } from "$lib/tickItem";
import type { Task } from "$lib/data";

/**
 * The mapping half of the merge layer.
 *
 * `useMergedSchedule` itself is a hook over four localStorage stores and needs
 * a DOM to exercise. These two functions are where the actual decisions live --
 * which day a thing lands on, whether it is all-day, whether a bad date takes
 * the page down -- so they are what is worth pinning.
 */

function task(over: Partial<Task> = {}): Task {
  return {
    id: "t1",
    title: "Submit peer review",
    // Local parts, deliberately: `new Date("2026-08-17")` parses as UTC and
    // lands on the 16th for anyone behind it. Every fixture here uses a full
    // local instant for the same reason the app does.
    dueDate: new Date(2026, 7, 17, 14, 30).toISOString(),
    source: "class",
    priority: "high",
    done: false,
    subtasks: [],
    ...over,
  };
}

describe("taskToItem", () => {
  it("lands on the local day, not the UTC one", () => {
    const item = taskToItem(task(), false);
    expect(item?.dayKey).toBe("2026-08-17");
  });

  it("is never all-day, so it sorts against classes by time", () => {
    const item = taskToItem(task(), false);
    expect(item?.allDay).toBe(false);
    expect(item?.sortMinutes).toBe(14 * 60 + 30);
  });

  it("carries done, priority and course through", () => {
    const item = taskToItem(task({ courseCode: "MGT 253" }), true);
    expect(item?.done).toBe(true);
    expect(item?.priority).toBe("high");
    expect(item?.courseCode).toBe("MGT 253");
    expect(item?.detail).toBe("MGT 253");
  });

  it("prefixes the id so it cannot collide with a server row", () => {
    expect(taskToItem(task({ id: "abc" }), false)?.id).toBe("task-abc");
  });

  it("returns null for an unparseable date rather than throwing", () => {
    expect(taskToItem(task({ dueDate: "not a date" }), false)).toBeNull();
  });

  it("uses the task category, so filters and dots agree", () => {
    expect(taskToItem(task(), false)?.category).toBe("task");
  });
});

function quick(over: Partial<QuickItem> = {}): QuickItem {
  return {
    id: "q1",
    title: "Email Amber",
    done: false,
    createdAt: 0,
    dueDate: new Date(2026, 7, 18, 9, 0).toISOString(),
    ...over,
  };
}

describe("todoToItem", () => {
  it("is all-day, because the picker never offers a time", () => {
    const item = todoToItem(quick());
    expect(item?.allDay).toBe(true);
    expect(item?.sortMinutes).toBe(0);
    expect(item?.timeLabel).toBe("All day");
  });

  it("lands on the local day", () => {
    expect(todoToItem(quick())?.dayKey).toBe("2026-08-18");
  });

  it("prefixes the id", () => {
    expect(todoToItem(quick())?.id).toBe("todo-q1");
  });

  it("carries done through", () => {
    expect(todoToItem(quick({ done: true }))?.done).toBe(true);
  });

  it("returns null for an unparseable date", () => {
    expect(todoToItem(quick({ dueDate: "nope" }))).toBeNull();
  });

  it("returns null when the to-do has no date at all", () => {
    expect(todoToItem(quick({ dueDate: undefined }))).toBeNull();
  });
});

/**
 * The whole point of the fix: a tickable row carries the object that has to be
 * written back, so nothing downstream has to find it by parsing an id.
 */
describe("the attached source row", () => {
  it("a task row carries its Task", () => {
    const source = task();
    const item = taskToItem(source, false);
    expect(item?.task).toBe(source);
    expect(item?.quickItem).toBeUndefined();
  });

  it("carries a task the server has never seen", () => {
    // This is the bug that started this: a self-added task is not in the
    // server's array, so an id-based lookup could never resolve it. Attaching
    // the object makes provenance irrelevant.
    const selfAdded = task({ id: "own-1755300000000" });
    expect(taskToItem(selfAdded, false)?.task?.id).toBe("own-1755300000000");
  });

  it("a to-do row carries its QuickItem", () => {
    const source = quick();
    const item = todoToItem(source);
    expect(item?.quickItem).toBe(source);
    expect(item?.task).toBeUndefined();
  });

  it("isTickable is true for both and false for anything else", () => {
    expect(isTickable(taskToItem(task(), false)!)).toBe(true);
    expect(isTickable(todoToItem(quick())!)).toBe(true);

    // A class: no source row, so nothing to write back to.
    expect(
      isTickable({
        id: "c1",
        category: "class",
        title: "MGT 142",
        timeLabel: "9:30 AM",
        detail: "",
        sortMinutes: 570,
        allDay: false,
      }),
    ).toBe(false);
  });

  /**
   * `DaySection` renders `done / tickable`, not `done / total`.
   *
   * The count is computed in the component, so this pins the arithmetic it
   * depends on rather than the JSX: a group holding one finished task and two
   * classes has one tickable thing, not three.
   */
  it("counts tickables separately from total, for the section fraction", () => {
    const rows: ScheduleItem[] = [
      taskToItem(task({ id: "a" }), true)!,
      {
        id: "c1",
        category: "class" as const,
        title: "MGT 142",
        timeLabel: "9:30 AM",
        detail: "",
        sortMinutes: 570,
        allDay: false,
      },
      {
        id: "c2",
        category: "class" as const,
        title: "MGT 100",
        timeLabel: "11:00 AM",
        detail: "",
        sortMinutes: 660,
        allDay: false,
      },
    ];

    const tickables = rows.filter(isTickable);
    const done = tickables.filter((row) => row.done === true).length;

    expect(rows).toHaveLength(3);
    expect(tickables).toHaveLength(1);
    expect(`${done}/${tickables.length}`).toBe("1/1");
  });

  it("is not fooled by a done flag with no source row", () => {
    // The agenda used to build exactly this shape for undated to-dos: a `done`
    // value and nothing to write it to, which rendered a checkbox that did
    // nothing when clicked.
    expect(
      isTickable({
        id: "q9",
        category: "todo",
        title: "Orphan",
        timeLabel: "",
        detail: "",
        sortMinutes: 0,
        allDay: true,
        done: false,
      }),
    ).toBe(false);
  });
});
