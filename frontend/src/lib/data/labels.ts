import type { CourseRequest } from "./types";

/**
 * Presentation strings for the course-request form.
 *
 * ## Why these are not in `mock/requests.ts`
 *
 * In the Next tree they lived in the fixtures file, and
 * `app/degree/requests/page.tsx:8` imported them with
 * `from "@/lib/data/mock/requests"` -- reaching past the `@/lib/data` boundary
 * into a mock module. It was the only such import in the whole tree, and it
 * would have broken the build the day the mock modules were deleted for
 * Django. MIGRATION.md section 9 defect 11.
 *
 * They are not mock data. They are the labels for a closed union in
 * `types.ts`, and they stay correct no matter what is behind the providers, so
 * they belong on the public side of the seam. Exported from `$lib/data` with
 * everything else -- see `index.ts`.
 *
 * Both maps are keyed by `CourseRequest["type"]`, so adding a fifth request
 * type is a type error here until it gets a label and a help line.
 */

/** Labels for the four request types, used in chips and summaries. */
export const requestTypeLabel: Record<CourseRequest["type"], string> = {
  enroll: "Enroll in a course",
  drop: "Drop a course",
  "reduced load": "Reduced course load",
  "out of major": "Out-of-major enrollment",
};

/** What each type actually does, shown under the type picker. */
export const requestTypeHelp: Record<CourseRequest["type"], string> = {
  enroll: "Add a course you are not currently enrolled in.",
  drop: "Drop a course you are enrolled in this term.",
  "reduced load":
    "Request approval to carry fewer units than your track requires. Applies to the whole term.",
  "out of major":
    "Take a course outside the MSBA curriculum and have it count toward your degree.",
};
