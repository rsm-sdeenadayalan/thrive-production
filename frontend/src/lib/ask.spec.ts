import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ASK_DESTINATIONS,
  DEFAULT_DESTINATION,
  conversationsFor,
  isAskDestination,
  relativeDayLabel,
  showsDayLabel,
  toConversationDetailView,
  toConversationView,
  type ChatMessageView,
} from "$lib/ask";
import type { AskDestination, Conversation } from "$lib/data";

/**
 * Ask THRIVE's vocabulary and arithmetic.
 *
 * Clock-free by construction: every function takes `todayKey`, so none of this
 * depends on the runner's timezone and the seven-zone sweep has nothing to
 * disagree about. The one block that does freeze a clock is the provider block
 * at the bottom, which has to, because the fixtures are dated relative to now.
 *
 * `relativeDayLabel` gets the most attention here for a specific reason: it is
 * the only date arithmetic on this surface, and the obvious implementation --
 * dividing an elapsed-millisecond difference by 86,400,000 -- is wrong in a way
 * that only shows up across a DST boundary or near midnight. A 23:00 to 01:00
 * pair is two hours apart and one calendar day. See TESTING.md.
 */

function message(
  id: string,
  dayLabel: string,
  role: ChatMessageView["role"] = "student",
): ChatMessageView {
  return {
    id, role, body: "b", timeLabel: "9:00 AM", dayLabel,
    quickReplies: [], form: null,
  };
}

function conversation(
  id: string,
  destination: AskDestination,
  updatedAt: string,
  count = 2,
): Conversation {
  return {
    id,
    destination,
    title: `t-${id}`,
    updatedAt,
    messages: Array.from({ length: count }, (_, index) => ({
      id: `${id}-m${index}`,
      role: index % 2 === 0 ? ("student" as const) : ("thrive" as const),
      body: `body ${index}`,
      sentAt: updatedAt,
    })),
  };
}

describe("the destination list", () => {
  it("is the two, in rail order", () => {
    expect(ASK_DESTINATIONS).toEqual(["resources", "courses"]);
  });

  it("has the default among them", () => {
    // Otherwise `/ask` would redirect to a 404, and the redirect is the only
    // thing standing between the nav item and a dead end.
    expect(ASK_DESTINATIONS).toContain(DEFAULT_DESTINATION);
  });

  it("accepts exactly those two slugs", () => {
    for (const slug of ASK_DESTINATIONS) {
      expect(isAskDestination(slug)).toBe(true);
    }
  });

  it("refuses anything else, including near misses", () => {
    // The guard is what makes a typo a 404 instead of an empty page. A prefix or
    // a case variation must not slip through.
    expect(isAskDestination("resource")).toBe(false);
    expect(isAskDestination("Resources")).toBe(false);
    expect(isAskDestination("recommender")).toBe(false);
    expect(isAskDestination("")).toBe(false);
    expect(isAskDestination("__proto__")).toBe(false);
  });

  it("refuses the removed Career sub-tab", () => {
    // The career bot itself stays -- `AskDestination` (in `$lib/data`) still
    // includes `"career"` for the backend and its API-facing tests -- but the
    // UI sub-tab is gone, so the segment must 404 like any other unknown one.
    expect(isAskDestination("career")).toBe(false);
  });
});

describe("conversationsFor", () => {
  const all = [
    conversation("a", "resources", "2026-08-20T10:00:00.000Z"),
    conversation("b", "career", "2026-08-19T10:00:00.000Z"),
    conversation("c", "resources", "2026-08-18T10:00:00.000Z"),
  ];

  it("keeps only the destination asked for", () => {
    expect(conversationsFor(all, "resources").map((c) => c.id)).toEqual([
      "a",
      "c",
    ]);
  });

  it("preserves the order it was given", () => {
    // The provider sorts newest first and this must not re-sort. Two things
    // ordering independently is how a rail and a list disagree about which
    // conversation is the recent one.
    expect(conversationsFor(all, "resources").map((c) => c.id)).toEqual([
      "a",
      "c",
    ]);
  });

  it("is empty rather than absent for a destination with nothing in it", () => {
    expect(conversationsFor(all, "courses")).toEqual([]);
  });
});

describe("relativeDayLabel", () => {
  const today = "2026-08-21";

  it("says Today for an instant on the current day", () => {
    expect(relativeDayLabel(new Date(2026, 7, 21, 9, 0).toISOString(), today)).toBe(
      "Today",
    );
  });

  it("says Today for LATE on the current day", () => {
    /*
     * 23:00 local. Behind UTC this instant's `toISOString()` already reads as the
     * 22nd, so anything comparing ISO prefixes instead of local day keys calls
     * this Yesterday-or-worse. `dayKeyOf` builds from local parts.
     */
    expect(
      relativeDayLabel(new Date(2026, 7, 21, 23, 0).toISOString(), today),
    ).toBe("Today");
  });

  it("says Today for one minute past midnight", () => {
    expect(relativeDayLabel(new Date(2026, 7, 21, 0, 1).toISOString(), today)).toBe(
      "Today",
    );
  });

  it("says Yesterday for the day before", () => {
    expect(relativeDayLabel(new Date(2026, 7, 20, 9, 0).toISOString(), today)).toBe(
      "Yesterday",
    );
  });

  it("says Yesterday across a month boundary", () => {
    // 1 September's yesterday is 31 August, which a naive day-1 on the day
    // NUMBER would compute as the 0th of September.
    expect(
      relativeDayLabel(new Date(2026, 7, 31, 9, 0).toISOString(), "2026-09-01"),
    ).toBe("Yesterday");
  });

  it("says Yesterday across a year boundary", () => {
    expect(
      relativeDayLabel(new Date(2025, 11, 31, 9, 0).toISOString(), "2026-01-01"),
    ).toBe("Yesterday");
  });

  it("says Yesterday across a leap day", () => {
    expect(
      relativeDayLabel(new Date(2028, 1, 29, 9, 0).toISOString(), "2028-03-01"),
    ).toBe("Yesterday");
  });

  it("falls through to a date at two days out", () => {
    // Not "2 days ago". Past yesterday a date is easier to place than a count.
    expect(relativeDayLabel(new Date(2026, 7, 19, 9, 0).toISOString(), today)).toBe(
      "Aug 19",
    );
  });

  it("falls through to a date for anything older", () => {
    expect(relativeDayLabel(new Date(2026, 6, 4, 9, 0).toISOString(), today)).toBe(
      "Jul 4",
    );
  });

  it("does not call a FUTURE day Yesterday or Today", () => {
    // Not reachable from the fixtures, but the function has no business
    // inventing a relative word for a direction it does not handle.
    expect(relativeDayLabel(new Date(2026, 7, 22, 9, 0).toISOString(), today)).toBe(
      "Aug 22",
    );
  });
});

describe("toConversationView", () => {
  const today = "2026-08-21";

  it("formats the date and counts the messages", () => {
    const view = toConversationView(
      conversation("a", "career", new Date(2026, 7, 20, 9).toISOString(), 4),
      today,
    );

    expect(view).toEqual({
      id: "a",
      destination: "career",
      title: "t-a",
      updatedLabel: "Yesterday",
      messageCount: 4,
    });
  });

  it("carries no raw instant at all", () => {
    /*
     * The property, not the shape. The rail cannot format a timestamp wrongly if
     * there is no timestamp on the object it is handed -- which is stronger than
     * a convention about what components may do.
     */
    const view = toConversationView(
      conversation("a", "career", new Date(2026, 7, 20, 9).toISOString()),
      today,
    );

    expect("updatedAt" in view).toBe(false);
    expect("messages" in view).toBe(false);
    for (const value of Object.values(view)) {
      expect(String(value)).not.toMatch(/\d{4}-\d{2}-\d{2}T/);
    }
  });
});

describe("toConversationDetailView", () => {
  const today = "2026-08-21";

  it("formats every message's time and day", () => {
    const source = conversation(
      "a",
      "resources",
      new Date(2026, 7, 21, 14, 30).toISOString(),
      2,
    );

    const view = toConversationDetailView(source, today);

    expect(view.messages).toHaveLength(2);
    expect(view.messages[0].timeLabel).toBe("2:30 PM");
    expect(view.messages[0].dayLabel).toBe("Today");
    expect(view.messages[0].role).toBe("student");
    expect(view.messages[1].role).toBe("thrive");
  });

  it("leaves no raw instant on a message either", () => {
    const view = toConversationDetailView(
      conversation("a", "resources", new Date(2026, 7, 21, 14, 30).toISOString()),
      today,
    );

    for (const message of view.messages) {
      expect("sentAt" in message).toBe(false);
    }
  });

  it("defaults quickReplies and form when the provider message omits them", () => {
    // Every free-text reply in the mock fixtures and most saved conversations
    // never sets these -- a component walking the view model must not have to
    // treat "absent" and "empty" as two different states.
    const view = toConversationDetailView(
      conversation("a", "courses", new Date(2026, 7, 21, 14, 30).toISOString(), 1),
      today,
    );

    expect(view.messages[0].quickReplies).toEqual([]);
    expect(view.messages[0].form).toBeNull();
  });

  it("carries quickReplies and form through when the provider message sets them", () => {
    const source = conversation("a", "courses", new Date(2026, 7, 21, 14, 30).toISOString(), 1);
    source.messages[0].quickReplies = [{ label: "11 month", send: "11 month" }];
    source.messages[0].form = {
      kind: "rating",
      rows: [{ key: "skill_python", label: "Python" }],
      scale: [{ value: 3, label: "3", help: "Comfortable" }],
      default: 3,
      submitLabel: "Submit ratings",
    };

    const view = toConversationDetailView(source, today);

    expect(view.messages[0].quickReplies).toEqual([{ label: "11 month", send: "11 month" }]);
    expect(view.messages[0].form?.rows).toEqual([{ key: "skill_python", label: "Python" }]);
  });
});

describe("showsDayLabel", () => {
  it("always prints on the first row", () => {
    // There is nothing behind it to be the same as.
    expect(showsDayLabel([message("m0", "Today")], 0)).toBe(true);
  });

  it("does not repeat the same day", () => {
    const rows = [message("m0", "Today"), message("m1", "Today")];
    expect(showsDayLabel(rows, 1)).toBe(false);
  });

  it("prints when the day changes", () => {
    const rows = [message("m0", "Aug 19"), message("m1", "Today")];
    expect(showsDayLabel(rows, 1)).toBe(true);
  });

  it("prints again when the day changes back", () => {
    // Not reachable in a sorted conversation, but the function answers about the
    // row before it rather than about the whole list, and that is worth pinning.
    const rows = [
      message("m0", "Aug 19"),
      message("m1", "Today"),
      message("m2", "Aug 19"),
    ];
    expect(showsDayLabel(rows, 2)).toBe(true);
  });

  it("prints exactly once for a conversation held in one afternoon", () => {
    const rows = ["a", "b", "c", "d"].map((id) => message(id, "Today"));
    const printed = rows.filter((_, index) => showsDayLabel(rows, index));
    expect(printed).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// The providers behind it
// ---------------------------------------------------------------------------

describe("the conversation providers", () => {
  /** Tuesday 15 September 2026, 08:00 local. Built from local parts. */
  const FROZEN = new Date(2026, 8, 15, 8, 0, 0);

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(FROZEN);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  async function freshData() {
    vi.resetModules();
    const { setMockLatencyMs } = await import("$lib/data/latency");
    setMockLatencyMs(0);
    return import("$lib/data/index");
  }

  it("returns conversations newest first", async () => {
    const data = await freshData();
    const conversations = await data.getConversations();

    expect(conversations.length).toBeGreaterThan(1);

    const stamps = conversations.map((entry) => Date.parse(entry.updatedAt));
    expect(stamps).toEqual([...stamps].sort((a, b) => b - a));
  });

  it("covers every UI destination, so no rail section is empty by accident", async () => {
    const data = await freshData();
    const conversations = await data.getConversations();

    for (const destination of ASK_DESTINATIONS) {
      expect(
        conversationsFor(conversations, destination).length,
        `${destination} has no example conversation`,
      ).toBeGreaterThan(0);
    }
  });

  it("hands out copies, including the message arrays", async () => {
    /*
     * The provider boundary's standing property. The nested array matters more
     * here than anywhere else in the data layer: a chat UI has an obvious reason
     * to want to append to `messages`, and a shallow spread would have handed it
     * the fixture's own array to push into.
     */
    const data = await freshData();

    const [first] = await data.getConversations();
    first.title = "Mutated";
    first.messages.push({
      id: "injected",
      role: "student",
      body: "x",
      sentAt: FROZEN.toISOString(),
    });

    const [again] = await data.getConversations();
    expect(again.title).not.toBe("Mutated");
    expect(again.messages.map((m) => m.id)).not.toContain("injected");
  });

  it("finds one by id", async () => {
    const data = await freshData();
    const conversation = await data.getConversation("conv-001");

    expect(conversation?.id).toBe("conv-001");
    expect(conversation?.destination).toBe("resources");
  });

  it("returns null for an id that is not on file", async () => {
    // A link to a conversation can outlive the conversation, so the page turns
    // this into a 404 rather than the provider throwing at a student.
    const data = await freshData();

    expect(await data.getConversation("conv-nope")).toBeNull();
    expect(await data.getConversation("")).toBeNull();
  });

  it("builds fresh dates on every call rather than freezing at module load", async () => {
    /*
     * The fixture is a function, not a const. With a const, a dev server left
     * open overnight would keep showing "Today" against yesterday -- which is
     * the same class of staleness the whole relative-dates module exists to
     * avoid.
     */
    const data = await freshData();
    const before = (await data.getConversations())[0].updatedAt;

    vi.setSystemTime(new Date(2026, 8, 17, 8, 0, 0));
    const after = (await data.getConversations())[0].updatedAt;

    expect(after).not.toBe(before);
  });
});
