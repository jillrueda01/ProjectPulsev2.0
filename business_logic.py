"""
business_logic.py — rules that must be applied consistently everywhere a
student's status is read or changed. Keeping these in one module (instead
of copy-pasted into each page) is the main lesson learned from the original
code, where the same status-mapping logic was starting to drift between
db_connect.py and the dashboard views.
"""

from datetime import datetime, date
import db

COURSEWORK_VALUES = ["Pending", "Cancelled", "Completed"]          # US-07
COMP_EXAM_VALUES = ["Incomplete", "In-Progress", "Passed"]         # US-08
COURSE_STATUS_VALUES = ["Pending", "Cancelled", "Completed"]

# Colorblind-safe palette (Okabe–Ito), never color-only: every indicator
# also carries a short text label / symbol (US-14 AC: colorblind-safe).
RYG = {
    "green":  {"hex": "#0072B2", "label": "On Track", "symbol": "\u25CF"},  # blue
    "amber":  {"hex": "#E69F00", "label": "Watch",     "symbol": "\u25B2"},  # orange
    "red":    {"hex": "#D55E00", "label": "At Risk",   "symbol": "\u2716"},  # vermillion
}


# ---------------------------------------------------------------------------
# US-07: Coursework status is DERIVED from the per-course rows, never typed
# in directly on the dashboard.
# ---------------------------------------------------------------------------
def derive_coursework_status(course_statuses: list[str]) -> str:
    if not course_statuses:
        return "Pending"
    if any(s == "Cancelled" for s in course_statuses):
        return "Cancelled"
    if all(s == "Completed" for s in course_statuses):
        return "Completed"
    return "Pending"


# ---------------------------------------------------------------------------
# US-09: Capstone has two independent flags (Defended, Completed) so a
# student can be "Defended for Completion" while revisions are still open.
# Gated by US-08: capstone cannot begin until CompExamStatus == 'Passed'.
# ---------------------------------------------------------------------------
def capstone_eligible(comp_exam_status: str) -> bool:
    return comp_exam_status == "Passed"


def derive_capstone_status(comp_exam_status: str, defended: bool, completed: bool) -> str:
    if not capstone_eligible(comp_exam_status):
        return "Not Eligible"
    if defended and completed:
        return "Completed"
    if defended and not completed:
        return "Defended for Completion"
    return "In-Progress"


# ---------------------------------------------------------------------------
# US-14: RYG indicator per lifecycle stage. Thresholds live in
# Risk_Thresholds (AtRiskDays) so they're configurable, not hardcoded.
# ---------------------------------------------------------------------------
def days_since(iso_date: str | None) -> int:
    if not iso_date:
        return 0
    try:
        d = datetime.strptime(iso_date[:10], "%Y-%m-%d").date()
    except ValueError:
        return 0
    return (date.today() - d).days


def stage_indicator(status: str, last_updated: str | None, at_risk_days: int) -> dict:
    """Returns one of RYG['green'|'amber'|'red'] for a single stage."""
    completed_values = {"Completed", "Passed", "Defended for Completion"}
    blocked_values = {"Cancelled", "Not Eligible"}
    if status in completed_values:
        return RYG["green"]
    if status in blocked_values:
        return RYG["red"]
    if days_since(last_updated) >= at_risk_days:
        return RYG["red"]
    if days_since(last_updated) >= at_risk_days * 0.6:
        return RYG["amber"]
    return RYG["green"]


def get_at_risk_days(program_id: int) -> int:
    with db.get_cursor() as cur:
        cur.execute("SELECT AtRiskDays FROM Risk_Thresholds WHERE ProgramID=?", (program_id,))
        row = cur.fetchone()
        return row["AtRiskDays"] if row else 180


# ---------------------------------------------------------------------------
# US-13: permission check. View-only roles cannot write; blocked attempts
# are logged (feeds the same Sync/Login-style log the admin screen reads).
# ---------------------------------------------------------------------------
def can_edit(role: str) -> bool:
    with db.get_cursor() as cur:
        cur.execute("SELECT CanEditStudentData FROM Role_Permissions WHERE Role=?", (role,))
        row = cur.fetchone()
        return bool(row and row["CanEditStudentData"])


def log_blocked_edit(role: str, user_id: str, student_number: str, attempted_field: str):
    with db.get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO Sync_Logs (SessionID, Status, ErrorMessage, RetryCount, Timestamp)
               VALUES (?, 'FAILED', ?, 0, ?)""",
            (
                None,
                f"Blocked edit: role '{role}' (user {user_id}) attempted to change "
                f"{attempted_field} for student {student_number} without edit permission.",
                db.now_iso(),
            ),
        )


# ---------------------------------------------------------------------------
# US-09 (status history retained, not overwritten)
# ---------------------------------------------------------------------------
def record_status_change(student_number: str, field: str, old_value, new_value, changed_by: str):
    with db.get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO Status_History (StudentNumber, Field, OldValue, NewValue, ChangedBy, ChangedAt)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (student_number, field, str(old_value), str(new_value), changed_by, db.now_iso()),
        )
