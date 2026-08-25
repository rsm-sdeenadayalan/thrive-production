import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from rsm_thrive.models import DocumentChunk
from rsm_thrive.services.bot_config import bot_config
from rsm_thrive.services.bots import answer_faq
from rsm_thrive.services.llm import FakeLLM, get_llm
from rsm_thrive.services.retrieval import retrieve

GOLDEN = Path(__file__).resolve().parents[2] / "data" / "evals" / "faq_golden.json"


class Command(BaseCommand):
    help = "Run the golden FAQ set through the bot; fails on any regression."

    def add_arguments(self, parser):
        parser.add_argument("--llm", choices=["fake", "real"], default="fake")
        # The shipped golden set describes the corpus that ships. Unit tests
        # need their own tiny set against their own fixture corpus, or the two
        # become coupled and the golden set can never grow past the fixture.
        parser.add_argument("--golden", default=str(GOLDEN),
                            help="Path to a golden-case JSON file (default: the shipped set).")

    def handle(self, *args, **options):
        if not DocumentChunk.objects.exists():
            raise CommandError("The knowledge table is empty — run ingest_corpus first.")
        cases = json.loads(Path(options["golden"]).read_text())
        config = bot_config("faq")
        failures = 0
        for case in cases:
            if options["llm"] == "fake":
                hits = retrieve(case["question"], "resources",
                                config["top_k"], config["min_similarity"])
                llm = FakeLLM(replies=[" ".join(c.text for c, _ in hits) or "?"])
            else:
                llm = get_llm()
            reply = answer_faq(llm, case["question"], [])
            chunks = ", ".join(str(i) for i in reply.chunk_ids) or "none"
            refused = reply.model_note == "refusal"
            if case["must_refuse"]:
                ok, why = refused, "answered instead of refusing"
            elif refused:
                ok, why = False, "refused instead of answering (no-retrieval?)"
            elif not reply.chunk_ids:
                ok, why = False, "no-retrieval"
            else:
                missing = [kw for kw in case["must_contain"]
                           if kw.lower() not in reply.body.lower()]
                ok, why = not missing, f"missing {missing}"
            if ok:
                self.stdout.write(f"PASS {case['id']} (chunks: {chunks})")
            else:
                failures += 1
                self.stdout.write(f"FAIL {case['id']}: {why} (chunks: {chunks})")
        self.stdout.write(f"{len(cases) - failures}/{len(cases)} passed")
        if failures:
            raise CommandError(f"{failures} eval case(s) failed.")
