import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The booking flow, through the real form actions.
 *
 * ## What this covers that `providers.spec.ts` does not
 *
 * The provider suite proves `bookAppointment` THROWS `SlotUnavailableError` on a
 * double booking. That is the data layer keeping its contract, and it is not the
 * interesting half: a thrown error reaching a student is a 500 page. What
 * matters on this surface is that the action turns the throw into a VALUE the
 * panel can render -- a 409 with a sentence -- so two people wanting the same
 * 2pm is an ordinary outcome rather than a crash.
 *
 * That translation lives in `+page.server.ts` and no other gate can see it.
 * `npm run check` proves the types agree, `check:interaction` drives a browser
 * but cannot make two students race, and nothing in the component suite renders.
 *
 * ## Why the event is faked rather than mocked
 *
 * The actions read exactly one thing off their argument: `request.formData()`.
 * A stub with that one method is the whole contract, and it keeps these tests in
 * Node with no server running -- the same reason the rest of the suite has no
 * jsdom.
 */

type ActionModule = typeof import("../routes/appointments/+page.server");
type DataModule = typeof import("./data/index");

/**
 * Tuesday 15 September 2026, 08:00 local.
 *
 * Built from local parts so the suite does not depend on the runner's timezone,
 * and 08:00 is before every published slot so nothing is filtered out as
 * already past. The same instant `providers.spec.ts` freezes, deliberately: the
 * slot ids below are derived from that file's reasoning about the hash.
 */
const FROZEN = new Date(2026, 8, 15, 8, 0, 0);

/**
 * Slot ids at the frozen instant, for `adv-gsa`.
 *
 * `isTaken` hashes `advisorId.length * 7 + dayIndex * 3 + timeIndex * 5` and
 * takes the slot when the result divides by 4. On day 0 that gives 49, 54, 59,
 * 64, 69 -- so only the fourth is taken before anyone books anything.
 */
const FREE_SLOT = "slot-adv-gsa-0-0";
const OTHER_FREE_SLOT = "slot-adv-gsa-0-1";
const SEEDED_TAKEN_SLOT = "slot-adv-gsa-0-3";

/** A `RequestEvent` with the one method the actions actually use. */
function event(fields: Record<string, string>) {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) form.set(key, value);

  return {
    request: { formData: async () => form },
  } as unknown as Parameters<ActionModule["actions"]["book"]>[0];
}

async function fresh(): Promise<{ actions: ActionModule["actions"]; data: DataModule }> {
  vi.resetModules();
  // Same reset registry, so the instance the action imports is the one we set.
  const { setMockLatencyMs } = await import("./data/latency");
  setMockLatencyMs(0);

  const [module, data] = await Promise.all([
    import("../routes/appointments/+page.server"),
    import("./data/index"),
  ]);

  return { actions: module.actions, data };
}

/** `fail()` returns an object carrying a status and a data payload. */
function failure(result: unknown): { status: number; error: string } {
  const shaped = result as { status?: number; data?: { error?: string } };
  return { status: shaped.status ?? 0, error: shaped.data?.error ?? "" };
}

beforeEach(() => {
  // Date only. setTimeout stays real, so `resolveAfterDelay` still resolves.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(FROZEN);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("the book action", () => {
  it("returns the whole formatted appointment, not just an id", async () => {
    const { actions } = await fresh();

    const result = await actions.book(
      event({ slotId: FREE_SLOT, reason: "Course planning" }),
    );

    const booked = (result as { booked: Record<string, unknown> }).booked;

    expect(booked.id).toBe("apt-001");
    expect(booked.reason).toBe("Course planning");
    /*
     * Formatted, on the server. The confirmation panel renders these strings
     * directly, which is what keeps a date off the client -- and it renders the
     * SAME object the list below it will render on the next load, through the
     * same mapper, so the two cannot disagree about when the meeting is.
     */
    expect(booked.dateLabel).toBe("Tue, Sep 15");
    expect(booked.timeLabel).toBe("9:30 AM");
    expect(booked.whenLabel).toBe("Tue, Sep 15 at 9:30 AM");
    expect(booked.dayKey).toBe("2026-09-15");
    expect(booked.advisorName).toBe("Amber Hanna");
  });

  it("claims the slot, so the panel cannot offer it again", async () => {
    const { actions, data } = await fresh();

    await actions.book(event({ slotId: FREE_SLOT, reason: "why" }));

    const slots = await data.getSlots("adv-gsa");
    const claimed = slots.find((slot) => slot.id === FREE_SLOT);

    expect(claimed?.available).toBe(false);
  });

  it("names Zoom as the location on a remote booking", async () => {
    const { actions, data } = await fresh();

    const slots = await data.getSlots("adv-gsa");
    const remote = slots.find((slot) => slot.mode === "zoom" && slot.available);

    expect(remote).toBeDefined();

    const result = await actions.book(
      event({ slotId: remote!.id, reason: "remote" }),
    );
    const booked = (result as { booked: Record<string, unknown> }).booked;

    /*
     * Not the advisor's office. Putting "Rady 2S111" on a Zoom booking would
     * send a student across campus for a call, and the same string goes into
     * the .ics file, where the mistake lands in their real calendar.
     */
    expect(booked.location).toBe("Zoom");
  });

  // -------------------------------------------------------------------------
  // The double-booking path -- the reason this file exists
  // -------------------------------------------------------------------------

  it("returns 409 rather than throwing when the slot was just taken", async () => {
    const { actions } = await fresh();

    await actions.book(event({ slotId: FREE_SLOT, reason: "mine" }));

    // The second attempt is the one a real student hits: their page was rendered
    // before somebody else took the slot.
    const result = await actions.book(
      event({ slotId: FREE_SLOT, reason: "also mine" }),
    );

    const { status, error } = failure(result);

    expect(status).toBe(409);
    // The data layer's own sentence, passed through. It distinguishes "somebody
    // took it" from "that id is not listed", and only the data layer knows
    // which happened.
    expect(error).toBe("That time was just taken. Pick another.");
    expect(error).not.toBe("");
  });

  it("does not create a second appointment on the refused attempt", async () => {
    const { actions, data } = await fresh();

    await actions.book(event({ slotId: FREE_SLOT, reason: "mine" }));
    await actions.book(event({ slotId: FREE_SLOT, reason: "also mine" }));

    const appointments = await data.getMyAppointments();

    expect(appointments).toHaveLength(1);
    expect(appointments[0].reason).toBe("mine");
  });

  it("returns 409 for a slot the hash already marks taken", async () => {
    const { actions } = await fresh();

    const { status, error } = failure(
      await actions.book(event({ slotId: SEEDED_TAKEN_SLOT, reason: "r" })),
    );

    expect(status).toBe(409);
    expect(error).toBe("That time was just taken. Pick another.");
  });

  it("returns 409 with a DIFFERENT sentence for a slot id that is not listed", async () => {
    const { actions } = await fresh();

    const { status, error } = failure(
      await actions.book(event({ slotId: "slot-adv-gsa-99-99", reason: "r" })),
    );

    expect(status).toBe(409);
    /*
     * The distinction the pass-through preserves. Flattening both to one string
     * from `messages.ts` would tell a student "somebody took it" about a slot
     * that never existed -- which is what would happen to a stale bookmark.
     */
    expect(error).toBe("That time is no longer listed.");
  });

  it("refuses an empty slot id with 400 before touching the store", async () => {
    const { actions, data } = await fresh();

    const { status, error } = failure(
      await actions.book(event({ slotId: "", reason: "r" })),
    );

    expect(status).toBe(400);
    expect(error).toBe("Pick a time first.");
    expect(await data.getMyAppointments()).toHaveLength(0);
  });

  it("truncates the reason at the ceiling rather than trusting the markup", async () => {
    const { actions } = await fresh();
    const { REASON_MAX } = await import("./appointmentsView");

    const result = await actions.book(
      event({ slotId: FREE_SLOT, reason: "x".repeat(REASON_MAX + 50) }),
    );

    const booked = (result as { booked: { reason: string } }).booked;

    /*
     * `maxlength` on the textarea is a courtesy to the person typing. A form
     * action is reachable by direct POST -- MIGRATION.md section 9 defect 2 --
     * so if the attribute were the only limit there would be nothing between
     * the store and an unbounded string.
     */
    expect(booked.reason).toHaveLength(REASON_MAX);
  });
});

describe("the cancel action", () => {
  it("releases the slot so it can be booked again", async () => {
    const { actions, data } = await fresh();

    const booked = (
      (await actions.book(
        event({ slotId: FREE_SLOT, reason: "first" }),
      )) as { booked: { id: string } }
    ).booked;

    const result = await actions.cancel(
      event({ appointmentId: booked.id }),
    );

    expect((result as { cancelled: string }).cancelled).toBe(booked.id);

    const slots = await data.getSlots("adv-gsa");
    expect(slots.find((slot) => slot.id === FREE_SLOT)?.available).toBe(true);
  });

  it("releases the slot it was actually booked against, not one that matches by time", async () => {
    /*
     * MIGRATION.md section 9 defect 8, checked at the action level.
     *
     * The Next data layer scanned the claimed set for a slot whose `start`
     * matched the appointment's and released the first hit, because an
     * appointment carried no slot reference. `Appointment.slotId` closed that in
     * Phase 5; this asserts the property the fix exists for -- cancelling one
     * booking must leave the other's slot claimed.
     */
    const { actions, data } = await fresh();

    const keep = (
      (await actions.book(event({ slotId: FREE_SLOT, reason: "keep" }))) as {
        booked: { id: string };
      }
    ).booked;
    const drop = (
      (await actions.book(
        event({ slotId: OTHER_FREE_SLOT, reason: "drop" }),
      )) as { booked: { id: string } }
    ).booked;

    await actions.cancel(event({ appointmentId: drop.id }));

    const slots = await data.getSlots("adv-gsa");

    expect(slots.find((slot) => slot.id === OTHER_FREE_SLOT)?.available).toBe(
      true,
    );
    expect(slots.find((slot) => slot.id === FREE_SLOT)?.available).toBe(false);

    const remaining = await data.getMyAppointments();
    expect(remaining.map((appointment) => appointment.id)).toEqual([keep.id]);
  });

  it("returns 404 for an id that is no longer on file", async () => {
    const { actions } = await fresh();

    const { status, error } = failure(
      await actions.cancel(event({ appointmentId: "apt-nope" })),
    );

    // What a stale page looks like. A student can act on being told so; a throw
    // would take the page down over a button that was already out of date.
    expect(status).toBe(404);
    expect(error).toBe("That appointment is no longer on file.");
  });

  it("returns 404 rather than throwing on an empty id", async () => {
    const { actions } = await fresh();

    expect(
      failure(await actions.cancel(event({ appointmentId: "" }))).status,
    ).toBe(404);
  });
});
