/**
 * THRIVE domain types.
 *
 * One file, on purpose: these are the contract between the UI and whatever
 * is behind it. Today that's local mock data; later it'll be campus APIs, a
 * knowledge layer, and MCP tools. Components import these types and the
 * provider functions in `./providers` -- never the mock modules directly --
 * so swapping the source is a change in one place.
 *
 * Dates are ISO-8601 strings, not `Date` objects. React Server Components
 * serialize props across the server/client boundary, and `Date` does not
 * survive that cleanly. Parse at the edge where you format.
 */

/** ISO-8601 timestamp, e.g. "2026-08-11T09:00:00-07:00". */
export type ISODateTime = string;

/** ISO-8601 calendar date, e.g. "2026-08-11". */
export type ISODate = string;

/**
 * The shared status vocabulary. These three values map 1:1 onto the reserved
 * status colors in the design tokens, so a status never has to pick a color.
 */
export type Standing = "onTrack" | "watch" | "needsHelp";

/** Which MSBA program length the student is enrolled in. */
export type Track = "11 month" | "17 month";

export type Priority = "low" | "medium" | "high";

/**
 * Where a piece of work came from. Drives the small source tag on a task row.
 * More sources (email, Slack, advising notes) will land here as integrations
 * arrive.
 */
export type TaskSource = "class" | "career" | "admin" | "event";

export type AssignmentStatus =
  | "not-started"
  | "in-progress"
  | "submitted"
  | "graded"
  | "late";

/**
 * Who is putting the event on. This is an origin, not a topic -- it answers
 * "whose event is this" so the student can tell a Rady workshop from a
 * city-wide meetup at a glance.
 */
export type EventType = "rady" | "ucsd" | "sandiego" | "club" | "career";

// ---------------------------------------------------------------------------
// Student
// ---------------------------------------------------------------------------

/**
 * Consent flags. THRIVE reads from a lot of systems, so what the student has
 * agreed to share is part of the model rather than an afterthought.
 */
export interface StudentConsent {
  /** Allow reading the student's calendar. THRIVE never writes to it. */
  calendarRead: boolean;
  /** Allow reading LMS/Canvas coursework. */
  lmsRead: boolean;
  /** Allow personalized career and event recommendations. */
  careerRecommendations: boolean;
  /** Allow sharing anonymized progress with academic advisors. */
  advisorSharing: boolean;
}

export interface Student {
  id: string;
  name: string;
  /** The career the student is working toward, e.g. "Data Scientist". */
  goal: string;
  track: Track;
  program: string;
  /** One-line plain-language summary of how the student is doing overall. */
  standingSummary: string;
  standing: Standing;
  consent: StudentConsent;
  /** Optional avatar URL; the UI falls back to initials when absent. */
  avatarUrl?: string;
  /** Current academic term label, e.g. "Summer 2026". */
  currentTerm: string;
  /**
   * The day the program began. The whole timeline is derived from this plus
   * `track` -- nothing about the finish line is stored.
   */
  programStart: ISODate;
}

// ---------------------------------------------------------------------------
// Program timeline
// ---------------------------------------------------------------------------

export type PhaseId =
  | "orientation"
  | "fall"
  | "winter"
  | "spring"
  | "summer"
  | "optional-fall";

/** Derived from today's date against the phase window. Never stored. */
export type PhaseStatus = "complete" | "current" | "upcoming";

export interface ProgramPhase {
  id: PhaseId;
  /** "Fall Quarter" */
  label: string;
  /** "Fall 2025" */
  term: string;
  start: ISODate;
  end: ISODate;
  /**
   * True for phases outside the shorter track. Still shown on the timeline so
   * a student on the 11 month track can see what taking it would add.
   */
  optional: boolean;
  status: PhaseStatus;
}

export interface ProgramTimeline {
  phases: ProgramPhase[];
  /** Null before the program starts or after the finish line. */
  currentPhaseId: PhaseId | null;
  /** 0-100, today's position between programStart and programEnd. */
  percentComplete: number;
  programStart: ISODate;
  /** End of the last phase this track requires. Derived, never stored. */
  programEnd: ISODate;
  /** Term the track finishes in, e.g. "Summer 2026". */
  expectedFinishTerm: string;
  track: Track;
}

// ---------------------------------------------------------------------------
// Courses and syllabi
// ---------------------------------------------------------------------------

/** A recurring class meeting. */
export interface CourseMeeting {
  /** 0 = Sunday ... 6 = Saturday, matching `Date.prototype.getDay()`. */
  dayOfWeek: number;
  /** 24-hour local wall time, "HH:mm". */
  startTime: string;
  endTime: string;
  location: string;
}

/** The single next thing due in a course. */
export interface NextAssignment {
  title: string;
  due: ISODateTime;
}

export interface Course {
  id: string;
  /** Catalog code, e.g. "MGT 142". */
  code: string;
  title: string;
  instructor: string;
  schedule: CourseMeeting[];
  term: string;
  /** Completion of the course itself, 0-100. */
  progress: number;
  standing: Standing;
  nextAssignment: NextAssignment;
  /**
   * A short, specific prompt shown only when the course needs attention.
   * Present on at most a course or two at a time -- a nudge on everything is
   * a nudge on nothing.
   */
  nudge?: string;
  syllabusId: string;
  units: number;
  /** Current letter or percentage grade, when one exists yet. */
  currentGrade?: string;
}

/** One weighted component of a course grade, e.g. "Final project, 30%". */
export interface SyllabusGradeComponent {
  label: string;
  /** Share of the final grade, 0-100. */
  weight: number;
}

export interface Syllabus {
  id: string;
  courseId: string;
  /** Short summary of what the course covers. */
  description: string;
  gradeBreakdown: SyllabusGradeComponent[];
  policies: string[];
  officeHours: string;
  /** Link to the source document, when there is one. */
  sourceUrl?: string;
  /** When THRIVE last read this syllabus from its source. */
  lastUpdated: ISODate;
}

// ---------------------------------------------------------------------------
// Work
// ---------------------------------------------------------------------------

export interface Assignment {
  id: string;
  courseId: string;
  title: string;
  dueDate: ISODateTime;
  /** Share of the course grade, 0-100. */
  weight: number;
  status: AssignmentStatus;
  /** Populated once status is "graded". */
  grade?: string;
  description?: string;
}

export interface Subtask {
  id: string;
  title: string;
  done: boolean;
}

export interface Task {
  id: string;
  title: string;
  dueDate: ISODateTime;
  source: TaskSource;
  priority: Priority;
  done: boolean;
  subtasks: Subtask[];
  /** Set when the task was derived from a specific course. */
  courseId?: string;
  /** Course code cached for display, so a row doesn't need a second lookup. */
  courseCode?: string;
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

export interface Event {
  id: string;
  title: string;
  type: EventType;
  start: ISODateTime;
  end?: ISODateTime;
  location: string;
  description?: string;
  registerUrl?: string;
  /**
   * True when the event lines up with the student's stated goal. Scored
   * behind the data layer so the UI only has to render the badge.
   */
  relevantToGoal: boolean;
}

// ---------------------------------------------------------------------------
// Degree progress
// ---------------------------------------------------------------------------

/** A specific unmet requirement, with enough context to act on it. */
export interface DegreeGap {
  id: string;
  label: string;
  /** Why it matters / what satisfies it. */
  detail: string;
  severity: Standing;
}

export interface DegreeProgress {
  unitsCompleted: number;
  unitsRequired: number;
  /** Core courses completed and total required. */
  coreDone: number;
  coreRequired: number;
  /** Electives completed and total required. */
  electiveDone: number;
  electiveRequired: number;
  gaps: DegreeGap[];
  track: Track;
  /*
   * No `expectedCompletion`. It was declared here and hardcoded "Spring 2027"
   * in the fixture while `buildProgramTimeline` derived Fall 2027 for the same
   * student -- two answers to one question, hidden only because the field
   * rendered nowhere. See MIGRATION.md section 9 defect 9. The finish term is
   * derived: read `ProgramTimeline.expectedFinishTerm`.
   */
}

// ---------------------------------------------------------------------------
// Appointments
// ---------------------------------------------------------------------------

/** Which service an advisor provides. Drives grouping and the service cards. */
export type AdvisingService = "advising" | "career";

/** How the student meets the advisor. */
export type MeetingMode = "in person" | "zoom";

export type AppointmentStatus = "confirmed" | "cancelled";

export interface Advisor {
  id: string;
  name: string;
  /** Job title, e.g. "Graduate Student Advisor". */
  role: string;
  service: AdvisingService;
  /** Avatar URL. Absent falls back to initials, same as the top bar. */
  avatar?: string;
  /** Where they are found, e.g. "Rady 2S111" or "CMC office / Zoom". */
  location: string;
  /** One line on what this person is for. */
  blurb?: string;
}

export interface AppointmentSlot {
  id: string;
  advisorId: string;
  start: ISODateTime;
  end: ISODateTime;
  mode: MeetingMode;
  /** False when somebody already has it. Taken slots still render, disabled,
   *  so the calendar reads as real rather than suspiciously empty. */
  available: boolean;
}

export interface Appointment {
  id: string;
  advisorId: string;
  studentId: string;
  /**
   * The slot this appointment claimed.
   *
   * Not in the Next version, and added deliberately. `cancelAppointment` there
   * released a slot by scanning the claimed set for one whose `start` matched
   * the appointment's, because it had no other way back to the slot. That is
   * correct only while no advisor ever publishes two simultaneous slots, and
   * releases the wrong one the moment somebody does -- MIGRATION.md section 9
   * defect 8. Holding the id makes the release exact, and it is the shape the
   * Django model has anyway.
   */
  slotId: string;
  start: ISODateTime;
  end: ISODateTime;
  mode: MeetingMode;
  /** What the student wants to talk about. */
  reason: string;
  status: AppointmentStatus;
}

// ---------------------------------------------------------------------------
// Course action requests (TSS / EASy style)
// ---------------------------------------------------------------------------

/** The four actions a student can request against their enrollment. */
export type CourseRequestType =
  | "enroll"
  | "drop"
  | "reduced load"
  | "out of major";

export type CourseRequestStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "denied";

export interface CourseRequest {
  id: string;
  type: CourseRequestType;
  /** Course code and title, or a term-wide marker for a reduced load. */
  course: string;
  reason: string;
  status: CourseRequestStatus;
  /** Set when the request leaves draft. Null while it is still a draft. */
  submittedAt: ISODateTime | null;
  /**
   * Snapshot of the student record as it stood when the request was raised.
   * Kept on the request rather than looked up later, because a submitted
   * request should show what was actually sent, not today's values.
   */
  prefill: CourseRequestPrefill;
}

/** The read-only student context auto-populated into every request. */
export interface CourseRequestPrefill {
  studentName: string;
  program: string;
  track: Track;
  term: string;
  /** Course codes the student is enrolled in right now. */
  currentCourses: string[];
  /** Total units in the current term. */
  currentUnits: number;
  unitsCompleted: number;
  unitsRequired: number;
}

/** What the student actually fills in. Everything else is pre-filled. */
export interface CourseRequestInput {
  type: CourseRequestType;
  course: string;
  reason: string;
}

// ---------------------------------------------------------------------------
// Living resume
// ---------------------------------------------------------------------------

/** Where a skill came from. Course-derived skills carry their origin. */
export type SkillSource = "course" | "manual";

export interface Skill {
  id: string;
  name: string;
  source: SkillSource;
  /** Set when source is "course" -- the class that produced the skill. */
  courseId?: string;
}

/** One line of experience on the resume. */
export interface ResumeExperience {
  id: string;
  title: string;
  organization: string;
  /** Free-text range, e.g. "Jun 2026 - present". */
  period: string;
  bullets: string[];
}

/** A coursework entry, kept separate from skills so both can be rendered. */
export interface ResumeCourse {
  code: string;
  title: string;
  /** What the student can now do because of it. */
  highlight: string;
}

export interface ResumeVersion {
  id: string;
  /** Human label, e.g. "After Summer 2026 midterms". */
  label: string;
  createdAt: ISODateTime;
  summary: string;
  skills: Skill[];
  courses: ResumeCourse[];
  experience: ResumeExperience[];
  /** Exactly one version is current at a time. */
  isCurrent: boolean;
}

/** What changed between the previous current version and a new one. */
export interface ResumeDiff {
  addedSkills: string[];
  addedCourses: string[];
  summaryChanged: boolean;
}

// ---------------------------------------------------------------------------
// Job search
// ---------------------------------------------------------------------------

/** How a match report grades the student against a posting's requirements. */
export type JobCompetency = "strong" | "good" | "stretch" | "reach";

export interface JobPosting {
  id: string; // "job-<pk>"
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  skills: string[];
  postedAt: ISODateTime | null;
  snippet: string;
}

/** The single-posting view. Trades `snippet` for the full `description`. */
export interface JobPostingDetail extends Omit<JobPosting, "snippet"> {
  description: string;
}

/** One search result: a posting plus how it compares to the student. */
export interface JobSearchEntry {
  job: JobPosting;
  score: number;
  matchedSkills: string[];
  missingSkills: string[];
}

/** What postings for a role typically ask for, across the sample searched. */
export interface RoleBenchmark {
  sampleSize: number;
  topSkills: { name: string; share: number }[];
}

export interface JobSearchResult {
  query: string;
  /** False when the student has no resume to score against yet. */
  profileAvailable: boolean;
  benchmark: RoleBenchmark;
  results: JobSearchEntry[];
}

/** A generated fit assessment against one posting. */
export interface MatchReport {
  id: string; // "rep-<pk>"
  jobId: string;
  score: number;
  competency: JobCompetency;
  matchedSkills: string[];
  gaps: string[];
  verdict: string;
  createdAt: ISODateTime;
}

// ---------------------------------------------------------------------------
// Job feed
// ---------------------------------------------------------------------------

/** Which slice of the feed a student is looking at. */
export type JobFeedTab = "recommended" | "liked" | "all";

/**
 * A selectable location bucket for the results page's region filter.
 *
 * Mirrors `backend/rsm_thrive/services/jobs/region.py` exactly -- values,
 * priority order and all. `""` (not a member of this type) means "All
 * regions," the default with no filter applied.
 */
export type JobRegion =
  | "remote"
  | "san_diego"
  | "bay_area"
  | "los_angeles"
  | "seattle"
  | "new_york"
  | "other_us"
  | "international";

/**
 * One posting in the feed: the hybrid search score every entry carries, plus
 * an optional cached LLM report score/competency layered on top when one
 * exists for the student's current resume version.
 */
export interface JobFeedEntry {
  job: JobPosting;
  score: number;
  reportScore: number | null;
  competency: JobCompetency | null;
  matchedSkills: string[];
  missingSkills: string[];
  liked: boolean;
  dismissed: boolean;
}

export interface JobFeedResult {
  results: JobFeedEntry[];
  counts: Record<JobFeedTab, number>;
  profileAvailable: boolean;
}

/** What a like/dismiss toggle returns: the posting's new interaction state. */
export interface JobInteractionState {
  jobId: string;
  liked: boolean;
  dismissed: boolean;
}

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

export type ResourceCategory =
  | "academic"
  | "career"
  | "wellness"
  | "technical"
  | "administrative";

export interface ResourceLink {
  id: string;
  title: string;
  description: string;
  url: string;
  category: ResourceCategory;
  /** Owning office or team, e.g. "Rady Career Management". */
  owner?: string;
}

// ---------------------------------------------------------------------------
// Ask THRIVE
// ---------------------------------------------------------------------------

/**
 * The three surfaces Ask THRIVE is split into.
 *
 * A closed union, and load-bearing in the same way `EventType` is: the route
 * parameter is validated against exactly this set, so an unknown destination is
 * a 404 rather than an empty page. `ASK_DESTINATIONS` in `$lib/ask` is the
 * ordered rendering list built from it.
 *
 * `courses` rather than `recommender`: the slug is what a student sees in the
 * address bar, and "what do I want to ask about" is answered by the subject, not
 * by the name of the machine answering.
 */
export type AskDestination = "resources" | "courses" | "career";

/** Who said it. Two participants, so this never needs to be a string. */
export type ChatRole = "student" | "thrive";

/**
 * A choice offered alongside a reply, rendered as a button.
 *
 * `send` is the text posted as the student's message when it is pressed, not an
 * opaque id: the transcript then reads exactly as though they typed it, and the
 * backend's extractor sees ordinary language rather than a code it would need a
 * second vocabulary for.
 */
export interface QuickReply {
  label: string;
  send: string;
}

/**
 * What a destination shows before the student has said anything.
 *
 * Only the course recommender has one: it runs a scripted interview, so opening
 * on its first question is strictly more useful than opening on an empty box.
 * The other two destinations answer free-text questions and have nothing
 * scripted to open with, so they get null.
 */
export interface ConversationStarter {
  /** Markdown, rendered the same way a reply is. */
  body: string;
  quickReplies: QuickReply[];
  /** Same shape as a reply, so the opening is not a special case downstream. */
  form: RatingForm | null;
}

/**
 * A small form offered with a reply, when one control per item beats a row of
 * buttons. Only the skills step uses one: it asks about five areas at once, and
 * twenty-five flat buttons is a wall rather than a shortcut.
 *
 * Every row starts at `default` so nothing is claimed on the student's behalf,
 * and submitting sends one ordinary text message — never a payload — so the
 * transcript reads as something a person said.
 */
export interface RatingForm {
  kind: "rating";
  rows: { key: string; label: string }[];
  scale: { value: number; label: string; help: string }[];
  default: number;
  submitLabel: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  body: string;
  /**
   * Optional, and additive to the upstream provider contract. Absent for every
   * free-text reply, and the same choices are always written into `body` too —
   * so a client that ignores this renders a usable conversation and a student
   * can always type the answer instead of pressing anything.
   */
  quickReplies?: QuickReply[];
  /** Optional and additive, like `quickReplies`. Null for almost every reply. */
  form?: RatingForm | null;
  sentAt: ISODateTime;
}

/**
 * One saved conversation.
 *
 * ## Why this is provider data and not a store
 *
 * A conversation cannot live in `localStorage`. They are large, they grow
 * without bound, and a student who opens THRIVE on a different laptop would
 * find an empty history with no way to tell that from never having asked
 * anything. So this is server data reached through a provider, mocked for now
 * exactly like every other surface in this app was built.
 *
 * Note what that means for the id: `conv-001` is a SERVER id, and nothing
 * client-side is keyed by it. It is not a fourth persisted key space -- the
 * three (raw `Event.id`, calendar item id, task id) are all `localStorage`
 * spaces, and this adds no store at all.
 */
export interface Conversation {
  id: string;
  destination: AskDestination;
  /** Short label for the history list. Written by the fixture, later derived. */
  title: string;
  messages: ChatMessage[];
  /** When the last message landed. Drives the history list's order. */
  updatedAt: ISODateTime;
}
