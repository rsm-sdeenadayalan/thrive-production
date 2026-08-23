from django.core.management.base import BaseCommand

from rsm_thrive.services.jobs.ingest import ingest_from
from rsm_thrive.services.jobs.sources import configured_sources


class Command(BaseCommand):
    help = "Fetch, normalize, and upsert job postings from all configured sources."

    def handle(self, *args, **options):
        result = ingest_from(configured_sources())
        self.stdout.write(
            f"ingested {result['ingested']} postings, "
            f"deactivated {result['deactivated']} stale"
            + (f", failed: {', '.join(result['failed_sources'])}"
               if result["failed_sources"] else ""))
