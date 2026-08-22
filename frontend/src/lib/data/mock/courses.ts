import type { Course } from "../types";
import { at, FRI, MON, THU, TUE, upcomingWeekday, WED } from "./relative-dates";

/**
 * Merna's four courses this term.
 *
 * MGT 253 is the one carrying a nudge. Exactly one course in trouble is the
 * point: it makes "focus here this week" legible instead of leaving the
 * student to compare four progress bars and guess.
 */
export function buildMockCourses(): Course[] {
  return [
    {
      id: "crs-142",
      code: "MGT 142",
      title: "Machine Learning for Business",
      instructor: "Prof. Nijs",
      term: "Summer 2026",
      units: 4,
      progress: 72,
      standing: "onTrack",
      syllabusId: "syl-142",
      currentGrade: "A-",
      nextAssignment: {
        title: "Problem Set 3",
        due: upcomingWeekday(FRI, { hour: 23, minute: 59 }),
      },
      schedule: [
        {
          dayOfWeek: MON,
          startTime: "09:30",
          endTime: "11:20",
          location: "Otterson Hall 2S111",
        },
        {
          dayOfWeek: WED,
          startTime: "09:30",
          endTime: "11:20",
          location: "Otterson Hall 2S111",
        },
      ],
    },
    {
      id: "crs-100",
      code: "MGT 100",
      title: "Data Management & SQL",
      instructor: "Prof. Rivera",
      term: "Summer 2026",
      units: 4,
      progress: 60,
      standing: "watch",
      syllabusId: "syl-100",
      currentGrade: "B",
      nextAssignment: {
        title: "Lab 4: Joins",
        due: at(1, 23, 59),
      },
      schedule: [
        {
          dayOfWeek: TUE,
          startTime: "11:00",
          endTime: "12:50",
          location: "Otterson Hall 1S118",
        },
        {
          dayOfWeek: THU,
          startTime: "11:00",
          endTime: "12:50",
          location: "Otterson Hall 1S118",
        },
      ],
    },
    {
      id: "crs-253",
      code: "MGT 253",
      title: "Data Visualization",
      instructor: "Prof. Kim",
      term: "Summer 2026",
      units: 4,
      progress: 45,
      standing: "needsHelp",
      syllabusId: "syl-253",
      currentGrade: "C+",
      nudge: "Grade slipped to C+. Focus here this week.",
      nextAssignment: {
        title: "Dashboard project",
        due: upcomingWeekday(MON, { hour: 23, minute: 59 }),
      },
      schedule: [
        {
          dayOfWeek: WED,
          startTime: "14:00",
          endTime: "15:50",
          location: "Wells Fargo Hall 1N108",
        },
      ],
    },
    {
      id: "crs-256",
      code: "MGT 256",
      title: "Marketing Analytics",
      instructor: "Prof. Alvarez",
      term: "Summer 2026",
      units: 2,
      progress: 80,
      standing: "onTrack",
      syllabusId: "syl-256",
      currentGrade: "A",
      nextAssignment: {
        title: "Quiz 5",
        due: upcomingWeekday(FRI, { hour: 10, minute: 0 }),
      },
      schedule: [
        {
          dayOfWeek: FRI,
          startTime: "10:00",
          endTime: "11:50",
          location: "Otterson Hall 3E202",
        },
      ],
    },
  ];
}
