---
id: "MGTA 495-MKTG"
code: "MGTA 495"
title: "Special Topics: Marketing Analytics"
department: "MGTA"
programme: "MSBA (Rady MS Business Analytics)"
units: 4
schedulable: true
is_core: false
technical_level: 4
workload: "moderate"
workload_basis: "Five substantial coding problem sets (~18% each) submitted as website blog posts; no exams; collaboration allowed."
grading: "Five assignments ~90%, engagement and website quality ~10%; no exams."
offerings: [{"term": "SP26", "season": "SP", "instructor": "Yavorsky", "format_notes": "Taught by Head of Analytics at GBK Collective (ex-Bain); no exams."}]
prerequisites: null
topics: ["A/B testing and causal inference", "regression discontinuity and diff-in-diff", "maximum likelihood and logit models", "conjoint analysis and Bayesian pricing", "customer segmentation", "variable importance and Shapley values", "cross-validation"]
skills: ["implementing statistical methods from scratch", "designing and analyzing experiments", "estimating consumer preferences", "optimal pricing via conjoint", "communicating results as blog posts", "building a portfolio website with Quarto and Git"]
tools: ["R", "Python", "Quarto", "Git"]
career_tags: ["marketing", "pricing", "machine-learning", "communication", "strategy-consulting"]
notes: "You leave with a public portfolio website of your coursework — a real asset for job searches."
units_note: "Catalog lists 2-4; quarter-long course."
syllabi: ["MGtA 495 Special Topics in Business Analytics - Marketing Analytics (Yavorsky) SP26.txt"]
---
# MGTA 495 — Special Topics: Marketing Analytics

**4 units** · MSBA (Rady MS Business Analytics) · offered SP26

## What this course covers

Develops technical, statistical, and communication skills for analytically-based
consumer insights. Five topics — experimentation/causal inference, preference
measurement via maximum likelihood, conjoint-based pricing with Bayesian methods,
segmentation via unsupervised learning, and driver analysis via supervised learning —
implemented 'by hand' in code and published as blog posts on a student-built portfolio
website.

## What you should be able to do afterwards

- implementing statistical methods from scratch
- designing and analyzing experiments
- estimating consumer preferences
- optimal pricing via conjoint
- communicating results as blog posts
- building a portfolio website with Quarto and Git

## Topics covered

A/B testing and causal inference, regression discontinuity and diff-in-diff, maximum likelihood and logit models, conjoint analysis and Bayesian pricing, customer segmentation, variable importance and Shapley values, cross-validation.

## Tools used

R, Python, Quarto, Git.

## Prerequisites

None stated in the syllabus.

## How it is graded

Five assignments ~90%, engagement and website quality ~10%; no exams.

## Workload

Moderate. Five substantial coding problem sets (~18% each) submitted as website blog posts; no exams; collaboration allowed.

## Offerings

- **SP26** — Yavorsky

## Syllabus text

_Verbatim from the syllabus PDF supplied by the Rady graduate programmes office._

### MGtA 495 Special Topics in Business Analytics - Marketing Analytics (Yavorsky) SP26

Syllabus
MGTA 495: Marketing Analytics
Spring 2025

Instructional Team
The professor for this course is Dan Yavorsky. Dan holds an MBA and PhD from UCLA Anderson and has
15 years of experience applying analytic and econometric techniques at consulting firms, including Bain &
Company. He is currently a Senior Vice President and the Head of Analytics at GBK Collective, a marketing
strategy and consumer insights firm.
Dan tries very hard to spend most of his time playing soccer with his kids, cycling with his brothers, sipping
bourbon with his wife, and curating his collections of mechanical keyboards, grandfatherly pocket knives,
boots, and statistics textbooks. In reality he spends most of his time consulting, teaching, raising kids, and
oscillating between being a hoarder and a minimalist.
Dan Yavorsky
• email: dyavorsky@ucsd.edu
• bio: website | LinkedIn | GBK bio
The TA for this course is Peichen Heather Li. She is finishing her PhD in marketing at UCSD Rady after
completing her MA in Industrial Organizational Psychology from NYU. Her research explores factors that
influence how people adopt feedback from AI systems.
Peichen Heather Li
• email: hel058@ucsd.edu
• LinkedIn

Logistics
Overview
We meet Fridays 1-4pm in 1E107
TA Office Hours via Zoom at 8-9pm PT on Tuesdays (only weeks with assignment due)
• There are 5 problem sets, submitted as blog posts to your personal website that we will build together
• There are no exams
•
•

Materials
All materials for this course are on (or linked from) Canvas: https://rady.instructure.com/courses/
2032.
Q&A
We will use Discussion Board within Canvas as the primary method of Q&A.

1

Course Introduction
Expert analysts are technically adept, statistically knowledgeable, and effective when communicating. This
course is designed to enable students to develop in each of those three areas. In addition, the best analysts
often have domain-specific expertise. Our focus in this course will be on analytically-based consumer insights
to inform marketing strategy.
Students begin the course using Quarto, Git, and the Command Line to build a personal website, which
will serve as a portfolio for their work in this course. We then structure the majority of the course around
5 marketing topics. For each topic, we spend half our time introducing and discussing the topic from a
business perspective. The other half is devoted to understanding the statistical methodology and analytic
techniques used in analysis related to the topic.
Each class session is followed by an application where students implement in R/Python/etc. the statistical
technique discussed in class on a dataset, and interpret their results to inform a marketing strategy. Students
report their approach, results, and recommendations in written posts on their personal websites.
I firmly believe in the idea that you don’t understand it until you code it. In that regard, implementation of
the analytic and statistical techniques will be done “by hand” and then compared to the results from routines
readily available in software packages. This enables students understand the underlying assumptions and
mechanics of the techniques, the limitations of the canned routines, and how students might approach an
extension or modification to canned routines when their need arises.
The course simulates a professional experience within the classroom and therefore require no memorization,
encourages collaboration, and ensures extensive resources (but limited time) to complete deliverables.

Topics
Our core marketing and statistical topics include:
1. Why and when are experiments the best choice?
(Experimentation via Classical Frequentist Statistics)
•
•

A/B testing and non-experimental methods for Causal Analysis
LLN, CLT, p-values, confidence intervals, regression discontinuity, differences-in-differences

2. How to measure consumer preferences using a survey and Best-Worst Scaling?
(Consumer Preference Measurement via the Method of Maximum Likelihood)
•
•

Introduction to Maximum Likelihood Estimations
Normal, Logit, and Multinomial Logit models

3. How to use conjoint analysis to set an optimal price?
(Pricing via Bayesian Statistics)
•
•

Introduction to Bayesian Statistics: Priors, Likelihoods, and Posteriors
Hierarchical Models

4. What are the various “types” of customers in the market?
(Segmentation via Unsupervised Machine Learning)
•
•

Distance-based, tree-based, and model-based methods of clustering for continuous and categorical data
K-means, Hierarchical, Density-based, 2-step, Mixture Models, and goodness-of-fit metrics

5. Which company practices are most important for customer satisfaction?
(Variable Importance via Supervised Machine Learning)
•
•

Bi-variate and Multi-variate models of association and Shapley Values
Cross Validation and Model Selection

2

Assignments and Grading
There are 5 assignments. Each assignment is worth approximately 18% of the final grade, the exact amount
may be adjusted to reflect the difficulty of the assignment.
The remaining 10% of the final grade is awarded for engagement and participation with the course, building
your website on time, completion of the course evaluation, and the overall quality of the assigned deliverables.
There are no exams.

Course Policies
Attendance
I strongly recommend regular attendance, as that can facilitate engagement and participation with the
course, but I will not formally assess it. You should proactively anticipate and manage issues you might
experience in balancing your efforts across courses or other obligations.
Collaboration
All assignments may be worked on in collaboration with other students. Collaboration is optional and groups
should be small. Each student is individually responsible for creating and submitting their own work.
Contacting Instructors
Please use Canvas Discussions as the primary method to ask questions about course content and assignments,
so that the instructor, TA, and other students can provide answers. For matters that pertain to you
individually (illness, questions about grading, etc.) please email the instructor and cc the TA (or vice-versa);
do not email us separately.
Use of AI Technology
You may use AI technology (e.g. ChatGPT) to help you develop an understanding of a topic or complete
an assignment, in much the same way that you may use online search (e.g. Google and Bing) and online
information sources (e.g. Wikipedia or StackOverflow). Recognize, however, that you are responsible for the
content of your work and that you must be able to explain and defend the content of your submissions. It is
plagiarism and a violation of UCSD Policy on the Integrity of Scholarship to copy work created by someone
else (or someone else’s technology) and pass it off as your own. Relevant additional information is available
in the FAQ of academicintegrity.ucsd.edu (link).
Late Submissions
Late deliverables will only be accepted in grave circumstances with documentation, such as serious illness
or death in the family, with some form of notification required prior to the deliverable due date. However,
at the discretion of the professor and TA, an assignment may be accepted late for partial credit. It should
be exceedingly rare that any student requests this and there is no guarantee that such a request will be
granted.
Re-grade Requests
Any request for regrading must be made in writing within two weeks of a deliverable being assessed but
before final course grades are submitted to the Registrar. The professor and/or TA will entirely regrade any
such deliverable, meaning that the resulting grade change may be positive or negative, depending on the
specifics of the situation.
3

Schedule

4

Important UCSD Topics

Academic Integrity
Academic Integrity is expected of everyone at UC San Diego. This means that you must be honest, fair,
responsible, respectful, and trustworthy in all of your actions. Lying, cheating, or any other forms of
dishonesty will not be tolerated because they undermine learning and the University’s ability to certify
students’ knowledge and abilities. Thus, any attempt to get, or help another get, a grade by cheating, lying,
or dishonesty will be reported to the Academic Integrity Office and will result in sanctions. Sanctions can
include an F in this class and suspension or dismissal from the University.
Integrity of scholarship is essential for an academic community. As members of the Rady School, we pledge
ourselves to uphold the highest ethical standards. The University expects that both faculty and students will
honor this principle and in so doing protect the validity of University intellectual work. For students, this
means that all academic work will be done by the individual to whom it is assigned, without unauthorized
aid of any kind.
You can learn more about academic integrity at:
https://academicintegrity.ucsd.edu/
The complete UCSD Policy on Integrity of Scholarship can be viewed at:
http://senate.ucsd.edu/Operating-Procedures/Senate-Manual/Appendices/2
All aspects of the UCSD honor code apply in this course. If you are ever unsure how they apply, please ask
your classmates, TA, or professor for clarification. It is much better to be conservative about honor code
violations than to take a risk. You can be suspended or expelled for cheating.

Students with Disabilities
A student who has a disability or special needs and requires an accommodation in order to have equal access
to the classroom must register with the Office for Students with Disabilities (OSD). The OSD will determine
what accommodations may be made and provide the necessary documentation to present to the instructor
and OSD liaison.
Students requesting accommodations for this course due to a disability must provide a current Authorization
for Accommodation (AFA) letter (paper or electronic) issued by the OSD. Students are required to discuss
accommodation arrangements with instructors and OSD liaisons in the department 72 business hours in
advance of any exams or assignments. No accommodations can be implemented retroactively.
Please visit the OSD website for further information or contact the Office for Students with Disabilities by
phone at 858-534-4382 or via email at osd@ucsd.edu.

NonDiscrimination Policy Statement
The University of California, in accordance with applicable Federal and State law and University policy, does
not discriminate on the basis of race, color, national origin, religion, sex, gender identity, pregnancy, physical
or mental disability, medical condition (cancer-related or genetic characteristics), ancestry, marital status,
age, sexual orientation, citizenship, or service in the uniformed services. The University also prohibits sexual
harassment. This nondiscrimination policy covers admission, access, and treatment in University programs
and activities.

5

Title IX
The Office for the Prevention of Harassment & Discrimination (OPHD) provides assistance to students,
faculty, and staff regarding reports of bias, harassment, and discrimination. OPHD is the UC San Diego Title
IX office. Title IX of the Education Amendments of 1972 is the federal law that prohibits sex discrimination
in educational institutions that are recipients of federal funds. Rady students have the right to an educational
environment that is free from harassment and discrimination.
You can make a complaint of harassment or discrimination – or simply make an appointment to find out
more information – by contacting OPHD:
•

by phone at 858-534-8298

•

by email at ophd@ucsd.edu

•

or online at the Overview for Students webpage

Students may feel more comfortable discussing their particular concern with a trusted employee. This may
be a Rady student affairs staff member, a department Chair, a faculty member, or other University official.
These individuals have an obligation to report incidents of sexual violence and sexual harassment to OPHD.
This does not necessarily mean that a formal complaint will be filed.
If you find yourself in an uncomfortable situation, ask for help. The Rady School of Management is committed
to upholding University policies regarding nondiscrimination, sexual violence, and sexual harassment.

Health and Well-Being
Throughout your time at UC San Diego, you may experience a range of issues that can negatively impact
your learning. These may include physical illness, housing or food insecurity, strained relationships, loss of
motivation, depression, anxiety, high levels of stress, alcohol and drug problems, feeling down, interpersonal
or sexual violence, or grief.
These concerns or stressful events may lead to diminished academic performance and affect your ability to
participate in day-to-day activities. If there are issues related to coursework that are a source of particular
stress or challenge, please speak with your professors so that we are able to support you. In addition, UC
San Diego provides a number of resources to all enrolled students, including:
•

Counseling and Psychological Services: 858-534-3755 or caps.ucsd.edu

•

Student Health Services: 858-534-3300 or studenthealth.ucsd.edu

•

CARE at the Sexual Assault Resource Center: 858-534-5793 or care.ucsd.edu

•

The Hub Basic Needs Center: 858-246-2632 or basicneeds.ucsd.edu

6

