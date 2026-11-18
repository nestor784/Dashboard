import streamlit as st

from panel_ventas import render

TITULO = "Ventas Complementarios"   # cámbialo por el nombre que quieras

if st.session_state["df2"] is None:
    st.title(TITULO)
    st.info("Sube el archivo de ventas de ventas complementarios, "
            "sección Ventas Complementarios")
    st.stop()

render(st.session_state["df2"], None, TITULO, con_presupuesto=False, por_unidad=True)
