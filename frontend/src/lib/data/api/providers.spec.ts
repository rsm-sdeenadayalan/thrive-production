import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Student } from "$lib/data/types";
import { runWithAuth } from "$lib/server/requestContext";
import * as api from "./providers";

const AUTH = { cookie: "sessionid=abc", student: null as Student | null };

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

describe("read providers", () => {
  it.each([
    ["getCourses", () => api.getCourses(), "/api/thrive/courses"],
    ["getSyllabi", () => api.getSyllabi(), "/api/thrive/syllabi"],
    ["getAssignments", () => api.getAssignments(), "/api/thrive/assignments"],
    ["getTasks", () => api.getTasks(), "/api/thrive/tasks?view=source"],
    ["getEvents", () => api.getEvents(), "/api/thrive/events"],
    ["getDegreeProgress", () => api.getDegreeProgress(), "/api/thrive/degree/progress"],
    ["getProgramTimeline", () => api.getProgramTimeline(), "/api/thrive/degree/timeline"],
    ["getResources", () => api.getResources(), "/api/thrive/resources"],
    ["getAdvisors", () => api.getAdvisors(), "/api/thrive/advisors"],
    ["getMyAppointments", () => api.getMyAppointments(), "/api/thrive/appointments"],
    ["getConversations", () => api.getConversations(), "/api/thrive/conversations"],
  ] as const)("%s hits its endpoint", async (_name, call, expectedPath) => {
    const impl = stubFetch(200, []);
    await runWithAuth(AUTH, call as () => Promise<any>);
    expect(impl.mock.calls[0][0]).toBe(`http://api.test${expectedPath}`);
  });

  it("getSlots encodes the advisor id", async () => {
    const impl = stubFetch(200, []);
    await runWithAuth(AUTH, () => api.getSlots("adv 1"));
    expect(impl.mock.calls[0][0]).toBe("http://api.test/api/thrive/advisors/adv%201/slots");
  });

  it("getStudent uses the context cache when hooks populated it", async () => {
    const impl = stubFetch(200, { id: "never" });
    const student = { id: "ada" } as Student;
    const result = await runWithAuth({ cookie: "", student }, () => api.getStudent());
    expect(result.id).toBe("ada");
    expect(result).not.toBe(student); // copy, never the stored object
    expect(impl).not.toHaveBeenCalled();
  });

  it("getStudent falls back to /me", async () => {
    const impl = stubFetch(200, { id: "ada" });
    const result = await runWithAuth(AUTH, () => api.getStudent());
    expect(result.id).toBe("ada");
    expect(impl.mock.calls[0][0]).toBe("http://api.test/api/thrive/me");
  });

  it("getConversation maps 404 to null and rethrows others", async () => {
    stubFetch(404, { error: { code: "unknown_conversation", message: "x" } });
    const missing = await runWithAuth(AUTH, () => api.getConversation("conv-9"));
    expect(missing).toBeNull();

    stubFetch(500, { error: { code: "boom", message: "x" } });
    await expect(runWithAuth(AUTH, () => api.getConversation("conv-9"))).rejects.toMatchObject({
      status: 500,
    });
  });
});

describe("write providers", () => {
  it("createConversation POSTs destination and body", async () => {
    const impl = stubFetch(201, { id: "conv-9", destination: "career",
      title: "q", messages: [], updatedAt: "2026-08-23T09:00:00-07:00" });
    const result = await runWithAuth(AUTH, () =>
      api.createConversation("career", "resume length?"));
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/conversations");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(
      { destination: "career", body: "resume length?" });
    expect(result.id).toBe("conv-9");
  });

  it("sendConversationMessage POSTs to the conversation", async () => {
    const impl = stubFetch(200, { id: "conv-9", destination: "career",
      title: "q", messages: [], updatedAt: "2026-08-23T09:00:00-07:00" });
    await runWithAuth(AUTH, () => api.sendConversationMessage("conv-9", "more"));
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/conversations/conv-9/messages");
    expect(JSON.parse(init.body as string)).toEqual({ body: "more" });
  });
});
