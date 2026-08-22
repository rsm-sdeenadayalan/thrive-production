/**
 * Page titles.
 *
 * Next did this declaratively in the root layout:
 *
 *     title: { default: "THRIVE", template: "%s · THRIVE" }
 *
 * SvelteKit has no equivalent -- `<svelte:head>` is per route and there is
 * nothing to inherit a template from -- so the pattern becomes this function,
 * called from each route's own head block. One place to change if the separator
 * or the product name ever does.
 */
export function pageTitle(name?: string): string {
	return name ? `${name} · THRIVE` : 'THRIVE';
}

/** The description the root layout sets, for routes that do not override it. */
export const SITE_DESCRIPTION =
	'One calm view of your MSBA program: classes, deadlines, degree progress, and what to do next.';
