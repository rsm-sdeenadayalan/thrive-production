from django.urls import path

from .views import advisors, appointments, assignments, courses, degree, events, health, overlay, requests, resources, resume, students, tasks

app_name = "rsm_thrive"

urlpatterns = [
    path("advisors", advisors.advisors, name="advisors"),
    path("advisors/<str:advisor_id>/slots", advisors.advisor_slots, name="advisor-slots"),
    path("appointments", appointments.appointments_dispatch, name="appointments"),
    path("appointments/<str:appointment_id>/cancel", appointments.cancel_appointment, name="appointment-cancel"),
    path("assignments", assignments.assignments, name="assignments"),
    path("calendar-prefs", overlay.calendar_prefs, name="calendar-prefs"),
    path("courses", courses.courses, name="courses"),
    path("degree/progress", degree.progress, name="degree-progress"),
    path("degree/timeline", degree.timeline, name="degree-timeline"),
    path("events", events.events, name="events"),
    path("events/<str:event_id>/ignore", overlay.ignore_event, name="event-ignore"),
    path("events/<str:event_id>/join", overlay.join_event, name="event-join"),
    path("health", health.health, name="health"),
    path("me", students.me, name="me"),
    path("overlay", overlay.overlay, name="overlay"),
    path("requests/prefill", requests.prefill, name="request-prefill"),
    path("requests", requests.requests_dispatch, name="requests"),
    path("requests/<str:request_id>/submit", requests.submit_request, name="request-submit"),
    path("resources", resources.resources, name="resources"),
    path("resume/current", resume.resume_current, name="resume-current"),
    path("resume/skills", resume.skills, name="resume-skills"),
    path("resume/versions", resume.resume_versions_dispatch, name="resume-versions"),
    path("syllabi", courses.syllabi, name="syllabi"),
    path("tss", requests.tss, name="tss"),
    path("tss/connect", requests.tss_connect, name="tss-connect"),
    path("tasks", tasks.tasks_dispatch, name="tasks"),
    path("tasks/<str:task_id>", tasks.delete_task, name="task-delete"),
    path("tasks/<str:task_id>/note", overlay.task_note, name="task-note"),
    path("tasks/<str:task_id>/override", tasks.override, name="task-override"),
]
