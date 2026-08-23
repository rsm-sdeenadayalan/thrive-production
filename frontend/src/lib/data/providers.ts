/**
 * Data providers -- the single seam between THRIVE's UI and its sources.
 *
 * Every one of these returns a Promise today and will keep returning a Promise
 * when the body is replaced with a Django call. That is the whole point:
 * callers already `await` these, so swapping the implementation touches no
 * caller. The signature is the contract; the mock behind it is not.
 *
 * Rules for this file:
 *   - Components import from `$lib/data`, never from here and never from
 *     `./mock`. See `index.ts`.
 *   - Shaping, sorting, and filtering that every consumer would otherwise
 *     redo belongs behind this boundary, not in a component.
 *   - No network calls yet. Mock data only. There is no HTTP client in this
 *     phase on purpose -- Django does not exist yet, and inventing a client
 *     against a backend nobody has written would bake in guesses.
 *
 * ## Callers never receive a stored object
 *
 * Every provider returns copies. A caller holding a result must never see it
 * change underneath them when something else mutates the store, and a real API
 * would hand back a fresh payload too.
 *
 * The Next version enforced this unevenly: the store-backed reads copied, but
 * `getStudent`, `getDegreeProgress`, `getAdvisors` and `getResources` returned
 * module fixtures straight out by reference, contradicting the comment two
 * functions above them (MIGRATION.md section 9 defect 15). Nothing mutated
 * them, so there was no live bug -- but "no live bug" is not the same as a
 * contract, so all four copy now.
 *
 * The copies are shallow, as they were in Next. Assigning to a field on a
 * returned object cannot reach the store; pushing onto a nested array still
 * can, because `{ ...version }` shares `version.skills`. See the note in
 * `providers.spec.ts` -- that gap is tested and recorded rather than quietly
 * closed, since deepening it is a behaviour change beyond a port.
 */

import type {
  Advisor,
  Appointment,
  AppointmentSlot,
  Assignment,
  Course,
  Conversation,
  CourseRequest,
  CourseRequestInput,
  CourseRequestPrefill,
  DegreeProgress,
  Event,
  JobCompetency,
  JobPosting,
  JobPostingDetail,
  JobSearchEntry,
  JobSearchResult,
  MatchReport,
  ProgramTimeline,
  ResourceLink,
  ResumeDiff,
  ResumeVersion,
  RoleBenchmark,
  Skill,
  Student,
  Syllabus,
  Task,
} from "./types";

import { resolveAfterDelay } from "./latency";

import {
  buildSlotsFor,
  mockAdvisors,
  nextAppointmentId,
  readStore,
} from "./mock/appointments";
import { buildProgramTimeline } from "./mock/program";
import { nextRequestId, readRequestStore } from "./mock/requests";
import {
  mockResumeCourses,
  mockSkills,
  nextVersionId,
  readResumeStore,
} from "./mock/resume";

import { buildMockAssignments } from "./mock/assignments";
import { buildMockConversations } from "./mock/conversations";
import { buildMockCourses } from "./mock/courses";
import { mockDegreeProgress } from "./mock/degree";
import { buildMockEvents } from "./mock/events";
import { type JobFixture, mockJobs } from "./mock/jobs";
import { mockResources } from "./mock/resources";
import { mockStudent } from "./mock/student";
import { buildMockSyllabi } from "./mock/syllabi";
import { buildMockTasks } from "./mock/tasks";

import { SlotUnavailableError } from "./errors";

export { SlotUnavailableError } from "./errors";

import * as api from "./api/providers";
import { apiEnabled } from "./api/client";

// ---------------------------------------------------------------------------
// Student, courses, coursework
// ---------------------------------------------------------------------------

function mockGetStudent(): Promise<Student> {
  return resolveAfterDelay({ ...mockStudent });
}

function mockGetCourses(): Promise<Course[]> {
  return resolveAfterDelay(buildMockCourses());
}

function mockGetSyllabi(): Promise<Syllabus[]> {
  return resolveAfterDelay(buildMockSyllabi());
}

/** Assignments, soonest due first. */
function mockGetAssignments(): Promise<Assignment[]> {
  const sorted = [...buildMockAssignments()].sort(
    (a, b) => Date.parse(a.dueDate) - Date.parse(b.dueDate),
  );
  return resolveAfterDelay(sorted);
}

/** Tasks, soonest due first. Completed tasks sort last. */
function mockGetTasks(): Promise<Task[]> {
  const sorted = [...buildMockTasks()].sort((a, b) => {
    if (a.done !== b.done) return a.done ? 1 : -1;
    return Date.parse(a.dueDate) - Date.parse(b.dueDate);
  });
  return resolveAfterDelay(sorted);
}

/**
 * Events that haven't finished yet, soonest first. An event stays listed
 * until its end time (or its start, if it has no end), so an all-day fair
 * doesn't vanish from the page at lunchtime. Filtering here means no
 * component has to remember to drop stale listings.
 *
 * The clock read stays behind the provider boundary deliberately. Today that
 * means it happens on the server, in a `load` function, which is where
 * CONVENTIONS.md wants it. When Django lands this becomes a query and the
 * filter moves into the database -- still server-side, still one answer to
 * "what time is it".
 */
function mockGetEvents(): Promise<Event[]> {
  const now = Date.now();
  const upcoming = buildMockEvents()
    .filter((event) => Date.parse(event.end ?? event.start) >= now)
    .sort((a, b) => Date.parse(a.start) - Date.parse(b.start));
  return resolveAfterDelay(upcoming);
}

function mockGetDegreeProgress(): Promise<DegreeProgress> {
  return resolveAfterDelay({ ...mockDegreeProgress });
}

/**
 * Where the student is in the program, computed from their start date and
 * track against today. Change the track on the student and the finish line,
 * the optional-phase tag, and the percentage all move with it.
 */
async function mockGetProgramTimeline(): Promise<ProgramTimeline> {
  const student = await getStudent();
  return buildProgramTimeline(student.programStart, student.track);
}

function mockGetResources(): Promise<ResourceLink[]> {
  return resolveAfterDelay(mockResources.map((resource) => ({ ...resource })));
}

// ---------------------------------------------------------------------------
// Appointments
// ---------------------------------------------------------------------------
//
// The only providers here that mutate. They write to an in-memory store and
// nothing else: no network call, and THRIVE never writes to a real calendar.
// "Add to calendar" stays a visual affordance until the student explicitly
// connects one.

function mockGetAdvisors(): Promise<Advisor[]> {
  return resolveAfterDelay(mockAdvisors.map((advisor) => ({ ...advisor })));
}

/**
 * Published slots for an advisor, with anything booked this session marked
 * unavailable. Merging the store in here means no caller has to remember to
 * cross-reference bookings against the calendar.
 */
function mockGetSlots(advisorId: string): Promise<AppointmentSlot[]> {
  const { claimedSlotIds } = readStore();

  const slots = buildSlotsFor(advisorId).map((slot) =>
    claimedSlotIds.has(slot.id) ? { ...slot, available: false } : slot,
  );

  return resolveAfterDelay(slots);
}

/** Confirmed appointments, soonest first. Cancelled ones drop out. */
function mockGetMyAppointments(): Promise<Appointment[]> {
  const { appointments } = readStore();

  const confirmed = appointments
    .filter((appointment) => appointment.status === "confirmed")
    .sort((a, b) => Date.parse(a.start) - Date.parse(b.start))
    .map((appointment) => ({ ...appointment }));

  return resolveAfterDelay(confirmed);
}

/**
 * Claim a slot and return the appointment created.
 *
 * Re-checks availability rather than trusting the caller: the page the
 * student is looking at may have been rendered before somebody else took the
 * slot, and a real scheduling API would reject that too.
 */
async function mockBookAppointment(
  slotId: string,
  reason: string,
): Promise<Appointment> {
  const store = readStore();

  const advisorId = mockAdvisors.find((advisor) =>
    slotId.startsWith(`slot-${advisor.id}-`),
  )?.id;

  const slot = advisorId
    ? buildSlotsFor(advisorId).find((candidate) => candidate.id === slotId)
    : undefined;

  if (!slot) {
    throw new SlotUnavailableError("That time is no longer listed.");
  }

  if (!slot.available || store.claimedSlotIds.has(slot.id)) {
    throw new SlotUnavailableError();
  }

  const appointment: Appointment = {
    id: nextAppointmentId(),
    advisorId: slot.advisorId,
    studentId: mockStudent.id,
    slotId: slot.id,
    start: slot.start,
    end: slot.end,
    mode: slot.mode,
    reason: reason.trim(),
    status: "confirmed",
  };

  store.claimedSlotIds.add(slot.id);
  store.appointments.push(appointment);

  return resolveAfterDelay({ ...appointment });
}

/**
 * Cancel an appointment and hand its slot back to the calendar. Returns the
 * cancelled record, or null when the ID is unknown.
 *
 * ## Releases by id, not by start time
 *
 * The Next version iterated the claimed set and released the first slot whose
 * `start` matched the appointment's, because the appointment carried no slot
 * reference and slot ids are regenerated per request. Correct with one advisor
 * per service; wrong the moment an advisor publishes two simultaneous slots,
 * where it releases whichever the iteration reached first -- MIGRATION.md
 * section 9 defect 8, and on the do-not-reproduce list.
 *
 * `Appointment.slotId` closes it. Slot ids are deterministic, so the id
 * recorded at booking still names the same slot on a later request, and the
 * release is a single exact delete. It also drops the rebuild of the advisor's
 * whole slot list that the scan needed.
 */
async function mockCancelAppointment(
  appointmentId: string,
): Promise<Appointment | null> {
  const store = readStore();

  const appointment = store.appointments.find(
    (candidate) => candidate.id === appointmentId,
  );

  if (!appointment) return resolveAfterDelay(null);

  appointment.status = "cancelled";

  // Release the slot so the time becomes bookable again.
  store.claimedSlotIds.delete(appointment.slotId);

  return resolveAfterDelay({ ...appointment });
}

// ---------------------------------------------------------------------------
// Course action requests
// ---------------------------------------------------------------------------
//
// SIMULATED. `submitRequest` flips a status in memory and stops there. There
// is no TSS integration behind this yet -- nothing leaves the server, no
// registrar system is contacted, and no human is notified. The UI says so.

/**
 * The student context stamped onto a new request, assembled from the same
 * providers the rest of the app reads. Building it here means the form never
 * has to know how to derive a unit count.
 */
async function mockGetRequestPrefill(): Promise<CourseRequestPrefill> {
  const [student, courses, degree] = await Promise.all([
    getStudent(),
    getCourses(),
    getDegreeProgress(),
  ]);

  return {
    studentName: student.name,
    program: student.program,
    track: student.track,
    term: student.currentTerm,
    currentCourses: courses.map((course) => `${course.code} · ${course.title}`),
    currentUnits: courses.reduce((total, course) => total + course.units, 0),
    unitsCompleted: degree.unitsCompleted,
    unitsRequired: degree.unitsRequired,
  };
}

/** Create a draft. Drafts are not sent anywhere; they only exist locally. */
async function mockCreateRequest(
  input: CourseRequestInput,
): Promise<CourseRequest> {
  const store = readRequestStore();
  const prefill = await getRequestPrefill();

  const request: CourseRequest = {
    id: nextRequestId(),
    type: input.type,
    course: input.course.trim(),
    reason: input.reason.trim(),
    status: "draft",
    submittedAt: null,
    prefill,
  };

  store.requests.push(request);
  return resolveAfterDelay({ ...request });
}

/**
 * Move a draft to submitted.
 *
 * In a wired-up version this is where the TSS call would happen, and where a
 * failure would have to be handled. Today it stamps a timestamp.
 *
 * Idempotent by design: a request that is not a draft comes back unchanged
 * rather than being re-stamped or rejected, so a double-submitted form cannot
 * move an approved request back to "submitted".
 */
async function mockSubmitRequest(
  requestId: string,
): Promise<CourseRequest | null> {
  const store = readRequestStore();
  const request = store.requests.find((candidate) => candidate.id === requestId);

  if (!request) return resolveAfterDelay(null);
  if (request.status !== "draft") return resolveAfterDelay({ ...request });

  request.status = "submitted";
  request.submittedAt = new Date().toISOString();

  return resolveAfterDelay({ ...request });
}

/** All requests, drafts first then newest. Copies, so the store stays private. */
function mockGetMyRequests(): Promise<CourseRequest[]> {
  const { requests } = readRequestStore();

  const ordered = [...requests]
    .sort((a, b) => {
      // Drafts float to the top; they are the ones still needing action.
      if (!a.submittedAt && b.submittedAt) return -1;
      if (a.submittedAt && !b.submittedAt) return 1;
      return Date.parse(b.submittedAt ?? "0") - Date.parse(a.submittedAt ?? "0");
    })
    .map((request) => ({ ...request }));

  return resolveAfterDelay(ordered);
}

/** Whether the student record is "linked" to TSS. Simulated end to end. */
function mockGetTssConnection(): Promise<boolean> {
  return resolveAfterDelay(readRequestStore().tssConnected);
}

function mockConnectTss(): Promise<boolean> {
  const store = readRequestStore();
  store.tssConnected = true;
  return resolveAfterDelay(true);
}

// ---------------------------------------------------------------------------
// Living resume
// ---------------------------------------------------------------------------
//
// SIMULATED. "Auto-update" reads the same mock course and skill data the rest
// of the app uses and assembles a version from it. There is no file upload, no
// document parsing, and no external resume service.

function mockGetSkills(): Promise<Skill[]> {
  return resolveAfterDelay(mockSkills.map((skill) => ({ ...skill })));
}

/** Versions newest first. Copies, so the store stays private. */
function mockGetResumeVersions(): Promise<ResumeVersion[]> {
  const { versions } = readResumeStore();

  const ordered = [...versions]
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))
    .map((version) => ({ ...version }));

  return resolveAfterDelay(ordered);
}

function mockGetCurrentResume(): Promise<ResumeVersion | null> {
  const { versions } = readResumeStore();
  const current = versions.find((version) => version.isCurrent);
  return resolveAfterDelay(current ? { ...current } : null);
}

/**
 * Write a summary from what the student is actually studying.
 *
 * Deliberately template-driven rather than free-form: it is honest about
 * being generated, and it stays readable. A real version would hand the same
 * inputs to a model.
 */
function composeSummary(goal: string, program: string, skillNames: string[]) {
  const headline = skillNames.slice(0, 4).join(", ");
  return (
    `${program} candidate at UC San Diego working toward a ${goal} role. ` +
    `Coursework and projects across ${headline}` +
    (skillNames.length > 4 ? `, and ${skillNames.length - 4} more.` : ".")
  );
}

/**
 * Build a new version from current courses and skills, make it current, and
 * keep every earlier version.
 *
 * Returns the version alongside a diff, so the UI can say what changed rather
 * than just claiming something did.
 */
async function mockGenerateNewVersion(): Promise<{
  version: ResumeVersion;
  diff: ResumeDiff;
}> {
  const store = readResumeStore();
  const [student, courses] = await Promise.all([getStudent(), getCourses()]);

  const previous = store.versions.find((version) => version.isCurrent) ?? null;

  // Everything the student has now, not just what was on the last version.
  const skills = mockSkills.map((skill) => ({ ...skill }));
  const courseCodes = new Set(courses.map((course) => course.code));
  const resumeCourses = mockResumeCourses.filter((entry) =>
    courseCodes.has(entry.code),
  );

  const summary = composeSummary(
    student.goal,
    student.program,
    skills.map((skill) => skill.name),
  );

  const previousSkillNames = new Set(
    previous?.skills.map((skill) => skill.name) ?? [],
  );
  const previousCourseCodes = new Set(
    previous?.courses.map((entry) => entry.code) ?? [],
  );

  const diff: ResumeDiff = {
    addedSkills: skills
      .filter((skill) => !previousSkillNames.has(skill.name))
      .map((skill) => skill.name),
    addedCourses: resumeCourses
      .filter((entry) => !previousCourseCodes.has(entry.code))
      .map((entry) => `${entry.code} · ${entry.title}`),
    summaryChanged: previous?.summary !== summary,
  };

  const version: ResumeVersion = {
    id: nextVersionId(),
    label: `Regenerated from ${student.currentTerm} courses`,
    createdAt: new Date().toISOString(),
    summary,
    skills,
    courses: resumeCourses,
    // Experience is student-authored, so it carries forward untouched.
    experience: previous?.experience ?? [],
    isCurrent: true,
  };

  for (const existing of store.versions) existing.isCurrent = false;
  store.versions.push(version);

  return resolveAfterDelay({ version: { ...version }, diff });
}

/** Make an earlier version current again. History is never deleted. */
function mockSetCurrentVersion(
  versionId: string,
): Promise<ResumeVersion | null> {
  const store = readResumeStore();
  const target = store.versions.find((version) => version.id === versionId);

  if (!target) return resolveAfterDelay(null);

  for (const version of store.versions) {
    version.isCurrent = version.id === versionId;
  }

  return resolveAfterDelay({ ...target });
}

// ---------------------------------------------------------------------------
// Ask THRIVE
// ---------------------------------------------------------------------------
//
// SIMULATED, and more thoroughly than anything else here. There is no retrieval
// service, no index of program material, and no model behind these -- they read
// a fixture and stop. What they are is the SHAPE the real thing has to arrive
// in: a promise of conversations, newest first, and a promise of one by id.
//
// ## Why these are providers rather than a client-side store
//
// A conversation cannot live in `localStorage`. They are large, they grow
// without bound, and a student opening THRIVE on a second laptop would find an
// empty history indistinguishable from never having asked anything. So the
// history is server data from the start, mocked exactly the way every other
// surface in this app was, and the body of each function is the only thing that
// changes when there is something real to call.
//
// Nothing here mutates. See the note in `mock/conversations.ts` for why there
// is deliberately no fourth module-scope store.

/**
 * Saved conversations, newest first.
 *
 * Sorted here rather than in the page for the usual reason: every consumer
 * would otherwise redo it, and two consumers sorting independently is how a
 * rail and a list come to disagree about which conversation is the recent one.
 *
 * NOT filtered by destination. The filter is one predicate over a list the
 * caller already holds -- see `conversationsFor` in `$lib/ask` -- and a
 * per-destination provider would mean three round trips to render one rail that
 * shows a count for each.
 */
function mockGetConversations(): Promise<Conversation[]> {
  const conversations = buildMockConversations()
    .slice()
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    // Copies out, and the message arrays too: a shallow spread would hand the
    // caller the fixture's own array, and this is the one provider whose nested
    // collection a UI has an obvious reason to want to append to.
    .map((conversation) => ({
      ...conversation,
      messages: conversation.messages.map((message) => ({ ...message })),
    }));

  return resolveAfterDelay(conversations);
}

/**
 * One conversation by id, or null when there is no such thing.
 *
 * Null rather than a throw: a stale link to a conversation is an ordinary thing
 * to hold, and the page turns it into a 404 itself. Built on `getConversations`
 * so the copying rule has exactly one implementation.
 */
async function mockGetConversation(
  conversationId: string,
): Promise<Conversation | null> {
  const conversations = await getConversations();
  return conversations.find((entry) => entry.id === conversationId) ?? null;
}

// ---------------------------------------------------------------------------
// Job search
// ---------------------------------------------------------------------------
//
// SIMULATED. There is no job board integration and no scoring model behind
// these -- `mockSearchJobs` fakes relevance from overlap with the mock
// student's skills, and `mockGenerateMatchReport` derives a fixed-shape
// report the same way. Fixtures live in `mock/jobs.ts`; the shaping logic
// lives here, same split as every other mock surface in this file.

function toPosting(fixture: JobFixture): JobPosting {
  const { description: _description, ...posting } = fixture;
  return { ...posting, skills: [...posting.skills] };
}

function toDetail(fixture: JobFixture): JobPostingDetail {
  const { snippet: _snippet, ...detail } = fixture;
  return { ...detail, skills: [...detail.skills] };
}

/** Split a posting's skills against what the mock student's resume claims. */
function splitSkills(job: JobPosting) {
  const known = new Set(mockSkills.map((skill) => skill.name));
  return {
    matchedSkills: job.skills.filter((skill) => known.has(skill)),
    missingSkills: job.skills.filter((skill) => !known.has(skill)),
  };
}

/** Sample size and top skills across every posting sharing a title. */
function benchmarkFor(title: string): RoleBenchmark {
  const group = mockJobs.filter((job) => job.title === title);
  const counts = new Map<string, number>();

  for (const job of group) {
    for (const skill of job.skills) {
      counts.set(skill, (counts.get(skill) ?? 0) + 1);
    }
  }

  const topSkills = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, count]) => ({
      name,
      share: Math.round((count / group.length) * 100) / 100,
    }));

  return { sampleSize: group.length, topSkills };
}

/**
 * Terms filter across title, company, and skills. An empty query matches
 * everything, the same way an empty search box would show the full board.
 */
function mockSearchJobs(query: string): Promise<JobSearchResult> {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);

  const matches = mockJobs.filter((job) => {
    if (terms.length === 0) return true;
    const haystack = `${job.title} ${job.company} ${job.skills.join(" ")}`.toLowerCase();
    return terms.some((term) => haystack.includes(term));
  });

  // Fake relevance: more overlap with the mock profile scores higher, then
  // nudge each entry down by its rank so a tie still sorts strictly
  // descending -- a results list is more convincing without twins.
  const results: JobSearchEntry[] = matches
    .map((job) => {
      const { matchedSkills, missingSkills } = splitSkills(job);
      return {
        job: toPosting(job),
        score: 55 + matchedSkills.length * 9,
        matchedSkills,
        missingSkills,
      };
    })
    .sort((a, b) => b.score - a.score)
    .map((entry, index) => ({ ...entry, score: Math.max(35, entry.score - index) }));

  const primaryTitle = matches[0]?.title ?? mockJobs[0].title;

  return resolveAfterDelay({
    query,
    profileAvailable: true,
    benchmark: benchmarkFor(primaryTitle),
    results,
  });
}

/** One posting by id, with the benchmark for its title. */
function mockGetJobPosting(
  jobId: string,
): Promise<{ job: JobPostingDetail; benchmark: RoleBenchmark }> {
  const fixture = mockJobs.find((job) => job.id === jobId);
  if (!fixture) throw new Error(`Unknown job id: ${jobId}`);

  return resolveAfterDelay({
    job: toDetail(fixture),
    benchmark: benchmarkFor(fixture.title),
  });
}

function competencyFor(score: number): JobCompetency {
  if (score >= 85) return "strong";
  if (score >= 70) return "good";
  if (score >= 50) return "stretch";
  return "reach";
}

let nextReportId = 1;

/** A fixed, plausible report -- there is no scoring model behind this yet. */
function mockGenerateMatchReport(jobId: string): Promise<MatchReport> {
  const fixture = mockJobs.find((job) => job.id === jobId);
  const { matchedSkills, missingSkills } = fixture
    ? splitSkills(fixture)
    : { matchedSkills: [], missingSkills: [] };

  const score = Math.min(95, 50 + matchedSkills.length * 10);
  const competency = competencyFor(score);

  return resolveAfterDelay({
    id: `rep-${nextReportId++}`,
    jobId,
    score,
    competency,
    matchedSkills,
    gaps: missingSkills,
    verdict:
      competency === "strong" || competency === "good"
        ? "Your resume covers most of what this posting asks for."
        : "This posting asks for a few skills your resume doesn't show yet.",
    createdAt: new Date().toISOString(),
  });
}

/** No-op: nothing parses the file yet, this only simulates the round trip. */
function mockUploadResume(_file: File): Promise<void> {
  return resolveAfterDelay(undefined);
}

// ---------------------------------------------------------------------------
// Delegation: THRIVE_API_ORIGIN selects the Django implementations.
// ---------------------------------------------------------------------------

export function getStudent(): Promise<Student> {
  return apiEnabled() ? api.getStudent() : mockGetStudent();
}

export function getCourses(): Promise<Course[]> {
  return apiEnabled() ? api.getCourses() : mockGetCourses();
}

export function getSyllabi(): Promise<Syllabus[]> {
  return apiEnabled() ? api.getSyllabi() : mockGetSyllabi();
}

export function getAssignments(): Promise<Assignment[]> {
  return apiEnabled() ? api.getAssignments() : mockGetAssignments();
}

export function getTasks(): Promise<Task[]> {
  return apiEnabled() ? api.getTasks() : mockGetTasks();
}

export function getEvents(): Promise<Event[]> {
  return apiEnabled() ? api.getEvents() : mockGetEvents();
}

export function getDegreeProgress(): Promise<DegreeProgress> {
  return apiEnabled() ? api.getDegreeProgress() : mockGetDegreeProgress();
}

export function getProgramTimeline(): Promise<ProgramTimeline> {
  return apiEnabled() ? api.getProgramTimeline() : mockGetProgramTimeline();
}

export function getResources(): Promise<ResourceLink[]> {
  return apiEnabled() ? api.getResources() : mockGetResources();
}

export function getAdvisors(): Promise<Advisor[]> {
  return apiEnabled() ? api.getAdvisors() : mockGetAdvisors();
}

export function getSlots(advisorId: string): Promise<AppointmentSlot[]> {
  return apiEnabled() ? api.getSlots(advisorId) : mockGetSlots(advisorId);
}

export function getMyAppointments(): Promise<Appointment[]> {
  return apiEnabled() ? api.getMyAppointments() : mockGetMyAppointments();
}

export function bookAppointment(
  slotId: string,
  reason: string,
): Promise<Appointment> {
  return apiEnabled()
    ? api.bookAppointment(slotId, reason)
    : mockBookAppointment(slotId, reason);
}

export function cancelAppointment(
  appointmentId: string,
): Promise<Appointment | null> {
  return apiEnabled()
    ? api.cancelAppointment(appointmentId)
    : mockCancelAppointment(appointmentId);
}

export function getRequestPrefill(): Promise<CourseRequestPrefill> {
  return apiEnabled() ? api.getRequestPrefill() : mockGetRequestPrefill();
}

export function createRequest(
  input: CourseRequestInput,
): Promise<CourseRequest> {
  return apiEnabled() ? api.createRequest(input) : mockCreateRequest(input);
}

export function submitRequest(
  requestId: string,
): Promise<CourseRequest | null> {
  return apiEnabled()
    ? api.submitRequest(requestId)
    : mockSubmitRequest(requestId);
}

export function getMyRequests(): Promise<CourseRequest[]> {
  return apiEnabled() ? api.getMyRequests() : mockGetMyRequests();
}

export function getTssConnection(): Promise<boolean> {
  return apiEnabled() ? api.getTssConnection() : mockGetTssConnection();
}

export function connectTss(): Promise<boolean> {
  return apiEnabled() ? api.connectTss() : mockConnectTss();
}

export function getSkills(): Promise<Skill[]> {
  return apiEnabled() ? api.getSkills() : mockGetSkills();
}

export function getResumeVersions(): Promise<ResumeVersion[]> {
  return apiEnabled() ? api.getResumeVersions() : mockGetResumeVersions();
}

export function getCurrentResume(): Promise<ResumeVersion | null> {
  return apiEnabled() ? api.getCurrentResume() : mockGetCurrentResume();
}

export function generateNewVersion(): Promise<{
  version: ResumeVersion;
  diff: ResumeDiff;
}> {
  return apiEnabled() ? api.generateNewVersion() : mockGenerateNewVersion();
}

export function setCurrentVersion(
  versionId: string,
): Promise<ResumeVersion | null> {
  return apiEnabled()
    ? api.setCurrentVersion(versionId)
    : mockSetCurrentVersion(versionId);
}

export function getConversations(): Promise<Conversation[]> {
  return apiEnabled() ? api.getConversations() : mockGetConversations();
}

export function getConversation(
  conversationId: string,
): Promise<Conversation | null> {
  return apiEnabled()
    ? api.getConversation(conversationId)
    : mockGetConversation(conversationId);
}

export function searchJobs(query: string): Promise<JobSearchResult> {
  return apiEnabled() ? api.searchJobs(query) : mockSearchJobs(query);
}

export function getJobPosting(
  jobId: string,
): Promise<{ job: JobPostingDetail; benchmark: RoleBenchmark }> {
  return apiEnabled() ? api.getJobPosting(jobId) : mockGetJobPosting(jobId);
}

export function generateMatchReport(jobId: string): Promise<MatchReport> {
  return apiEnabled()
    ? api.generateMatchReport(jobId)
    : mockGenerateMatchReport(jobId);
}

export function uploadResume(file: File): Promise<void> {
  return apiEnabled() ? api.uploadResume(file) : mockUploadResume(file);
}
