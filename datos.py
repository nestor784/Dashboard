"""Funciones y constantes compartidas por todas las páginas del dashboard."""
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

MESES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
         7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
ANIOS = [2025, 2026]


# ---------------------------------------------------------------- datos
@st.cache_data
def datos_demo(grupo: int = 1) -> pd.DataFrame:
    """Datos de ejemplo. Reemplázalos por tu CSV/Excel (fecha, producto, ventas)."""
    rng = np.random.default_rng(42 if grupo == 1 else 5)
    fechas = pd.date_range("2025-01-01", "2026-12-31", freq="D")
    if grupo == 1:
        base = {"Producto A": 1200, "Producto B": 800, "Producto C": 500}
        crecimiento = {"Producto A": 1.08, "Producto B": 0.95, "Producto C": 1.20}
    else:
        base = {"Producto D": 950, "Producto E": 640, "Producto F": 380}
        crecimiento = {"Producto D": 1.12, "Producto E": 1.03, "Producto F": 0.90}
    filas = []
    for prod, b in base.items():
        estacional = 1 + 0.25 * np.sin((fechas.month - 3) / 12 * 2 * np.pi)
        factor = np.where(fechas.year == 2026, crecimiento[prod], 1.0)
        ventas = b * estacional * factor * rng.normal(1, 0.12, len(fechas))
        if grupo == 1:
            # Cada venta diaria se reparte entre comb Frontera y Nacional, con transacciones
            rng2 = np.random.default_rng(99)
            ticket_base = {"Producto A": 45, "Producto B": 30, "Producto C": 22}[prod]
            parte = np.clip(rng2.normal(0.35, 0.05, len(fechas)), 0.2, 0.5)
            for comb, share, mult in (("Frontera", parte, 1.08), ("Nacional", 1 - parte, 0.97)):
                v = (ventas * share).round(2)
                ticket = ticket_base * mult * rng2.normal(1, 0.06, len(fechas))
                filas.append(pd.DataFrame({
                    "fecha": fechas, "producto": prod, "comb": comb, "ventas": v,
                    "transacciones": np.maximum(1, np.round(v / ticket)).astype(int)}))
        else:
            filas.append(pd.DataFrame({"fecha": fechas, "producto": prod,
                                       "ventas": ventas.round(2)}))
    demo = pd.concat(filas, ignore_index=True)
    if grupo == 2:
        demo["unidad"] = demo["producto"].map(
            {"Producto D": "kg", "Producto E": "caja", "Producto F": "litro"})
    return demo


@st.cache_data
def cargar_archivo(archivo) -> pd.DataFrame:
    if archivo.name.lower().endswith(".csv"):
        return pd.read_csv(archivo)
    return pd.read_excel(archivo)


def adaptar(raw: pd.DataFrame, prefijo: str = "", ct=None,
            con_unidad: bool = False, con_extras: bool = False) -> pd.DataFrame:
    """Convierte el archivo subido al formato interno: fecha, producto, ventas.

    ct: dónde dibujar los selectores (por defecto la barra lateral).
    prefijo: se antepone a las claves de los selectores (necesario si se llama
    más de una vez, para que no se repitan).
    con_unidad: ofrece elegir una columna opcional con el tipo de unidad (kg, caja...).
    con_extras: ofrece elegir las columnas opcionales «transacciones» (número) y
    «comb» (frontera / nacional). Solo aplica al formato largo.
    """
    ct = ct or st.sidebar
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    cols = list(raw.columns)

    def buscar(*claves):
        for i, c in enumerate(cols):
            if any(k in c.lower() for k in claves):
                return i
        return 0

    formato = ct.radio(
        "Formato de tus datos",
        ["Largo: fecha, producto, ventas", "Ancho: fecha + una columna por producto"],
        key=f"{prefijo}fmt")
    c_fecha = ct.selectbox("Columna de fecha", cols, key=f"{prefijo}c_fecha",
                           index=buscar("fecha", "date", "dia", "día"))

    if formato.startswith("Largo"):
        c_prod = ct.selectbox("Columna de producto", cols, key=f"{prefijo}c_prod",
                              index=buscar("producto", "product", "item", "articulo"))
        c_ventas = ct.selectbox("Columna de ventas", cols, key=f"{prefijo}c_ventas",
                                index=buscar("venta", "monto", "total", "valor", "unidades", "cantidad"))
        out = raw[[c_fecha, c_prod, c_ventas]].set_axis(["fecha", "producto", "ventas"], axis=1)
        if con_unidad:
            ninguna = "(ninguna)"
            idx_u = next((i + 1 for i, c in enumerate(cols)
                          if any(k in c.lower() for k in ("unidad", "unit", "medida"))), 0)
            c_unidad = ct.selectbox("Columna de unidad (opcional)", [ninguna] + cols,
                                    index=idx_u, key=f"{prefijo}c_unidad")
            if c_unidad != ninguna:
                out["unidad"] = raw[c_unidad].astype(str).str.strip()
        if con_extras:
            ninguna = "(ninguna)"
            idx_t = next((i + 1 for i, c in enumerate(cols)
                          if any(k in c.lower() for k in ("transac", "tickets", "operaciones"))), 0)
            c_tx = ct.selectbox("Columna de transacciones (opcional)", [ninguna] + cols,
                                index=idx_t, key=f"{prefijo}c_tx")
            if c_tx != ninguna:
                out["transacciones"] = pd.to_numeric(raw[c_tx], errors="coerce")
            idx_c = next((i + 1 for i, c in enumerate(cols)
                          if any(k in c.lower() for k in ("comb", "combust"))), 0)
            c_comb = ct.selectbox("Columna de comb: frontera / nacional (opcional)",
                                  [ninguna] + cols, index=idx_c, key=f"{prefijo}c_comb")
            if c_comb != ninguna:
                out["comb"] = (raw[c_comb].astype("string").str.strip().str.capitalize()
                               .fillna("(sin dato)"))
    else:
        resto = [c for c in cols if c != c_fecha]
        c_prods = ct.multiselect("Columnas de productos", resto, default=resto[:3],
                                 key=f"{prefijo}c_prods")
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


def adaptar_presupuesto(raw: pd.DataFrame, dayfirst: bool, prefijo: str = "") -> pd.DataFrame:
    """Archivo de presupuesto -> columnas: anio, producto, mes, presupuesto."""
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    cols = list(raw.columns)
    sin_anio = "(sin año: aplica a ambos años)"

    c_prod = st.selectbox("Columna de producto", cols, key=f"{prefijo}p_prod",
                          index=_buscar(cols, "producto", "product", "item", "articulo"))
    c_mes = st.selectbox("Columna de mes (1-12, nombre o fecha)", cols, key=f"{prefijo}p_mes",
                         index=_buscar(cols, "mes", "month", "fecha", "periodo"))
    c_pres = st.selectbox("Columna de presupuesto", cols, key=f"{prefijo}p_pres",
                          index=_buscar(cols, "presupuesto", "budget", "meta"))
    idx_anio = next((i + 1 for i, c in enumerate(cols)
                     if any(k in c.lower() for k in ("año", "anio", "year"))), 0)
    c_anio = st.selectbox("Columna de año", [sin_anio] + cols, index=idx_anio, key=f"{prefijo}p_anio")

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
    if "transacciones" in df.columns:
        # Ticket promedio = suma(ventas) / suma(transacciones), usando solo las filas
        # que tienen transacciones, para que un dato faltante no infle el resultado.
        df["ventas_tx"] = df["ventas"].where(df["transacciones"].notna())
    return df[df["anio"].isin(ANIOS)]



# ---------------------------------------------------------------- indicadores comerciales
def adaptar_kpis(raw: pd.DataFrame, dayfirst: bool) -> pd.DataFrame:
    """Archivo mensual -> columnas: anio, mes, referidos, fidelizacion, margen, nps."""
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    cols = list(raw.columns)
    de_fecha = "(tomar el año de la fecha en «mes»)"

    c_mes = st.selectbox("Columna de mes (1-12, nombre o fecha)", cols, key="k_mes",
                         index=_buscar(cols, "mes", "month", "fecha", "periodo"))
    idx_anio = next((i + 1 for i, c in enumerate(cols)
                     if any(k in c.lower() for k in ("año", "anio", "ano", "year"))), 0)
    c_anio = st.selectbox("Columna de año", [de_fecha] + cols, index=idx_anio, key="k_anio")
    c_ref = st.selectbox("Referidos", cols, key="k_ref",
                         index=_buscar(cols, "referid", "referral"))
    c_fid = st.selectbox("Fidelización", cols, key="k_fid",
                         index=_buscar(cols, "fideliz", "retenc", "loyal"))
    c_mar = st.selectbox("Margen bruto", cols, key="k_mar",
                         index=_buscar(cols, "margen", "margin"))
    c_nps = st.selectbox("NPS", cols, key="k_nps", index=_buscar(cols, "nps"))

    mes, anio_fecha = parsear_mes(raw[c_mes], dayfirst)
    out = pd.DataFrame({
        "mes": mes,
        "referidos": pd.to_numeric(raw[c_ref], errors="coerce"),
        "fidelizacion": pd.to_numeric(raw[c_fid], errors="coerce"),
        "margen": pd.to_numeric(raw[c_mar], errors="coerce"),
        "nps": pd.to_numeric(raw[c_nps], errors="coerce"),
    })
    if c_anio != de_fecha:
        out["anio"] = pd.to_numeric(raw[c_anio], errors="coerce")
    elif anio_fecha is not None:
        out["anio"] = anio_fecha
    else:
        st.error("No encuentro el año: elige la columna de año o usa fechas en «mes».")
        st.stop()

    # Fidelización y margen pueden venir como fracción (0.35) o como porcentaje (35)
    for c in ("fidelizacion", "margen"):
        s = out[c].dropna()
        if not s.empty and s.abs().max() <= 1.0:
            out[c] = out[c] * 100
            st.caption(f"«{c}» venía en fracción (0-1): se convirtió a %.")

    out = out.dropna(subset=["mes", "anio"])
    out["mes"] = out["mes"].astype(int)
    out["anio"] = out["anio"].astype(int)
    out = out[out["mes"].between(1, 12)]
    return out.groupby(["anio", "mes"], as_index=False).agg(
        referidos=("referidos", lambda s: s.sum(min_count=1)),
        fidelizacion=("fidelizacion", "mean"),
        margen=("margen", "mean"),
        nps=("nps", "mean"))


@st.cache_data
def kpis_demo() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    filas = []
    for anio, mejora in ((2025, 0.0), (2026, 1.0)):
        for mes in range(1, 13):
            filas.append({
                "anio": anio, "mes": mes,
                "referidos": int(rng.integers(35, 70) + 12 * mejora),
                "fidelizacion": round(rng.normal(66 + 4 * mejora, 2.5), 1),
                "margen": round(rng.normal(31 + 1.5 * mejora, 1.8), 1),
                "nps": round(rng.normal(42 + 6 * mejora, 4), 0),
            })
    return pd.DataFrame(filas)
