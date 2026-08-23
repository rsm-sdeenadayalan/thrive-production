import { isHttpError, isRedirect, type Handle } from "@sveltejs/kit";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { handle } from "./hooks.server";

type Event = Parameters<Handle>[0]["event"];

function makeEvent(): Event {
	return {
		request: new Request("http://localhost:3123/", { headers: { cookie: "sessionid=abc" } }),
		url: new URL("http://localhost:3123/"),
		locals: {},
	} as unknown as Event;
}

function stubFetch(status: number, payload: unknown) {
	const impl = vi.fn().mockResolvedValue({
		ok: status >= 200 && status < 300,
		status,
		json: () => Promise.resolve(payload),
	});
	vi.stubGlobal("fetch", impl);
	return impl;
}

describe("hooks.server handle", () => {
	beforeEach(() => {
		vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test");
	});

	afterEach(() => {
		vi.unstubAllEnvs();
		vi.unstubAllGlobals();
	});

	it("passes through untouched when the API is not configured", async () => {
		vi.stubEnv("THRIVE_API_ORIGIN", "");
		const fetchImpl = vi.fn();
		vi.stubGlobal("fetch", fetchImpl);
		const event = makeEvent();
		const resolve = vi.fn().mockResolvedValue(new Response("ok"));

		await handle({ event, resolve } as Parameters<Handle>[0]);

		expect(resolve).toHaveBeenCalledOnce();
		expect(fetchImpl).not.toHaveBeenCalled();
	});

	it("redirects to dev-login on a 401 from /me", async () => {
		stubFetch(401, { error: { code: "unauthorized", message: "Not logged in" } });
		const event = makeEvent();
		const resolve = vi.fn().mockResolvedValue(new Response("ok"));

		let caught: unknown;
		try {
			await handle({ event, resolve } as Parameters<Handle>[0]);
			expect.unreachable("expected handle to throw a redirect");
		} catch (error) {
			caught = error;
		}

		expect(isRedirect(caught)).toBe(true);
		const redirectError = caught as { status: number; location: string };
		expect(redirectError.status).toBe(303);
		expect(redirectError.location).toContain("/api/thrive/dev-login?next=");
	});

	it("responds with a 403 page instead of redirecting on no_profile", async () => {
		stubFetch(403, {
			error: { code: "no_profile", message: "This account has no student profile." },
		});
		const event = makeEvent();
		const resolve = vi.fn().mockResolvedValue(new Response("ok"));

		let caught: unknown;
		try {
			await handle({ event, resolve } as Parameters<Handle>[0]);
			expect.unreachable("expected handle to throw an HttpError");
		} catch (error) {
			caught = error;
		}

		expect(isHttpError(caught)).toBe(true);
		const httpError = caught as { status: number };
		expect(httpError.status).toBe(403);
	});

	it("sets locals.student and returns resolve's response on success", async () => {
		const student = { id: "s1", name: "Demo Student" };
		stubFetch(200, student);
		const event = makeEvent();
		const response = new Response("ok");
		const resolve = vi.fn().mockResolvedValue(response);

		const result = await handle({ event, resolve } as Parameters<Handle>[0]);

		expect(event.locals.student).toEqual(student);
		expect(result).toBe(response);
		expect(resolve).toHaveBeenCalledWith(event);
	});
});
