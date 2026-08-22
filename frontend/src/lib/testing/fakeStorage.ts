/**
 * A `localStorage` stand-in for tests. TEST-ONLY -- nothing in the app imports
 * this.
 *
 * The store layer decides "am I in a browser" by asking whether `localStorage`
 * exists, so a fake one is all it takes to exercise the whole thing in the Node
 * environment the rest of the suite already runs in. No jsdom, which keeps this
 * consistent with how every other spec in the repo works.
 */

export interface FakeStorage extends Storage {
	/** Everything currently held, for asserting on what was persisted. */
	dump(): Record<string, string>;
	/** Make every write throw, to stand in for a quota error or private mode. */
	failWrites(): void;
}

export function fakeStorage(seed: Record<string, string> = {}): FakeStorage {
	const data = new Map(Object.entries(seed));
	let writesFail = false;

	return {
		get length() {
			return data.size;
		},
		key(index: number) {
			return [...data.keys()][index] ?? null;
		},
		getItem(key: string) {
			return data.has(key) ? data.get(key)! : null;
		},
		setItem(key: string, value: string) {
			if (writesFail) throw new DOMException("QuotaExceededError");
			data.set(key, value);
		},
		removeItem(key: string) {
			data.delete(key);
		},
		clear() {
			data.clear();
		},
		dump() {
			return Object.fromEntries(data);
		},
		failWrites() {
			writesFail = true;
		},
	};
}

/**
 * Install a fake storage as the global `localStorage`.
 *
 * `defineProperty` rather than assignment because the DOM lib types
 * `globalThis.localStorage` as read-only.
 */
export function installStorage(seed: Record<string, string> = {}): FakeStorage {
	const store = fakeStorage(seed);
	Object.defineProperty(globalThis, "localStorage", {
		value: store,
		configurable: true,
		writable: true,
	});
	return store;
}

/** Remove it again, which is what "we are on the server" looks like. */
export function uninstallStorage(): void {
	Reflect.deleteProperty(globalThis as object, "localStorage");
}
