"""
ui_helpers.py — shared header/nav chrome so every page looks like the
provided mockups (MBA_Dashboard_0X_*.jpg): a navy top bar with the school
breadcrumb + title, a role badge pill top-right, a "Program instance" line,
and a row of tab buttons for navigation.
"""

import streamlit as st

ROLE_LABELS = {
    "Dean": "DEAN VIEW",
    "Program_Chair": "PROGRAM CHAIR / ADVISOR VIEW",
    "Faculty_Advisor": "FACULTY / PROGRAM ADVISOR VIEW",
    "IT_Admin": "IT / ADMIN VIEW",
}

ROLE_BADGE_COLOR = {
    "Dean": "#8a6d1d",
    "Program_Chair": "#8a6d1d",
    "Faculty_Advisor": "#8a6d1d",
    "IT_Admin": "#1b2a4a",
}

NAV_ITEMS = [
    ("Overview", "dashboard_views/executive_overview.py"),
    ("Roster", "dashboard_views/student_roster.py"),
    ("Student Profile", "dashboard_views/student_profile.py"),
    ("Admin Config", "dashboard_views/admin_config.py"),
]

# Which nav tabs each role is allowed to see (mirrors login.py's role gate)
ROLE_PAGES = {
    "Dean": ["Overview", "Roster", "Student Profile"],
    "Program_Chair": ["Overview", "Roster", "Student Profile"],
    "Faculty_Advisor": ["Overview", "Roster", "Student Profile"],
    "IT_Admin": ["Overview", "Admin Config"],
}


def inject_css():
    st.markdown(
        """
        <style>
        .pulse-header {background:#16233f; padding: 14px 24px; border-radius: 6px;
            margin-bottom: 4px; color: white;}
        .pulse-breadcrumb {font-size: 12px; letter-spacing: 1px; color: #b7c2dd; text-transform: uppercase;}
        .pulse-title {font-size: 22px; font-weight: 700; color: white; margin-top: 2px;}
        .pulse-badge {display:inline-block; padding: 4px 12px; border-radius: 4px;
            font-size: 11px; font-weight: 700; letter-spacing: .5px; color: white;}
        .pulse-subline {color:#4b5a75; font-size: 13px; margin: 10px 0 4px 0;}
        div[data-testid="stHorizontalBlock"] button {border-radius: 4px !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(user: dict, program_name: str, term: str):
    inject_css()
    role = user["role"]
    role_label = ROLE_LABELS.get(role, role.upper())
    badge_color = ROLE_BADGE_COLOR.get(role, "#1b2a4a")

    st.markdown(
        f"""
        <div class="pulse-header">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                    <div class="pulse-breadcrumb">Mapúa University · ASU Pathways · ETYSB</div>
                    <div class="pulse-title">Success Advisor Dashboard — {program_name}</div>
                </div>
                <div style="text-align:right;">
                    <span class="pulse-badge" style="background:{badge_color};">{role_label}</span>
                    <div style="font-size:12px; color:#c7d0e6; margin-top:6px;">
                        {user.get('FirstName','')} {user.get('LastName','')} &nbsp;|&nbsp; Term: {term}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_program_line(program_name: str):
    st.markdown(f"<div class='pulse-subline'>Program instance: <b>{program_name}</b></div>",
                unsafe_allow_html=True)


def render_nav(active: str, role: str):
    allowed = ROLE_PAGES.get(role, [])
    items = [item for item in NAV_ITEMS if item[0] in allowed]
    cols = st.columns(len(items) if items else 1)
    for col, (label, path) in zip(cols, items):
        with col:
            is_active = (label == active)
            if st.button(label, key=f"nav_{label}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                if not is_active:
                    st.switch_page(path)
    st.divider()


def page_shell(active: str, user: dict, program_name: str, term: str):
    """Call at the top of every page for a consistent look."""
    render_header(user, program_name, term)
    render_program_line(program_name)
    render_nav(active, user["role"])
