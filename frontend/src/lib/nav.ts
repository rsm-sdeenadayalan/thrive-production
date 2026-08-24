import type House from '@lucide/svelte/icons/house';
import BookOpen from '@lucide/svelte/icons/book-open';
import BriefcaseBusiness from '@lucide/svelte/icons/briefcase-business';
import CalendarCheck from '@lucide/svelte/icons/calendar-check';
import CalendarDays from '@lucide/svelte/icons/calendar-days';
import CalendarRange from '@lucide/svelte/icons/calendar-range';
import ClipboardList from '@lucide/svelte/icons/clipboard-list';
import FileText from '@lucide/svelte/icons/file-text';
import GraduationCap from '@lucide/svelte/icons/graduation-cap';
import HouseIcon from '@lucide/svelte/icons/house';
import LibraryBig from '@lucide/svelte/icons/library-big';
import Settings from '@lucide/svelte/icons/settings';
import Sparkles from '@lucide/svelte/icons/sparkles';

/**
 * The icon type, derived from a real icon rather than declared.
 *
 * `@lucide/svelte` exports `LucideIcon` from a `types` module that is not in its
 * package exports map, so it cannot be imported. Taking `typeof` an icon gets
 * the same `Component<LucideProps>` through the public surface, and cannot drift
 * from what the icons actually are.
 */
export type NavIcon = typeof House;

export interface NavItem {
	href: string;
	label: string;
	icon: NavIcon;
	/** Short description, used as the accessible hint and rail tooltip. */
	description: string;
	/**
	 * Destinations nested under this one, rendered as a disclosure in the rail.
	 *
	 * ## Why children rather than a fifth top-level item per destination
	 *
	 * Ask THRIVE's two surfaces are one destination a student picks a subject
	 * inside, not separate things to navigate between. Four rail items plus two
	 * more is six, well inside the eleven-item nav this project already trimmed
	 * once.
	 *
	 * ## The rule that keeps this from splintering
	 *
	 * A child is a REAL route with its own href, label, icon and description --
	 * exactly a `NavItem`, recursively. Nothing about a child is a special case, so
	 * every consumer that walks the tree gets the same shape at every level, and
	 * `PagePlaceholder`'s lookup keeps working without knowing that nesting exists.
	 *
	 * One level only, and deliberately: `flattenNav` recurses, so a second level
	 * would WORK, but the rail's disclosure is designed for one and a nested
	 * disclosure inside a 240px rail is a different design question. If a grandchild
	 * is ever wanted, that is a conversation rather than an edit.
	 */
	children?: NavItem[];
}

/**
 * The visible navigation. FIVE DESTINATIONS, in this order.
 *
 * ONE LIST drives the desktop rail and the mobile bottom bar, so the two can
 * never drift apart. Trimmed from eleven on 2026-08-22: nine of the eleven were
 * placeholders, and a nav that is four-fifths stubs reads as broken rather than
 * unfinished. Jobs was added on 2026-08-23 as the fifth -- a real page, not a
 * stub, so the trim's own reasoning is not undone by growing the list back out.
 *
 * The bottom bar renders this list DIRECTLY rather than naming its own hrefs,
 * which is new. It used to carry `PRIMARY_SLOTS = ['/', '/calendar',
 * '/classes', '/assignments']` -- a second, hardcoded copy of "which are the
 * important ones" that had to be kept in step by hand. Two of those four are
 * parked now, so that copy would have been the thing that broke.
 */
export const primaryNav: NavItem[] = [
	{
		href: '/',
		label: 'Home',
		icon: HouseIcon,
		description: 'Your day at a glance'
	},
	{
		href: '/calendar',
		label: 'Calendar',
		icon: CalendarDays,
		description: 'Classes, deadlines, and events on one timeline'
	},
	{
		href: '/appointments',
		label: 'Appointments',
		icon: CalendarCheck,
		description: 'Book time with advising and career coaching'
	},
	{
		href: '/jobs',
		label: 'Career',
		icon: BriefcaseBusiness,
		description: 'Postings ranked against your resume — search, save, apply'
	},
	{
		href: '/ask',
		label: 'Ask THRIVE',
		icon: Sparkles,
		description: 'Ask a question, or get class and job suggestions',
		/*
		 * The two subjects, which used to live in a second rail on the page.
		 *
		 * They are here because they are NAVIGATION -- each is a route with its own
		 * URL, its own empty state and its own saved conversations -- and navigation
		 * belongs in the navigation. A page-level rail holding them meant two rails
		 * on the left and a student having to learn which one meant what.
		 *
		 * `/ask` itself redirects to the first of these. So the parent is a real
		 * destination AND a group, which is what lets one tap on a phone still go
		 * somewhere useful.
		 *
		 * A third child, Career, lived here until 2026-08-24: the career bot itself
		 * stays (see `$lib/data`'s `AskDestination` and its API-facing tests), but
		 * the sub-tab is gone from the UI, folded into the Career job feed at
		 * `/jobs` instead. `$lib/ask`'s `ASK_DESTINATIONS` no longer lists it, so
		 * `/ask/career` 404s cleanly rather than crashing.
		 */
		children: [
			{
				href: '/ask/resources',
				label: 'Resources',
				icon: LibraryBig,
				description: 'Answers from the program’s own material'
			},
			{
				href: '/ask/courses',
				label: 'Course Recommender',
				icon: GraduationCap,
				description: 'Which classes and electives fit where you are going'
			}
		]
	}
];

/**
 * PARKED. Routes that still exist and are deliberately rendered by no nav
 * surface.
 *
 * Not deleted, because they come back as the product grows -- the routes, their
 * files, their icons and their descriptions are all intact and reachable by URL.
 * The only thing removed is the way in.
 *
 * ## Why a separate list rather than a `hidden` flag on one list
 *
 * A flag would need every surface to remember to filter on it. There are two
 * surfaces today and there will be more, and the failure mode of forgetting is
 * that a parked item silently reappears in one place -- exactly the class of bug
 * "one list drives everything" exists to prevent. With a separate list, the
 * surfaces render `primaryNav` and CANNOT render these, structurally, without
 * importing something new. Same reasoning as `filterSchedule` in
 * CONVENTIONS.md: make the failure impossible rather than something to
 * remember.
 *
 * The cost is that `PagePlaceholder` has to look through more than one list --
 * which is why the lookup lives in `allNav` below instead of being spread at
 * each call site.
 *
 * To bring one back: move it into `primaryNav`. That is the whole operation.
 */
export const parkedNav: NavItem[] = [
	{
		href: '/classes',
		label: 'Classes',
		icon: BookOpen,
		description: 'Your courses this term'
	},
	{
		href: '/syllabi',
		label: 'Syllabi',
		icon: FileText,
		description: 'What each course expects of you'
	},
	{
		href: '/assignments',
		label: 'Assignments',
		icon: ClipboardList,
		description: 'Everything due, in one list'
	},
	{
		href: '/degree',
		label: 'Degree',
		icon: GraduationCap,
		description: 'Progress toward graduation'
	},
	{
		href: '/events',
		label: 'Events',
		icon: CalendarRange,
		description: 'Career fairs, panels, and workshops'
	},
	{
		href: '/resources',
		label: 'Resources',
		icon: LibraryBig,
		description: 'Support and services across campus'
	},
	/*
	 * Settings is parked too, and it is the one item the brief's list did not
	 * name -- flagged in the handoff rather than decided quietly.
	 *
	 * It was the eleventh destination and one of the nine placeholders, it used
	 * to live in a `secondaryNav` list pinned to the bottom of the rail, and on
	 * mobile the ONLY way to it was the More sheet. So "trim to four" and "the
	 * More sheet has nothing to hold" are both only true with Settings parked:
	 * keeping it would have left the sheet alive holding exactly one item.
	 *
	 * `secondaryNav` is gone with it. One item in its own list, rendered in its
	 * own pinned strip, was a structure worth having for a gear at the bottom of
	 * a rail; it is not worth having for nothing.
	 *
	 * Reachable at /settings, and one line from coming back.
	 */
	{
		href: '/settings',
		label: 'Settings',
		icon: Settings,
		description: 'Preferences, connections, and consent'
	}
];

/**
 * Every entry in a tree, flattened depth-first, parents before children.
 *
 * THE reason the tree is still a single source. Every consumer that needs "is
 * this a route" or "find me this href" walks a FLATTENED view derived from the
 * same array the rail renders -- so adding a child cannot be forgotten in one
 * place, because there is no second place to add it to.
 *
 * Recursive, though the rail only draws one level. See the note on `children`.
 */
export function flattenNav(items: NavItem[]): NavItem[] {
	return items.flatMap((item) => [item, ...flattenNav(item.children ?? [])]);
}

/**
 * Every nav entry, visible or parked. THE LOOKUP LIST -- not for rendering.
 *
 * `PagePlaceholder` resolves its own href against this and throws when there is
 * no match, which is what makes "a stub page can never disagree with its nav
 * entry" a guarantee rather than an intention. Parking a route must not start
 * that throwing, so parked entries have to stay findable; that is the whole
 * reason this export exists.
 *
 * If you are reaching for this to render something, you want `primaryNav`.
 */
export const allNav: NavItem[] = flattenNav([...primaryNav, ...parkedNav]);

/**
 * Is this route a page worth sending someone to?
 *
 * **`primaryNav` membership IS the definition**, which is the whole point: the
 * visible navigation already encodes "this is a real destination", so a card
 * linking out asks the same list rather than carrying its own opinion. Parked
 * routes still render — they return `PagePlaceholder`, a title and a note — and
 * a "View all" landing on one reads as broken rather than unfinished.
 *
 * ## Why this is derived rather than a flag on each card
 *
 * Four cards on Home link out and three of them point at parked routes today.
 * The alternative was each card deciding for itself whether to show its link,
 * which is four places to edit when a route is built and four chances to forget
 * one. Asking `primaryNav` means **moving a route out of `parkedNav` brings its
 * card's link back with no further edit** — the same one-list-drives-everything
 * property the rail and the bottom bar already have.
 *
 * Same reasoning as `parkedNav` being a separate list rather than a `hidden`
 * flag: make the failure impossible rather than something to remember.
 */
export function isBuiltRoute(href: string): boolean {
	// Flattened, so a child destination counts as built. `/ask/courses` is as real
	// a page as `/calendar`, and a card linking to one must not be withheld
	// because the route happens to be nested.
	return flattenNav(primaryNav).some((item) => item.href === href);
}

/**
 * Is this href in either nav list?
 *
 * The companion to `isBuiltRoute`, and it exists because those two questions
 * have the same answer for very different reasons. A parked route answers
 * "false, deliberately"; a mistyped one answers "false, because it does not
 * exist" — and silently hiding a link because somebody fat-fingered an href is
 * the silent no-op this repo treats as its worst failure mode.
 *
 * `SectionCard` warns in development on the second case. Not a throw:
 * `PagePlaceholder` can throw because it IS the page, whereas taking Home down
 * over a "View all" would be worse than the broken link.
 */
export function isKnownRoute(href: string): boolean {
	return allNav.some((item) => item.href === href);
}

/**
 * True when `href` is the section the user is currently in. Exact match for
 * Home so it doesn't stay lit on every route; prefix match elsewhere so
 * nested routes still highlight their section.
 */
export function isActiveRoute(href: string, pathname: string): boolean {
	if (href === '/') return pathname === '/';
	return pathname === href || pathname.startsWith(`${href}/`);
}
