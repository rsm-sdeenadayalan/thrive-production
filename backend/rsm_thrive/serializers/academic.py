from rsm_thrive.serialize import iso_instant


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
