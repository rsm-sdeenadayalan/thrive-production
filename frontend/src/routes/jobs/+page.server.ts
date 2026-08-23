import { fail, redirect } from "@sveltejs/kit";

import { apiEnabled, ApiError } from "$lib/data/api/client";
import { searchJobs, uploadResume } from "$lib/data";
import { toJobResultView } from "$lib/jobs";
import { messages } from "$lib/messages";
import type { Actions, PageServerLoad } from "./$types";

/**
 * The search page: a query, a benchmark, and a ranked list.
 *
 * ## The query is a search param, not a stored preference
 *
 * A GET form with no JavaScript needed -- `q` lands in the URL, `load` reads
 * it, and the page is linkable and shareable exactly as searched. There is no
 * client-side fetch to keep in sync with the address bar.
 *
 * ## Every date is formatted here, once
 *
 * `toJobResultView` calls `formatShortDate` on each posting's `postedAt`
 * before it ever reaches a component, the same rule every other surface in
 * this app follows: a `.svelte` file never sees a raw instant.
 *
 * ## No query, no search
 *
 * The page's own empty state ("Search above to see postings") already covers
 * a student who has not typed anything, and ignores `results` in that case.
 * Calling `searchJobs` anyway would mean every landing hit -- `/jobs` with no
 * `q` at all -- pays for a full unfiltered search whose results are thrown
 * away unseen. A blank/whitespace-only query skips the call entirely.
 */
export const load: PageServerLoad = async ({ url }) => {
	const query = url.searchParams.get("q") ?? "";

	if (query.trim().length === 0) {
		return {
			query,
			profileAvailable: false,
			benchmark: { sampleSize: 0, topSkills: [] },
			results: [],
		};
	}

	const result = await searchJobs(query);

	return {
		query,
		profileAvailable: result.profileAvailable,
		benchmark: result.benchmark,
		results: result.results.map((entry) => toJobResultView(entry, result.profileAvailable)),
	};
};

/**
 * Uploading a resume, the one mutation this page has.
 *
 * ## Errors are values, the same rule appointments follows
 *
 * `uploadResume` throws `ApiError` in API mode; anything else escapes rather
 * than being reported to a student as an upload problem they can act on.
 *
 * ## Success is a redirect back to the same search
 *
 * Not a returned view model: a redirect makes `load` re-run, which is what
 * turns `profileAvailable` true and makes the banner disappear on its own
 * rather than the page guessing that it should.
 */
export const actions: Actions = {
	upload: async ({ request, locals, url }) => {
		if (apiEnabled() && !locals.student) {
			return fail(401, { error: messages.jobs.errors.signedOut });
		}

		const form = await request.formData();
		const file = form.get("file");

		if (!(file instanceof File) || file.size === 0) {
			return fail(400, { error: messages.jobs.profileBanner.empty });
		}

		try {
			await uploadResume(file);
		} catch (error) {
			if (error instanceof ApiError) {
				return fail(error.status, { error: messages.jobs.profileBanner.error });
			}
			throw error;
		}

		const rawQuery = form.get("q");
		const query =
			(typeof rawQuery === "string" ? rawQuery : null) ?? url.searchParams.get("q") ?? "";
		redirect(303, `/jobs?q=${encodeURIComponent(query)}`);
	},
};
