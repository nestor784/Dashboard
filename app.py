import numpy as np
import streamlit as st


from datos import (adaptar, adaptar_kpis, adaptar_presupuesto, cargar_archivo,
                   datos_demo, kpis_demo, preparar, presupuesto_demo)

st.set_page_config(page_title="Dashboard de ventas 2025 vs 2026", layout="wide")


# ---------------------------------------------------------------- sidebar
st.sidebar.header("Filtros")

archivo = st.sidebar.file_uploader(
    "Sube tus datos (CSV/Excel: fecha, producto, ventas y, opcional, transacciones y comb)",
    type=["csv", "xlsx"])

if archivo:
    dayfirst = st.sidebar.checkbox("Fechas con día primero (dd/mm/aaaa)", value=True)
    df = preparar(adaptar(cargar_archivo(archivo), con_extras=True), dayfirst=dayfirst)
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

with st.sidebar.expander("Ventas Complementarios"):
    arch2 = st.file_uploader(
        "Sube las ventas de complementarios (CSV/Excel: fecha, producto, ventas, unidad)",
        type=["csv", "xlsx"], key="arch2")
    if arch2:
        dayfirst2 = st.checkbox("Fechas con día primero (dd/mm/aaaa)", value=True,
                                key="dayfirst2")
        df2 = preparar(adaptar(cargar_archivo(arch2), prefijo="g2_", ct=st, con_unidad=True),
                       dayfirst=dayfirst2)
        if df2.empty:
            st.error("No quedaron datos válidos en el archivo del grupo 2. "
                     "Revisa las columnas elegidas o el formato de fecha.")
            df2 = None
    elif not archivo:
        st.caption("Usando datos de ejemplo.")
        df2 = preparar(datos_demo(2))
    else:
        df2 = None

with st.sidebar.expander("Indicadores comerciales (referidos, fidelización, margen, NPS)"):
    arch_kpi = st.file_uploader(
        "Sube el archivo (CSV/Excel: mes, año, referidos, fidelización, margen bruto, NPS)",
        type=["csv", "xlsx"], key="arch_kpi")
    if arch_kpi:
        kpi = adaptar_kpis(cargar_archivo(arch_kpi), dayfirst if archivo else True)
    elif not archivo:
        st.caption("Usando datos de ejemplo.")
        kpi = kpis_demo()
    else:
        kpi = None

if pres is not None:
    pres["trimestre"] = "T" + ((pres["mes"] - 1) // 3 + 1).astype(str)
    pres["semestre"] = np.where(pres["mes"] <= 6, "S1", "S2")

# Los datos se comparten con las páginas mediante session_state
st.session_state["df"] = df
st.session_state["pres"] = pres
st.session_state["df2"] = df2
st.session_state["kpi"] = kpi

# ---------------------------------------------------------------- navegación
navegacion = st.navigation([
    st.Page("vistas/ventas.py", title="Ventas Combustible",
            icon=":material/bar_chart:", default=True),
    st.Page("vistas/indicadores.py", title="Otros Indicadores Combustible",
            icon=":material/insights:"),
    st.Page("vistas/ventas2.py", title="Ventas Complementarios",
                icon=":material/bar_chart:"),
    st.Page("vistas/comercial.py", title="Indicadores Comerciales (NPS, Fidelización)",
            icon=":material/groups:"),
])
navegacion.run()
