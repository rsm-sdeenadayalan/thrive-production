/**
 * A parser for the tiny Markdown subset a chat reply actually uses.
 *
 * ## Why a parser and not a Markdown library
 *
 * No new dependency is allowed, and every general-purpose Markdown renderer
 * answers "how do I get raw HTML out of this" sooner or later -- which is
 * precisely the question this file must never be asked. `parseRichText`
 * returns data, not markup: a tree of plain objects that a component walks
 * with `{#each}` and real Svelte elements. There is no string of HTML
 * anywhere in this module, so there is nothing for `{@html}` to be tempted
 * by and nothing a prompt-injected corpus chunk can smuggle through as a
 * tag.
 *
 * ## The subset, deliberately small
 *
 * A reply looks like a numbered course list, a bold course title, an inline
 * code snippet, a `[1]` citation, and an occasional "> " warning line. That
 * is the entire vocabulary handled here: paragraphs, ordered lists (`1.`),
 * unordered lists (`-` / `*`), blockquotes (`> `), and three inline spans
 * (bold, code, plain text). Links, headings, tables and images are not
 * Markdown this app's replies produce today, so they are intentionally left
 * unparsed -- a heading's `#` or a table's `|` renders as the literal
 * characters it is, which is honest and never crashes, rather than a half
 * implementation of syntax nobody asked for.
 *
 * ## Never crash, never drop content
 *
 * An LLM reply is untrusted text with no obligation to be well-formed
 * Markdown. `**bold` with no closing `**` is not an error here -- the
 * marker degrades to two literal asterisks and parsing continues. There is
 * no code path that throws and no code path that swallows a character the
 * model actually sent.
 */

// ---------------------------------------------------------------------------
// The inline layer -- what a line of text is made of
// ---------------------------------------------------------------------------

export type InlineSpan =
  | { kind: "text"; text: string }
  | { kind: "bold"; text: string }
  | { kind: "code"; text: string };

// ---------------------------------------------------------------------------
// The block layer -- what a message is made of
// ---------------------------------------------------------------------------

/**
 * One paragraph or blockquote line is `InlineSpan[]`, not a single string,
 * because a line already carries its own bold/code spans. A whole paragraph
 * or blockquote is `InlineSpan[][]` -- one entry per source line -- so a
 * single `\n` inside it can be rendered as an explicit break without the
 * component re-deriving line boundaries from a joined string.
 */
export type RichBlock =
  | { type: "paragraph"; lines: InlineSpan[][] }
  | { type: "ordered-list"; items: InlineSpan[][] }
  | { type: "unordered-list"; items: InlineSpan[][] }
  | { type: "blockquote"; lines: InlineSpan[][] };

type LineKind = "paragraph" | "ordered-list" | "unordered-list" | "blockquote";

const ORDERED_MARKER = /^\d+\.\s+/;
const UNORDERED_MARKER = /^[-*]\s+/;
const BLOCKQUOTE_MARKER = /^>\s?/;

function classifyLine(line: string): LineKind {
  if (ORDERED_MARKER.test(line)) return "ordered-list";
  if (UNORDERED_MARKER.test(line)) return "unordered-list";
  if (BLOCKQUOTE_MARKER.test(line)) return "blockquote";
  return "paragraph";
}

function stripMarker(line: string, kind: LineKind): string {
  switch (kind) {
    case "ordered-list":
      return line.replace(ORDERED_MARKER, "");
    case "unordered-list":
      return line.replace(UNORDERED_MARKER, "");
    case "blockquote":
      return line.replace(BLOCKQUOTE_MARKER, "");
    case "paragraph":
      return line;
  }
}

/**
 * Turn one line's text into inline spans.
 *
 * A single left-to-right scan, hunting for the next `**` or `` ` ``. Each
 * marker is provisional until its matching closer is actually found later
 * on the SAME line -- Markdown that never closes a marker is common in a
 * streamed or truncated reply, and "no closer found" is not a parse error,
 * it is the marker read back as the two (or one) literal characters it is.
 *
 * `[1]`-style citations are never special-cased, so they always fall
 * through into a plain "text" span exactly as written.
 */
export function parseInline(line: string): InlineSpan[] {
  const spans: InlineSpan[] = [];
  let buffer = "";
  let i = 0;

  const flushText = () => {
    if (buffer.length > 0) {
      spans.push({ kind: "text", text: buffer });
      buffer = "";
    }
  };

  while (i < line.length) {
    if (line.startsWith("**", i)) {
      const close = line.indexOf("**", i + 2);
      if (close !== -1) {
        flushText();
        spans.push({ kind: "bold", text: line.slice(i + 2, close) });
        i = close + 2;
        continue;
      }
      // Unclosed: the marker is literal, not a formatting instruction.
      buffer += "**";
      i += 2;
      continue;
    }

    if (line[i] === "`") {
      const close = line.indexOf("`", i + 1);
      if (close !== -1) {
        flushText();
        spans.push({ kind: "code", text: line.slice(i + 1, close) });
        i = close + 1;
        continue;
      }
      buffer += "`";
      i += 1;
      continue;
    }

    buffer += line[i];
    i += 1;
  }

  flushText();
  return spans;
}

/**
 * Parse a full reply into a sequence of blocks.
 *
 * Blank lines are hard block boundaries -- they end whatever run is in
 * progress, list included, which is what stops one blank line from fusing
 * two unrelated numbered lists into one. Inside a run, consecutive lines
 * of the SAME kind merge into one block; a kind change (paragraph line
 * followed by a `1.` line, no blank line between) starts a new block
 * rather than being forced into the old one.
 *
 * List numbering is never read for its value -- only for "is this a list
 * line at all" -- because the output is a real `<ol>`, and a `<ol>` numbers
 * itself. A model that prints `1.` five times in a row still renders as
 * 1, 2, 3, 4, 5.
 */
export function parseRichText(text: string): RichBlock[] {
  const lines = text.replace(/\r\n/g, "\n").split("\n");

  const blocks: RichBlock[] = [];
  let current: { kind: LineKind; raw: string[] } | null = null;

  const flush = () => {
    if (!current) return;

    const parsedLines = current.raw.map(parseInline);
    switch (current.kind) {
      case "ordered-list":
        blocks.push({ type: "ordered-list", items: parsedLines });
        break;
      case "unordered-list":
        blocks.push({ type: "unordered-list", items: parsedLines });
        break;
      case "blockquote":
        blocks.push({ type: "blockquote", lines: parsedLines });
        break;
      case "paragraph":
        blocks.push({ type: "paragraph", lines: parsedLines });
        break;
    }
    current = null;
  };

  for (const rawLine of lines) {
    if (rawLine.trim() === "") {
      flush();
      continue;
    }

    const kind = classifyLine(rawLine);
    const content = stripMarker(rawLine, kind);

    if (current && current.kind === kind) {
      current.raw.push(content);
    } else {
      flush();
      current = { kind, raw: [content] };
    }
  }
  flush();

  return blocks;
}
