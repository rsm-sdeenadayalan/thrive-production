import { describe, expect, it } from "vitest";

import {
	allNav,
	flattenNav,
	isActiveRoute,
	isBuiltRoute,
	isKnownRoute,
	parkedNav,
	primaryNav
} from "./nav";

/**
 * The nav lists, and the two questions a card asks them.
 *
 * `isBuiltRoute` is what decides whether a Home card renders its "View all", so
 * the thing worth pinning is not the four hrefs that happen to be primary today
 * — it is the RELATIONSHIP: primary means linkable, parked means not, and moving
 * an entry between the lists is the whole operation.
 */

describe("the nav lists", () => {
	it("keeps the two lists disjoint", () => {
		// A route in both would make `isBuiltRoute` and `isKnownRoute` disagree about
		// which list won, and the answer would depend on array order.
		const parked = new Set(parkedNav.map((item) => item.href));
		expect(primaryNav.filter((item) => parked.has(item.href))).toEqual([]);
	});

	it("has no duplicate hrefs anywhere", () => {
		const hrefs = allNav.map((item) => item.href);
		expect(hrefs.length).toBe(new Set(hrefs).size);
	});

	it("is the FLATTENED union, in primary-then-parked order", () => {
		/*
		 * Flattened since Ask THRIVE grew children. This is the assertion that keeps
		 * the tree a single source: `allNav` is DERIVED from the two lists rather
		 * than maintained beside them, so a child cannot exist in the rail and be
		 * missing from the lookup `PagePlaceholder` throws on.
		 */
		expect(allNav).toEqual(flattenNav([...primaryNav, ...parkedNav]));
	});

	it("carries more entries than there are top-level items", () => {
		// Non-vacuous: with no children anywhere, the flatten assertion above would
		// pass against a function that did nothing.
		expect(allNav.length).toBeGreaterThan(primaryNav.length + parkedNav.length);
	});
});

describe("flattenNav", () => {
	it("puts a parent before its children", () => {
		const hrefs = flattenNav(primaryNav).map((item) => item.href);
		const parent = hrefs.indexOf("/ask");
		const child = hrefs.indexOf("/ask/resources");

		expect(parent).toBeGreaterThanOrEqual(0);
		expect(child).toBeGreaterThan(parent);
	});

	it("finds every child of every item", () => {
		const flat = flattenNav(primaryNav);

		for (const item of primaryNav) {
			for (const child of item.children ?? []) {
				expect(flat, `${child.href} is missing from the flattened list`).toContain(child);
			}
		}
	});

	it("is the identity on a list with no children", () => {
		expect(flattenNav(parkedNav)).toEqual(parkedNav);
	});

	it("returns an empty list for an empty one", () => {
		expect(flattenNav([])).toEqual([]);
	});
});

describe("a nav item's children", () => {
	const ask = primaryNav.find((item) => item.href === "/ask");

	it("hang off Ask THRIVE", () => {
		expect(ask?.children).toHaveLength(3);
	});

	it("are real routes nested under their parent's href", () => {
		/*
		 * The property that makes the rail's disclosure honest: a child is a route,
		 * not a filter. If one ever stopped living under `/ask`, `isActiveRoute`
		 * would stop lighting the parent when the child was current and the group
		 * would stop opening itself.
		 */
		for (const child of ask?.children ?? []) {
			expect(child.href.startsWith("/ask/")).toBe(true);
			expect(isActiveRoute("/ask", child.href)).toBe(true);
		}
	});

	it("carry the same fields as any other item, so nothing special-cases them", () => {
		for (const child of ask?.children ?? []) {
			expect(typeof child.label).toBe("string");
			expect(child.label.length).toBeGreaterThan(0);
			expect(typeof child.description).toBe("string");
			expect(child.description.length).toBeGreaterThan(0);
			expect(child.icon).toBeTruthy();
		}
	});
});

describe("isBuiltRoute", () => {
	it("accepts every primary route, children included", () => {
		// Non-vacuous: if `primaryNav` were empty the loop below would assert nothing.
		expect(primaryNav.length).toBeGreaterThan(0);
		for (const item of flattenNav(primaryNav)) {
			expect(isBuiltRoute(item.href), `${item.href} should be built`).toBe(true);
		}
	});

	it("accepts a child destination", () => {
		// `/ask/career` is as real a page as `/calendar`. A card linking to one must
		// not have its link withheld because the route happens to be nested.
		expect(isBuiltRoute("/ask/career")).toBe(true);
	});

	it("rejects every parked route", () => {
		expect(parkedNav.length).toBeGreaterThan(0);
		for (const item of parkedNav) {
			expect(isBuiltRoute(item.href)).toBe(false);
		}
	});

	it("rejects an href in neither list", () => {
		expect(isBuiltRoute("/nope")).toBe(false);
		expect(isBuiltRoute("")).toBe(false);
	});

	it("is exact, never a prefix match", () => {
		/*
		 * The distinction from `isActiveRoute`, which DOES match prefixes so a nested
		 * route keeps its section lit. A prefix match here would call `/calendar/2026`
		 * built, and a card linking there would send someone to a 404 rather than to a
		 * placeholder — a worse failure than the one this function prevents.
		 */
		expect(isBuiltRoute("/calendar/2026")).toBe(false);
		expect(isActiveRoute("/calendar", "/calendar/2026")).toBe(true);
	});

	it("does not treat Home as a prefix of everything", () => {
		// `/` is primary, and a naive `startsWith` would make every route built.
		expect(isBuiltRoute("/")).toBe(true);
		expect(isBuiltRoute("/classes")).toBe(false);
	});
});

describe("isKnownRoute", () => {
	it("accepts primary and parked alike", () => {
		for (const item of allNav) {
			expect(isKnownRoute(item.href)).toBe(true);
		}
	});

	it("separates 'parked on purpose' from 'does not exist'", () => {
		/*
		 * The pair that matters. Both answer false to `isBuiltRoute`, for completely
		 * different reasons, and `SectionCard` warns on only the second — hiding a
		 * link because of a typo is a silent no-op, hiding one because the page is
		 * parked is the feature.
		 */
		expect(isBuiltRoute("/classes")).toBe(false);
		expect(isKnownRoute("/classes")).toBe(true);

		expect(isBuiltRoute("/clases")).toBe(false);
		expect(isKnownRoute("/clases")).toBe(false);
	});
});

describe("what Home's cards link to", () => {
	/*
	 * Not a rendering test — Vitest renders nothing here. This pins the DATA behind
	 * the decision: these are the four destinations Home's cards name, and the
	 * split between them is what a student sees as three cards without a link.
	 *
	 * It is deliberately written to survive a route being built: when `/assignments`
	 * moves into `primaryNav`, this test still passes and the link returns. What it
	 * would catch is a card pointed at an href that is in no list at all.
	 */
	const cardDestinations = ["/assignments", "/calendar", "/classes", "/events"];

	it("names only routes the nav knows about", () => {
		for (const href of cardDestinations) {
			expect(isKnownRoute(href)).toBe(true);
		}
	});

	it("has at least one linkable and at least one parked, so both branches render", () => {
		// A companion assertion: if every destination were parked, "the link is
		// hidden" would be trivially true and prove nothing about the condition.
		expect(cardDestinations.some(isBuiltRoute)).toBe(true);
		expect(cardDestinations.some((href) => !isBuiltRoute(href))).toBe(true);
	});
});
