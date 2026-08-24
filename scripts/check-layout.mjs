#!/usr/bin/env node
/**
 * Layout gate: the document must not scroll further than it renders.
 *
 *     npm run check:layout          (from frontend/)
 *     node scripts/check-layout.mjs
 *
 * Exits non-zero if any route on any breakpoint can be scrolled past its own
 * content. No arguments, no config.
 *
 * ## Why this exists
 *
 * On 2026-08-21 Home could not fit any viewport shorter than 1275px, and 37px of
 * that was scrollable EMPTY SPACE. Every element rendered at or above 1238px.
 * `body.scrollHeight` agreed at 1238. And `window.scrollTo(0, 1e6)` still moved
 * 37px, because a card with a fixed height and overflowing content was leaking
 * its scrollable overflow out to the document.
 *
 * Nothing caught it. It was found by hand, while chasing a different 8px, and
 * the only reason it was found at all is that a predicted saving did not show up
 * in a measurement. That is not a process.
 *
 * A document that scrolls past its own content is always a bug. It is dead space
 * at the bottom of the page, it makes "does this fit on one screen" unanswerable,
 * and it is invisible in a screenshot. So it gets a gate.
 *
 * ## Why it is not a Vitest test
 *
 * It needs a real layout engine. Vitest runs in Node with no jsdom in this repo
 * (a standing decision -- see TESTING.md), and jsdom would not help anyway: it
 * does not do layout, so every height it reports is zero. Same shape as
 * `check-contrast.py`: a separate gate, run deliberately, that measures the
 * thing rather than a model of it.
 *
 * ## Why it skips instead of failing when there is no browser
 *
 * `playwright-core` ships no browser. On a machine or CI runner without one this
 * would fail for a reason that has nothing to do with the code, and a gate that
 * cries wolf gets ignored. It says loudly that it skipped and exits 0. Install a
 * browser with `npx playwright install chromium` to turn it on.
 */

import { spawn } from 'node:child_process';
import { existsSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const FRONTEND = join(ROOT, 'frontend');
/*
 * The ADAPTER-NODE build, not the Netlify one.
 *
 * `frontend/build/` is Netlify's publish directory and holds static assets plus a
 * bundle of serverless functions -- nothing this can spawn. `adapter-node` writes
 * `build-node/` instead, and `npm run check:layout` / `check:interaction` build it
 * first (`ADAPTER=node vite build`). Two adapters writing one folder would mean
 * whichever ran last decided what this gate measured.
 */
const ENTRY = join(FRONTEND, 'build-node', 'index.js');
const PORT = 4399;
const BASE = `http://127.0.0.1:${PORT}`;

/**
 * Every route, so a shell-level regression cannot hide on an unvisited page.
 *
 * ## The calendar counts three times
 *
 * Its view is a persisted PREFERENCE, not a URL. So `/calendar` on its own only
 * ever measured the month grid, and the two views added in Phase 7b were
 * invisible to this gate for the same reason they are invisible to every other
 * one: nothing navigates to them.
 *
 * That gap is exactly what a vertical-overflow gate is for. The agenda renders
 * thirty days of grouped rows and measured **13,764px on a phone** — the tallest
 * thing in the app by an order of magnitude, and the surface where a stray fixed
 * height or an un-contained scroller would be least visible. The week view has
 * the opposite risk: seven columns of clamped titles, where a leaked overflow
 * would be horizontal first and vertical second.
 *
 * `prefs` is written into `thrive:calendar-prefs` before the page is measured;
 * `null` means the key is removed, so a target cannot inherit the one before it.
 * Approved for 7c and deferred out of 7b because the surface it guards was still
 * moving.
 */
const TARGETS = [
	{ route: '/', label: '/' },
	{ route: '/calendar', label: '/calendar month', prefs: { view: 'month' } },
	{ route: '/calendar', label: '/calendar week', prefs: { view: 'week' } },
	{ route: '/calendar', label: '/calendar agenda', prefs: { view: 'agenda' } },
	{ route: '/appointments', label: '/appointments' },
	/*
	 * The booking area OPEN, which is the state with something to measure.
	 *
	 * Closed, `/appointments` is two cards and a list -- it measured 1079px on a
	 * phone and could not have overflowed. The risk is entirely in the expanded
	 * state: a month grid, a slot list, a textarea and the day pane, stacked in one
	 * column at 375px. MIGRATION.md section 9 defect 6 is an overflow on THIS
	 * route at THIS width, on the do-not-reproduce list.
	 *
	 * A preference could not reach it -- which advisor is open is component state,
	 * not a persisted key -- so this is the first target that has to press
	 * something. `click` is a selector waited for and clicked after the reload,
	 * before anything is measured.
	 */
	{
		route: '/appointments',
		label: '/appointments booking',
		click: '[data-service]:not([disabled])'
	},
	{ route: '/jobs', label: '/jobs' },
	/*
	 * A real query, so this measures the two-column results-plus-benchmark
	 * layout rather than the empty "search to see postings" state above.
	 */
	{ route: '/jobs?q=data', label: '/jobs results' },
	/*
	 * The Liked tab, so a regression in the feed's other slices cannot hide
	 * behind the default Recommended tab being the only one ever measured.
	 */
	{ route: '/jobs?tab=liked', label: '/jobs liked' },
	{ route: '/jobs/job-1', label: '/jobs detail' },
	{ route: '/ask', label: '/ask' },
	/*
	 * A saved conversation OPEN, which is the tall state.
	 *
	 * `/ask` on its own is an empty state and a rail. With a conversation open the
	 * page holds a log of message bubbles above a composer, and the whole point of
	 * the layout is that the LOG scrolls rather than the document -- which needs
	 * `min-h-0` on every flex parent down the spine, and silently degrades to the
	 * document growing if one of them is missing. That degradation is exactly what
	 * this gate measures.
	 *
	 * Reachable by URL rather than by a click, because the conversation is a search
	 * param -- which is the argument for it being one.
	 */
	{ route: '/ask/resources?c=conv-001', label: '/ask conversation' },
	/*
	 * The Course Recommender destination too, so a per-destination regression
	 * cannot hide. Its empty state carries the longest example questions of the
	 * two.
	 */
	{ route: '/ask/courses', label: '/ask courses' },
	{ route: '/classes', label: '/classes' },
	{ route: '/syllabi', label: '/syllabi' },
	{ route: '/assignments', label: '/assignments' },
	{ route: '/degree', label: '/degree' },
	{ route: '/events', label: '/events' },
	{ route: '/resources', label: '/resources' },
	{ route: '/settings', label: '/settings' }
];

/** The one key the calendar's view lives under. See `calendarPrefs.ts`. */
const PREFS_KEY = 'thrive:calendar-prefs';

/**
 * Both sides of the `lg` breakpoint, because that is where the card cap, the
 * bar height and the navigation all change at once -- and the bug this gate
 * exists for lived on the desktop side only.
 */
const VIEWPORTS = [
	{ w: 1512, h: 1052, label: 'desktop' },
	{ w: 1512, h: 1330, label: 'desktop tall' },
	{ w: 375, h: 812, label: 'phone' }
];

/** A pixel of slack for sub-pixel rounding. Two would hide a real 3px leak. */
const TOLERANCE = 1;

function skip(reason) {
	console.log('check-layout: SKIPPED');
	console.log(`  ${reason}`);
	console.log('  Install a browser with: npx playwright install chromium');
	process.exit(0);
}

/*
 * Resolved from `frontend/`, not from here. This file lives in the repo-root
 * `scripts/` beside `check-contrast.py`, which has no `node_modules` of its own
 * -- a bare `import 'playwright-core'` fails from here even though the package
 * is installed one directory down, and it fails in a way that looks exactly like
 * "not installed".
 */
let chromium;
try {
	const require = createRequire(join(FRONTEND, 'package.json'));
	const mod = await import(pathToFileURL(require.resolve('playwright-core')).href);
	// `playwright-core` is CommonJS. Importing it by file URL does not always
	// surface its named exports, so take the default namespace as well.
	chromium = mod.chromium ?? mod.default?.chromium;
	if (!chromium) throw new Error('no chromium export');
} catch (error) {
	skip(`Could not load playwright-core from frontend/: ${error.message.split('\n')[0]}`);
}

/**
 * The browser playwright would use, found by hand if it has to be.
 *
 * `chromium.launch()` looks for the exact revision THIS playwright-core expects.
 * A machine that installed browsers with a different playwright version has a
 * perfectly good chromium that the launcher will not find, and skipping in that
 * case would mean the gate never runs anywhere it is most needed. So: try the
 * normal launch, and fall back to any `chrome-headless-shell` in the cache.
 */
function findCachedShell() {
	const cache = join(
		process.env.HOME ?? '',
		'Library',
		'Caches',
		'ms-playwright'
	);
	if (!existsSync(cache)) return null;
	for (const entry of readdirSync(cache)) {
		if (!entry.startsWith('chromium')) continue;
		const candidates = [
			join(cache, entry, 'chrome-headless-shell-mac-arm64', 'chrome-headless-shell'),
			join(cache, entry, 'chrome-headless-shell-mac-x64', 'chrome-headless-shell')
		];
		for (const path of candidates) if (existsSync(path)) return path;
	}
	return null;
}

if (!existsSync(ENTRY)) {
	console.error('check-layout: FAILED');
	console.error(`  No build at ${ENTRY}. Run \`npm run build:node\` first.`);
	console.error('  (`npm run build` produces the Netlify output, which this cannot spawn.)');
	process.exit(1);
}

/*
 * `ORIGIN` is not optional once the app has a form action.
 *
 * `adapter-node` cannot know the public URL it is served on, so without this it
 * guesses -- and SvelteKit's CSRF check compares a POST's `Origin` header against
 * that guess. Every form submission comes back **403 "Cross-site POST form
 * submissions are forbidden"**, which is what happened the first time this gate
 * tried to book an appointment.
 *
 * Nothing before Phase 8 posted anything: Home and the calendar write to
 * `localStorage`, so the whole app was GET-only and the omission was invisible.
 * Setting it here is not a workaround for the gate -- it is the same variable a
 * real deployment has to set, so the gate now drives the app the way it must
 * actually be run. See setup_info.md.
 */
const server = spawn(process.execPath, [ENTRY], {
	cwd: FRONTEND,
	env: { ...process.env, PORT: String(PORT), ORIGIN: BASE },
	stdio: 'ignore'
});

async function waitForServer() {
	for (let i = 0; i < 60; i += 1) {
		try {
			const res = await fetch(BASE + '/');
			if (res.ok) return true;
		} catch {
			/* not up yet */
		}
		await new Promise((r) => setTimeout(r, 200));
	}
	return false;
}

let failures = 0;

try {
	if (!(await waitForServer())) {
		console.error('check-layout: FAILED\n  Server did not start.');
		process.exit(1);
	}

	let browser;
	try {
		browser = await chromium.launch();
	} catch {
		const executablePath = findCachedShell();
		if (!executablePath) {
			server.kill();
			skip('No chromium found, either at the expected revision or in the cache.');
		}
		browser = await chromium.launch({ executablePath });
	}

	console.log(`${'target'.padEnd(22)}${'viewport'.padEnd(14)}${'renders'.padStart(9)}${'scrolls to'.padStart(12)}   result`);
	console.log('-'.repeat(71));

	for (const vp of VIEWPORTS) {
		const page = await browser.newPage({ viewport: { width: vp.w, height: vp.h } });

		for (const target of TARGETS) {
			await page.goto(BASE + target.route, { waitUntil: 'networkidle' });

			/*
			 * Write the view preference, then reload so the store hydrates with it.
			 *
			 * Set on EVERY target rather than only the ones that want it, and removed
			 * when a target names none -- otherwise the calendar's view would leak
			 * forward into whatever is measured after it and a run's results would
			 * depend on the order of the array above.
			 *
			 * A reload rather than an in-page write: `hydrateStores()` runs once, in
			 * the root layout's effect, and there is deliberately no second path.
			 */
			await page.evaluate(
				({ key, value }) => {
					if (value === null) localStorage.removeItem(key);
					else localStorage.setItem(key, JSON.stringify({ value }));
				},
				{ key: PREFS_KEY, value: target.prefs ?? null }
			);
			await page.reload({ waitUntil: 'networkidle' });

			/*
			 * Open whatever this target needs open, then let the layout settle.
			 *
			 * The wait is on the SELECTOR rather than a timeout: the button only
			 * exists once the page has hydrated, and a fixed sleep would either be
			 * too short on a cold run or waste a second on every other target.
			 */
			if (target.click) {
				await page.waitForSelector(target.click, { state: 'visible' });
				await page.click(target.click);
				await page.waitForLoadState('networkidle');
			}

			const measured = await page.evaluate(() => {
				/*
				 * How far the page can actually be scrolled. Deliberately NOT
				 * `documentElement.scrollHeight` -- that is the property that reported
				 * 1275 while nothing rendered below 1238, so trusting it here would
				 * reproduce the blind spot this gate exists to close.
				 */
				const before = window.scrollY;
				window.scrollTo(0, 1e6);
				const maxScroll = Math.round(window.scrollY);
				window.scrollTo(0, before);

				/*
				 * The lowest point anything actually PAINTS, in document coordinates.
				 * Fixed elements are excluded because they do not scroll, and anything
				 * inside a scroll container is excluded because its overflow is clipped
				 * and is not the document's business.
				 */
				const inScroller = (el) => {
					for (let p = el.parentElement; p; p = p.parentElement) {
						const o = getComputedStyle(p).overflowY;
						if (o === 'auto' || o === 'scroll' || o === 'hidden') return true;
					}
					return false;
				};

				let lowest = 0;
				for (const el of document.querySelectorAll('body *')) {
					const cs = getComputedStyle(el);
					if (cs.position === 'fixed' || cs.display === 'none') continue;
					if (inScroller(el)) continue;
					const box = el.getBoundingClientRect();
					if (box.height === 0 && box.width === 0) continue;
					lowest = Math.max(lowest, box.bottom + window.scrollY);
				}

				return {
					rendersTo: Math.round(lowest),
					scrollsTo: maxScroll + window.innerHeight,
					viewport: window.innerHeight
				};
			});

			// A page shorter than the viewport scrolls to the viewport's bottom and
			// that is not overflow, so the floor is whichever is larger.
			const allowed = Math.max(measured.rendersTo, measured.viewport);
			const slack = measured.scrollsTo - allowed;
			const passed = slack <= TOLERANCE;
			if (!passed) failures += 1;

			console.log(
				`${target.label.padEnd(22)}${vp.label.padEnd(14)}` +
					`${String(measured.rendersTo).padStart(9)}${String(measured.scrollsTo).padStart(12)}   ` +
					`${passed ? 'PASS' : `FAIL  ${slack}px of empty scroll`}`
			);
		}

		await page.close();
	}

	await browser.close();
} finally {
	server.kill();
}

console.log('-'.repeat(71));
const total = TARGETS.length * VIEWPORTS.length;
console.log(`${total - failures}/${total} pass`);
if (failures > 0) {
	console.log('');
	console.log('A document that scrolls past its own content has dead space at the');
	console.log('bottom of it. Look for a fixed-height element whose content overflows:');
	console.log('`contain: paint` on the scroll container is what fixed the last one.');
}
process.exit(failures > 0 ? 1 : 0);
