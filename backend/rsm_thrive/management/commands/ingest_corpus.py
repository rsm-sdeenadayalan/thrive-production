import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from rsm_thrive.services.embeddings import get_embeddings
from rsm_thrive.services.ingest import extract_pdf_text, ingest_document

CATALOG = Path(__file__).resolve().parents[2] / "data" / "catalog" / "courses.json"


class Command(BaseCommand):
    help = "Ingest a corpus directory (PDF/md/txt) and optionally the course catalog."

    def add_arguments(self, parser):
        parser.add_argument("directory", nargs="?", default="")
        parser.add_argument("--catalog", action="store_true")

    def handle(self, *args, **options):
        embeddings = get_embeddings()
        directory = options["directory"]
        if not directory and not options["catalog"]:
            raise CommandError("Give a corpus directory, --catalog, or both.")

        if directory:
            root = Path(directory)
            if not root.is_dir():
                raise CommandError(f"{directory} is not a directory.")
            for path in sorted(root.iterdir()):
                if path.suffix.lower() == ".pdf":
                    text = extract_pdf_text(path)
                    kind, destinations = "syllabus", ["resources", "courses"]
                elif path.suffix.lower() in (".md", ".txt"):
                    text = path.read_text()
                    kind, destinations = "policy", ["resources"]
                else:
                    continue
                doc = ingest_document(f"file:{path.name}", path.stem, kind,
                                      destinations, text, embeddings)
                self.stdout.write(f"ingested file:{path.name} "
                                  f"({doc.chunks.count()} chunks)")

        if options["catalog"]:
            for course in json.loads(CATALOG.read_text()):
                parts = [course.get("description", "")]
                for offering in course.get("offerings", []):
                    parts.append(
                        f"Offered {offering.get('term', '')} "
                        f"with {offering.get('instructor', '')}. "
                        f"{offering.get('format_notes', '')}")
                if course.get("units_note"):
                    parts.append(course["units_note"])
                doc = ingest_document(
                    f"catalog:{course['code']}",
                    f"{course['code']} — {course['title']}",
                    "catalog", ["resources", "courses"],
                    "\n\n".join(p for p in parts if p), embeddings)
                self.stdout.write(f"ingested catalog:{course['code']} "
                                  f"({doc.chunks.count()} chunks)")
