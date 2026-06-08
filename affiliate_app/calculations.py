"""Business logic: payment calculations, tax estimates, and KPI helpers."""

from __future__ import annotations
import pandas as pd


# ── Payment calculation ───────────────────────────────────────────────────────

def calc_member_payment(member: dict, gross_income: float, net_income: float,
                        bonus: float = 0) -> dict:
    """Return base, commission, bonus, and total_gross for one team member."""
    base = 0.0
    commission = 0.0

    ptype = member.get("payment_type", "")

    if ptype == "salario_fijo":
        base = float(member.get("base_amount", 0))

    elif ptype == "comisión":
        commission = gross_income * (float(member.get("commission_rate", 0)) / 100)

    elif ptype == "reparto_ingresos":
        # Partners: share of net income
        base = net_income * (float(member.get("revenue_share_pct", 0)) / 100)

    elif ptype == "híbrido":
        base = float(member.get("base_amount", 0))
        commission = gross_income * (float(member.get("commission_rate", 0)) / 100)

    total_gross = base + commission + bonus
    return {
        "member_id": member["id"],
        "base_amount": base,
        "commission_amount": commission,
        "bonus_amount": bonus,
        "total_gross": total_gross,
    }


def calc_all_payments(team_df: pd.DataFrame, gross_income: float,
                      net_income: float) -> list[dict]:
    items = []
    for _, m in team_df.iterrows():
        items.append(calc_member_payment(m.to_dict(), gross_income, net_income))
    return items


# ── CLP conversion & Chilean PPM ─────────────────────────────────────────────

PPM_RATE = 0.1225  # Retención boleta de honorarios Chile 2024


def to_clp(usd_amount: float, usd_clp_rate: float) -> float:
    return round(usd_amount * usd_clp_rate, 0)


def calc_ppm(gross_clp: float) -> float:
    """Retención PPM (12.25%) para boleta de honorarios en Chile."""
    return round(gross_clp * PPM_RATE, 0)


def payment_with_currency(item: dict, member: dict, usd_clp_rate: float) -> dict:
    """
    Augments a payment item with CLP amounts and PPM if the member uses CLP.
    employment_type 'Boleta (Chile)' triggers PPM retention.
    """
    currency = member.get("currency", "USD")
    emp_type = member.get("employment_type", "")
    gross_usd = item["total_gross"]

    result = {**item, "currency": currency, "usd_clp_rate": usd_clp_rate}

    if currency == "CLP":
        gross_clp = to_clp(gross_usd, usd_clp_rate)
        ppm = calc_ppm(gross_clp) if "Boleta" in emp_type or "1099" in emp_type else 0
        result["gross_clp"] = gross_clp
        result["ppm_clp"] = ppm
        result["net_clp"] = gross_clp - ppm
    else:
        result["gross_clp"] = None
        result["ppm_clp"] = None
        result["net_clp"] = None

    return result


# ── US Tax estimates ──────────────────────────────────────────────────────────

# 2024 federal brackets (single filer) – approximate for planning purposes
_FED_BRACKETS = [
    (11600, 0.10),
    (47150, 0.12),
    (100525, 0.22),
    (191950, 0.24),
    (243725, 0.32),
    (609350, 0.35),
    (float("inf"), 0.37),
]

# SE tax: 15.3% up to SS wage base, 2.9% above
_SS_WAGE_BASE = 168600


def estimate_federal_tax(income: float) -> float:
    tax = 0.0
    prev = 0.0
    for ceiling, rate in _FED_BRACKETS:
        if income <= prev:
            break
        taxable = min(income, ceiling) - prev
        tax += taxable * rate
        prev = ceiling
    return round(tax, 2)


def estimate_se_tax(net_se_income: float) -> float:
    """Self-employment tax for 1099 contractors (deduct 50% of SE tax first)."""
    deductible = net_se_income * 0.9235  # net SE earnings
    if deductible <= _SS_WAGE_BASE:
        return round(deductible * 0.153, 2)
    return round(_SS_WAGE_BASE * 0.153 + (deductible - _SS_WAGE_BASE) * 0.029, 2)


def needs_1099(annual_total: float) -> bool:
    """1099-NEC required when payments to a contractor exceed $600/year."""
    return annual_total >= 600


def quarterly_estimated_tax(annual_income: float, employment_type: str) -> float:
    """Rough quarterly estimated tax payment."""
    fed = estimate_federal_tax(annual_income)
    se = estimate_se_tax(annual_income) if employment_type == "1099" else 0
    return round((fed + se) / 4, 2)


# ── KPI helpers ───────────────────────────────────────────────────────────────

def compute_kpis(income_df: pd.DataFrame, expense_df: pd.DataFrame) -> dict:
    total_income = float(income_df["commission"].sum()) if not income_df.empty else 0
    total_sales = float(income_df["sale_amount"].sum()) if not income_df.empty else 0
    total_expenses = float(expense_df["amount"].sum()) if not expense_df.empty else 0
    net_profit = total_income - total_expenses
    margin = (net_profit / total_income * 100) if total_income > 0 else 0
    avg_commission = (total_income / total_sales * 100) if total_sales > 0 else 0
    return {
        "total_income": total_income,
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "margin_pct": margin,
        "avg_commission_rate": avg_commission,
    }


def top_programs(income_df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    if income_df.empty:
        return pd.DataFrame(columns=["program_name", "commission"])
    return (
        income_df.groupby("program_name")["commission"]
        .sum()
        .reset_index()
        .sort_values("commission", ascending=False)
        .head(n)
    )


def income_by_month(income_df: pd.DataFrame) -> pd.DataFrame:
    if income_df.empty:
        return pd.DataFrame(columns=["mes", "commission"])
    df = income_df.copy()
    df["mes"] = pd.to_datetime(df["record_date"]).dt.to_period("M").astype(str)
    return df.groupby("mes")["commission"].sum().reset_index().sort_values("mes")
