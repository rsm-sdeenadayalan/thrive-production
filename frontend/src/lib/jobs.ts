import type {
  JobCompetency,
  JobFeedEntry,
  JobFeedTab,
  JobPostingDetail,
  JobRegion,
  JobSearchEntry,
} from "$lib/data";
import { formatShortDate } from "$lib/format";
import { messages } from "$lib/messages";

/**
 * Job search's vocabulary and arithmetic.
 *
 * Everything here is pure and clock-free -- the same split `ask.ts` draws.
 * Dates arrive already formatted (`formatShortDate` is called once, on the
 * server, inside the view-model builders below) so the routes never hand a
 * component a raw `postedAt` to interpret.
 */

// ---------------------------------------------------------------------------
// Results list
// ---------------------------------------------------------------------------

/** One search result, with every date already a string. */
export interface JobResultView {
  id: string;
  title: string;
  company: string;
  location: string;
  /** Null when the posting carries no date, same as the source field. */
  postedAtLabel: string | null;
  matchedSkills: string[];
  missingSkills: string[];
  /** Null when there is no resume to score against yet. */
  score: number | null;
}

/**
 * A search entry becomes a view model.
 *
 * `score` collapses to `null` when the student has no profile to score
 * against, rather than the card deciding whether to trust a number the
 * provider still filled in. One place makes that call, not every card that
 * renders one.
 */
export function toJobResultView(
  entry: JobSearchEntry,
  profileAvailable: boolean,
): JobResultView {
  return {
    id: entry.job.id,
    title: entry.job.title,
    company: entry.job.company,
    location: entry.job.location,
    postedAtLabel: entry.job.postedAt ? formatShortDate(entry.job.postedAt) : null,
    matchedSkills: entry.matchedSkills,
    missingSkills: entry.missingSkills,
    score: profileAvailable ? entry.score : null,
  };
}

/**
 * Which of the two dead ends applies, or none.
 *
 * Two things can make a results list empty, and they are different states: a
 * student who has not searched yet is not the same as one whose search came
 * back with nothing. Extracted so the page does not re-derive the same
 * either/or from `query` and `results.length` inline.
 */
export type JobsEmptyState = "no-query" | "no-results" | null;

export function jobsEmptyState(
  query: string,
  resultCount: number,
): JobsEmptyState {
  if (query.trim().length === 0) return "no-query";
  if (resultCount === 0) return "no-results";
  return null;
}

// ---------------------------------------------------------------------------
// Detail page
// ---------------------------------------------------------------------------

/** A posting's full detail, with its date already a string. */
export interface JobPostingDetailView {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  skills: string[];
  postedAtLabel: string | null;
  description: string;
}

export function toJobPostingDetailView(
  job: JobPostingDetail,
): JobPostingDetailView {
  return {
    id: job.id,
    title: job.title,
    company: job.company,
    location: job.location,
    url: job.url,
    source: job.source,
    skills: job.skills,
    postedAtLabel: job.postedAt ? formatShortDate(job.postedAt) : null,
    description: job.description,
  };
}

// ---------------------------------------------------------------------------
// Benchmark
// ---------------------------------------------------------------------------

/**
 * A skill's share of a benchmark sample, as a bar width.
 *
 * `RoleBenchmark.topSkills[].share` arrives as a 0-1 fraction. Rounded rather
 * than left with float noise, since it feeds both a percentage bar's width
 * and its printed value -- and the two would disagree at the fourth decimal
 * place if only one of them rounded.
 */
export function shareWidth(share: number): string {
  const clamped = Math.max(0, Math.min(1, share));
  return `${Math.round(clamped * 100)}%`;
}

// ---------------------------------------------------------------------------
// Match report
// ---------------------------------------------------------------------------

/** A competency's word, from the one map that owns the translation. */
export function competencyLabel(competency: JobCompetency): string {
  return messages.jobs.report.competencyLabels[competency];
}

// ---------------------------------------------------------------------------
// Job feed
// ---------------------------------------------------------------------------

/** One feed entry, with every date already a string and its score resolved. */
export interface JobFeedEntryView {
  id: string;
  title: string;
  company: string;
  location: string;
  postedLabel: string | null;
  url: string;
  /** Null when there is no resume to score against yet. */
  score: number | null;
  /** Whether `score` came from a generated report or the search estimate. */
  scoreKind: "report" | "estimate";
  competency: JobCompetency | null;
  matchedSkills: string[];
  missingSkills: string[];
  liked: boolean;
  dismissed: boolean;
}

/**
 * A feed entry becomes a view model.
 *
 * The displayed score prefers the cached report's score over the hybrid
 * search score that ranked the feed -- a generated report is the stronger
 * signal -- and collapses to `null` under the same rule `toJobResultView`
 * uses: no profile, no number for a card to render.
 */
export function toJobFeedEntryView(
  entry: JobFeedEntry,
  profileAvailable: boolean,
): JobFeedEntryView {
  const resolvedScore = entry.reportScore ?? entry.score;
  return {
    id: entry.job.id,
    title: entry.job.title,
    company: entry.job.company,
    location: entry.job.location,
    postedLabel: entry.job.postedAt ? formatShortDate(entry.job.postedAt) : null,
    url: entry.job.url,
    score: profileAvailable ? resolvedScore : null,
    scoreKind: entry.reportScore === null ? "estimate" : "report",
    competency: entry.competency,
    matchedSkills: entry.matchedSkills,
    missingSkills: entry.missingSkills,
    liked: entry.liked,
    dismissed: entry.dismissed,
  };
}

/**
 * Which of the feed's three dead ends applies.
 *
 * Unlike `jobsEmptyState`, the feed always has something selected -- there is
 * no "haven't searched yet" state, only a tab that came back with nothing --
 * so this takes no result count and callers only reach for it once they
 * already know the current tab is empty.
 */
export type JobFeedEmptyState =
  | "no-jobs-at-all"
  | "no-matches-for-query"
  | "liked-tab-empty";

export function feedEmptyState(tab: JobFeedTab, q: string): JobFeedEmptyState {
  if (tab === "liked") return "liked-tab-empty";
  if (q.trim().length > 0) return "no-matches-for-query";
  return "no-jobs-at-all";
}

/** A score as a ring's fill percentage: 0-100, clamped against bad input. */
export function ringPercent(score: number): number {
  return Math.max(0, Math.min(100, score));
}

// ---------------------------------------------------------------------------
// Targeted results (Career, step 2)
// ---------------------------------------------------------------------------

/**
 * The Recommended tab's whole reason to exist: a SHORT list, not a feed.
 *
 * A student optimizing for interview conversions is worse off staring at
 * fifty ranked postings than at the ten that are actually worth the hour it
 * takes to prep one -- and worse off still if the tenth spot is filled by
 * something scoring 30, dragged in only because the query had few results.
 * `cap` bounds the length; `floor` bounds the quality, independently -- a
 * search with three strong matches shows three, not padded out to ten.
 *
 * An entry with a `null` score (no resume on file yet, see
 * `toJobFeedEntryView`) always clears `floor`: there is no number to judge it
 * against, so silently dropping it would read as the search coming back
 * emptier than it is, not as "upload a resume for a real score."
 *
 * Pure and order-preserving -- `entries` is trusted to already be sorted by
 * display score, descending, the same trust `JobFeedCard` already places in
 * `getJobFeed`'s ranking.
 */
export function targetResults(
  entries: JobFeedEntryView[],
  { cap = 10, floor = 45 }: { cap?: number; floor?: number } = {},
): JobFeedEntryView[] {
  return entries.filter((entry) => entry.score === null || entry.score >= floor).slice(0, cap);
}

// ---------------------------------------------------------------------------
// Region filter (results page)
// ---------------------------------------------------------------------------

/**
 * Every selectable region, in the same priority order
 * `backend/rsm_thrive/services/jobs/region.py` checks them in. `""` (all
 * regions, the default) is deliberately not a member -- it is the absence
 * of a filter, not one more bucket to render alongside these.
 */
export const JOB_REGIONS: JobRegion[] = [
  "remote",
  "san_diego",
  "bay_area",
  "los_angeles",
  "seattle",
  "new_york",
  "other_us",
  "international",
];

export function isJobRegion(value: string): value is JobRegion {
  return (JOB_REGIONS as string[]).includes(value);
}

/**
 * A region's display label, from the one map that owns the translation --
 * same pattern `competencyLabel` uses. `null` (all regions) reads as "All
 * regions."
 */
export function jobRegionLabel(region: JobRegion | null): string {
  return region === null
    ? messages.jobs.results.regions.all
    : messages.jobs.results.regions.names[region];
}

/**
 * The mock provider's offline stand-in for `region_of` in
 * `backend/rsm_thrive/services/jobs/region.py`.
 *
 * Not required to be byte-for-byte identical to the backend's heuristic --
 * mock mode exists so the app runs with no API configured, not to reproduce
 * production ranking -- but it follows the same priority order (Remote
 * first, so a "Remote" fixture never gets swallowed by a named city) so a
 * developer poking at the region filter offline sees behaviour that rhymes
 * with the real one.
 */
export function regionOf(location: string): JobRegion {
  const text = location.toLowerCase();
  if (text.includes("remote")) return "remote";
  if (text.includes("san diego")) return "san_diego";
  if (["san francisco", "bay area", "san jose", "oakland"].some((k) => text.includes(k))) {
    return "bay_area";
  }
  if (text.includes("los angeles")) return "los_angeles";
  if (text.includes("seattle") || text.includes("bellevue")) return "seattle";
  if (text.includes("new york")) return "new_york";
  if (/\b(usa|united states)\b/.test(text) || /,\s*[a-z]{2}\b/.test(text)) return "other_us";
  return "international";
}
