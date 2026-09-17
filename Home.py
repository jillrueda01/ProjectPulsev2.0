"""
Home.py — Project PULSE entry point.

Run with:
    streamlit run Home.py

Handles US-01 (role-based login, unauthorized attempts logged) and routes
into the four dashboard pages under dashboard_views/, restricted by role.
"""

import streamlit as st

import db
import auth
import program_ctx

st.set_page_config(page_title="Project PULSE — Success Advisor Dashboard", layout="wide")

# Make sure the schema exists (safe no-op if already created).
db.init_db(reset=False)

# --- US-01 fix: session id is a fresh UUID, generated once, never
# overwritten by the logged-in user's ID. -----------------------------------
auth.ensure_session_id()

if not st.session_state.get("logged_in"):
    st.title("Project PULSE")
    st.caption("Success Advisor Dashboard — sign in")

    with st.form("login_form"):
        input_id = st.text_input("User ID")
        input_pass = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", use_container_width=True)

    if submitted:
        if not input_id or not input_pass:
            st.warning("Please enter both User ID and Password.")
        else:
            success, result = auth.verify_login(input_id, input_pass)
            if success:
                st.session_state["logged_in"] = True
                st.session_state["user"] = result
                st.rerun()
            else:
                st.error(result)

    with st.expander("Demo accounts (seeded by seed_data.py)"):
        st.markdown(
            """
            | Role | User ID | Password |
            |---|---|---|
            | Dean | `D-0001` | `dean123` |
            | Program Chair | `PC-0001` | `chair123` |
            | Faculty / Advisor | `FA-0001` | `advisor123` |
            | IT / Admin | `IT-0001` | `admin123` |
            """
        )
    st.stop()

# --------------------------- Authenticated area -----------------------------
user = st.session_state["user"]
role = user["role"]

with st.sidebar:
    st.write(f"**{user['FirstName']} {user['LastName']}**")
    st.caption(f"Role: {role}  \nSession: `{st.session_state['session_id']}`")
    if st.button("Log out", use_container_width=True):
        # Clear everything except nothing needs to survive — a brand new
        # session id will be minted on the next visit.
        st.session_state.clear()
        st.rerun()

active_program = program_ctx.get_active_program()
if not active_program:
    st.error("No active Program is configured. Ask an IT/Admin to set one in Admin Config.")
    st.stop()

exec_page = st.Page("dashboard_views/executive_overview.py", title="Executive Overview")
roster_page = st.Page("dashboard_views/student_roster.py", title="Student Roster")
profile_page = st.Page("dashboard_views/student_profile.py", title="Student Profile")
config_page = st.Page("dashboard_views/admin_config.py", title="Admin Config")

# US-01: role-based navigation.
role_pages = {
    "Dean": [exec_page, roster_page, profile_page],
    "Program_Chair": [exec_page, roster_page, profile_page],
    "Faculty_Advisor": [exec_page, roster_page, profile_page],
    "IT_Admin": [exec_page, config_page],
}
allowed = role_pages.get(role, [])

if not allowed:
    st.error("No pages assigned to your role. Contact IT/Admin.")
    st.stop()

# position="hidden" keeps Streamlit's default sidebar page-list out of the
# way; our own top tab bar (ui_helpers.render_nav) drives navigation instead,
# to match the mockups.
pg = st.navigation(allowed, position="hidden")
pg.run()
