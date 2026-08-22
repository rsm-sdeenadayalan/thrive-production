/**
 * Public entry point for the data layer.
 *
 * Import from `$lib/data` and nothing deeper. In the Next app that convention
 * kept the mock modules an implementation detail that could be deleted without
 * touching the UI; here it is what will keep the Django client swappable.
 *
 * Three things are public, and nothing else is:
 *
 * - `./types`     the domain contract
 * - `./providers` the 25 functions and `SlotUnavailableError`
 * - `./labels`    presentation strings for the closed unions in `types`
 *
 * `./mock/*` and `./latency` are deliberately not re-exported. Everything under
 * `mock/` is what Django deletes, and `latency` is scaffolding for a delay that
 * a real network will supply. A component that needs something from either has
 * found a gap in the provider surface -- widen the surface rather than reach
 * through it.
 *
 * The Next tree violated this exactly once: `degree/requests/page.tsx:8` did
 * `import { requestTypeLabel } from "@/lib/data/mock/requests"`. It was the
 * only such import in the tree and it would have broken the build the day the
 * mocks were deleted. Fixed rather than reproduced -- both label maps now live
 * in `./labels` on this side of the boundary. MIGRATION.md section 9 defect 11.
 */

export * from "./types";
export * from "./providers";
export * from "./labels";
