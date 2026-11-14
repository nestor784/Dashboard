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


def adaptar(raw: pd.DataFrame) -> pd.DataFrame:
    """Convierte el archivo subido al formato interno: fecha, producto, ventas."""
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    cols = list(raw.columns)

    def buscar(*claves):
        for i, c in enumerate(cols):
            if any(k in c.lower() for k in claves):
                return i
        return 0

    formato = st.sidebar.radio(
        "Formato de tus datos",
        ["Largo: fecha, producto, ventas", "Ancho: fecha + una columna por producto"])
    c_fecha = st.sidebar.selectbox("Columna de fecha", cols,
                                   index=buscar("fecha", "date", "dia", "día"))

    if formato.startswith("Largo"):
        c_prod = st.sidebar.selectbox("Columna de producto", cols,
                                      index=buscar("producto", "product", "item", "articulo"))
        c_ventas = st.sidebar.selectbox("Columna de ventas", cols,
                                        index=buscar("venta", "monto", "total", "valor", "unidades", "cantidad"))
        out = raw[[c_fecha, c_prod, c_ventas]].set_axis(["fecha", "producto", "ventas"], axis=1)
    else:
        resto = [c for c in cols if c != c_fecha]
        c_prods = st.sidebar.multiselect("Columnas de productos", resto, default=resto[:3])
        if not c_prods:
            st.info("Selecciona al menos una columna de producto.")
            st.stop()
        out = (raw.melt(id_vars=c_fecha, value_vars=c_prods,
                        var_name="producto", value_name="ventas")
                  .rename(columns={c_fecha: "fecha"}))

    out["ventas"] = pd.to_numeric(out["ventas"], errors="coerce")
    return out


def _buscar(cols, *claves):
    for i, c in enumerate(cols):
        if any(k in c.lower() for k in claves):
            return i
    return 0


def parsear_mes(serie: pd.Series, dayfirst: bool):
    """Devuelve (mes, anio). anio es None si la columna no trae año."""
    if not pd.api.types.is_datetime64_any_dtype(serie):
        num = pd.to_numeric(serie, errors="coerce")
        if num.notna().all() and num.between(1, 12).all():
            return num.astype(int), None
        nombres = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
                   "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}
        por_nombre = serie.astype(str).str.strip().str.lower().str[:3].map(nombres)
        if por_nombre.notna().all():
            return por_nombre.astype(int), None
    fechas = pd.to_datetime(serie, dayfirst=dayfirst, errors="coerce")
    return fechas.dt.month, fechas.dt.year


def adaptar_presupuesto(raw: pd.DataFrame, dayfirst: bool) -> pd.DataFrame:
    """Archivo de presupuesto -> columnas: anio, producto, mes, presupuesto."""
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    cols = list(raw.columns)
    sin_anio = "(sin año: aplica a ambos años)"

    c_prod = st.selectbox("Columna de producto", cols, key="p_prod",
                          index=_buscar(cols, "producto", "product", "item", "articulo"))
    c_mes = st.selectbox("Columna de mes (1-12, nombre o fecha)", cols, key="p_mes",
                         index=_buscar(cols, "mes", "month", "fecha", "periodo"))
    c_pres = st.selectbox("Columna de presupuesto", cols, key="p_pres",
                          index=_buscar(cols, "presupuesto", "budget", "meta"))
    idx_anio = next((i + 1 for i, c in enumerate(cols)
                     if any(k in c.lower() for k in ("año", "anio", "year"))), 0)
    c_anio = st.selectbox("Columna de año", [sin_anio] + cols, index=idx_anio, key="p_anio")

    mes, anio_fecha = parsear_mes(raw[c_mes], dayfirst)
    out = pd.DataFrame({
        "producto": raw[c_prod].astype(str).str.strip(),
        "mes": mes,
        "presupuesto": pd.to_numeric(raw[c_pres], errors="coerce"),
    })
    if c_anio != sin_anio:
        out["anio"] = pd.to_numeric(raw[c_anio], errors="coerce")
    elif anio_fecha is not None:
        out["anio"] = anio_fecha

    out = out.dropna(subset=["mes", "presupuesto"])
    out["mes"] = out["mes"].astype(int)
    if "anio" in out.columns:
        out = out.dropna(subset=["anio"])
        out["anio"] = out["anio"].astype(int)
    else:
        out = pd.concat([out.assign(anio=a) for a in ANIOS], ignore_index=True)
    out = out[out["anio"].isin(ANIOS)]
    return out.groupby(["anio", "producto", "mes"], as_index=False)["presupuesto"].sum()


@st.cache_data
def presupuesto_demo(base: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    m = base.groupby(["anio", "producto", "mes"], as_index=False)["ventas"].sum()
    m["presupuesto"] = (m["ventas"] * rng.uniform(0.9, 1.15, len(m))).round(0)
    return m[["anio", "producto", "mes", "presupuesto"]]


def preparar(df: pd.DataFrame, dayfirst: bool = False) -> pd.DataFrame:
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=dayfirst, errors="coerce")
    df = df.dropna(subset=["fecha", "ventas"])
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

if archivo:
    dayfirst = st.sidebar.checkbox("Fechas con día primero (dd/mm/aaaa)", value=False)
    df = preparar(adaptar(cargar_archivo(archivo)), dayfirst=dayfirst)
else:
    df = preparar(datos_demo())

if df.empty:
    st.error("No quedaron datos válidos tras leer el archivo. Revisa las columnas de fecha y ventas elegidas, o el formato de fecha.")
    st.stop()

with st.sidebar.expander("Presupuesto mensual por producto", expanded=True):
    if archivo:
        arch_pres = st.file_uploader(
            "Sube el presupuesto (CSV/Excel: producto, mes, presupuesto y, opcional, año)",
            type=["csv", "xlsx"], key="arch_pres")
        pres = adaptar_presupuesto(cargar_archivo(arch_pres), dayfirst) if arch_pres else None
    else:
        st.caption("Usando presupuesto de ejemplo.")
        pres = presupuesto_demo(df)

if pres is not None:
    pres["trimestre"] = "T" + ((pres["mes"] - 1) // 3 + 1).astype(str)
    pres["semestre"] = np.where(pres["mes"] <= 6, "S1", "S2")

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
st.subheader("Real vs presupuesto")
if pres is None:
    st.info("Sube el archivo de presupuesto en la barra lateral para ver esta comparación.")
else:
    anio_cmp = st.radio("Año a comparar con el presupuesto", ANIOS,
                        index=len(ANIOS) - 1, horizontal=True)

    sin_match = sorted(set(pres["producto"].astype(str)) - set(df["producto"].astype(str)))
    if sin_match:
        st.warning("Productos del presupuesto que no coinciden con los de ventas "
                   "(revisa los nombres): " + ", ".join(sin_match))

    pres_f = pres[(pres["anio"] == anio_cmp)
                  & pres["producto"].isin(sel_productos)
                  & pres[col_periodo].isin(sel_periodos)]
    real_m = (f[f["anio"] == anio_cmp]
              .groupby(["producto", "mes"], as_index=False)["ventas"].sum()
              .rename(columns={"ventas": "real"}))
    pres_m = pres_f.groupby(["producto", "mes"], as_index=False)["presupuesto"].sum()
    cmp_df = (real_m.merge(pres_m, on=["producto", "mes"], how="outer")
                    .fillna(0).sort_values(["producto", "mes"]))

    if cmp_df.empty:
        st.info("No hay datos de presupuesto para los filtros seleccionados.")
    else:
        t_real, t_pres = cmp_df["real"].sum(), cmp_df["presupuesto"].sum()
        cumpl = t_real / t_pres * 100 if t_pres else np.nan
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(f"Real {anio_cmp}", f"{t_real:,.0f}")
        k2.metric("Presupuesto", f"{t_pres:,.0f}")
        k3.metric("Diferencia", f"{t_real - t_pres:+,.0f}")
        k4.metric("Cumplimiento", f"{cumpl:.1f}%")

        cmp_df["mes_n"] = cmp_df["mes"].map(MESES)
        orden_meses = [MESES[m] for m in sorted(cmp_df["mes"].unique())]
        largo = cmp_df.melt(id_vars=["producto", "mes", "mes_n"],
                            value_vars=["presupuesto", "real"],
                            var_name="serie", value_name="valor").sort_values("mes")
        fig4 = px.bar(largo, x="mes_n", y="valor", color="serie", barmode="group",
                      facet_col="producto", category_orders={"mes_n": orden_meses},
                      color_discrete_map={"presupuesto": "#9aa5b1", "real": "#1f77b4"})
        fig4.update_layout(legend_title_text="", xaxis_title=None, yaxis_title="Ventas")
        fig4.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig4, use_container_width=True)

        por_p = cmp_df.groupby("producto", as_index=False)[["real", "presupuesto"]].sum()
        por_p["cumplimiento"] = por_p["real"] / por_p["presupuesto"].replace(0, np.nan) * 100
        fig5 = px.bar(por_p, x="producto", y="cumplimiento", text="cumplimiento",
                      color=por_p["cumplimiento"] >= 100,
                      color_discrete_map={True: "#2ca02c", False: "#d62728"})
        fig5.update_traces(texttemplate="%{text:.1f}%")
        fig5.add_hline(y=100, line_dash="dash")
        fig5.update_layout(showlegend=False, xaxis_title=None,
                           yaxis_title="% de cumplimiento del presupuesto")
        st.plotly_chart(fig5, use_container_width=True)

        with st.expander("Ver detalle real vs presupuesto"):
            det = cmp_df[["producto", "mes_n", "presupuesto", "real"]].copy()
            det["diferencia"] = det["real"] - det["presupuesto"]
            det["cumplimiento_%"] = det["real"] / det["presupuesto"].replace(0, np.nan) * 100
            st.dataframe(det.round(1), use_container_width=True)
            st.download_button("Descargar detalle (CSV)", det.to_csv(index=False).encode("utf-8"),
                               "real_vs_presupuesto.csv", "text/csv")

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