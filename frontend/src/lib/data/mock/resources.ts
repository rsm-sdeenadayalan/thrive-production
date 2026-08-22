import type { ResourceLink } from "../types";

export const mockResources: ResourceLink[] = [
  {
    id: "res-001",
    title: "Career Management Center",
    description:
      "Resume reviews, mock interviews, and employer connections for Rady students.",
    url: "https://rady.ucsd.edu/career/",
    category: "career",
    owner: "Rady Career Management",
  },
  {
    id: "res-002",
    title: "MSBA Academic Advising",
    description:
      "Degree planning, elective selection, and petitions for the MSBA program.",
    url: "https://rady.ucsd.edu/programs/masters-programs/msba/",
    category: "academic",
    owner: "MSBA Program Office",
  },
  {
    id: "res-003",
    title: "UCSD Counseling and Psychological Services",
    description:
      "Confidential mental health support, drop-in hours, and crisis resources.",
    url: "https://caps.ucsd.edu/",
    category: "wellness",
    owner: "UC San Diego CAPS",
  },
  {
    id: "res-004",
    title: "Research Computing and Data Services",
    description:
      "Cluster access, GPU allocations, and help with large-scale data workflows.",
    url: "https://blink.ucsd.edu/technology/computing/",
    category: "technical",
    owner: "UCSD IT Services",
  },
  {
    id: "res-005",
    title: "Registrar: Enrollment and Deadlines",
    description:
      "Enrollment appointments, add/drop deadlines, and the academic calendar.",
    url: "https://students.ucsd.edu/academics/enroll/",
    category: "administrative",
    owner: "Office of the Registrar",
  },
  {
    id: "res-006",
    title: "Rady Library Guides",
    description:
      "Industry reports, market data, and database access curated for business analytics.",
    url: "https://ucsd.libguides.com/",
    category: "academic",
    owner: "UCSD Library",
  },
];
