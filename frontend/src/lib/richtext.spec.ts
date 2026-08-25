import { describe, expect, it } from "vitest";

import { parseInline, parseRichText, type InlineSpan, type RichBlock } from "$lib/richtext";

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

/** The visible text of a span tree, ignoring which kind carried it. */
function flatten(spans: InlineSpan[]): string {
  return spans
    .map((s) => (s.kind === "bold" || s.kind === "italic" ? flatten(s.spans) : s.text))
    .join("");
}

function textOf(spans: InlineSpan[]): string[] {
  return spans.map((span) =>
    span.kind === "bold" || span.kind === "italic"
      ? `${span.kind}:${flatten(span.spans)}`
      : `${span.kind}:${span.text}`,
  );
}

describe("parseInline", () => {
  it("reads a bold span", () => {
    expect(parseInline("**CSE 251A**")).toEqual([
      { kind: "bold", spans: [{ kind: "text", text: "CSE 251A" }] },
    ]);
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

describe("parseInline emphasis", () => {
  it("reads an underscore-delimited italic span", () => {
    // The exact shape the course recommender writes its help line in. This
    // rendered as literal underscores around the sentence before italics
    // existed, on the first screen of the course recommender.
    expect(textOf(parseInline("_It decides how many quarters the plan has._"))).toEqual([
      "italic:It decides how many quarters the plan has.",
    ]);
  });

  it("reads an asterisk-delimited italic span", () => {
    expect(textOf(parseInline("that is *usually* true"))).toEqual([
      "text:that is ",
      "italic:usually",
      "text: true",
    ]);
  });

  it("leaves underscores inside an identifier alone", () => {
    // `min_similarity` and friends are quoted verbatim by the bots. Naive
    // emphasis scanning turns the run between two underscores into italics and
    // mangles the name being quoted.
    expect(parseInline("set min_similarity and lexical_floor")).toEqual([
      { kind: "text", text: "set min_similarity and lexical_floor" },
    ]);
  });

  it("does not read multiplication as emphasis", () => {
    expect(parseInline("2 * 3 * 4 units")).toEqual([
      { kind: "text", text: "2 * 3 * 4 units" },
    ]);
  });

  it("keeps bold bold rather than reading it as empty italics", () => {
    expect(textOf(parseInline("**CSE 251A**"))).toEqual(["bold:CSE 251A"]);
  });

  it("nests a link inside italics", () => {
    expect(parseInline("_see [WebReg](https://act.ucsd.edu/webreg2)_")).toEqual([
      {
        kind: "italic",
        spans: [
          { kind: "text", text: "see " },
          { kind: "link", text: "WebReg", href: "https://act.ucsd.edu/webreg2" },
        ],
      },
    ]);
  });

  it("treats an unclosed marker as the literal character", () => {
    expect(parseInline("a _ b")).toEqual([{ kind: "text", text: "a _ b" }]);
    expect(parseInline("_unclosed emphasis")).toEqual([
      { kind: "text", text: "_unclosed emphasis" },
    ]);
  });

  it("reads bold inside italics", () => {
    expect(textOf(parseInline("_a **b** c_"))).toEqual(["italic:a b c"]);
  });
});

describe("parseInline links", () => {
  it("reads a link as a link span carrying its href", () => {
    expect(parseInline("[Quarterly Timeline](https://students.ucsd.edu/x.html)")).toEqual([
      {
        kind: "link",
        text: "Quarterly Timeline",
        href: "https://students.ucsd.edu/x.html",
      },
    ]);
  });

  it("keeps parentheses that belong to the page title inside the label", () => {
    // A real corpus title. The label is scanned to its `]` before the href is
    // read, which is the only reason these parens do not truncate it.
    const spans = parseInline(
      "[How to Drop a Class (Graduate Students) — students.ucsd.edu](https://students.ucsd.edu/drop.html)",
    );
    expect(spans).toEqual([
      {
        kind: "link",
        text: "How to Drop a Class (Graduate Students) — students.ucsd.edu",
        href: "https://students.ucsd.edu/drop.html",
      },
    ]);
  });

  it("reads the sources line the backend actually appends", () => {
    // `append_sources` in backend/rsm_thrive/services/bots.py. Documents with
    // no source_url list by bare title, so links and plain text interleave.
    expect(
      textOf(parseInline("Sources: [A](https://a.test), handbook-excerpt, [B](https://b.test)")),
    ).toEqual([
      "text:Sources: ",
      "link:A",
      "text:, handbook-excerpt, ",
      "link:B",
    ]);
  });

  it("leaves a [1] citation as literal text", () => {
    expect(parseInline("as stated [1]")).toEqual([{ kind: "text", text: "as stated [1]" }]);
  });

  it("leaves a bracket with no parenthetical as literal text", () => {
    expect(parseInline("[not a link] really")).toEqual([
      { kind: "text", text: "[not a link] really" },
    ]);
  });

  it("refuses a javascript: href and degrades it to literal text", () => {
    // The body is untrusted LLM output over a corpus this app did not vet.
    // Nothing is swallowed: the student sees exactly what the model wrote.
    expect(parseInline("[click](javascript:alert(1))")).toEqual([
      { kind: "text", text: "[click](javascript:alert(1))" },
    ]);
  });

  it("refuses a data: href", () => {
    expect(parseInline("[x](data:text/html,<script>alert(1)</script>)")).toEqual([
      { kind: "text", text: "[x](data:text/html,<script>alert(1)</script>)" },
    ]);
  });

  it("allows mailto", () => {
    expect(parseInline("[email](mailto:msba@rady.ucsd.edu)")).toEqual([
      { kind: "link", text: "email", href: "mailto:msba@rady.ucsd.edu" },
    ]);
  });

  it("leaves an empty href as literal text", () => {
    expect(parseInline("[title]()")).toEqual([{ kind: "text", text: "[title]()" }]);
  });

  it("reads bold and a link on the same line", () => {
    expect(textOf(parseInline("**Week 9** per [the timeline](https://a.test)"))).toEqual([
      "bold:Week 9",
      "text: per ",
      "link:the timeline",
    ]);
  });

  it("reads a link inside a list item", () => {
    const blocks = parseRichText("- see [the page](https://a.test)");
    expect(blocks[0].type).toBe("unordered-list");
    if (blocks[0].type === "unordered-list") {
      expect(blocks[0].items[0]).toEqual([
        { kind: "text", text: "see " },
        { kind: "link", text: "the page", href: "https://a.test" },
      ]);
    }
  });
});

describe("parseRichText headings", () => {
  it("reads a heading and its level", () => {
    const blocks = parseRichText("## Fall — 14 units");
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("heading");
    if (blocks[0].type === "heading") {
      expect(blocks[0].level).toBe(2);
      expect(textOf(blocks[0].spans)).toEqual(["text:Fall — 14 units"]);
    }
  });

  it("reads every level from # to ######", () => {
    for (let level = 1; level <= 6; level += 1) {
      const blocks = parseRichText(`${"#".repeat(level)} Title`);
      expect(blocks[0].type).toBe("heading");
      if (blocks[0].type === "heading") expect(blocks[0].level).toBe(level);
    }
  });

  it("parses inline spans inside a heading", () => {
    const blocks = parseRichText("## Your **4-unit** elective");
    if (blocks[0].type === "heading") {
      expect(textOf(blocks[0].spans)).toEqual([
        "text:Your ",
        "bold:4-unit",
        "text: elective",
      ]);
    } else {
      throw new Error("expected a heading");
    }
  });

  it("requires the space, so #1 stays text", () => {
    expect(parseRichText("#1 pick")[0].type).toBe("paragraph");
    expect(parseRichText("#")[0].type).toBe("paragraph");
  });

  it("does not treat a mid-sentence hash as a heading", () => {
    expect(parseRichText("slot # 2 is open")[0].type).toBe("paragraph");
  });

  it("ends the heading at the line, keeping what follows separate", () => {
    const blocks = parseRichText("## Fall\nMGTA 452 is core.");
    expect(blocks.map((b) => b.type)).toEqual(["heading", "paragraph"]);
  });

  it("keeps a heading next to a table, as a plan emits them", () => {
    const blocks = parseRichText(
      ["## Fall", "", "| a | b |", "|---|---|", "| 1 | 2 |"].join("\n"),
    );
    expect(blocks.map((b) => b.type)).toEqual(["heading", "table"]);
  });

  it("more than six hashes is not a heading", () => {
    expect(parseRichText("####### too deep")[0].type).toBe("paragraph");
  });
});

describe("parseRichText tables", () => {
  const TABLE = ["| Plan | Units |", "|---|---|", "| 11-Month | 50 |", "| 17-Month | 50 |"].join(
    "\n",
  );

  it("reads a header row, a separator and body rows", () => {
    const blocks = parseRichText(TABLE);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("table");
    if (blocks[0].type === "table") {
      expect(blocks[0].head.map((c) => textOf(c))).toEqual([["text:Plan"], ["text:Units"]]);
      expect(blocks[0].rows).toHaveLength(2);
      expect(blocks[0].rows[0].map((c) => textOf(c))).toEqual([["text:11-Month"], ["text:50"]]);
    }
  });

  it("accepts alignment colons in the separator", () => {
    const blocks = parseRichText(["| a | b |", "|:--|--:|", "| 1 | 2 |"].join("\n"));
    expect(blocks[0].type).toBe("table");
  });

  it("parses inline spans inside cells", () => {
    const blocks = parseRichText(
      ["| Course | Where |", "|---|---|", "| **MGTA 451** | [plan](https://a.test) |"].join("\n"),
    );
    if (blocks[0].type === "table") {
      expect(blocks[0].rows[0][0]).toEqual([
        { kind: "bold", spans: [{ kind: "text", text: "MGTA 451" }] },
      ]);
      expect(blocks[0].rows[0][1]).toEqual([
        { kind: "link", text: "plan", href: "https://a.test" },
      ]);
    } else {
      throw new Error("expected a table");
    }
  });

  it("leaves a pipe-delimited SENTENCE alone when there is no separator row", () => {
    // The reason the separator is required: this is prose, not a table, and
    // restructuring it would silently rewrite what the model said.
    const blocks = parseRichText("| units 8 | 12 | 14 |");
    expect(blocks[0].type).toBe("paragraph");
  });

  it("does not treat a mid-sentence pipe as a table", () => {
    const blocks = parseRichText("Fall is 12 units | Winter is 14");
    expect(blocks[0].type).toBe("paragraph");
  });

  it("ends the table at a blank line and keeps what follows separate", () => {
    const blocks = parseRichText(`${TABLE}\n\nConfirm with MSBA advising.`);
    expect(blocks.map((b) => b.type)).toEqual(["table", "paragraph"]);
  });

  it("ends the table at the first non-row line", () => {
    const blocks = parseRichText(`${TABLE}\nConfirm with MSBA advising.`);
    expect(blocks.map((b) => b.type)).toEqual(["table", "paragraph"]);
  });

  it("reads a header-only table with no body rows", () => {
    const blocks = parseRichText(["| a | b |", "|---|---|"].join("\n"));
    expect(blocks[0].type).toBe("table");
    if (blocks[0].type === "table") expect(blocks[0].rows).toEqual([]);
  });

  it("keeps a table that is the last thing in a reply", () => {
    const blocks = parseRichText(`Here it is:\n\n${TABLE}`);
    expect(blocks.map((b) => b.type)).toEqual(["paragraph", "table"]);
  });

  it("does not crash on a separator with no header above it", () => {
    const blocks = parseRichText("|---|---|");
    expect(blocks[0].type).toBe("paragraph");
  });
});

describe("parseInline nesting", () => {
  it("parses a link wrapped in bold", () => {
    // What the model actually writes when it emphasises a link. Before bold
    // nested, this rendered as the literal string in the bubble.
    expect(parseInline("use **[WebReg](https://act.ucsd.edu/webreg2)** to enroll")).toEqual([
      { kind: "text", text: "use " },
      {
        kind: "bold",
        spans: [{ kind: "link", text: "WebReg", href: "https://act.ucsd.edu/webreg2" }],
      },
      { kind: "text", text: " to enroll" },
    ]);
  });

  it("parses bold around a link plus trailing text", () => {
    expect(textOf(parseInline("**see [the plan](https://a.test) now**"))).toEqual([
      "bold:see the plan now",
    ]);
  });

  it("parses code inside bold", () => {
    expect(parseInline("**`npm test`**")).toEqual([
      { kind: "bold", spans: [{ kind: "code", text: "npm test" }] },
    ]);
  });

  it("keeps an unclosed bold literal rather than swallowing the rest", () => {
    expect(parseInline("**not closed")).toEqual([{ kind: "text", text: "**not closed" }]);
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
            { kind: "bold", spans: [{ kind: "text", text: "Heads up:" }] },
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
