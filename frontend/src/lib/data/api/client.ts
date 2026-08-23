/**
 * Server-only HTTP client for the Django API. Reads the incoming request's
 * cookie from the per-request AsyncLocalStorage context, so provider
 * signatures never carry credentials. Never import from a component.
 */
import { currentAuth } from "$lib/server/requestContext";

export class ApiError extends Error {
	constructor(
		public status: number,
		public code: string,
		message: string,
	) {
		super(message);
		this.name = "ApiError";
	}
}

export function apiOrigin(): string | null {
	return process.env.THRIVE_API_ORIGIN || null;
}

export function apiEnabled(): boolean {
	return apiOrigin() !== null;
}

function csrfToken(cookie: string): string | null {
	const match = cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
	return match ? match[1] : null;
}

interface Envelope {
	error?: { code?: string; message?: string };
}

export async function apiFetch<T>(
	path: string,
	init: { method?: string; body?: unknown } = {},
): Promise<T> {
	const origin = apiOrigin();
	if (!origin) throw new Error("THRIVE_API_ORIGIN is not set");
	const auth = currentAuth();
	const method = init.method ?? "GET";
	const headers: Record<string, string> = { accept: "application/json" };
	if (auth?.cookie) headers.cookie = auth.cookie;
	if (method !== "GET" && auth?.cookie) {
		const token = csrfToken(auth.cookie);
		if (token) headers["x-csrftoken"] = token;
		headers.referer = origin;
	}
	if (init.body !== undefined) headers["content-type"] = "application/json";
	const response = await fetch(`${origin}/api/thrive${path}`, {
		method,
		headers,
		body: init.body === undefined ? undefined : JSON.stringify(init.body),
	});
	if (response.status === 204) return undefined as T;
	const payload = (await response.json().catch(() => null)) as (Envelope & T) | null;
	if (!response.ok) {
		throw new ApiError(
			response.status,
			payload?.error?.code ?? "unknown",
			payload?.error?.message ?? `API error ${response.status}`,
		);
	}
	return payload as T;
}
