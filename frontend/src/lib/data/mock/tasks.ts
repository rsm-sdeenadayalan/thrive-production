import type { Task } from "../types";
import { at, FRI, MON, THU, upcomingWeekday, WED } from "./relative-dates";

/**
 * Ten tasks spread deliberately across urgency states, so Home always has
 * something overdue, something due today, a filled week, and a Done group.
 */
export function buildMockTasks(): Task[] {
  return [
    // --- Overdue ---------------------------------------------------------
    {
      id: "tsk-001",
      title: "Submit peer review",
      dueDate: at(-2, 23, 59),
      source: "class",
      priority: "high",
      done: false,
      courseId: "crs-253",
      courseCode: "MGT 253",
      subtasks: [],
    },

    // --- Due today -------------------------------------------------------
    {
      id: "tsk-002",
      title: "Lab 4: SQL joins",
      dueDate: at(0, 23, 59),
      source: "class",
      priority: "high",
      done: false,
      courseId: "crs-100",
      courseCode: "MGT 100",
      subtasks: [
        { id: "tsk-002-a", title: "Inner and outer joins", done: true },
        { id: "tsk-002-b", title: "Self joins exercise", done: false },
      ],
    },
    {
      id: "tsk-003",
      title: "Career Fair registration closes",
      dueDate: at(0, 17, 0),
      source: "career",
      priority: "medium",
      done: false,
      subtasks: [],
    },

    // --- This week -------------------------------------------------------
    {
      id: "tsk-004",
      title: "Problem Set 3",
      dueDate: upcomingWeekday(FRI, { hour: 23, minute: 59 }),
      source: "class",
      priority: "high",
      done: false,
      courseId: "crs-142",
      courseCode: "MGT 142",
      subtasks: [
        { id: "tsk-004-a", title: "Fit the baseline model", done: true },
        { id: "tsk-004-b", title: "Cross-validate", done: false },
        { id: "tsk-004-c", title: "Write up results", done: false },
      ],
    },
    {
      id: "tsk-005",
      title: "Dashboard project checkpoint",
      dueDate: upcomingWeekday(MON, { hour: 23, minute: 59 }),
      source: "class",
      priority: "medium",
      done: false,
      courseId: "crs-253",
      courseCode: "MGT 253",
      subtasks: [],
    },
    {
      id: "tsk-006",
      title: "Upload updated resume to CMC",
      dueDate: upcomingWeekday(WED, { hour: 17, minute: 0 }),
      source: "career",
      priority: "medium",
      done: false,
      subtasks: [
        { id: "tsk-006-a", title: "Add capstone bullet", done: false },
        { id: "tsk-006-b", title: "Career center review", done: false },
      ],
    },
    {
      id: "tsk-007",
      title: "Capstone team sync",
      dueDate: upcomingWeekday(THU, { hour: 16, minute: 0 }),
      source: "admin",
      priority: "low",
      done: false,
      subtasks: [],
    },
    {
      id: "tsk-008",
      title: "Read chapter 6",
      dueDate: upcomingWeekday(THU, { hour: 23, minute: 59 }),
      source: "class",
      priority: "low",
      done: false,
      courseId: "crs-256",
      courseCode: "MGT 256",
      subtasks: [],
    },

    // --- Done ------------------------------------------------------------
    {
      id: "tsk-009",
      title: "Watch orientation module",
      dueDate: at(-6, 23, 59),
      source: "admin",
      priority: "low",
      done: true,
      subtasks: [],
    },
    {
      id: "tsk-010",
      title: "Set up GitHub",
      dueDate: at(-5, 23, 59),
      source: "admin",
      priority: "medium",
      done: true,
      subtasks: [],
    },
  ];
}
