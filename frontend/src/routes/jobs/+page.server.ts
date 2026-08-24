import { fail, redirect } from "@sveltejs/kit";

import { apiEnabled, ApiError } from "$lib/data/api/client";
import { dismissJob, getJobFeed, likeJob, searchJobs, uploadResume } from "$lib/data";
import type { JobFeedTab, RoleBenchmark } from "$lib/data";
import { toJobFeedEntryView } from "$lib/jobs";
import { messages } from "$lib/messages";
import type { Actions, PageServerLoad } from "./$types";

/**
 * The Career tab: a ranked feed, not a search box waiting for a query.
 *
 * ## `tab`, `q` and `minScore` are all search params, not stored preferences
 *
 * Same reasoning `/jobs` always had for `q`: a GET form and plain links keep
 * the feed linkable and shareable exactly as viewed, with no client-side
 * fetch to keep in sync with the address bar.
 *
 * ## No short-circuit on a blank query, unlike the search page this replaced
 *
 * The old `/jobs` had nothing to show without a query, so it skipped the
 * search entirely rather than pay for one whose results were thrown away
 * unseen. A feed is the opposite: Recommended is exactly what a student with
 * no query wants to see, so `q` blank is the feed's normal resting state, not
 * a state with nothing to fetch.
 *
 * ## The benchmark is a second call, on purpose
 *
 * `JobFeedResult` carries no benchmark -- it is a ranked list of postings, not
 * a search result -- so the panel that shows what a role typically asks for
 * still comes from `searchJobs`, exactly as it did before. That call only
 * happens when `q` is non-empty, matching `BenchmarkPanel`'s own condition on
 * the page: no query, no benchmark to compute.
 */
export const load: PageServerLoad = async ({ url }) => {
	const tab = parseTab(url.searchParams.get("tab"));
	const q = url.searchParams.get("q") ?? "";
	const minScore = parseMinScore(url.searchParams.get("minScore"));

	const [feed, benchmark] = await Promise.all([
		getJobFeed({ tab, q, minScore }),
		q.trim().length > 0 ? searchJobs(q).then((result) => result.benchmark) : Promise.resolve<RoleBenchmark | null>(null),
	]);

	return {
		tab,
		q,
		minScore,
		profileAvailable: feed.profileAvailable,
		counts: feed.counts,
		results: feed.results.map((entry) => toJobFeedEntryView(entry, feed.profileAvailable)),
		benchmark,
	};
};

const FEED_TABS = new Set<JobFeedTab>(["recommended", "liked", "all"]);

function parseTab(value: string | null): JobFeedTab {
	return value !== null && FEED_TABS.has(value as JobFeedTab) ? (value as JobFeedTab) : "recommended";
}

function parseMinScore(value: string | null): number | undefined {
	if (value === null) return undefined;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : undefined;
}

function formString(form: FormData, key: string): string | null {
	const value = form.get(key);
	return typeof value === "string" ? value : null;
}

/**
 * Where an action sends the student back to.
 *
 * Every mutation on this page -- upload, like, dismiss -- is followed by a
 * redirect back to the same tab/query/minScore rather than a returned view
 * model, the same rule `actions.upload` already followed: a redirect makes
 * `load` re-run, which is what turns a like into a filled heart and a
 * dismissal into a card disappearing on its own rather than the page
 * guessing that it should.
 *
 * Reads from the submitted form first and the current URL second, matching
 * how `actions.upload` already fell back to `url.searchParams` for `q` --
 * every form on this page carries its own hidden copies of `tab`/`q`/
 * `minScore` so a like on the Liked tab does not silently bounce a student
 * back to Recommended.
 */
function redirectTarget(form: FormData, url: URL): string {
	const tab = parseTab(formString(form, "tab") ?? url.searchParams.get("tab"));
	const q = formString(form, "q") ?? url.searchParams.get("q") ?? "";
	const minScore = formString(form, "minScore") ?? url.searchParams.get("minScore");

	const params = new URLSearchParams();
	if (tab !== "recommended") params.set("tab", tab);
	if (q.trim().length > 0) params.set("q", q);
	if (minScore !== null && minScore.trim().length > 0) params.set("minScore", minScore);

	const query = params.toString();
	return query ? `/jobs?${query}` : "/jobs";
}

/**
 * Uploading a resume, liking a posting, dismissing one.
 *
 * ## Errors are values, the same rule appointments follows
 *
 * Each provider call can throw `ApiError` in API mode; anything else escapes
 * rather than being reported to a student as a problem they can act on.
 *
 * ## Both guard first, matching appointments' actions
 *
 * No `locals.student` while `apiEnabled()` is true means the session lapsed
 * between page render and form submit -- a `fail()`, not a thrown error a
 * student cannot act on.
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

		redirect(303, redirectTarget(form, url));
	},

	like: async ({ request, locals, url }) => {
		if (apiEnabled() && !locals.student) {
			return fail(401, { error: messages.jobs.errors.signedOut });
		}

		const form = await request.formData();
		const jobId = formString(form, "jobId");
		if (!jobId) return fail(400, { error: messages.jobs.notFound });

		await likeJob(jobId);
		redirect(303, redirectTarget(form, url));
	},

	dismiss: async ({ request, locals, url }) => {
		if (apiEnabled() && !locals.student) {
			return fail(401, { error: messages.jobs.errors.signedOut });
		}

		const form = await request.formData();
		const jobId = formString(form, "jobId");
		if (!jobId) return fail(400, { error: messages.jobs.notFound });

		await dismissJob(jobId);
		redirect(303, redirectTarget(form, url));
	},
};
