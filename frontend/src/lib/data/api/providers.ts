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
	Conversation,
	Course,
	CourseRequest,
	CourseRequestInput,
	CourseRequestPrefill,
	DegreeProgress,
	Event,
	ProgramTimeline,
	ResourceLink,
	ResumeDiff,
	ResumeVersion,
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
