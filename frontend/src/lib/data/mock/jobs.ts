import type { JobPosting } from "../types";
import { at } from "./relative-dates";

/** A fixture posting: everything `JobPosting` has, plus the long-form body
 *  that only the detail view (`JobPostingDetail`) shows. */
export interface JobFixture extends JobPosting {
  description: string;
}

/**
 * Six postings across three titles -- enough for a search to look real and
 * for a per-title benchmark to mean something more than "the one job that
 * matched".
 */
export const mockJobs: JobFixture[] = [
  {
    id: "job-1",
    title: "Data Analyst",
    company: "Bloom Analytics",
    location: "San Diego, CA",
    url: "https://example.com/jobs/bloom-analytics-data-analyst",
    source: "greenhouse",
    skills: ["SQL", "Excel", "Data visualization", "Tableau", "Python"],
    postedAt: at(-3),
    snippet:
      "Own weekly reporting for the growth team and turn ad-hoc questions into repeatable dashboards.",
    description:
      "Bloom Analytics is looking for a Data Analyst to support the growth team. You will build and maintain Tableau dashboards, write SQL against our warehouse, and partner with marketing to turn one-off questions into self-serve reports. Comfort with Excel for quick turnarounds and basic Python for cleanup scripts is expected.",
  },
  {
    id: "job-2",
    title: "Data Analyst",
    company: "Meridian Health Systems",
    location: "Remote",
    url: "https://example.com/jobs/meridian-health-data-analyst",
    source: "lever",
    skills: ["SQL", "Python", "Data visualization", "Statistics", "Power BI"],
    postedAt: at(-6),
    snippet:
      "Analyze patient outcomes data and build Power BI reports for clinical operations leadership.",
    description:
      "Meridian Health Systems is hiring a Data Analyst for the clinical operations analytics team. Day to day work is SQL against a claims and outcomes warehouse, Power BI reporting for department leads, and light statistical analysis to support quality initiatives. Python is used for data cleaning pipelines.",
  },
  {
    id: "job-3",
    title: "Data Analyst",
    company: "Coastal Retail Group",
    location: "San Diego, CA",
    url: "https://example.com/jobs/coastal-retail-data-analyst",
    source: "company site",
    skills: ["SQL", "Excel", "A/B testing", "Data visualization"],
    postedAt: at(-10),
    snippet:
      "Support merchandising with SQL reporting and read out A/B test results for the e-commerce site.",
    description:
      "Coastal Retail Group's merchandising analytics team needs an analyst who can write SQL against our sales and inventory tables, build clear visualizations for weekly business reviews, and read out results from the e-commerce team's A/B tests. Excel is still how findings reach store operations, so fluency there matters.",
  },
  {
    id: "job-4",
    title: "Data Scientist",
    company: "Nimbus AI",
    location: "San Francisco, CA (hybrid)",
    url: "https://example.com/jobs/nimbus-ai-data-scientist",
    source: "greenhouse",
    skills: ["Python", "Machine learning", "Model evaluation", "SQL", "Statistics"],
    postedAt: at(-2),
    snippet:
      "Build and evaluate ML models for a fraud-detection product used by mid-market fintechs.",
    description:
      "Nimbus AI builds fraud-detection tooling for mid-market fintechs. As a Data Scientist you will design features, train and evaluate models in Python, and work with SQL to pull training data from our warehouse. A statistics background is expected for designing offline evaluation that holds up in production.",
  },
  {
    id: "job-5",
    title: "Data Scientist",
    company: "Harbor Freight Analytics",
    location: "Remote",
    url: "https://example.com/jobs/harbor-freight-data-scientist",
    source: "lever",
    skills: ["Python", "Machine learning", "Deep learning", "SQL", "Model evaluation"],
    postedAt: at(-8),
    snippet:
      "Forecast freight demand with a mix of classical ML and deep learning models.",
    description:
      "Harbor Freight Analytics forecasts shipping demand for logistics customers. This role builds both classical ML and deep learning forecasting models in Python, evaluates them against held-out shipment history, and maintains the SQL pipelines that feed training data.",
  },
  {
    id: "job-6",
    title: "Product Analyst",
    company: "Lightpath Software",
    location: "San Diego, CA",
    url: "https://example.com/jobs/lightpath-product-analyst",
    source: "company site",
    skills: ["SQL", "A/B testing", "Data visualization", "Product analytics", "Python"],
    postedAt: at(-5),
    snippet:
      "Design and read out experiments for the onboarding funnel alongside product managers.",
    description:
      "Lightpath Software's product analytics team partners directly with product managers to design experiments, read out results, and build the dashboards that track the onboarding funnel. Strong SQL and A/B testing fundamentals matter most; Python is used for anything a dashboard tool can't express.",
  },
];
