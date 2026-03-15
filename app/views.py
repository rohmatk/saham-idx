import streamlit as st
import pandas as pd
import plotly.express as px
from app.db import load_data

def dashboard_section():
    st.subheader("Data dari Database")

    limit = st.slider("Jumlah data yang ditampilkan", 100, 10000, 2000, 100)

    df = load_data(limit=limit)

    if df.empty:
        st.info("Belum ada data di database.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Jumlah baris", f"{len(df):,}")
    with c2:
        st.metric("Jumlah emiten", df["share_code"].nunique())
    with c3:
        st.metric("Jumlah investor", df["investor_name"].nunique())

    issuer_options = ["Semua"] + sorted(df["share_code"].dropna().unique().tolist())
    investor_type_options = ["Semua"] + sorted(df["investor_type"].dropna().unique().tolist())
    local_foreign_options = ["Semua"] + sorted(df["local_foreign"].dropna().unique().tolist())

    f1, f2, f3 = st.columns(3)
    with f1:
        selected_code = st.selectbox("Filter kode saham", issuer_options)
    with f2:
        selected_type = st.selectbox("Filter tipe investor", investor_type_options)
    with f3:
        selected_lf = st.selectbox("Filter lokal/asing", local_foreign_options)

    filtered = df.copy()

    if selected_code != "Semua":
        filtered = filtered[filtered["share_code"] == selected_code]
    if selected_type != "Semua":
        filtered = filtered[filtered["investor_type"] == selected_type]
    if selected_lf != "Semua":
        filtered = filtered[filtered["local_foreign"] == selected_lf]

    st.dataframe(filtered, width="stretch")

    if not filtered.empty:
        chart_df = (
            filtered[["investor_name", "percentage"]]
            .dropna()
            .sort_values("percentage", ascending=False)
            .head(15)
        )

        if not chart_df.empty:
            fig = px.bar(
                chart_df,
                x="investor_name",
                y="percentage",
                title="Top 15 Pemegang Saham",
            )
            st.plotly_chart(fig, width="stretch")

        st.subheader("Distribusi Tipe Investor")
        pie_df = (
            filtered.groupby("investor_type", dropna=False)["total_holding_shares"]
            .sum()
            .reset_index()
            .sort_values("total_holding_shares", ascending=False)
        )
        if not pie_df.empty:
            fig_pie = px.pie(
                pie_df,
                names="investor_type",
                values="total_holding_shares",
                title="Distribusi Saham berdasarkan Tipe Investor",
            )
            st.plotly_chart(fig_pie, width="stretch")

        st.subheader("Investor dengan Kepemilikan di Beberapa Saham")
        multi_df = (
            filtered.groupby("investor_name", dropna=False)
            .agg(
                num_issuers=("share_code", "nunique"),
                total_shares=("total_holding_shares", "sum"),
            )
            .reset_index()
            .query("num_issuers > 1")
            .sort_values("num_issuers", ascending=False)
            .head(15)
        )
        if not multi_df.empty:
            fig_multi = px.bar(
                multi_df,
                x="investor_name",
                y="num_issuers",
                title="Top 15 Investor dengan Kepemilikan di Beberapa Saham",
                text="num_issuers",
            )
            st.plotly_chart(fig_multi, width="stretch")

        summary_df = (
            filtered.groupby(["share_code", "issuer_name"], dropna=False)
            .agg(
                total_investor=("investor_name", "count"),
                avg_percentage=("percentage", "mean"),
                max_percentage=("percentage", "max"),
                total_shares=("total_holding_shares", "sum"),
            )
            .reset_index()
            .sort_values(["max_percentage", "total_shares"], ascending=[False, False])
        )

        st.subheader("Ringkasan per emiten")
        st.dataframe(summary_df, width="stretch")