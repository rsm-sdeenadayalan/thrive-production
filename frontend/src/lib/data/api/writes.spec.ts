import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SlotUnavailableError } from "$lib/data/errors";
import { runWithAuth } from "$lib/server/requestContext";
import * as api from "./providers";

const AUTH = { cookie: "sessionid=abc; csrftoken=t", student: null };

function stubFetch(status: number, payload: unknown) {
  const impl = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
  vi.stubGlobal("fetch", impl);
  return impl;
}

beforeEach(() => vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test"));
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("write providers", () => {
  it("bookAppointment posts and returns the appointment", async () => {
    const impl = stubFetch(201, { id: "appt-1", status: "confirmed" });
    const result = await runWithAuth(AUTH, () => api.bookAppointment("s1", "why"));
    expect(result.id).toBe("appt-1");
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/appointments");
    expect(init.body).toBe(JSON.stringify({ slotId: "s1", reason: "why" }));
  });

  it("bookAppointment translates 409 and slot_unknown into SlotUnavailableError", async () => {
    stubFetch(409, { error: { code: "slot_unavailable", message: "That time was just taken. Pick another." } });
    await expect(runWithAuth(AUTH, () => api.bookAppointment("s1", "r")))
      .rejects.toThrow(SlotUnavailableError);

    stubFetch(404, { error: { code: "slot_unknown", message: "That time is no longer listed." } });
    const attempt = runWithAuth(AUTH, () => api.bookAppointment("s1", "r"));
    await expect(attempt).rejects.toThrow("That time is no longer listed.");
  });

  it("cancelAppointment maps 404 to null", async () => {
    stubFetch(404, { error: { code: "unknown_appointment", message: "x" } });
    expect(await runWithAuth(AUTH, () => api.cancelAppointment("appt-9"))).toBeNull();
  });

  it("submitRequest and setCurrentVersion map 404 to null", async () => {
    stubFetch(404, { error: { code: "unknown_request", message: "x" } });
    expect(await runWithAuth(AUTH, () => api.submitRequest("req-9"))).toBeNull();
    stubFetch(404, { error: { code: "unknown_version", message: "x" } });
    expect(await runWithAuth(AUTH, () => api.setCurrentVersion("rv-9"))).toBeNull();
  });

  it("tss providers unwrap the connected flag", async () => {
    stubFetch(200, { connected: false });
    expect(await runWithAuth(AUTH, () => api.getTssConnection())).toBe(false);
    const impl = stubFetch(200, { connected: true });
    expect(await runWithAuth(AUTH, () => api.connectTss())).toBe(true);
    expect(impl.mock.calls[0][1].method).toBe("POST");
  });

  it("getCurrentResume maps no_resume 404 to null; generate returns version+diff", async () => {
    stubFetch(404, { error: { code: "no_resume", message: "x" } });
    expect(await runWithAuth(AUTH, () => api.getCurrentResume())).toBeNull();

    stubFetch(201, { version: { id: "rv-1" }, diff: { addedSkills: [], addedCourses: [], summaryChanged: true } });
    const generated = await runWithAuth(AUTH, () => api.generateNewVersion());
    expect(generated.version.id).toBe("rv-1");
    expect(generated.diff.summaryChanged).toBe(true);
  });

  it("createRequest posts the input", async () => {
    const impl = stubFetch(201, { id: "req-1", status: "draft" });
    await runWithAuth(AUTH, () =>
      api.createRequest({ type: "drop", course: "MGTA 453", reason: "conflict" }),
    );
    expect(impl.mock.calls[0][1].body).toBe(
      JSON.stringify({ type: "drop", course: "MGTA 453", reason: "conflict" }),
    );
  });
});
