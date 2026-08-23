import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.ingest import ingest_document

pytestmark = pytest.mark.django_db

HANDBOOK = """# Dropping a course

Students may drop a course before the end of week two without a W. After
week two, a drop requires approval from the program office.

# Laptop loans

Laptop loans are handled by the Rady tech desk in room 2W108.
"""


def test_eval_passes_on_seeded_corpus(capsys):
    ingest_document("test:handbook", "MSBA Handbook", "policy", ["resources"],
                    HANDBOOK, FakeEmbeddings())
    call_command("eval_bots", "--llm", "fake")
    out = capsys.readouterr().out
    assert "PASS drop-deadline" in out
    assert "PASS off-topic-refusal" in out
    assert "FAIL" not in out


def test_eval_fails_loudly_on_empty_corpus():
    with pytest.raises(CommandError):
        call_command("eval_bots", "--llm", "fake")
