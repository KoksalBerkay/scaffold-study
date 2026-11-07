---
tags:
  - databases
---
# Quick Links
- **Past Exams**:
	- [[#2 July 2026 Exam]]
		1. **(1 pt)** **Normalization:** *identify* the normal form that forbids partial dependencies
		2. **(1 pt)** **Keys:** *identify* what a foreign key must reference
		3. **(4 pts)** **Relational Algebra:** *list* students enrolled in every course taught by Rossi
		4. **(10 pts)** **SQL Grouping and Aggregation:** *compute* department average salaries for employees hired after 2020, keeping departments with at least five such employees and ordering by average
		5. **(7 pts)** **ER Design:** *draw* a library model with books, copies, members, and dated loans
		6. **(4 pts)** **Triggers:** *write* a trigger that limits each member to three active loans
	- [[#28 January 2026 Exam]]
		1. **(1 pt)** **Transactions:** *state* what ACID stands for
		2. **(10 pts)** **SQL Grouping and Aggregation:** *write* a grouped query with a nested query on `Orders`
		3. **(7 pts)** **ER Design:** *design* a hospital model with wards, doctors, patients, and admissions
		4. **(3 pts)** **Schema Translation:** *translate* an ER diagram into a logical schema
## Past Exams
## 2 July 2026 Exam
### Exercise 1 (1 pt)
Which normal form forbids partial dependencies? a) 1NF b) 2NF c) 3NF

#### Solution
A **functional dependency** states that one attribute or set of attributes determines another attribute. A **partial dependency** occurs when a non-key attribute depends on only part of a composite candidate key. A **composite key** contains more than one attribute.

*Example:* If the key is `(student_id, course_id)` and `student_name` depends only on `student_id`, then `student_name` is partially dependent on the key.

**Second normal form (2NF)** forbids partial dependencies of non-key attributes on candidate keys. First normal form requires atomic attribute values. Third normal form adds a condition about non-key attributes depending transitively on keys.

Common mistake: choosing 3NF because it is a stricter form. The question asks specifically about partial dependencies, which 2NF removes.

#### Solution continued
A **foreign key** is an attribute or set of attributes whose values refer to a key in another or the same relation. A referenced key must uniquely identify a row so the reference is unambiguous.

| Candidate reference | Valid? | Reason |
|---|---|---|
| Primary key | Yes | It uniquely identifies a row. |
| Unique key | Yes | It also uniquely identifies a row. |
| Any column | No | Repeated values would not identify one row. |

#### Final Answer
The correct answer is **b) 2NF**. ^db-2026-07-02-q1

### Exercise 2 (1 pt)
A foreign key must reference: a) a primary or unique key b) any column

#### Solution
A **foreign key** is an attribute or set of attributes whose values refer to a key in another or the same relation. A referenced key must uniquely identify a row so the reference is unambiguous.

| Candidate reference | Valid? | Reason |
|---|---|---|
| Primary key | Yes | It uniquely identifies a row. |
| Unique key | Yes | It also uniquely identifies a row. |
| Any column | No | Repeated values would not identify one row. |

Common mistake: saying that a foreign key may point to any column. The referenced values need a key constraint that guarantees uniqueness.

#### Final Answer
The correct answer is **a) a primary or unique key**. ^db-2026-07-02-q2

### Exercise 3 (4 pts)
Relational algebra: list the names of students enrolled in every course taught by
Rossi.

#### Solution
Relational algebra operates on relations, which are tables of tuples. The **division operator** expresses “for every” queries. Assume the relations are `Student(sid, name)`, `Enrollment(sid, cid)`, `Course(cid, title, teacher)`.

First select courses taught by Rossi and project their identifiers:

$$
C_{\text{Rossi}} = \pi_{\text{cid}}\left(\sigma_{\text{teacher} = \text{'Rossi'}}(\text{Course})\right)
$$

Then divide enrollments by that course set. This yields identifiers of students enrolled in every Rossi course:

$$
S = \text{Enrollment} \div C_{\text{Rossi}}
$$

Finally join the student identifiers with names:

$$
\pi_{\text{name}}(\text{Student} \bowtie S)
$$

*Example:* If Rossi teaches courses with identifiers `C1` and `C2`, only a student enrolled in both appears in `S`.

Common mistake: using a join alone, because a join finds students in at least one selected course, not all selected courses.

#### Final Answer
$$
\pi_{\text{name}}\left(\text{Student} \bowtie \left(\text{Enrollment} \div \pi_{\text{cid}}\left(\sigma_{\text{teacher} = \text{'Rossi'}}(\text{Course})\right)\right)\right)
$$ ^db-2026-07-02-q3

### Exercise 4 (10 pts)
SQL: for each department, the average salary of employees hired after 2020, only departments with at least 5 such employees, ordered by average.

#### Solution
A **grouped query** forms one group for each value of a grouping column. An **aggregate function** computes one result from each group. `AVG` computes an average, and `COUNT` counts rows.

*Example:* For salaries `40, 50, 60` in one department, `AVG(salary)` is `50`.

Filtering before grouping uses `WHERE`; filtering groups after aggregation uses `HAVING`. The hire-date condition belongs in `WHERE`, while the minimum group size belongs in `HAVING`.

Assume `Employee(department, salary, hire_date)`. Use a date literal for the start of 2021 so “after 2020” means hired on or after 1 January 2021.

```sql
SELECT department, AVG(salary) AS average_salary
FROM Employee
WHERE hire_date >= DATE '2021-01-01'
GROUP BY department
HAVING COUNT(*) >= 5
ORDER BY average_salary;
```

Common mistake: putting `COUNT(*) >= 5` in `WHERE`. `WHERE` filters individual rows before groups exist, so aggregate conditions belong in `HAVING`.

#### Final Answer
For each department, include employees hired from 1 January 2021 onward, group them by department, retain groups containing at least five employees, and return the average salary in ascending order.

```sql
SELECT department, AVG(salary) AS average_salary
FROM Employee
WHERE hire_date >= DATE '2021-01-01'
GROUP BY department
HAVING COUNT(*) >= 5
ORDER BY average_salary;
``` ^db-2026-07-02-q4

### Exercise 5 (7 pts)
Draw the ER diagram for a library: books, copies, members, loans with dates.

#### Solution
An **entity** represents an object or concept with its own identity. A **relationship** connects entities. A book may have many physical copies, while each copy belongs to one book. A member may borrow many copies over time. Each loan records the start and return dates.

*Example:* Book `B12` can have copies `C1` and `C2`; member `M7` may loan `C1` from one date until another.

A loan is best modeled as an associative entity because it connects one copy and one member and has its own attributes.

| Entity or relationship | Attributes |
|---|---|
| Book | `book_id` (key), title, author |
| Copy | `copy_id` (key), book_id (reference) |
| Member | `member_id` (key), name |
| Loan | `loan_id` (key), copy_id (reference), member_id (reference), loan_date, return_date |

The cardinalities are Book 1-to-many Copy, Copy 1-to-many Loan over time, and Member 1-to-many Loan over time. Each Loan refers to exactly one Copy and one Member.

Common mistake: connecting Member directly to Copy without a Loan entity. That would lose the dates and the history of repeated loans.

#### Final Answer
Draw `Book(book_id, title, author)` with a one-to-many relationship to `Copy(copy_id, book_id)`. Draw `Member(member_id, name)` and connect it to `Copy` through the associative entity `Loan(loan_id, copy_id, member_id, loan_date, return_date)`. Each copy and member can participate in many loans over time; each loan refers to exactly one copy and one member. ^db-2026-07-02-q5

### Exercise 6 (4 pts)
Write a trigger that prevents a member from having more than 3 active loans.

#### Solution
A **trigger** is database code that runs automatically when a specified event occurs. An active loan has no return date. The trigger must reject an insert if the member already has three active loans.

*Example:* If member `M7` has three active loans, inserting a fourth must fail.

The exact syntax varies by database system. The following is PostgreSQL-style pseudocode; the trigger function checks the existing active loans before accepting a new row.

```sql
CREATE FUNCTION check_active_loan_limit()
RETURNS trigger AS $$
BEGIN
  IF (
    SELECT COUNT(*)
    FROM Loan
    WHERE member_id = NEW.member_id
      AND return_date IS NULL
  ) >= 3 THEN
    RAISE EXCEPTION 'A member may have at most 3 active loans';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_active_loan_limit
BEFORE INSERT ON Loan
FOR EACH ROW
EXECUTE FUNCTION check_active_loan_limit();
```

Common mistake: counting all historical loans. Returned loans are not active, so the query filters to rows with a null return date.

#### Final Answer
Use a `BEFORE INSERT` trigger on `Loan`. Count the member’s rows with a null `return_date` and reject the insert when the count is at least three. ^db-2026-07-02-q6

## 28 January 2026 Exam
### Exercise 1 (1 pt)
What does ACID stand for?

#### Solution
**ACID** names four transaction properties that help preserve correct database behavior. A **transaction** is a logical unit of database work.

*Example:* A bank transfer can debit one account and credit another as one transaction.

- **Atomicity** means all transaction steps happen, or none do.
- **Consistency** means a transaction preserves database rules.
- **Isolation** means concurrent transactions behave as if appropriately separated.
- **Durability** means committed changes survive failures.

Common mistake: confusing durability with consistency. Durability concerns persistence after commit; consistency concerns valid states.

#### Final Answer
ACID stands for **Atomicity, Consistency, Isolation, and Durability**. ^db-2026-01-28-q1

### Exercise 2 (10 pts)
SQL with GROUP BY and nested queries on Orders(id, customer, date, total).

#### Solution
The source gives the schema and topic, but no specific requested output or filtering condition. A unique query therefore cannot be derived. A representative query can demonstrate grouping and a nested query without claiming it is the exam’s exact intended query.

Assume the task is to find customers whose total order value exceeds the average customer total. The inner query computes each customer’s total. The outer query compares those totals to their average.

*Example:* If customer totals are `100` and `200`, their average is `150`, so only the second customer qualifies.

```sql
SELECT customer, SUM(total) AS customer_total
FROM Orders
GROUP BY customer
HAVING SUM(total) > (
  SELECT AVG(customer_total)
  FROM (
    SELECT SUM(total) AS customer_total
    FROM Orders
    GROUP BY customer
  ) AS customer_totals
);
```

The inner grouped query produces one total per customer. The outer `AVG` averages those per-customer totals. `HAVING` compares each customer group’s sum with that scalar result.

Common mistake: comparing each order’s `total` directly with the average order value. That compares individual orders rather than customer-level sums.

#### Final Answer
The extracted prompt does not specify which result to return or what condition to apply, so no unique exam answer can be stated. Under the explicit assumption that the goal is to find customers whose total order value is above the average customer total, the query is:

```sql
SELECT customer, SUM(total) AS customer_total
FROM Orders
GROUP BY customer
HAVING SUM(total) > (
  SELECT AVG(customer_total)
  FROM (
    SELECT SUM(total) AS customer_total
    FROM Orders
    GROUP BY customer
  ) AS customer_totals
);
``` ^db-2026-01-28-q2

### Exercise 3 (7 pts)
ER design for a hospital: wards, doctors, patients, admissions.

#### Solution
A **ward** is a hospital unit, a **doctor** provides care, and a **patient** receives care. An **admission** records a patient’s stay, including its dates and assigned ward.

*Example:* Patient `P4` may have one admission in March and another in June.

Model Admission as an entity because it has dates and connects a patient to a ward. Doctors may care for many admissions, and each admission may involve multiple doctors, so use a many-to-many relationship unless the requirements say otherwise.

| Entity | Suggested attributes |
|---|---|
| Ward | `ward_id` (key), name |
| Doctor | `doctor_id` (key), name |
| Patient | `patient_id` (key), name |
| Admission | `admission_id` (key), patient_id, ward_id, admission_date, discharge_date |

Connect one Patient to many Admissions and one Ward to many Admissions. Connect Doctors and Admissions many-to-many through `AdmissionDoctor(admission_id, doctor_id)`.

Common mistake: storing a single doctor directly on Admission when several doctors may participate in the same stay.

#### Final Answer
Draw `Patient`, `Ward`, `Doctor`, and `Admission` entities. Give `Admission` a unique identifier, patient and ward references, admission date, and discharge date. Connect Patient 1-to-many Admission and Ward 1-to-many Admission. Connect Doctor and Admission many-to-many using an associative entity `AdmissionDoctor`. ^db-2026-01-28-q3

### Exercise 4 (3 pts)
Translate the ER diagram to a logical schema.

#### Solution
A **logical schema** expresses an entity-relationship design as relations with columns and keys. Each entity becomes a table. A one-to-many relationship is represented by placing the one-side key as a foreign key on the many side. A many-to-many relationship becomes a separate table containing both foreign keys.

*Example:* A one-to-many Ward–Admission relationship places `ward_id` in `Admission`.

Because the actual ER diagram is not included in the extracted material, its exact schema cannot be determined. The translation rules still identify the standard mapping.

Common mistake: representing a many-to-many relationship with only one foreign key. That cannot represent multiple links on both sides.

#### Final Answer
The exact logical schema depends on the missing ER diagram. In general, map each entity to a table with its key; place the one-side key as a foreign key on the many side for each one-to-many relationship; and create a separate relation containing both foreign keys for each many-to-many relationship. ^db-2026-01-28-q4
