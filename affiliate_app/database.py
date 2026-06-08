import sqlite3
import pandas as pd
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent / "affiliate_business.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS affiliate_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            network TEXT,
            commission_type TEXT,
            commission_rate REAL DEFAULT 0,
            niche TEXT,
            url TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS income_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER,
            sale_amount REAL DEFAULT 0,
            commission REAL NOT NULL,
            record_date DATE NOT NULL,
            description TEXT,
            payment_status TEXT DEFAULT 'pendiente',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (program_id) REFERENCES affiliate_programs(id)
        );

        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            employment_type TEXT,
            email TEXT,
            payment_type TEXT,
            base_amount REAL DEFAULT 0,
            commission_rate REAL DEFAULT 0,
            revenue_share_pct REAL DEFAULT 0,
            start_date DATE,
            status TEXT DEFAULT 'activo',
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            amount REAL NOT NULL,
            expense_date DATE NOT NULL,
            description TEXT,
            vendor TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payment_periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            total_income REAL DEFAULT 0,
            total_expenses REAL DEFAULT 0,
            net_income REAL DEFAULT 0,
            status TEXT DEFAULT 'borrador',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payment_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            base_amount REAL DEFAULT 0,
            commission_amount REAL DEFAULT 0,
            bonus_amount REAL DEFAULT 0,
            total_gross REAL DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (period_id) REFERENCES payment_periods(id),
            FOREIGN KEY (member_id) REFERENCES team_members(id)
        );
    """)
    conn.commit()
    conn.close()


# ── Affiliate Programs ──────────────────────────────────────────────────────

def get_programs(active_only=False):
    conn = get_connection()
    q = "SELECT * FROM affiliate_programs"
    if active_only:
        q += " WHERE status='active'"
    q += " ORDER BY name"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


def upsert_program(data: dict):
    conn = get_connection()
    if data.get("id"):
        conn.execute(
            """UPDATE affiliate_programs
               SET name=?, network=?, commission_type=?, commission_rate=?,
                   niche=?, url=?, status=?
               WHERE id=?""",
            (data["name"], data["network"], data["commission_type"],
             data["commission_rate"], data["niche"], data["url"],
             data["status"], data["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO affiliate_programs
               (name, network, commission_type, commission_rate, niche, url, status)
               VALUES (?,?,?,?,?,?,?)""",
            (data["name"], data["network"], data["commission_type"],
             data["commission_rate"], data["niche"], data["url"],
             data.get("status", "active")),
        )
    conn.commit()
    conn.close()


def delete_program(program_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM affiliate_programs WHERE id=?", (program_id,))
    conn.commit()
    conn.close()


# ── Income Records ───────────────────────────────────────────────────────────

def get_income(start=None, end=None):
    conn = get_connection()
    q = """
        SELECT ir.*, ap.name AS program_name
        FROM income_records ir
        LEFT JOIN affiliate_programs ap ON ir.program_id = ap.id
    """
    params = []
    if start and end:
        q += " WHERE ir.record_date BETWEEN ? AND ?"
        params = [str(start), str(end)]
    q += " ORDER BY ir.record_date DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def add_income(data: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO income_records
           (program_id, sale_amount, commission, record_date, description, payment_status)
           VALUES (?,?,?,?,?,?)""",
        (data["program_id"], data["sale_amount"], data["commission"],
         str(data["record_date"]), data["description"],
         data.get("payment_status", "pendiente")),
    )
    conn.commit()
    conn.close()


def delete_income(record_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM income_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()


def update_income_status(record_id: int, status: str):
    conn = get_connection()
    conn.execute("UPDATE income_records SET payment_status=? WHERE id=?",
                 (status, record_id))
    conn.commit()
    conn.close()


# ── Team Members ─────────────────────────────────────────────────────────────

def get_team(active_only=False):
    conn = get_connection()
    q = "SELECT * FROM team_members"
    if active_only:
        q += " WHERE status='activo'"
    q += " ORDER BY role, name"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


def upsert_member(data: dict):
    conn = get_connection()
    if data.get("id"):
        conn.execute(
            """UPDATE team_members
               SET name=?, role=?, employment_type=?, email=?,
                   payment_type=?, base_amount=?, commission_rate=?,
                   revenue_share_pct=?, start_date=?, status=?, notes=?
               WHERE id=?""",
            (data["name"], data["role"], data["employment_type"], data["email"],
             data["payment_type"], data["base_amount"], data["commission_rate"],
             data["revenue_share_pct"], data.get("start_date"), data["status"],
             data.get("notes", ""), data["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO team_members
               (name, role, employment_type, email, payment_type, base_amount,
                commission_rate, revenue_share_pct, start_date, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["role"], data["employment_type"], data["email"],
             data["payment_type"], data["base_amount"], data["commission_rate"],
             data["revenue_share_pct"], data.get("start_date"),
             data.get("status", "activo"), data.get("notes", "")),
        )
    conn.commit()
    conn.close()


def delete_member(member_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM team_members WHERE id=?", (member_id,))
    conn.commit()
    conn.close()


# ── Expenses ─────────────────────────────────────────────────────────────────

def get_expenses(start=None, end=None):
    conn = get_connection()
    q = "SELECT * FROM expenses"
    params = []
    if start and end:
        q += " WHERE expense_date BETWEEN ? AND ?"
        params = [str(start), str(end)]
    q += " ORDER BY expense_date DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def add_expense(data: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO expenses (category, amount, expense_date, description, vendor)
           VALUES (?,?,?,?,?)""",
        (data["category"], data["amount"], str(data["expense_date"]),
         data["description"], data["vendor"]),
    )
    conn.commit()
    conn.close()


def delete_expense(expense_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()


# ── Payment Periods ───────────────────────────────────────────────────────────

def get_payment_periods():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM payment_periods ORDER BY period_start DESC", conn
    )
    conn.close()
    return df


def create_payment_period(data: dict, items: list):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO payment_periods
           (period_start, period_end, total_income, total_expenses, net_income, status, notes)
           VALUES (?,?,?,?,?,?,?)""",
        (str(data["period_start"]), str(data["period_end"]),
         data["total_income"], data["total_expenses"], data["net_income"],
         data.get("status", "borrador"), data.get("notes", "")),
    )
    period_id = cur.lastrowid
    for item in items:
        conn.execute(
            """INSERT INTO payment_items
               (period_id, member_id, base_amount, commission_amount,
                bonus_amount, total_gross, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (period_id, item["member_id"], item["base_amount"],
             item["commission_amount"], item.get("bonus_amount", 0),
             item["total_gross"], item.get("notes", "")),
        )
    conn.commit()
    conn.close()
    return period_id


def get_payment_items(period_id: int):
    conn = get_connection()
    df = pd.read_sql_query(
        """SELECT pi.*, tm.name, tm.role, tm.employment_type, tm.payment_type
           FROM payment_items pi
           JOIN team_members tm ON pi.member_id = tm.id
           WHERE pi.period_id = ?""",
        conn, params=(period_id,),
    )
    conn.close()
    return df


def update_period_status(period_id: int, status: str):
    conn = get_connection()
    conn.execute("UPDATE payment_periods SET status=? WHERE id=?",
                 (status, period_id))
    conn.commit()
    conn.close()
