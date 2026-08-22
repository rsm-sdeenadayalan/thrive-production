/**
 * Simulated network latency for the mock providers.
 *
 * ## Why this exists, and why it is not deleted
 *
 * Every provider routes its result through `resolveAfterDelay`. The delay is
 * not decoration: it is there to make loading and skeleton states *real rather
 * than theoretical*. With an instantly-resolving promise, a route that forgot
 * its pending state looks perfect in development and flickers in production.
 * The 120ms is small enough not to be annoying and large enough that a missing
 * loading state is visible on every page load.
 *
 * It stays until the Django client replaces the provider bodies, at which point
 * the real network supplies the delay and this module goes away.
 *
 * ## The knob
 *
 * `setMockLatencyMs(0)` removes the delay. That is the whole mechanism -- one
 * number, one place. Tests set it to 0 so the suite is not 40 x 120ms slower
 * than it needs to be; nothing in the app calls it.
 *
 * Note the compounding: `getProgramTimeline`, `getRequestPrefill`,
 * `bookAppointment`, `createRequest`, `submitRequest` and `generateNewVersion`
 * await other providers internally, so their real latency is a multiple of this
 * value.
 */

/** The default. Restored by `setMockLatencyMs(DEFAULT_MOCK_LATENCY_MS)`. */
export const DEFAULT_MOCK_LATENCY_MS = 120;

let latencyMs = DEFAULT_MOCK_LATENCY_MS;

/** The delay every provider currently pays, in milliseconds. */
export function mockLatencyMs(): number {
  return latencyMs;
}

/**
 * Set the simulated latency. Pass 0 to remove it.
 *
 * Negative values are clamped to 0 rather than handed to `setTimeout`, which
 * treats them as 0 anyway but would leave `mockLatencyMs()` lying about it.
 */
export function setMockLatencyMs(ms: number): void {
  latencyMs = Math.max(0, ms);
}

/**
 * Resolve `value` after the simulated latency.
 *
 * Always goes through `setTimeout`, even at 0, so provider results land on a
 * macrotask under every setting. A fast path that resolved synchronously at 0
 * would give tests a different ordering from production -- the opposite of what
 * the knob is for.
 */
export function resolveAfterDelay<T>(value: T): Promise<T> {
  return new Promise((resolve) => {
    setTimeout(() => resolve(value), latencyMs);
  });
}
