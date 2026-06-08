"""
Affiliate Business Manager
Gestión de ingresos, equipo y distribución de pagos para negocios de afiliados en EE.UU.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

from database import (
    init_db, get_programs, upsert_program, delete_program,
    get_income, add_income, delete_income, update_income_status,
    get_team, upsert_member, delete_member,
    get_expenses, add_expense, delete_expense,
    get_payment_periods, create_payment_period, get_payment_items,
    update_period_status,
)
from calculations import (
    calc_all_payments, compute_kpis, top_programs, income_by_month,
    estimate_federal_tax, estimate_se_tax, needs_1099,
    quarterly_estimated_tax, payment_with_currency,
)

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Affiliate Business Manager",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ── Helpers ────────────────────────────────────────────────────────────────────

COMMISSION_TYPES = ["RevShare %", "CPA (fijo por venta)", "CPC (por clic)", "CPL (por lead)"]
NICHES = ["Finanzas", "Salud & Fitness", "Tecnología", "Educación", "Viajes",
          "Hogar", "Moda & Belleza", "Gaming", "Seguros", "Otro"]
NETWORKS = ["Amazon Associates", "ClickBank", "ShareASale", "Commission Junction (CJ)",
            "Rakuten", "Impact", "Awin", "FlexOffers", "PartnerStack", "Otro"]
ROLES = ["Socio (Partner)", "Trabajador (Worker)"]
EMP_TYPES = ["1099 (Contratista)", "W-2 (Empleado)", "Socio Equity"]
PAYMENT_TYPES = ["salario_fijo", "comisión", "reparto_ingresos", "híbrido"]
PAYMENT_TYPE_LABELS = {
    "salario_fijo": "Salario Fijo",
    "comisión": "Comisión",
    "reparto_ingresos": "Reparto de Ingresos",
    "híbrido": "Híbrido (Salario + Comisión)",
}
EXPENSE_CATEGORIES = ["Herramientas/Software", "Publicidad", "Hosting/Dominio",
                      "Diseño/Contenido", "Comisiones/Fees", "Legal/Contabilidad",
                      "Educación/Cursos", "Otro"]
PERIOD_STATUSES = ["borrador", "aprobado", "pagado"]
INCOME_STATUSES = ["pendiente", "recibido"]


def fmt_usd(value: float) -> str:
    return f"${value:,.2f}"


def color_delta(val: float) -> str:
    return "normal" if val >= 0 else "inverse"


def _render_member_card(m):
    label = PAYMENT_TYPE_LABELS.get(m.get("payment_type", ""), m.get("payment_type", ""))
    with st.expander(f"{'🟢' if m['status']=='activo' else '🔴'} {m['name']} — {m['employment_type']}"):
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Rol:** {m['role']}")
        c1.write(f"**Email:** {m.get('email') or '—'}")
        c2.write(f"**Tipo empleo:** {m['employment_type']}")
        c2.write(f"**Estructura pago:** {label}")
        c2.write(f"**Moneda:** {m.get('currency', 'USD')}")
        if m["payment_type"] == "salario_fijo":
            c3.write(f"**Salario/período:** {fmt_usd(m['base_amount'])}")
        elif m["payment_type"] == "comisión":
            c3.write(f"**Tasa comisión:** {m['commission_rate']}%")
        elif m["payment_type"] == "reparto_ingresos":
            c3.write(f"**% Reparto:** {m['revenue_share_pct']}%")
        elif m["payment_type"] == "híbrido":
            c3.write(f"**Salario:** {fmt_usd(m['base_amount'])} + {m['commission_rate']}%")
        if m.get("notes"):
            st.caption(f"📝 {m['notes']}")
        if st.button("🗑️ Eliminar", key=f"del_mem_{m['id']}"):
            delete_member(int(m["id"]))
            st.rerun()


# ── Sidebar navigation ─────────────────────────────────────────────────────────

PAGES = {
    "📊 Dashboard": "dashboard",
    "🔗 Programas de Afiliados": "programs",
    "💰 Ingresos": "income",
    "💸 Gastos": "expenses",
    "👥 Equipo": "team",
    "💳 Distribución de Pagos": "payments",
    "📋 Reportes": "reports",
}

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/briefcase.png", width=64)
    st.title("Affiliate Business\nManager")
    st.caption("EE.UU. — Dashboard de gestión")
    st.markdown("---")
    selection = st.radio("Navegación", list(PAGES.keys()), label_visibility="collapsed")
    st.markdown("---")
    st.caption("💡 Tip: Los cálculos fiscales son estimados para planificación. Consulte un CPA.")

page = PAGES[selection]

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

if page == "dashboard":
    st.title("📊 Dashboard")
    today = date.today()
    year_start = date(today.year, 1, 1)

    income_df = get_income(year_start, today)
    expense_df = get_expenses(year_start, today)
    kpis = compute_kpis(income_df, expense_df)

    # ── KPI row ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Ingresos YTD", fmt_usd(kpis["total_income"]))
    c2.metric("💸 Gastos YTD", fmt_usd(kpis["total_expenses"]))
    c3.metric("📈 Ganancia Neta", fmt_usd(kpis["net_profit"]),
              delta=fmt_usd(kpis["net_profit"]),
              delta_color=color_delta(kpis["net_profit"]))
    c4.metric("🎯 Margen Neto", f"{kpis['margin_pct']:.1f}%")

    st.markdown("---")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        # Monthly income trend
        monthly = income_by_month(income_df)
        if not monthly.empty:
            fig = px.bar(monthly, x="mes", y="commission",
                         title="Comisiones por Mes (YTD)",
                         labels={"mes": "Mes", "commission": "Comisiones ($)"},
                         color_discrete_sequence=["#4CAF50"])
            fig.update_layout(showlegend=False, height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos de ingresos para el año actual.")

    with col_right:
        # Top programs donut
        top = top_programs(income_df)
        if not top.empty:
            fig2 = px.pie(top, names="program_name", values="commission",
                          title="Top Programas YTD",
                          hole=0.45,
                          color_discrete_sequence=px.colors.qualitative.Set3)
            fig2.update_layout(height=320, showlegend=True,
                               legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sin programas con ingresos.")

    # ── Recent income ─────────────────────────────────────────────────────────
    st.subheader("Últimos 10 Ingresos Registrados")
    recent = get_income()
    if not recent.empty:
        display = recent[["record_date", "program_name", "sale_amount",
                           "commission", "payment_status"]].head(10).copy()
        display.columns = ["Fecha", "Programa", "Venta ($)", "Comisión ($)", "Estado"]
        display["Venta ($)"] = display["Venta ($)"].map(lambda x: f"${x:,.2f}")
        display["Comisión ($)"] = display["Comisión ($)"].map(lambda x: f"${x:,.2f}")
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay ingresos registrados.")

    # ── Expense breakdown ─────────────────────────────────────────────────────
    if not expense_df.empty:
        st.subheader("Gastos por Categoría (YTD)")
        exp_cat = expense_df.groupby("category")["amount"].sum().reset_index()
        fig3 = px.bar(exp_cat, x="amount", y="category", orientation="h",
                      labels={"amount": "Monto ($)", "category": "Categoría"},
                      color_discrete_sequence=["#FF6B6B"])
        fig3.update_layout(height=280, showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PROGRAMAS DE AFILIADOS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "programs":
    st.title("🔗 Programas de Afiliados")
    tab_list, tab_add = st.tabs(["📋 Lista de Programas", "➕ Agregar / Editar"])

    with tab_list:
        df = get_programs()
        if df.empty:
            st.info("No hay programas registrados. Ve a la pestaña 'Agregar / Editar'.")
        else:
            for _, row in df.iterrows():
                with st.expander(f"{'🟢' if row['status']=='active' else '🔴'} {row['name']} — {row['network']}"):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Red:** {row['network']}")
                    c1.write(f"**Nicho:** {row['niche']}")
                    c2.write(f"**Tipo comisión:** {row['commission_type']}")
                    c2.write(f"**Tasa:** {row['commission_rate']}%")
                    c3.write(f"**Estado:** {row['status']}")
                    if row["url"]:
                        c3.markdown(f"[🔗 Ir al programa]({row['url']})")
                    if st.button("🗑️ Eliminar", key=f"del_prog_{row['id']}"):
                        delete_program(row["id"])
                        st.rerun()

    with tab_add:
        st.subheader("Nuevo Programa / Editar")
        programs_df = get_programs()
        edit_options = ["— Nuevo programa —"] + list(
            programs_df["name"].values if not programs_df.empty else []
        )
        selected_name = st.selectbox("Editar programa existente", edit_options)
        existing = {}
        if selected_name != "— Nuevo programa —" and not programs_df.empty:
            row = programs_df[programs_df["name"] == selected_name].iloc[0]
            existing = row.to_dict()

        with st.form("program_form"):
            name = st.text_input("Nombre del programa*", value=existing.get("name", ""))
            c1, c2 = st.columns(2)
            network = c1.selectbox("Red de afiliados", NETWORKS,
                                   index=NETWORKS.index(existing["network"])
                                   if existing.get("network") in NETWORKS else 0)
            niche = c2.selectbox("Nicho", NICHES,
                                 index=NICHES.index(existing["niche"])
                                 if existing.get("niche") in NICHES else 0)
            c3, c4 = st.columns(2)
            comm_type = c3.selectbox("Tipo de comisión", COMMISSION_TYPES,
                                     index=COMMISSION_TYPES.index(existing["commission_type"])
                                     if existing.get("commission_type") in COMMISSION_TYPES else 0)
            comm_rate = c4.number_input("Tasa de comisión (%)", min_value=0.0,
                                        max_value=100.0, step=0.1,
                                        value=float(existing.get("commission_rate", 0)))
            url = st.text_input("URL del programa", value=existing.get("url", ""))
            status = st.selectbox("Estado", ["active", "inactive"],
                                  index=0 if existing.get("status", "active") == "active" else 1)
            submitted = st.form_submit_button("💾 Guardar")
            if submitted:
                if not name:
                    st.error("El nombre es obligatorio.")
                else:
                    upsert_program({
                        "id": existing.get("id"),
                        "name": name, "network": network, "niche": niche,
                        "commission_type": comm_type, "commission_rate": comm_rate,
                        "url": url, "status": status,
                    })
                    st.success(f"✅ Programa '{name}' guardado.")
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# INGRESOS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "income":
    st.title("💰 Registro de Ingresos")
    tab_list, tab_add = st.tabs(["📋 Historial", "➕ Registrar Ingreso"])

    with tab_add:
        programs_df = get_programs(active_only=True)
        if programs_df.empty:
            st.warning("Primero agrega al menos un programa de afiliados.")
        else:
            with st.form("income_form"):
                st.subheader("Nuevo Ingreso")
                prog_options = dict(zip(programs_df["name"], programs_df["id"]))
                prog_name = st.selectbox("Programa de afiliado", list(prog_options.keys()))
                c1, c2 = st.columns(2)
                record_date = c1.date_input("Fecha", value=date.today())
                status = c2.selectbox("Estado de pago", INCOME_STATUSES,
                                      format_func=lambda x: "Pendiente" if x == "pendiente" else "Recibido")
                c3, c4 = st.columns(2)
                sale_amount = c3.number_input("Monto de venta ($)", min_value=0.0, step=0.01)
                commission = c4.number_input("Comisión ganada ($)*", min_value=0.0, step=0.01)
                description = st.text_input("Descripción / referencia", "")
                if submitted := st.form_submit_button("💾 Registrar"):
                    if commission <= 0:
                        st.error("La comisión debe ser mayor a $0.")
                    else:
                        add_income({
                            "program_id": prog_options[prog_name],
                            "sale_amount": sale_amount,
                            "commission": commission,
                            "record_date": record_date,
                            "description": description,
                            "payment_status": status,
                        })
                        st.success("✅ Ingreso registrado.")
                        st.rerun()

    with tab_list:
        c1, c2 = st.columns(2)
        start = c1.date_input("Desde", value=date(date.today().year, 1, 1),
                               key="inc_start")
        end = c2.date_input("Hasta", value=date.today(), key="inc_end")
        df = get_income(start, end)

        if df.empty:
            st.info("No hay ingresos en el rango seleccionado.")
        else:
            total = df["commission"].sum()
            st.metric("Total comisiones en el período", fmt_usd(total))
            st.markdown("---")

            display = df[["record_date", "program_name", "sale_amount",
                           "commission", "payment_status", "description", "id"]].copy()
            display.columns = ["Fecha", "Programa", "Venta ($)",
                                "Comisión ($)", "Estado", "Descripción", "ID"]
            display["Venta ($)"] = display["Venta ($)"].map(lambda x: f"${x:,.2f}")
            display["Comisión ($)"] = display["Comisión ($)"].map(lambda x: f"${x:,.2f}")

            st.dataframe(display.drop(columns=["ID"]), use_container_width=True,
                         hide_index=True)

            st.markdown("#### Acciones")
            col_a, col_b, col_c = st.columns(3)
            rec_ids = df["id"].tolist()
            rec_labels = [f"#{r['id']} — {r['program_name']} {fmt_usd(r['commission'])} ({r['record_date']})"
                          for _, r in df.iterrows()]

            sel_label = col_a.selectbox("Seleccionar registro", rec_labels, key="inc_sel")
            sel_idx = rec_labels.index(sel_label)
            sel_id = rec_ids[sel_idx]

            new_status = col_b.selectbox("Cambiar estado", INCOME_STATUSES,
                                         format_func=lambda x: "Pendiente" if x == "pendiente" else "Recibido",
                                         key="inc_status")
            if col_b.button("✅ Actualizar estado"):
                update_income_status(sel_id, new_status)
                st.rerun()

            if col_c.button("🗑️ Eliminar registro seleccionado"):
                delete_income(sel_id)
                st.success("Registro eliminado.")
                st.rerun()

            # Export
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Exportar CSV", csv, "ingresos.csv", "text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# GASTOS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "expenses":
    st.title("💸 Gastos")
    tab_list, tab_add = st.tabs(["📋 Historial", "➕ Registrar Gasto"])

    with tab_add:
        with st.form("expense_form"):
            st.subheader("Nuevo Gasto")
            c1, c2 = st.columns(2)
            category = c1.selectbox("Categoría", EXPENSE_CATEGORIES)
            exp_date = c2.date_input("Fecha", value=date.today())
            c3, c4 = st.columns(2)
            amount = c3.number_input("Monto ($)*", min_value=0.01, step=0.01, value=0.01)
            vendor = c4.text_input("Proveedor / Vendor")
            description = st.text_input("Descripción")
            if st.form_submit_button("💾 Guardar Gasto"):
                add_expense({
                    "category": category, "amount": amount,
                    "expense_date": exp_date, "description": description,
                    "vendor": vendor,
                })
                st.success("✅ Gasto registrado.")
                st.rerun()

    with tab_list:
        c1, c2 = st.columns(2)
        start = c1.date_input("Desde", value=date(date.today().year, 1, 1), key="exp_s")
        end = c2.date_input("Hasta", value=date.today(), key="exp_e")
        df = get_expenses(start, end)

        if df.empty:
            st.info("No hay gastos en el período seleccionado.")
        else:
            total = df["amount"].sum()
            st.metric("Total gastos en el período", fmt_usd(total))

            cat_totals = df.groupby("category")["amount"].sum().reset_index()
            fig = px.pie(cat_totals, names="category", values="amount",
                         title="Distribución de Gastos por Categoría", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

            display = df[["expense_date", "category", "amount", "vendor",
                           "description", "id"]].copy()
            display["amount"] = display["amount"].map(lambda x: f"${x:,.2f}")
            display.columns = ["Fecha", "Categoría", "Monto ($)", "Proveedor",
                                "Descripción", "ID"]
            st.dataframe(display.drop(columns=["ID"]), use_container_width=True,
                         hide_index=True)

            ids = df["id"].tolist()
            labels = [f"#{r['id']} — {r['category']} {fmt_usd(r['amount'])} ({r['expense_date']})"
                      for _, r in df.iterrows()]
            sel = st.selectbox("Seleccionar para eliminar", labels, key="exp_del")
            sel_id = ids[labels.index(sel)]
            if st.button("🗑️ Eliminar gasto seleccionado"):
                delete_expense(sel_id)
                st.rerun()

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Exportar CSV", csv, "gastos.csv", "text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# EQUIPO
# ══════════════════════════════════════════════════════════════════════════════

elif page == "team":
    st.title("👥 Equipo — Socios y Trabajadores")
    tab_list, tab_add = st.tabs(["📋 Miembros del Equipo", "➕ Agregar / Editar"])

    with tab_list:
        df = get_team()
        if df.empty:
            st.info("No hay miembros del equipo. Ve a 'Agregar / Editar'.")
        else:
            partners = df[df["role"].str.contains("Socio", na=False)]
            workers = df[~df["role"].str.contains("Socio", na=False)]

            if not partners.empty:
                st.subheader("🤝 Socios (Partners)")
                for _, m in partners.iterrows():
                    _render_member_card(m)

            if not workers.empty:
                st.subheader("🛠️ Trabajadores (Workers)")
                for _, m in workers.iterrows():
                    _render_member_card(m)

    with tab_add:
        df_team = get_team()
        edit_opts = ["— Nuevo miembro —"] + (list(df_team["name"].values) if not df_team.empty else [])
        sel_name = st.selectbox("Editar miembro existente", edit_opts)
        existing = {}
        if sel_name != "— Nuevo miembro —" and not df_team.empty:
            existing = df_team[df_team["name"] == sel_name].iloc[0].to_dict()

        with st.form("member_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre*", value=existing.get("name", ""))
            email = c2.text_input("Email", value=existing.get("email", ""))

            c3, c4 = st.columns(2)
            role = c3.selectbox("Rol", ROLES,
                                 index=0 if "Socio" in existing.get("role", "") else 1)
            emp_type = c4.selectbox("Tipo de empleo", EMP_TYPES,
                                     index=EMP_TYPES.index(existing["employment_type"])
                                     if existing.get("employment_type") in EMP_TYPES else 0)

            payment_type = st.selectbox(
                "Estructura de pago",
                PAYMENT_TYPES,
                format_func=lambda x: PAYMENT_TYPE_LABELS[x],
                index=PAYMENT_TYPES.index(existing["payment_type"])
                if existing.get("payment_type") in PAYMENT_TYPES else 0,
            )

            st.caption("Completa los campos aplicables a la estructura de pago seleccionada.")
            c5, c6, c7 = st.columns(3)
            base_amount = c5.number_input(
                "Salario fijo / período ($)",
                min_value=0.0, step=100.0,
                value=float(existing.get("base_amount", 0)),
                help="Para tipos: Salario Fijo e Híbrido",
            )
            commission_rate = c6.number_input(
                "Tasa de comisión (%)",
                min_value=0.0, max_value=100.0, step=0.1,
                value=float(existing.get("commission_rate", 0)),
                help="Para tipos: Comisión e Híbrido",
            )
            revenue_share_pct = c7.number_input(
                "% Reparto de ingresos netos",
                min_value=0.0, max_value=100.0, step=0.5,
                value=float(existing.get("revenue_share_pct", 0)),
                help="Para tipo: Reparto de Ingresos (socios)",
            )

            c8, c9, c10 = st.columns(3)
            start_date = c8.date_input("Fecha de inicio",
                                        value=date.fromisoformat(existing["start_date"])
                                        if existing.get("start_date") else date.today())
            status = c9.selectbox("Estado", ["activo", "inactivo"],
                                   index=0 if existing.get("status", "activo") == "activo" else 1)
            currency = c10.selectbox(
                "Moneda de pago",
                ["USD", "CLP"],
                index=0 if existing.get("currency", "USD") == "USD" else 1,
                help="USD: pago en dólares. CLP: pago en pesos chilenos (aplica PPM si es boleta).",
            )
            notes = st.text_area("Notas / acuerdo", value=existing.get("notes", ""), height=80)

            if st.form_submit_button("💾 Guardar"):
                if not name:
                    st.error("El nombre es obligatorio.")
                else:
                    upsert_member({
                        "id": existing.get("id"),
                        "name": name, "role": role, "employment_type": emp_type,
                        "email": email, "payment_type": payment_type,
                        "base_amount": base_amount, "commission_rate": commission_rate,
                        "revenue_share_pct": revenue_share_pct, "currency": currency,
                        "start_date": str(start_date), "status": status, "notes": notes,
                    })
                    st.success(f"✅ Miembro '{name}' guardado.")
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# DISTRIBUCIÓN DE PAGOS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "payments":
    st.title("💳 Distribución de Pagos")
    tab_calc, tab_history = st.tabs(["🧮 Calcular Distribución", "📜 Historial de Períodos"])

    with tab_calc:
        st.subheader("Nuevo Período de Pago")
        c1, c2 = st.columns(2)
        period_start = c1.date_input("Inicio del período",
                                      value=date.today().replace(day=1))
        period_end = c2.date_input("Fin del período", value=date.today())

        if period_start > period_end:
            st.error("La fecha de inicio debe ser anterior al fin del período.")
            st.stop()

        income_df = get_income(period_start, period_end)
        expense_df = get_expenses(period_start, period_end)
        total_income = float(income_df["commission"].sum()) if not income_df.empty else 0
        total_expenses = float(expense_df["amount"].sum()) if not expense_df.empty else 0
        net_income = total_income - total_expenses

        st.markdown("#### Resumen del Período")
        m1, m2, m3 = st.columns(3)
        m1.metric("Ingresos (comisiones)", fmt_usd(total_income))
        m2.metric("Gastos", fmt_usd(total_expenses))
        m3.metric("Ingreso Neto", fmt_usd(net_income),
                  delta=fmt_usd(net_income), delta_color=color_delta(net_income))

        team_df = get_team(active_only=True)
        if team_df.empty:
            st.warning("No hay miembros activos en el equipo. Agrega socios o trabajadores primero.")
        else:
            has_clp = "CLP" in team_df.get("currency", pd.Series(["USD"])).values
            usd_clp_rate = 1.0
            if has_clp:
                usd_clp_rate = st.number_input(
                    "Tipo de cambio USD → CLP para este período",
                    min_value=100.0, max_value=2000.0, step=1.0, value=950.0,
                    help="Ingresa el tipo de cambio vigente al cierre del período.",
                )

            st.markdown("#### Distribución Calculada")
            items = calc_all_payments(team_df, total_income, net_income)
            items_df = pd.DataFrame(items)
            items_df = items_df.merge(
                team_df[["id", "name", "role", "employment_type", "payment_type"]],
                left_on="member_id", right_on="id", how="left",
            )
            items_df["payment_type_label"] = items_df["payment_type"].map(PAYMENT_TYPE_LABELS)

            # Bonus overrides
            st.caption("Puedes ajustar bonos individuales antes de guardar:")
            bonuses = {}
            for _, row in items_df.iterrows():
                bonuses[row["member_id"]] = st.number_input(
                    f"Bono adicional para {row['name']} (USD)",
                    min_value=0.0, step=50.0, key=f"bonus_{row['member_id']}",
                )

            # Recalculate with bonuses and currency
            final_items = []
            member_map = {int(r["id"]): r.to_dict() for _, r in team_df.iterrows()}
            for item in items:
                b = bonuses.get(item["member_id"], 0)
                item["bonus_amount"] = b
                item["total_gross"] = item["base_amount"] + item["commission_amount"] + b
                member = member_map.get(item["member_id"], {})
                final_items.append(payment_with_currency(item, member, usd_clp_rate))

            final_df = pd.DataFrame(final_items)
            final_df = final_df.merge(
                team_df[["id", "name", "role", "employment_type", "currency"]],
                left_on="member_id", right_on="id", how="left",
            )

            # Build display table
            rows = []
            for _, r in final_df.iterrows():
                row = {
                    "Nombre": r["name"], "Rol": r["role"],
                    "Base (USD)": fmt_usd(r["base_amount"]),
                    "Comisión (USD)": fmt_usd(r["commission_amount"]),
                    "Bono (USD)": fmt_usd(r["bonus_amount"]),
                    "Total Bruto (USD)": fmt_usd(r["total_gross"]),
                    "Moneda": r["currency"],
                }
                if r["currency"] == "CLP" and r["gross_clp"] is not None:
                    row["Total Bruto (CLP)"] = f"${r['gross_clp']:,.0f}"
                    row["PPM 12.25% (CLP)"] = f"-${r['ppm_clp']:,.0f}"
                    row["Neto a Pagar (CLP)"] = f"${r['net_clp']:,.0f}"
                else:
                    row["Total Bruto (CLP)"] = "—"
                    row["PPM 12.25% (CLP)"] = "—"
                    row["Neto a Pagar (CLP)"] = "—"
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            total_payments = final_df["total_gross"].sum()
            st.metric("Total a Distribuir (USD)", fmt_usd(total_payments))

            # Chart
            if not final_df.empty:
                fig = px.bar(final_df, x="name", y="total_gross",
                             color="role",
                             title="Distribución por Miembro",
                             labels={"name": "Nombre", "total_gross": "Total ($)"})
                st.plotly_chart(fig, use_container_width=True)

            notes = st.text_area("Notas del período", "")
            if st.button("💾 Guardar Distribución como Borrador"):
                create_payment_period(
                    {
                        "period_start": period_start, "period_end": period_end,
                        "total_income": total_income, "total_expenses": total_expenses,
                        "net_income": net_income, "status": "borrador", "notes": notes,
                    },
                    final_items,
                )
                st.success("✅ Distribución guardada.")
                st.rerun()

    with tab_history:
        periods = get_payment_periods()
        if periods.empty:
            st.info("No hay períodos de pago registrados.")
        else:
            for _, p in periods.iterrows():
                status_icon = {"borrador": "📝", "aprobado": "✅", "pagado": "💳"}.get(
                    p["status"], "❓"
                )
                with st.expander(
                    f"{status_icon} {p['period_start']} → {p['period_end']} | "
                    f"Neto: {fmt_usd(p['net_income'])} | Estado: {p['status'].upper()}"
                ):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Ingresos", fmt_usd(p["total_income"]))
                    c2.metric("Gastos", fmt_usd(p["total_expenses"]))
                    c3.metric("Neto", fmt_usd(p["net_income"]))

                    items_df = get_payment_items(int(p["id"]))
                    if not items_df.empty:
                        disp = items_df[["name", "role", "employment_type",
                                         "base_amount", "commission_amount",
                                         "bonus_amount", "total_gross"]].copy()
                        disp.columns = ["Nombre", "Rol", "Tipo Empleo",
                                        "Base ($)", "Comisión ($)", "Bono ($)", "Total ($)"]
                        for col in ["Base ($)", "Comisión ($)", "Bono ($)", "Total ($)"]:
                            disp[col] = disp[col].map(lambda x: f"${x:,.2f}")
                        st.dataframe(disp, use_container_width=True, hide_index=True)

                    new_s = st.selectbox("Cambiar estado", PERIOD_STATUSES,
                                         index=PERIOD_STATUSES.index(p["status"]),
                                         key=f"pstatus_{p['id']}")
                    if st.button("Actualizar estado", key=f"pupd_{p['id']}"):
                        update_period_status(int(p["id"]), new_s)
                        st.rerun()

                    if not items_df.empty:
                        csv = items_df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "⬇️ Exportar detalle CSV",
                            csv,
                            f"pago_{p['period_start']}_{p['period_end']}.csv",
                            "text/csv",
                            key=f"dl_period_{p['id']}",
                        )


# ══════════════════════════════════════════════════════════════════════════════
# REPORTES
# ══════════════════════════════════════════════════════════════════════════════

elif page == "reports":
    st.title("📋 Reportes")
    tab_pl, tab_prog, tab_tax = st.tabs([
        "📊 P&L Mensual", "🏆 Performance de Programas", "🇺🇸 Impuestos EE.UU."
    ])

    with tab_pl:
        st.subheader("Estado de Resultados (P&L)")
        year = st.selectbox("Año", list(range(date.today().year, 2022, -1)))
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)

        income_df = get_income(year_start, year_end)
        expense_df = get_expenses(year_start, year_end)

        monthly_inc = income_by_month(income_df)
        if not expense_df.empty:
            expense_df["mes"] = pd.to_datetime(expense_df["expense_date"]).dt.to_period("M").astype(str)
            monthly_exp = expense_df.groupby("mes")["amount"].sum().reset_index()
            monthly_exp.columns = ["mes", "gastos"]
        else:
            monthly_exp = pd.DataFrame(columns=["mes", "gastos"])

        if not monthly_inc.empty or not monthly_exp.empty:
            pl = pd.merge(monthly_inc.rename(columns={"commission": "ingresos"}),
                          monthly_exp, on="mes", how="outer").fillna(0)
            pl = pl.sort_values("mes")
            pl["ganancia_neta"] = pl["ingresos"] - pl["gastos"]

            fig = go.Figure()
            fig.add_trace(go.Bar(name="Ingresos", x=pl["mes"], y=pl["ingresos"],
                                  marker_color="#4CAF50"))
            fig.add_trace(go.Bar(name="Gastos", x=pl["mes"], y=pl["gastos"],
                                  marker_color="#FF6B6B"))
            fig.add_trace(go.Scatter(name="Ganancia Neta", x=pl["mes"],
                                      y=pl["ganancia_neta"], mode="lines+markers",
                                      line=dict(color="#2196F3", width=2)))
            fig.update_layout(barmode="group", title=f"P&L Mensual {year}",
                               height=380, xaxis_title="Mes", yaxis_title="USD ($)")
            st.plotly_chart(fig, use_container_width=True)

            # Summary table
            pl["ingresos_fmt"] = pl["ingresos"].map(fmt_usd)
            pl["gastos_fmt"] = pl["gastos"].map(fmt_usd)
            pl["ganancia_neta_fmt"] = pl["ganancia_neta"].map(fmt_usd)
            st.dataframe(
                pl[["mes", "ingresos_fmt", "gastos_fmt", "ganancia_neta_fmt"]]
                .rename(columns={"mes": "Mes", "ingresos_fmt": "Ingresos",
                                  "gastos_fmt": "Gastos", "ganancia_neta_fmt": "Ganancia Neta"}),
                use_container_width=True, hide_index=True,
            )
            csv = pl.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Exportar P&L CSV", csv, f"pl_{year}.csv", "text/csv")
        else:
            st.info(f"No hay datos para el año {year}.")

    with tab_prog:
        st.subheader("Performance por Programa de Afiliado")
        c1, c2 = st.columns(2)
        start = c1.date_input("Desde", value=date(date.today().year, 1, 1), key="rp_s")
        end = c2.date_input("Hasta", value=date.today(), key="rp_e")

        income_df = get_income(start, end)
        if income_df.empty:
            st.info("No hay datos en el período seleccionado.")
        else:
            prog_stats = (
                income_df.groupby("program_name")
                .agg(
                    total_ventas=("sale_amount", "sum"),
                    total_comisiones=("commission", "sum"),
                    num_ventas=("id", "count"),
                )
                .reset_index()
                .sort_values("total_comisiones", ascending=False)
            )
            prog_stats["tasa_efectiva"] = (
                prog_stats["total_comisiones"] / prog_stats["total_ventas"].replace(0, 1) * 100
            ).round(2)

            fig = px.bar(prog_stats, x="program_name", y="total_comisiones",
                         color="program_name",
                         title="Comisiones Totales por Programa",
                         labels={"program_name": "Programa", "total_comisiones": "Comisiones ($)"})
            fig.update_layout(showlegend=False, height=320)
            st.plotly_chart(fig, use_container_width=True)

            prog_stats["total_ventas"] = prog_stats["total_ventas"].map(fmt_usd)
            prog_stats["total_comisiones"] = prog_stats["total_comisiones"].map(fmt_usd)
            prog_stats["tasa_efectiva"] = prog_stats["tasa_efectiva"].map(lambda x: f"{x:.2f}%")
            prog_stats.columns = ["Programa", "Total Ventas", "Total Comisiones",
                                   "# Ventas", "Tasa Efectiva"]
            st.dataframe(prog_stats, use_container_width=True, hide_index=True)

    with tab_tax:
        st.subheader("🇺🇸 Guía de Impuestos — Negocio de Afiliados en EE.UU.")

        st.info(
            "**Aviso:** Estos son estimados para planificación. Consulta a un CPA o "
            "contador certificado para tu situación fiscal específica."
        )

        team_df = get_team(active_only=True)
        year = st.selectbox("Año fiscal", list(range(date.today().year, 2022, -1)),
                             key="tax_year")
        income_df = get_income(date(year, 1, 1), date(year, 12, 31))

        # Annual payments per member
        periods_df = get_payment_periods()
        annual_payments: dict[str, float] = {}
        if not periods_df.empty:
            year_periods = periods_df[
                periods_df["period_start"].str.startswith(str(year))
            ]
            for _, p in year_periods.iterrows():
                items = get_payment_items(int(p["id"]))
                for _, item in items.iterrows():
                    name = item["name"]
                    annual_payments[name] = annual_payments.get(name, 0) + float(item["total_gross"])

        st.markdown("---")
        st.markdown("#### 1099-NEC — Contratistas (umbral: $600/año)")
        if team_df.empty:
            st.info("No hay miembros del equipo registrados.")
        else:
            contractors = team_df[team_df["employment_type"] == "1099 (Contratista)"]
            if contractors.empty:
                st.info("No hay contratistas 1099 en el equipo.")
            else:
                rows = []
                for _, m in contractors.iterrows():
                    total_paid = annual_payments.get(m["name"], 0)
                    rows.append({
                        "Nombre": m["name"],
                        "Total Pagado": fmt_usd(total_paid),
                        "Requiere 1099-NEC": "✅ Sí" if needs_1099(total_paid) else "❌ No (< $600)",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Estimado de Impuestos Trimestrales (Pagos IRS)")
        annual_income = float(income_df["commission"].sum()) if not income_df.empty else 0
        annual_expenses = float(get_expenses(date(year, 1, 1), date(year, 12, 31))["amount"].sum()
                                 if not get_expenses(date(year, 1, 1), date(year, 12, 31)).empty else 0)
        net_business = annual_income - annual_expenses

        st.write(f"**Ingresos netos del negocio ({year}):** {fmt_usd(net_business)}")

        if net_business > 0:
            fed_tax = estimate_federal_tax(net_business)
            se_tax = estimate_se_tax(net_business)
            quarterly = quarterly_estimated_tax(net_business, "1099")

            c1, c2, c3 = st.columns(3)
            c1.metric("Impuesto Federal Estimado", fmt_usd(fed_tax))
            c2.metric("SE Tax (15.3%)", fmt_usd(se_tax))
            c3.metric("Pago Trimestral Estimado", fmt_usd(quarterly))

            st.markdown("""
            **Fechas de pago estimado de impuestos (IRS):**
            | Período | Fecha Límite |
            |---------|-------------|
            | Ene – Mar | 15 de Abril |
            | Abr – May | 15 de Junio |
            | Jun – Ago | 15 de Septiembre |
            | Sep – Dic | 15 de Enero (año siguiente) |
            """)

            st.markdown("""
            **Deducciones comunes para afiliados (Schedule C):**
            - Hosting, dominio, herramientas de software
            - Gastos de publicidad y marketing
            - Home office (Form 8829)
            - Educación y cursos relacionados al negocio
            - Equipo de cómputo (depreciación Section 179)
            - Fees de plataformas de afiliados
            """)
        else:
            st.info("Registra ingresos y gastos para ver el estimado de impuestos.")
