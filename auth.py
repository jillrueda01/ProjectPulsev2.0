"""
auth.py — login/session handling for Project PULSE.

THE SESSION BUG THAT WAS REPORTED
------------------------------------
In the original login.py:

    if "session_id" not in st.session_state:
        st.session_state.session_id = f"SESSION-{uuid.uuid4().hex[:6].upper()}"
    ...
    if success:
        st.session_state["session_id"] = str(result.get("UserID", "default_admin"))

A random UUID session id was generated correctly on page load, but the
moment login succeeded it was thrown away and replaced with the plain
UserID. That defeats the point of a session id (tracking a browser session
across sync/log events, including *before* a user has authenticated) and
means two logins from the same user collapse into one "session" in the
logs.

THE FIX
--------
session_id is generated once via uuid.uuid4() and never reassigned for the
lifetime of the Streamlit session. Who is logged in is tracked completely
separately in st.session_state["user"].
"""

import streamlit as st

import db
from security import hash_password

MAX_FAILED_ATTEMPTS = 3


def ensure_session_id():
    """Call once near the top of the app. Idempotent — never overwrites an
    existing session id (this is the fix)."""
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = db.new_session_id()
    if "failed_attempts" not in st.session_state:
        st.session_state["failed_attempts"] = 0


def _log_login_attempt(session_id, user_id_tried, success, reason):
    with db.get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO Login_Logs (SessionID, UserIDTried, Success, Reason, AttemptedAt)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, user_id_tried, int(success), reason, db.now_iso()),
        )


def verify_login(user_id: str, password: str):
    """Returns (success: bool, user_row_or_message). Every attempt is
    logged with the session's UUID — not the attempted user id — so
    unauthorized attempts can be traced back to a browser session
    (US-01 AC: unauthorized access attempts are logged)."""
    session_id = st.session_state.get("session_id", "UNKNOWN_SESSION")

    try:
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT UserID, FirstName, LastName, password_hash, salt, role, email "
                "FROM Users WHERE UserID = ?",
                (user_id,),
            )
            user = cur.fetchone()
    except db.DBConnectionError as e:
        _log_login_attempt(session_id, user_id, False, str(e))
        return False, f"Database connection failed: {e}"

    if not user:
        _log_login_attempt(session_id, user_id, False, "Unknown User ID")
        st.session_state.failed_attempts += 1
        return False, "Invalid User ID or password."

    computed, _ = hash_password(password, user["salt"])
    if computed == user["password_hash"]:
        st.session_state.failed_attempts = 0
        _log_login_attempt(session_id, user_id, True, "OK")
        return True, dict(user)

    st.session_state.failed_attempts += 1
    reason = "Wrong password"
    if st.session_state.failed_attempts >= MAX_FAILED_ATTEMPTS:
        reason = f"Wrong password ({st.session_state.failed_attempts} consecutive failures)"
        _log_login_attempt(session_id, user_id, False, reason)
        return False, "Invalid User ID or password. Unauthorized attempts have been logged."

    _log_login_attempt(session_id, user_id, False, reason)
    return False, "Invalid User ID or password."
