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
 * (bold, code, plain text) plus inline links.
 *
 * Links earn their place because the backend produces them: `append_sources`
 * ends every retrieved answer with `Sources: [title](url), ...` so a student
 * about to act on a deadline can open the page that states it. Parsed here,
 * that is a real `<a>`; unparsed, it was the literal string
 * `[Quarterly Timeline](https://...)` sitting in the bubble, which is the one
 * thing worse than no link at all.
 *
 * Tables are handled for the same reason links are: the model produces them.
 * Once the MSBA plans of study were in the corpus, "compare the 11-month and
 * 17-month unit loads by quarter" started coming back as a real Markdown
 * table, and unparsed that rendered as a wall of `|---|---|` in the bubble.
 * A table is recognised only when a header row is followed by a `|---|`
 * separator, so a sentence that merely contains a pipe stays a sentence.
 *
 * Headings earn their place for the same reason links and tables did: the
 * replies produce them. A plan of study is delivered as "## Fall - 14 units"
 * per quarter, and the guided review adds "## Your 4-unit elective: ...". Left
 * unparsed those rendered as 28 literal `#` characters on a single page.
 *
 * Images are still not Markdown this app's replies produce, so they remain
 * intentionally unparsed -- which is honest and never crashes, rather than a
 * half implementation of syntax nobody asked for.
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
  // Bold holds SPANS, not a string. `**[WebReg](https://act.ucsd.edu/webreg2)**`
  // is what the model actually writes when it emphasises a link, and a flat
  // `text` field made that render as the literal characters -- the bold scan
  // matched first and swallowed the link whole. Only bold nests: code is
  // literal by definition, and a link's label is plain text.
  | { kind: "bold"; spans: InlineSpan[] }
  // Italic nests for the same reason bold does, and it is not decorative here:
  // the course recommender writes its help line as `_It decides how many
  // quarters the plan has._`, which rendered as literal underscores around the
  // sentence until this existed.
  | { kind: "italic"; spans: InlineSpan[] }
  | { kind: "code"; text: string }
  | { kind: "link"; text: string; href: string };

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
  | { type: "blockquote"; lines: InlineSpan[][] }
  | { type: "table"; head: InlineSpan[][]; rows: InlineSpan[][][] }
  | { type: "heading"; level: number; spans: InlineSpan[] };

type LineKind = "paragraph" | "ordered-list" | "unordered-list" | "blockquote";

/**
 * Schemes an LLM reply is allowed to turn into a real `href`.
 *
 * The rest of this module is injection-proof by construction -- it returns
 * data and the component builds elements, so there is no markup to smuggle a
 * tag through. An `href` is the one exception: it is attacker-controlled
 * STRING that the browser then treats as an instruction, so
 * `[click me](javascript:fetch('/api/thrive/me').then(...))` would execute in
 * the student's authenticated session if this allowlist were not here.
 *
 * A rejected scheme is not dropped -- `linkAt` degrades it to literal text, so
 * the student still sees exactly what the model wrote and nothing is silently
 * swallowed.
 */
const SAFE_SCHEME = /^(?:https?:\/\/|mailto:)/i;

const ORDERED_MARKER = /^\d+\.\s+/;
const UNORDERED_MARKER = /^[-*]\s+/;
const BLOCKQUOTE_MARKER = /^>\s?/;

// `#` through `######`, and the space is required: "#1 pick" is not a heading,
// and neither is a bare "#".
const HEADING_MARKER = /^(#{1,6})\s+(.*)$/;

/**
 * A table row: starts and ends with a pipe.
 *
 * Deliberately strict about the OUTER pipes. Markdown permits a table without
 * them, but so does prose -- "units 8 | 12 | 14" is a sentence, and treating
 * it as a table would silently restructure a reply the model wrote as text.
 * Requiring the outer pipes plus a separator row (below) means a table is
 * recognised only when the model clearly meant one.
 */
const TABLE_ROW = /^\s*\|.*\|\s*$/;

/** The `|---|:--:|` line under a header row. Alignment colons are allowed and
 *  then ignored -- this renders left-aligned regardless. */
const TABLE_SEPARATOR = /^\s*\|(?:\s*:?-+:?\s*\|)+\s*$/;

function tableCells(line: string): InlineSpan[][] {
  const trimmed = line.trim();
  // Drop the empty strings the leading and trailing pipes produce.
  const inner = trimmed.slice(1, trimmed.length - 1);
  return inner.split("|").map((cell) => parseInline(cell.trim()));
}

/**
 * Read a table starting at `start`, or null if there is not one there.
 *
 * A header row alone is not a table -- the separator is what distinguishes a
 * real table from a line that happens to be pipe-delimited. Rows are taken
 * until the first line that is not a row, so a table ends at a blank line or
 * at prose without needing a terminator.
 */
function tableAt(
  lines: string[],
  start: number,
): { block: RichBlock; next: number } | null {
  if (!TABLE_ROW.test(lines[start])) return null;
  if (start + 1 >= lines.length) return null;
  if (!TABLE_SEPARATOR.test(lines[start + 1])) return null;

  const head = tableCells(lines[start]);
  const rows: InlineSpan[][][] = [];
  let i = start + 2;
  while (i < lines.length && TABLE_ROW.test(lines[i])) {
    rows.push(tableCells(lines[i]));
    i += 1;
  }
  return { block: { type: "table", head, rows }, next: i };
}

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
 * `[1]`-style citations are never special-cased and still fall through into a
 * plain "text" span exactly as written: link parsing requires a `](` pair, and
 * a citation has no parenthetical after its bracket, so the two syntaxes
 * cannot be confused for one another.
 */
/**
 * Read a `[text](href)` link starting at `start`, or null if there is not one.
 *
 * Deliberately not a regex. The titles this parses are page titles, and they
 * contain their own parentheses -- "How to Drop a Class (Graduate Students) —
 * students.ucsd.edu" is a real one. A regex like `\[([^\]]+)\]\(([^)]+)\)`
 * reads correctly only because the LABEL is scanned to its `]` first; writing
 * it as a scan makes that ordering explicit instead of load-bearing and
 * accidental.
 *
 * An empty label or an empty href returns null rather than an `<a>` with
 * nothing to click or nowhere to go.
 */
function linkAt(
  line: string,
  start: number,
): { text: string; href: string; end: number } | null {
  const labelEnd = line.indexOf("]", start + 1);
  if (labelEnd === -1) return null;
  if (line[labelEnd + 1] !== "(") return null;

  const hrefEnd = line.indexOf(")", labelEnd + 2);
  if (hrefEnd === -1) return null;

  const text = line.slice(start + 1, labelEnd).trim();
  const href = line.slice(labelEnd + 2, hrefEnd).trim();
  if (!text || !href) return null;
  if (!SAFE_SCHEME.test(href)) return null;

  return { text, href, end: hrefEnd + 1 };
}

const ALPHANUMERIC = /[\p{L}\p{N}]/u;

/**
 * Find the closer for a single-character emphasis marker, or -1.
 *
 * Emphasis is the one inline marker that cannot be matched by "find the next
 * one of these", because both characters it uses are ordinary punctuation in
 * text this app actually renders:
 *
 *   - `_` appears inside identifiers the bots quote — `min_similarity`,
 *     `resume_version`, `skill_python` — and a naive scan turns the run between
 *     two of them into italics, mangling the very name being quoted.
 *   - `*` appears as multiplication and as a literal bullet — "2 * 3 * 4".
 *
 * So this applies CommonMark's flanking rules, which is what distinguishes
 * emphasis from punctuation in both cases:
 *
 *   - an OPENER may not be followed by whitespace ("2 * 3" cannot open), and
 *   - a CLOSER may not be preceded by whitespace, and
 *   - for `_` only, neither side may sit between two word characters
 *     (`min_similarity` cannot open or close; CommonMark allows intraword `*`
 *     but not intraword `_`, for exactly this reason).
 *
 * An unclosed marker returns -1 and is then rendered as the literal character
 * it is, the same way `**` and `` ` `` already behave here.
 */
function emphasisCloser(line: string, start: number, marker: string): number {
  const after = line[start + 1];
  if (after === undefined || /\s/.test(after)) return -1;
  if (marker === "_") {
    const before = line[start - 1];
    if (before !== undefined && ALPHANUMERIC.test(before)) return -1;
  }

  for (let j = start + 1; j < line.length; j += 1) {
    if (line[j] !== marker) continue;
    const preceding = line[j - 1];
    if (preceding !== undefined && /\s/.test(preceding)) continue;
    if (marker === "_") {
      const following = line[j + 1];
      if (following !== undefined && ALPHANUMERIC.test(following)) continue;
    }
    // An empty span (`__`, `**` handled elsewhere) is not emphasis.
    if (j === start + 1) continue;
    return j;
  }
  return -1;
}

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
    if (line[i] === "[") {
      const link = linkAt(line, i);
      if (link) {
        flushText();
        spans.push({ kind: "link", text: link.text, href: link.href });
        i = link.end;
        continue;
      }
      // Not a link (a `[1]` citation, an unclosed bracket, or a scheme this
      // app will not hand the browser): the `[` is literal.
      buffer += "[";
      i += 1;
      continue;
    }

    if (line.startsWith("**", i)) {
      const close = line.indexOf("**", i + 2);
      if (close !== -1) {
        flushText();
        // Recurse: bold content is itself inline markup, so a link, a code
        // span, or plain text inside it all parse normally.
        spans.push({ kind: "bold", spans: parseInline(line.slice(i + 2, close)) });
        i = close + 2;
        continue;
      }
      // Unclosed: the marker is literal, not a formatting instruction.
      buffer += "**";
      i += 2;
      continue;
    }

    // AFTER the `**` branch above, which is what keeps `**bold**` from being
    // read as an empty italic followed by a stray asterisk.
    if (line[i] === "_" || line[i] === "*") {
      const close = emphasisCloser(line, i, line[i]);
      if (close !== -1) {
        flushText();
        spans.push({ kind: "italic", spans: parseInline(line.slice(i + 1, close)) });
        i = close + 1;
        continue;
      }
      buffer += line[i];
      i += 1;
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

  // An index loop rather than for-of: a table needs to look at the NEXT line
  // (its separator) before it can be recognised at all, and then consumes
  // several lines at once.
  let index = 0;
  while (index < lines.length) {
    const rawLine = lines[index];

    if (rawLine.trim() === "") {
      flush();
      index += 1;
      continue;
    }

    const table = tableAt(lines, index);
    if (table) {
      flush();
      blocks.push(table.block);
      index = table.next;
      continue;
    }

    const heading = HEADING_MARKER.exec(rawLine);
    if (heading) {
      flush();
      blocks.push({
        type: "heading",
        level: heading[1].length,
        spans: parseInline(heading[2].trim()),
      });
      index += 1;
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
    index += 1;
  }
  flush();

  return blocks;
}
