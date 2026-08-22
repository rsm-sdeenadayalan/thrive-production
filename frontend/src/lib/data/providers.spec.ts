import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The provider layer's invariants.
 *
 * These do not test the fixtures' contents -- those are demo data and will be
 * thrown away. They test the four properties that have to survive the swap to
 * Django, plus the store behaviours that have bitten before.
 *
 * ## Every test gets its own module registry
 *
 * The three stores are plain module-scope objects, shared by every importer and
 * wiped only on restart (MIGRATION.md section 9 defect 1). Under a single
 * registry, a test that books an appointment changes what the next test sees,
 * and the suite passes or fails on file order.
 *
 * `freshData()` calls `vi.resetModules()` and re-imports, so each test gets
 * untouched stores. This is deliberately done from the test side: adding a
 * `resetStores()` export to make the suite convenient would put a function in
 * the production surface that only tests use, and it would still be there long
 * after Django made the stores irrelevant.
 *
 * ## Imports go through the public entry point
 *
 * Everything below imports `./index`, never `./providers` or `./mock/*`, so
 * these tests fail if the barrel stops re-exporting something the app needs.
 * `./latency` is imported directly because it is deliberately NOT public -- the
 * knob exists for this suite and for a developer chasing a loading state.
 */

type DataModule = typeof import("./index");

async function freshData(): Promise<DataModule> {
  vi.resetModules();
  // Same reset registry, so the instance `./index` imports is the one we set.
  const { setMockLatencyMs } = await import("./latency");
  setMockLatencyMs(0);
  return import("./index");
}

/**
 * Tuesday 15 September 2026, 08:00 local.
 *
 * Built from local parts so the suite does not depend on the runner's
 * timezone. 08:00 is before every published slot, so nothing is filtered out
 * as already past -- which is what makes the counts below assertable at all.
 *
 * A Tuesday keeps the five-business-day window inside one week, which is what
 * makes the day indices above predictable. (Phase 8 briefly raised the window to
 * 25 business days, where the weekday stopped mattering; the chip strip brought
 * it back to five.)
 */
const FROZEN = new Date(2026, 8, 15, 8, 0, 0);

/**
 * Slot ids at the frozen instant, for `adv-gsa` whose times are
 * 09:30 / 10:30 / 11:30 / 14:00 / 15:00.
 *
 * `isTaken` hashes `advisorId.length * 7 + dayIndex * 3 + timeIndex * 5` and
 * takes the slot when the result is divisible by 4. For adv-gsa on day 0 that
 * is 49, 54, 59, 64, 69 -- so only the 14:00 lands on a multiple of 4.
 */
const FREE_SLOT = "slot-adv-gsa-0-0";
const OTHER_FREE_SLOT = "slot-adv-gsa-0-1";
const SEEDED_TAKEN_SLOT = "slot-adv-gsa-0-3";

beforeEach(() => {
  // Date only. setTimeout stays real, so `resolveAfterDelay` still resolves.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(FROZEN);
});

afterEach(() => {
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Property 1 -- the seam is the signature
// ---------------------------------------------------------------------------

describe("the provider surface", () => {
  const PROVIDERS = [
    "getStudent",
    "getCourses",
    "getSyllabi",
    "getAssignments",
    "getTasks",
    "getEvents",
    "getDegreeProgress",
    "getProgramTimeline",
    "getResources",
    "getAdvisors",
    "getSlots",
    "getMyAppointments",
    "bookAppointment",
    "cancelAppointment",
    "getRequestPrefill",
    "createRequest",
    "submitRequest",
    "getMyRequests",
    "getTssConnection",
    "connectTss",
    "getSkills",
    "getResumeVersions",
    "getCurrentResume",
    "generateNewVersion",
    "setCurrentVersion",
    "getConversations",
    "getConversation",
  ] as const;

  it("exports all 27 providers and SlotUnavailableError from $lib/data", async () => {
    const data = await freshData();

    // 25 through Phase 7; the two Ask THRIVE conversation reads landed in
    // Phase 9. The literal is the pin -- widening the seam should be a decision.
    expect(PROVIDERS).toHaveLength(27);
    for (const name of PROVIDERS) {
      expect(typeof data[name], `${name} is missing from the barrel`).toBe(
        "function",
      );
    }
    expect(typeof data.SlotUnavailableError).toBe("function");
  });

  it("exports the request label maps, so no caller reaches into mock/", async () => {
    // MIGRATION.md section 9 defect 11: degree/requests/page.tsx imported these
    // straight from lib/data/mock/requests, the one boundary violation in the
    // Next tree. They are public here instead.
    const data = await freshData();

    expect(data.requestTypeLabel.enroll).toBe("Enroll in a course");
    expect(data.requestTypeHelp["reduced load"]).toContain("fewer units");
  });

  it("keeps the mock internals and the latency knob out of the barrel", async () => {
    const data = await freshData();
    const leaked = [
      "readStore",
      "readRequestStore",
      "readResumeStore",
      "buildSlotsFor",
      "bookingDays",
      "nextAppointmentId",
      "nextRequestId",
      "nextVersionId",
      "mockStudent",
      "mockAdvisors",
      "mockSkills",
      "buildMockCourses",
      "buildMockConversations",
      "buildProgramTimeline",
      "resolveAfterDelay",
      "setMockLatencyMs",
    ];

    for (const name of leaked) {
      expect(name in data, `${name} should not be public`).toBe(false);
    }
  });

  it("returns a Promise from every provider", async () => {
    // Property 1: the signature must not change when the body becomes a Django
    // call, and "returns a Promise" is the load-bearing half of it.
    const data = await freshData();

    const calls: Promise<unknown>[] = [
      data.getStudent(),
      data.getCourses(),
      data.getSyllabi(),
      data.getAssignments(),
      data.getTasks(),
      data.getEvents(),
      data.getDegreeProgress(),
      data.getProgramTimeline(),
      data.getResources(),
      data.getAdvisors(),
      data.getSlots("adv-gsa"),
      data.getMyAppointments(),
      data.bookAppointment(FREE_SLOT, "why"),
      data.cancelAppointment("apt-001"),
      data.getRequestPrefill(),
      data.createRequest({ type: "enroll", course: "MGT 1", reason: "r" }),
      data.submitRequest("req-000"),
      data.getMyRequests(),
      data.getTssConnection(),
      data.connectTss(),
      data.getSkills(),
      data.getResumeVersions(),
      data.getCurrentResume(),
      data.generateNewVersion(),
      data.setCurrentVersion("res-001"),
      data.getConversations(),
      data.getConversation("conv-001"),
    ];

    expect(calls).toHaveLength(27);
    for (const call of calls) {
      expect(call).toBeInstanceOf(Promise);
    }

    await Promise.allSettled(calls);
  });
});

// ---------------------------------------------------------------------------
// Property 2 -- callers never receive a stored object
// ---------------------------------------------------------------------------

describe("returned objects are copies, not the stored record", () => {
  it("does not let a mutation to the student reach the fixture", async () => {
    const data = await freshData();

    const first = await data.getStudent();
    first.name = "Mutated";
    first.standing = "needsHelp";

    const second = await data.getStudent();
    expect(second.name).toBe("Merna");
    expect(second.standing).toBe("onTrack");
  });

  it("does not let a mutation to degree progress reach the fixture", async () => {
    // One of the four the Next version returned by reference -- section 9
    // defect 15.
    const data = await freshData();

    const first = await data.getDegreeProgress();
    first.unitsCompleted = 999;

    expect((await data.getDegreeProgress()).unitsCompleted).toBe(38);
  });

  it("does not let a mutation to an advisor or a resource reach the fixture", async () => {
    const data = await freshData();

    const [advisor] = await data.getAdvisors();
    advisor.name = "Mutated";
    const [resource] = await data.getResources();
    resource.title = "Mutated";

    expect((await data.getAdvisors())[0].name).toBe("Amber Hanna");
    expect((await data.getResources())[0].title).toBe(
      "Career Management Center",
    );
  });

  it("does not let a mutation to a skill reach the fixture", async () => {
    const data = await freshData();

    const [skill] = await data.getSkills();
    skill.name = "Mutated";

    expect((await data.getSkills())[0].name).toBe("SQL");
  });

  it("does not let a mutation to an appointment reach the store", async () => {
    // The real bug this property is named after: returning the stored object
    // meant a later mutation silently changed a record the caller already held.
    const data = await freshData();

    await data.bookAppointment(FREE_SLOT, "Course planning");

    const [held] = await data.getMyAppointments();
    held.status = "cancelled";
    held.reason = "Mutated";

    const [reread] = await data.getMyAppointments();
    expect(reread.status).toBe("confirmed");
    expect(reread.reason).toBe("Course planning");
  });

  it("does not let a mutation to a request reach the store", async () => {
    const data = await freshData();

    const [held] = await data.getMyRequests();
    held.status = "denied";

    expect((await data.getMyRequests())[0].status).toBe("approved");
  });

  it("does not let a mutation to a resume version reach the store", async () => {
    const data = await freshData();

    const [held] = await data.getResumeVersions();
    held.label = "Mutated";
    held.isCurrent = false;

    const [reread] = await data.getResumeVersions();
    expect(reread.label).toBe("Current term update");
    expect(reread.isCurrent).toBe(true);
  });

  it("shares nested arrays with the store -- a known, inherited limit", async () => {
    /*
     * The copies are shallow, exactly as they were in the Next app. Assigning
     * to a field on a returned object cannot reach the store; reaching into a
     * nested array can, because `{ ...version }` copies the reference.
     *
     * Pinned rather than fixed. Deepening the copy is a behaviour change beyond
     * a port, and leaving it undocumented is how it becomes a surprise later.
     * If someone deep-copies the store reads on purpose, this test fails and
     * says why -- delete it then.
     */
    const data = await freshData();

    const [held] = await data.getResumeVersions();
    const before = held.skills.length;
    held.skills.push({ id: "skl-fake", name: "Injected", source: "manual" });

    const [reread] = await data.getResumeVersions();
    expect(reread.skills).toHaveLength(before + 1);
    expect(reread.skills.at(-1)?.name).toBe("Injected");
  });
});

// ---------------------------------------------------------------------------
// Property 3 -- deterministic generation, never Math.random()
// ---------------------------------------------------------------------------

describe("generation is deterministic", () => {
  it("builds identical slots for the same advisor at the same instant", async () => {
    const data = await freshData();

    const first = await data.getSlots("adv-gsa");
    const second = await data.getSlots("adv-gsa");

    // BOOKING_WINDOW_DAYS business days x 5 published times. The literal is the
    // pin: changing the window should go red here and be confirmed, not
    // recomputed silently from the constant it is meant to be checking.
    expect(first).toHaveLength(25); // 5 business days x 5 times
    expect(second).toEqual(first);
  });

  it("mints slot ids as slot-<advisor>-<dayIndex>-<timeIndex>", async () => {
    // Ids have to be stable across requests: a booking is recorded against one
    // and has to still resolve on the next request, even though the slot list
    // is rebuilt from "today" every call.
    const data = await freshData();

    const slots = await data.getSlots("adv-gsa");

    expect(slots[0].id).toBe("slot-adv-gsa-0-0");
    // Day index 4 is the fifth business day, time index 4 the fifth slot.
    expect(slots.at(-1)?.id).toBe("slot-adv-gsa-4-4");
    for (const slot of slots) {
      expect(slot.id).toMatch(/^slot-adv-gsa-\d+-\d+$/);
    }
  });

  it("derives availability from the hash, not from chance", async () => {
    const data = await freshData();

    const slots = await data.getSlots("adv-gsa");
    const byId = new Map(slots.map((slot) => [slot.id, slot]));

    // 49 + 3*0 + 5*3 = 64, divisible by 4.
    expect(byId.get(SEEDED_TAKEN_SLOT)?.available).toBe(false);
    // 49 and 54 are not.
    expect(byId.get(FREE_SLOT)?.available).toBe(true);
    expect(byId.get(OTHER_FREE_SLOT)?.available).toBe(true);
  });

  it("builds identical events on repeated calls", async () => {
    const data = await freshData();

    const first = await data.getEvents();
    const second = await data.getEvents();

    expect(first.length).toBeGreaterThan(0);
    expect(second.map((event) => event.id)).toEqual(
      first.map((event) => event.id),
    );
    expect(second).toEqual(first);
  });

  it("contains no Math.random() anywhere in the data layer", async () => {
    /*
     * The guard behind the property. Math.random() in a fixture hands back a
     * different calendar on every render and desynchronises the server from the
     * client -- a hydration mismatch on the events grid or the slot picker,
     * which is exactly what the hash functions exist to avoid.
     */
    /*
     * Read through Vite's glob rather than node:fs -- this repo has no
     * @types/node, and `npm run check` is a gate. The spec files are excluded
     * because this one names the thing it forbids.
     */
    const sources = import.meta.glob<string>(
      ["./**/*.ts", "!./**/*.spec.ts"],
      { query: "?raw", import: "default", eager: true },
    );

    const files = Object.keys(sources);
    expect(files.length).toBeGreaterThan(10);

    /*
     * Comments are stripped first. Both hash functions carry a comment naming
     * Math.random() as the thing they exist to avoid, and those comments are
     * the most useful lines in the file -- a guard that forced them out would
     * be deleting the explanation to satisfy the check.
     */
    const stripComments = (source: string) =>
      source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

    const stripped = files.map((path) => stripComments(sources[path]));

    // The guard must not be able to pass by stripping everything: both hash
    // functions have to survive the strip for the absence of Math.random to
    // mean anything.
    const corpus = stripped.join("\n");
    expect(corpus).toContain("function isTaken");
    expect(corpus).toContain("dayOffset * 3");

    const offenders = files.filter((_, index) =>
      stripped[index].includes("Math.random"),
    );
    expect(offenders).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Property 4 -- fixtures dated relative to now
// ---------------------------------------------------------------------------

describe("fixtures are dated relative to now", () => {
  it("puts course deadlines ahead of the frozen clock", async () => {
    const data = await freshData();

    const courses = await data.getCourses();
    expect(courses).toHaveLength(4);
    for (const course of courses) {
      expect(Date.parse(course.nextAssignment.due)).toBeGreaterThan(
        FROZEN.getTime(),
      );
    }
  });

  it("keeps overdue and completed work behind it, so Home is never empty", async () => {
    const data = await freshData();

    const tasks = await data.getTasks();
    const overdue = tasks.filter(
      (task) => !task.done && Date.parse(task.dueDate) < FROZEN.getTime(),
    );

    expect(overdue.length).toBeGreaterThan(0);
    expect(tasks.some((task) => task.done)).toBe(true);
  });

  it("drops events that have already finished", async () => {
    // getEvents filters on the clock behind the provider boundary. When Django
    // lands this becomes a query; either way the read is server-side.
    const data = await freshData();

    for (const event of await data.getEvents()) {
      expect(
        Date.parse(event.end ?? event.start),
      ).toBeGreaterThanOrEqual(FROZEN.getTime());
    }
  });
});

// ---------------------------------------------------------------------------
// Shaping done behind the boundary
// ---------------------------------------------------------------------------

describe("shaping happens behind the provider boundary", () => {
  it("sorts assignments soonest due first", async () => {
    const data = await freshData();

    const assignments = await data.getAssignments();
    const dues = assignments.map((a) => Date.parse(a.dueDate));

    expect(assignments).toHaveLength(8);
    expect([...dues].sort((a, b) => a - b)).toEqual(dues);
  });

  it("sorts tasks by due date with completed ones last", async () => {
    const data = await freshData();

    const tasks = await data.getTasks();
    const firstDone = tasks.findIndex((task) => task.done);

    expect(firstDone).toBeGreaterThan(-1);
    expect(tasks.slice(firstDone).every((task) => task.done)).toBe(true);

    const openDues = tasks
      .slice(0, firstDone)
      .map((task) => Date.parse(task.dueDate));
    expect([...openDues].sort((a, b) => a - b)).toEqual(openDues);
  });

  it("derives the program timeline from the student, not from a stored field", async () => {
    const data = await freshData();

    const student = await data.getStudent();
    const timeline = await data.getProgramTimeline();

    // 17 month finishes on the optional Fall, one year after a 2026 start.
    expect(student.track).toBe("17 month");
    expect(timeline.expectedFinishTerm).toBe("Fall 2027");
    expect(timeline.track).toBe("17 month");
    expect(timeline.phases).toHaveLength(6);
    // The final Fall is required on this track, so the optional tag is gone.
    expect(timeline.phases.at(-1)?.optional).toBe(false);
  });

  it("derives the request prefill's unit count from the courses", async () => {
    const data = await freshData();

    const prefill = await data.getRequestPrefill();

    expect(prefill.currentUnits).toBe(14); // 4 + 4 + 4 + 2
    expect(prefill.currentCourses).toHaveLength(4);
    expect(prefill.studentName).toBe("Merna");
    expect(prefill.unitsRequired).toBe(52);
  });
});

// ---------------------------------------------------------------------------
// The booking store
// ---------------------------------------------------------------------------

describe("booking", () => {
  it("claims the slot it booked", async () => {
    const data = await freshData();

    const appointment = await data.bookAppointment(FREE_SLOT, "  Planning  ");

    expect(appointment.id).toBe("apt-001");
    expect(appointment.slotId).toBe(FREE_SLOT);
    expect(appointment.advisorId).toBe("adv-gsa");
    expect(appointment.status).toBe("confirmed");
    expect(appointment.reason).toBe("Planning"); // trimmed

    const slots = await data.getSlots("adv-gsa");
    expect(slots.find((slot) => slot.id === FREE_SLOT)?.available).toBe(false);
    // Only the booked one moves.
    expect(slots.find((slot) => slot.id === OTHER_FREE_SLOT)?.available).toBe(
      true,
    );
  });

  it("lists the booking as confirmed, soonest first", async () => {
    const data = await freshData();

    await data.bookAppointment(OTHER_FREE_SLOT, "second");
    await data.bookAppointment(FREE_SLOT, "first");

    const mine = await data.getMyAppointments();
    expect(mine).toHaveLength(2);
    expect(mine[0].slotId).toBe(FREE_SLOT); // 09:30 before 10:30
    expect(mine.every((a) => a.status === "confirmed")).toBe(true);
  });

  it("throws SlotUnavailableError on a double booking", async () => {
    const data = await freshData();

    await data.bookAppointment(FREE_SLOT, "mine");

    await expect(data.bookAppointment(FREE_SLOT, "also mine")).rejects.toThrow(
      data.SlotUnavailableError,
    );
    await expect(data.bookAppointment(FREE_SLOT, "also mine")).rejects.toThrow(
      "That time was just taken. Pick another.",
    );
    // The failed attempt did not create a record.
    expect(await data.getMyAppointments()).toHaveLength(1);
  });

  it("throws SlotUnavailableError for a slot the hash already marks taken", async () => {
    const data = await freshData();

    await expect(
      data.bookAppointment(SEEDED_TAKEN_SLOT, "reason"),
    ).rejects.toThrow(data.SlotUnavailableError);
  });

  it("throws SlotUnavailableError for a slot id that is not listed", async () => {
    const data = await freshData();

    await expect(
      data.bookAppointment("slot-adv-gsa-99-99", "reason"),
    ).rejects.toThrow("That time is no longer listed.");
    await expect(data.bookAppointment("nonsense", "reason")).rejects.toThrow(
      "That time is no longer listed.",
    );
  });
});

describe("cancelling", () => {
  it("releases the slot it claimed and drops out of the list", async () => {
    const data = await freshData();

    const appointment = await data.bookAppointment(FREE_SLOT, "Planning");
    const cancelled = await data.cancelAppointment(appointment.id);

    expect(cancelled?.status).toBe("cancelled");
    expect(await data.getMyAppointments()).toEqual([]);

    const slots = await data.getSlots("adv-gsa");
    expect(slots.find((slot) => slot.id === FREE_SLOT)?.available).toBe(true);
  });

  it("releases only the cancelled appointment's slot", async () => {
    /*
     * The reason `Appointment.slotId` exists. The Next version scanned the
     * claimed set for the first slot whose `start` matched the appointment's
     * and released that -- fine while no advisor publishes two simultaneous
     * slots, wrong the moment one does (section 9 defect 8). The current
     * fixtures give each advisor distinct times, so the old code would pass
     * this too; what the test pins is that the appointment carries the id, so
     * the release is exact rather than a guess that happens to be right.
     */
    const data = await freshData();

    const first = await data.bookAppointment(FREE_SLOT, "keep");
    const second = await data.bookAppointment(OTHER_FREE_SLOT, "cancel");

    expect(second.slotId).toBe(OTHER_FREE_SLOT);
    await data.cancelAppointment(second.id);

    const slots = await data.getSlots("adv-gsa");
    expect(slots.find((slot) => slot.id === OTHER_FREE_SLOT)?.available).toBe(
      true,
    );
    expect(slots.find((slot) => slot.id === FREE_SLOT)?.available).toBe(false);

    const mine = await data.getMyAppointments();
    expect(mine).toHaveLength(1);
    expect(mine[0].id).toBe(first.id);
  });

  it("returns null for an unknown appointment id", async () => {
    const data = await freshData();

    expect(await data.cancelAppointment("apt-nope")).toBeNull();
  });

  it("frees the slot for a fresh booking", async () => {
    const data = await freshData();

    const first = await data.bookAppointment(FREE_SLOT, "first");
    await data.cancelAppointment(first.id);
    const second = await data.bookAppointment(FREE_SLOT, "second");

    expect(second.id).toBe("apt-002");
    expect(second.slotId).toBe(FREE_SLOT);
  });
});

// ---------------------------------------------------------------------------
// The request store
// ---------------------------------------------------------------------------

describe("course action requests", () => {
  it("seeds one approved historical request, lazily", async () => {
    const data = await freshData();

    const requests = await data.getMyRequests();
    expect(requests).toHaveLength(1);
    expect(requests[0].id).toBe("req-000");
    expect(requests[0].status).toBe("approved");
    // Seeded on first read, not at module load, so the date is relative to now.
    expect(Date.parse(requests[0].submittedAt!)).toBeLessThan(FROZEN.getTime());
  });

  it("creates a draft numbered past the seed", async () => {
    /*
     * The id generator counts from 1 with no knowledge of the seed, and works
     * only because the seed is numbered req-000 by hand. If someone seeds a
     * req-001 without moving nextId, this test fails -- which is the point.
     */
    const data = await freshData();

    const request = await data.createRequest({
      type: "out of major",
      course: "  MGT 256  ",
      reason: "  supports my goal  ",
    });

    expect(request.id).toBe("req-001");
    expect(request.status).toBe("draft");
    expect(request.submittedAt).toBeNull();
    expect(request.course).toBe("MGT 256"); // trimmed
    expect(request.reason).toBe("supports my goal");
    // Prefill is snapshotted onto the request, not looked up later.
    expect(request.prefill.currentUnits).toBe(14);
  });

  it("floats drafts above submitted requests, then sorts newest first", async () => {
    const data = await freshData();

    await data.createRequest({ type: "enroll", course: "A", reason: "r" });

    const requests = await data.getMyRequests();
    expect(requests.map((r) => r.id)).toEqual(["req-001", "req-000"]);
  });

  it("moves a draft to submitted and stamps the time", async () => {
    const data = await freshData();

    const draft = await data.createRequest({
      type: "enroll",
      course: "A",
      reason: "r",
    });
    const submitted = await data.submitRequest(draft.id);

    expect(submitted?.status).toBe("submitted");
    expect(submitted?.submittedAt).toBe(FROZEN.toISOString());
  });

  it("is idempotent -- a second submit returns the record unchanged", async () => {
    const data = await freshData();

    const draft = await data.createRequest({
      type: "enroll",
      course: "A",
      reason: "r",
    });
    const first = await data.submitRequest(draft.id);

    // Move the clock so a re-stamp would be visible.
    vi.setSystemTime(new Date(2026, 8, 16, 9, 0, 0));
    const second = await data.submitRequest(draft.id);

    expect(second?.status).toBe("submitted");
    expect(second?.submittedAt).toBe(first?.submittedAt);
  });

  it("does not drag an approved request back to submitted", async () => {
    // The same guard, seen from the direction that matters: a double-posted
    // form must not undo a decision somebody already made.
    const data = await freshData();

    const result = await data.submitRequest("req-000");

    expect(result?.status).toBe("approved");
    expect((await data.getMyRequests())[0].status).toBe("approved");
  });

  it("returns null for an unknown request id", async () => {
    const data = await freshData();

    expect(await data.submitRequest("req-nope")).toBeNull();
  });

  it("connects to TSS", async () => {
    const data = await freshData();

    expect(await data.getTssConnection()).toBe(false);
    expect(await data.connectTss()).toBe(true);
    expect(await data.getTssConnection()).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// The resume store
// ---------------------------------------------------------------------------

describe("the living resume", () => {
  it("seeds three versions newest first, with the third current", async () => {
    const data = await freshData();

    const versions = await data.getResumeVersions();

    expect(versions.map((v) => v.id)).toEqual(["res-003", "res-002", "res-001"]);
    expect(versions[0].isCurrent).toBe(true);
    expect((await data.getCurrentResume())?.id).toBe("res-003");
  });

  it("generates res-004 and reports what it added", async () => {
    const data = await freshData();

    const { version, diff } = await data.generateNewVersion();

    expect(version.id).toBe("res-004");
    expect(version.isCurrent).toBe(true);
    // Everything the student has now, not just what was on res-003.
    expect(diff.addedSkills).toEqual([
      "Tableau",
      "Marketing analytics",
      "A/B testing",
    ]);
    expect(diff.addedCourses).toEqual(["MGT 256 · Marketing Analytics"]);
    expect(diff.summaryChanged).toBe(true);
    // Experience is student-authored, so it carries forward untouched.
    expect(version.experience.map((e) => e.id)).toEqual([
      "exp-capstone",
      "exp-ta",
    ]);
  });

  it("keeps every earlier version and clears their current flag", async () => {
    const data = await freshData();

    await data.generateNewVersion();
    const versions = await data.getResumeVersions();

    expect(versions).toHaveLength(4);
    expect(versions.filter((v) => v.isCurrent).map((v) => v.id)).toEqual([
      "res-004",
    ]);
  });

  it("restores an earlier version without deleting history", async () => {
    const data = await freshData();

    await data.generateNewVersion();
    const restored = await data.setCurrentVersion("res-001");

    expect(restored?.id).toBe("res-001");
    expect(restored?.isCurrent).toBe(true);

    const versions = await data.getResumeVersions();
    expect(versions).toHaveLength(4);
    expect(versions.filter((v) => v.isCurrent).map((v) => v.id)).toEqual([
      "res-001",
    ]);
    expect((await data.getCurrentResume())?.id).toBe("res-001");
  });

  it("returns null for an unknown version id and changes nothing", async () => {
    const data = await freshData();

    expect(await data.setCurrentVersion("res-nope")).toBeNull();
    expect((await data.getCurrentResume())?.id).toBe("res-003");
  });
});

// ---------------------------------------------------------------------------
// The latency knob
// ---------------------------------------------------------------------------

describe("the mock latency", () => {
  it("defaults to 120ms and can be set to 0", async () => {
    /*
     * The delay exists to surface missing loading states, so it is not deleted.
     * It is behind one number so a developer can take it out while chasing
     * something else -- and so this suite is not 40 x 120ms slower than it
     * needs to be.
     */
    vi.resetModules();
    const latency = await import("./latency");

    expect(latency.DEFAULT_MOCK_LATENCY_MS).toBe(120);
    expect(latency.mockLatencyMs()).toBe(120);

    latency.setMockLatencyMs(0);
    expect(latency.mockLatencyMs()).toBe(0);

    latency.setMockLatencyMs(-5);
    expect(latency.mockLatencyMs()).toBe(0);
  });
});
