import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Dashboard de ventas 2025 vs 2026", layout="wide")

MESES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
         7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
ANIOS = [2025, 2026]


# ---------------------------------------------------------------- datos
@st.cache_data
def datos_demo() -> pd.DataFrame:
    """Datos de ejemplo. Reemplázalos por tu CSV/Excel (fecha, producto, ventas)."""
    rng = np.random.default_rng(42)
    fechas = pd.date_range("2025-01-01", "2026-12-31", freq="D")
    base = {"Producto A": 1200, "Producto B": 800, "Producto C": 500}
    crecimiento = {"Producto A": 1.08, "Producto B": 0.95, "Producto C": 1.20}
    filas = []
    for prod, b in base.items():
        estacional = 1 + 0.25 * np.sin((fechas.month - 3) / 12 * 2 * np.pi)
        factor = np.where(fechas.year == 2026, crecimiento[prod], 1.0)
        ventas = b * estacional * factor * rng.normal(1, 0.12, len(fechas))
        filas.append(pd.DataFrame({"fecha": fechas, "producto": prod,
                                   "ventas": ventas.round(2)}))
    return pd.concat(filas, ignore_index=True)


@st.cache_data
def cargar_archivo(archivo) -> pd.DataFrame:
    if archivo.name.lower().endswith(".csv"):
        return pd.read_csv(archivo)
    return pd.read_excel(archivo)


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["anio"] = df["fecha"].dt.year.astype(int)
    df["mes"] = df["fecha"].dt.month
    df["trimestre"] = "T" + df["fecha"].dt.quarter.astype(str)
    df["semestre"] = np.where(df["mes"] <= 6, "S1", "S2")
    return df[df["anio"].isin(ANIOS)]


# ---------------------------------------------------------------- sidebar
st.sidebar.header("Filtros")

archivo = st.sidebar.file_uploader(
    "Sube tus datos (CSV/Excel con columnas: fecha, producto, ventas)",
    type=["csv", "xlsx"])
df = preparar(cargar_archivo(archivo) if archivo else datos_demo())

productos = sorted(df["producto"].unique())
sel_productos = st.sidebar.multiselect("Productos", productos, default=productos)

granularidad = st.sidebar.radio("Segmentar por", ["Mes", "Trimestre", "Semestre"],
                                horizontal=True)

if granularidad == "Mes":
    col_periodo = "mes"
    opciones = list(MESES.keys())
    sel_periodos = st.sidebar.multiselect("Meses", opciones, default=opciones,
                                          format_func=lambda m: MESES[m])
elif granularidad == "Trimestre":
    col_periodo = "trimestre"
    opciones = ["T1", "T2", "T3", "T4"]
    sel_periodos = st.sidebar.multiselect("Trimestres", opciones, default=opciones)
else:
    col_periodo = "semestre"
    opciones = ["S1", "S2"]
    sel_periodos = st.sidebar.multiselect("Semestres", opciones, default=opciones)

tipo_grafico = st.sidebar.radio("Tipo de gráfico", ["Barras", "Líneas"], horizontal=True)

# ---------------------------------------------------------------- filtrado
f = df[df["producto"].isin(sel_productos) & df[col_periodo].isin(sel_periodos)]

st.title("Ventas 2025 vs 2026")
if f.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

# ---------------------------------------------------------------- KPIs
tot = f.groupby("anio")["ventas"].sum().reindex(ANIOS).fillna(0)
var_total = (tot[2026] / tot[2025] - 1) * 100 if tot[2025] else np.nan

c1, c2, c3 = st.columns(3)
c1.metric("Total 2025", f"{tot[2025]:,.0f}")
c2.metric("Total 2026", f"{tot[2026]:,.0f}", f"{var_total:+.1f}%")
c3.metric("Diferencia", f"{tot[2026] - tot[2025]:+,.0f}")

st.subheader("Por producto")
por_prod = f.groupby(["producto", "anio"])["ventas"].sum().unstack("anio").reindex(columns=ANIOS).fillna(0)
cols = st.columns(len(por_prod))
for col, (prod, fila) in zip(cols, por_prod.iterrows()):
    var = (fila[2026] / fila[2025] - 1) * 100 if fila[2025] else np.nan
    col.metric(prod, f"{fila[2026]:,.0f}", f"{var:+.1f}% vs 2025")

# ---------------------------------------------------------------- gráfico principal
agg = (f.groupby(["anio", "producto", col_periodo], as_index=False)["ventas"].sum())
agg["anio"] = agg["anio"].astype(str)
agg["periodo"] = agg[col_periodo].map(MESES) if col_periodo == "mes" else agg[col_periodo]
orden = [MESES[m] for m in opciones] if col_periodo == "mes" else opciones

st.subheader(f"Ventas por {granularidad.lower()}")
if tipo_grafico == "Barras":
    fig = px.bar(agg, x="periodo", y="ventas", color="anio", barmode="group",
                 facet_col="producto", category_orders={"periodo": orden},
                 color_discrete_map={"2025": "#9aa5b1", "2026": "#1f77b4"})
else:
    fig = px.line(agg, x="periodo", y="ventas", color="anio", markers=True,
                  facet_col="producto", category_orders={"periodo": orden},
                  color_discrete_map={"2025": "#9aa5b1", "2026": "#1f77b4"})
fig.update_layout(legend_title_text="Año", xaxis_title=None, yaxis_title="Ventas")
fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- variación y tendencia
izq, der = st.columns(2)

with izq:
    st.subheader("Variación % 2026 vs 2025")
    var_prod = ((por_prod[2026] / por_prod[2025].replace(0, np.nan) - 1) * 100).reset_index()
    var_prod.columns = ["producto", "variacion"]
    fig2 = px.bar(var_prod, x="producto", y="variacion", text="variacion",
                  color=var_prod["variacion"] >= 0,
                  color_discrete_map={True: "#2ca02c", False: "#d62728"})
    fig2.update_traces(texttemplate="%{text:.1f}%")
    fig2.update_layout(showlegend=False, xaxis_title=None, yaxis_title="%")
    st.plotly_chart(fig2, use_container_width=True)

with der:
    st.subheader("Tendencia mensual acumulada")
    mensual = (f.groupby(["anio", "producto", "mes"], as_index=False)["ventas"].sum()
                .sort_values("mes"))
    mensual["acumulado"] = mensual.groupby(["anio", "producto"])["ventas"].cumsum()
    mensual["anio"] = mensual["anio"].astype(str)
    mensual["mes_n"] = mensual["mes"].map(MESES)
    fig3 = px.line(mensual, x="mes_n", y="acumulado", color="producto",
                   line_dash="anio", category_orders={"mes_n": list(MESES.values())})
    fig3.update_layout(xaxis_title=None, yaxis_title="Acumulado", legend_title_text="")
    st.plotly_chart(fig3, use_container_width=True)

# ---------------------------------------------------------------- tabla
with st.expander("Ver tabla de datos"):
    tabla = agg.pivot_table(index=["producto", "periodo"], columns="anio",
                            values="ventas", aggfunc="sum")
    tabla["variacion_%"] = (tabla.get("2026") / tabla.get("2025") - 1) * 100
    st.dataframe(tabla.round(1), use_container_width=True)
    st.download_button("Descargar CSV", tabla.to_csv().encode("utf-8"),
                       "ventas_filtradas.csv", "text/csv")