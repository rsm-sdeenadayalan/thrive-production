import { defineConfig } from 'vitest/config';
import tailwindcss from '@tailwindcss/vite';
import netlifyAdapter from '@sveltejs/adapter-netlify';
import nodeAdapter from '@sveltejs/adapter-node';
import { sveltekit } from '@sveltejs/kit/vite';

/**
 * TWO ADAPTERS, ONE PICKED BY AN ENVIRONMENT VARIABLE.
 *
 * `adapter-netlify` is the default, because that is what a push to `main`
 * deploys. `ADAPTER=node` selects `adapter-node`, and the two browser gates set
 * it — they spawn a real server and drive it with Playwright, which needs a
 * long-running Node process rather than a bundle of serverless functions.
 *
 * ## Why both rather than a swap
 *
 * Deleting `adapter-node` would have cost the two gates that have caught the most
 * real defects in this project — the dead stat pill, the `derived_inert` warning,
 * the dialog's TypeError, and Phase 8's 403. Replacing them with `netlify dev`
 * would mean the gates depended on the Netlify CLI and on a serverless emulator,
 * which is a lot of moving parts between a gate and the thing it measures.
 *
 * It is not a hedge. Both adapters take the SAME SvelteKit build and neither
 * changes the app: there is no `prerender`, no `ssr = false` and no `csr = false`
 * anywhere in `src/routes`, so every route is server-rendered per request under
 * both. See the note in `netlify.toml`.
 *
 * ## The out directories are separate on purpose
 *
 * `adapter-node` writes to `build-node/`, not `build/`. Netlify's publish
 * directory is `build/`, and two adapters writing the same folder means whichever
 * ran last decides what a gate is testing — a build-order bug that would look
 * like a flaky gate.
 */
/*
 * Read through `globalThis` rather than touching `process` directly, and NOT by
 * adding `@types/node`.
 *
 * This project has no Node types on purpose -- DEPENDENCIES.md records rejecting
 * them in Phase 5, because `import.meta.glob(..., { query: '?raw' })` did the job
 * that would have justified them. The rule is "do not add a dependency where the
 * platform already answers", and one narrowed property read is not an answer
 * worth a dependency.
 *
 * A bare `process.env.ADAPTER` fails `svelte-check` with "Cannot find name
 * 'process'", which is correct: this file is type-checked inside a project that
 * has no Node globals declared. Narrowing `globalThis` states the assumption --
 * there may or may not be a Node process here -- and type-checks without one.
 */
const useNode =
	(globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env
		?.ADAPTER === 'node';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) => filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: useNode ? nodeAdapter({ out: 'build-node' }) : netlifyAdapter()
		})
	],
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
