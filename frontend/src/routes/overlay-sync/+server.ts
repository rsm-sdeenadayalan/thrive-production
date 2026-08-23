/**
 * Same-origin proxy for overlaySync's fire-and-forget writes.
 *
 * A client component can only fetch same-origin (no CSRF token, no Django
 * cookie visible to it); this route is what turns `{op, ...payload}` into an
 * authenticated `apiFetch` call. It runs inside the hooks' `runWithAuth`
 * context, so `apiFetch` already has the incoming cookie and CSRF token — this
 * file only has to know the allowlist of ops and how each maps to a Django
 * path/method/body.
 *
 * The allowlist is deliberately closed: an op string this table doesn't know
 * about is a 400, never a pass-through to an arbitrary path.
 */
import { json } from "@sveltejs/kit";

import { ApiError, apiEnabled, apiFetch } from "$lib/data/api/client";
import type { RequestHandler } from "./$types";

type Payload = Record<string, unknown>;

interface Forward {
	path: string;
	method: string;
	body?: unknown;
}

function enc(value: unknown): string {
	return encodeURIComponent(String(value));
}

function projectTaskAdd(task: unknown): Payload {
	// Subtasks are deliberately not persisted: every addTask caller creates
	// them empty, and the seed rebuilds added tasks with the stored [] anyway.
	const source = (task ?? {}) as Payload;
	return {
		title: source.title,
		dueDate: source.dueDate,
		priority: source.priority,
		source: source.source,
		clientKey: source.clientKey,
	};
}

function projectCustomEvent(event: unknown): Payload {
	const source = (event ?? {}) as Payload;
	return {
		title: source.title,
		dayKey: source.dayKey,
		time: source.time,
		label: source.label,
		urgent: source.urgent,
		createdAt: source.createdAt,
	};
}

function projectQuickItem(item: unknown): Payload {
	const source = (item ?? {}) as Payload;
	return {
		title: source.title,
		done: source.done,
		createdAt: source.createdAt,
		copiedFrom: source.copiedFrom,
		dueDate: source.dueDate,
		note: source.note,
	};
}

function resolve(payload: Payload): Forward | null {
	const op = payload.op;

	switch (op) {
		case "task-override":
			return {
				path: `/tasks/${enc(payload.taskKey)}/override`,
				method: "PATCH",
				body: payload.facets,
			};
		case "task-add":
			return {
				path: "/tasks",
				method: "POST",
				body: projectTaskAdd(payload.task),
			};
		case "task-remove":
			return { path: `/tasks/${enc(payload.taskKey)}`, method: "DELETE" };
		case "task-order-bulk":
			return {
				path: "/tasks/order",
				method: "PATCH",
				body: { orders: payload.orders },
			};
		case "event-join":
			return {
				path: `/events/${enc(payload.eventId)}/join`,
				method: payload.on ? "PUT" : "DELETE",
			};
		case "event-ignore":
			return {
				path: `/events/${enc(payload.eventId)}/ignore`,
				method: payload.on ? "PUT" : "DELETE",
			};
		case "calendar-prefs":
			return { path: "/calendar-prefs", method: "PUT", body: payload.prefs };
		case "task-note":
			return {
				path: `/tasks/${enc(payload.taskKey)}/note`,
				method: "PUT",
				body: { note: payload.note },
			};
		case "item-label":
			return {
				path: `/calendar-items/${enc(payload.itemKey)}/label`,
				method: "PUT",
				body: { label: payload.label },
			};
		case "item-urgent":
			return {
				path: `/calendar-items/${enc(payload.itemKey)}/urgent`,
				method: payload.on ? "PUT" : "DELETE",
			};
		case "custom-event-put":
			return {
				path: `/custom-events/${enc(payload.key)}`,
				method: "PUT",
				body: projectCustomEvent(payload.event),
			};
		case "custom-event-delete":
			return { path: `/custom-events/${enc(payload.key)}`, method: "DELETE" };
		case "quick-put":
			return {
				path: `/quick-items/${enc(payload.key)}`,
				method: "PUT",
				body: projectQuickItem(payload.item),
			};
		case "quick-delete":
			return { path: `/quick-items/${enc(payload.key)}`, method: "DELETE" };
		default:
			return null;
	}
}

export const POST: RequestHandler = async ({ request }) => {
	if (!apiEnabled()) {
		return json({ error: { code: "api_disabled", message: "API mode is off." } }, { status: 404 });
	}

	const payload = (await request.json()) as Payload;
	const forward = resolve(payload);
	if (!forward) {
		return json({ error: { code: "unknown_op", message: `Unknown op: ${String(payload.op)}` } }, { status: 400 });
	}

	try {
		await apiFetch(forward.path, { method: forward.method, body: forward.body });
	} catch (error) {
		if (error instanceof ApiError) {
			return json({ error: { code: error.code, message: error.message } }, { status: error.status });
		}
		throw error;
	}

	return json({ ok: true });
};
