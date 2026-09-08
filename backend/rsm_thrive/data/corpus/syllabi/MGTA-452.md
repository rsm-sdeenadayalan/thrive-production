---
id: "MGTA 452"
code: "MGTA 452"
title: "Collecting and Analyzing Large Data"
department: "MGTA"
programme: "MSBA (Rady MS Business Analytics)"
units: 4
schedulable: true
is_core: true
technical_level: 4
workload: "heavy"
workload_basis: "Midterm and final exams, individual assignments, team project for a real organization, participation, flipped-class pre-work."
grading: "35% final exam, 20% midterm, 20% team project, 10% assignments, 15% participation."
offerings: [{"term": "FA25", "season": "FA", "instructor": "Hansen", "format_notes": "8am Tuesday meetings; several flipped classes."}, {"term": "FA26", "season": "FA", "instructor": "Hansen, Karsten"}]
prerequisites: "Basic knowledge of algebra and introductory probability. Familiarity with common business concepts such as revenue, cost, profit, conversion, retention, and customer value."
topics: ["analytics life-cycle", "web scraping and APIs", "A/B testing", "exploratory data analysis", "customer lifetime value", "KPIs and dashboards", "clickstream analytics", "segmentation and clustering", "regression and regularization", "text analytics"]
skills: ["collecting data via scraping, APIs, and experiments", "data cleaning and preprocessing", "querying and joining transactional data", "building visualizations and dashboards", "predictive modeling and evaluation", "consulting for a real business"]
tools: ["Python", "R"]
career_tags: ["marketing", "operations", "machine-learning", "data-engineering"]
notes: "Team project consults for an actual business; GenAI encouraged but students must explain all submitted code."
syllabi: ["MGTA 452 Collecting and Analyzing Large Data (Hansen) FA26.txt"]
---
# MGTA 452 — Collecting and Analyzing Large Data

**4 units** · MSBA (Rady MS Business Analytics) · offered FA25, FA26

## What this course covers

An introduction to tools and frameworks for collecting and analyzing large datasets to
drive strategic business decisions. Covers the full analytics project cycle — scoping,
data collection (web scraping, APIs, experiments), exploratory analysis, predictive
modeling, and presenting findings — with a team project consulting for a real
organization.

## What you should be able to do afterwards

- collecting data via scraping, APIs, and experiments
- data cleaning and preprocessing
- querying and joining transactional data
- building visualizations and dashboards
- predictive modeling and evaluation
- consulting for a real business

## Topics covered

analytics life-cycle, web scraping and APIs, A/B testing, exploratory data analysis, customer lifetime value, KPIs and dashboards, clickstream analytics, segmentation and clustering, regression and regularization, text analytics.

## Tools used

Python, R.

## Prerequisites

Basic knowledge of algebra and introductory probability. Familiarity with common business concepts such as revenue, cost, profit, conversion, retention, and customer value.

## How it is graded

35% final exam, 20% midterm, 20% team project, 10% assignments, 15% participation.

## Workload

Heavy. Midterm and final exams, individual assignments, team project for a real organization, participation, flipped-class pre-work.

## Offerings

- **FA25** — Hansen
- **FA26** — Hansen, Karsten

## Syllabus text

_Verbatim from the syllabus PDF supplied by the Rady graduate programmes office._

### MGTA 452 Collecting and Analyzing Large Data (Hansen) FA26

Rady School of Management, University of California San Diego

MGTA 452: Collecting and Analyzing Large Data
- An Agentic Approach to Business Analytics
Course Information
Item

Information

Course number

MGTA 452

Course title

MGTA 452: Collecting and Analyzing Large Data - An Agentic
Approach to Business Analytics

Instructor

Professor Karsten T. Hansen

Quarter

F26

Course location

1E107

Office hours

By appointment

Contact information

karstenhansen@ucsd.edu

Syllabus version

August 2026

Course Description
Having data does not by itself tell a manager what to do. The calculation is often the easy part. The harder work is deciding
whether the data can answer the question, checking that the data are trustworthy, and being clear about what the result does—
and does not—mean for the decision.
The course covers four types of business analytics. Descriptive analysis asks what happened. Predictive analysis asks what is
likely to happen. Causal analysis asks what would change if the business took an action. Prescriptive analysis asks which
action should be chosen given the organization’s goals and constraints. Students will use Python to prepare and analyze data,
build and evaluate models, study randomized experiments, and make choices under economic and operational limits.
Students will sometimes work with an analytical agent while planning, coding, and checking an analysis. The agent can save
time, but it can also produce plausible errors. Its output must therefore be checked against the data, the code, and the question
being answered.
Throughout the course, I will ask students to explain what they did, why it fits the decision, and how they checked it.

Class Materials
All class materials will be made available through the class Canvas site at rady.instructure.com.

Course Overview
The course builds from one week to the next. We start with the decision and the data available to inform it. Later weeks add
description, prediction, causal analysis, and choice. In Week 10, students bring the work together in a complete analysis. The
final exam follows in Week 11.
My aim is for students to leave the course with a practical way to turn an unclear request into a defensible recommendation.
That requires judgment before and after the code: defining the decision, deciding what the data can support, and explaining
where the evidence stops.
The ten instructional weeks form four phases:
Phase

Weeks

What we do

I. Build Evidence

1-3

Define the decision, prepare reliable
data, and describe what has happened.

II. Learn Patterns and Predict

4-6

Build and evaluate regression,
classification, and forecast models.

III. Turn Analysis into Choices

7-9

Use forecasts and segments, study
randomized actions, and choose under
practical limits.

IV. Put Everything Together

10

Bring the course’s methods together in
one complete analysis.

Prerequisites
Students should have:
Basic knowledge of algebra and introductory probability.
Familiarity with common business concepts such as revenue, cost, profit, conversion, retention, and customer value.

Course Learning Objectives
By the end of the course, students should be able to:
1. Define the business decision and distinguish descriptive, predictive, causal, and prescriptive questions.
2. Obtain, prepare, combine, and check business data in Python.
3. Produce clear descriptive summaries and graphics for a business question.
4. Build regression, classification, forecasting, and segmentation models and judge their performance against a relevant baseline,
using held-out data when appropriate.
5. Estimate and interpret the effects of randomized business actions.
6. Turn predictions and experimental evidence into decisions under costs and constraints.
7. Give an analytical agent clear instructions, check its output, and document how it was used.
8. Explain the evidence, assumptions, uncertainty, and limitations behind a recommendation.

Course Workflow
The course uses one workflow:
request → decision outline → questions → agent prompt → calculations and checks → conclusion
1. Request: Write down the request as it was given.
2. Decision outline: Explain who will use the analysis and what choice that person faces. Define the outcome, unit of
analysis, time horizon, and practical limits on the choice.
3. Questions: Turn the request into specific questions and identify each as descriptive, predictive, causal, or prescriptive.
4. Agent prompt: If an agent will be used, write instructions that explain the task and its context. State any limits, the checks
to perform, and the output needed.
5. Calculations and checks: Do the analysis in Python and check it as you go. Confirm that the code uses the intended data
and comparisons and that another analyst can reproduce the result.
6. Conclusion: State what the analysis supports, what remains uncertain, and what that means for the decision.
Coding begins only after the decision and questions are clear; otherwise, it is easy to produce a technically correct answer to
the wrong problem. A finding may send the analyst back to an earlier question or assumption.

Computing Environment
The course uses Python exclusively.
We will use the following software:
Python
pandas as the primary DataFrame library
NumPy
Matplotlib, seaborn, or plotnine
SciPy, including scipy.optimize
statsmodels
scikit-learn
requests
Beautiful Soup
Jupyter notebooks and Quarto
pandas is the required DataFrame library. We may discuss similar operations in other libraries, but students will not be expected
to learn a second API.

Class Format
Most class meetings will use the following structure:
Time

Activity

0:00–0:20

Business case and decision outline

0:20–1:05

Concepts and methods

1:05–1:40

Instructor-led Python demonstration

1:40–1:50

Break

1:50–2:40

Individual agent-assisted laboratory

2:40–3:00

Validation, interpretation, and discussion of the decision

Week 1 uses a modified schedule for course orientation, a short history of coding interfaces, and a decision study led by the
instructor. Weeks 6 and 7 also use modified schedules. The midterm occupies the first half of Week 6, and forecasting
continues through the first half of Week 7.

Weekly Schedule
The schedule moves from defining a decision to completing and checking an analysis, followed by the final exam in Week 11.
Week

Focus

1

Decisions, analytical questions, and working with an analytical
agent

2

Acquiring, cleaning, combining, and checking data

3

Describing business performance

4

Regression and numerical prediction

5

Classification and targeting

6

Midterm and forecasting foundations

7

Forecasting applications and segmentation

8

Randomized experiments and causal analysis

9

Decisions under costs and constraints

10

Completing and checking an analysis

11 (Dec. 8)

Final Exam

Week 1: Business Decisions and Agentic Analytics
We begin with a basic question: What decision is the analysis intended to improve?
The course overview and the work of a business analyst.
Descriptive, predictive, causal, and prescriptive analytics.
Broad business requests and analytical questions.
Who will use the analysis, the choices they face, the outcome to improve, and practical limits.
Units of analysis and time horizons.
Measures of success, decision rules, and signs that the decision is causing harm.
Correlation, prediction, intervention, and optimization.
A brief history of coding, from assembly and C/C++ to Python and work with analytical agents.
Why easier coding tools do not change the analyst’s responsibility to say what the code should do and check that it
worked.
The course workflow: request → decision outline → questions → agent prompt → calculations and checks →
conclusion.
What an analytical agent can help with and what the student must decide and check.
Keeping code, sources, and decisions clear enough for someone else to review.

Week 2: Acquiring, Cleaning, and Organizing Data in Python
Week 2 is about getting the data into a usable form and checking whether it can support the analysis.
DataFrames, observations, variables, and table grain.
Reading CSV, Excel, JSON, and Parquet files.
Selecting, filtering, sorting, grouping, and aggregation.
Creating and transforming variables.
Combining DataFrames.
Reshaping data.
Dates, strings, and categorical variables.
Missing values, duplicates, outliers, and impossible values.
Data-type, range, and uniqueness checks.
Data dictionaries and separation of raw and processed data.

Web data module
HTTP requests and responses.
APIs compared with HTML scraping.
Basic HTML structure and CSS selectors.
Beautiful Soup.
Extracting tables and repeated elements.
Pagination.
Rate limiting and responsible collection.
Recording the source and collection date.
Saving raw responses.
Detecting changes in page structure.
When an analytical agent may—and may not—collect data from the web.

Week 3: Describing Business Performance
This week concentrates on description: establishing what happened and identifying patterns that deserve closer
attention.
Describing distributions with measures of center and spread and identifying skewness and outliers.
Calculating rates, ratios, weighted averages, and business performance indicators with the correct denominators.
Comparing performance across groups, cohorts, funnels, and time periods.
Designing statistical graphics that answer a business question clearly.

Week 4: Predictive Analytics I—Regression
Week 4 introduces regression for predicting numerical business outcomes.
Defining a supervised prediction problem in terms of observations, features, outcomes, and a prediction horizon.
Dividing data into time-ordered training, validation, and test samples and comparing models with a simple baseline.
Fitting simple and multiple linear regressions with categorical predictors, transformations, interactions, and
nonlinear relationships.
Understanding the purpose of regularization.
Evaluating predictions with mean absolute error, root mean squared error, and percentage errors.
Diagnosing residual patterns, quantifying prediction uncertainty, and recognizing the risks of extrapolation.
Checking for overfitting with out-of-sample results and distinguishing predictive interpretation from causal
interpretation.

Week 5: Predictive Analytics II—Classification and Targeting
We then turn to binary outcomes and the practical problem of deciding which cases warrant attention.
Predicting binary outcomes and probabilities with logistic regression, decision trees, and introductory tree
ensembles.
Evaluating classifications with confusion matrices, sensitivity, specificity, precision, and recall.
Comparing models with ROC curves, precision-recall curves, lift, and gains.
Addressing class imbalance and checking whether predicted probabilities are well calibrated.
Recognizing and preventing target leakage.
Choosing thresholds that reflect the costs of errors and limits on capacity.
Examining subgroup performance and possible fairness concerns.

Week 6: Midterm Examination and Forecasting Foundations
First 90 minutes: Midterm examination
The midterm is administered during the first half of the class. Its format is described in the Assessment and
Examinations section below.
Second 90 minutes: Break and forecasting foundations
The second half begins with a short break. The remaining class time introduces:
Organizing and inspecting time-indexed business data, including trend and seasonal patterns.
Creating lagged variables and moving averages.
Establishing naive and seasonal-naive forecast baselines.
Explaining why random train-test splits are usually inappropriate for time-series data.
Evaluating forecasts with time-ordered validation and communicating forecast uncertainty.

Week 7: Forecasting Applications and Business Segmentation
Week 7 has two parts, both concerned with how forecasts and customer groups can inform operational choices.

Module A: Forecasting applications
Building forecasts with exponential smoothing and regression using trend and seasonal predictors.
Using lagged features in machine-learning forecasts.
Evaluating forecasts with rolling-origin backtesting and forecast intervals.
Detecting structural change and model drift.
Translating forecasts into inventory and staffing decisions.
Module B: Segmentation and unsupervised learning
When segmentation is useful and how unsupervised learning differs from supervised prediction.
Selecting and standardizing features and understanding the role of distance measures.
Constructing segments with k-means and choosing a suitable number of clusters.
Assessing cluster stability and developing clear profiles of the resulting groups.
Comparing the segmentation with simpler business rules and deciding whether it supports a useful action.

Week 8: Causal Business Analytics—Experiments and A/B Testing
Week 8 asks a different kind of question: did the action itself change the outcome? We begin by separating causal
questions from prediction and naming the treatment, control condition, outcome, and the effect we want to estimate—
usually the average treatment effect.
A well-run randomized experiment makes the comparison credible, but random assignment does not end the work.
Students will check whether the groups looked similar at the start, analyze people according to their original
assignment, and consider what noncompliance or attrition may have changed. We will also distinguish an effect that
can be measured from one that is large enough to matter and use minimum detectable effects and power to plan the
study.
Finally, we look at common ways experiments can mislead: testing many outcomes, checking results repeatedly or too
soon, ignoring harmful side effects, and assuming the same result will hold for every group or setting. We close by
discussing why an observational comparison cannot provide the same causal support as random assignment.

Week 9: Prescriptive Analytics and Decision Optimization
Week 9 uses the available evidence to compare feasible actions under cost and capacity limits.
Why a prediction informs, but does not by itself determine, a decision.
Comparing alternatives with expected value, expected utility, and the costs of false positives and false negatives.
Choosing decision thresholds that reflect budget and capacity constraints.
Testing choices with scenario analysis, sensitivity analysis, and Monte Carlo simulation.
Formulating and solving basic optimization problems in Python.
Applying these methods to resource allocation, inventory, and staffing decisions.
Using predicted outcomes or predicted treatment effects to decide whom to target, then stating the rule clearly.

Week 10: Completing and Auditing an Analysis
In Week 10, students assemble and review a complete analysis to see whether it supports the proposed business
decision. They will decide which kinds of analysis—descriptive, predictive, causal, or prescriptive—the decision actually
needs. The point is not to use every method, but to connect the methods used to the questions asked.
Students will give an analytical agent clear instructions and pause at sensible points to check its work. They will check
the data, calculations, and models as the analysis develops, using direct checks and simple baselines. Their code and
notes should allow another person to follow the work and question any unsupported claim, calculation, or source.
Week 10 closes with the question that follows every real analysis: what should we watch after the decision is put into
practice? We will consider changes in the data, model performance, and business results. We will also ask whether the
recommendation treats people fairly, protects private information, creates security risks, and is honest about what
remains uncertain.

Week 11: Final Exam
Assessment and Examinations
Assessment

Weight

Nine individual weekly assignments

35%

Individual midterm examination

25%

Individual final examination

40%

Total

100%

Weekly Assignments
Nine individual assignments will be submitted during the quarter. There is no separate assignment in Week 6 because the
midterm is given during that class. Every assignment uses Python.

Midterm Examination
The midterm is administered during the first 90 minutes of Week 6.
Component

Time

Part A: Human-only multiple choice

30 minutes

Part B: Practical analysis; analytical agent permitted

60 minutes

Part A: Human-only multiple choice
Part A contains approximately 15 multiple-choice questions. Students may not use notes, a laptop, a phone, a calculator, or an
analytical agent. The exact scope will be announced during Week 6.
Part A will be collected before laptops may be opened and before the materials for Part B are released. After submitting Part A,
students may not return to it.
Part B: Practical analysis
Part B begins after Part A has been collected. Students may use Python, the course materials listed in the exam instructions,
and an analytical agent. The problem, required files, and deliverables will be provided when Part B is released.

Final Examination
The final examination is held on December 8 during Week 11 and lasts three hours.
Component

Time

Part A: Human-only multiple choice

50 minutes

Part B: Practical analysis; analytical agent permitted

130 minutes

Part A follows the same rules as Part A of the midterm and will be collected before Part B begins. During Part B, students may
use Python, the course materials listed in the exam instructions, and an analytical agent. I will announce the exact scope during
Week 11. The problem, required files, and deliverables will be provided when Part B is released.

Use of Analytical Agents
Analytical agents are part of the laboratory work. For assignments, the instructions will say whether you must use one or may
choose to do so. The assessment section above explains when agents may be used during examinations.
When allowed, an analytical agent may help plan the work, write or revise Python code, explain errors, suggest checks, and
improve the wording of an interpretation. An agent is not a source of evidence. Evidence comes from data, code, calculations,
and cited sources that the student has checked.
You are responsible for every analysis and recommendation you submit. Show the important checks you carried out yourself. If
the instructions ask for an interaction record, include it.

Assignment Submission and Late Work
Submit assignments by the deadline I give you, along with every file needed to run and understand the analysis. Late work is
not accepted; an assignment submitted after the deadline receives a grade of zero.

Academic Integrity
Do your own work on individual assignments and examinations unless I say that collaboration is allowed. Using an agent does
not change that rule. Follow the agent-use instructions for the activity.
Do not share examination materials or contact another person for help during an examination.

Course Policies
Students requesting disability-related accommodations should begin with the UC San Diego Office for Students with Disabilities.
After receiving an Authorization for Accommodation letter, students should discuss the arrangements with the instructor and the
department’s OSD liaison. Accommodations are not retroactive.
The UC San Diego Academic Integrity Policy and university policies on student conduct and privacy also apply to this course.

