import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runWithAuth } from "$lib/server/requestContext";
import { messages } from "$lib/messages";
import { actions } from "./+page.server";

/**
 * The resume upload action's failure reporting.
 *
 * Every rejection used to collapse into one "Something went wrong uploading
 * your resume. Try again." — so the three failures a student can actually
 * cause and fix (a scan with no text layer, a file over 5MB, something that is
 * not a PDF) were indistinguishable from one another and from a server fault,
 * and the advice attached to all of them was the one thing that cannot help
 * with any of the three. Retrying a scanned PDF fails forever.
 *
 * These pin the mapping from the backend's error CODE to what the student
 * reads, including the fallback for a code nobody has seen yet.
 */

const upload = actions.upload as (event: unknown) => Promise<{
  status: number;
  data: { error: string };
}>;

/**
 * A signed-in student.
 *
 * Cast rather than built out: the action reads `locals.student` for PRESENCE
 * only (`!locals.student` → 401), so filling in the other nine fields of
 * `Student` would be nine values no assertion here depends on.
 */
const SIGNED_IN = { id: "stu-1" } as unknown as NonNullable<
  App.Locals["student"]
>;

/** A multipart POST carrying one file, the way the browser sends it. */
function call(file: File | null) {
  const form = new FormData();
  if (file) form.set("file", file);
  const request = new Request("http://localhost/jobs?/upload", {
    method: "POST",
    body: form,
  });
  return runWithAuth(
    { cookie: "sessionid=s; csrftoken=t", student: SIGNED_IN },
    () => upload({ request, locals: { student: SIGNED_IN } }),
  );
}

/** Make the Django call fail the way `apiFetch` reports a rejection. */
function stubApiFailure(status: number, code: string, message: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status,
      json: () => Promise.resolve({ error: { code, message } }),
    }),
  );
}

function pdf(name = "cv.pdf") {
  return new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], name, {
    type: "application/pdf",
  });
}

beforeEach(() => vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test"));
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("the resume upload action's failures", () => {
  it("names a scanned PDF as a scan, and does not say to try again", async () => {
    stubApiFailure(400, "unreadable_resume", "Could not extract enough text.");

    const result = await call(pdf());

    expect(result.status).toBe(400);
    expect(result.data.error).toBe(
      messages.jobs.profileBanner.uploadErrors.unreadable_resume,
    );
    // The whole point: retrying a scan is futile, so it must not be advised.
    expect(result.data.error).not.toContain("Try again");
    expect(result.data.error).not.toBe(messages.jobs.profileBanner.error);
  });

  it("names the size limit when the file is too big", async () => {
    stubApiFailure(400, "too_large", "Resume file is too large (5MB max).");

    const result = await call(pdf());

    expect(result.data.error).toBe(
      messages.jobs.profileBanner.uploadErrors.too_large,
    );
    expect(result.data.error).toContain("5MB");
  });

  it("says it is not a PDF when the file is not one", async () => {
    stubApiFailure(400, "bad_request", "Only PDF resumes are supported.");

    const result = await call(pdf("resume.docx"));

    expect(result.data.error).toBe(
      messages.jobs.profileBanner.uploadErrors.bad_request,
    );
  });

  it("says the reader is down, and DOES invite a retry, when it is", async () => {
    // The one failure retrying actually helps with.
    stubApiFailure(503, "llm_unavailable", "Service unavailable.");

    const result = await call(pdf());

    expect(result.status).toBe(503);
    expect(result.data.error).toBe(
      messages.jobs.profileBanner.uploadErrors.llm_unavailable,
    );
    expect(result.data.error).toContain("try again");
  });

  it("falls back to the generic line for a code it has never seen", async () => {
    stubApiFailure(500, "some_new_code", "Boom.");

    const result = await call(pdf());

    expect(result.data.error).toBe(messages.jobs.profileBanner.error);
  });

  it("asks for a file when the form arrives without one", async () => {
    // Reachable now that the input has dropped `required`: the browser used to
    // block this submit outright and show the student nothing at all.
    const result = await call(null);

    expect(result.status).toBe(400);
    expect(result.data.error).toBe(messages.jobs.profileBanner.empty);
  });
});
