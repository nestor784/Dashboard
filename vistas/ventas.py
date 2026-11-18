import streamlit as st

from panel_ventas import render

render(st.session_state["df"], st.session_state["pres"], "Ventas Combustible")
