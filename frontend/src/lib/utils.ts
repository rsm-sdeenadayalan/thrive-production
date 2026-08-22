import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge class strings, with later Tailwind utilities beating earlier ones.
 *
 * Svelte 5 can take an array or object in `class=` and resolves conditionals
 * natively, so most of what `clsx` did here is now built in. What is NOT built
 * in is `tailwind-merge`'s conflict resolution, and that is the half that
 * matters wherever a component accepts a `class` override: without it
 * `p-4` and a caller's `p-2` both land in the attribute and the cascade picks
 * by stylesheet order rather than by intent.
 *
 * So this survives for the override case, and plain `class={[...]}` is fine
 * everywhere else.
 */
export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}
