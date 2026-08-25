import { error, fail, redirect } from "@sveltejs/kit";

import { isAskDestination, toConversationDetailView } from "$lib/ask";
import { apiEnabled } from "$lib/data/api/client";
import { deleteConversation, getConversation, getConversationStarter } from "$lib/data";
import { messages } from "$lib/messages";
import { dayKeyOf } from "$lib/schedule";
import type { Actions, PageServerLoad } from "./$types";

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

	/**
	 * Whether the write path is live. `ChatWindow` needs this to pick its send
	 * flow; the layout above computes the same flag for the intro copy it
	 * renders. Two reads of the same env var, not one threaded down -- the same
	 * tradeoff the layout's own doc comment makes for `todayKey`.
	 */
	const live = apiEnabled();

	if (!conversationId) {
		/*
		 * No conversation yet, so offer the destination's opening prompt if it has
		 * one. Only the course recommender does: it runs a scripted interview, and
		 * opening on its first question with its buttons is strictly more useful
		 * than opening on a box the student has to type into to find out a question
		 * was coming. Fetched here rather than written in the component so the
		 * question cannot drift from the one the bot asks.
		 */
		const starter = await getConversationStarter(destination);
		return { destination, conversation: null, todayKey, live, starter };
	}

	const conversation = await getConversation(conversationId);

	if (!conversation) {
		error(404, messages.ask.notFound.conversation);
	}

	/*
	 * A conversation opened under the wrong destination is a 404 too.
	 *
	 * `/ask/resources?c=conv-002` names a real conversation in the wrong section,
	 * and rendering it would put a Course Recommender exchange under the
	 * Resources heading with the Resources rail highlighted -- a page quietly
	 * contradicting its own URL. The destinations are separate surfaces, and
	 * this is where that is enforced rather than assumed.
	 */
	if (conversation.destination !== destination) {
		error(404, messages.ask.notFound.conversation);
	}

	return {
		destination,
		conversation: toConversationDetailView(conversation, todayKey),
		todayKey,
		live,
		// A conversation is open, so there is nothing to open ON.
		starter: null,
	};
};

/**
 * Deleting a saved conversation.
 *
 * A form action rather than a `fetch` from the rail, for the reason every other
 * write in this app is one: it works before the client bundle has loaded and
 * without JavaScript at all, and the redirect below is then the browser's own
 * rather than something the component has to remember to do.
 *
 * The action lives on the PAGE while the control lives in the LAYOUT, which is
 * fine and is why the form posts to an explicit `?/deleteConversation` URL: a
 * layout has no actions of its own, and the destination page is always the one
 * underneath it.
 */
export const actions = {
	deleteConversation: async ({ request, params, url }) => {
		if (!isAskDestination(params.destination)) {
			error(404, messages.ask.notFound.destination);
		}

		const data = await request.formData();
		const conversationId = String(data.get("conversationId") ?? "");
		if (!conversationId) {
			return fail(400, { deleteFailed: true });
		}

		try {
			await deleteConversation(conversationId);
		} catch {
			// The rail still shows the row, which is the truth: it is still there.
			return fail(500, { deleteFailed: true });
		}

		/*
		 * If the conversation just deleted is the one on screen, the URL now points
		 * at something that does not exist and `load` would 404 on it. Land on the
		 * bare destination instead -- a new conversation, which is what a student
		 * who just threw this one away is ready for.
		 *
		 * Deleting any OTHER row leaves the open one open: the action returns, the
		 * page invalidates, and only the rail changes.
		 */
		if (url.searchParams.get("c") === conversationId) {
			redirect(303, `/ask/${params.destination}`);
		}

		return { deleted: conversationId };
	}
} satisfies Actions;
