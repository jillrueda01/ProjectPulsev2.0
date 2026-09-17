"""
seed_data.py — builds realistic sample data for the prototype.

Run directly to (re)build the local database:
    python seed_data.py --reset

This also produces PULSE_Sample_Data.xlsx (Students, Advisors, Courses,
Field Mapping, Data Dictionary sheets) as requested — "create a excel file
tapos ill just update the mysql" — so this file doubles as the source of
truth you can hand to whoever loads the real SQL Server tables.
"""

import argparse
import random
from datetime import datetime, timedelta

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

import db
from security import hash_password

random.seed(42)  # reproducible sample data

# --------------------------------------------------------------------------
# Filipino name pools (first + last names commonly used in PH university
# rosters) — used to replace the placeholder StudentEmail/Name columns in
# the original spreadsheet with realistic fake data, as requested.
# --------------------------------------------------------------------------
FIRST_NAMES = [
    "Angela", "Antonio", "Grace", "Julio", "Louisa", "Patricio", "Ramon",
    "Teresa", "Vanessa", "Miguel", "Josefina", "Ricardo", "Corazon", "Danilo",
    "Marites", "Eduardo", "Rosario", "Fernando", "Imelda", "Gerardo",
    "Leonora", "Bienvenido", "Perla", "Rodrigo", "Cristina", "Alfredo",
    "Remedios", "Benjamin", "Consuelo", "Nestor", "Milagros", "Rogelio",
    "Estrella", "Wilfredo", "Adoracion", "Marlon", "Charmaine", "Jerico",
    "Kristine", "Arnel",
]

LAST_NAMES = [
    "Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia", "Mendoza",
    "Torres", "Flores", "Ilagan", "Salazar", "Bagay", "Del Rosario",
    "Fernandez", "Aquino", "Villanueva", "Ramos", "Castillo", "Domingo",
    "Pascual", "Gonzales", "De Leon", "Manalo", "Navarro", "Aguilar",
    "Panganiban", "Rivera", "Tolentino", "Marasigan", "Lim",
]

ADVISOR_FIRST = ["Liwayway", "Cristina", "Roberto", "Mary Grace", "Emmanuel", "Ana"]
ADVISOR_LAST = ["Ilagan", "Torres", "Moreno", "Bagay", "Cabahug", "Villareal"]

COURSES_MBA = [
    ("BSA501", "Managerial Accounting"),
    ("FIN510", "Corporate Finance"),
    ("MKT505", "Strategic Marketing"),
    ("OPM515", "Operations Management"),
    ("TAM521", "Technology & Innovation Management"),
    ("LDR530", "Organizational Leadership"),
    ("ECO500", "Managerial Economics"),
]

COURSES_MSCS = [
    ("CSC601", "Advanced Algorithms"),
    ("CSC610", "Distributed Systems"),
    ("CSC620", "Machine Learning"),
    ("CSC630", "Software Architecture"),
]

COHORTS = ["2024-Fall", "2025-Spring", "2025-Fall"]


def random_date_2025():
    start = datetime(2025, 1, 1)
    end = datetime(2025, 12, 31)
    delta = end - start
    return (start + timedelta(days=random.randint(0, delta.days))).strftime("%Y-%m-%d")


def build_students(n, program_id, prefix):
    """Returns a list of student dicts with unique, realistic PH names."""
    used_numbers = set()
    students = []
    for i in range(n):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        number = f"{prefix}-{2401 + i}"
        while number in used_numbers:
            number = f"{prefix}-{2401 + i + random.randint(1, 50)}"
        used_numbers.add(number)
        email = f"{first.lower().replace(' ', '')}.{last.lower().replace(' ', '')}{i}@mapua.edu.ph"
        students.append({
            "StudentNumber": number,
            "ProgramID": program_id,
            "FirstName": first,
            "LastName": last,
            "StudentEmail": email,
            "Cohort": random.choice(COHORTS),
            "EnrollmentStatus": "Active",
            "CreatedAt": db.now_iso(),
        })
    return students


def seed(reset=True):
    db.init_db(reset=reset)

    with db.get_cursor(commit=True) as cur:
        # --- Programs (US-02 / US-06: more than one program can exist) ---
        cur.execute(
            "INSERT INTO Program (ProgramCode, ProgramName, IsActive, CreatedAt) VALUES (?,?,?,?)",
            ("MBA", "MBA (E.T. Yuchengco School of Business)", 1, db.now_iso()),
        )
        mba_id = cur.lastrowid
        cur.execute(
            "INSERT INTO Program (ProgramCode, ProgramName, IsActive, CreatedAt) VALUES (?,?,?,?)",
            ("MSCS", "MS Computer Science (School of EECE)", 1, db.now_iso()),
        )
        mscs_id = cur.lastrowid

        cur.execute("INSERT INTO Active_Program (ID, ProgramID, Term) VALUES (1, ?, ?)",
                    (mba_id, "Fall 2025-2026"))

        # --- Courses per program (admin can add more later) ---
        for code, name in COURSES_MBA:
            cur.execute("INSERT INTO Course (CourseCode, ProgramID, CourseName, IsActive) VALUES (?,?,?,1)",
                        (code, mba_id, name))
        for code, name in COURSES_MSCS:
            cur.execute("INSERT INTO Course (CourseCode, ProgramID, CourseName, IsActive) VALUES (?,?,?,1)",
                        (code, mscs_id, name))

        # --- Advisors ---
        advisor_ids = []
        for fn, ln in zip(ADVISOR_FIRST, ADVISOR_LAST):
            cur.execute("INSERT INTO Advisor (AdvisorName, AdvisorEmail) VALUES (?,?)",
                        (f"{fn} {ln}", f"{fn.split()[0].lower()}.{ln.lower()}@mapua.edu.ph"))
            advisor_ids.append(cur.lastrowid)

        # --- Students (MBA: 18 to match the original mock; MSCS: 8) ---
        mba_students = build_students(18, mba_id, "MBA")
        mscs_students = build_students(8, mscs_id, "MSCS")
        all_students = mba_students + mscs_students

        for s in all_students:
            cur.execute(
                """INSERT INTO Students
                   (StudentNumber, ProgramID, FirstName, LastName, StudentEmail, Cohort, EnrollmentStatus, CreatedAt)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (s["StudentNumber"], s["ProgramID"], s["FirstName"], s["LastName"],
                 s["StudentEmail"], s["Cohort"], s["EnrollmentStatus"], s["CreatedAt"]),
            )

            # 1 or 2 advisors per student (many-to-many, as requested)
            primary_advisor = random.choice(advisor_ids)
            cur.execute(
                "INSERT INTO Student_Advisor (StudentNumber, AdvisorID, IsPrimary, AssignedDate) VALUES (?,?,1,?)",
                (s["StudentNumber"], primary_advisor, random_date_2025()),
            )
            if random.random() < 0.3:
                second = random.choice([a for a in advisor_ids if a != primary_advisor])
                cur.execute(
                    "INSERT INTO Student_Advisor (StudentNumber, AdvisorID, IsPrimary, AssignedDate) VALUES (?,?,0,?)",
                    (s["StudentNumber"], second, random_date_2025()),
                )

            # Per-course statuses -> derive Coursework status (US-07)
            course_list = COURSES_MBA if s["ProgramID"] == mba_id else COURSES_MSCS
            n_courses = random.randint(len(course_list) - 2, len(course_list))
            chosen_courses = random.sample(course_list, n_courses)
            course_statuses = []
            for code, _ in chosen_courses:
                status = random.choices(
                    ["Completed", "Pending", "Cancelled"], weights=[82, 14, 4]
                )[0]
                course_statuses.append(status)
                cur.execute(
                    """INSERT INTO Student_Course_Status (StudentNumber, CourseCode, Status, LastUpdated)
                       VALUES (?,?,?,?)""",
                    (s["StudentNumber"], code, status, random_date_2025()),
                )

            from business_logic import derive_coursework_status, derive_capstone_status
            coursework_status = derive_coursework_status(course_statuses)

            comp_exam_status = "Incomplete"
            if coursework_status == "Completed":
                comp_exam_status = random.choices(
                    ["In-Progress", "Passed", "Incomplete"], weights=[50, 35, 15]
                )[0]

            defended, completed = False, False
            if comp_exam_status == "Passed":
                defended = random.random() < 0.55
                completed = defended and random.random() < 0.4

            cur.execute(
                """INSERT INTO Student_Lifecycle
                   (StudentNumber, CourseworkStatus, CourseworkUpdated, CompExamStatus, CompExamUpdated,
                    CapstoneDefended, CapstoneCompleted, CapstoneUpdated)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (s["StudentNumber"], coursework_status, random_date_2025(),
                 comp_exam_status, random_date_2025(),
                 int(defended), int(completed), random_date_2025()),
            )

            # A sample advisor note for realism (US supports Advisor_Notes)
            if random.random() < 0.6:
                cur.execute(
                    "INSERT INTO Advisor_Notes (StudentNumber, AdvisorID, NoteText, NoteDate) VALUES (?,?,?,?)",
                    (s["StudentNumber"], primary_advisor,
                     "Initial advising check-in for the term. No blockers reported at this time.",
                     random_date_2025()),
                )

        # --- Users: one per role (US-01) ---
        users = [
            ("D-0001", "Mary Grace", "Piatos", "Dean", "mgpiatos@mapua.edu.ph", "dean123"),
            ("PC-0001", "Carlos", "Villareal", "Program_Chair", "cvillareal@mapua.edu.ph", "chair123"),
            ("FA-0001", "Liwayway", "Ilagan", "Faculty_Advisor", "lilagan@mapua.edu.ph", "advisor123"),
            ("IT-0001", "Jillian Ysabel", "Rueda", "IT_Admin", "jrueda@mapua.edu.ph", "admin123"),
        ]
        for uid, fn, ln, role, email, pw in users:
            pw_hash, salt = hash_password(pw)
            cur.execute(
                "INSERT INTO Users (UserID, FirstName, LastName, password_hash, salt, role, email) VALUES (?,?,?,?,?,?,?)",
                (uid, fn, ln, pw_hash, salt, role, email),
            )

        # --- Role permissions (US-13): Faculty/Advisor can edit; everyone
        # else is view-only until IT_Admin changes it.
        for role, can_edit in [("Dean", 0), ("Program_Chair", 0), ("Faculty_Advisor", 1), ("IT_Admin", 0)]:
            cur.execute(
                "INSERT INTO Role_Permissions (Role, CanEditStudentData, UpdatedBy, UpdatedAt) VALUES (?,?,?,?)",
                (role, can_edit, "system_seed", db.now_iso()),
            )

        # --- Risk thresholds (US-14) ---
        cur.execute("INSERT INTO Risk_Thresholds (ProgramID, AtRiskDays) VALUES (?,180)", (mba_id,))
        cur.execute("INSERT INTO Risk_Thresholds (ProgramID, AtRiskDays) VALUES (?,180)", (mscs_id,))

        # --- Field mapping (US-10) ---
        default_fields = [
            ("Student ID", "dbo.Students.StudentNumber"),
            ("Student Name", "dbo.Students.FirstName, dbo.Students.LastName"),
            ("Cohort", "dbo.Students.Cohort"),
            ("Coursework Status", "dbo.Student_Lifecycle.CourseworkStatus"),
            ("Comprehensive Exam Status", "dbo.Student_Lifecycle.CompExamStatus"),
            ("Capstone Status", "dbo.Student_Lifecycle.CapstoneDefended, dbo.Student_Lifecycle.CapstoneCompleted"),
            ("Assigned Advisor", "dbo.Advisor.AdvisorName"),
        ]
        for pid in (mba_id, mscs_id):
            for label, col in default_fields:
                cur.execute(
                    "INSERT INTO Field_Mapping (ProgramID, UILabel, ColumnPath, IsMapped) VALUES (?,?,?,1)",
                    (pid, label, col),
                )

        # --- Sync status / logs (US-12, US-16) ---
        cur.execute("INSERT INTO Sync_Status (ProgramID, LastSuccessfulSync) VALUES (?,?)", (mba_id, db.now_iso()))
        cur.execute("INSERT INTO Sync_Status (ProgramID, LastSuccessfulSync) VALUES (?,?)", (mscs_id, db.now_iso()))
        cur.execute(
            "INSERT INTO Sync_Logs (SessionID, Status, ErrorMessage, RetryCount, Timestamp) VALUES (?,?,?,?,?)",
            (None, "SUCCESS", None, 0, db.now_iso()),
        )

    print(f"Seeded {len(all_students)} students across 2 programs into {db.DB_PATH}")
    return mba_id, mscs_id


# ---------------------------------------------------------------------------
# Excel export — mirrors what the client asked for directly in the PDF:
# "with the schema create a excel file tapos ill just update the mysql"
# ---------------------------------------------------------------------------
def export_excel(path="PULSE_Sample_Data.xlsx"):
    HEADER_FILL = PatternFill("solid", fgColor="1F3864")
    HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
    BODY_FONT = Font(name="Arial", size=10)

    wb = openpyxl.Workbook()

    def write_sheet(ws, headers, rows):
        ws.append(headers)
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=c)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center")
        for r in rows:
            ws.append(r)
        for c in range(1, len(headers) + 1):
            col_letter = get_column_letter(c)
            max_len = max([len(str(headers[c - 1]))] + [len(str(r[c - 1])) for r in rows] + [10])
            ws.column_dimensions[col_letter].width = min(max_len + 2, 45)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = BODY_FONT

    with db.get_cursor() as cur:
        cur.execute("""
            SELECT s.StudentNumber, s.FirstName, s.LastName, s.StudentEmail, s.Cohort,
                   s.EnrollmentStatus, p.ProgramCode,
                   GROUP_CONCAT(a.AdvisorName, ' | ') AS Advisors
            FROM Students s
            JOIN Program p ON p.ProgramID = s.ProgramID
            LEFT JOIN Student_Advisor sa ON sa.StudentNumber = s.StudentNumber
            LEFT JOIN Advisor a ON a.AdvisorID = sa.AdvisorID
            GROUP BY s.StudentNumber
            ORDER BY p.ProgramCode, s.LastName
        """)
        student_rows = [tuple(r) for r in cur.fetchall()]

        cur.execute("SELECT AdvisorID, AdvisorName, AdvisorEmail FROM Advisor ORDER BY AdvisorName")
        advisor_rows = [tuple(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT c.CourseCode, c.CourseName, p.ProgramCode, c.IsActive
            FROM Course c JOIN Program p ON p.ProgramID = c.ProgramID
            ORDER BY p.ProgramCode, c.CourseCode
        """)
        course_rows = [tuple(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT s.StudentNumber, s.LastName, s.FirstName, sl.CourseworkStatus, sl.CompExamStatus,
                   CASE WHEN sl.CapstoneCompleted THEN 'Completed'
                        WHEN sl.CapstoneDefended THEN 'Defended for Completion'
                        WHEN sl.CompExamStatus='Passed' THEN 'In-Progress'
                        ELSE 'Not Eligible' END AS CapstoneStatus,
                   sl.CourseworkUpdated, sl.CompExamUpdated, sl.CapstoneUpdated
            FROM Student_Lifecycle sl JOIN Students s ON s.StudentNumber = sl.StudentNumber
            ORDER BY s.LastName
        """)
        lifecycle_rows = [tuple(r) for r in cur.fetchall()]

        cur.execute("SELECT ProgramID, UILabel, ColumnPath, IsMapped FROM Field_Mapping WHERE ProgramID=1")
        mapping_rows = [tuple(r) for r in cur.fetchall()]

    ws1 = wb.active
    ws1.title = "Students"
    write_sheet(ws1, ["StudentNumber", "FirstName", "LastName", "StudentEmail", "Cohort",
                       "EnrollmentStatus", "Program", "Advisor(s)"], student_rows)

    ws2 = wb.create_sheet("Advisors")
    write_sheet(ws2, ["AdvisorID", "AdvisorName", "AdvisorEmail"], advisor_rows)

    ws3 = wb.create_sheet("Courses")
    write_sheet(ws3, ["CourseCode", "CourseName", "Program", "IsActive"], course_rows)

    ws4 = wb.create_sheet("Lifecycle Status")
    write_sheet(ws4, ["StudentNumber", "LastName", "FirstName", "CourseworkStatus", "CompExamStatus",
                       "CapstoneStatus", "CourseworkUpdated", "CompExamUpdated", "CapstoneUpdated"],
                lifecycle_rows)

    ws5 = wb.create_sheet("Field Mapping (US-10)")
    write_sheet(ws5, ["ProgramID", "DashboardField", "SourceColumn", "IsMapped"], mapping_rows)

    ws6 = wb.create_sheet("Data Dictionary")
    dd_rows = [
        ("Students.StudentNumber", "text", "Primary key. Format: {PROGRAMCODE}-{4-digit}."),
        ("Students.StudentEmail", "text", "Fake data for prototype — replace with real institutional email on import."),
        ("Student_Advisor", "junction table", "Many-to-many: a student may have more than one advisor (IsPrimary flags the main one)."),
        ("Student_Course_Status.Status", "enum", "Pending / Cancelled / Completed (US-07)."),
        ("Student_Lifecycle.CourseworkStatus", "enum, DERIVED", "Computed from Student_Course_Status — do not edit directly."),
        ("Student_Lifecycle.CompExamStatus", "enum", "Incomplete / In-Progress / Passed (US-08)."),
        ("Student_Lifecycle.CapstoneDefended/Completed", "boolean pair", "Capstone requires CompExamStatus='Passed' first (US-09 gating)."),
        ("Status_History", "table", "Every status change is appended here, never overwritten (US-09 AC)."),
    ]
    write_sheet(ws6, ["Field", "Type", "Notes"], dd_rows)

    wb.save(path)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop and rebuild the local database")
    parser.add_argument("--excel", default="PULSE_Sample_Data.xlsx")
    args = parser.parse_args()
    seed(reset=args.reset)
    out = export_excel(args.excel)
    print(f"Excel export written to {out}")
