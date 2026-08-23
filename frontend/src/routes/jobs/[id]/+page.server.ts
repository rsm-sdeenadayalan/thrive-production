import { error, fail } from "@sveltejs/kit";

import { apiEnabled, ApiError } from "$lib/data/api/client";
import { generateMatchReport, getJobPosting } from "$lib/data";
import { toJobPostingDetailView } from "$lib/jobs";
import { messages } from "$lib/messages";
import type { Actions, PageServerLoad } from "./$types";

/**
 * One posting, its benchmark, and the match report a student can generate.
 *
 * ## `getJobPosting` throws rather than returning null
 *
 * Unlike `getConversation`, which hands back `null` for an unknown id and lets
 * the page decide, the job providers throw in both modes -- a plain `Error` in
 * mock, an `ApiError` in API mode. Both mean the same thing here (there is no
 * posting behind this id): an `ApiError` with status 404, or a mock-mode
 * `Error` whose message starts with "Unknown job". Both become the one 404.
 * Anything else is a failure nobody has a story for -- a network error, a
 * malformed response -- and rethrowing it is the honest shape, rather than a
 * catch-all that would report it to a student as "not on file" when the
 * posting might well exist.
 */
export const load: PageServerLoad = async ({ params }) => {
	try {
		const { job, benchmark } = await getJobPosting(params.id);
		return {
			job: toJobPostingDetailView(job),
			benchmark,
		};
	} catch (err) {
		if (err instanceof ApiError && err.status === 404) {
			error(404, messages.jobs.notFound);
		}
		if (err instanceof Error && err.message.startsWith("Unknown job")) {
			error(404, messages.jobs.notFound);
		}
		throw err;
	}
};

/**
 * Generating a match report. The data layer's own two failure shapes become
 * the two `fail()`s a student can actually hit; anything else re-throws,
 * because a provider failing for a reason nobody has thought about must not be
 * reported as an ordinary "no resume" or "service down" outcome.
 */
export const actions: Actions = {
	report: async ({ params, locals }) => {
		if (apiEnabled() && !locals.student) {
			return fail(401, { error: messages.jobs.errors.signedOut });
		}

		try {
			const report = await generateMatchReport(params.id);
			return { report };
		} catch (err) {
			if (err instanceof ApiError) {
				if (err.status === 409) return fail(409, { error: messages.jobs.report.noResume });
				if (err.status === 503) return fail(503, { error: messages.jobs.report.unavailable });
			}
			throw err;
		}
	},
};
