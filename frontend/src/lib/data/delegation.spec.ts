import { afterEach, describe, expect, it, vi } from "vitest";

import { runWithAuth } from "$lib/server/requestContext";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("provider delegation", () => {
  it("uses the mock path when THRIVE_API_ORIGIN is unset", async () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "");
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    const { getStudent } = await import("./providers");
    const student = await getStudent();
    expect(student.id).toBeTruthy(); // mock student
    expect(spy).not.toHaveBeenCalled();
  });

  it("uses the api path when THRIVE_API_ORIGIN is set", async () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test");
    const impl = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: "ada" }),
    });
    vi.stubGlobal("fetch", impl);
    const { getStudent } = await import("./providers");
    const student = await runWithAuth({ cookie: "", student: null }, () => getStudent());
    expect(student.id).toBe("ada");
    expect(impl.mock.calls[0][0]).toBe("http://api.test/api/thrive/me");
  });
});
