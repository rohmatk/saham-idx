import streamlit as st
from app.db import init_db
from app.uploader import upload_section
from app.views import dashboard_section

st.set_page_config(
    page_title="Saham IDX - Ownership Analyzer",
    layout="wide"
)

st.title("Saham IDX - Upload PDF & Ownership Dashboard")

init_db()

tab1, tab2 = st.tabs(["Upload PDF", "Dashboard"])

with tab1:
    upload_section()

with tab2:
    dashboard_section()