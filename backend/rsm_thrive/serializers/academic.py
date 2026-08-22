from rsm_thrive.serialize import iso_date, iso_instant


def assignment_payload(assignment, student_assignment=None) -> dict:
    payload = {
        "id": assignment.id,
        "courseId": assignment.course_id,
        "title": assignment.title,
        "dueDate": iso_instant(assignment.due_date),
        "weight": assignment.weight,
        "status": student_assignment.status if student_assignment else "not-started",
    }
    if student_assignment and student_assignment.grade:
        payload["grade"] = student_assignment.grade
    if assignment.description:
        payload["description"] = assignment.description
    return payload


def next_assignment_for(course, now) -> dict:
    rows = list(course.assignments.all())  # uses the prefetch cache
    upcoming = [a for a in rows if a.due_date >= now]
    if upcoming:
        chosen = min(upcoming, key=lambda a: a.due_date)
    elif rows:
        chosen = max(rows, key=lambda a: a.due_date)
    else:
        return {"title": "Nothing scheduled yet", "due": iso_instant(now)}
    return {"title": chosen.title, "due": iso_instant(chosen.due_date)}


def course_payload(course, enrollment, now) -> dict:
    syllabus = getattr(course, "syllabus", None)
    payload = {
        "id": course.id,
        "code": course.code,
        "title": course.title,
        "instructor": course.instructor,
        "schedule": [
            {"dayOfWeek": m.day_of_week, "startTime": m.start_time,
             "endTime": m.end_time, "location": m.location}
            for m in course.meetings.all()
        ],
        "term": course.term,
        "progress": enrollment.progress,
        "standing": enrollment.standing,
        "nextAssignment": next_assignment_for(course, now),
        # "" until ingestion guarantees a syllabus per course (F3 invariant)
        "syllabusId": syllabus.id if syllabus else "",
        "units": course.units,
    }
    if enrollment.nudge:
        payload["nudge"] = enrollment.nudge
    if enrollment.current_grade:
        payload["currentGrade"] = enrollment.current_grade
    return payload


def syllabus_payload(syllabus) -> dict:
    payload = {
        "id": syllabus.id,
        "courseId": syllabus.course_id,
        "description": syllabus.description,
        "gradeBreakdown": syllabus.grade_breakdown,
        "policies": syllabus.policies,
        "officeHours": syllabus.office_hours,
        "lastUpdated": iso_date(syllabus.last_updated),
    }
    if syllabus.source_url:
        payload["sourceUrl"] = syllabus.source_url
    return payload
