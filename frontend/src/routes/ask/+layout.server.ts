import { toConversationView, type ConversationView } from "$lib/ask";
import { getConversations } from "$lib/data";
import { dayKeyOf } from "$lib/schedule";
import type { LayoutServerLoad } from "./$types";

/**
 * The rail's data, loaded once for the whole section.
 *
 * ## Why the layout and not the page
 *
 * The saved-conversation list is the same list on all three destinations -- the
 * rail shows every destination's history, scoped per section by a predicate over
 * one array. Loading it in each `+page.server.ts` would re-fetch it on every
 * destination switch and re-render the rail underneath the student for no reason.
 * A layout load runs once and survives navigation between its children, which is
 * exactly the lifetime the rail has.
 *
 * ## One clock read, and it is here
 *
 * `new Date()` once. `todayKey` comes off it and every "Today" / "Yesterday" in
 * the rail is decided against that one answer. The page below reads its own
 * clock for the open conversation's message stamps -- a second read, microseconds
 * apart, and the same tradeoff `routes/calendar/+page.server.ts` documents: they
 * can only disagree across a midnight boundary, at which point the page is stale
 * anyway.
 *
 * Nothing raw crosses to the client. `ConversationView` has no ISO field on it
 * at all, so there is not even a timestamp available to a component that wanted
 * to format one.
 */
export const load: LayoutServerLoad = async () => {
	const conversations = await getConversations();
	const todayKey = dayKeyOf(new Date());

	const views: ConversationView[] = conversations.map((conversation) =>
		toConversationView(conversation, todayKey),
	);

	return {
		/** Every saved conversation, newest first, already formatted. */
		conversations: views,
	};
};
