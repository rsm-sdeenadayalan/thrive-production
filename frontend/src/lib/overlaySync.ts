/**
 * overlaySync — the client-side half of the localStorage-to-Django bridge.
 *
 * Plain `.ts`, no runes: this module holds no reactive state of its own. It
 * only remembers the primed seed (a snapshot handed to it once at hydration)
 * and a couple of pending-write buffers for the two ops that coalesce.
 *
 * Every store's `set()` calls `syncOverlay(storageKey, id, value)` right after
 * it commits its own write. This dispatcher decides, from `storageKey` alone,
 * whether that write means anything to the server; if it does, it fires a
 * fire-and-forget POST to the same-origin `/overlay-sync` proxy. A write that
 * fails is not retried and not surfaced — same contract a localStorage quota
 * throw already had: the optimistic local value stands, and the next full
 * reload re-seeds from whatever the server actually has.
 */

export interface OverlaySeed {
	stores: Record<string, Record<string, unknown>>;
}

let seed: OverlaySeed | null = null;

export function primeOverlay(data: OverlaySeed | null): void {
	seed = data;
	// A fresh prime starts clean: any writes queued against a previous student
	// (or against no student, pre-login) never belong to whatever comes next.
	pendingOrders = null;
	if (prefsTimer !== null) {
		clearTimeout(prefsTimer);
		prefsTimer = null;
	}
	pendingPrefs = null;
}

export function overlayEnabled(): boolean {
	return seed !== null;
}

export function seedFor(key: string): Record<string, unknown> | null {
	return seed?.stores[key] ?? null;
}

function send(op: string, payload: Record<string, unknown>): void {
	try {
		fetch("/overlay-sync", {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ op, ...payload }),
		})
			.then((response) => {
				if (!response.ok) {
					console.warn(`overlaySync: ${op} failed with status ${response.status}`);
				}
			})
			.catch((error) => {
				console.warn(`overlaySync: ${op} failed`, error);
			});
	} catch (error) {
		// A synchronous throw from `fetch` itself (unlikely, but the contract is
		// "nothing escapes") is warned about exactly like an async rejection.
		console.warn(`overlaySync: ${op} failed`, error);
	}
}

// thrive:task-order coalescing: every set() in the same tick adds to one
// pending map, and the FIRST call in a tick schedules the flush.
let pendingOrders: Record<string, number | null> | null = null;

function queueOrder(id: string, value: unknown): void {
	if (pendingOrders === null) {
		pendingOrders = {};
		queueMicrotask(flushOrders);
	}
	pendingOrders[id] = value === undefined || value === null ? null : (value as number);
}

function flushOrders(): void {
	const orders = pendingOrders;
	pendingOrders = null;
	if (orders === null) return;
	send("task-order-bulk", { orders });
}

// thrive:calendar-prefs debouncing: 400ms trailing, latest value wins.
let prefsTimer: ReturnType<typeof setTimeout> | null = null;
let pendingPrefs: unknown = null;

function queuePrefs(value: unknown): void {
	pendingPrefs = value;
	if (prefsTimer !== null) clearTimeout(prefsTimer);
	prefsTimer = setTimeout(() => {
		prefsTimer = null;
		const prefs = pendingPrefs;
		pendingPrefs = null;
		send("calendar-prefs", { prefs });
	}, 400);
}

function orNull(value: unknown): unknown {
	return value === undefined || value === null ? null : value;
}

type Handler = (id: string, value: unknown) => void;

const handlers: Record<string, Handler> = {
	"thrive:task-done": (id, value) => {
		send("task-override", { taskKey: id, facets: { done: orNull(value) } });
	},
	"thrive:task-titles": (id, value) => {
		send("task-override", { taskKey: id, facets: { title: orNull(value) } });
	},
	"thrive:task-priority": (id, value) => {
		send("task-override", { taskKey: id, facets: { priority: orNull(value) } });
	},
	"thrive:task-due": (id, value) => {
		send("task-override", { taskKey: id, facets: { dueDate: orNull(value) } });
	},
	"thrive:task-order": (id, value) => {
		queueOrder(id, value);
	},
	"thrive:task-added": (id, value) => {
		if (value === undefined || value === null) {
			send("task-remove", { taskKey: id });
			return;
		}
		const task = value as Record<string, unknown>;
		send("task-add", { task: { ...task, clientKey: id } });
	},
	"thrive:event-joins": (id, value) => {
		send("event-join", { eventId: id, on: value === true });
	},
	"thrive:ignored-events": (id, value) => {
		send("event-ignore", { eventId: id, on: value === true });
	},
	"thrive:item-labels": (id, value) => {
		send("item-label", { itemKey: id, label: value === undefined || value === null ? "" : value });
	},
	"thrive:item-urgent": (id, value) => {
		send("item-urgent", { itemKey: id, on: value === true });
	},
	"thrive:custom-events": (id, value) => {
		if (value === undefined || value === null) {
			send("custom-event-delete", { key: id });
			return;
		}
		send("custom-event-put", { key: id, event: value });
	},
	"thrive:quicklist": (id, value) => {
		if (value === undefined || value === null) {
			send("quick-delete", { key: id });
			return;
		}
		send("quick-put", { key: id, item: value });
	},
	"thrive:task-notes": (id, value) => {
		send("task-note", { taskKey: id, note: value === undefined || value === null ? "" : value });
	},
	"thrive:calendar-prefs": (_id, value) => {
		queuePrefs(value);
	},
};

export function syncOverlay(storageKey: string, id: string, value: unknown): void {
	if (!overlayEnabled()) return;
	const handler = handlers[storageKey];
	if (!handler) return;
	try {
		handler(id, value);
	} catch (error) {
		// Belt and suspenders: nothing thrown by a handler (or by `send`, which
		// already swallows its own errors) is allowed to escape into a store's
		// set() call.
		console.warn(`overlaySync: ${storageKey} failed`, error);
	}
}
