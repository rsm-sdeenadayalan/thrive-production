import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runWithAuth } from "$lib/server/requestContext";
import { ApiError, apiEnabled, apiFetch } from "./client";

const AUTH = { cookie: "sessionid=abc; csrftoken=tok123", student: null };

function stubFetch(status: number, payload: unknown) {
  const impl = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
  vi.stubGlobal("fetch", impl);
  return impl;
}

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("is disabled without the env var", () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "");
    expect(apiEnabled()).toBe(false);
  });

  it("forwards the request cookie and prefixes the path", async () => {
    const impl = stubFetch(200, { ok: true });
    const result = await runWithAuth(AUTH, () => apiFetch<{ ok: boolean }>("/me"));
    expect(result).toEqual({ ok: true });
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/me");
    expect(init.headers.cookie).toBe(AUTH.cookie);
    expect(init.headers["x-csrftoken"]).toBeUndefined();
  });

  it("sends csrf header and json body on POST", async () => {
    const impl = stubFetch(201, { id: "appt-1" });
    await runWithAuth(AUTH, () =>
      apiFetch("/appointments", { method: "POST", body: { slotId: "s1" } }),
    );
    const [, init] = impl.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers["x-csrftoken"]).toBe("tok123");
    expect(init.headers["content-type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ slotId: "s1" }));
  });

  it("throws ApiError with the envelope's code and message", async () => {
    stubFetch(409, { error: { code: "slot_unavailable", message: "That time was just taken. Pick another." } });
    const attempt = runWithAuth(AUTH, () => apiFetch("/appointments", { method: "POST", body: {} }));
    await expect(attempt).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      code: "slot_unavailable",
      message: "That time was just taken. Pick another.",
    });
    expect(new ApiError(404, "x", "y")).toBeInstanceOf(Error);
  });
});
