import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from datos import ANIOS, MESES

df = st.session_state["df"]
pres = st.session_state["pres"]

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
COLOR_ANIO = {"2025": "#9aa5b1", "2026": "#1f77b4"}

# ---------------------------------------------------------------- filtros
productos = sorted(df["producto"].unique())
sel_productos = st.sidebar.multiselect("Productos", productos, default=productos,
                                       key="ind_productos")
anio = st.sidebar.radio("Año de análisis", ANIOS, index=len(ANIOS) - 1,
                        horizontal=True, key="ind_anio")

st.title("Otros indicadores")

f = df[df["producto"].isin(sel_productos)].copy()
f["dia"] = f["fecha"].dt.normalize()
fa = f[f["anio"] == anio]
ant = f[f["anio"] == anio - 1]

if fa.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

# ---------------------------------------------------------------- KPIs
diario = fa.groupby("dia")["ventas"].sum()
mensual = fa.groupby("mes")["ventas"].sum()
prom_dia = diario.mean()
prom_ant = ant.groupby("dia")["ventas"].sum().mean() if not ant.empty else np.nan
delta_prom = f"{(prom_dia / prom_ant - 1) * 100:+.1f}% vs {anio - 1}" if prom_ant else None

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Venta promedio diaria", f"{prom_dia:,.0f}", delta_prom)
k2.metric("Días con ventas", f"{diario.size:,}")
k3.metric("Mejor mes", MESES[mensual.idxmax()], f"{mensual.max():,.0f}", delta_color="off")
k4.metric("Peor mes", MESES[mensual.idxmin()], f"{mensual.min():,.0f}", delta_color="off")
k5.metric("Mejor día", diario.idxmax().strftime("%d/%m/%Y"), f"{diario.max():,.0f}",
          delta_color="off")

# ---------------------------------------------------------------- participación
st.subheader("Participación por producto")
mix = f.groupby(["anio", "producto"], as_index=False)["ventas"].sum()
colores = dict(zip(productos, px.colors.qualitative.Set2))
cols = st.columns(len(ANIOS))
for col, a in zip(cols, ANIOS):
    d = mix[mix["anio"] == a]
    if d.empty:
        continue
    fig = px.pie(d, names="producto", values="ventas", hole=0.5, title=str(a),
                 color="producto", color_discrete_map=colores)
    fig.update_traces(textinfo="percent")
    col.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- variación mensual
a0, a1 = ANIOS[0], ANIOS[-1]
st.subheader(f"Variación % {a1} vs {a0} por producto y mes")
m = (f.groupby(["anio", "producto", "mes"])["ventas"].sum()
      .unstack("anio").reindex(columns=ANIOS))
var = (m[a1] / m[a0].replace(0, np.nan) - 1) * 100
heat = var.unstack("mes").reindex(columns=range(1, 13))
if heat.notna().any().any():
    fig = px.imshow(heat, x=[MESES[i] for i in heat.columns], text_auto=".0f",
                    color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                    aspect="auto", labels=dict(color="%"))
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Solo se muestran los meses con datos en ambos años. "
               "El último mes con datos puede estar incompleto.")
else:
    st.info("No hay meses con datos en ambos años para comparar.")

# ---------------------------------------------------------------- día de la semana
st.subheader("Venta promedio por día de la semana")
por_dia = f.groupby(["anio", "producto", "dia"], as_index=False)["ventas"].sum()
por_dia["dia_sem"] = por_dia["dia"].dt.dayofweek.map(dict(enumerate(DIAS)))
prom_sem = (por_dia.groupby(["anio", "producto", "dia_sem"], as_index=False)["ventas"]
                   .mean())
prom_sem["anio"] = prom_sem["anio"].astype(str)
fig = px.bar(prom_sem, x="dia_sem", y="ventas", color="anio", barmode="group",
             facet_col="producto", category_orders={"dia_sem": DIAS},
             color_discrete_map=COLOR_ANIO)
fig.update_layout(legend_title_text="Año", xaxis_title=None, yaxis_title="Promedio diario")
fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- cumplimiento presupuesto
st.subheader(f"Cumplimiento del presupuesto {anio} por producto y mes")
if pres is None:
    st.info("Sube el archivo de presupuesto en la barra lateral para ver este indicador.")
else:
    real = fa.groupby(["producto", "mes"])["ventas"].sum()
    p = (pres[(pres["anio"] == anio) & pres["producto"].isin(sel_productos)]
         .groupby(["producto", "mes"])["presupuesto"].sum())
    c = pd.concat([real, p], axis=1).dropna()
    if c.empty:
        st.info("No hay meses con ventas y presupuesto a la vez para este año.")
    else:
        cump = c["ventas"] / c["presupuesto"].replace(0, np.nan) * 100
        heat = cump.unstack("mes").reindex(columns=range(1, 13))
        fig = px.imshow(heat, x=[MESES[i] for i in heat.columns], text_auto=".0f",
                        color_continuous_scale="RdYlGn", color_continuous_midpoint=100,
                        aspect="auto", labels=dict(color="%"))
        fig.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("100 % = presupuesto cumplido. Verde por encima, rojo por debajo.")

# ---------------------------------------------------------------- mejores días
with st.expander(f"Los 10 mejores días de {anio}"):
    top = diario.nlargest(10).reset_index()
    top.columns = ["fecha", "ventas"]
    top["fecha"] = top["fecha"].dt.strftime("%d/%m/%Y")
    st.dataframe(top.round(1), use_container_width=True, hide_index=True)
