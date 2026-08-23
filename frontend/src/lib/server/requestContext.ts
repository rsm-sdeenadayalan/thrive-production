import { AsyncLocalStorage } from "node:async_hooks";

import type { Student } from "$lib/data/types";

export interface RequestAuth {
	cookie: string;
	student: Student | null;
}

const storage = new AsyncLocalStorage<RequestAuth>();

export function runWithAuth<T>(auth: RequestAuth, fn: () => T | Promise<T>) {
	return storage.run(auth, fn);
}

export function currentAuth(): RequestAuth | null {
	return storage.getStore() ?? null;
}
