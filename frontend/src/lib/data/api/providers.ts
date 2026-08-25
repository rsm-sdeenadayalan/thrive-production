/**
 * HTTP implementations of the provider contract. Bodies only — the public
 * surface stays `$lib/data`; `providers.ts` delegates here when
 * THRIVE_API_ORIGIN is set. Server-only.
 */
import { currentAuth } from "$lib/server/requestContext";

import type {
	Advisor,
	Appointment,
	AppointmentSlot,
	Assignment,
	AskDestination,
	Conversation,
	ConversationStarter,
	Course,
	CourseRequest,
	CourseRequestInput,
	CourseRequestPrefill,
	DegreeProgress,
	Event,
	JobFeedResult,
	JobFeedTab,
	JobInteractionState,
	JobRegion,
	JobPostingDetail,
	JobSearchResult,
	MatchReport,
	ProgramTimeline,
	ResourceLink,
	ResumeDiff,
	ResumeVersion,
	RoleBenchmark,
	Skill,
	Student,
	Syllabus,
	Task,
} from "../types";
import { SlotUnavailableError } from "../errors";
import { ApiError, apiFetch } from "./client";

export async function getStudent(): Promise<Student> {
	const cached = currentAuth()?.student;
	if (cached) return { ...cached };
	return apiFetch<Student>("/me");
}

export function getCourses(): Promise<Course[]> {
	return apiFetch<Course[]>("/courses");
}

export function getSyllabi(): Promise<Syllabus[]> {
	return apiFetch<Syllabus[]>("/syllabi");
}

export function getAssignments(): Promise<Assignment[]> {
	return apiFetch<Assignment[]>("/assignments");
}

export function getTasks(): Promise<Task[]> {
	// In API mode the client owns the merge (stores are seeded from the
	// server), so this must deliver SOURCE tasks, exactly like the mock
	// provider does. `/tasks` without the query stays the server-merged view,
	// used by the contract suite.
	return apiFetch<Task[]>("/tasks?view=source");
}

export function getEvents(): Promise<Event[]> {
	return apiFetch<Event[]>("/events");
}

export function getDegreeProgress(): Promise<DegreeProgress> {
	return apiFetch<DegreeProgress>("/degree/progress");
}

export function getProgramTimeline(): Promise<ProgramTimeline> {
	return apiFetch<ProgramTimeline>("/degree/timeline");
}

export function getResources(): Promise<ResourceLink[]> {
	return apiFetch<ResourceLink[]>("/resources");
}

export function getAdvisors(): Promise<Advisor[]> {
	return apiFetch<Advisor[]>("/advisors");
}

export function getSlots(advisorId: string): Promise<AppointmentSlot[]> {
	return apiFetch<AppointmentSlot[]>(
		`/advisors/${encodeURIComponent(advisorId)}/slots`,
	);
}

export function getMyAppointments(): Promise<Appointment[]> {
	return apiFetch<Appointment[]>("/appointments");
}

export function getConversations(): Promise<Conversation[]> {
	return apiFetch<Conversation[]>("/conversations");
}

/**
 * The opening prompt for a destination, or null when it has none.
 *
 * Comes from the backend rather than being written in the frontend so the
 * question a student is opened on and the question they are re-asked are the
 * same string from the same place. Only the course recommender has a script;
 * the other destinations return null and keep their existing empty state.
 *
 * A failure here is not worth a broken page: the empty state is a perfectly
 * good fallback, so this swallows the error and returns null.
 */
export async function getConversationStarter(
	destination: string,
): Promise<ConversationStarter | null> {
	if (destination !== "courses") return null;
	try {
		const body = await apiFetch<{ starter: ConversationStarter | null }>(
			"/plan/intake",
		);
		return body.starter ?? null;
	} catch {
		return null;
	}
}

export async function getConversation(
	conversationId: string,
): Promise<Conversation | null> {
	try {
		return await apiFetch<Conversation>(
			`/conversations/${encodeURIComponent(conversationId)}`,
		);
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}

/**
 * Write providers for the chat composer. No mock counterpart on purpose --
 * mock mode's `ChatWindow` never persists anything (see its own doc comment),
 * so there is nothing for these to delegate through and they are not added to
 * `data/providers.ts`'s list. `/ask-sync` imports them directly, the same way
 * `/overlay-sync` imports `apiFetch` directly rather than going through a
 * delegator.
 */
export function createConversation(
	destination: AskDestination,
	body: string,
): Promise<Conversation> {
	return apiFetch<Conversation>("/conversations", {
		method: "POST",
		body: { destination, body },
	});
}

export function sendConversationMessage(
	conversationId: string,
	body: string,
): Promise<Conversation> {
	return apiFetch<Conversation>(
		`/conversations/${encodeURIComponent(conversationId)}/messages`,
		{ method: "POST", body: { body } },
	);
}

export async function bookAppointment(
	slotId: string,
	reason: string,
): Promise<Appointment> {
	try {
		return await apiFetch<Appointment>("/appointments", {
			method: "POST",
			body: { slotId, reason },
		});
	} catch (error) {
		if (
			error instanceof ApiError &&
			(error.status === 409 || error.code === "slot_unknown")
		) {
			throw new SlotUnavailableError(error.message);
		}
		throw error;
	}
}

export async function cancelAppointment(
	appointmentId: string,
): Promise<Appointment | null> {
	try {
		return await apiFetch<Appointment>(
			`/appointments/${encodeURIComponent(appointmentId)}/cancel`,
			{ method: "POST" },
		);
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}

export function getRequestPrefill(): Promise<CourseRequestPrefill> {
	return apiFetch<CourseRequestPrefill>("/requests/prefill");
}

export function createRequest(input: CourseRequestInput): Promise<CourseRequest> {
	return apiFetch<CourseRequest>("/requests", { method: "POST", body: input });
}

export async function submitRequest(
	requestId: string,
): Promise<CourseRequest | null> {
	try {
		return await apiFetch<CourseRequest>(
			`/requests/${encodeURIComponent(requestId)}/submit`,
			{ method: "POST" },
		);
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}

export function getMyRequests(): Promise<CourseRequest[]> {
	return apiFetch<CourseRequest[]>("/requests");
}

export async function getTssConnection(): Promise<boolean> {
	return (await apiFetch<{ connected: boolean }>("/tss")).connected;
}

export async function connectTss(): Promise<boolean> {
	return (
		await apiFetch<{ connected: boolean }>("/tss/connect", { method: "POST" })
	).connected;
}

export function getSkills(): Promise<Skill[]> {
	return apiFetch<Skill[]>("/resume/skills");
}

export function getResumeVersions(): Promise<ResumeVersion[]> {
	return apiFetch<ResumeVersion[]>("/resume/versions");
}

export async function getCurrentResume(): Promise<ResumeVersion | null> {
	try {
		return await apiFetch<ResumeVersion>("/resume/current");
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}

export function generateNewVersion(): Promise<{
	version: ResumeVersion;
	diff: ResumeDiff;
}> {
	return apiFetch<{ version: ResumeVersion; diff: ResumeDiff }>(
		"/resume/versions",
		{ method: "POST" },
	);
}

export async function setCurrentVersion(
	versionId: string,
): Promise<ResumeVersion | null> {
	try {
		return await apiFetch<ResumeVersion>(
			`/resume/versions/${encodeURIComponent(versionId)}/current`,
			{ method: "POST" },
		);
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}

// ---------------------------------------------------------------------------
// Job search
// ---------------------------------------------------------------------------

export function searchJobs(query: string): Promise<JobSearchResult> {
	return apiFetch<JobSearchResult>(`/jobs?q=${encodeURIComponent(query)}`);
}

export function getJobPosting(
	jobId: string,
): Promise<{ job: JobPostingDetail; benchmark: RoleBenchmark }> {
	return apiFetch<{ job: JobPostingDetail; benchmark: RoleBenchmark }>(
		`/jobs/${encodeURIComponent(jobId)}`,
	);
}

export async function generateMatchReport(jobId: string): Promise<MatchReport> {
	const { report } = await apiFetch<{ report: MatchReport }>(
		`/jobs/${encodeURIComponent(jobId)}/report`,
		{ method: "POST" },
	);
	return report;
}

/**
 * Multipart upload: the resume file goes in a `FormData` body so `client.ts`
 * skips JSON-encoding it and leaves the content-type header for the runtime
 * to set with its multipart boundary.
 */
export async function uploadResume(file: File): Promise<void> {
	const body = new FormData();
	body.append("file", file);
	await apiFetch<unknown>("/resume/upload", { method: "POST", body });
}

// ---------------------------------------------------------------------------
// Job feed
// ---------------------------------------------------------------------------

export function getJobFeed(params: {
	tab?: JobFeedTab;
	q?: string;
	minScore?: number;
	/** Results-page-only: score the top candidates with the real LLM rubric
	 *  instead of the hybrid-search proxy. See `feed_for`'s `score_with_llm`. */
	scoreWithLlm?: boolean;
	/** Narrows the candidate pool to one location bucket. See `feed_for`'s
	 *  `region` and `services/jobs/region.py`. Omitted (or `""`, never sent)
	 *  means "All regions." */
	region?: JobRegion | "";
}): Promise<JobFeedResult> {
	const search = new URLSearchParams();
	if (params.tab !== undefined) search.set("tab", params.tab);
	if (params.q !== undefined) search.set("q", params.q);
	if (params.minScore !== undefined) search.set("min_score", String(params.minScore));
	if (params.scoreWithLlm) search.set("score_with_llm", "1");
	if (params.region) search.set("region", params.region);
	const qs = search.toString();
	return apiFetch<JobFeedResult>(`/jobs/feed${qs ? `?${qs}` : ""}`);
}

export function likeJob(jobId: string): Promise<JobInteractionState> {
	return apiFetch<JobInteractionState>(
		`/jobs/${encodeURIComponent(jobId)}/like`,
		{ method: "POST" },
	);
}

export function dismissJob(jobId: string): Promise<JobInteractionState> {
	return apiFetch<JobInteractionState>(
		`/jobs/${encodeURIComponent(jobId)}/dismiss`,
		{ method: "POST" },
	);
}
