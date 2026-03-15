import streamlit as st
from app.db import init_db
from app.uploader import upload_section
from app.views import dashboard_section, stock_summary_section, monthly_visualization_section

st.set_page_config(
    page_title="Saham IDX - Ownership Analyzer",
    layout="wide"
)

st.title("Saham IDX - Upload PDF & Ownership Dashboard")

init_db()

tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Stock Summary", "Monthly Visualization", "Upload PDF"])

with tab4:
    upload_section()

with tab1:
    dashboard_section()

with tab2:
    stock_summary_section()

with tab3:
    monthly_visualization_section()