import { error as kitError, redirect, type Handle } from "@sveltejs/kit";

import { ApiError, apiEnabled, apiFetch, apiOrigin } from "$lib/data/api/client";
import type { Student } from "$lib/data/types";
import { runWithAuth, type RequestAuth } from "$lib/server/requestContext";

export const handle: Handle = async ({ event, resolve }) => {
	if (!apiEnabled()) return resolve(event);

	const auth: RequestAuth = {
		cookie: event.request.headers.get("cookie") ?? "",
		student: null,
	};

	return runWithAuth(auth, async () => {
		try {
			auth.student = await apiFetch<Student>("/me");
		} catch (caught) {
			if (caught instanceof ApiError && caught.code === "no_profile") {
				kitError(403, "This account has no student profile. Ask the program team to set one up.");
			}
			if (caught instanceof ApiError && (caught.status === 401 || caught.status === 403)) {
				const login = process.env.THRIVE_LOGIN_URL ?? `${apiOrigin()}/api/thrive/dev-login`;
				redirect(303, `${login}?next=${encodeURIComponent(event.url.href)}`);
			}
			throw caught;
		}
		event.locals.student = auth.student;
		return resolve(event);
	});
};
