import { fail, redirect } from "@sveltejs/kit";

import { apiEnabled, ApiError } from "$lib/data/api/client";
import { getJobFeed, uploadResume } from "$lib/data";
import { messages } from "$lib/messages";
import type { Actions, PageServerLoad } from "./$types";

/**
 * The Career tab, step 1: setup, not results.
 *
 * ## Why this redirects rather than ever rendering a feed
 *
 * `/jobs` used to BE the feed -- search box, tabs and ranked cards all on one
 * page. It is now the page a student lands on before searching: the intro,
 * the resume panel, and a role search that hands off to `/jobs/results`. Any
 * URL carrying `tab`, `q` or `minScore` is a link built for the OLD single
 * page (a bookmark, a stale link elsewhere in the app, someone's browser
 * history) and the honest thing to do with it is land the student on the
 * results it always meant, not silently drop the state it was carrying.
 *
 * ## `getJobFeed` runs anyway, for `profileAvailable` alone
 *
 * There is no narrower call in the data layer for "does this student have a
 * resume on file" -- see the module note in `$lib/data/providers` -- and
 * adding one would be a backend-shaped change this restructuring does not
 * make. Asking for the (unused) recommended feed and reading only its
 * `profileAvailable` flag costs one round trip, the same one `/jobs` already
 * paid before this split.
 */
export const load: PageServerLoad = async ({ url }) => {
	if (url.searchParams.has("q") || url.searchParams.has("tab") || url.searchParams.has("minScore")) {
		redirect(303, `/jobs/results?${url.searchParams.toString()}`);
	}

	const feed = await getJobFeed({});

	return {
		profileAvailable: feed.profileAvailable,
	};
};

/**
 * Uploading a resume. The only mutation left on this page -- liking and
 * dismissing postings both moved to `/jobs/results` along with the cards
 * they act on.
 *
 * Same guard-then-act shape every action in this app follows: no
 * `locals.student` while `apiEnabled()` is true means the session lapsed
 * between page render and form submit, a `fail()` rather than a thrown error.
 */
export const actions: Actions = {
	upload: async ({ request, locals }) => {
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
				/*
				 * Say WHICH thing was wrong with the file.
				 *
				 * Every rejection used to collapse into one "Something went wrong —
				 * try again", so the three failures a student can actually cause and
				 * fix — a scan with no text layer, a file over 5MB, something that
				 * is not a PDF — were indistinguishable from each other and from a
				 * server fault, and the advice attached to all of them ("try again")
				 * is the one thing that cannot help with any of the three.
				 *
				 * Keyed by the backend's error code; an unrecognised code still
				 * falls back to the generic line, which is what it is for.
				 */
				const reasons: Record<string, string> = messages.jobs.profileBanner.uploadErrors;
				return fail(error.status, {
					error: reasons[error.code] ?? messages.jobs.profileBanner.error,
				});
			}
			throw error;
		}

		// Back to this same page -- the resume panel switches to its
		// "on file" shape and the banner disappears on its own.
		redirect(303, "/jobs");
	},
};
