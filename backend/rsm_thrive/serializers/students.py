from rsm_thrive.serialize import iso_date


def student_payload(profile) -> dict:
    payload = {
        "id": profile.user.username,
        "name": profile.display_name,
        "goal": profile.goal,
        "track": profile.track,
        "program": profile.program,
        "standingSummary": profile.standing_summary,
        "standing": profile.standing,
        "consent": {
            "calendarRead": profile.consent_calendar_read,
            "lmsRead": profile.consent_lms_read,
            "careerRecommendations": profile.consent_career_recommendations,
            "advisorSharing": profile.consent_advisor_sharing,
        },
        "currentTerm": profile.current_term,
        "programStart": iso_date(profile.program_start),
    }
    if profile.avatar_url:
        payload["avatarUrl"] = profile.avatar_url
    return payload
