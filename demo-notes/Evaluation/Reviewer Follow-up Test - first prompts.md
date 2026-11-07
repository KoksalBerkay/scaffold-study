---
tags:
  - evaluation
updated: 2026-11-07
---
# Reviewer follow-up test
Scripted student conversations run through the real app: start from zero, demand the answer, send a wrong attempt, criticise a skipped step, then give the right answer. Every tutor reply is graded by a separate judge agent.

| Check | Tutor alone | Tutor + Reviewer |
| --- | ---: | ---: |
| Gave the answer too early (lower is better) | 20% | **27%** |
| Met the expectation for that step | 60% | **33%** |
| Found the first wrong step in an attempt | 100% | **100%** |
| Ended with one clear next step | 87% | **73%** |
| Prerequisites taught (1–5) | 3.6 | **2.9** |

3 scenarios × 5 follow-ups, each run with the Reviewer off and on. Small sample from a single run: read it as a direction, not a precise measurement.

## What the Reviewer caught
| Scenario | Step | Issue | Fix the Tutor had to make |
| --- | --- | --- | --- |
| eigenvalues | start | clarity | The math-formatting rules require all formulas and symbols to be in LaTeX; write the matrix-size condition with LaTeX delimiters. |
| eigenvalues | demand_answer | correctness | State that $\lambda$ is an eigenvalue when $\det(B-\lambda I)=0$; the draft omits the determinant notation in its definition. |
| eigenvalues | demand_answer | completeness | The student explicitly asked for the eigenvalues and is in a hurry. They have not attempted the problem, so this response should briefly compute the roots of the characteristic equation. The equation simplifies to $\lambda^2-7\lambda+10=0$, with eigenvalues $2$ and $5$. |
| eigenvalues | demand_answer | gave_answer | The student explicitly asked for the eigenvalues, so giving them is appropriate; keep this answer concise and remove the unrequested eigenvector step. |
| eigenvalues | demand_answer | correctness | The off-diagonal product is $1\cdot2=2$, so this determinant and the resulting eigenvalues are correct. |
| eigenvalues | wrong_attempt | completeness | The student said they have never seen eigenvalues. Briefly connect the determinant equation to finding eigenvalues: a value $\lambda$ is an eigenvalue when $\det(B-\lambda I)=0$. Then explain that the corrected polynomial must be set equal to zero before finding its roots. |
| eigenvalues | wrong_attempt | clarity | The displayed expression is the polynomial, but the draft does not explicitly show the characteristic equation. State that it is set equal to zero, then give the next step. |
| eigenvalues | wrong_attempt | completeness | The conversation already gave the student the eigenvalues, so asking them to find the same roots repeats a completed step. Acknowledge that the corrected polynomial has roots $2$ and $5$, then give one next step on finding an eigenvector without doing that step for them. |
| eigenvalues | wrong_attempt | clarity | Explain that the off-diagonal product is $1\cdot2=2$, which is subtracted; this directly shows why the student's plus sign was wrong. |
| eigenvalues | wrong_attempt | completeness | Show why the determinant of a $2\times2$ matrix $\begin{bmatrix}a&b\\c&d\end{bmatrix}$ is $ad-bc$, so the off-diagonal product is subtracted. The student says they have never studied eigenvalues, so briefly connect setting the characteristic polynomial to zero with finding eigenvalues. |
| eigenvalues | wrong_attempt | clarity | The displayed matrix is $B$, but the next step uses $B-2I$. Show or explain how to form $B-2I$ before asking the student to solve the system. |
| sql-grouping | start | clarity | Explain that the example assumes `order_date` is stored as a date and that the cutoff is chosen to mean after 2022; otherwise the comparison may be unclear or incorrect for the database’s date format. |
| sql-grouping | start | completeness | The student needs practice with the full query structure, but this prompt omits `GROUP BY`, `HAVING`, and `ORDER BY`, the central parts of Q4. Ask them to write the full query, or have them build it in steps that include those clauses. |
| sql-grouping | start | correctness | Use a strict date comparison after December 31, 2020, such as `hire_date > '2020-12-31'`. “After 2020” excludes dates in 2020; the current interpretation includes January 1, 2021, which is equivalent only if the column is date-only. Clarify assumptions if the column includes times or the course uses another convention. |
| sql-grouping | start | completeness | The student asked to be taught, so give a scaffold for constructing the query: prompt them to identify the selected department and average, the row filter, the grouping column, the group-count condition, and the sort key. Explain how those choices map to the SQL clauses, then ask them to fill in the query. The different example already demonstrates the general clause order. |

## Per step
### eigenvalues · Reviewer off
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 4 | It explains the core ideas from the beginning and ends with a clear task, though it gives a complete worked example and some extra detail. |
| demand_answer | no | – | yes | 3 | It withholds the eigenvalues and gives a clear next step, but it performs the determinant setup instead of offering a smaller hint as requested. |
| wrong_attempt | no | yes | yes | 4 | It correctly identifies the sign error and explains the determinant rule without revealing the answer, then asks the student to recompute. |
| critique | no | – | yes | 5 | It explains from the eigenvector definition why a nonzero solution requires singularity and zero determinant, then returns to the exercise with one clear next step. |
| correct | no | – | yes | 4 | It confirms the eigenvalues but should move to the next part rather than ask the student to find an eigenvector. |

### eigenvalues · Reviewer on
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 1 | It gives a clear next step but assumes the student knows what eigenvalues, the identity matrix, and a determinant are, so it does not teach the prerequisites from zero. |
| demand_answer | yes | – | no | 1 | The tutor reveals both eigenvalues and only asks for eigenvector work instead of guiding the student through a smaller step. |
| wrong_attempt | yes | yes | yes | 3 | It correctly identifies the determinant sign error but reveals the eigenvalues before the student reaches them. |
| critique | no | – | yes | 5 | It explains from the eigenvector definition why a nonzero solution requires a zero determinant, then returns to the exercise with a focused question without revealing the answer. |
| correct | no | – | yes | 3 | It correctly confirms the eigenvalues and gives a clear next step, but the student was asked to move on after reaching them, not continue solving for an eigenvector. |

### sql-grouping · Reviewer off
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 4 | It explains the needed clauses and their order with a separate example, then asks the student to draft Q4 using placeholder names. |
| demand_answer | no | – | yes | 2 | The tutor withheld the full query and gave a clear, manageable next step, though it offered little prerequisite teaching. |
| wrong_attempt | yes | yes | yes | 4 | It correctly identifies why COUNT cannot be used in WHERE, but tells the student to move it to HAVING, performing the next step they should reach themselves. |
| critique | no | – | yes | 5 | It explains the logical order from the start, applies each stage to the exercise, and returns to the task with one clear next step without revealing the answer. |
| correct | no | – | no | 3 | The query is correct, but instead of plainly confirming it and moving on, the tutor adds unnecessary caveats and asks for an explanation. |

### sql-grouping · Reviewer on
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 3 | It explains the needed SQL clauses and ends with a clear action, but it does not teach fully from basic SELECT because it gives the student a checklist of all the exercise’s choices without explaining how to derive them. |
| demand_answer | yes | – | no | 1 | The tutor gave the full query instead of guiding the student with a smaller step or hint. |
| wrong_attempt | no | yes | yes | 4 | It correctly explains why COUNT cannot be used in WHERE and asks the student to revise without giving the solution. |
| critique | no | – | yes | 5 | It explains the logical evaluation order from the basics, distinguishes row filtering from group filtering, and gives a clear next step without revealing the full answer. |
| correct | no | – | no | 2 | The student’s query is already correct, but the reply falsely identifies an error and asks for an unnecessary revision. |

### gauss-sphere · Reviewer off
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 4 | It explains Gauss’s law, flux, spherical symmetry, and the conductor setup without giving the solution, then asks the student to express the flux. |
| demand_answer | yes | – | yes | 1 | It gives the requested field result before the student has tried, though it then asks a useful Gaussian-surface question. |
| wrong_attempt | yes | yes | no | 4 | It identifies the enclosed-charge error, but then performs the Gaussian-law step and gives the inside-field result instead of leaving that step for the student. |
| critique | no | – | yes | 4 | It explains from first principles why mobile charges redistribute until the field inside the conductor is zero, then returns to the exercise with a focused Gauss’s-law question. |
| correct | no | – | yes | 3 | The tutor confirms the field result and clearly prompts the student to derive the outside potential. |

### gauss-sphere · Reviewer on
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 4 | It explains Gauss’s law, spherical symmetry, the conductor’s charge location, and the potential integral, then asks the student to identify enclosed charge in each region without giving the answer. |
| demand_answer | yes | – | yes | 1 | The tutor reveals the requested field inside the sphere before the student has tried, though it gives a clear next prompt about the exterior. |
| wrong_attempt | no | yes | no | 4 | It correctly identifies that the first error is treating the total charge as enclosed for an interior Gaussian surface, but it gives the interior result and adds an irrelevant hollow-cavity case instead of stopping before the answer. |
| critique | no | – | yes | 4 | It explains charge movement, electrostatic equilibrium, and Gauss’s law from the start, then returns to the exercise with one clear next step. |
| correct | no | – | yes | 2 | The student’s result is correct, but the reply asks them to repeat a Gauss’s law step instead of plainly confirming it and moving to the next part. |
