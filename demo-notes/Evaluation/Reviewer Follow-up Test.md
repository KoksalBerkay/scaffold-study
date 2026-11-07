---
tags:
  - evaluation
updated: 2026-11-07
---
# Reviewer follow-up test
Scripted student conversations run through the real app: start from zero, demand the answer, send a wrong attempt, criticise a skipped step, then give the right answer. Every tutor reply is graded by a separate judge agent.

| Check | Tutor alone | Tutor + Reviewer |
| --- | ---: | ---: |
| Gave the answer too early (lower is better) | 13% | **13%** |
| Met the expectation for that step | 53% | **60%** |
| Found the first wrong step in an attempt | 100% | **100%** |
| Ended with one clear next step | 87% | **100%** |
| Prerequisites taught (1–5) | 3.5 | **3.7** |

3 scenarios × 5 follow-ups, each run with the Reviewer off and on. Small sample from a single run: read it as a direction, not a precise measurement.

## What the Reviewer caught
| Scenario | Step | Issue | Fix the Tutor had to make |
| --- | --- | --- | --- |
| eigenvalues | correct | completeness | Explain that an eigenvector must be nonzero and that the homogeneous system gives a relationship between its components, so the student should choose a nonzero vector satisfying that relationship. |
| eigenvalues | correct | gave_answer | The student has now produced the quadratic but has not explicitly asked for its solution, and the earlier request for eigenvalues was not permission to provide them. Acknowledge that the quadratic is correct without confirming its roots. |
| sql-grouping | start | completeness | Explain that in standard SQL, `ORDER BY` defaults to ascending when no direction is stated, while the student should follow any course-specific convention. |
| sql-grouping | start | completeness | Clarify the sorting direction is unspecified. Explain that ascending is the SQL default, but the exam prompt does not say whether it wants ascending or descending, so the student should check the course convention or ask the examiner before choosing. |
| sql-grouping | start | completeness | Explain that SQL statements are written in clause order, but the logical processing order starts with FROM, then WHERE, GROUP BY, HAVING, SELECT, and ORDER BY. The draft's description of processing order omits SELECT and could leave a beginner confused. |
| sql-grouping | start | clarity | Clarify that the prompt is underspecified about sort direction; explain that ascending is the SQL default, so the query can omit ASC unless the course expects a stated direction. |
| sql-grouping | correct | gave_answer | Remove the completed query. The student has not yet attempted this exact corrected step; ask them to place the row filter and group-count condition in the appropriate clauses, then send their revised query. |
| sql-grouping | correct | correctness | The exam asks for departments with at least five employees hired after 2020. The query’s `HAVING COUNT(*) >= 5` counts all employees in each group, including those hired on or before the cutoff. Ask the student to make the count apply only to employees who satisfy the hire-date condition, without supplying the needed expression. |
| sql-grouping | correct | completeness | Clarify that the prompt says “after 2020,” so the strict date condition must exclude employees hired on December 31, 2020, or earlier. The student’s date filter does that, but the group count still needs to match the same hire-date restriction. |
| gauss-sphere | start | correctness | Clarify that this assumes the sphere is an isolated conductor with no charge inside its cavity. In that standard case all excess charge $Q$ resides on its outer surface, so a Gaussian surface within the conducting material encloses zero net charge; the problem statement does not explicitly specify whether the sphere is solid or hollow. |
| gauss-sphere | start | completeness | Clarify that $\vec{E}$ is radial and parallel to the outward area vector for positive $Q$; for negative $Q$ it points inward, so the flux has the opposite sign. The equation with $E(r)$ as a magnitude should account for the sign of $Q_{\text{enc}}$ or state that it assumes $Q>0$. |
| gauss-sphere | start | completeness | State that the line integral gives the potential difference and explain the radial simplification for this problem: $V(r)-V(\infty)=-\int_{\infty}^{r}E_r(r')\,dr'$, where $E_r$ is the signed radial component. This helps the student apply the relation once they find the field. |
| gauss-sphere | start | correctness | Clarify that this conclusion applies to the conducting material only. For a hollow sphere, a Gaussian surface with $r<R$ may lie in the cavity, where the enclosed charge is zero under the stated no-cavity-charge assumption, but that fact alone does not establish that the field there is zero. The problem likely means a solid conducting sphere; state that assumption or explain the ambiguity. |
| gauss-sphere | start | completeness | Explain that the potential must be found separately in each region, using the field there, and that for $r<R$ the conducting material has constant potential equal to the surface potential. Make the next step unambiguous by asking the student to identify the enclosed charge for $r<R$ and $r>R$ under the solid-sphere assumption. |
| gauss-sphere | critique | correctness | Clarify that this argument shows there is no net excess charge in the conductor’s bulk. It does not by itself prove all charge lies on the *outer* surface; for the assumed solid sphere with no charge-filled cavity, say that the excess charge resides on the outer surface. |

## Per step
### eigenvalues · Reviewer off
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 4 | It introduces the key definitions and determinant method without solving the exercise, then gives the student one clear next step. |
| demand_answer | no | – | yes | 3 | It withholds the eigenvalues and gives a clear next step, though it could explain how to form the characteristic determinant. |
| wrong_attempt | yes | yes | no | 3 | It correctly identifies the determinant sign error, but gives the corrected characteristic polynomial and asks the student to compute its discriminant, revealing the answer and doing the intended next step. |
| critique | no | – | yes | 5 | It explains from the eigenvector definition why a nonzero solution requires a singular matrix, then asks the student to connect this to the determinant criterion before returning to the exercise. |
| correct | no | – | yes | 1 | It confirms the eigenvalues correctly and gives a clear next step, but fails to move on as required after the student reached the right result. |

### eigenvalues · Reviewer on
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 4 | The reply introduces the key concepts and methods without solving the exercise, then asks the student to form the determinant as the next step. |
| demand_answer | no | – | yes | 3 | It withholds the eigenvalues and gives a clear next step by asking the student to expand the determinant equation. |
| wrong_attempt | no | yes | yes | 4 | It identifies the determinant sign error and asks the student to recompute the determinant, without revealing the answer. |
| critique | no | – | yes | 4 | It explains from the eigenvector equation why a nonzero solution requires a singular matrix and zero determinant, then returns to the exercise with one clear next step. |
| correct | no | – | yes | 4 | The tutor correctly confirms the polynomial and roots, but asks for another step instead of moving on as required. |

### sql-grouping · Reviewer off
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 5 | It explains filtering, grouping, aggregates, and sorting from the exercise context, uses a separate example, and ends by asking the student to identify the WHERE and HAVING conditions. |
| demand_answer | no | – | yes | 3 | It withholds the full query, explains the WHERE/HAVING distinction, and asks the student to write those clauses as a smaller next step. |
| wrong_attempt | no | yes | no | 4 | It correctly identifies why COUNT cannot be used in WHERE, but telling the student to rewrite both clauses gives away the next step instead of asking them to make that correction. |
| critique | no | – | yes | 5 | It explains SQL’s logical processing order and why row filters belong in WHERE while aggregate group filters belong in HAVING, then returns the student to the exercise with a clear next step. |
| correct | no | – | yes | 3 | It confirms the query but repeats the full SQL and asks for another explanation instead of moving to the next part. |

### sql-grouping · Reviewer on
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 5 | It explains the needed SQL concepts from basic SELECT, anchors them to Q4, withholds the solution, and ends by asking the student to write the first clauses. |
| demand_answer | no | – | yes | 3 | The tutor withholds the full query, gives a smaller filtering step, and asks the student to write the next clause. |
| wrong_attempt | no | yes | yes | 4 | It correctly explains why COUNT belongs in HAVING, but tells the student to rewrite the query with that fix, performing the next step instead of leaving it to the student. |
| critique | no | – | yes | 5 | It explains the logical order from the basics, why WHERE and HAVING apply at different stages, and returns the student to rewriting the query. |
| correct | no | – | yes | 4 | The query was correct, but the tutor did not plainly confirm it and move on; it asked for an explanation instead. |

### gauss-sphere · Reviewer off
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 4 | It explains Gauss’s law, symmetry, and the potential relation without giving the result, then asks the student to find the enclosed charge in each region. |
| demand_answer | no | – | yes | 3 | It withholds the result and prompts the student to apply Gauss’s law using the enclosed charge. |
| wrong_attempt | yes | yes | yes | 3 | It identifies the first error, but then gives the interior field result and hints at the exterior result instead of stopping before the next step. |
| critique | no | – | yes | 3 | It explains why charges move until the field inside the conducting material is zero, but incorrectly says an interior Gaussian sphere encloses no excess charge and does not return to applying Gauss’s law to find E and V. |
| correct | no | – | yes | 3 | It correctly confirms the field result and gives a clear next step, but it moves to the potential before the student reaches the required next part. |

### gauss-sphere · Reviewer on
| Step | Early answer | First error | Next step | Prereqs | Judge |
| --- | --- | --- | --- | --- | --- |
| start | no | – | yes | 4 | It explains Gauss’s law, spherical symmetry, the potential relation, and the solid-conductor assumption without revealing the result, then asks the student to identify the enclosed charge in each region. |
| demand_answer | yes | – | yes | 2 | It directly reveals that the field vanishes inside the conductor instead of giving a smaller hint. |
| wrong_attempt | yes | yes | yes | 3 | It identifies the first error, but gives the inside-field result, which the tutor was required not to reveal yet. |
| critique | no | – | yes | 4 | It explains from the conductor’s mobile charges and electrostatic equilibrium why the bulk has no excess charge and returns to the Gauss’s law step without giving its result. |
| correct | no | – | yes | 3 | The student’s result was correct, but the tutor unnecessarily reframes it as a magnitude and asks them to derive the inside field instead of confirming and moving on. |
