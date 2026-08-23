import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runWithAuth } from "$lib/server/requestContext";
import { POST } from "./+server";

function stubFetch(status = 204, payload: unknown = null) {
  const impl = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
  vi.stubGlobal("fetch", impl);
  return impl;
}

function call(body: unknown) {
  const request = new Request("http://localhost/overlay-sync", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return runWithAuth({ cookie: "sessionid=s; csrftoken=t", student: null }, () =>
    POST({ request } as Parameters<typeof POST>[0]),
  );
}

beforeEach(() => vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test"));
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("POST /overlay-sync", () => {
  it("forwards task-override to the Django PATCH", async () => {
    const impl = stubFetch(200, {});
    const response = await call({ op: "task-override", taskKey: "asg:a1",
                                  facets: { done: true } });
    expect(response.status).toBe(200);
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/tasks/asg%3Aa1/override");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ done: true }));
    expect(init.headers["x-csrftoken"]).toBe("t");
  });

  it("projects only the five task-add fields", async () => {
    const impl = stubFetch(201, {});
    await call({ op: "task-add", task: { id: "x", title: "T", done: false,
      dueDate: "2026-09-01T12:00:00-07:00", source: "admin", priority: "low",
      subtasks: [], clientKey: "task-add-1", courseId: "c1" } });
    const sent = JSON.parse(impl.mock.calls[0][1].body as string);
    expect(sent).toEqual({ title: "T", dueDate: "2026-09-01T12:00:00-07:00",
      priority: "low", source: "admin", clientKey: "task-add-1" });
  });

  it("routes on/off ops to PUT vs DELETE", async () => {
    const impl = stubFetch();
    await call({ op: "event-ignore", eventId: "evt-1", on: true });
    await call({ op: "event-ignore", eventId: "evt-1", on: false });
    expect(impl.mock.calls[0][1].method).toBe("PUT");
    expect(impl.mock.calls[1][1].method).toBe("DELETE");
  });

  it("400s unknown ops and passes ApiError envelopes through", async () => {
    stubFetch();
    const bad = await call({ op: "nonsense" });
    expect(bad.status).toBe(400);
    stubFetch(404, { error: { code: "unknown_task", message: "x" } });
    const notFound = await call({ op: "task-override", taskKey: "asg:x",
                                  facets: { done: true } });
    expect(notFound.status).toBe(404);
    expect((await notFound.json()).error.code).toBe("unknown_task");
  });

  it("404s when api mode is off", async () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "");
    const response = await call({ op: "task-override", taskKey: "x",
                                  facets: { done: true } });
    expect(response.status).toBe(404);
  });
});
