"""Generate a small demo materials folder (synthetic exams) for testing and the demo."""
from pathlib import Path
import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1] / "demo-materials"

EXAMS = {
    "Linear Algebra": {
        "Exams/LA_exam_2026-06-18.pdf": ["Linear Algebra - Written exam - 18 June 2026 - Duration: 120 minutes - Total 30 points",
            "Exercise 1 (6 pts). Compute the determinant of A = [[2,1,0],[1,3,1],[0,1,2]] and say whether A is invertible.",
            "Exercise 2 (8 pts). Find eigenvalues and eigenvectors of B = [[4,1],[2,3]]. Is B diagonalizable? Justify.",
            "Exercise 3 (8 pts). Let W = span{(1,1,0),(0,1,1)}. Find an orthonormal basis of W with Gram-Schmidt and the orthogonal projection of v=(1,2,3) onto W.",
            "Exercise 4 (8 pts). For which values of k does the system x+y+kz=1, x+ky+z=1, kx+y+z=1 have unique, infinite or no solutions?"],
        "Exams/LA_exam_2026-02-10.pdf": ["Linear Algebra - Written exam - 10 February 2026 - Duration: 120 minutes - Total 30 points",
            "Exercise 1 (5 pts). State the rank-nullity theorem and apply it to f: R^4 -> R^3, f(x)=Mx with M given.",
            "Exercise 2 (9 pts). Diagonalize C = [[1,2,0],[2,1,0],[0,0,3]] with an orthogonal matrix.",
            "Exercise 3 (8 pts). Find the kernel and image of the linear map g(x,y,z)=(x+y, y+z, x-z).",
            "Exercise 4 (8 pts). Prove that eigenvectors associated with distinct eigenvalues are linearly independent."],
        "Exams/LA_exam_2026-02-10_solutions.pdf": ["Solutions - 10 February 2026", "Exercise 1: rank + nullity = 4 ...", "Exercise 2: eigenvalues 3, -1, 3 ..."],
        "Slides/Lecture 07 - Eigenvalues.pdf": ["Lecture 7: Eigenvalues and eigenvectors", "Definition: Av = lambda v, v != 0", "Characteristic polynomial det(A - lambda I) = 0"],
    },
    "Databases": {
        "Exams/DB_exam_2026-07-02.pdf": ["Databases - Exam 2 July 2026 - 90 minutes - Total 31 points",
            "Q1 (1 pt). Which normal form forbids partial dependencies? a) 1NF b) 2NF c) 3NF",
            "Q2 (1 pt). A foreign key must reference: a) a primary or unique key b) any column",
            "Schema: Student(sid, name), Course(cid, title, teacher), Enrollment(sid, cid). Q3 (4 pts). Relational algebra: list the names of students enrolled in every course taught by Rossi.",
            "Schema: Employee(eid, name, dept, salary, hire_date). Q4 (10 pts). SQL: for each department, the average salary of employees hired after 2020, only departments with at least 5 such employees, ordered by average.",
            "Q5 (7 pts). Draw the ER diagram for a library: books, copies, members, loans with dates.",
            "Schema: Member(mid, name), Loan(lid, mid, copy_id, loan_date, return_date). A loan is active while return_date IS NULL. Q6 (4 pts). Write a trigger that prevents a member from having more than 3 active loans."],
        "Exams/DB_exam_2026-01-28.pdf": ["Databases - Exam 28 January 2026 - 90 minutes",
            "Q1 (1 pt). What does ACID stand for?", "Q2 (10 pts). SQL with GROUP BY and nested queries on Orders(id, customer, date, total).",
            "Q3 (7 pts). ER design for a hospital: wards, doctors, patients, admissions.", "Q4 (3 pts). Translate the ER diagram to a logical schema."],
        "Exercises/SQL practice sheet 3.pdf": ["SQL practice sheet 3: GROUP BY, HAVING", "Exercise 1. Count orders per customer.", "Exercise 2. Customers whose total exceeds the average."],
    },
    "Physics II": {
        "Exams/Physics2_exam_2026-06-25.pdf": ["Physics II - Electromagnetism - 25 June 2026 - Part A: 15 multiple choice (30 min), Part B: problems (90 min)",
            "Q1. Two point charges q1 = 2 uC and q2 = -3 uC are 0.5 m apart. Find the force.",
            "Q2. A long straight wire carries I = 5 A. Find B at 10 cm using Ampere's law.",
            "Problem 1 (10 pts). A conducting sphere of radius R carries charge Q. Find E(r) everywhere using Gauss's law and the potential V(r).",
            "Problem 2 (10 pts). A rectangular loop of resistance R, with side L along the field boundary, moves to the right out of a uniform magnetic field B pointing into the page, at constant speed v. Find the induced emf, the current and its direction (Lenz)."],
        "Slides/Ch 23 - Gauss law.pdf": ["Chapter 23: Gauss's law", "Flux Phi = integral E . dA", "Gauss: Phi = Q_enc / epsilon_0"],
    },
}

for course, files in EXAMS.items():
    for rel, pages in files.items():
        p = ROOT / course / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        doc = fitz.open()
        # put exam header + 2 questions per page
        chunks = [pages[0:1] + pages[1:3]] + [pages[i:i + 2] for i in range(3, len(pages), 2)]
        for chunk in chunks:
            if not chunk:
                continue
            page = doc.new_page()
            page.insert_textbox(fitz.Rect(50, 50, 545, 800), "\n\n".join(chunk), fontsize=12)
        doc.save(p)
print("demo materials in", ROOT)
