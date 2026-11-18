import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from datos import MESES

k = st.session_state["kpi"]

st.title("Indicadores Comerciales (NPS, Fidelización)")

if k is None:
    st.info("Sube el archivo en la barra lateral, sección «Indicadores comerciales» "
            "(columnas: mes, año, referidos, fidelización, margen bruto, NPS).")
    st.stop()

k = k.copy()
k["trimestre"] = "T" + ((k["mes"] - 1) // 3 + 1).astype(str)
k["semestre"] = np.where(k["mes"] <= 6, "S1", "S2")

# ---------------------------------------------------------------- filtros
anios = sorted(k["anio"].unique())
sel_anios = st.sidebar.multiselect("Años", anios, default=anios, key="k_anios")

granularidad = st.sidebar.radio("Segmentar por", ["Mes", "Trimestre", "Semestre"],
                                horizontal=True, key="k_gran")
if granularidad == "Mes":
    col_periodo = "mes"
    opciones = list(MESES.keys())
    sel_periodos = st.sidebar.multiselect("Meses", opciones, default=opciones[:10],
                                          format_func=lambda m: MESES[m], key="k_meses")
elif granularidad == "Trimestre":
    col_periodo = "trimestre"
    opciones = ["T1", "T2", "T3", "T4"]
    sel_periodos = st.sidebar.multiselect("Trimestres", opciones, default=opciones,
                                          key="k_trims")
else:
    col_periodo = "semestre"
    opciones = ["S1", "S2"]
    sel_periodos = st.sidebar.multiselect("Semestres", opciones, default=opciones,
                                          key="k_sems")

f = k[k["anio"].isin(sel_anios) & k[col_periodo].isin(sel_periodos)]
if f.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

# ---------------------------------------------------------------- KPIs
a1 = max(sel_anios)
a0 = a1 - 1 if (a1 - 1) in sel_anios else None


def resumen(anio):
    d = f[f["anio"] == anio]
    return {"referidos": d["referidos"].sum(min_count=1), "fidelizacion": d["fidelizacion"].mean(),
            "margen": d["margen"].mean(), "nps": d["nps"].mean()}


def fmt(v, formato):
    return "—" if pd.isna(v) else formato.format(v)


def delta(v, p, formato):
    if a0 is None or pd.isna(v) or pd.isna(p):
        return None
    return formato.format(v - p) + f" vs {a0}"


r1 = resumen(a1)
r0 = resumen(a0) if a0 is not None else {}

st.caption(f"Resumen {a1}" + (f" (variación contra {a0})" if a0 else "")
           + " según los filtros seleccionados")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Referidos (total)", fmt(r1["referidos"], "{:,.0f}"),
          None if a0 is None or not r0.get("referidos")
          else f"{(r1['referidos'] / r0['referidos'] - 1) * 100:+.1f}% vs {a0}")
c2.metric("Fidelización (prom.)", fmt(r1["fidelizacion"], "{:.1f}%"),
          delta(r1["fidelizacion"], r0.get("fidelizacion"), "{:+.1f} pp"))
c3.metric("Margen bruto (prom.)", fmt(r1["margen"], "{:.1f} $"),
          delta(r1["margen"], r0.get("margen"), "{:+.1f} pesos"))
c4.metric("NPS (prom.)", fmt(r1["nps"], "{:.1f}%"),
          delta(r1["nps"], r0.get("nps"), "{:+.0f} pp"))

# ---------------------------------------------------------------- gráficos
agg = (f.groupby(["anio", col_periodo], as_index=False)
        .agg(referidos=("referidos", lambda s: s.sum(min_count=1)),
             fidelizacion=("fidelizacion", "mean"),
             margen=("margen", "mean"),
             nps=("nps", "mean"))
        .sort_values(["anio", col_periodo]))
agg["anio"] = agg["anio"].astype(str)
agg["periodo"] = agg[col_periodo].map(MESES) if col_periodo == "mes" else agg[col_periodo]
orden = ([MESES[m] for m in sorted(sel_periodos)] if col_periodo == "mes"
         else sorted(sel_periodos))
COLORES = {"2025": "#9aa5b1", "2026": "#1f77b4"}


def grafico(y, titulo, barras=False, sufijo=None):
    kw = dict(x="periodo", y=y, color="anio", category_orders={"periodo": orden},
              color_discrete_map=COLORES)
    fig = px.bar(agg, barmode="group", **kw) if barras else px.line(agg, markers=True, **kw)
    fig.update_layout(title=titulo, legend_title_text="Año", xaxis_title=None,
                      yaxis_title=None)
    if sufijo:
        fig.update_yaxes(ticksuffix=sufijo)
    return fig


g1, g2 = st.columns(2)
g1.plotly_chart(grafico("referidos", "Referidos", barras=True), use_container_width=True)
g2.plotly_chart(grafico("fidelizacion", "Fidelización (%)", sufijo="%"),
                use_container_width=True)
g3, g4 = st.columns(2)
g3.plotly_chart(grafico("margen", "Margen bruto ($)", sufijo="$"), use_container_width=True)
g4.plotly_chart(grafico("nps", "NPS"), use_container_width=True)

st.caption(f"Por {granularidad.lower()}: los referidos se suman; fidelización, margen bruto "
           "y NPS se promedian entre los meses incluidos.")

# ---------------------------------------------------------------- tabla
with st.expander("Ver tabla de datos"):
    tabla = agg.drop(columns=[col_periodo]).set_index(["periodo", "anio"]).round(1)
    st.dataframe(tabla, use_container_width=True)
    st.download_button("Descargar CSV", tabla.to_csv().encode("utf-8"),
                       "indicadores_comerciales.csv", "text/csv")
