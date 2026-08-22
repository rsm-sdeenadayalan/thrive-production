import { redirect } from "@sveltejs/kit";

import { DEFAULT_DESTINATION } from "$lib/ask";
import type { PageServerLoad } from "./$types";

/**
 * `/ask` has no page of its own. It sends you to a destination.
 *
 * ## Why a redirect rather than a landing page
 *
 * The alternative was a chooser at `/ask` showing the three destinations as
 * cards. It was rejected for two reasons:
 *
 *  - **The rail already is the chooser**, and it is on screen on every one of
 *    the three destinations. A landing page would be a fourth surface whose only
 *    job is duplicated by furniture the student can see from wherever they land.
 *  - **A destination has to be in the URL for a conversation to be linkable**,
 *    which is the requirement this route shape exists for. `/ask` would be the
 *    one address in this section that names nothing.
 *
 * The cost is that clicking "Ask THRIVE" in the nav presumes Resources, which
 * is a guess about intent. It is a cheap one to correct -- the other two are one
 * click away in the rail -- and it beats landing somewhere that cannot answer
 * anything.
 *
 * 307 rather than 301 or 302: the destination `/ask` points at is a product
 * decision that may well change, and a permanent redirect would be cached in
 * students' browsers past the change.
 */
export const load: PageServerLoad = async () => {
	redirect(307, `/ask/${DEFAULT_DESTINATION}`);
};
