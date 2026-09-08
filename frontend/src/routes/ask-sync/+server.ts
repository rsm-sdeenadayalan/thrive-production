/**
 * Same-origin proxy for the chat composer.
 *
 * Same shape and reasons as /overlay-sync: a client component cannot reach
 * Django cross-origin with credentials, so this route turns a small closed
 * set of actions into authenticated apiFetch calls. Unlike overlay-sync the
 * response body matters — the caller needs the persisted conversation back,
 * since that is what `ChatWindow` navigates to after a successful send.
 */
import { json } from "@sveltejs/kit";

import { ApiError, apiEnabled } from "$lib/data/api/client";
import {
	createConversation,
	rateMessage,
	sendConversationMessage,
} from "$lib/data/api/providers";
import type { AskDestination } from "$lib/data";
import type { RequestHandler } from "./$types";

type Payload = Record<string, unknown>;

export const POST: RequestHandler = async ({ request }) => {
	if (!apiEnabled()) {
		return json({ error: { code: "api_disabled", message: "API mode is off." } }, { status: 404 });
	}

	const payload = (await request.json()) as Payload;

	try {
		if (payload.action === "create") {
			const conversation = await createConversation(
				payload.destination as AskDestination,
				String(payload.body ?? ""),
			);
			return json({ conversation });
		}
		if (payload.action === "message") {
			const conversation = await sendConversationMessage(
				String(payload.conversationId ?? ""),
				String(payload.body ?? ""),
			);
			return json({ conversation });
		}
		/*
		 * A thumb, and the optional sentence that follows it.
		 *
		 * Deliberately does NOT return the conversation. Rating an answer is not a
		 * change to the transcript, and re-fetching one so the caller can throw it
		 * away would make every click cost a conversation load. The verdict alone
		 * comes back, and `ChatWindow` holds it in component state.
		 */
		if (payload.action === "rate") {
			const feedback = await rateMessage(
				String(payload.conversationId ?? ""),
				String(payload.messageId ?? ""),
				{
					// `?? undefined` would be wrong here: a null rating is the CLEAR
					// instruction (pressing the pressed thumb again), and collapsing it
					// to undefined turns "unrate this" into "leave it as it was".
					rating: ("rating" in payload
						? payload.rating
						: undefined) as "up" | "down" | null | undefined,
					note: payload.note === undefined ? undefined : String(payload.note),
				},
			);
			return json({ feedback });
		}
	} catch (error) {
		if (error instanceof ApiError) {
			return json({ error: { code: error.code, message: error.message } }, { status: error.status });
		}
		throw error;
	}

	return json(
		{ error: { code: "unknown_action", message: `Unknown action: ${String(payload.action)}` } },
		{ status: 400 },
	);
};
