import db


def list_programs():
    with db.get_cursor() as cur:
        cur.execute("SELECT * FROM Program ORDER BY ProgramName")
        return [dict(r) for r in cur.fetchall()]


def get_active_program():
    """US-02: single source of truth for which program's data every view
    filters to. Nothing downstream should hardcode 'MBA' anywhere."""
    with db.get_cursor() as cur:
        cur.execute(
            """SELECT ap.Term, p.* FROM Active_Program ap
               JOIN Program p ON p.ProgramID = ap.ProgramID WHERE ap.ID = 1"""
        )
        row = cur.fetchone()
        return dict(row) if row else None


def set_active_program(program_id: int, term: str):
    with db.get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO Active_Program (ID, ProgramID, Term) VALUES (1, ?, ?) "
            "ON CONFLICT(ID) DO UPDATE SET ProgramID=excluded.ProgramID, Term=excluded.Term",
            (program_id, term),
        )


def create_program(code: str, name: str):
    with db.get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO Program (ProgramCode, ProgramName, IsActive, CreatedAt) VALUES (?,?,1,?)",
            (code, name, db.now_iso()),
        )
        return cur.lastrowid
