import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px


st.set_page_config(page_title="Saham IDX Analyzer", layout="wide")

@st.cache_resource
def get_engine():
    pg = st.secrets["postgres"]
    url = (
        f"postgresql+psycopg2://{pg['user']}:{pg['password']}"
        f"@{pg['host']}:{pg['port']}/{pg['database']}"
    )
    return create_engine(url)

@st.cache_data(ttl=600)
def load_shareholders(limit=5000):
    engine = get_engine()
    schema = st.secrets["app"]["schema"]
    table = st.secrets["app"]["table_shareholders"]

    query = text(f"""
        SELECT *
        FROM {schema}.{table}
        LIMIT :limit
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"limit": limit})

    return df

st.title("📊 Saham IDX Fundamental & Discount Analyzer")

try:
    df = load_shareholders()

    st.success(f"Berhasil mengambil {len(df):,} baris data dari PostgreSQL.")

    st.subheader("Preview data")
    st.dataframe(df, width='stretch')

    # Bersihkan kolom numerik bila ada
    numeric_candidates = ["TOTAL_HOLDING_SHARES", "PERCENTAGE"]
    for col in numeric_candidates:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Filter sederhana
    c1, c2, c3 = st.columns(3)

    with c1:
        issuer_list = sorted(df["ISSUER_NAME"].dropna().unique().tolist()) if "ISSUER_NAME" in df.columns else []
        selected_issuer = st.selectbox("Pilih emiten", ["Semua"] + issuer_list)

    with c2:
        investor_type_list = sorted(df["INVESTOR_TYPE"].dropna().unique().tolist()) if "INVESTOR_TYPE" in df.columns else []
        selected_type = st.selectbox("Pilih tipe investor", ["Semua"] + investor_type_list)

    with c3:
        local_foreign_list = sorted(df["LOCAL_FOREIGN"].dropna().unique().tolist()) if "LOCAL_FOREIGN" in df.columns else []
        selected_lf = st.selectbox("Pilih lokal/asing", ["Semua"] + local_foreign_list)

    filtered = df.copy()

    if selected_issuer != "Semua" and "ISSUER_NAME" in filtered.columns:
        filtered = filtered[filtered["ISSUER_NAME"] == selected_issuer]

    if selected_type != "Semua" and "INVESTOR_TYPE" in filtered.columns:
        filtered = filtered[filtered["INVESTOR_TYPE"] == selected_type]

    if selected_lf != "Semua" and "LOCAL_FOREIGN" in filtered.columns:
        filtered = filtered[filtered["LOCAL_FOREIGN"] == selected_lf]

    st.subheader("Data setelah filter")
    st.dataframe(filtered, width='stretch')

    # Visualisasi komposisi pemegang saham
    if {"INVESTOR_NAME", "PERCENTAGE"}.issubset(filtered.columns):
        chart_df = (
            filtered[["INVESTOR_NAME", "PERCENTAGE"]]
            .dropna()
            .sort_values("PERCENTAGE", ascending=False)
            .head(15)
        )

        if not chart_df.empty:
            fig = px.bar(
                chart_df,
                x="INVESTOR_NAME",
                y="PERCENTAGE",
                title="Top 15 Pemegang Saham"
            )
            st.plotly_chart(fig, width='stretch')

    # Ringkasan sederhana
    st.subheader("Ringkasan")
    k1, k2, k3 = st.columns(3)

    with k1:
        st.metric("Jumlah baris", len(filtered))

    with k2:
        if "ISSUER_NAME" in filtered.columns:
            st.metric("Jumlah emiten", filtered["ISSUER_NAME"].nunique())

    with k3:
        if "INVESTOR_NAME" in filtered.columns:
            st.metric("Jumlah investor", filtered["INVESTOR_NAME"].nunique())

except Exception as e:
    st.error(f"Gagal konek ke database: {e}")