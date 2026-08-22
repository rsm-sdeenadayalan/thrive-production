import { describe, expect, it } from "vitest";

import { collapseList, isCollapsedByDefault } from "./collapse";

/**
 * The collapse rule.
 *
 * Boundaries rather than middles, which is this suite's house style: the
 * interesting cases are exactly-at-the-limit and one-over, because those are
 * where "show 0 more" and a control that collapses nothing come from.
 */

const rows = (n: number) => Array.from({ length: n }, (_, i) => `row-${i}`);

describe("collapseList", () => {
	it("shows everything and offers nothing when the list fits", () => {
		const state = collapseList(rows(3), 4, false);

		expect(state.visible).toHaveLength(3);
		expect(state.hiddenCount).toBe(0);
		// The important half: no control on a card with nothing to reveal.
		expect(state.canExpand).toBe(false);
		expect(state.isExpanded).toBe(false);
	});

	it("shows everything and offers nothing at exactly the limit", () => {
		// The boundary. `rows.length > limit` rather than `>=` is what stops a
		// four-row card with a four-row limit growing a "show 0 more".
		const state = collapseList(rows(4), 4, false);

		expect(state.visible).toHaveLength(4);
		expect(state.hiddenCount).toBe(0);
		expect(state.canExpand).toBe(false);
	});

	it("holds back the overflow one row over the limit", () => {
		const state = collapseList(rows(5), 4, false);

		expect(state.visible).toHaveLength(4);
		expect(state.visible.at(-1)).toBe("row-3");
		expect(state.hiddenCount).toBe(1);
		expect(state.canExpand).toBe(true);
	});

	it("counts the real remainder, not a page size", () => {
		// "show 10 more" is the number that tells a student whether to click.
		expect(collapseList(rows(14), 4, false).hiddenCount).toBe(10);
	});

	it("shows everything when expanded, and still offers to collapse", () => {
		const state = collapseList(rows(14), 4, true);

		expect(state.visible).toHaveLength(14);
		expect(state.hiddenCount).toBe(0);
		expect(state.canExpand).toBe(true);
		expect(state.isExpanded).toBe(true);
	});

	it("does not report itself expanded when there was nothing to expand", () => {
		/*
		 * A card whose content fits, whose state got flipped anyway. `isExpanded`
		 * drives the control's label and `aria-expanded`, so reporting true here
		 * would render "show less" on a card that never hid anything.
		 */
		const state = collapseList(rows(2), 4, true);

		expect(state.canExpand).toBe(false);
		expect(state.isExpanded).toBe(false);
	});

	it("treats a zero limit as show-none, which is what the done group wants", () => {
		const state = collapseList(rows(3), 0, false);

		expect(state.visible).toEqual([]);
		expect(state.hiddenCount).toBe(3);
		expect(state.canExpand).toBe(true);
	});

	it("expands a zero-limit list normally", () => {
		const state = collapseList(rows(3), 0, true);

		expect(state.visible).toHaveLength(3);
		expect(state.isExpanded).toBe(true);
	});

	it("offers nothing for an empty list, at any limit", () => {
		// Guards the done group: no done tasks must not render "show 0 more".
		for (const limit of [0, 1, 4]) {
			const state = collapseList([], limit, false);
			expect(state.visible).toEqual([]);
			expect(state.hiddenCount).toBe(0);
			expect(state.canExpand).toBe(false);
		}
	});

	it("clamps a negative or fractional limit rather than slicing strangely", () => {
		// `slice(0, -2)` drops from the END, which would silently hide the wrong
		// rows. A fractional limit comes from arithmetic on a token.
		expect(collapseList(rows(5), -2, false).visible).toEqual([]);
		expect(collapseList(rows(5), -2, false).hiddenCount).toBe(5);
		expect(collapseList(rows(5), 2.7, false).visible).toHaveLength(2);
	});

	it("never hands back the caller's array", () => {
		// The card renders `visible` in an `{#each}`; a shared reference would let
		// a sort in one card reorder another's source data.
		const source = rows(3);
		const state = collapseList(source, 4, false);

		expect(state.visible).not.toBe(source);
		state.visible.push("mutated");
		expect(source).toHaveLength(3);
	});

	it("preserves order, so the collapse takes from the end", () => {
		const state = collapseList(rows(6), 3, false);
		expect(state.visible).toEqual(["row-0", "row-1", "row-2"]);
	});
});

describe("isCollapsedByDefault", () => {
	it("hides done behind its count and leaves open groups open", () => {
		// Done is the record of what is finished, not the list of what to do.
		expect(isCollapsedByDefault("done")).toBe(true);
		expect(isCollapsedByDefault("open")).toBe(false);
	});
});
