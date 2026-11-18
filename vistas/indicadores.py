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

tiene_tx = "transacciones" in df.columns
tiene_comb = "comb" in df.columns
sel_comb = combs = None
if tiene_comb:
    combs = sorted(df["comb"].dropna().astype(str).unique())
    sel_comb = st.sidebar.multiselect("Comb", combs, default=combs, key="ind_comb")

st.title("Otros Indicadores Ventas Combustible")

f_base = df[df["producto"].isin(sel_productos)].copy()   # todos los comb
f_base["dia"] = f_base["fecha"].dt.normalize()
f = f_base[f_base["comb"].astype(str).isin(sel_comb)] if tiene_comb else f_base
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

if tiene_tx:
    def _pct(v, previo):
        if previo is None or np.isnan(previo) or not previo:
            return None
        return f"{(v / previo - 1) * 100:+.1f}% vs {anio - 1}"

    def _ticket(d):
        t = d["transacciones"].sum()
        return d["ventas_tx"].sum() / t if t else np.nan

    hay_ant = not ant.empty
    tx_total = fa["transacciones"].sum()
    tx_total_ant = ant["transacciones"].sum() if hay_ant else np.nan
    tk, tk_ant = _ticket(fa), (_ticket(ant) if hay_ant else np.nan)
    tx_dia = fa.groupby("dia")["transacciones"].sum().mean()
    tx_dia_ant = ant.groupby("dia")["transacciones"].sum().mean() if hay_ant else np.nan

    n1, n2, n3 = st.columns(3)
    n1.metric("Transacciones", f"{tx_total:,.0f}", _pct(tx_total, tx_total_ant))
    n2.metric("Ticket promedio", "—" if np.isnan(tk) else f"{tk:,.2f}", _pct(tk, tk_ant))
    n3.metric("Transacciones promedio diarias", f"{tx_dia:,.0f}", _pct(tx_dia, tx_dia_ant))
    st.caption("Ticket promedio = ventas ÷ transacciones, calculado sobre los totales.")

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

if tiene_comb:
    st.subheader("Participación por comb")
    mix_c = f_base.groupby(["anio", "comb"], as_index=False)["ventas"].sum()
    cols_c = st.columns(len(ANIOS))
    for col, a in zip(cols_c, ANIOS):
        d = mix_c[mix_c["anio"] == a]
        if d.empty:
            continue
        fig = px.pie(d, names="comb", values="ventas", hole=0.5, title=str(a), color="comb",
                     color_discrete_map={"Frontera": "#ff7f0e", "Nacional": "#1f77b4"})
        fig.update_traces(textinfo="percent")
        col.plotly_chart(fig, use_container_width=True)
    if tiene_tx:
        tk_c = (f_base.groupby(["anio", "comb"], as_index=False)[["ventas_tx", "transacciones"]]
                .sum())
        tk_c["ticket"] = tk_c["ventas_tx"] / tk_c["transacciones"].replace(0, np.nan)
        tk_c["anio"] = tk_c["anio"].astype(str)
        fig = px.bar(tk_c, x="comb", y="ticket", color="anio", barmode="group",
                     color_discrete_map=COLOR_ANIO, title="Ticket promedio por comb")
        fig.update_layout(legend_title_text="Año", xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    st.caption("Esta sección muestra todos los comb, sin importar el filtro de la barra lateral.")

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

if tiene_tx:
    st.subheader(f"Variación % del ticket promedio {a1} vs {a0} por producto y mes")
    mt = f.groupby(["anio", "producto", "mes"])[["ventas_tx", "transacciones"]].sum()
    mt["ticket"] = mt["ventas_tx"] / mt["transacciones"].replace(0, np.nan)
    tkm = mt["ticket"].unstack("anio").reindex(columns=ANIOS)
    var_t = (tkm[a1] / tkm[a0] - 1) * 100
    heat_t = var_t.unstack("mes").reindex(columns=range(1, 13))
    if heat_t.notna().any().any():
        fig = px.imshow(heat_t, x=[MESES[i] for i in heat_t.columns], text_auto=".0f",
                        color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                        aspect="auto", labels=dict(color="%"))
        fig.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Solo se muestran los meses con datos en ambos años.")
    else:
        st.info("No hay meses con datos de transacciones en ambos años para comparar.")

    st.subheader("Ticket promedio y transacciones por día de la semana")
    dd = (f.groupby(["anio", "producto", "dia"], as_index=False)[["ventas_tx", "transacciones"]]
          .sum())
    dd["dia_sem"] = dd["dia"].dt.dayofweek.map(dict(enumerate(DIAS)))
    sem_t = (dd.groupby(["anio", "producto", "dia_sem"])
               .agg(ventas_tx=("ventas_tx", "sum"), tx_sum=("transacciones", "sum"),
                    tx_prom=("transacciones", "mean"))
               .reset_index())
    sem_t["ticket"] = sem_t["ventas_tx"] / sem_t["tx_sum"].replace(0, np.nan)
    sem_t["anio"] = sem_t["anio"].astype(str)
    for y, titulo in (("ticket", "Ticket promedio"),
                      ("tx_prom", "Transacciones promedio por día")):
        fig = px.bar(sem_t, x="dia_sem", y=y, color="anio", barmode="group",
                     facet_col="producto", category_orders={"dia_sem": DIAS},
                     color_discrete_map=COLOR_ANIO, title=titulo)
        fig.update_layout(legend_title_text="Año", xaxis_title=None, yaxis_title=None)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- cumplimiento presupuesto
st.subheader(f"Cumplimiento del presupuesto {anio} por producto y mes")
if pres is None:
    st.info("Sube el archivo de presupuesto en la barra lateral para ver este indicador.")
else:
    real = (f_base[f_base["anio"] == anio]      # todos los comb: el presupuesto no se divide por comb
            .groupby(["producto", "mes"])["ventas"].sum())
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
        st.caption("100 % = presupuesto cumplido. Verde por encima, rojo por debajo."
                   + (" El presupuesto no está separado por comb, por eso se usan todos los comb."
                      if tiene_comb else ""))

# ---------------------------------------------------------------- mejores días
with st.expander(f"Los 10 mejores días de {anio}"):
    top = diario.nlargest(10).reset_index()
    top.columns = ["fecha", "ventas"]
    top["fecha"] = top["fecha"].dt.strftime("%d/%m/%Y")
    st.dataframe(top.round(1), use_container_width=True, hide_index=True)
