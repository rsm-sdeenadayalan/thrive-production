"""Rebuild courses.json from the per-course markdown in corpus/syllabi/.

The markdown is the SOURCE. One file per course, holding both halves of what we
know: a frontmatter block of facts, and the syllabus itself underneath. Both
bots read the same file -- retrieval reads the body, the planner reads the
frontmatter through this command -- so a course cannot be describable and
unschedulable, or scheduled and undescribed.

`courses.json` remains, as a BUILD ARTIFACT rather than something anyone edits.
It exists because the planner does arithmetic: quarters have unit floors and
ceilings and a plan must sum to 50, and summing requires `units` to be a number
in a list, not a sentence in a document. Retrieval cannot do arithmetic and
prose cannot be summed, which is the whole reason the two forms coexist.

Frontmatter is written in YAML flow style, which is also valid JSON, so every
value parses with `json.loads` and no YAML dependency is needed.

    uv run python manage.py build_catalog          # rewrite courses.json
    uv run python manage.py build_catalog --check  # fail if it is out of date
"""
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

SYLLABI = Path(__file__).resolve().parents[3] / "rsm_thrive/data/corpus/syllabi"
CATALOG = Path(__file__).resolve().parents[3] / "rsm_thrive/data/catalog/courses.json"

# The order courses.json has always used. Kept so a rebuild produces a readable
# diff against the hand-written file rather than a reshuffle of every line.
FIELDS = ("id", "code", "title", "units", "is_core", "offerings", "description",
          "topics", "skills", "tools", "prerequisites", "workload",
          "workload_basis", "career_tags", "technical_level", "grading",
          "notes", "department", "units_note", "also_known_as",
          "also_known_as_note")

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def frontmatter(text):
    """The frontmatter block as a dict. Every value is JSON."""
    match = _FRONTMATTER.match(text)
    if not match:
        return None
    out = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, raw = line.partition(":")
        try:
            out[key.strip()] = json.loads(raw.strip())
        except json.JSONDecodeError:
            out[key.strip()] = raw.strip().strip('"')
    return out


def body_of(text):
    return _FRONTMATTER.sub("", text, count=1)


def description_from(text):
    """The "What this course covers" prose, for the catalog's `description`."""
    match = re.search(r"## What this course covers\n\n(.*?)(?=\n## |\Z)", text, re.S)
    return " ".join(match.group(1).split()) if match else ""


def course_from(path):
    """One catalog row, or None when the file is not schedulable.

    A course with no unit count anywhere in the material stays out of the
    catalog and lives only in the corpus. That is the grounding rule applied to
    ourselves: the planner may not schedule what it cannot count, and inventing
    "probably 4 units" is exactly the kind of assertion this codebase forbids.
    """
    text = path.read_text()
    meta = frontmatter(text)
    if not meta or not meta.get("schedulable") or not meta.get("units"):
        return None
    row = {
        "id": meta.get("id") or meta["code"],
        "code": meta["code"],
        "title": meta.get("title") or meta["code"],
        "units": meta["units"],
        "is_core": bool(meta.get("is_core")),
        "offerings": meta.get("offerings") or [],
        "description": description_from(body_of(text)),
        "topics": meta.get("topics") or [],
        "skills": meta.get("skills") or [],
        "tools": meta.get("tools") or [],
        "prerequisites": meta.get("prerequisites"),
        "workload": meta.get("workload") or "moderate",
        "workload_basis": meta.get("workload_basis") or "",
        "career_tags": meta.get("career_tags") or [],
        "technical_level": meta.get("technical_level") or 3,
        "grading": meta.get("grading") or "",
        "notes": meta.get("notes") or "",
        "department": meta.get("department") or meta["code"].split()[0],
    }
    for optional in ("units_note", "also_known_as", "also_known_as_note"):
        if meta.get(optional):
            row[optional] = meta[optional]
    return {k: row[k] for k in FIELDS if k in row}


def build():
    files = [p for p in sorted(SYLLABI.glob("*.md"))
             if not re.match(r".* \d+$", p.stem)]  # iCloud conflict copies
    rows = [c for c in (course_from(p) for p in files) if c]
    rows.sort(key=lambda c: (not c["is_core"], c["code"]))
    return rows


class Command(BaseCommand):
    help = "Rebuild data/catalog/courses.json from data/corpus/syllabi/*.md"

    def add_arguments(self, parser):
        parser.add_argument(
            "--check", action="store_true",
            help="Exit non-zero if courses.json differs from the markdown, "
                 "without writing. For CI: the two must not drift.")

    def handle(self, *args, **options):
        rows = build()
        rendered = json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
        if options["check"]:
            if CATALOG.read_text() != rendered:
                raise CommandError(
                    "courses.json is out of date with corpus/syllabi/*.md — "
                    "run `python manage.py build_catalog`.")
            self.stdout.write(self.style.SUCCESS(f"courses.json matches ({len(rows)} courses)"))
            return
        CATALOG.write_text(rendered)
        core = sum(1 for c in rows if c["is_core"])
        self.stdout.write(self.style.SUCCESS(
            f"wrote {len(rows)} courses ({core} core, {len(rows) - core} electives) "
            f"to {CATALOG.name}"))
