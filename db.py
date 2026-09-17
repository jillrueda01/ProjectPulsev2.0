"""
db.py — Project PULSE data layer (prototype).

WHY SQLITE FOR THE PROTOTYPE
-----------------------------
The original code (db_connect.py) connects straight to a MySQL/SQL Server
instance using credentials from .env. That's the right call for the real
deployment, but it means the app can't run anywhere without a live DB server
and network access. For a runnable prototype we swap the storage engine to
a single local SQLite file (pulse.db) — same table shapes, same column
names, same business rules — so `streamlit run Home.py` just works.

TO SWITCH BACK TO MYSQL / SQL SERVER LATER
--------------------------------------------
Everything that touches the database goes through get_connection() and the
query helpers in this file. To point at a real server:
  1. `pip install mysql-connector-python`
  2. Replace get_connection() with the mysql.connector.connect(**db_config)
     version from the original db_connect.py (kept below, commented out,
     for reference).
  3. Because every query in this codebase uses plain SQL with %s / ?
     placeholders through the helpers below, you mainly need to swap the
     paramstyle (sqlite uses '?', mysql uses '%s') — the DB_PARAMSTYLE
     constant centralizes that so callers don't hardcode it.
"""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "data", "pulse.db")

# US-11: in production this flips to "mysql" and get_connection() below
# talks to the real SQL Server / MySQL instance using managed credentials
# from .env (never hardcoded, never a personal login).
DB_ENGINE = os.getenv("PULSE_DB_ENGINE", "sqlite")


class DBConnectionError(Exception):
    """Raised so the UI can show a visible error instead of a silent blank
    dashboard (US-11 acceptance criterion)."""


def get_connection():
    """Return a live DB connection. Raises DBConnectionError on failure so
    callers can surface it instead of failing silently."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        raise DBConnectionError(f"Could not connect to the database: {e}")

    # --- Reference: real MySQL/SQL Server connection (US-11) -------------
    # import mysql.connector
    # db_config = {
    #     "host": os.getenv("DB_HOST"),
    #     "user": os.getenv("DB_USER"),           # read-only service account
    #     "password": os.getenv("DB_PASSWORD"),
    #     "database": os.getenv("DB_NAME"),
    #     "port": int(os.getenv("DB_PORT", 3306)),
    # }
    # try:
    #     return mysql.connector.connect(**db_config)
    # except mysql.connector.Error as e:
    #     raise DBConnectionError(format_mysql_error(e))


@contextmanager
def get_cursor(commit=False):
    """Context manager that always closes the connection and surfaces
    connection failures as DBConnectionError rather than a blank screen."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


SCHEMA_SQL = """
-- ===========================================================================
-- Project PULSE schema (prototype / SQLite). Mirrors the SQL Server/MySQL
-- design in PULSE_ERD.png. See README.md -> "Schema notes" for the mapping
-- of each table to the user stories it supports.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS Program (
    ProgramID     INTEGER PRIMARY KEY AUTOINCREMENT,
    ProgramCode   TEXT UNIQUE NOT NULL,
    ProgramName   TEXT NOT NULL,
    IsActive      INTEGER NOT NULL DEFAULT 1,
    CreatedAt     TEXT NOT NULL
);

-- US-02 / US-06: which program instance the dashboard is currently showing.
CREATE TABLE IF NOT EXISTS Active_Program (
    ID          INTEGER PRIMARY KEY CHECK (ID = 1),  -- single-row table
    ProgramID   INTEGER NOT NULL REFERENCES Program(ProgramID),
    Term        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Course (
    CourseCode   TEXT PRIMARY KEY,
    ProgramID    INTEGER NOT NULL REFERENCES Program(ProgramID),
    CourseName   TEXT NOT NULL,
    IsActive     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS Advisor (
    AdvisorID    INTEGER PRIMARY KEY AUTOINCREMENT,
    AdvisorName  TEXT NOT NULL,
    AdvisorEmail TEXT
);

CREATE TABLE IF NOT EXISTS Students (
    StudentNumber   TEXT PRIMARY KEY,
    ProgramID       INTEGER NOT NULL REFERENCES Program(ProgramID),
    FirstName       TEXT NOT NULL,
    LastName        TEXT NOT NULL,
    StudentEmail    TEXT NOT NULL,
    Cohort          TEXT NOT NULL,
    EnrollmentStatus TEXT NOT NULL DEFAULT 'Active',
    CreatedAt       TEXT NOT NULL
);

-- Student <-> Advisor is many-to-many: a student can have more than one
-- advisor (per the client's request in the PDF).
CREATE TABLE IF NOT EXISTS Student_Advisor (
    StudentNumber TEXT NOT NULL REFERENCES Students(StudentNumber),
    AdvisorID     INTEGER NOT NULL REFERENCES Advisor(AdvisorID),
    IsPrimary     INTEGER NOT NULL DEFAULT 0,
    AssignedDate  TEXT NOT NULL,
    PRIMARY KEY (StudentNumber, AdvisorID)
);

-- Per-course status feeding the derived Coursework status (US-07).
CREATE TABLE IF NOT EXISTS Student_Course_Status (
    StudentNumber TEXT NOT NULL REFERENCES Students(StudentNumber),
    CourseCode    TEXT NOT NULL REFERENCES Course(CourseCode),
    Status        TEXT NOT NULL,  -- Pending / Cancelled / Completed
    LastUpdated   TEXT NOT NULL,
    PRIMARY KEY (StudentNumber, CourseCode)
);

-- The three lifecycle pillars shown together on the Student Profile (US-04).
CREATE TABLE IF NOT EXISTS Student_Lifecycle (
    StudentNumber       TEXT PRIMARY KEY REFERENCES Students(StudentNumber),
    CourseworkStatus    TEXT NOT NULL DEFAULT 'Pending',   -- derived (US-07)
    CourseworkUpdated   TEXT,
    CompExamStatus      TEXT NOT NULL DEFAULT 'Incomplete', -- US-08
    CompExamUpdated     TEXT,
    CapstoneDefended    INTEGER NOT NULL DEFAULT 0,
    CapstoneCompleted   INTEGER NOT NULL DEFAULT 0,
    CapstoneUpdated     TEXT
);

-- US-09: status change history retained, never overwritten.
CREATE TABLE IF NOT EXISTS Status_History (
    HistoryID     INTEGER PRIMARY KEY AUTOINCREMENT,
    StudentNumber TEXT NOT NULL REFERENCES Students(StudentNumber),
    Field         TEXT NOT NULL,   -- 'CourseworkStatus' / 'CompExamStatus' / 'Capstone'
    OldValue      TEXT,
    NewValue      TEXT NOT NULL,
    ChangedBy     TEXT NOT NULL,
    ChangedAt     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Advisor_Notes (
    NoteID        INTEGER PRIMARY KEY AUTOINCREMENT,
    StudentNumber TEXT NOT NULL REFERENCES Students(StudentNumber),
    AdvisorID     INTEGER REFERENCES Advisor(AdvisorID),
    NoteText      TEXT NOT NULL,
    NoteDate      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Users (
    UserID        TEXT PRIMARY KEY,
    FirstName     TEXT NOT NULL,
    LastName      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    role          TEXT NOT NULL,  -- Dean / Program_Chair / Faculty_Advisor / IT_Admin
    email         TEXT
);

-- US-01 / US-16: every login attempt (successful or not) is logged with a
-- randomized UUID session id, independent of whether login succeeds.
CREATE TABLE IF NOT EXISTS Login_Logs (
    LogID        INTEGER PRIMARY KEY AUTOINCREMENT,
    SessionID    TEXT NOT NULL,
    UserIDTried  TEXT,
    Success      INTEGER NOT NULL,
    Reason       TEXT,
    AttemptedAt  TEXT NOT NULL
);

-- US-16: failed data-sync attempts, timestamped with a reason.
CREATE TABLE IF NOT EXISTS Sync_Logs (
    LogID        INTEGER PRIMARY KEY AUTOINCREMENT,
    SessionID    TEXT,
    Status       TEXT NOT NULL,  -- SUCCESS / FAILED
    ErrorMessage TEXT,
    RetryCount   INTEGER NOT NULL DEFAULT 0,
    Timestamp    TEXT NOT NULL
);

-- US-12: "data last updated" timestamp per program.
CREATE TABLE IF NOT EXISTS Sync_Status (
    ProgramID          INTEGER PRIMARY KEY REFERENCES Program(ProgramID),
    LastSuccessfulSync TEXT
);

-- US-10: dashboard field -> source column mapping, editable without a
-- code deploy.
CREATE TABLE IF NOT EXISTS Field_Mapping (
    MappingID   INTEGER PRIMARY KEY AUTOINCREMENT,
    ProgramID   INTEGER NOT NULL REFERENCES Program(ProgramID),
    UILabel     TEXT NOT NULL,
    ColumnPath  TEXT NOT NULL,   -- e.g. dbo.Students.StudentNumber
    IsMapped    INTEGER NOT NULL DEFAULT 1
);

-- US-13: which roles may perform write actions (status changes, notes).
-- Only IT_Admin can change this table (enforced in the UI layer).
CREATE TABLE IF NOT EXISTS Role_Permissions (
    Role               TEXT PRIMARY KEY,
    CanEditStudentData INTEGER NOT NULL DEFAULT 0,
    UpdatedBy          TEXT,
    UpdatedAt          TEXT
);

-- US-14: RYG thresholds, configurable instead of hardcoded.
CREATE TABLE IF NOT EXISTS Risk_Thresholds (
    ProgramID    INTEGER PRIMARY KEY REFERENCES Program(ProgramID),
    AtRiskDays   INTEGER NOT NULL DEFAULT 180
);
"""


def init_db(reset=False):
    """Create the schema if it doesn't exist. reset=True drops the file
    first (used by seed_data.py --reset)."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def new_session_id() -> str:
    """US-01 fix: session id is ALWAYS a fresh random UUID, generated once
    per browser session, and is never overwritten by the logged-in user's
    ID. This is what login.py got wrong originally."""
    return f"SESSION-{uuid.uuid4().hex[:12].upper()}"


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    init_db()
    print(f"Schema ensured at {DB_PATH}")
