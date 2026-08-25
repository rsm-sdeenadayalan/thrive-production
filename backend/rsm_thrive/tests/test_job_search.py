import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import JobPosting, ResumeVersion
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.jobs.search import profile_of, role_benchmark, search_postings

pytestmark = pytest.mark.django_db


@pytest.fixture
def student():
    return User.objects.create_user("stu")


def _posting(external_id, title, description, skills, active=True):
    [vector] = FakeEmbeddings().embed([f"{title}\n{description}"])
    return JobPosting.objects.create(
        source="fake", external_id=external_id, title=title, company="Acme",
        url=f"https://e.example/{external_id}", description=description,
        skills=skills, embedding=vector, active=active)


def _resume(user, skills=("Python", "SQL")):
    return ResumeVersion.objects.create(
        user=user, label="v1", summary="Analytics student strong in sql and python",
        skills=[{"id": f"s{i}", "name": n, "source": "manual"}
                for i, n in enumerate(skills)],
        courses=[], experience=[], is_current=True)


class TestProfile:
    def test_none_without_current_resume(self, student):
        assert profile_of(student) is None

    def test_profile_lowercases_skills(self, student):
        _resume(student)
        profile = profile_of(student)
        assert profile["skills"] == {"python", "sql"}
        assert "sql" in profile["text"].lower()

    def test_profile_text_carries_organization_and_period(self, student):
        """Tenure and employer are invisible to anything that scores a match
        unless they reach `profile["text"]` -- neither the embedding nor the
        LLM report sees fields the profile text never mentions.
        """
        resume = _resume(student)
        resume.experience = [{
            "id": "exp-1", "title": "Senior Business Analyst",
            "organization": "Acme Corp", "period": "2019-2025",
            "bullets": ["Led analytics for revenue and operations teams"],
        }]
        resume.save()

        text = profile_of(student)["text"]
        assert "Senior Business Analyst" in text
        assert "Acme Corp" in text
        assert "2019-2025" in text

    def test_profile_text_tolerates_missing_organization_or_period(self, student):
        resume = _resume(student)
        resume.experience = [{"id": "exp-1", "title": "Analyst", "bullets": ["Did analysis"]}]
        resume.save()

        text = profile_of(student)["text"]
        assert "Analyst" in text


class TestSearch:
    def test_terms_filter_and_profile_ranking(self, student):
        _resume(student)
        _posting("1", "Data Analyst", "sql python dashboards",
                 ["sql", "python", "data visualization"])
        _posting("2", "Data Analyst", "supply chain optimization",
                 ["supply chain", "optimization"])
        _posting("3", "Chef", "cooking", [])

        result = search_postings(student, "data analyst")
        ids = [r["posting"].external_id for r in result["results"]]
        assert "3" not in ids
        assert ids[0] == "1"  # skill+embedding overlap wins
        top = result["results"][0]
        assert top["matched_skills"] == ["python", "sql"]
        assert top["missing_skills"] == ["data visualization"]
        assert result["profile_available"] is True

    def test_inactive_excluded_and_no_profile_falls_back(self, student):
        _posting("1", "Data Analyst", "sql", ["sql"])
        _posting("2", "Data Analyst old", "sql", ["sql"], active=False)
        result = search_postings(student, "analyst")
        assert len(result["results"]) == 1
        assert result["profile_available"] is False
        assert result["results"][0]["score"] == 0.0

    def test_empty_query_returns_all_active(self, student):
        _posting("1", "A", "x", [])
        _posting("2", "B", "y", [])
        assert len(search_postings(student, "")["results"]) == 2

    def test_title_aware_ranking_surfaces_the_true_role_over_a_high_overlap_impostor(
        self, student,
    ):
        """The reported bug, at the `search_postings` boundary: a genuine
        "Data Analyst" posting with only middling skill overlap must rank
        ABOVE a "Senior Workday Analyst, Payroll" posting whose skills
        happen to overlap heavily with the resume but whose role does not
        match the query at all. See `services/jobs/ranking.py`.
        """
        _resume(student, skills=("Workday", "Payroll", "HRIS", "Python", "SQL"))
        data_analyst = _posting("1", "Data Analyst", "sql dashboards",
                                ["sql", "excel", "tableau"])
        workday_analyst = _posting("2", "Senior Workday Analyst, Payroll",
                                   "manages payroll data systems",
                                   ["workday", "payroll", "hris", "python", "sql"])

        ids = [r["posting"].external_id
              for r in search_postings(student, "data analyst")["results"]]

        assert ids.index(data_analyst.external_id) < ids.index(workday_analyst.external_id)

    def test_region_filters_before_the_candidate_limit(self, student):
        sd = _posting("1", "Data Analyst", "sql", ["sql"])
        sd.location = "San Diego, CA"
        sd.save()
        _posting("2", "Data Analyst", "sql", ["sql"])

        result = search_postings(student, "data analyst", region="san_diego")
        ids = [r["posting"].external_id for r in result["results"]]
        assert ids == [sd.external_id]

    def test_unrecognized_region_is_treated_as_no_filter(self, student):
        _posting("1", "Data Analyst", "sql", ["sql"])
        _posting("2", "Data Analyst", "sql", ["sql"])
        assert len(search_postings(student, "data analyst", region="mars")["results"]) == 2


class TestBenchmark:
    def test_shares_and_ranking(self, student):
        _posting("1", "Data Analyst", "d", ["sql", "python"])
        _posting("2", "Senior Data Analyst", "d", ["sql", "tableau"])
        _posting("3", "Chef", "d", ["cooking"])
        benchmark = role_benchmark("data analyst")
        assert benchmark["sampleSize"] == 2
        top = benchmark["topSkills"][0]
        assert top["name"] == "sql" and top["share"] == 1.0

    def test_empty(self, student):
        assert role_benchmark("") == {"sampleSize": 0, "topSkills": []}
