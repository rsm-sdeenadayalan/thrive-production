import { describe, expect, it } from "vitest";

import { abbreviateTerm, phaseStatusWord } from "./programStrip";

describe("abbreviateTerm", () => {
	it("shortens the four seasons to a known short form", () => {
		expect(abbreviateTerm("Summer 2026")).toBe("Sum 26");
		expect(abbreviateTerm("Winter 2027")).toBe("Win 27");
		expect(abbreviateTerm("Spring 2027")).toBe("Spr 27");
	});

	it("leaves Fall alone, because it already fits", () => {
		expect(abbreviateTerm("Fall 2027")).toBe("Fall 27");
	});

	it("passes an unexpected shape through unchanged rather than mangling it", () => {
		/*
		 * Not a defensive hypothetical: `buildProgramTimeline` falls back to
		 * `toLocaleDateString` for a phase with no season, which produces
		 * "August 2026" -- a shape this regex does not match. Truncating that to
		 * "Aug…" would name nothing, so it is passed through whole.
		 */
		expect(abbreviateTerm("August 2026")).toBe("August 2026");
		expect(abbreviateTerm("Autumn 2026")).toBe("Autumn 2026");
		expect(abbreviateTerm("Summer 26")).toBe("Summer 26");
		expect(abbreviateTerm("")).toBe("");
	});

	it("takes the last two digits of the year, not the first two", () => {
		expect(abbreviateTerm("Summer 2100")).toBe("Sum 00");
	});
});

describe("phaseStatusWord", () => {
	it("gives every phase status a spoken form", () => {
		// The pips carry status in fill and stroke. Neither reaches a screen reader,
		// so each pip also renders this word in an sr-only span.
		expect(phaseStatusWord.complete).toBe("completed");
		expect(phaseStatusWord.current).toBe("in progress");
		expect(phaseStatusWord.upcoming).toBe("not started");
		expect(Object.keys(phaseStatusWord)).toHaveLength(3);
	});
});
