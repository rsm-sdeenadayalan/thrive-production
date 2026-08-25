import { fail, redirect } from "@sveltejs/kit";

import { apiEnabled } from "$lib/data/api/client";
import { dismissJob, getJobFeed, likeJob, searchJobs } from "$lib/data";
import type { JobFeedTab, RoleBenchmark } from "$lib/data";
import { targetResults, toJobFeedEntryView } from "$lib/jobs";
import { messages } from "$lib/messages";
import type { Actions, PageServerLoad } from "./$types";

/**
 * The Career tab, step 2: the ranked list `/jobs` hands off to.
 *
 * ## `tab`, `q` and `minScore` are search params, not stored preferences
 *
 * Same reasoning the single-page version this replaced always had: a GET
 * form and plain links keep the results linkable and shareable exactly as
 * viewed, with no client-side fetch to keep in sync with the address bar.
 *
 * ## Recommended is the only tab `targetResults` touches
 *
 * Liked and All exist specifically so the capping and floor-filtering on
 * Recommended has an escape hatch -- a safety valve for "show me literally
 * everything," see `messages.jobs.results.tabHints.all`. Running the same cap
 * and floor there would defeat the point of having them as a separate tab at
 * all, so only `tab === "recommended"` ever calls `targetResults`; Liked and
 * All render exactly what `getJobFeed` returned.
 *
 * `rawRecommendedCount` and `targetedCount` travel down only when
 * `tab === "recommended"` (`null` otherwise) -- they exist purely so the page
 * can tell "no postings matched at all" apart from "postings matched, none
 * cleared the bar" apart from "a couple cleared it, worth flagging as thin."
 * Both counts are `null` on Liked/All because that distinction does not apply
 * there: whatever `getJobFeed` returned for those tabs *is* what renders.
 */
export const load: PageServerLoad = async ({ url }) => {
	const tab = parseTab(url.searchParams.get("tab"));
	const q = url.searchParams.get("q") ?? "";
	const minScore = parseMinScore(url.searchParams.get("minScore"));

	const [feed, benchmark] = await Promise.all([
		getJobFeed({ tab, q, minScore }),
		q.trim().length > 0 ? searchJobs(q).then((result) => result.benchmark) : Promise.resolve<RoleBenchmark | null>(null),
	]);

	const viewEntries = feed.results.map((entry) => toJobFeedEntryView(entry, feed.profileAvailable));

	const isRecommended = tab === "recommended";
	const targeted = isRecommended ? targetResults(viewEntries) : viewEntries;

	const counts = { ...feed.counts };
	if (isRecommended) {
		// The tab bar's own label should match what is actually on screen when
		// you are looking at it -- the raw backend count would read as a typo
		// the moment it disagreed with the list underneath it.
		counts.recommended = targeted.length;
	}

	return {
		tab,
		q,
		minScore,
		profileAvailable: feed.profileAvailable,
		counts,
		results: targeted,
		rawRecommendedCount: isRecommended ? viewEntries.length : null,
		targetedCount: isRecommended ? targeted.length : null,
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
 * Every mutation on this page -- like, dismiss -- is followed by a redirect
 * back to the same tab/query/minScore rather than a returned view model: a
 * redirect makes `load` re-run, which is what turns a like into a filled
 * heart and a dismissal into a card disappearing on its own rather than the
 * page guessing that it should.
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
	return query ? `/jobs/results?${query}` : "/jobs/results";
}

/**
 * Liking a posting, dismissing one. Uploading a resume stays on `/jobs` --
 * this page only acts on postings already on screen.
 *
 * ## Errors are values, the same rule appointments follows
 *
 * Each provider call can throw `ApiError` in API mode; anything else escapes
 * rather than being reported to a student as a problem they can act on.
 */
export const actions: Actions = {
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
