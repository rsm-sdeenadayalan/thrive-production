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
	return apiFetch<Task[]>("/tasks");
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
