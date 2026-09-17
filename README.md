# Project PULSE — Success Advisor Dashboard (Prototype)

A working prototype of the Streamlit dashboard described in
`Project_PULSE__Calypso_s_Business_Analyst___Developer_Documentation.pdf`
and the four `MBA_Dashboard_0X_*.jpg` mockups, implementing **User Stories
US-01 through US-16** from `Copy_of_Product_Backlog_for_Project_Pulse.xlsx`.

## Stack

- **Streamlit** for the UI (kept — matches your existing code and skillset)
- **SQLite** as the database for this prototype, instead of the MySQL/SQL
  Server instance the original code pointed at. This is the one deliberate
  stack change, and it's purely so the app **runs immediately with zero
  setup** — no server, no credentials, no network. `db.py` is written so
  that swapping back to a real MySQL/SQL Server is a small, contained
  change (see "Going to production" below) — every other file talks to the
  database only through `db.py` / `get_cursor()`.

## How to run it

```bash
cd pulse
pip install -r requirements.txt

# builds the local database with realistic sample data (Filipino names,
# 2 programs, courses, advisors, students) AND writes PULSE_Sample_Data.xlsx
python seed_data.py --reset

streamlit run Home.py
```

Open the URL Streamlit prints (usually http://localhost:8501). Log in with
one of the seeded demo accounts (also shown on the login screen):

| Role | User ID | Password |
|---|---|---|
| Dean | `D-0001` | `dean123` |
| Program Chair | `PC-0001` | `chair123` |
| Faculty / Advisor | `FA-0001` | `advisor123` |
| IT / Admin | `IT-0001` | `admin123` |

To start over with fresh random sample data at any point, just re-run
`python seed_data.py --reset`.

## What was actually broken in the original code (and the fix)

1. **Session ID bug (the one you flagged).** In `login.py`, a random UUID
   session id was generated on page load, but the moment login succeeded
   it was overwritten with the plain UserID:
   ```python
   st.session_state["session_id"] = str(result.get("UserID", "default_admin"))
   ```
   This defeats the purpose of a session id (tracing a browser session
   across log events, *including failed attempts before login*) and
   collapses two different logins by the same user into one "session" in
   the logs. **Fixed** in `auth.py` / `db.new_session_id()`: the session id
   is generated once via `uuid.uuid4()` and is never reassigned. Who is
   logged in is tracked completely separately in `st.session_state["user"]`.

2. **Non-clickable roster rows.** The original `student_roster.py` (not
   included in your upload, but referenced) had no way to jump to a
   specific student. `dashboard_views/student_roster.py` now uses
   `st.dataframe(..., on_select="rerun", selection_mode="single-row")` —
   clicking any row stores that student's ID in session state and routes
   straight to Student Profile (US-04).

3. **Student Profile buttons not wired up / stale `last_updated`.** The
   Comprehensive Exam and Capstone controls in `student_profile.py` now
   actually write to the database, stamp `LastUpdated` with the real time
   of the change, and append to `Status_History` instead of silently
   overwriting the previous value (US-04, US-09).

4. **Business rules the client asked for in the PDF, now enforced
   everywhere instead of only in the mockup:**
   - Coursework status is **derived** from each course's status, never
     typed in directly (`business_logic.derive_coursework_status`).
   - Capstone is **locked** until Comprehensive Exam = "Passed"
     (`business_logic.capstone_eligible`).
   - Capstone tracks **Defended** and **Completed** as two separate flags,
     so a student can be "Defended for Completion" while revisions are
     still open.
   - A student can now have **more than one advisor**
     (`Student_Advisor` is a many-to-many join table).
   - Programs and Courses are first-class, admin-manageable records
     (`Program`, `Course` tables + the "Add a new Program" form in Admin
     Config) instead of hardcoded MBA-only values.

## User story coverage (US-01 → US-16)

| US | What it needed | Where it lives |
|---|---|---|
| US-01 | Role-based login, nav restricted by role, unauthorized attempts logged | `auth.py`, `Home.py` (role→page map), `Login_Logs` table |
| US-02 | Admin selects/creates active Program; all views filter to it; nothing hardcoded | `program_ctx.py`, `Active_Program` table, Admin Config |
| US-03 | Program Chair sees full roster w/ status, sortable, live from DB | `student_roster.py` (click any column header to sort) |
| US-04 | One-click student profile showing all 3 lifecycle pillars + last-updated | `student_profile.py` |
| US-05 | Dean sees total enrolled headcount, labeled with term, on landing view | `executive_overview.py` (default page after login for Dean) |
| US-06 | Filter roster by cohort/intake, clearable | `student_roster.py` cohort dropdown |
| US-07 | Coursework = Pending/Cancelled/Completed exactly, derived from live data | `business_logic.derive_coursework_status`, `Student_Course_Status` |
| US-08 | Comp Exam = In-Progress/Incomplete/Passed, visible on list + profile | `Student_Lifecycle.CompExamStatus`, shown in both views |
| US-09 | Capstone = In-Progress/Defended for Completion, history retained | `derive_capstone_status`, `Status_History` table |
| US-10 | Field-mapping config screen, no code deploy needed, invalid mappings flagged | Admin Config → "Field Mapping" section |
| US-11 | Live SQL Server connection, managed creds, visible error not blank screen | `db.py` (`DBConnectionError`), Admin Config → "Database Connection" |
| US-12 | "Data last updated" timestamp on every major view | `Sync_Status` table, shown on Overview + Roster |
| US-13 | View-only vs edit permission levels, only IT/Admin can change them | `Role_Permissions` table, Admin Config (IT/Admin-only page) |
| US-14 | Colorblind-safe RYG indicator per stage, configurable thresholds | `business_logic.RYG` (Okabe–Ito palette + symbols, not color-only), `Risk_Thresholds` |
| US-15 | Search by name or ID, partial match, clear "no results" state | Roster search box + Student Profile picker |
| US-16 | Failed syncs logged with reason, viewable in admin screen, repeated-failure banner | `Sync_Logs` table, Admin Config → "System / Sync Logs", banner on Overview |

## Files

```
pulse/
├── Home.py                       # entry point: login + role routing
├── db.py                         # DB connection + schema (SQLite; MySQL notes inline)
├── business_logic.py             # status derivation, RYG, permission checks (read this first)
├── auth.py                       # login/session handling (the UUID fix lives here)
├── security.py                   # password hashing (no Streamlit dependency)
├── program_ctx.py                # active-program helpers (US-02)
├── ui_helpers.py                 # shared header/nav chrome matching the mockups
├── seed_data.py                  # sample data generator + Excel export
├── erd_generate.py               # regenerates PULSE_ERD.png/.svg from the schema
├── dashboard_views/
│   ├── executive_overview.py     # US-05, US-12, US-16 banner
│   ├── student_roster.py         # US-03, US-06, US-14, US-15, clickable rows
│   ├── student_profile.py        # US-04, US-07/08/09, US-13
│   └── admin_config.py           # US-02, US-10, US-11, US-13, US-14, US-16
├── requirements.txt
└── .env.example                  # for when you switch to real MySQL/SQL Server
```

`db_connect.py`, `field_mapping.py`, `login.py`, and `system_log.py` from
your original upload are effectively superseded by `db.py` +
`business_logic.py` + `auth.py` + `Home.py` above — I kept the same table
and column names wherever possible so migrating the real MySQL schema over
is mostly mechanical.

## Going to production (swapping SQLite for the real DB)

1. `pip install mysql-connector-python cryptography`
2. In `db.py`, replace `get_connection()`'s body with the commented
   MySQL/SQL Server version right below it (it's already written, just
   commented out), reading `DB_HOST` / `DB_USER` / `DB_PASSWORD` /
   `DB_NAME` / `DB_PORT` from `.env` via a **read-only service account**
   (US-11 AC).
3. Set `PULSE_DB_ENGINE=mysql` in `.env`.
4. Run the real schema (see `PULSE_ERD.png` / `.svg`) against SQL Server,
   or hand `PULSE_Sample_Data.xlsx` to whoever owns that migration — it has
   one sheet per table with the exact columns this app expects.
5. Everything else (business rules, permission checks, UI) needs no
   changes, because it all goes through `db.get_cursor()`.

## What I'd extend first (beyond US-16)

Roughly in priority order, based on what the mockups (`MBA_Dashboard_04`)
and the backlog beyond US-16 hint at:

1. **"Clone this configuration" for a new program instance (US-26+).** The
   Admin Config mockup shows a one-click clone of field mappings/KPI
   tiles/thresholds into a brand-new, data-isolated program. `program_ctx.py`
   already has the pieces (`create_program` + default mapping/threshold
   seeding); wiring a "Clone from existing" button is a small follow-up.
2. **Term-over-term trend chart** on the Executive Overview (visible but
   disabled in the mockup's KPI Tile Configuration) — needs at least two
   terms of historical `Sync_Status` snapshots to chart against.
3. **Configurable terminology per program** (mockup's "Capstone Label" /
   "Comprehensive Exam Label" editors) — swap the hardcoded strings in
   `business_logic.py` for a `Program_Terminology` lookup table.
4. **Real SQL Server integration (US-11)** — this prototype proves the UI
   and business rules; the production cutover is the step in the section
   above.
5. **Search-as-you-type** on the roster (US-15's AC allows "on submit,
   minimum viable," which is what's implemented) — Streamlit's
   `st.dataframe` filtering already reruns on every keystroke in the text
   box, so this mostly already behaves like live search; a debounce would
   smooth it out for larger rosters.
6. **Automated tests** for `business_logic.py` — it's the one module with
   zero UI dependency, so it's the cheapest place to add pytest coverage
   before this grows past a prototype.

## Files delivered alongside this prototype

- `PULSE_Sample_Data.xlsx` — Students / Advisors / Courses / Lifecycle
  Status / Field Mapping / Data Dictionary sheets, generated from the same
  seed data the app runs on.
- `PULSE_ERD.png` / `PULSE_ERD.svg` — the updated schema diagram (adds
  Program/Course as manageable entities, many-to-many Student↔Advisor,
  split Capstone Defended/Completed flags, and Status_History).
