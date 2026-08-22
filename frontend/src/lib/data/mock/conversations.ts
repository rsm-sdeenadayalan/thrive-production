import type { Conversation } from "../types";
import { at } from "./relative-dates";

/**
 * Saved Ask THRIVE conversations.
 *
 * ## A pure fixture, deliberately not a store
 *
 * The other three mock modules that back a mutable surface -- appointments,
 * requests, resume -- hold a module-scope object and are the reason
 * MIGRATION.md section 9 defect 1 is graded BLOCKING. This one holds none, and
 * that is a decision rather than an omission: a conversation is written by a
 * retrieval service that does not exist, so there is nothing to write yet, and a
 * store here would be a fourth process-global object inherited for no benefit.
 *
 * What the UI does with a message the student sends before there is a backend is
 * the composer's problem, and the answer is component-local state that is gone
 * on navigation -- said out loud on screen. Nothing pretends to persist.
 *
 * ## Built when a provider is called
 *
 * `buildMockConversations()` is a function, not a const, for the same reason
 * `buildMockCourses` is: `at()` reads the clock, and a module-level const would
 * freeze the history at whenever the server started. A dev session left open
 * overnight would show "Today" against yesterday.
 *
 * ## Content
 *
 * Real MSBA questions with THRIVE answering plausibly, because the shell has to
 * be designed against message lengths a student would actually produce -- a
 * two-line answer and a six-line one wrap very differently. None of it is
 * generated at runtime and none of it is a claim about what the real assistant
 * will say.
 */
export function buildMockConversations(): Conversation[] {
  return [
    {
      id: "conv-001",
      destination: "resources",
      title: "Withdrawing from a course after week 2",
      updatedAt: at(-1, 16, 12),
      messages: [
        {
          id: "conv-001-m1",
          role: "student",
          body: "What happens to my transcript if I drop a course after the second week?",
          sentAt: at(-1, 16, 8),
        },
        {
          id: "conv-001-m2",
          role: "thrive",
          body: "After the second week a drop is recorded as a W on your transcript rather than disappearing from it. A W does not affect your GPA, but the units still count toward the enrolment you were billed for, and international students should check the effect on full-time status before filing. The petition goes through your graduate student advisor, not the registrar directly.",
          sentAt: at(-1, 16, 9),
        },
        {
          id: "conv-001-m3",
          role: "student",
          body: "Does that deadline shift in a quarter with a holiday in it?",
          sentAt: at(-1, 16, 11),
        },
        {
          id: "conv-001-m4",
          role: "thrive",
          body: "No. The drop deadlines are set by calendar week of instruction, so a campus holiday inside the quarter does not move them.",
          sentAt: at(-1, 16, 12),
        },
      ],
    },
    {
      id: "conv-002",
      destination: "courses",
      title: "Electives for a product analytics path",
      updatedAt: at(-3, 11, 40),
      messages: [
        {
          id: "conv-002-m1",
          role: "student",
          body: "I want to end up in product analytics. Which electives actually matter for that?",
          sentAt: at(-3, 11, 35),
        },
        {
          id: "conv-002-m2",
          role: "thrive",
          body: "Experimentation and causal inference is the one that shows up in almost every product analytics interview — A/B testing is the daily work. Pair it with a data engineering elective so you can get your own data out rather than waiting on someone, and one course with a heavy presentation component, because the job is mostly convincing a product manager of something. Deep learning is optional for this path and often crowds out the first two.",
          sentAt: at(-3, 11, 37),
        },
        {
          id: "conv-002-m3",
          role: "student",
          body: "Can I take experimentation and data engineering in the same quarter?",
          sentAt: at(-3, 11, 39),
        },
        {
          id: "conv-002-m4",
          role: "thrive",
          body: "You can, and people do, but both carry weekly assignments with real compute time. If you are also interviewing that quarter, split them.",
          sentAt: at(-3, 11, 40),
        },
      ],
    },
    {
      id: "conv-003",
      destination: "career",
      title: "Answering the salary question in a first screen",
      updatedAt: at(-6, 9, 21),
      messages: [
        {
          id: "conv-003-m1",
          role: "student",
          body: "A recruiter asked my expected salary in the first call and I froze. What should I have said?",
          sentAt: at(-6, 9, 18),
        },
        {
          id: "conv-003-m2",
          role: "thrive",
          body: "You are allowed to not answer first. Something like \"I'd rather understand the scope before naming a number — what range is budgeted for the role?\" is a normal thing to say and recruiters hear it constantly. In California they have to give you the range if you ask for it. If you are pushed, give a band rather than a point, anchored on published data for the title and city rather than on what you earned before.",
          sentAt: at(-6, 9, 20),
        },
        {
          id: "conv-003-m3",
          role: "student",
          body: "What if the range they give is below what I need?",
          sentAt: at(-6, 9, 21),
        },
      ],
    },
    {
      id: "conv-004",
      destination: "resources",
      title: "Getting a laptop loan for the quarter",
      updatedAt: at(-11, 14, 5),
      messages: [
        {
          id: "conv-004-m1",
          role: "student",
          body: "My laptop cannot handle the compute for one of my classes. Is there anything on campus?",
          sentAt: at(-11, 14, 2),
        },
        {
          id: "conv-004-m2",
          role: "thrive",
          body: "Two routes. The library runs a quarter-long laptop loan that you request at the start of the term, and it goes quickly. Separately, most compute-heavy coursework is meant to run on the school's cluster rather than locally — if a course expects that and you are running it on your own machine, that is worth raising with the instructor before borrowing hardware you may not need.",
          sentAt: at(-11, 14, 5),
        },
      ],
    },
    {
      id: "conv-005",
      destination: "courses",
      title: "Whether an audit counts toward the degree",
      updatedAt: at(-19, 10, 55),
      messages: [
        {
          id: "conv-005-m1",
          role: "student",
          body: "If I audit a course does it count for anything?",
          sentAt: at(-19, 10, 52),
        },
        {
          id: "conv-005-m2",
          role: "thrive",
          body: "It does not count toward units or the degree audit, and it does not appear on your transcript as a completed course. It is worth doing anyway when you want the material for a specific interview and cannot fit the graded version — but plan it as time you are spending, not as progress you are making.",
          sentAt: at(-19, 10, 55),
        },
      ],
    },
  ];
}
