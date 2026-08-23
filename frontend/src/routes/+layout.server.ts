import { getStudent } from '$lib/data';
import { apiEnabled, apiFetch } from '$lib/data/api/client';
import type { LayoutServerLoad } from './$types';

/**
 * The student, loaded once for the whole app.
 *
 * In the Next app `AppShell` was an `async` server component that awaited
 * `getStudent()` mid-tree. This is where that goes: a root server load, so the
 * shell receives the record as data rather than fetching it while rendering.
 *
 * Server-side, and it stays server-side. Every provider will be a Django call
 * behind an authenticated session, and `+layout.server.ts` is the only place in
 * a SvelteKit app that can hold a credential without shipping it.
 *
 * `getStudent` is the real provider as of Phase 5. It was a hardcoded stub
 * through Phase 4 and this load function did not change when it was replaced --
 * only the import path did. That is the provider boundary working as intended,
 * and it is the same non-event the switch to Django should be.
 */
export const load: LayoutServerLoad = async () => {
	const student = await getStudent();
	if (!apiEnabled()) return { student };
	const overlay = await apiFetch<{ stores: Record<string, Record<string, unknown>> }>(
		'/overlay',
	);
	return { student, overlay: { stores: overlay.stores } };
};
