from django.conf import settings
from django.db import models

from .students import TRACK_CHOICES


class CoursePlan(models.Model):
    """One student's answers to the planner interview, plus their overrides.

    Deliberately stores the INTAKE and the SWAPS, not the generated plan.

    The plan is a pure function of (intake, overrides, catalog), so persisting
    it would be storing a cache that goes stale the moment the catalog changes
    — and it would go stale silently, leaving a student looking at a course
    that is no longer offered in that quarter. Rebuilding on read costs one
    ranking pass and cannot drift.

    `intake` may be PARTIAL. The interview accumulates answers turn by turn, and
    storing them as they arrive is what stops the conversation losing its place:
    asking an LLM to re-read the whole history each turn looked fine in tests
    and dropped the track the moment a student answered the next question,
    sending them back to step one.

    `selections` is {quarter_key: {slot_index_as_string: course_id}}. Slot
    index is a string because this is JSON and JSON object keys are strings;
    reading it back as an int would work in Python and fail after a round trip
    through the database.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="thrive_course_plan",
    )
    # Blank while the interview is still running: the row exists as soon as the
    # student answers anything, so a half-finished conversation survives a
    # reload, and the track is simply the first thing they tell us.
    track = models.CharField(max_length=16, choices=TRACK_CHOICES,
                             blank=True, default="")
    intake = models.JSONField(default=dict)
    selections = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.track})"


class PlannerSession(models.Model):
    """One conversation's run through the interview.

    Scoped to the CONVERSATION, not the student, and that is the whole point.

    The interview state first lived on `CoursePlan`, which is per-user, so every
    new conversation opened with the answers from the last one already filled in
    and jumped straight to a finished plan. That made the interview impossible
    to re-run — and worse, it silently answered questions the student had not
    been asked in this conversation, so a new goal ("esports analyst") was
    dropped while last week's goal quietly supplied the plan.

    A fresh conversation starts a fresh interview. `CoursePlan` still holds the
    COMMITTED plan and its swaps, which is what `/api/thrive/plan` serves; this
    holds only the answers gathered so far in one chat.
    """
    conversation = models.OneToOneField(
        "rsm_thrive.Conversation", on_delete=models.CASCADE,
        related_name="planner_session",
    )
    intake = models.JSONField(default=dict)
    # How far through the quarter-by-quarter review this conversation is:
    # {"index": <quarter position>} while walking it, null otherwise. Held here
    # rather than re-derived from the transcript because "which quarter are we
    # on" is state, and reading it back out of prose is exactly the guesswork
    # that made the interview lose its place.
    review = models.JSONField(null=True, blank=True, default=None)
    # What this conversation has established about where the student IS:
    # {"track": ..., "start_from": ..., "previous_track": ...}. Null until the
    # situational route resolves something.
    #
    # Its own field rather than a key inside `intake`, because it is not an
    # interview answer: `intake` is handed straight to `planner.build_for` and
    # saved onto `CoursePlan`, and smuggling a private key through both means
    # every consumer of an intake has to know to ignore it. Keeping it separate
    # is also what stops the follow-up loop it exists to prevent -- asked for a
    # track and then for a quarter, the second turn states only the quarter,
    # and without somewhere to keep the first answer the route asks for the
    # track again forever.
    situation = models.JSONField(null=True, blank=True, default=None)
    # Questions this conversation has already put to the student, by key.
    #
    # There is only one, and it still needs recording. The load preference is
    # asked once before the plan is built; without a record of having asked,
    # a student who replies with something else -- a question, a course code --
    # gets asked it again on the next turn that would build a plan, forever.
    # An interview with no exit is the thing being removed, so the exit is
    # stored rather than inferred.
    asked = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"session for conversation {self.conversation_id}"
