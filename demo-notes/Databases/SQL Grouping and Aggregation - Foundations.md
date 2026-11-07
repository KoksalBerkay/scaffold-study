---
tags:
  - databases
status: growing
---
# SQL Grouping and Aggregation - Foundations
This note explains grouped queries, aggregate functions, and the difference between row filtering and group filtering. More examples can be added as further SQL exercises are worked.

Related practice: [[Past Exams#Exercise 4 (10 pts)|department salary averages]] · [[Past Exams#Exercise 2 (10 pts)|customer order totals]]

## Groups and aggregate functions
A **grouped query** partitions rows with the same grouping value into a group. An **aggregate function** computes one value from the rows in a group.

*Example:* `AVG(salary)` computes the average salary in one department group.

Common aggregate functions include `COUNT`, `SUM`, `AVG`, `MIN`, and `MAX`. `COUNT(*)` counts rows. `COUNT(column)` counts non-null values in that column.

## Filtering rows and groups
`WHERE` filters individual input rows before grouping. `HAVING` filters completed groups, often using aggregate values.

*Example:* Filter hires to 2021 onward with `WHERE`, then keep departments with at least five employees using `HAVING COUNT(*) >= 5`.

| Clause | Operates on | Example purpose |
|---|---|---|
| `WHERE` | Individual rows | Keep only employees hired since a date |
| `GROUP BY` | Remaining rows | Form one group per department |
| `HAVING` | Groups | Keep groups meeting an aggregate condition |
| `ORDER BY` | Final result rows | Sort by a selected value |

> [!important] Filter at the right stage
> It is wrong to put an aggregate condition such as `COUNT(*) >= 5` in `WHERE`, because individual rows have not yet been grouped.

## Nested queries with grouped results
A nested query can compute one result and let an outer query use it. To compare each customer’s total with the average customer total, first calculate one sum per customer, then average those sums.

*Example:* If customer totals are `100` and `200`, the average customer total is `150`.

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

The inner query returns one row per customer. The middle query returns the average of those row totals. The outer query returns customers whose grouped sum is greater than that average.

## Query processing order
SQL’s logical processing order explains why `WHERE` cannot use aggregate results: rows are filtered before grouping and aggregation occur. A useful simplified order is `FROM`, `WHERE`, `GROUP BY`, `HAVING`, `SELECT`, then `ORDER BY`.

Common mistake: assuming the written order is the execution order. The query is written with `SELECT` first, but grouping and filtering logically happen before the final select list is produced.
