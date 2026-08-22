"""JSON Schemas (draft 2020-12) transcribed from frontend/src/lib/data/types.ts.

Every schema sets ``additionalProperties: False`` and marks contract-optional
keys (``?`` in types.ts, or keys our serializers omit when blank) as optional
by leaving them out of ``required``. Closed unions are copied verbatim as
``enum`` lists.
"""

ISO_INSTANT = {"type": "string",
               "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$"}
ISO_DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
STANDING = {"enum": ["onTrack", "watch", "needsHelp"]}
TRACK = {"enum": ["11 month", "17 month"]}
PRIORITY = {"enum": ["low", "medium", "high"]}

STUDENT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "name", "goal", "track", "program", "standingSummary",
                 "standing", "consent", "currentTerm", "programStart"],
    "properties": {
        "id": {"type": "string"}, "name": {"type": "string"},
        "goal": {"type": "string"}, "track": TRACK, "program": {"type": "string"},
        "standingSummary": {"type": "string"}, "standing": STANDING,
        "consent": {
            "type": "object", "additionalProperties": False,
            "required": ["calendarRead", "lmsRead", "careerRecommendations",
                         "advisorSharing"],
            "properties": {k: {"type": "boolean"} for k in
                           ["calendarRead", "lmsRead", "careerRecommendations",
                            "advisorSharing"]},
        },
        "avatarUrl": {"type": "string"},
        "currentTerm": {"type": "string"}, "programStart": ISO_DATE,
    },
}

TASK = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "title", "dueDate", "source", "priority", "done", "subtasks"],
    "properties": {
        "id": {"type": "string"}, "title": {"type": "string"},
        "dueDate": ISO_INSTANT,
        "source": {"enum": ["class", "career", "admin", "event"]},
        "priority": PRIORITY, "done": {"type": "boolean"},
        "subtasks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "title", "done"],
            "properties": {"id": {"type": "string"}, "title": {"type": "string"},
                           "done": {"type": "boolean"}},
        }},
        "courseId": {"type": "string"}, "courseCode": {"type": "string"},
    },
}

# ---------------------------------------------------------------------------
# Courses and syllabi
# ---------------------------------------------------------------------------

COURSE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "code", "title", "instructor", "schedule", "term",
                 "progress", "standing", "nextAssignment", "syllabusId", "units"],
    "properties": {
        "id": {"type": "string"}, "code": {"type": "string"},
        "title": {"type": "string"}, "instructor": {"type": "string"},
        "schedule": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["dayOfWeek", "startTime", "endTime", "location"],
            "properties": {
                "dayOfWeek": {"type": "number"},
                "startTime": {"type": "string", "pattern": r"^\d{2}:\d{2}$"},
                "endTime": {"type": "string", "pattern": r"^\d{2}:\d{2}$"},
                "location": {"type": "string"},
            },
        }},
        "term": {"type": "string"}, "progress": {"type": "number"},
        "standing": STANDING,
        "nextAssignment": {
            "type": "object", "additionalProperties": False,
            "required": ["title", "due"],
            "properties": {"title": {"type": "string"}, "due": ISO_INSTANT},
        },
        "nudge": {"type": "string"},
        "syllabusId": {"type": "string"}, "units": {"type": "number"},
        "currentGrade": {"type": "string"},
    },
}

SYLLABUS = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "courseId", "description", "gradeBreakdown", "policies",
                 "officeHours", "lastUpdated"],
    "properties": {
        "id": {"type": "string"}, "courseId": {"type": "string"},
        "description": {"type": "string"},
        "gradeBreakdown": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["label", "weight"],
            "properties": {"label": {"type": "string"}, "weight": {"type": "number"}},
        }},
        "policies": {"type": "array", "items": {"type": "string"}},
        "officeHours": {"type": "string"},
        "sourceUrl": {"type": "string"},
        "lastUpdated": ISO_DATE,
    },
}

# ---------------------------------------------------------------------------
# Work
# ---------------------------------------------------------------------------

ASSIGNMENT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "courseId", "title", "dueDate", "weight", "status"],
    "properties": {
        "id": {"type": "string"}, "courseId": {"type": "string"},
        "title": {"type": "string"}, "dueDate": ISO_INSTANT,
        "weight": {"type": "number"},
        "status": {"enum": ["not-started", "in-progress", "submitted", "graded",
                             "late"]},
        "grade": {"type": "string"}, "description": {"type": "string"},
    },
}

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

EVENT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "title", "type", "start", "location", "relevantToGoal"],
    "properties": {
        "id": {"type": "string"}, "title": {"type": "string"},
        "type": {"enum": ["rady", "ucsd", "sandiego", "club", "career"]},
        "start": ISO_INSTANT, "end": ISO_INSTANT,
        "location": {"type": "string"},
        "description": {"type": "string"}, "registerUrl": {"type": "string"},
        "relevantToGoal": {"type": "boolean"},
    },
}

# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

RESOURCE_LINK = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "title", "description", "url", "category"],
    "properties": {
        "id": {"type": "string"}, "title": {"type": "string"},
        "description": {"type": "string"}, "url": {"type": "string"},
        "category": {"enum": ["academic", "career", "wellness", "technical",
                               "administrative"]},
        "owner": {"type": "string"},
    },
}

# ---------------------------------------------------------------------------
# Degree progress and program timeline
# ---------------------------------------------------------------------------

DEGREE_PROGRESS = {
    "type": "object",
    "additionalProperties": False,
    "required": ["unitsCompleted", "unitsRequired", "coreDone", "coreRequired",
                 "electiveDone", "electiveRequired", "gaps", "track"],
    "properties": {
        "unitsCompleted": {"type": "number"}, "unitsRequired": {"type": "number"},
        "coreDone": {"type": "number"}, "coreRequired": {"type": "number"},
        "electiveDone": {"type": "number"}, "electiveRequired": {"type": "number"},
        "gaps": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "label", "detail", "severity"],
            "properties": {
                "id": {"type": "string"}, "label": {"type": "string"},
                "detail": {"type": "string"}, "severity": STANDING,
            },
        }},
        "track": TRACK,
    },
}

PHASE_ID = {"enum": ["orientation", "fall", "winter", "spring", "summer",
                      "optional-fall"]}

PROGRAM_TIMELINE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["phases", "currentPhaseId", "percentComplete", "programStart",
                 "programEnd", "expectedFinishTerm", "track"],
    "properties": {
        "phases": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "label", "term", "start", "end", "optional",
                         "status"],
            "properties": {
                "id": PHASE_ID,
                "label": {"type": "string"}, "term": {"type": "string"},
                "start": ISO_DATE, "end": ISO_DATE,
                "optional": {"type": "boolean"},
                "status": {"enum": ["complete", "current", "upcoming"]},
            },
        }},
        "currentPhaseId": {"enum": ["orientation", "fall", "winter", "spring",
                                     "summer", "optional-fall", None]},
        "percentComplete": {"type": "integer", "minimum": 0, "maximum": 100},
        "programStart": ISO_DATE, "programEnd": ISO_DATE,
        "expectedFinishTerm": {"type": "string"},
        "track": TRACK,
    },
}

# ---------------------------------------------------------------------------
# Overlay (Task 11 aggregate; not part of types.ts)
# ---------------------------------------------------------------------------

OVERLAY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ignoredEventIds", "joinedEventIds", "calendarPrefs", "taskNotes"],
    "properties": {
        "ignoredEventIds": {"type": "array", "items": {"type": "string"}},
        "joinedEventIds": {"type": "array", "items": {"type": "string"}},
        "calendarPrefs": {"type": "object"},
        "taskNotes": {"type": "object", "additionalProperties": {"type": "string"}},
    },
}

# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

SERVICE = {"enum": ["advising", "career"]}
MEETING_MODE = {"enum": ["in person", "zoom"]}

ADVISOR = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "name", "role", "service", "location"],
    "properties": {
        "id": {"type": "string"}, "name": {"type": "string"},
        "role": {"type": "string"}, "service": SERVICE,
        "avatar": {"type": "string"}, "location": {"type": "string"},
        "blurb": {"type": "string"},
    },
}

APPOINTMENT_SLOT = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "advisorId", "start", "end", "mode", "available"],
    "properties": {
        "id": {"type": "string"}, "advisorId": {"type": "string"},
        "start": ISO_INSTANT, "end": ISO_INSTANT,
        "mode": MEETING_MODE, "available": {"type": "boolean"},
    },
}

APPOINTMENT = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "advisorId", "studentId", "slotId", "start", "end",
                 "mode", "reason", "status"],
    "properties": {
        "id": {"type": "string"}, "advisorId": {"type": "string"},
        "studentId": {"type": "string"}, "slotId": {"type": "string"},
        "start": ISO_INSTANT, "end": ISO_INSTANT, "mode": MEETING_MODE,
        "reason": {"type": "string"},
        "status": {"enum": ["confirmed", "cancelled"]},
    },
}

# ---------------------------------------------------------------------------
# Course action requests (TSS / EASy style)
# ---------------------------------------------------------------------------

COURSE_REQUEST_PREFILL = {
    "type": "object",
    "additionalProperties": False,
    "required": ["studentName", "program", "track", "term", "currentCourses",
                 "currentUnits", "unitsCompleted", "unitsRequired"],
    "properties": {
        "studentName": {"type": "string"}, "program": {"type": "string"},
        "track": TRACK, "term": {"type": "string"},
        "currentCourses": {"type": "array", "items": {"type": "string"}},
        "currentUnits": {"type": "number"},
        "unitsCompleted": {"type": "number"},
        "unitsRequired": {"type": "number"},
    },
}

COURSE_REQUEST = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "type", "course", "reason", "status", "submittedAt",
                 "prefill"],
    "properties": {
        "id": {"type": "string"},
        "type": {"enum": ["enroll", "drop", "reduced load", "out of major"]},
        "course": {"type": "string"}, "reason": {"type": "string"},
        "status": {"enum": ["draft", "submitted", "approved", "denied"]},
        "submittedAt": {"anyOf": [ISO_INSTANT, {"type": "null"}]},
        "prefill": COURSE_REQUEST_PREFILL,
    },
}

# TSS connection status. Our own aggregate; not part of types.ts.
TSS = {
    "type": "object",
    "additionalProperties": False,
    "required": ["connected"],
    "properties": {"connected": {"type": "boolean"}},
}

# ---------------------------------------------------------------------------
# Living resume
# ---------------------------------------------------------------------------

SKILL = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "name", "source"],
    "properties": {
        "id": {"type": "string"}, "name": {"type": "string"},
        "source": {"enum": ["course", "manual"]},
        "courseId": {"type": "string"},
    },
}

RESUME_COURSE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["code", "title", "highlight"],
    "properties": {
        "code": {"type": "string"}, "title": {"type": "string"},
        "highlight": {"type": "string"},
    },
}

RESUME_EXPERIENCE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "title", "organization", "period", "bullets"],
    "properties": {
        "id": {"type": "string"}, "title": {"type": "string"},
        "organization": {"type": "string"}, "period": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}},
    },
}

RESUME_VERSION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "label", "createdAt", "summary", "skills", "courses",
                 "experience", "isCurrent"],
    "properties": {
        "id": {"type": "string"}, "label": {"type": "string"},
        "createdAt": ISO_INSTANT, "summary": {"type": "string"},
        "skills": {"type": "array", "items": SKILL},
        "courses": {"type": "array", "items": RESUME_COURSE},
        "experience": {"type": "array", "items": RESUME_EXPERIENCE},
        "isCurrent": {"type": "boolean"},
    },
}

RESUME_DIFF = {
    "type": "object",
    "additionalProperties": False,
    "required": ["addedSkills", "addedCourses", "summaryChanged"],
    "properties": {
        "addedSkills": {"type": "array", "items": {"type": "string"}},
        "addedCourses": {"type": "array", "items": {"type": "string"}},
        "summaryChanged": {"type": "boolean"},
    },
}
