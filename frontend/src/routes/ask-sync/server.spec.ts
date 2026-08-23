import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runWithAuth } from "$lib/server/requestContext";
import { POST } from "./+server";

function stubFetch(status = 201, payload: unknown = {}) {
  const impl = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300, status,
    json: () => Promise.resolve(payload),
  });
  vi.stubGlobal("fetch", impl);
  return impl;
}

function call(body: unknown) {
  const request = new Request("http://localhost/ask-sync", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return runWithAuth({ cookie: "sessionid=s; csrftoken=t", student: null },
    () => POST({ request } as Parameters<typeof POST>[0]));
}

beforeEach(() => vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test"));
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("POST /ask-sync", () => {
  it("create forwards to POST /conversations and wraps the payload", async () => {
    const impl = stubFetch(201, { id: "conv-3" });
    const response = await call({ action: "create", destination: "career",
                                  body: "hi" });
    expect(response.status).toBe(200);
    expect((await response.json()).conversation.id).toBe("conv-3");
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/conversations");
    expect(init.method).toBe("POST");
    expect(init.headers["x-csrftoken"]).toBe("t");
  });

  it("message forwards to the conversation's messages", async () => {
    const impl = stubFetch(200, { id: "conv-3" });
    await call({ action: "message", conversationId: "conv-3", body: "more" });
    expect(impl.mock.calls[0][0])
      .toBe("http://api.test/api/thrive/conversations/conv-3/messages");
  });

  it("unknown action 400s; ApiError envelopes pass through", async () => {
    stubFetch();
    expect((await call({ action: "nope" })).status).toBe(400);
    stubFetch(404, { error: { code: "unknown_conversation", message: "x" } });
    const missing = await call({ action: "message", conversationId: "conv-99",
                                 body: "q" });
    expect(missing.status).toBe(404);
    expect((await missing.json()).error.code).toBe("unknown_conversation");
  });

  it("404s when api mode is off", async () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "");
    expect((await call({ action: "create", destination: "career", body: "q" }))
      .status).toBe(404);
  });
});
