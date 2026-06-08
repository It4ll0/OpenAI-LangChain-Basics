"""
🚗 Estadísticas de Precios de Autos en Chile
Streamlit app — optimizada para mobile y desktop
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime

import scraper

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🚗 Autos Chile",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Estadísticas de precios de autos en Chile · MercadoLibre Chile API"},
)

COLORS    = px.colors.qualitative.Bold
TEMPLATE  = "plotly_white"

# ─── CSS mobile-friendly ─────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Reducir padding en mobile */
    .block-container { padding: 1rem 1rem 2rem; max-width: 1200px; }
    /* Tabs más compactos */
    .stTabs [data-baseweb="tab"] { font-size: 13px; padding: 6px 12px; }
    /* KPI cards */
    .kpi-card {
        background: #f0f4ff;
        border-radius: 10px;
        padding: 14px 10px;
        text-align: center;
        margin-bottom: 8px;
        border-left: 4px solid #3b82f6;
    }
    .kpi-val  { font-size: 22px; font-weight: 700; color: #1e3a8a; }
    .kpi-lbl  { font-size: 12px; color: #6b7280; margin-top: 2px; }
    /* Ocultar footer */
    footer { visibility: hidden; }
    /* Fuente más legible */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar — Filtros ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración")

    marcas_sel = st.multiselect(
        "Marcas a analizar",
        options=scraper.MARCAS_DEFAULT,
        default=scraper.MARCAS_DEFAULT,
        help="Selecciona las marcas que quieres comparar",
    )

    max_por_marca = st.slider(
        "Avisos por marca",
        min_value=20, max_value=200, value=100, step=20,
        help="Más avisos = más precisión pero más tiempo de carga",
    )

    st.divider()
    actualizar = st.button("🔄 Actualizar datos", use_container_width=True, type="primary")

    st.caption(
        f"Fuente: MercadoLibre Chile (API pública)\n\n"
        f"Los datos se cargan en tiempo real al presionar el botón."
    )


# ─── Data loading con caché ───────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)   # cache 30 min
def load_data(marcas: tuple, max_per_brand: int) -> pd.DataFrame:
    return scraper.fetch_all(list(marcas), max_per_brand)


# ─── Header ──────────────────────────────────────────────────────────────────
st.title("🚗 Mercado de Autos en Chile")
st.caption("Estadísticas avanzadas en tiempo real · MercadoLibre Chile")

# Trigger de carga
if "df" not in st.session_state or actualizar:
    if not marcas_sel:
        st.warning("Selecciona al menos una marca en el panel lateral.")
        st.stop()

    prog_bar  = st.progress(0, text="Iniciando descarga…")
    prog_text = st.empty()

    def on_progress(marca, current, total):
        pct = int(current / total * 100) if total else 100
        prog_bar.progress(pct, text=f"Descargando {marca}…" if marca else "Procesando…")
        prog_text.caption(f"{current}/{total} marcas")

    with st.spinner("Obteniendo datos de MercadoLibre Chile…"):
        df = load_data(tuple(marcas_sel), max_por_marca)

    prog_bar.empty()
    prog_text.empty()
    st.session_state["df"]       = df
    st.session_state["ts"]       = datetime.now().strftime("%d/%m/%Y %H:%M")
    st.session_state["usd_clp"]  = scraper.get_usd_clp()

df      = st.session_state["df"]
ts      = st.session_state["ts"]
usd_clp = st.session_state["usd_clp"]

if df.empty:
    st.error("No se obtuvieron datos. Intenta de nuevo.")
    st.stop()

# ─── Filtros inline ───────────────────────────────────────────────────────────
with st.expander("🔍 Filtrar resultados", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        cond_sel = st.multiselect(
            "Condición", ["Nuevo", "Usado", "No especificado"],
            default=["Nuevo", "Usado", "No especificado"],
        )
    with col2:
        precio_rng = st.slider(
            "Precio (millones CLP)",
            float(df["precio_m"].min()),
            min(float(df["precio_m"].max()), 300.0),
            (float(df["precio_m"].min()), min(float(df["precio_m"].max()), 300.0)),
        )
    with col3:
        anio_vals = df["anio_num"].dropna()
        if len(anio_vals):
            anio_rng = st.slider(
                "Año",
                int(anio_vals.min()), int(anio_vals.max()),
                (int(anio_vals.min()), int(anio_vals.max())),
            )
        else:
            anio_rng = (1990, datetime.now().year)

mask = (
    df["condicion_es"].isin(cond_sel) &
    df["precio_m"].between(*precio_rng) &
    (df["anio_num"].isna() | df["anio_num"].between(*anio_rng))
)
dff = df[mask].copy()

st.caption(
    f"📋 {len(dff):,} avisos · {dff['marca'].nunique()} marcas · "
    f"Actualizado: {ts} · USD/CLP: {usd_clp:,.0f}"
)

# ─── KPI cards ───────────────────────────────────────────────────────────────
nuevos  = (dff["condicion_es"] == "Nuevo").sum()
usados  = (dff["condicion_es"] == "Usado").sum()
med_p   = dff["precio_m"].median()
prom_p  = dff["precio_m"].mean()
med_km  = dff["km"].median()
n_mod   = dff["modelo"].nunique()

kpis = [
    (f"{len(dff):,}",          "Total avisos",       "#3b82f6"),
    (f"{nuevos:,}",            "Nuevos",             "#10b981"),
    (f"{usados:,}",            "Usados",             "#f59e0b"),
    (f"${med_p:.1f}M",         "Precio mediano",     "#8b5cf6"),
    (f"${prom_p:.1f}M",        "Precio promedio",    "#ec4899"),
    (f"{n_mod}",               "Modelos únicos",     "#06b6d4"),
]
if not np.isnan(med_km):
    kpis.append((f"{med_km/1000:.0f}k km", "Km medianos (usado)", "#64748b"))

cols = st.columns(len(kpis))
for col, (val, label, color) in zip(cols, kpis):
    col.markdown(
        f"<div class='kpi-card' style='border-left-color:{color}'>"
        f"<div class='kpi-val' style='color:{color}'>{val}</div>"
        f"<div class='kpi-lbl'>{label}</div></div>",
        unsafe_allow_html=True,
    )

st.divider()

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Por Marca", "📉 Depreciación", "🛣️ Kilometraje", "⛽ Otros", "🏆 Modelos"
])

# ── TAB 1: Por marca ──────────────────────────────────────────────────────────
with tab1:
    top_marcas = dff["marca"].value_counts().head(12).index.tolist()
    df_tm      = dff[dff["marca"].isin(top_marcas)]

    c1, c2 = st.columns([3, 2])

    with c1:
        orden = df_tm.groupby("marca")["precio_m"].median().sort_values().index.tolist()
        fig = px.box(
            df_tm, x="marca", y="precio_m",
            category_orders={"marca": orden},
            color="marca", color_discrete_sequence=COLORS,
            points="outliers",
            labels={"marca": "", "precio_m": "Precio (M CLP)"},
            title="Distribución de precios por marca",
            template=TEMPLATE, height=380,
        )
        fig.update_layout(showlegend=False, margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        brand_stats = df_tm.groupby("marca").agg(
            Mediana=("precio_m", "median"),
            Promedio=("precio_m", "mean"),
            Mín=("precio_m", "min"),
            Máx=("precio_m", "max"),
            Avisos=("id", "count"),
        ).round(1).sort_values("Mediana")
        st.dataframe(
            brand_stats.style.background_gradient(subset=["Mediana"], cmap="Blues"),
            use_container_width=True, height=380,
        )

    # Percentiles
    percentiles = [10, 25, 50, 75, 90]
    perc = (
        df_tm.groupby("marca")["precio_m"]
        .quantile([p/100 for p in percentiles])
        .unstack()
        .round(1)
        .sort_values(0.5)
    )
    perc.columns = [f"P{p}" for p in percentiles]
    color_map = {"P10": "#bfdbfe", "P25": "#60a5fa", "P50": "#1d4ed8",
                 "P75": "#f97316", "P90": "#dc2626"}
    fig2 = go.Figure()
    for p_col in perc.columns:
        fig2.add_trace(go.Bar(
            name=p_col, x=perc.index, y=perc[p_col],
            marker_color=color_map[p_col],
        ))
    fig2.update_layout(
        barmode="group", title="Percentiles de precio por marca",
        yaxis_title="M CLP", xaxis_title="",
        template=TEMPLATE, height=340, legend_title="Percentil",
        margin=dict(t=40, b=10),
    )
    st.plotly_chart(fig2, use_container_width=True)


# ── TAB 2: Depreciación ───────────────────────────────────────────────────────
with tab2:
    df_dep = dff.dropna(subset=["anio_num"])
    df_dep = df_dep[df_dep["anio_num"] >= 2005]
    top8   = dff["marca"].value_counts().head(8).index.tolist()

    dep_data = (
        df_dep[df_dep["marca"].isin(top8)]
        .groupby(["marca", "anio_num"])["precio_m"]
        .median().reset_index()
    )

    fig = px.line(
        dep_data, x="anio_num", y="precio_m", color="marca",
        markers=True,
        labels={"anio_num": "Año del vehículo", "precio_m": "Precio mediano (M CLP)", "marca": "Marca"},
        title="📉 Curva de depreciación — precio mediano por año de fabricación",
        color_discrete_sequence=COLORS, template=TEMPLATE, height=400,
    )
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(margin=dict(t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Heatmap
    df_h = (
        df_dep[df_dep["marca"].isin(top8) & (df_dep["anio_num"] >= 2012)]
        .groupby(["marca", "anio_num"])["precio_m"]
        .median().unstack("anio_num").round(1)
    )
    if not df_h.empty:
        fig2 = go.Figure(go.Heatmap(
            z=df_h.values,
            x=[str(int(c)) for c in df_h.columns],
            y=df_h.index.tolist(),
            colorscale="Blues",
            text=df_h.values.round(1),
            texttemplate="%{text}M",
            hoverongaps=False,
            colorbar_title="M CLP",
        ))
        fig2.update_layout(
            title="🗺️ Mapa de calor — Marca × Año (precio mediano)",
            xaxis_title="Año", template=TEMPLATE, height=360,
            margin=dict(t=50, b=10),
        )
        st.plotly_chart(fig2, use_container_width=True)


# ── TAB 3: Kilometraje ────────────────────────────────────────────────────────
with tab3:
    df_km = dff.dropna(subset=["km"])
    df_km = df_km[(df_km["km"] > 100) & (df_km["km"] < 400_000)]
    top8  = dff["marca"].value_counts().head(8).index.tolist()
    df_km = df_km[df_km["marca"].isin(top8)]

    if len(df_km) > 10:
        fig = px.scatter(
            df_km, x="km", y="precio_m", color="marca",
            opacity=0.55, trendline="lowess", trendline_scope="overall",
            labels={"km": "Kilometraje", "precio_m": "Precio (M CLP)", "marca": "Marca"},
            title="🛣️ Precio vs Kilometraje (tendencia global en negro)",
            color_discrete_sequence=COLORS, template=TEMPLATE, height=400,
        )
        fig.update_traces(marker=dict(size=5))
        fig.update_layout(margin=dict(t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay suficientes datos de kilometraje para este filtro.")

    # Precio por rango de km
    bins   = [0, 20_000, 50_000, 100_000, 150_000, 200_000, 400_000]
    labels = ["0–20k", "20–50k", "50–100k", "100–150k", "150–200k", "200k+"]
    df_km2 = dff.dropna(subset=["km"])
    df_km2 = df_km2[(df_km2["km"] > 100) & (df_km2["km"] < 400_000)].copy()
    if not df_km2.empty:
        df_km2["rango_km"] = pd.cut(df_km2["km"], bins=bins, labels=labels)
        rng_stats = (
            df_km2.groupby("rango_km", observed=True)["precio_m"]
            .agg(mediana="median", avisos="count").reset_index()
        )
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(go.Bar(
            x=rng_stats["rango_km"].astype(str), y=rng_stats["mediana"],
            name="Precio mediano", marker_color="#3b82f6",
            text=rng_stats["mediana"].round(1).astype(str)+"M", textposition="outside",
        ), secondary_y=False)
        fig2.add_trace(go.Scatter(
            x=rng_stats["rango_km"].astype(str), y=rng_stats["avisos"],
            name="Avisos", mode="lines+markers", marker_color="#f59e0b",
        ), secondary_y=True)
        fig2.update_yaxes(title_text="Precio mediano (M CLP)", secondary_y=False)
        fig2.update_yaxes(title_text="Cantidad de avisos", secondary_y=True)
        fig2.update_layout(
            title="Precio mediano por rango de kilometraje",
            xaxis_title="Rango km", template=TEMPLATE, height=360,
            margin=dict(t=50, b=10),
        )
        st.plotly_chart(fig2, use_container_width=True)


# ── TAB 4: Combustible / Transmisión ─────────────────────────────────────────
with tab4:
    c1, c2 = st.columns(2)

    with c1:
        df_cb = dff.dropna(subset=["combustible"])
        if not df_cb.empty:
            cb = (
                df_cb.groupby("combustible")["precio_m"]
                .agg(mediana="median", avisos="count")
                .query("avisos >= 3").sort_values("mediana", ascending=False)
            )
            fig = px.bar(
                cb.reset_index(), x="combustible", y="mediana",
                color="combustible", color_discrete_sequence=COLORS,
                text=cb["mediana"].round(1).astype(str).values+"M",
                labels={"combustible": "", "mediana": "Precio mediano (M CLP)"},
                title="⛽ Precio por combustible",
                template=TEMPLATE, height=350,
            )
            fig.update_layout(showlegend=False, margin=dict(t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        df_tr = dff.dropna(subset=["transmision"])
        if not df_tr.empty:
            tr = (
                df_tr.groupby("transmision")["precio_m"]
                .agg(mediana="median", avisos="count")
                .query("avisos >= 3").sort_values("mediana", ascending=False)
            )
            fig2 = px.bar(
                tr.reset_index(), x="transmision", y="mediana",
                color="transmision", color_discrete_sequence=COLORS,
                text=tr["mediana"].round(1).astype(str).values+"M",
                labels={"transmision": "", "mediana": "Precio mediano (M CLP)"},
                title="⚙️ Precio por transmisión",
                template=TEMPLATE, height=350,
            )
            fig2.update_layout(showlegend=False, margin=dict(t=50, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    # Nuevo vs Usado por marca
    top6 = dff["marca"].value_counts().head(6).index.tolist()
    df_cv = dff[dff["marca"].isin(top6)]
    fig3 = px.box(
        df_cv, x="condicion_es", y="precio_m", color="condicion_es",
        facet_col="marca", facet_col_wrap=3,
        color_discrete_map={"Nuevo": "#10b981", "Usado": "#f59e0b", "No especificado": "#94a3b8"},
        labels={"condicion_es": "", "precio_m": "Precio (M CLP)"},
        title="🆕 Nuevo vs Usado por marca (Top 6)",
        template=TEMPLATE, height=420,
    )
    fig3.update_layout(showlegend=False, margin=dict(t=60, b=10))
    fig3.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    st.plotly_chart(fig3, use_container_width=True)


# ── TAB 5: Top modelos ────────────────────────────────────────────────────────
with tab5:
    df_mod = dff.dropna(subset=["modelo"]).copy()
    df_mod["marca_modelo"] = df_mod["marca"] + " " + df_mod["modelo"]

    mod_stats = (
        df_mod.groupby("marca_modelo")
        .agg(avisos=("id", "count"), mediana=("precio_m", "median"))
        .reset_index()
    )

    c1, c2 = st.columns(2)
    with c1:
        top_of = mod_stats.nlargest(15, "avisos")
        fig = px.bar(
            top_of, y="marca_modelo", x="avisos", orientation="h",
            color="avisos", color_continuous_scale="Blues",
            text="avisos",
            labels={"marca_modelo": "", "avisos": "Avisos"},
            title="🏆 Top 15 — Más ofertados",
            template=TEMPLATE, height=450,
        )
        fig.update_layout(coloraxis_showscale=False, margin=dict(t=50, l=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        top_eco = mod_stats[mod_stats["avisos"] >= 3].nsmallest(15, "mediana")
        fig2 = px.bar(
            top_eco, y="marca_modelo", x="mediana", orientation="h",
            color="mediana", color_continuous_scale="Greens_r",
            text=top_eco["mediana"].round(1).astype(str)+"M",
            labels={"marca_modelo": "", "mediana": "Precio mediano (M CLP)"},
            title="💚 Top 15 — Más económicos",
            template=TEMPLATE, height=450,
        )
        fig2.update_layout(coloraxis_showscale=False, margin=dict(t=50, l=10, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    # Bubble chart
    df_bub = (
        dff.groupby("marca").agg(
            precio_med=("precio_m", "median"),
            ant_prom=("antiguedad", "mean"),
            avisos=("id", "count"),
        ).reset_index().dropna()
    )
    fig3 = px.scatter(
        df_bub, x="ant_prom", y="precio_med",
        size="avisos", color="marca", text="marca",
        size_max=60,
        labels={
            "ant_prom": "Antigüedad promedio (años)",
            "precio_med": "Precio mediano (M CLP)",
        },
        title="🫧 Precio vs Antigüedad vs Volumen",
        color_discrete_sequence=COLORS, template=TEMPLATE, height=420,
    )
    fig3.update_traces(textposition="top center")
    fig3.update_layout(showlegend=False, margin=dict(t=50, b=10))
    st.plotly_chart(fig3, use_container_width=True)

# ─── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "🚗 **Chile Auto Stats** · Fuente: MercadoLibre Chile API (pública) · "
    f"Datos a {ts} · Tipo de cambio: 1 USD = {usd_clp:,.0f} CLP"
)
