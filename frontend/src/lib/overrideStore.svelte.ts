/**
 * The one mechanism THRIVE uses to persist a student's own edits.
 *
 * Every store built here holds *overrides* keyed by id, never the whole truth:
 * the providers stay authoritative and this layer records only what the student
 * has personally changed. That distinction is load-bearing. A bare "set of done
 * task ids" cannot express "I unticked a task that ships as done" -- reload and
 * it silently ticks itself again. `undefined` means "never touched, use the
 * source value"; an explicit value means "the student decided this".
 *
 * `localStorage` rather than anything server-side: a module-level store in a
 * node process is shared by every visitor at once, which is right for seeded
 * fixtures and wrong for one person's edits.
 *
 * When the Django backend lands, this module is the seam that changes.
 * Components never touch storage directly.
 *
 * ## The file extension is not decoration
 *
 * `.svelte.ts`, because Svelte 5 only processes runes in `.svelte.js` /
 * `.svelte.ts` modules. A plain `.ts` file containing `$state` silently does
 * nothing reactive. Import it as `$lib/overrideStore.svelte`.
 *
 * ## Hydration: empty on the server, real after mount
 *
 * `values` starts empty and STAYS empty until something calls `hydrate()`.
 * That is the whole server/client contract, and it replaces React's
 * `getServerSnapshot()`:
 *
 *   - On the server there is no `localStorage`, so hydration cannot happen and
 *     the un-personalised page is the only thing that can render.
 *   - On the client the first render also sees empty, matching the SSR markup,
 *     and the student's overrides land on the render after `hydrateStores()`
 *     runs from the root layout's mount.
 *
 * The gate is an explicit function call rather than a `browser` guard or a lazy
 * read, because a lazy read during the first client render would populate
 * mid-render and diverge from the server's markup -- the exact mismatch this
 * ordering exists to avoid. It being a single named call is also what lets one
 * surface later choose to wait for it without any change down here.
 *
 * In API mode the same contract is served by the server seed primed from the
 * root layout.
 */

import { overlayEnabled, seedFor, syncOverlay } from "./overlaySync";

/**
 * The browser's storage, or null when there is none.
 *
 * Wrapped because merely *touching* `localStorage` throws in some sandboxed
 * and cookie-blocked contexts rather than returning undefined. Also the reason
 * this module needs no `$app/environment` import: no storage IS the server.
 */
function storage(): Storage | null {
	try {
		return typeof localStorage === "undefined" ? null : localStorage;
	} catch {
		return null;
	}
}

/**
 * Every store's hydrate function, so one call can load them all.
 *
 * Registered at creation. Stores are module singletons created once at import,
 * so this set is stable for the life of the process.
 */
const registry = new Set<() => void>();

/**
 * Load every store from `localStorage`.
 *
 * Call this ONCE, from the root layout, after mount. Idempotent per store, and
 * a no-op anywhere there is no storage, so calling it on the server is safe but
 * pointless.
 *
 * Not wired to a layout yet -- there are no routes this phase. Until it is
 * called, a store hydrates lazily on its first `set`, so an edit can never
 * clobber stored data it has not read.
 */
export function hydrateStores(): void {
	for (const hydrate of registry) hydrate();
}

export interface OverrideStore<T> {
	/**
	 * Every override, as reactive state.
	 *
	 * Read it inside a component or a `$derived` and that reader re-runs when it
	 * changes. Empty until `hydrate()` has run.
	 */
	readonly values: Readonly<Record<string, T>>;
	/** Record an override. Passing `undefined` forgets it, back to source truth. */
	set: (id: string, value: T | undefined) => void;
	/** Read outside a reactive context, for event handlers. Never triggers a load. */
	read: () => Readonly<Record<string, T>>;
	/** Load from storage. Idempotent, and a no-op where there is no storage. */
	hydrate: () => void;
}

export function createOverrideStore<T>(key: string): OverrideStore<T> {
	type Values = Record<string, T>;

	let values = $state<Values>({});
	let hydrated = false;

	/**
	 * Parse stored JSON, defensively.
	 *
	 * A hand-edited or half-written value must not take the page down, and an
	 * array would happily pass `typeof === "object"`.
	 */
	function parse(raw: string | null): Values {
		if (!raw) return {};

		try {
			const parsed: unknown = JSON.parse(raw);
			return parsed && typeof parsed === "object" && !Array.isArray(parsed)
				? (parsed as Values)
				: {};
		} catch {
			return {};
		}
	}

	function hydrate(): void {
		if (hydrated) return;

		const seeded = seedFor(key);
		if (seeded) {
			hydrated = true;
			values = seeded as Values;
			return;
		}

		const store = storage();
		// No storage means the server. Leave `hydrated` false so a later call in
		// a real browser still works.
		if (!store) return;

		hydrated = true;
		values = parse(store.getItem(key));
	}

	registry.add(hydrate);

	function set(id: string, value: T | undefined): void {
		// Load before writing, or a pre-hydration edit would persist `{ [id]: v }`
		// over everything already stored under this key.
		hydrate();

		const next = { ...values };

		if (value === undefined) {
			delete next[id];
		} else {
			next[id] = value;
		}

		values = next;

		syncOverlay(key, id, value);
		if (overlayEnabled()) return;

		const store = storage();
		if (!store) return;

		try {
			store.setItem(key, JSON.stringify(next));
		} catch {
			// Out of quota, or blocked in private mode. The in-memory value still
			// holds the edit for this session rather than silently discarding it.
		}
	}

	return {
		get values() {
			return values;
		},
		set,
		/*
		 * Deliberately does NOT hydrate.
		 *
		 * This is the escape hatch for event handlers, but a component calling it
		 * during render would assign `$state` mid-render, which Svelte rejects.
		 * Handlers run after `hydrateStores()`, and `set` hydrates anyway, so
		 * there is nothing left for this to be responsible for.
		 */
		read: () => values,
		hydrate,
	};
}
