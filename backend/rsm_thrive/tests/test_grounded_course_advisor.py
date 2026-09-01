from rsm_thrive.services.grounded_course_advisor.advisor import (
    _matches,
    is_industry_course_question,
)


def test_aerospace_course_question_is_routed_to_industry_segment():
    assert is_industry_course_question(
        "What electives can I take to assist in the aerospace field in the MSBA program?"
    )


def test_any_named_industry_is_routed_to_the_same_segment():
    assert is_industry_course_question(
        "Which electives would help me work in healthcare analytics?"
    )


def test_non_course_aerospace_question_is_not_routed():
    assert not is_industry_course_question("What skills are used in aerospace?")


def test_generic_catalog_question_stays_local():
    assert not is_industry_course_question("What electives are offered in the MSBA?")


def test_only_electives_with_two_catalog_matches_are_returned():
    catalog = [
        {
            "code": "MGTA 1", "title": "Analytics", "units": 4,
            "is_core": False, "skills": ["predictive modeling"],
            "topics": ["optimization"], "tools": [],
        },
        {
            "code": "MGTA 2", "title": "One Match", "units": 4,
            "is_core": False, "skills": ["optimization"],
            "topics": [], "tools": [],
        },
        {
            "code": "MGTA 3", "title": "Core Match", "units": 4,
            "is_core": True, "skills": ["predictive modeling"],
            "topics": ["optimization"], "tools": [],
        },
    ]
    rows = _matches(
        {"skills": ["predictive modeling"], "tools": [], "topics": ["optimization"]},
        catalog,
    )
    assert [row["course"]["code"] for row in rows] == ["MGTA 1"]
