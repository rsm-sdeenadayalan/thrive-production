import { describe, expect, it } from "vitest";

import { rowPriorityOf, taskLabels } from "./taskView";
import { describeDue } from "./format";
import { standingTone, tagTones, urgencyTone, progressTones, statTones } from "./tones";
import type { Task } from "./data";

const NOW = new Date(2026, 8, 15, 9, 0, 0);

/** A descriptor at `days` from NOW. */
function dueIn(days: number) {
	const date = new Date(NOW);
	date.setDate(date.getDate() + days);
	date.setHours(17, 0, 0, 0);
	return describeDue(date.toISOString(), NOW);
}

const base: Pick<Task, "source" | "courseCode" | "priority"> = {
	source: "class",
	courseCode: "MGT 253",
	priority: "medium"
};

describe("rowPriorityOf", () => {
	it("lets the deadline outrank the stated priority", () => {
		// A low-priority task that is already overdue is the most urgent thing on
		// the screen. Tinting it by its stated priority would bury it.
		expect(rowPriorityOf(dueIn(-1), "low", false)).toBe("urgent");
	});

	it("treats due-today and high priority as the same strength", () => {
		expect(rowPriorityOf(dueIn(0), "low", false)).toBe("soon");
		expect(rowPriorityOf(dueIn(5), "high", false)).toBe("soon");
	});

	it("tints a medium-priority upcoming task, and leaves a low one alone", () => {
		expect(rowPriorityOf(dueIn(5), "medium", false)).toBe("later");
		expect(rowPriorityOf(dueIn(5), "low", false)).toBe("none");
	});

	it("strips the tint from anything done, however urgent it was", () => {
		// A finished task has stopped competing for attention.
		expect(rowPriorityOf(dueIn(-10), "high", true)).toBe("none");
	});

	it("gives an unparseable date no tint rather than inventing one", () => {
		const unknown = describeDue("nope", NOW);
		expect(unknown.urgency).toBe("unknown");
		expect(rowPriorityOf(unknown, "low", false)).toBe("none");
	});
});

describe("taskLabels", () => {
	it("caps at two labels: one state, one origin", () => {
		// A row wearing four tags is a row shouting.
		const labels = taskLabels(base, dueIn(-1), false);
		expect(labels).toHaveLength(2);
		expect(labels[0].text).toBe("Urgent");
		expect(labels[1].text).toBe("MGT 253");
	});

	it("prefers the course code over the generic source word", () => {
		// "MGT 253" places the work; "Class" does not.
		expect(taskLabels(base, dueIn(5), false)[0].text).toBe("MGT 253");
		expect(
			taskLabels({ ...base, courseCode: undefined }, dueIn(5), false)[0].text
		).toBe("Class");
	});

	it("names the source for non-class work", () => {
		expect(taskLabels({ ...base, source: "career", courseCode: undefined }, dueIn(5), false)[0].text)
			.toBe("Career");
		expect(taskLabels({ ...base, source: "admin", courseCode: undefined }, dueIn(5), false)[0].text)
			.toBe("Admin");
	});

	it("replaces the state label with Done rather than joining it", () => {
		// A finished task has no urgency left to report.
		const labels = taskLabels(base, dueIn(-5), true);
		expect(labels.map((l) => l.text)).toEqual(["Done", "MGT 253"]);
	});

	it("emits no state label for an upcoming, unremarkable task", () => {
		const labels = taskLabels({ ...base, priority: "low" }, dueIn(5), false);
		expect(labels.map((l) => l.text)).toEqual(["MGT 253"]);
	});

	it("emits no state label for an unparseable date", () => {
		// Same reason as rowPriorityOf: inventing an urgency for a date that does
		// not exist is how a broken deadline ends up looking fine.
		const labels = taskLabels(base, describeDue("nope", NOW), false);
		expect(labels.map((l) => l.text)).toEqual(["MGT 253"]);
	});
});

describe("the tone maps", () => {
	it("covers every tag tone", () => {
		// Exhaustive by type, but a missing ENTRY is only a compile error if the
		// key is required -- this asserts the values are really there.
		for (const tone of Object.keys(tagTones)) {
			expect(tagTones[tone as keyof typeof tagTones]).toBeTruthy();
		}
		expect(Object.keys(tagTones)).toHaveLength(9);
	});

	it("maps every standing, and none of them to a green", () => {
		expect(Object.keys(standingTone)).toEqual(["onTrack", "watch", "needsHelp"]);
		// on-track moved off blue when primary became navy. If it ever lands back
		// on the primary tone, a status chip and a primary button read alike.
		expect(Object.values(standingTone)).not.toContain("primary");
	});

	it("leaves upcoming unfilled and unknown neutral", () => {
		// Most tasks are upcoming; a filled chip on every row makes the two that
		// matter invisible.
		expect(urgencyTone.upcoming).toBe("quiet");
		expect(tagTones.quiet).not.toContain("bg-");
		// "How urgent is it" has no answer for a date that does not exist.
		expect(urgencyTone.unknown).toBe("neutral");
	});

	it("keeps every tone map free of hardcoded colour", () => {
		// The design system rule, checked where the colours actually live.
		const all = [
			...Object.values(tagTones),
			...Object.values(progressTones),
			...Object.values(statTones).flatMap((s) => [s.wrap, s.icon])
		].join(" ");
		expect(all).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
		expect(all).not.toMatch(/rgb|hsl|oklab/);
	});
});
