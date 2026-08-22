import type {
  Advisor,
  Appointment,
  AppointmentSlot,
  MeetingMode,
} from "../types";
import { startOfToday } from "./relative-dates";

export const mockAdvisors: Advisor[] = [
  {
    id: "adv-gsa",
    name: "Amber Hanna",
    role: "Graduate Student Advisor",
    service: "advising",
    location: "Rady 2S111",
    blurb:
      "Course planning, electives, petitions, and anything about your degree audit.",
  },
  {
    id: "adv-cmc",
    name: "Nelitza Morales",
    role: "Career Coach",
    service: "career",
    location: "CMC office / Zoom",
    blurb:
      "Resume reviews, interview prep, and mapping a path toward your goal role.",
  },
];

/**
 * The times each advisor holds open, as local wall clock. Amber keeps
 * half-hour starts, the CMC works on the hour -- small differences like this
 * are what stop mock data reading as generated.
 */
const SLOT_TIMES: Record<string, string[]> = {
  "adv-gsa": ["09:30", "10:30", "11:30", "14:00", "15:00"],
  "adv-cmc": ["10:00", "11:00", "13:00", "14:00", "15:00", "16:00"],
};

const SLOT_MINUTES = 30;

/**
 * How many business days of availability to publish.
 *
 * ## Back to 5, and why
 *
 * Raised to 25 in Phase 8 when the day picker became a month calendar: five days
 * marked one week of a 42-cell grid and left the rest looking like an advisor who
 * never works.
 *
 * The month calendar has been reverted and the CHIP STRIP is the picker again, so
 * the number goes back with it. A strip is a fixed row of visible options, and 25
 * business days would be 25 chips -- which is not a strip, it is a grid drawn in
 * one line. The alternative was keeping the wider fixture and showing only the
 * first few chips, but then a student's availability would exist and be
 * unreachable, which is worse than a shorter window honestly stated.
 *
 * So the window IS the fixture again: `bookingDays()` publishes five business
 * days, the strip shows those five, and the page's copy says so. There is no
 * separate one-calendar-month rule any more -- `bookingWindowEnd` and
 * `isBookableDay` went with the grid, because with the fixture and the window the
 * same thing there was nothing left for them to disagree about.
 */
export const BOOKING_WINDOW_DAYS = 5;

/**
 * The next N business days, starting today. Weekends are skipped rather than
 * shown empty, so the day picker never offers a Saturday with nothing in it.
 */
export function bookingDays(from: Date = startOfToday()): Date[] {
  const days: Date[] = [];
  const cursor = new Date(from);

  while (days.length < BOOKING_WINDOW_DAYS) {
    const day = cursor.getDay();
    if (day !== 0 && day !== 6) {
      days.push(new Date(cursor));
    }
    cursor.setDate(cursor.getDate() + 1);
  }

  return days;
}

/**
 * Availability is derived, not random.
 *
 * `Math.random()` here would hand back a different calendar on every render
 * and desynchronise the server from the client. This hash is stable for a
 * given advisor, day, and time, so the same slot is taken every time it is
 * asked about -- while still looking irregular.
 */
function isTaken(advisorId: string, dayIndex: number, timeIndex: number) {
  const seed = advisorId.length * 7 + dayIndex * 3 + timeIndex * 5;
  return seed % 4 === 0;
}

function modeFor(
  advisorId: string,
  dayIndex: number,
  timeIndex: number,
): MeetingMode {
  // The CMC leans remote, the GSA leans in person. Both offer some of each.
  const remoteBias = advisorId === "adv-cmc" ? 1 : 2;
  return (dayIndex + timeIndex) % 3 < remoteBias ? "zoom" : "in person";
}

/**
 * Generate the published slots for an advisor.
 *
 * IDs are deterministic (`slot-<advisor>-<day>-<time>`) so a booking recorded
 * against an ID still resolves on the next request, even though the slot list
 * itself is rebuilt each time from "today".
 *
 * ## What is and is not deterministic
 *
 * MIGRATION.md section 2 calls both the ids and the availability
 * deterministic. The ids are, and so is `isTaken` -- but `available` is
 * `!inThePast && !isTaken(...)`, and `inThePast` reads the clock. So for a
 * fixed instant the output is fully determined by `advisorId`; across
 * instants, today's earlier slots drop out one by one as the day passes, and
 * the whole window shifts when the date rolls over. Freeze the clock to
 * assert on it.
 */
export function buildSlotsFor(advisorId: string): AppointmentSlot[] {
  const times = SLOT_TIMES[advisorId] ?? [];
  const slots: AppointmentSlot[] = [];

  bookingDays().forEach((day, dayIndex) => {
    times.forEach((time, timeIndex) => {
      const [hour, minute] = time.split(":").map(Number);

      const start = new Date(day);
      start.setHours(hour, minute, 0, 0);

      const end = new Date(start);
      end.setMinutes(end.getMinutes() + SLOT_MINUTES);

      // A slot that has already passed today is not bookable.
      const inThePast = start.getTime() < Date.now();

      slots.push({
        id: `slot-${advisorId}-${dayIndex}-${timeIndex}`,
        advisorId,
        start: start.toISOString(),
        end: end.toISOString(),
        mode: modeFor(advisorId, dayIndex, timeIndex),
        available: !inThePast && !isTaken(advisorId, dayIndex, timeIndex),
      });
    });
  });

  return slots;
}

/**
 * In-memory booking store.
 *
 * Module-level state is the honest shape of "mock backend": it survives
 * across requests within the running server, which is what makes a booking
 * still be there after a page navigation. It resets on restart or hot reload,
 * and it is shared by every visitor -- both fine for a prototype, and both
 * gone the moment `providers.ts` points at Django.
 *
 * ## Known, inherited, and BLOCKING
 *
 * Being process-global means several students testing at once book over each
 * other and see each other's appointments. MIGRATION.md section 9 defect 1
 * grades this BLOCKING ahead of a control group. An adapter-node process has
 * exactly the same module-scope hazard the Next server had, so this port
 * inherits the bug verbatim rather than fixing it. Django is the fix, and this
 * store is what Django replaces.
 */
interface BookingStore {
  appointments: Appointment[];
  /** Slot IDs claimed during this session, on top of the seeded ones. */
  claimedSlotIds: Set<string>;
  nextId: number;
}

const store: BookingStore = {
  appointments: [],
  claimedSlotIds: new Set(),
  nextId: 1,
};

export function readStore(): BookingStore {
  return store;
}

/**
 * The next appointment id.
 *
 * Starts at 1 and this store seeds empty, so `apt-001` is free. That is luck,
 * not design: the generator counts independently of whatever the seed put in
 * the store, so anyone who adds a seeded appointment must move `nextId` past
 * it by hand. The requests and resume stores both carry the same hazard --
 * see the note on `nextRequestId`.
 */
export function nextAppointmentId(): string {
  return `apt-${String(store.nextId++).padStart(3, "0")}`;
}
