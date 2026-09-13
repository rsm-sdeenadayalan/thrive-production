---
id: "MGTF 413"
code: "MGTF 413"
title: "Computational Finance Methods"
department: "MGTF"
programme: "Rady MQF (Master of Quantitative Finance)"
schedulable: false
is_core: false
technical_level: 5
workload: "heavy"
workload_basis: "Graded work includes weekly quizzes, four written homework assignments, a comprehensive midterm exam, and a final project with report and presentation."
grading: "Grades are based on weekly quizzes (10%), written homework assignments (28%), a comprehensive midterm exam (30%), and a final project report and presentation (32%)."
offerings: [{"term": "WI26", "season": "WI", "instructor": "Cheng & Williams"}]
prerequisites: null
topics: ["optimization", "linear programming", "quadratic programming", "portfolio optimization", "binomial trees", "monte carlo simulation", "option pricing", "stochastic differential equations", "partial differential equations", "finite difference methods"]
skills: ["formulating and solving quadratic programming problems", "applying monte carlo simulation to derivative pricing", "implementing euler and milstein schemes for stochastic differential equations", "using variance reduction techniques in simulation", "pricing european, american, and exotic options", "solving the black-scholes equation with finite difference methods", "building binomial tree models for option pricing"]
tools: ["python", "r", "jupyter notebooks"]
career_tags: ["finance", "pricing"]
syllabi: ["MGTF 413 Computational Finance Methods (Cheng & Williams) WI26.txt"]
---
# MGTF 413 — Computational Finance Methods

Rady MQF (Master of Quantitative Finance) · offered WI26 · _unit count not stated in the material supplied_

## What this course covers

This course introduces computational methods used in modern finance, including
optimization, Monte Carlo simulation, and finite difference methods. Applications
include portfolio selection, option pricing for European, American, and exotic options,
and solving the Black-Scholes partial differential equation. The course is taught
through lectures, course notes, and hands-on computational assignments using Python and
R in Jupyter notebooks.

## What you should be able to do afterwards

- formulating and solving quadratic programming problems
- applying monte carlo simulation to derivative pricing
- implementing euler and milstein schemes for stochastic differential equations
- using variance reduction techniques in simulation
- pricing european, american, and exotic options
- solving the black-scholes equation with finite difference methods
- building binomial tree models for option pricing

## Topics covered

optimization, linear programming, quadratic programming, portfolio optimization, binomial trees, monte carlo simulation, option pricing, stochastic differential equations, partial differential equations, finite difference methods.

## Tools used

python, r, jupyter notebooks.

## Prerequisites

None stated in the syllabus.

## How it is graded

Grades are based on weekly quizzes (10%), written homework assignments (28%), a comprehensive midterm exam (30%), and a final project report and presentation (32%).

## Workload

Heavy. Graded work includes weekly quizzes, four written homework assignments, a comprehensive midterm exam, and a final project with report and presentation.

## Offerings

- **WI26** — Cheng & Williams

## Syllabus text

_Verbatim from the syllabus PDF supplied by the Rady graduate programmes office._

### MGTF 413 Computational Finance Methods (Cheng & Williams) WI26

MGTF 413: Computational Finance Methods
TERM (Winter 2026)

This course will be co-taught by the following two instructors.
PROFESSOR LI-TIEN CHENG
EMAIL: l3cheng@ucsd.edu
PROFESSOR RUTH WILLIAMS
EMAIL: rjwilliams@ucsd.edu
TEACHING ASSISTANT: Zhaolong Han
TA EMAIL: zhhan@ucsd.edu

Class Meeting Time: Fridays, 1-3:50pm (PST)
DESCRIPTION
Computational methods have become indispensable in modern finance. This course will introduce
common computational methods of importance for finance and illustrate their use in solving problems.
The course will begin with an introduction to optimization, which will include application of quadratic
programming to portfolio selection. This will be followed by an introduction to simulation methods with
applications to option pricing. Fundamentals of Monte Carlo simulation and numerical solution of
stochastic differential equations will be treated. The course will conclude with a discussion of finite
difference methods for solving partial differential equations arising in finance. Applications to pricing of
European, American and exotic options will be given using simulation and partial differential equation
methods.

OBJECTIVES

At the conclusion of this course, the student will:
- understand the role of optimization problems and techniques in finance;
- understand the distinction between unconstrained, constrained, nonlinear, quadratic programming (QP)
- understand how to formulate and numerically solve QP problems;
- be able to apply basic algorithmic tools for QP to portfolio optimization and other problems in finance;
- understand the basic ideas of Monte Carlo techniques for the purpose of option pricing;
- understand basic concepts related to simulation including random variable generation, variance
reduction methods and statistical analysis of simulation output;
- understand and be able to apply the computational methods of importance sampling, pricing using
binomial trees, explicit and approximate solutions of stochastic differential equations including Euler and
Milstein schemes;
- understand the basic concepts of numerical quadrature;
- be able to use Monte Carlo simulation in solving applied problems on derivative pricing, including but not
limited to pricing of European and American options, pricing interest rate dependent claims and path
dependent options;
- understand the role of partial differential equations in option pricing;
- understand how to formulate and numerically solve the Black-Scholes equation for European and
American options;
- be able to use basic numerical methods for solving the Black-Scholes partial differential equation for
option pricing;
- understand how the Black-Scholes framework can be extended to exotic options and nonlinear models.
MATERIALS
-Course notes, which are required reading, will be provided in electronic format via the course website on
Canvas at https://rady.instructure.com/
-Students are expected to read the notes and other relevant material provided on Canvas in advance of
the class meeting time.
The course will use Python and R within Jupyter notebooks.
Reference Materials: for extended reading by interested students (electronic access available through
roger.ucsd.edu --- use vpn to gain access requiring a UCSD IP address)
1. Optimization Methods in Finance, G. Cornuejols and R. Tutuncu, Second Edition, Cambridge Univ.
Press, 2018.
2. Introduction to the Mathematics of Finance, R J Williams, American Mathematical Society, 2006.
3. Implementing Models in Quantitative Finance: Methods and Cases, Gianluca Fusai,
Andrea Roncoroni, Springer, 2008
4. Monte Carlo Methods in Financial Engineering, Paul Glasserman, Springer, 2003.
5. Tools for Computational Finance, Sixth Edition, R. U. Seydel, Springer, 2017

COURSE SCHEDULE
Week 1
- examples of optimization problems and techniques in finance

- linear programming, with applications to asset/liability cash flow matching, arbitrage detection, and
bond portfolio management
- sensitivity analysis
Week 2
- Newton’s method
- unconstrained optimization, steepest descent, Newton’s method, interior-point method, and sequential
quadratic programming
- quadratic programming (QP): portfolio mean-variance optimization
Friday of Week 2: Homework Assignment 1a due
Week 3:
- discrete models of option pricing
- dynamic programming
- pricing and hedging with binomial trees: European call and American put
Friday of Week 3: Homework Assignment 1b due
Week 4
- motivation for Monte Carlo techniques in computational finance
- static Monte Carlo
- simulating random variables
Friday of Week 4: Homework Assignment 2a due
Week 5
-variance reduction
-importance sampling
-applications to option pricing in discrete time models
Friday of Week 5: Homework Assignment 2b due
Week 6
- dynamic Monte Carlo
- simulating continuous stochastic processes: Euler and Milstein schemes
- pricing European options
- numerical quadrature and pricing Asian options
Friday of Week 6: Homework Assignment 3a due
Week 7
- pricing American options
- dynamic programming and Longstaff-Schwartz algorithm
Friday of Week 7: Homework Assignment 3b due
Week 8
- COMPREHENSIVE EXAM (1.5 hours)
- basic notation and concepts for working with partial differential equations
- examples of partial differential equations
- the Black-Scholes partial differential equation for European options

Friday of Week 8: Homework Assignment 3c due
Week 9
- finite difference methods for numerical approximation: explicit, implicit, and Crank-Nicolson schemes
- stability, consistency, convergence, and accuracy of numerical methods
Week 10
- the Black-Scholes free boundary problem for American options
- numerical methods for American option pricing under the Black-Scholes model
- extensions to exotic options and nonlinear models
Friday of Week 10: Homework Assignment 4 due
Week 11
Final project due: paper and presentations (about 15 min in length) to be given in final exam time
slot of Friday, March 20, 2026, 1-4pm
COURSE GRADES
Course grades will be based on the following weighted components:
Weekly quizzes (on Canvas): 10%
Written homework assignments: 4 in total (28%)
Comprehensive (midterm) exam in week 8: (30%)
Final project: written report and presentation (32%)
Homework Policy
Students are strongly encouraged to first attempt the homework assignments on their own. After that,
students may consult other students, the Professors, or the TA.
However, students must produce their own individual final solutions independently.
Students must NOT copy solutions from another student or from any other source.
Do NOT share your own independent homework solution with anyone else.
If a student got an idea for the homework from another student, the name of that student and the
extent of the helpful idea must be acknowledged on the first page of the homework solution.
Moreover, all communication with the TA and Professors needs to be done through UCSD e-mail/Piazza
accounts only.
Final Project
The final project should be completed in groups of 5-6 people. The contribution of each member of the
group needs to be identified in the written report and each member of the group needs to participate in
the final presentation.
CLASS POLICIES
The highest professional standards are expected of all members of the Rady community. The collective
class reputation and the value of the Rady experience hinges on this.
Student learning and the classroom experience is enhanced when:
●

Students join class on time. On time arrival ensures that classes are able to start and finish at
the scheduled time. On time arrival shows respect for both fellow students and faculty and it

enhances learning by reducing avoidable distractions. This will enable the instructors to have
more interaction with the class and will provide a good experience for the whole class.
●

Students are fully prepared for each class meeting. Students will gain much more from the class
meetings and associated discussions if they read the notes in advance of the class meeting
time. When students are not prepared they cannot contribute to the overall learning process.
This affects not only the individual, but their peers who count on them, as well.

●

Students respect the views and opinions of their colleagues. Discussion is encouraged.
Intolerance for the views of others is unacceptable.

●

Students minimize distractions while participating in class meetings. When students are surfing
the web, responding to e-mail, instant messaging each other, and otherwise not devoting their
full attention to the topic at hand, they are doing themselves and their peers a major disservice.
Fellow students cannot benefit from the insights of students who are not engaged. Phones and
other devices not being used for the class session should be put away. Their use is not
professional and takes attention away from class participation.

Class materials and recordings: Class materials must not be shared beyond the class. In
particular, notes and recordings (audio, photo or video) made by the instructors are not to be shared. No
recordings (audio, photo or video) should be made by students. Students are encouraged to take notes.
ACADEMIC INTEGRITY
Integrity of scholarship is essential for any academic community. As members of the Rady School, we
pledge ourselves to uphold the highest ethical standards. The University expects that both faculty and
students will honor this principle and in so doing protect the validity of University intellectual work. For
students, this means that all academic work will be done by the individual to whom it is assigned, without
unauthorized aid of any kind.
Further elaboration is provided in the following statement modeled after one provided by the UCSD
Academic Integrity Office:
"Academic Integrity is expected of everyone at UC San Diego. This means that you must be honest, fair,
responsible, respectful, and trustworthy in all of your actions. Lying, cheating or any other forms of
dishonesty will not be tolerated because they undermine learning and the University’s ability to certify
students’ knowledge and abilities. Thus, any attempt to get, or help another get, a grade by cheating,
lying or dishonesty will be reported to the Academic Integrity Office and will result in sanctions. Sanctions
can include an F in this class and suspension or dismissal from the University. So, think carefully before
you act by asking yourself: a) is what I’m about to do or submit for credit an honest, fair, respectful,
responsible & trustworthy representation of my knowledge and abilities at this time and,
b) would my instructor approve of my action? You are ultimately the only person responsible for your
behavior. So, if you are unsure, don’t ask a friend—ask your instructor, instructional assistant, or the
Academic Integrity Office. You can learn more about academic integrity at academicintegrity.ucsd.edu”
For tips on how to Excel with Integrity, check out the Academic Integrity webpage here.
The complete UCSD Policy on Integrity of Scholarship can be viewed at:
http://senate.ucsd.edu/Operating-Procedures/Senate-Manual/Appendices/2
ASSESSMENT VERSIONING

Following UCSD (and common) practice recommended by the Academic Integrity Office, assessments,
especially those given at non-overlapping times, will be comparable, but may not be identical.
This
practice is meant to maintain course integrity, avoiding non-allowed collaboration (either
intentional or
accidental.
STUDENTS WITH DISABILITIES
A student who has a disability or special need and requires an accommodation in order to have equal
access to the class must register with the Office for Students with Disabilities (OSD). The OSD will
determine what accommodations may be made and provide the necessary documentation to present to
the faculty member.
The student must provide the OSD letter of certification and OSD accommodation recommendation to the
appropriate faculty member as early as possible in order to initiate the request for accommodation in
classes, examinations, or other academic program activities. No accommodations can be implemented
retroactively.
Please visit the OSD website for further information or contact the Office for Students with Disabilities at
(858) 534-4382 or osd@ucsd.edu.

