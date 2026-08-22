import type { Event, EventType } from "../types";
import { at } from "./relative-dates";

/**
 * A busy, plausible events calendar.
 *
 * Generated rather than hand-listed: two months of hand-written fixtures would
 * be unmaintainable and would drift out of date. A small catalogue is rotated
 * across the days ahead, so most days have something without every day looking
 * identical.
 *
 * Deterministic on purpose. `Math.random()` here would hand back a different
 * calendar on every render and desynchronise the server from the client.
 */

interface EventTemplate {
  title: string;
  type: EventType;
  /** Fits a Data Scientist goal, so it earns a "For you" badge. */
  relevant: boolean;
  location: string;
  hour: number;
  minute: number;
  durationMinutes: number;
  description: string;
  registerUrl?: string;
}

const CATALOG: EventTemplate[] = [
  // --- career -----------------------------------------------------------
  {
    title: "Data Science Career Fair",
    type: "career",
    relevant: true,
    location: "Rady Hall",
    hour: 11,
    minute: 0,
    durationMinutes: 240,
    description:
      "Twenty-two employers hiring analytics and data science roles.",
    registerUrl: "https://rady.ucsd.edu/events/ds-career-fair",
  },
  {
    title: "Analytics Alumni Panel",
    type: "career",
    relevant: true,
    location: "Otterson Hall 2S111",
    hour: 17,
    minute: 30,
    durationMinutes: 90,
    description: "Four MSBA alumni now working as data scientists.",
    registerUrl: "https://rady.ucsd.edu/events/alumni-panel",
  },
  {
    title: "Resume Lab",
    type: "career",
    relevant: true,
    location: "CMC Office",
    hour: 13,
    minute: 0,
    durationMinutes: 120,
    description: "Drop in for a line-by-line review with a career coach.",
  },
  {
    title: "Mock Interview Clinic",
    type: "career",
    relevant: true,
    location: "CMC Office",
    hour: 15,
    minute: 0,
    durationMinutes: 120,
    description: "Practice technical and behavioural rounds, with feedback.",
  },
  {
    title: "Employer Coffee Chat: Fintech Analytics",
    type: "career",
    relevant: true,
    location: "Rady Commons",
    hour: 9,
    minute: 0,
    durationMinutes: 60,
    description: "Informal conversation with two analytics hiring managers.",
  },
  // --- club -------------------------------------------------------------
  {
    title: "AI Club: Kaggle Night",
    type: "club",
    relevant: true,
    location: "Wells Fargo Hall 2E115",
    hour: 18,
    minute: 0,
    durationMinutes: 180,
    description: "Team up on an active Kaggle competition.",
  },
  {
    title: "Product Club Mixer",
    type: "club",
    relevant: false,
    location: "Rady Commons",
    hour: 17,
    minute: 0,
    durationMinutes: 120,
    description: "Meet the product management side of the cohort.",
  },
  {
    title: "Women in Analytics Meetup",
    type: "club",
    relevant: true,
    location: "Otterson Hall 1S118",
    hour: 12,
    minute: 0,
    durationMinutes: 60,
    description: "Lunch discussion on breaking into technical analytics roles.",
  },
  {
    title: "Consulting Club Case Prep",
    type: "club",
    relevant: false,
    location: "Otterson Hall 3E202",
    hour: 18,
    minute: 30,
    durationMinutes: 90,
    description: "Paired case practice, all levels welcome.",
  },
  // --- rady -------------------------------------------------------------
  {
    title: "Tableau Workshop",
    type: "rady",
    relevant: true,
    location: "Otterson Hall 1S118",
    hour: 13,
    minute: 0,
    durationMinutes: 120,
    description: "Hands-on dashboard building, useful for the MGT 253 project.",
  },
  {
    title: "Faculty Research Talk: Causal ML",
    type: "rady",
    relevant: true,
    location: "Wells Fargo Hall 1N108",
    hour: 12,
    minute: 0,
    durationMinutes: 60,
    description: "Recent work on treatment effects in large observational data.",
  },
  {
    title: "Rady Speaker Series",
    type: "rady",
    relevant: false,
    location: "Otterson Hall 2S111",
    hour: 16,
    minute: 0,
    durationMinutes: 90,
    description: "This week: scaling operations in a growth-stage company.",
  },
  {
    title: "SQL Clinic",
    type: "rady",
    relevant: true,
    location: "Rady Lab 2W",
    hour: 10,
    minute: 0,
    durationMinutes: 90,
    description: "Bring a query that is not working and leave with it working.",
  },
  // --- ucsd -------------------------------------------------------------
  {
    title: "Grad Student Mixer",
    type: "ucsd",
    relevant: false,
    location: "Price Center Ballroom",
    hour: 18,
    minute: 0,
    durationMinutes: 180,
    description: "Cross-program social for graduate students.",
  },
  {
    title: "Career Center Webinar",
    type: "ucsd",
    relevant: true,
    location: "Online",
    hour: 12,
    minute: 0,
    durationMinutes: 60,
    description: "Negotiating your first offer, run by the campus career centre.",
  },
  {
    title: "Wellness Hour",
    type: "ucsd",
    relevant: false,
    location: "Recreation Center",
    hour: 8,
    minute: 0,
    durationMinutes: 60,
    description: "Guided stretch and reset before the teaching day.",
  },
  {
    title: "Grad Writing Workshop",
    type: "ucsd",
    relevant: false,
    location: "Geisel Library",
    hour: 14,
    minute: 0,
    durationMinutes: 90,
    description: "Structuring a technical write-up for a non-technical reader.",
  },
  // --- sandiego ---------------------------------------------------------
  {
    title: "SD Tech Meetup",
    type: "sandiego",
    relevant: true,
    location: "Downtown San Diego",
    hour: 18,
    minute: 30,
    durationMinutes: 120,
    description: "Local data and ML practitioners, open to students.",
  },
  {
    title: "PyData San Diego",
    type: "sandiego",
    relevant: true,
    location: "UTC Innovation Hub",
    hour: 18,
    minute: 0,
    durationMinutes: 150,
    description: "Talks on the Python data stack, plus an open lightning slot.",
  },
  {
    title: "Analytics Happy Hour",
    type: "sandiego",
    relevant: false,
    location: "Little Italy",
    hour: 17,
    minute: 30,
    durationMinutes: 120,
    description: "Casual meetup for San Diego analytics folks.",
  },
];

/** How far ahead to publish. Roughly the rest of this month plus the next. */
const HORIZON_DAYS = 60;

/** ISO timestamp `minutes` after an ISO timestamp. */
function addMinutes(iso: string, minutes: number): string {
  const date = new Date(iso);
  date.setMinutes(date.getMinutes() + minutes);
  return date.toISOString();
}

/**
 * Events from today forward.
 *
 * Nothing is generated in the past: `getEvents` drops finished events anyway,
 * and a registerable event you cannot attend is noise on the calendar.
 */
export function buildMockEvents(): Event[] {
  const events: Event[] = [];
  const nowHour = new Date().getHours();

  for (let dayOffset = 0; dayOffset < HORIZON_DAYS; dayOffset += 1) {
    // Leaves roughly one day in nine clear, so "most days" has something
    // without the month looking machine-filled.
    if ((dayOffset * 4 + 1) % 9 === 0) continue;

    // Today draws only from times still ahead. Otherwise a morning pick would
    // be generated and then immediately dropped by `getEvents`, leaving the
    // default view of the calendar empty for no good reason.
    const pool =
      dayOffset === 0
        ? CATALOG.filter((template) => template.hour > nowHour)
        : CATALOG;

    if (pool.length === 0) continue;

    const count = Math.min(2 + ((dayOffset * 5 + 3) % 3), pool.length); // 2-4

    // Rotate the catalogue by the day, then take every third entry. Distinct
    // by construction, varied across types, and stable for a given day.
    const start = (dayOffset * 3) % pool.length;
    const rotated = [...pool.slice(start), ...pool.slice(0, start)];
    const chosen = rotated.filter((_, index) => index % 3 === 0).slice(0, count);

    chosen.forEach((template, i) => {
      const startISO = at(dayOffset, template.hour, template.minute);

      events.push({
        id: `evt-${dayOffset}-${i}`,
        title: template.title,
        type: template.type,
        start: startISO,
        end: addMinutes(startISO, template.durationMinutes),
        location: template.location,
        description: template.description,
        registerUrl: template.registerUrl,
        relevantToGoal: template.relevant,
      });
    });
  }

  return events;
}
