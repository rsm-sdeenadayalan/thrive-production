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
    ["getJobPosting", () => api.getJobPosting("job-1"), "/api/thrive/jobs/job-1"],
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

describe("job search providers", () => {
  it("searchJobs encodes the query", async () => {
    const impl = stubFetch(200, { query: "x", profileAvailable: false,
      benchmark: { sampleSize: 0, topSkills: [] }, results: [] });
    await runWithAuth(AUTH, () => api.searchJobs("data analyst"));
    expect(impl.mock.calls[0][0])
      .toBe("http://api.test/api/thrive/jobs?q=data%20analyst");
  });

  it("generateMatchReport POSTs and unwraps", async () => {
    const impl = stubFetch(200, { report: { id: "rep-1", jobId: "job-1",
      score: 70, competency: "good", matchedSkills: [], gaps: [],
      verdict: "v", createdAt: "2026-08-23T09:00:00-07:00" } });
    const report = await runWithAuth(AUTH, () => api.generateMatchReport("job-1"));
    expect(impl.mock.calls[0][1].method).toBe("POST");
    expect(report.id).toBe("rep-1");
  });

  it("uploadResume sends a multipart body with no forced content-type", async () => {
    const impl = stubFetch(201, {});
    const file = new File(["hello"], "resume.pdf", { type: "application/pdf" });
    await runWithAuth(AUTH, () => api.uploadResume(file));
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/resume/upload");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBe(file);
    expect(init.headers["content-type"]).toBeUndefined();
  });
});

describe("job feed providers", () => {
  const FEED_PAYLOAD = { results: [], counts: { recommended: 0, liked: 0, all: 0 },
    profileAvailable: false };

  it("getJobFeed hits the bare endpoint with no params given", async () => {
    const impl = stubFetch(200, FEED_PAYLOAD);
    await runWithAuth(AUTH, () => api.getJobFeed({}));
    expect(impl.mock.calls[0][0]).toBe("http://api.test/api/thrive/jobs/feed");
  });

  it("getJobFeed encodes tab, q, and minScore as tab/q/min_score", async () => {
    const impl = stubFetch(200, FEED_PAYLOAD);
    await runWithAuth(AUTH, () =>
      api.getJobFeed({ tab: "all", q: "data analyst", minScore: 50 }));
    expect(impl.mock.calls[0][0]).toBe(
      "http://api.test/api/thrive/jobs/feed?tab=all&q=data+analyst&min_score=50");
  });

  it("getJobFeed omits params that were not given", async () => {
    const impl = stubFetch(200, FEED_PAYLOAD);
    await runWithAuth(AUTH, () => api.getJobFeed({ tab: "liked" }));
    expect(impl.mock.calls[0][0]).toBe(
      "http://api.test/api/thrive/jobs/feed?tab=liked");
  });

  it("likeJob POSTs to the job's like endpoint and returns the interaction state", async () => {
    const impl = stubFetch(200, { jobId: "job-1", liked: true, dismissed: false });
    const result = await runWithAuth(AUTH, () => api.likeJob("job-1"));
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/jobs/job-1/like");
    expect(init.method).toBe("POST");
    expect(result).toEqual({ jobId: "job-1", liked: true, dismissed: false });
  });

  it("dismissJob POSTs to the job's dismiss endpoint and encodes the id", async () => {
    const impl = stubFetch(200, { jobId: "job 1", liked: false, dismissed: true });
    await runWithAuth(AUTH, () => api.dismissJob("job 1"));
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/jobs/job%201/dismiss");
    expect(init.method).toBe("POST");
  });
});
