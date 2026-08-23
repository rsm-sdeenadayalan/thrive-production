from .academic import (  # noqa: F401
    Assignment, Course, CourseMeeting, Enrollment, StudentAssignment, Syllabus,
)
from .appointments import (  # noqa: F401
    Advisor, Appointment, AppointmentNotification, AppointmentSlot,
)
from .chat import ChatMessage, Conversation  # noqa: F401
from .degree import (  # noqa: F401
    DegreeGap, DegreeRequirement, ProgramPhaseRow,
)
from .events import Event  # noqa: F401
from .knowledge import Document, DocumentChunk  # noqa: F401
from .overlay import (  # noqa: F401
    CalendarPrefs, EventJoin, IgnoredEvent, SharedTask, StudentTask, TaskNote,
    TaskOverride,
)
from .personal import (  # noqa: F401
    CalendarItemLabel, CalendarItemUrgent, CustomCalendarEvent, QuickListItem,
)
from .requests import CourseRequest  # noqa: F401
from .resources import ResourceLink  # noqa: F401
from .resume import (  # noqa: F401
    ResumeCourseHighlight, ResumeVersion, Skill,
)
from .students import StudentProfile  # noqa: F401
