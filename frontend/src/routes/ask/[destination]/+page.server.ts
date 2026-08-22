import { error } from "@sveltejs/kit";

import { isAskDestination, toConversationDetailView } from "$lib/ask";
import { getConversation } from "$lib/data";
import { messages } from "$lib/messages";
import { dayKeyOf } from "$lib/schedule";
import type { PageServerLoad } from "./$types";

/**
 * One destination, and optionally one conversation open inside it.
 *
 * ## The URL shape, and why the conversation is a search param
 *
 * `/ask/courses` is the destination. `/ask/courses?c=conv-002` is a specific
 * conversation inside it. Both are linkable and both work with the back button,
 * which is the requirement.
 *
 * A nested route (`/ask/courses/conv-002`) was the other option. The search
 * param wins because the conversation is a SELECTION WITHIN this page rather
 * than a page of its own: the rail, the destination heading and the composer are
 * all identical whether one is open or not, and a nested route would have needed
 * a second layout to say so. It also keeps "no conversation open" as the absence
 * of a parameter rather than as a special segment.
 *
 * ## An unknown destination is a 404, not a redirect
 *
 * `isAskDestination` validates the segment against the one list that also drives
 * the rail. Quietly redirecting a typo to Resources would make a broken link
 * look like a working one -- the same reasoning `PagePlaceholder` throws on an
 * href absent from `nav.ts` rather than rendering a generic page.
 *
 * A conversation id that does not resolve is a 404 for the same reason, and it
 * is a genuinely reachable state: the history lives on a server, so a link can
 * outlive what it points at.
 */
export const load: PageServerLoad = async ({ params, url }) => {
	if (!isAskDestination(params.destination)) {
		error(404, messages.ask.notFound.destination);
	}

	const destination = params.destination;
	const conversationId = url.searchParams.get("c");

	/*
	 * The clock, read once for this page's own formatting. The layout above reads
	 * it too for the rail; see the note there on why two reads microseconds apart
	 * is the accepted shape rather than a value threaded down.
	 */
	const todayKey = dayKeyOf(new Date());

	if (!conversationId) {
		return { destination, conversation: null, todayKey };
	}

	const conversation = await getConversation(conversationId);

	if (!conversation) {
		error(404, messages.ask.notFound.conversation);
	}

	/*
	 * A conversation opened under the wrong destination is a 404 too.
	 *
	 * `/ask/career?c=conv-002` names a real conversation in the wrong section, and
	 * rendering it would put a Course Recommender exchange under the Career
	 * heading with the Career rail highlighted -- a page quietly contradicting its
	 * own URL. The three destinations are separate surfaces, and this is where
	 * that is enforced rather than assumed.
	 */
	if (conversation.destination !== destination) {
		error(404, messages.ask.notFound.conversation);
	}

	return {
		destination,
		conversation: toConversationDetailView(conversation, todayKey),
		todayKey,
	};
};
