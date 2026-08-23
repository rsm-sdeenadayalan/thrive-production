import { redirect, type Handle } from "@sveltejs/kit";

import { ApiError, apiEnabled, apiFetch } from "$lib/data/api/client";
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
		} catch (error) {
			if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
				const login =
					process.env.THRIVE_LOGIN_URL ??
					`${process.env.THRIVE_API_ORIGIN}/api/thrive/dev-login`;
				redirect(303, `${login}?next=${encodeURIComponent(event.url.href)}`);
			}
			throw error;
		}
		event.locals.student = auth.student;
		return resolve(event);
	});
};
