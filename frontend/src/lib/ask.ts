import type {
  AskDestination,
  ChatRole,
  Conversation,
} from "$lib/data";
import { formatShortDate, formatTime } from "$lib/format";
import { messages } from "$lib/messages";
import { dayKeyOf } from "$lib/schedule";

/**
 * Ask THRIVE's vocabulary and arithmetic.
 *
 * Everything here is pure and clock-free. "Today" arrives as a day key, the
 * same shape as `describeDue`'s `now` and `$lib/availability`'s `todayKey`, so
 * the server stays the only thing that decides what today is and the whole
 * module is timezone-independent by construction.
 *
 * ## Two destinations, one list
 *
 * `ASK_DESTINATIONS` drives the rail, the route validation and the empty
 * states. Same property `nav.ts` has: one list, so a third destination is one
 * edit and a destination cannot exist in the rail while the router refuses it.
 *
 * Career lived here until 2026-08-24, when its sub-tab was removed from the
 * UI in favor of the Career job feed at `/jobs` -- one obvious way to reach
 * the career tools, not two. `AskDestination` itself (in `$lib/data`) still
 * includes `"career"`: the backend career bot and its API-facing tests are
 * untouched, only the UI's list of reachable destinations shrank. Leaving
 * `"career"` off this list is what makes `isAskDestination("career")` false
 * and `/ask/career` a clean 404 rather than a route that still half-works.
 */

/** The two surfaces, in rail order. */
export const ASK_DESTINATIONS: readonly AskDestination[] = [
  "resources",
  "courses",
] as const;

/** The one a bare `/ask` lands on. */
export const DEFAULT_DESTINATION: AskDestination = "resources";

/**
 * Is this URL segment a live Ask destination?
 *
 * The route parameter is a string from the address bar, so this is what stands
 * between a typo and a page rendering an empty rail with no explanation. The
 * page throws a 404 on false rather than defaulting: quietly redirecting a
 * mistyped destination to Resources would make a broken link look like a
 * working one.
 */
export function isAskDestination(value: string): value is AskDestination {
  return (ASK_DESTINATIONS as readonly string[]).includes(value);
}

/**
 * Conversations belonging to one destination, order preserved.
 *
 * Generic over "anything carrying a destination" so it serves the `Conversation`
 * a provider returns AND the `ConversationView` the rail holds. The alternative
 * was two functions, or the rail filtering inline -- and the rail filtering
 * inline is how the scoping rule ends up stated in one place and applied in
 * another.
 */
export function conversationsFor<T extends { destination: AskDestination }>(
  conversations: readonly T[],
  destination: AskDestination,
): T[] {
  return conversations.filter(
    (conversation) => conversation.destination === destination,
  );
}

/**
 * "Today" / "Yesterday" / "Aug 19" for a saved conversation's last activity.
 *
 * Relative wins where it applies, because "Today" is what a student is actually
 * looking for in a history list and a bare date makes them do the subtraction.
 * Past two days it becomes a date, since "5 days ago" is harder to place than
 * the date itself.
 *
 * Takes `todayKey` rather than reading a clock. Day keys are compared as
 * strings and the offsets are computed from local parts, so this cannot drift
 * across a timezone or a DST boundary the way an elapsed-milliseconds division
 * would -- a 23:00 to 01:00 pair is two hours apart and one calendar day.
 */
export function relativeDayLabel(iso: string, todayKey: string): string {
  const dayKey = dayKeyOf(iso);
  const copy = messages.ask.history;

  if (dayKey === todayKey) return copy.today;

  const yesterday = new Date(
    Number(todayKey.slice(0, 4)),
    Number(todayKey.slice(5, 7)) - 1,
    Number(todayKey.slice(8, 10)) - 1,
  );

  if (dayKey === dayKeyOf(yesterday)) return copy.yesterday;

  return formatShortDate(iso);
}

// ---------------------------------------------------------------------------
// View models -- every date already a string
// ---------------------------------------------------------------------------

export interface ChatMessageView {
  id: string;
  role: ChatRole;
  body: string;
  /** "9:30 AM" */
  timeLabel: string;
  /** "Today" / "Yesterday" / "Aug 19" */
  dayLabel: string;
}

export interface ConversationView {
  id: string;
  destination: AskDestination;
  title: string;
  /** "Today" / "Yesterday" / "Aug 19" — the history list's timestamp. */
  updatedLabel: string;
  /** How many messages, for the rail's mono count. */
  messageCount: number;
}

/** One conversation opened, with every message formatted. */
export interface ConversationDetailView extends ConversationView {
  messages: ChatMessageView[];
}

/**
 * A conversation as the rail shows it: a title, when, and how long.
 *
 * The messages are NOT included. The rail renders five of these and the
 * fixtures carry four messages each; shipping every body to render a title
 * would be the page's largest payload by far and none of it would be read.
 */
export function toConversationView(
  conversation: Conversation,
  todayKey: string,
): ConversationView {
  return {
    id: conversation.id,
    destination: conversation.destination,
    title: conversation.title,
    updatedLabel: relativeDayLabel(conversation.updatedAt, todayKey),
    messageCount: conversation.messages.length,
  };
}

/** The same, plus the messages, for the one conversation actually open. */
export function toConversationDetailView(
  conversation: Conversation,
  todayKey: string,
): ConversationDetailView {
  return {
    ...toConversationView(conversation, todayKey),
    messages: conversation.messages.map((message) => ({
      id: message.id,
      role: message.role,
      body: message.body,
      timeLabel: formatTime(message.sentAt),
      dayLabel: relativeDayLabel(message.sentAt, todayKey),
    })),
  };
}

/**
 * Whether a message row should print its own day.
 *
 * Only when it differs from the row before it, so a conversation held in one
 * afternoon shows one day heading rather than one per message. Index 0 always
 * prints, because the first row has nothing behind it to be the same as.
 *
 * Out here rather than in the component for the usual reason: it is an
 * off-by-one waiting to happen, and logic left in a `.svelte` file is logic no
 * gate can see.
 */
export function showsDayLabel(
  messages: readonly ChatMessageView[],
  index: number,
): boolean {
  if (index === 0) return true;
  return messages[index].dayLabel !== messages[index - 1].dayLabel;
}
