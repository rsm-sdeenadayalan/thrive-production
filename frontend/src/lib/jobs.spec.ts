import { describe, expect, it } from "vitest";

import {
  competencyLabel,
  jobsEmptyState,
  shareWidth,
  toJobPostingDetailView,
  toJobResultView,
} from "$lib/jobs";
import type {
  JobCompetency,
  JobPostingDetail,
  JobSearchEntry,
} from "$lib/data";

/**
 * Job search's pure logic: view models and the small vocabulary and
 * arithmetic on top of them. Same shape as `ask.spec.ts` -- clock-free,
 * source-free, and testing the ARITHMETIC rather than rendering anything.
 */

function entry(overrides: Partial<JobSearchEntry> = {}): JobSearchEntry {
  return {
    job: {
      id: "job-1",
      title: "Data Analyst",
      company: "Bloom Analytics",
      location: "San Diego, CA",
      url: "https://example.com/jobs/1",
      source: "LinkedIn",
      skills: ["SQL", "Excel"],
      postedAt: "2026-08-11T09:00:00-07:00",
      snippet: "Own weekly reporting.",
    },
    score: 82,
    matchedSkills: ["SQL"],
    missingSkills: ["Excel"],
    ...overrides,
  };
}

function detail(overrides: Partial<JobPostingDetail> = {}): JobPostingDetail {
  return {
    id: "job-1",
    title: "Data Analyst",
    company: "Bloom Analytics",
    location: "San Diego, CA",
    url: "https://example.com/jobs/1",
    source: "LinkedIn",
    skills: ["SQL", "Excel"],
    postedAt: "2026-08-11T09:00:00-07:00",
    description: "Own weekly reporting for the growth team.",
    ...overrides,
  };
}

describe("toJobResultView", () => {
  it("formats the posted date and carries the skill split", () => {
    const view = toJobResultView(entry(), true);

    expect(view).toEqual({
      id: "job-1",
      title: "Data Analyst",
      company: "Bloom Analytics",
      location: "San Diego, CA",
      postedAtLabel: "Aug 11",
      matchedSkills: ["SQL"],
      missingSkills: ["Excel"],
      score: 82,
    });
  });

  it("carries no raw instant at all", () => {
    const view = toJobResultView(entry(), true);
    expect("postedAt" in view).toBe(false);
    for (const value of Object.values(view)) {
      expect(String(value)).not.toMatch(/\d{4}-\d{2}-\d{2}T/);
    }
  });

  it("is null for a posting with no posted date", () => {
    const view = toJobResultView(
      entry({ job: { ...entry().job, postedAt: null } }),
      true,
    );
    expect(view.postedAtLabel).toBeNull();
  });

  it("hides the score entirely when there is no profile to score against", () => {
    // Not zero, and not the provider's number kept but ignored -- null, so a
    // card cannot accidentally render a score nobody can trust.
    const view = toJobResultView(entry({ score: 91 }), false);
    expect(view.score).toBeNull();
  });

  it("keeps the score when a profile is available", () => {
    const view = toJobResultView(entry({ score: 55 }), true);
    expect(view.score).toBe(55);
  });
});

describe("toJobPostingDetailView", () => {
  it("formats the posted date and keeps the description", () => {
    const view = toJobPostingDetailView(detail());

    expect(view.postedAtLabel).toBe("Aug 11");
    expect(view.description).toBe("Own weekly reporting for the growth team.");
    expect("postedAt" in view).toBe(false);
  });

  it("is null for a posting with no posted date", () => {
    const view = toJobPostingDetailView(detail({ postedAt: null }));
    expect(view.postedAtLabel).toBeNull();
  });
});

describe("jobsEmptyState", () => {
  it("is 'no-query' before anything has been searched", () => {
    expect(jobsEmptyState("", 0)).toBe("no-query");
  });

  it("treats whitespace-only input the same as empty", () => {
    expect(jobsEmptyState("   ", 0)).toBe("no-query");
  });

  it("is 'no-results' for a real search with nothing back", () => {
    expect(jobsEmptyState("underwater basket weaving", 0)).toBe("no-results");
  });

  it("is null once there is a query and results to show", () => {
    expect(jobsEmptyState("data analyst", 6)).toBeNull();
  });

  it("prefers 'no-query' over 'no-results' when both could apply", () => {
    // An empty query with a zero count is what "nothing searched yet" looks
    // like, not zero results for the empty string.
    expect(jobsEmptyState("", 0)).toBe("no-query");
  });
});

describe("shareWidth", () => {
  it("turns a 0-1 fraction into a rounded percentage", () => {
    expect(shareWidth(0.83)).toBe("83%");
    expect(shareWidth(1)).toBe("100%");
    expect(shareWidth(0)).toBe("0%");
  });

  it("rounds rather than truncates", () => {
    expect(shareWidth(0.665)).toBe("67%");
    expect(shareWidth(0.664)).toBe("66%");
  });

  it("clamps out-of-range input rather than printing a nonsense width", () => {
    expect(shareWidth(1.4)).toBe("100%");
    expect(shareWidth(-0.2)).toBe("0%");
  });
});

describe("competencyLabel", () => {
  const all: JobCompetency[] = ["strong", "good", "stretch", "reach"];

  it("has a label for every competency", () => {
    for (const competency of all) {
      expect(competencyLabel(competency).length).toBeGreaterThan(0);
    }
  });

  it("gives each competency its own word", () => {
    const labels = all.map(competencyLabel);
    expect(new Set(labels).size).toBe(all.length);
  });
});
