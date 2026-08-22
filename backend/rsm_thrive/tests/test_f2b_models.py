import pytest
from django.db import IntegrityError, transaction

from rsm_thrive.models import ResumeVersion
from rsm_thrive.testing import make_course_request, make_skill, make_student

pytestmark = pytest.mark.django_db


def test_only_one_current_resume_version_per_user():
    profile = make_student()
    ResumeVersion.objects.create(user=profile.user, label="v1", summary="s",
                                 is_current=True)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ResumeVersion.objects.create(user=profile.user, label="v2",
                                         summary="s", is_current=True)
    # a different user's current is unaffected
    other = make_student(username="other")
    ResumeVersion.objects.create(user=other.user, label="v1", summary="s",
                                 is_current=True)


def test_request_and_skill_factories():
    profile = make_student()
    req = make_course_request(profile)
    assert req.status == "draft" and req.submitted_at is None
    skill = make_skill(profile, name="SQL")
    assert skill.source == "manual" and skill.course_id is None
    assert profile.tss_connected is False
