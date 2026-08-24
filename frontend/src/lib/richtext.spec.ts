import { describe, expect, it } from "vitest";

import { parseInline, parseRichText, type RichBlock } from "$lib/richtext";

/**
 * The rich-text parser's vocabulary, pinned span by span and block by
 * block.
 *
 * Rendering is out of scope here on purpose -- same split `designSystem.spec.ts`
 * draws for the rest of the app: Vitest runs in Node with no jsdom, so this
 * tests the DATA `RichMessage.svelte` walks, not what a browser does with it.
 * A bug in the tree the parser hands back is a bug no gate downstream could
 * localise; a bug in how faithfully `<RichMessage>` renders that tree is a
 * different bug, in a different file.
 */

function textOf(spans: { kind: string; text: string }[]) {
  return spans.map((span) => `${span.kind}:${span.text}`);
}

describe("parseInline", () => {
  it("reads a bold span", () => {
    expect(parseInline("**CSE 251A**")).toEqual([{ kind: "bold", text: "CSE 251A" }]);
  });

  it("reads bold in the middle of plain text", () => {
    expect(textOf(parseInline("Try **CSE 251A** first"))).toEqual([
      "text:Try ",
      "bold:CSE 251A",
      "text: first",
    ]);
  });

  it("reads an inline code span", () => {
    expect(parseInline("Run `npm test` first")).toEqual([
      { kind: "text", text: "Run " },
      { kind: "code", text: "npm test" },
      { kind: "text", text: " first" },
    ]);
  });

  it("degrades an unclosed bold marker to two literal asterisks", () => {
    // Nothing here throws and nothing is dropped -- an LLM reply has no
    // obligation to close what it opens.
    expect(textOf(parseInline("**CSE 251A is great"))).toEqual([
      "text:**CSE 251A is great",
    ]);
  });

  it("degrades an unclosed inline-code backtick to a literal backtick", () => {
    expect(textOf(parseInline("the `npm test command"))).toEqual([
      "text:the `npm test command",
    ]);
  });

  it("never mangles a [n] citation", () => {
    // Citations are exactly the shape the app's replies use, and they are
    // deliberately not a Markdown construct this parser knows about --
    // they must survive untouched as plain text.
    expect(parseInline("a strong fit [1].")).toEqual([
      { kind: "text", text: "a strong fit [1]." },
    ]);
  });

  it("returns one plain span for text with no markers at all", () => {
    expect(parseInline("plain sentence")).toEqual([
      { kind: "text", text: "plain sentence" },
    ]);
  });

  it("returns nothing for an empty line", () => {
    expect(parseInline("")).toEqual([]);
  });
});

describe("parseRichText", () => {
  it("returns an empty list for an empty string", () => {
    expect(parseRichText("")).toEqual([]);
  });

  it("returns one paragraph for a single plain sentence", () => {
    const blocks = parseRichText("Here is a plain sentence.");
    expect(blocks).toEqual([
      { type: "paragraph", lines: [[{ kind: "text", text: "Here is a plain sentence." }]] },
    ]);
  });

  it("keeps a single newline inside one paragraph as an explicit line break", () => {
    const blocks = parseRichText("First line\nSecond line");
    expect(blocks).toHaveLength(1);
    const [block] = blocks as [RichBlock & { type: "paragraph" }];
    expect(block.type).toBe("paragraph");
    expect(block.lines).toEqual([
      [{ kind: "text", text: "First line" }],
      [{ kind: "text", text: "Second line" }],
    ]);
  });

  it("splits two sentences separated by a blank line into two paragraphs", () => {
    const blocks = parseRichText("First paragraph.\n\nSecond paragraph.");
    expect(blocks.map((block) => block.type)).toEqual(["paragraph", "paragraph"]);
  });

  it("groups an unordered list's dash lines into one block", () => {
    const blocks = parseRichText("- CSE 251A\n- MGTA 461\n- MGTA 495");
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("unordered-list");
    if (blocks[0].type === "unordered-list") {
      expect(blocks[0].items).toEqual([
        [{ kind: "text", text: "CSE 251A" }],
        [{ kind: "text", text: "MGTA 461" }],
        [{ kind: "text", text: "MGTA 495" }],
      ]);
    }
  });

  it("groups a star-bulleted list the same way as a dash list", () => {
    const blocks = parseRichText("* one\n* two");
    expect(blocks).toEqual([
      {
        type: "unordered-list",
        items: [
          [{ kind: "text", text: "one" }],
          [{ kind: "text", text: "two" }],
        ],
      },
    ]);
  });

  it("parses bold inside a blockquote's inline text", () => {
    const blocks = parseRichText("> **Heads up:** enrollment closes Friday.");
    expect(blocks).toEqual([
      {
        type: "blockquote",
        lines: [
          [
            { kind: "bold", text: "Heads up:" },
            { kind: "text", text: " enrollment closes Friday." },
          ],
        ],
      },
    ]);
  });

  it("parses the full course-recommendation shape: paragraph, ol, blockquote, paragraph", () => {
    // The example this feature was built against: a lead-in sentence, five
    // numbered picks with bold titles and a citation each, a warning
    // blockquote, and a closing question.
    const reply = [
      "Great choice! Here are the top courses for that goal.",
      "",
      "1. **CSE 251A – Machine Learning** ⭐ Top Pick — foundational modeling [1].",
      "2. **MGTA 461 – Web Mining** — text and network methods [2].",
      "3. **MGTA 452 – Collecting and Analyzing Large Data** — pipelines at scale [3].",
      "4. **MGTA 495 – GenAI for Business** — applied LLM workflows [4].",
      "5. **MGTA 464 – SQL and ETL** — the data plumbing underneath all four [5].",
      "",
      "> ⚠️ A heads-up: two of these run only in one quarter, so check the schedule before you commit.",
      "",
      "Would you like help mapping these against your remaining electives?",
    ].join("\n");

    const blocks = parseRichText(reply);

    expect(blocks.map((block) => block.type)).toEqual([
      "paragraph",
      "ordered-list",
      "blockquote",
      "paragraph",
    ]);

    const [lead, list, warning, closing] = blocks;

    expect(lead.type).toBe("paragraph");
    if (lead.type === "paragraph") {
      expect(lead.lines).toHaveLength(1);
    }

    expect(list.type).toBe("ordered-list");
    if (list.type === "ordered-list") {
      expect(list.items).toHaveLength(5);
      // The model's own numbers are discarded; a real <ol> renumbers itself,
      // which is exactly why they are never read back out of the parse tree.
      expect(textOf(list.items[0])).toEqual([
        "bold:CSE 251A – Machine Learning",
        "text: ⭐ Top Pick — foundational modeling [1].",
      ]);
      expect(textOf(list.items[4])).toEqual([
        "bold:MGTA 464 – SQL and ETL",
        "text: — the data plumbing underneath all four [5].",
      ]);
    }

    expect(warning.type).toBe("blockquote");
    if (warning.type === "blockquote") {
      expect(warning.lines).toHaveLength(1);
      expect(textOf(warning.lines[0])).toEqual([
        "text:⚠️ A heads-up: two of these run only in one quarter, so check the schedule before you commit.",
      ]);
    }

    expect(closing.type).toBe("paragraph");
    if (closing.type === "paragraph") {
      expect(textOf(closing.lines[0])).toEqual([
        "text:Would you like help mapping these against your remaining electives?",
      ]);
    }
  });

  it("re-groups a numbered list repeating the same number as one ol with every item kept", () => {
    // Models drift on numbering under truncation or retries. The parser must
    // still keep every item, in the order it arrived, for a real <ol> to
    // renumber.
    const blocks = parseRichText("1. first\n1. second\n1. third");
    expect(blocks).toEqual([
      {
        type: "ordered-list",
        items: [
          [{ kind: "text", text: "first" }],
          [{ kind: "text", text: "second" }],
          [{ kind: "text", text: "third" }],
        ],
      },
    ]);
  });

  it("ends a list at a blank line rather than fusing it with what follows", () => {
    const blocks = parseRichText("1. first\n1. second\n\n1. third");
    expect(blocks).toHaveLength(2);
    expect(blocks[0].type).toBe("ordered-list");
    expect(blocks[1].type).toBe("ordered-list");
    if (blocks[0].type === "ordered-list" && blocks[1].type === "ordered-list") {
      expect(blocks[0].items).toHaveLength(2);
      expect(blocks[1].items).toHaveLength(1);
    }
  });
});
