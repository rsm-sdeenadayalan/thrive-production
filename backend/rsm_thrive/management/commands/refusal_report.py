"""What students asked that we could not answer.

The content backlog, written by the people who need the material. Every
refusal is a question a student actually had, in their own words, that the
corpus did not cover — which is a far better prioritisation signal than a
guess about what to crawl next.

Questions the bot correctly declined (out of scope) are excluded unless
`--all`. Filing "what's the weather" as content to write buries the real
backlog under noise.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from rsm_thrive.models import ChatTurnLog


class Command(BaseCommand):
    help = "List the questions the bots refused, most-asked first."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=0,
                            help="Only the last N days (default: all).")
        parser.add_argument("--bot", default="", help="resources | courses | career")
        parser.add_argument("--all", action="store_true",
                            help="Include correctly out-of-scope refusals.")
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        rows = ChatTurnLog.objects.filter(refused=True)
        if options["days"]:
            rows = rows.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=options["days"]))
        if options["bot"]:
            rows = rows.filter(bot=options["bot"])
        if not options["all"]:
            rows = rows.exclude(route="out-of-scope")

        grouped = {}
        for turn in rows:
            key = " ".join((turn.question or "").lower().split())
            if not key:
                continue
            entry = grouped.setdefault(
                key, {"question": turn.question.strip(), "asked": 0, "bots": set()})
            entry["asked"] += 1
            entry["bots"].add(turn.bot)

        backlog = sorted(grouped.values(),
                         key=lambda row: (-row["asked"], row["question"]))
        if not backlog:
            self.stdout.write("No refusals logged for that window.")
            return
        for row in backlog[:options["limit"]]:
            self.stdout.write(
                f"{row['asked']:>4}x  [{','.join(sorted(row['bots']))}]  {row['question']}")
        self.stdout.write(f"\n{len(backlog)} distinct question(s), "
                          f"{sum(r['asked'] for r in backlog)} refusal(s).")
