"""
erd_generate.py — renders the Project PULSE ERD as PNG/SVG using Graphviz.

This updates the client's original hand-drawn ERD (in the PDF) to reflect
the requested changes:
  - Program is now its own manageable entity (admin can add more programs)
  - Course belongs to a Program (admin can add courses per program)
  - Student <-> Advisor is many-to-many (a student can have more than one advisor)
  - Capstone tracked as two flags (Defended / Completed) instead of one status
  - Coursework status is derived from Student_Course_Status, not typed directly
  - Status_History retains every change instead of overwriting
"""

import html as html_lib

import graphviz

TABLE_COLOR = "#1F3864"
KEY_ROW_COLOR = "#DCE6F1"


def esc(s):
    """HTML-escape plain text used inside a Graphviz HTML-like label —
    required for any literal '<', '>', or '&' (e.g. the '->' arrows)."""
    return html_lib.escape(str(s), quote=False)


def entity(name, rows):
    """rows: list of (marker, field, type) tuples. marker in {'PK','FK','PF',''}"""
    html = [
        f'<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="6">',
        f'<TR><TD BGCOLOR="{TABLE_COLOR}" COLSPAN="3"><FONT COLOR="white"><B>{esc(name)}</B></FONT></TD></TR>',
    ]
    for marker, field, ftype in rows:
        bg = KEY_ROW_COLOR if marker else "white"
        bold_open, bold_close = ("<B>", "</B>") if marker in ("PK", "PF") else ("", "")
        underline = marker in ("PK", "PF")
        field_esc = esc(field)
        field_html = f"<U>{bold_open}{field_esc}{bold_close}</U>" if underline else f"{bold_open}{field_esc}{bold_close}"
        html.append(
            f'<TR><TD BGCOLOR="{bg}">{esc(marker)}</TD>'
            f'<TD BGCOLOR="{bg}" ALIGN="LEFT">{field_html}</TD>'
            f'<TD BGCOLOR="{bg}" ALIGN="LEFT"><FONT POINT-SIZE="10" COLOR="#555555">{esc(ftype)}</FONT></TD></TR>'
        )
    html.append("</TABLE>")
    return "<" + "".join(html) + ">"


def build():
    g = graphviz.Digraph("PULSE_ERD", format="png")
    g.attr(rankdir="LR", fontname="Helvetica", bgcolor="white", splines="ortho")
    g.attr("node", shape="plain", fontname="Helvetica")
    g.attr("edge", fontname="Helvetica", fontsize="9", color="#666666")

    g.node("Program", entity("Program", [
        ("PK", "ProgramID", "int"),
        ("", "ProgramCode", "text"),
        ("", "ProgramName", "text"),
        ("", "IsActive", "bool"),
        ("", "CreatedAt", "datetime"),
    ]))

    g.node("ActiveProgram", entity("Active_Program", [
        ("PK", "ID", "int (=1)"),
        ("FK", "ProgramID", "-> Program"),
        ("", "Term", "text"),
    ]))

    g.node("Course", entity("Course", [
        ("PK", "CourseCode", "text"),
        ("FK", "ProgramID", "-> Program"),
        ("", "CourseName", "text"),
        ("", "IsActive", "bool"),
    ]))

    g.node("Students", entity("Students", [
        ("PK", "StudentNumber", "text"),
        ("FK", "ProgramID", "-> Program"),
        ("", "FirstName", "text"),
        ("", "LastName", "text"),
        ("", "StudentEmail", "text"),
        ("", "Cohort", "text"),
        ("", "EnrollmentStatus", "text"),
        ("", "CreatedAt", "datetime"),
    ]))

    g.node("Advisor", entity("Advisor", [
        ("PK", "AdvisorID", "int"),
        ("", "AdvisorName", "text"),
        ("", "AdvisorEmail", "text"),
    ]))

    g.node("StudentAdvisor", entity("Student_Advisor", [
        ("PF", "StudentNumber", "-> Students"),
        ("PF", "AdvisorID", "-> Advisor"),
        ("", "IsPrimary", "bool"),
        ("", "AssignedDate", "date"),
    ]))

    g.node("StudentCourseStatus", entity("Student_Course_Status", [
        ("PF", "StudentNumber", "-> Students"),
        ("PF", "CourseCode", "-> Course"),
        ("", "Status", "Pending/Cancelled/Completed"),
        ("", "LastUpdated", "date"),
    ]))

    g.node("StudentLifecycle", entity("Student_Lifecycle", [
        ("PF", "StudentNumber", "-> Students"),
        ("", "CourseworkStatus", "DERIVED"),
        ("", "CourseworkUpdated", "date"),
        ("", "CompExamStatus", "Incomplete/In-Progress/Passed"),
        ("", "CompExamUpdated", "date"),
        ("", "CapstoneDefended", "bool"),
        ("", "CapstoneCompleted", "bool"),
        ("", "CapstoneUpdated", "date"),
    ]))

    g.node("StatusHistory", entity("Status_History", [
        ("PK", "HistoryID", "int"),
        ("FK", "StudentNumber", "-> Students"),
        ("", "Field", "text"),
        ("", "OldValue", "text"),
        ("", "NewValue", "text"),
        ("", "ChangedBy", "text"),
        ("", "ChangedAt", "datetime"),
    ]))

    g.node("AdvisorNotes", entity("Advisor_Notes", [
        ("PK", "NoteID", "int"),
        ("FK", "StudentNumber", "-> Students"),
        ("FK", "AdvisorID", "-> Advisor"),
        ("", "NoteText", "text"),
        ("", "NoteDate", "date"),
    ]))

    g.node("Users", entity("Users", [
        ("PK", "UserID", "text"),
        ("", "FirstName", "text"),
        ("", "LastName", "text"),
        ("", "password_hash", "text"),
        ("", "salt", "text"),
        ("", "role", "Dean/Program_Chair/Faculty_Advisor/IT_Admin"),
        ("", "email", "text"),
    ]))

    g.node("LoginLogs", entity("Login_Logs", [
        ("PK", "LogID", "int"),
        ("", "SessionID", "uuid (US-01 fix)"),
        ("FK", "UserIDTried", "-> Users"),
        ("", "Success", "bool"),
        ("", "Reason", "text"),
        ("", "AttemptedAt", "datetime"),
    ]))

    g.node("SyncLogs", entity("Sync_Logs", [
        ("PK", "LogID", "int"),
        ("", "SessionID", "uuid"),
        ("", "Status", "SUCCESS/FAILED"),
        ("", "ErrorMessage", "text"),
        ("", "RetryCount", "int"),
        ("", "Timestamp", "datetime"),
    ]))

    g.node("SyncStatus", entity("Sync_Status", [
        ("PF", "ProgramID", "-> Program"),
        ("", "LastSuccessfulSync", "datetime"),
    ]))

    g.node("FieldMapping", entity("Field_Mapping", [
        ("PK", "MappingID", "int"),
        ("FK", "ProgramID", "-> Program"),
        ("", "UILabel", "text"),
        ("", "ColumnPath", "text"),
        ("", "IsMapped", "bool"),
    ]))

    g.node("RolePermissions", entity("Role_Permissions", [
        ("PK", "Role", "text"),
        ("", "CanEditStudentData", "bool"),
        ("", "UpdatedBy", "text"),
        ("", "UpdatedAt", "datetime"),
    ]))

    g.node("RiskThresholds", entity("Risk_Thresholds", [
        ("PF", "ProgramID", "-> Program"),
        ("", "AtRiskDays", "int"),
    ]))

    # --- relationships ---
    g.edge("Program", "ActiveProgram", label="1 to 1 (current)")
    g.edge("Program", "Course", label="1 to many")
    g.edge("Program", "Students", label="1 to many")
    g.edge("Program", "FieldMapping", label="1 to many")
    g.edge("Program", "SyncStatus", label="1 to 1")
    g.edge("Program", "RiskThresholds", label="1 to 1")

    g.edge("Students", "StudentAdvisor", label="1 to many")
    g.edge("Advisor", "StudentAdvisor", label="1 to many")

    g.edge("Students", "StudentCourseStatus", label="1 to many")
    g.edge("Course", "StudentCourseStatus", label="1 to many")
    g.edge("StudentCourseStatus", "StudentLifecycle", label="derives", style="dashed")

    g.edge("Students", "StudentLifecycle", label="1 to 1")
    g.edge("StudentLifecycle", "StatusHistory", label="logs changes to", style="dashed")

    g.edge("Students", "AdvisorNotes", label="1 to many")
    g.edge("Advisor", "AdvisorNotes", label="1 to many")

    g.edge("Users", "LoginLogs", label="1 to many")

    return g


if __name__ == "__main__":
    g = build()
    g.render("PULSE_ERD", cleanup=True)
    g.format = "svg"
    g.render("PULSE_ERD", cleanup=True)
    print("Wrote PULSE_ERD.png and PULSE_ERD.svg")
