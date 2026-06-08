"""
Seed the database with demo data for testing.
Run once: python -m affiliate_app.sample_data
"""

from datetime import date, timedelta
import random
from database import init_db, get_connection

PROGRAMS = [
    ("Amazon Associates", "Amazon Associates", "RevShare %", 4.5, "Tecnología", "https://affiliate-program.amazon.com"),
    ("ClickBank - Fitness Pro", "ClickBank", "RevShare %", 50.0, "Salud & Fitness", "https://clickbank.com"),
    ("ShareASale - VPN", "ShareASale", "CPA (fijo por venta)", 35.0, "Tecnología", "https://shareasale.com"),
    ("CJ - Insurance Leads", "Commission Junction (CJ)", "CPL (por lead)", 22.0, "Seguros", "https://cj.com"),
    ("Impact - SaaS Tools", "Impact", "RevShare %", 30.0, "Tecnología", "https://impact.com"),
]

TEAM = [
    ("Carlos Mendoza", "Socio (Partner)", "Socio Equity", "carlos@example.com",
     "reparto_ingresos", 0, 0, 40.0, "2023-01-01",
     "Socio fundador — 40% del ingreso neto"),
    ("Ana García", "Socio (Partner)", "Socio Equity", "ana@example.com",
     "reparto_ingresos", 0, 0, 30.0, "2023-01-01",
     "Socia fundadora — 30% del ingreso neto"),
    ("Luis Torres", "Trabajador (Worker)", "1099 (Contratista)", "luis@example.com",
     "híbrido", 2000.0, 5.0, 0, "2023-03-15",
     "Creador de contenido — $2,000/mes + 5% comisión"),
    ("Sofia Reyes", "Trabajador (Worker)", "W-2 (Empleado)", "sofia@example.com",
     "salario_fijo", 4500.0, 0, 0, "2023-06-01",
     "Manager de SEO — $4,500/mes"),
    ("Mike Johnson", "Trabajador (Worker)", "1099 (Contratista)", "mike@example.com",
     "comisión", 0, 8.0, 0, "2024-01-10",
     "Media buyer — 8% sobre ingresos generados"),
]

EXPENSE_ITEMS = [
    ("Herramientas/Software", "Ahrefs SEO Tool", "Ahrefs"),
    ("Herramientas/Software", "Clickmagick tracking", "Clickmagick"),
    ("Hosting/Dominio", "Cloudflare + Namecheap", "Namecheap"),
    ("Publicidad", "Facebook Ads", "Meta"),
    ("Publicidad", "Google Ads", "Google"),
    ("Diseño/Contenido", "Freelancer diseñador", "Upwork"),
    ("Legal/Contabilidad", "CPA mensual", "Smith CPA LLC"),
]


def seed():
    init_db()
    conn = get_connection()

    # Clear existing data
    conn.executescript("""
        DELETE FROM payment_items;
        DELETE FROM payment_periods;
        DELETE FROM income_records;
        DELETE FROM expenses;
        DELETE FROM team_members;
        DELETE FROM affiliate_programs;
    """)

    # Insert programs
    prog_ids = []
    for name, network, ctype, crate, niche, url in PROGRAMS:
        cur = conn.execute(
            """INSERT INTO affiliate_programs (name, network, commission_type, commission_rate, niche, url, status)
               VALUES (?,?,?,?,?,?,'active')""",
            (name, network, ctype, crate, niche, url),
        )
        prog_ids.append(cur.lastrowid)

    # Insert team
    for name, role, emp, email, ptype, base, crate, rshare, start, notes in TEAM:
        conn.execute(
            """INSERT INTO team_members
               (name, role, employment_type, email, payment_type, base_amount,
                commission_rate, revenue_share_pct, start_date, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,'activo',?)""",
            (name, role, emp, email, ptype, base, crate, rshare, start, notes),
        )

    # Insert 12 months of income (2025)
    random.seed(42)
    today = date.today()
    for month in range(1, today.month + 1 if today.year == 2025 else 13):
        for _ in range(random.randint(8, 20)):
            prog_id = random.choice(prog_ids)
            sale = round(random.uniform(30, 400), 2)
            rate = random.uniform(0.04, 0.50)
            commission = round(sale * rate, 2)
            day = random.randint(1, 28)
            record_date = date(2025, month, day)
            conn.execute(
                """INSERT INTO income_records
                   (program_id, sale_amount, commission, record_date, description, payment_status)
                   VALUES (?,?,?,?,?,?)""",
                (prog_id, sale, commission, str(record_date),
                 "Venta orgánica", random.choice(["recibido", "recibido", "pendiente"])),
            )

    # Insert monthly expenses
    for month in range(1, today.month + 1 if today.year == 2025 else 13):
        for cat, desc, vendor in EXPENSE_ITEMS:
            amount = round(random.uniform(50, 800), 2)
            exp_date = date(2025, month, 5)
            conn.execute(
                """INSERT INTO expenses (category, amount, expense_date, description, vendor)
                   VALUES (?,?,?,?,?)""",
                (cat, amount, str(exp_date), desc, vendor),
            )

    conn.commit()
    conn.close()
    print("✅ Sample data loaded successfully.")


if __name__ == "__main__":
    seed()
