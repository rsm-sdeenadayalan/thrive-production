import pytest
from django.db import IntegrityError

from rsm_thrive.models import JobPosting
from rsm_thrive.services.jobs.skills import extract_skills, load_skills_vocab

pytestmark = pytest.mark.django_db


class TestVocab:
    def test_loads_with_canonical_keys(self):
        vocab = load_skills_vocab()
        assert "python" in vocab and isinstance(vocab["sql"], list)


class TestExtractSkills:
    def test_matches_canonical_and_alias_case_insensitive(self):
        text = "We use Python, PostgreSQL and PyTorch daily."
        skills = extract_skills(text)
        assert "python" in skills
        assert "sql" in skills           # via postgresql alias
        assert "deep learning" in skills  # via pytorch alias

    def test_whole_word_only(self):
        # "rstudio" must not match the skill "r"; "sparkle" not "spark"
        assert "r" not in extract_skills("we love rstudio and sparkle")
        assert "spark" not in extract_skills("sparkle")

    def test_multiword_alias(self):
        assert "nlp" in extract_skills("natural language processing pipelines")

    def test_sorted_and_deduped(self):
        skills = extract_skills("SQL sql PostgreSQL python")
        assert skills == sorted(set(skills))
        assert skills.count("sql") == 1


class TestModels:
    def test_posting_dedup_constraint(self):
        JobPosting.objects.create(source="greenhouse", external_id="1",
                                  title="Analyst", company="Acme",
                                  url="https://a.example/1", description="d")
        with pytest.raises(IntegrityError):
            JobPosting.objects.create(source="greenhouse", external_id="1",
                                      title="Other", company="Acme",
                                      url="https://a.example/1", description="d")
