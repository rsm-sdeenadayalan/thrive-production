"""Turn every thumbs-down into a golden case.

`eval_bots` ships nine hand-written cases. Nine cases written by the people who
built the bot is a smoke test, not a regression net — they encode the failures
we already thought of, which are the ones already fixed. A fortnight of testers
produces the other kind: the questions nobody predicted, each one already
labelled by a person who read the answer and said it was wrong.

## What this can and cannot produce

A thumbs-down states that an answer was bad. It does not state what the right
answer was, and no amount of processing here can invent one — so a case leaves
this command as `needs_expectation`, carrying the question, the answer that was
rated bad, the chunks behind it and whatever the tester typed. Somebody then
writes the `must_contain` (or sets `must_refuse`) and flips it to `ready`.

That intermediate state is the honest one. The alternative — asserting the
reply must simply CHANGE — passes the moment the model rewords itself and tells
you nothing about whether it got better.

## Re-running is safe

Cases already in the output file keep their curation. This only ever adds rows
and refreshes the evidence attached to an uncurated one; it never overwrites a
`must_contain` a human wrote.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from rsm_thrive.models import DocumentChunk, TurnFeedback

DEFAULT_OUT = (Path(__file__).resolve().parents[2] / "data" / "evals"
               / "from_feedback.json")

NEEDS_EXPECTATION = "needs_expectation"


class Command(BaseCommand):
    help = "Write the thumbs-down turns out as golden eval cases."

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(DEFAULT_OUT),
                            help="Case file to merge into (default: data/evals/from_feedback.json).")
        parser.add_argument("--days", type=int, default=0,
                            help="Only feedback from the last N days (default: all).")
        parser.add_argument("--include-up", action="store_true",
                            help="Also export thumbs-UP turns, as regression anchors.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Print what would be written and change nothing.")

    def handle(self, *args, **options):
        rows = (TurnFeedback.objects
                .select_related("turn", "turn__message")
                .order_by("turn_id"))
        if not options["include_up"]:
            rows = rows.filter(rating="down")
        if options["days"]:
            rows = rows.filter(
                updated_at__gte=timezone.now() - timezone.timedelta(days=options["days"]))
        rows = list(rows)

        out_path = Path(options["out"])
        existing = []
        if out_path.exists():
            existing = json.loads(out_path.read_text())
        by_id = {case["id"]: case for case in existing}

        titles = self._chunk_titles(rows)
        added, refreshed = 0, 0
        for feedback in rows:
            turn = feedback.turn
            case_id = f"fb-{turn.pk}"
            evidence = {
                "ratedAt": feedback.updated_at.isoformat(),
                "rating": feedback.rating,
                "note": feedback.note,
                "bot": turn.bot,
                "route": turn.route,
                "modelNote": turn.model_note,
                "refused": turn.refused,
                "durationMs": turn.duration_ms,
                "reply": turn.message.body,
                "chunkIds": list(turn.chunk_ids or []),
                "chunkTitles": [titles.get(cid, f"(chunk {cid} no longer exists)")
                                for cid in (turn.chunk_ids or [])],
            }
            case = by_id.get(case_id)
            if case is None:
                by_id[case_id] = {
                    "id": case_id,
                    "question": turn.question,
                    "bot": turn.bot,
                    "must_contain": [],
                    "must_not_contain": [],
                    "must_refuse": False,
                    "status": NEEDS_EXPECTATION,
                    "reported": evidence,
                }
                added += 1
                continue
            # Curation is a human's; evidence is ours. Refreshing the evidence
            # on a case somebody has already written an expectation for would
            # be pointless (the expectation is what runs) and confusing, so
            # only uncurated cases are touched.
            if case.get("status") == NEEDS_EXPECTATION:
                case["reported"] = evidence
                case["question"] = turn.question
                refreshed += 1

        cases = sorted(by_id.values(), key=lambda case: case["id"])
        pending = sum(1 for case in cases if case.get("status") == NEEDS_EXPECTATION)
        self.stdout.write(
            f"{len(rows)} rated turn(s) -> {len(cases)} case(s): "
            f"{added} new, {refreshed} refreshed, {pending} awaiting an expectation.")
        for case in cases:
            if case.get("status") != NEEDS_EXPECTATION:
                continue
            note = (case["reported"].get("note") or "").strip()
            self.stdout.write(f"  {case['id']}  {case['question'][:70]!r}"
                              + (f"  — {note[:60]!r}" if note else "  — (no note)"))
        if options["dry_run"]:
            self.stdout.write("dry run: nothing written")
            return
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(cases, indent=2) + "\n")
        self.stdout.write(self.style.SUCCESS(f"wrote {out_path}"))

    def _chunk_titles(self, rows):
        wanted = {cid for feedback in rows
                  for cid in (feedback.turn.chunk_ids or [])
                  if isinstance(cid, int)}
        if not wanted:
            return {}
        return {chunk.pk: (f"{chunk.document.title} — {chunk.heading}"
                           if chunk.heading else chunk.document.title)
                for chunk in DocumentChunk.objects.filter(pk__in=wanted)
                                                  .select_related("document")}
