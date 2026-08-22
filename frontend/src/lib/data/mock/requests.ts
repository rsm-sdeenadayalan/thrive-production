import type { CourseRequest } from "../types";
import { at } from "./relative-dates";

/**
 * In-memory request store.
 *
 * Same shape and same caveats as the appointments store: survives across
 * requests in the running server, resets on restart or hot reload, shared by
 * everyone (MIGRATION.md section 9 defect 1). It exists so the flow behaves
 * like a real one end to end while the actual TSS integration is still
 * missing.
 */
interface RequestStore {
  requests: CourseRequest[];
  /** Whether the student has "linked" their record to TSS this session. */
  tssConnected: boolean;
  nextId: number;
  seeded: boolean;
}

const store: RequestStore = {
  requests: [],
  tssConnected: false,
  nextId: 1,
  seeded: false,
};

/**
 * One historical request, so "My requests" isn't empty on a cold demo and the
 * status chips have something other than "submitted" to show.
 *
 * Seeded lazily rather than at module load, because the dates are relative to
 * "now" and module load may be minutes or hours earlier.
 */
function seedOnce() {
  if (store.seeded) return;
  store.seeded = true;

  store.requests.push({
    id: "req-000",
    type: "out of major",
    course: "MGT 256 · Marketing Analytics",
    reason:
      "Marketing Analytics sits outside the MSBA core but supports my goal of moving into a data science role on a marketing team.",
    status: "approved",
    submittedAt: at(-24, 14, 20),
    prefill: {
      studentName: "Merna",
      program: "MSBA",
      track: "11 month",
      term: "Summer 2026",
      currentCourses: ["MGT 142", "MGT 100", "MGT 253"],
      currentUnits: 12,
      unitsCompleted: 34,
      unitsRequired: 52,
    },
  });
}

export function readRequestStore(): RequestStore {
  seedOnce();
  return store;
}

/**
 * The next request id.
 *
 * ## The id-collision hazard this port inherits
 *
 * `nextId` counts from 1 with no knowledge of what `seedOnce` put in the
 * store. It works today only because the seed is deliberately numbered
 * `req-000`, leaving `req-001` free -- the two are kept in step by hand and
 * nothing checks them.
 *
 * Seed a second historical request as `req-001` and the first request the
 * student creates gets that same id. Nothing throws: `getMyRequests` returns
 * both, and `submitRequest` picks whichever `find` reaches first, so
 * submitting the new request can silently flip the status of the seeded one.
 *
 * The resume store solves it the same manual way, starting `nextId` at 4 past
 * three seeded versions. Django's sequence removes the whole class of bug; a
 * seed added before then must move `nextId` past it.
 */
export function nextRequestId(): string {
  return `req-${String(store.nextId++).padStart(3, "0")}`;
}
