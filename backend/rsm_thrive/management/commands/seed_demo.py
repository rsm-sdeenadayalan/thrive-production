import datetime as dt

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from rsm_thrive import testing as t
from rsm_thrive.services.resume import generate_version


class Command(BaseCommand):
    help = "Seed an idempotent demo world for local browsing."

    def handle(self, *args, **options):
        if get_user_model().objects.filter(username="demo").exists():
            self.stdout.write("demo world already seeded")
            return
        with transaction.atomic():
            profile = t.make_student(username="demo", display_name="Demo Student",
                                     goal="Data Scientist")
            profile.user.set_password("demo")
            profile.user.save(update_fields=["password"])
            demo_courses = []
            for i in (1, 2):
                course = t.make_course(id=f"demo-c{i}")
                demo_courses.append(course)
                t.make_meeting(course, day_of_week=1 + i)
                t.make_syllabus(course)
                t.make_assignment(course, weight=30)
                t.make_assignment(course, due=timezone.now() + dt.timedelta(days=10 + i))
                t.enroll(profile, course, bucket="core" if i == 1 else "elective")
            for _ in range(4):
                t.make_event(goal_tags=["data scientist"])
            for cat in ("academic", "career", "technical"):
                t.make_resource(category=cat)
            t.make_shared_task(source="career")
            today = timezone.localdate()
            for track in ("11 month", "17 month"):
                t.make_phase(track, "fall", today - dt.timedelta(days=10),
                             today + dt.timedelta(days=60), term="Fall 2026")
                t.make_requirement(track)
            gsa = t.make_advisor(id="demo-adv-gsa", name="Gail Advisor",
                                 service="advising", email="gsa-demo@ucsd.edu")
            cmc = t.make_advisor(id="demo-adv-cmc", name="Cam Coach", service="career",
                                 role="Career Coach", location="CMC office / Zoom",
                                 email="cmc-demo@ucsd.edu")
            for adv in (gsa, cmc):
                for d in (3, 4, 5):
                    t.make_slot(adv, start=timezone.now() + dt.timedelta(days=d))
            t.make_skill(profile, name="SQL", source="course", course=demo_courses[0])
            t.make_skill(profile, name="Data storytelling", source="course",
                         course=demo_courses[1])
            t.make_skill(profile, name="Stakeholder communication", source="manual")
            for course in demo_courses:
                t.make_highlight(course.code, title=course.title,
                                 highlight=f"Applied analytics from {course.code}")
            generate_version(profile)
        self.stdout.write(self.style.SUCCESS("demo world seeded (user: demo)"))
