import streamlit as st
import pandas as pd
import plotly.express as px
from app.db import load_data, load_stock_data

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
    holding_type_options = ["Semua", "Scripless Only", "Scrip Only"]
    investor_options = ["Semua"] + sorted(df["investor_name"].dropna().unique().tolist())

    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        selected_code = st.selectbox("Filter kode saham", issuer_options)
    with f2:
        selected_type = st.selectbox("Filter tipe investor", investor_type_options)
    with f3:
        selected_lf = st.selectbox("Filter lokal/asing", local_foreign_options)
    with f4:
        selected_holding = st.selectbox("Filter Tipe Holding", holding_type_options)
    with f5:
        selected_investor = st.selectbox("Filter Investor Name", investor_options)

    filtered = df.copy()

    if selected_code != "Semua":
        filtered = filtered[filtered["share_code"] == selected_code]
    if selected_type != "Semua":
        filtered = filtered[filtered["investor_type"] == selected_type]
    if selected_lf != "Semua":
        filtered = filtered[filtered["local_foreign"] == selected_lf]
    if selected_holding == "Scripless Only":
        filtered = filtered[filtered["holdings_scripless"] > 0]
    elif selected_holding == "Scrip Only":
        filtered = filtered[filtered["holdings_scrip"] > 0]
    if selected_investor != "Semua":
        filtered = filtered[filtered["investor_name"] == selected_investor]

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
        investor_mapping = {
            'ID': 'Individual',
            'CP': 'Corporate (Perusahaan)',
            'MF': 'Mutual Fund (Reksa Dana)',
            'IB': 'Financial Institution (Lembaga Keuangan)',
            'IS': 'Insurance (Asuransi)',
            'SC': 'Securities Company (Perusahaan Efek)',
            'PF': 'Pension Fund (Dana Pensiun)',
            'FD': 'Foundation (Yayasan)',
            'OT': 'Others (Lainnya)'
        }
        pie_df = (
            filtered.groupby("investor_type", dropna=False)["total_holding_shares"]
            .sum()
            .reset_index()
            .sort_values("total_holding_shares", ascending=False)
        )
        if not pie_df.empty:
            # Map known investor types; keep unknown values clearly labeled rather than showing raw tokens like "4"
            pie_df["investor_type"] = pie_df["investor_type"].map(investor_mapping).fillna("Unknown")
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
                color="total_shares",
                color_continuous_scale="Blues",
            )
            st.plotly_chart(fig_multi, width="stretch")

        # Bubble chart: investor vs holdings vs number of issuers
        bubble_df = (
            filtered.groupby(["investor_name", "investor_type"], dropna=False)
            .agg(
                num_issuers=("share_code", "nunique"),
                total_shares=("total_holding_shares", "sum"),
            )
            .reset_index()
            .sort_values("total_shares", ascending=False)
            .head(50)
        )

        if not bubble_df.empty:
            bubble_df["investor_type"] = bubble_df["investor_type"].map(investor_mapping).fillna("Unknown")
            fig_bubble = px.scatter(
                bubble_df,
                x="num_issuers",
                y="total_shares",
                size="total_shares",
                color="investor_type",
                hover_name="investor_name",
                title="Bubble Chart: Investor vs Jumlah Emiten vs Total Saham",
                labels={
                    "num_issuers": "Jumlah Emiten",
                    "total_shares": "Total Saham",
                    "investor_type": "Tipe Investor",
                },
            )
            st.plotly_chart(fig_bubble, width="stretch")

        st.subheader("Hubungan Holdings vs Persentase")
        scatter_df = filtered[["total_holding_shares", "percentage", "investor_type", "share_code"]].dropna()
        if not scatter_df.empty:
            fig_scatter = px.scatter(
                scatter_df,
                x="total_holding_shares",
                y="percentage",
                color="share_code",
                title="Scatter Plot: Total Holdings vs Persentase",
                log_x=True,
            )
            st.plotly_chart(fig_scatter, width="stretch")

        st.subheader("Top Issuers by Total Holdings")
        issuers_df = (
            filtered.groupby("share_code", dropna=False)["total_holding_shares"]
            .sum()
            .reset_index()
            .sort_values("total_holding_shares", ascending=False)
            .head(15)
        )
        if not issuers_df.empty:
            fig_issuers = px.bar(
                issuers_df,
                x="share_code",
                y="total_holding_shares",
                title="Top 15 Issuers by Total Holdings",
                text="total_holding_shares",
            )
            st.plotly_chart(fig_issuers, width="stretch")

        st.subheader("Perbandingan Holdings Scripless vs Scrip")
        stack_df = (
            filtered.groupby("share_code", dropna=False)
            .agg(
                holdings_scripless=("holdings_scripless", "sum"),
                holdings_scrip=("holdings_scrip", "sum"),
            )
            .reset_index()
            .assign(total=lambda x: x["holdings_scripless"] + x["holdings_scrip"])
            .sort_values("total", ascending=False)
            .head(15)
        )
        if not stack_df.empty:
            fig_stack = px.bar(
                stack_df,
                x="share_code",
                y=["holdings_scripless", "holdings_scrip"],
                title="Top 15 Issuers: Holdings Scripless vs Scrip",
                barmode="stack",
            )
            st.plotly_chart(fig_stack, width="stretch")

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


def stock_summary_section():
    st.subheader("Data Summary Saham IDX")

    df = load_stock_data()

    # Filter only EQUITY
    df = df[df['type'] == 'EQUITY']

    if df.empty:
        st.info("Belum ada data summary EQUITY.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Jumlah Saham", f"{len(df):,}")
    with c2:
        st.metric("Jumlah Sektor", df["sector"].nunique())
    with c3:
        st.metric("Rata-rata Closing Price", f"{df['closing_price'].mean():,.0f}")

    sector_options = ["Semua"] + sorted(df["sector"].dropna().unique().tolist())
    code_options = ["Semua"] + sorted(df["code"].dropna().unique().tolist())

    f1, f2, f3 = st.columns(3)
    with f1:
        selected_sector = st.selectbox("Filter Sektor", sector_options)
    with f2:
        selected_code = st.selectbox("Filter Kode Saham", code_options)
    with f3:
        price_range = st.slider("Range Closing Price", 0, int(df['closing_price'].max()), (0, int(df['closing_price'].max())))

    filtered = df.copy()

    if selected_sector != "Semua":
        filtered = filtered[filtered["sector"] == selected_sector]
    if selected_code != "Semua":
        filtered = filtered[filtered["code"] == selected_code]
    filtered = filtered[(filtered['closing_price'] >= price_range[0]) & (filtered['closing_price'] <= price_range[1])]

    st.dataframe(filtered, width="stretch")

    # Top sectors by local ownership
    st.subheader("Top Sektor by Local Ownership")
    sector_df = (
        filtered.groupby("sector", dropna=False)["local_%"]
        .mean()
        .reset_index()
        .sort_values("local_%", ascending=False)
        .head(10)
    )
    if not sector_df.empty:
        fig_sector = px.bar(
            sector_df,
            x="sector",
            y="local_%",
            title="Rata-rata Kepemilikan Lokal per Sektor",
        )
        st.plotly_chart(fig_sector, width="stretch")

    # Pie chart for sector distribution
    st.subheader("Distribusi Sektor")
    pie_df = filtered["sector"].value_counts().reset_index()
    pie_df.columns = ["sector", "count"]
    if not pie_df.empty:
        fig_pie = px.pie(
            pie_df,
            names="sector",
            values="count",
            title="Distribusi Jumlah Saham per Sektor",
        )
        st.plotly_chart(fig_pie, width="stretch")

    # Top by foreign ownership
    st.subheader("Top Sektor by Foreign Ownership")
    foreign_df = (
        filtered.groupby("sector", dropna=False)["foreign_%"]
        .mean()
        .reset_index()
        .sort_values("foreign_%", ascending=False)
        .head(10)
    )
    if not foreign_df.empty:
        fig_foreign = px.bar(
            foreign_df,
            x="sector",
            y="foreign_%",
            title="Rata-rata Kepemilikan Asing per Sektor",
        )
        st.plotly_chart(fig_foreign, width="stretch")

    # Scatter closing price vs local %
    st.subheader("Hubungan Closing Price vs Local Ownership")
    scatter_df = filtered[["closing_price", "local_%", "sector"]].dropna()
    if not scatter_df.empty:
        fig_scatter = px.scatter(
            scatter_df,
            x="closing_price",
            y="local_%",
            color="sector",
            title="Scatter: Closing Price vs Local (%)",
            log_x=True,
        )
        st.plotly_chart(fig_scatter, width="stretch")

    # Scatter closing price vs foreign %
    st.subheader("Hubungan Closing Price vs Foreign Ownership")
    scatter_foreign_df = filtered[["closing_price", "foreign_%", "sector"]].dropna()
    if not scatter_foreign_df.empty:
        fig_scatter_foreign = px.scatter(
            scatter_foreign_df,
            x="closing_price",
            y="foreign_%",
            color="sector",
            title="Scatter: Closing Price vs Foreign (%)",
            log_x=True,
        )
        st.plotly_chart(fig_scatter_foreign, width="stretch")


import os
from pathlib import Path

def load_monthly_balance_data():
    """Load all balance position data from monthly TXT files."""
    data_dir = Path(__file__).resolve().parents[1] / "data" / "BalanceposEfek"
    dfs = []
    for file_path in data_dir.glob("*.txt"):
        try:
            df = pd.read_csv(file_path, sep='|', dtype=str, encoding='latin1')
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date'], format='%d-%b-%Y', errors='coerce')
            df['Local IS'] = pd.to_numeric(df['Local IS'], errors='coerce')
            df['Local CP'] = pd.to_numeric(df['Local CP'], errors='coerce')
            df['Local PF'] = pd.to_numeric(df['Local PF'], errors='coerce')
            df['Local IB'] = pd.to_numeric(df['Local IB'], errors='coerce')
            df['Local ID'] = pd.to_numeric(df['Local ID'], errors='coerce')
            df['Local MF'] = pd.to_numeric(df['Local MF'], errors='coerce')
            df['Local SC'] = pd.to_numeric(df['Local SC'], errors='coerce')
            df['Local FD'] = pd.to_numeric(df['Local FD'], errors='coerce')
            df['Local OT'] = pd.to_numeric(df['Local OT'], errors='coerce')
            df['Local Total'] = pd.to_numeric(df['Total'], errors='coerce')
            df['Foreign IS'] = pd.to_numeric(df['Foreign IS'], errors='coerce')
            df['Foreign CP'] = pd.to_numeric(df['Foreign CP'], errors='coerce')
            df['Foreign PF'] = pd.to_numeric(df['Foreign PF'], errors='coerce')
            df['Foreign IB'] = pd.to_numeric(df['Foreign IB'], errors='coerce')
            df['Foreign ID'] = pd.to_numeric(df['Foreign ID'], errors='coerce')
            df['Foreign MF'] = pd.to_numeric(df['Foreign MF'], errors='coerce')
            df['Foreign SC'] = pd.to_numeric(df['Foreign SC'], errors='coerce')
            df['Foreign FD'] = pd.to_numeric(df['Foreign FD'], errors='coerce')
            df['Foreign OT'] = pd.to_numeric(df['Foreign OT'], errors='coerce')
            df['Foreign Total'] = pd.to_numeric(df['Total.1'], errors='coerce')
            df['Total'] = pd.to_numeric(df['Total'], errors='coerce') + pd.to_numeric(df['Total.1'], errors='coerce')
            dfs.append(df)
        except Exception as e:
            st.error(f"Error loading {file_path}: {e}")
    if dfs:
        combined_df = pd.concat(dfs, ignore_index=True)
        # Filter only EQUITY
        combined_df = combined_df[combined_df['Type'] == 'EQUITY']
        return combined_df
    return pd.DataFrame()

def load_monthly_statis_data():
    """Load all statis efek data from monthly TXT files."""
    data_dir = Path(__file__).resolve().parents[1] / "data" / "StatisEfek"
    dfs = []
    for file_path in data_dir.glob("*.txt"):
        try:
            df = pd.read_csv(file_path, sep='|', dtype=str, encoding='latin1')
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date'], format='%d-%b-%Y', errors='coerce')
            df['Num. of Sec'] = pd.to_numeric(df['Num. of Sec'], errors='coerce')
            df['Total Scripless'] = pd.to_numeric(df['Total Scripless'], errors='coerce')
            df['Local (%)'] = pd.to_numeric(df['Local (%)'], errors='coerce')
            df['Foreign (%)'] = pd.to_numeric(df['Foreign (%)'], errors='coerce')
            df['Total (%)'] = pd.to_numeric(df['Total (%)'], errors='coerce')
            df['Closing Price'] = pd.to_numeric(df['Closing Price'], errors='coerce')
            dfs.append(df)
        except Exception as e:
            st.error(f"Error loading {file_path}: {e}")
    if dfs:
        combined_df = pd.concat(dfs, ignore_index=True)
        # Filter only EQUITY
        combined_df = combined_df[combined_df['Type'] == 'EQUITY']
        return combined_df
    return pd.DataFrame()

def monthly_visualization_section():
    st.subheader("Visualisasi Data Bulanan")

    # Load data
    balance_df = load_monthly_balance_data()
    statis_df = load_monthly_statis_data()

    if balance_df.empty and statis_df.empty:
        st.info("Tidak ada data bulanan ditemukan.")
        return

    # Investor type mapping
    investor_mapping = {
        'ID': 'Individual',
        'CP': 'Corporate (Perusahaan)',
        'MF': 'Mutual Fund (Reksa Dana)',
        'IB': 'Financial Institution (Lembaga Keuangan)',
        'IS': 'Insurance (Asuransi)',
        'SC': 'Securities Company (Perusahaan Efek)',
        'PF': 'Pension Fund (Dana Pensiun)',
        'FD': 'Foundation (Yayasan)',
        'OT': 'Others (Lainnya)'
    }

    # Aggregate balance data by month
    if not balance_df.empty:
        balance_monthly = balance_df.groupby(balance_df['Date'].dt.to_period('M')).agg({
            'Local Total': 'sum',
            'Foreign Total': 'sum',
            'Total': 'sum'
        }).reset_index()
        balance_monthly['Date'] = balance_monthly['Date'].dt.to_timestamp()
        balance_monthly['Local %'] = (balance_monthly['Local Total'] / balance_monthly['Total']) * 100
        balance_monthly['Foreign %'] = (balance_monthly['Foreign Total'] / balance_monthly['Total']) * 100

        st.subheader("Trend Kepemilikan Lokal vs Asing (Balance Position)")
        fig_balance = px.line(
            balance_monthly,
            x='Date',
            y=['Local %', 'Foreign %'],
            title="Persentase Kepemilikan Lokal vs Asing per Bulan",
            markers=True
        )
        st.plotly_chart(fig_balance, width="stretch")

        # Show changes
        if len(balance_monthly) > 1:
            balance_monthly = balance_monthly.sort_values('Date')
            balance_monthly['Local Change'] = balance_monthly['Local %'].pct_change() * 100
            balance_monthly['Foreign Change'] = balance_monthly['Foreign %'].pct_change() * 100
            st.subheader("Perubahan Persentase Bulanan")
            st.dataframe(balance_monthly[['Date', 'Local %', 'Foreign %', 'Local Change', 'Foreign Change']], width="stretch")

        # New: Investor breakdown
        st.subheader("Breakdown Pemegang Saham per Tipe Investor")
        category = st.radio("Pilih Kategori:", ["Local", "Foreign"], horizontal=True)

        prefix = category.lower()  # 'local' or 'foreign'
        investor_cols = [col for col in balance_df.columns if col.startswith(f'{category} ') and col != f'{category} Total']
        
        if investor_cols:
            # Aggregate by month and investor type
            agg_dict = {col: 'sum' for col in investor_cols}
            investor_monthly = balance_df.groupby(balance_df['Date'].dt.to_period('M')).agg(agg_dict).reset_index()
            investor_monthly['Date'] = investor_monthly['Date'].dt.to_timestamp()
            
            # Rename columns using mapping
            renamed_cols = {}
            for col in investor_cols:
                code = col.replace(f'{category} ', '')
                if code in investor_mapping:
                    renamed_cols[col] = investor_mapping[code]
                else:
                    renamed_cols[col] = code
            
            investor_monthly = investor_monthly.rename(columns=renamed_cols)
            renamed_investor_cols = list(renamed_cols.values())
            
            # Line chart for trends
            fig_investor = px.line(
                investor_monthly,
                x='Date',
                y=renamed_investor_cols,
                title=f"Trend Kepemilikan {category} per Tipe Investor",
                markers=True
            )
            st.plotly_chart(fig_investor, width="stretch")
            
            # Pie chart for latest month
            latest_data = investor_monthly.iloc[-1] if not investor_monthly.empty else None
            if latest_data is not None:
                pie_data = latest_data[renamed_investor_cols]
                pie_data = pie_data[pie_data > 0]  # Only show positive values
                if not pie_data.empty:
                    fig_pie = px.pie(
                        names=pie_data.index,
                        values=pie_data.values,
                        title=f"Distribusi {category} Pemegang Saham Bulan Terakhir ({latest_data['Date'].strftime('%B %Y')})"
                    )
                    st.plotly_chart(fig_pie, width="stretch")

    # Aggregate statis data by month
    if not statis_df.empty:
        statis_monthly = statis_df.groupby(statis_df['Date'].dt.to_period('M')).agg({
            'Local (%)': 'mean',
            'Foreign (%)': 'mean',
            'Total (%)': 'mean',
            'Closing Price': 'mean'
        }).reset_index()
        statis_monthly['Date'] = statis_monthly['Date'].dt.to_timestamp()

        st.subheader("Trend Rata-rata Kepemilikan per Bulan (Statis Efek)")
        fig_statis = px.line(
            statis_monthly,
            x='Date',
            y=['Local (%)', 'Foreign (%)'],
            title="Rata-rata Persentase Kepemilikan Lokal vs Asing per Bulan",
            markers=True
        )
        st.plotly_chart(fig_statis, width="stretch")

        # Perubahan per saham
        st.subheader("Perubahan Kepemilikan per Saham")
        change_df = pd.DataFrame()
        latest = None
        prev = None
        if len(statis_df['Date'].unique()) > 1:
            pivot_df = statis_df.pivot_table(
                index='Code',
                columns=statis_df['Date'].dt.to_period('M'),
                values=['Local (%)', 'Foreign (%)'],
                aggfunc='first'
            ).reset_index()
            pivot_df.columns = [f"{col[0]}_{col[1]}" if col[1] else col[0] for col in pivot_df.columns]
            
            # Calculate changes for each stock
            dates = sorted(statis_df['Date'].dt.to_period('M').dropna().unique())
            change_df = pd.DataFrame()
            latest = None
            prev = None
            if len(dates) >= 2:
                latest = dates[-1]
                prev = dates[-2]
                change_df = statis_df[statis_df['Date'].dt.to_period('M').isin([prev, latest])]
                change_df = change_df.pivot_table(index='Code', columns='Date', values=['Local (%)', 'Foreign (%)'], aggfunc='first').reset_index()
                change_df.columns = change_df.columns.map(lambda x: f"{x[0]}_{x[1]}" if isinstance(x, tuple) else x)
                # Rename columns to match expected
                col_mapping = {}
                for col in change_df.columns:
                    if col.startswith('Code'):
                        col_mapping[col] = 'Code'
                    elif 'Local (%)_' in col:
                        date_part = col.replace('Local (%)_', '')
                        if str(prev) in date_part:
                            col_mapping[col] = f'Local_{prev}'
                        elif str(latest) in date_part:
                            col_mapping[col] = f'Local_{latest}'
                    elif 'Foreign (%)_' in col:
                        date_part = col.replace('Foreign (%)_', '')
                        if str(prev) in date_part:
                            col_mapping[col] = f'Foreign_{prev}'
                        elif str(latest) in date_part:
                            col_mapping[col] = f'Foreign_{latest}'
                change_df = change_df.rename(columns=col_mapping)
                if f'Local_{latest}' in change_df.columns and f'Local_{prev}' in change_df.columns:
                    change_df[f'Local_Change'] = change_df[f'Local_{latest}'] - change_df[f'Local_{prev}']
                if f'Foreign_{latest}' in change_df.columns and f'Foreign_{prev}' in change_df.columns:
                    change_df[f'Foreign_Change'] = change_df[f'Foreign_{latest}'] - change_df[f'Foreign_{prev}']
                change_df = change_df.sort_values('Local_Change', ascending=False)
                cols_to_show = ['Code']
                if f'Local_{prev}' in change_df.columns:
                    cols_to_show.append(f'Local_{prev}')
                if f'Local_{latest}' in change_df.columns:
                    cols_to_show.append(f'Local_{latest}')
                if 'Local_Change' in change_df.columns:
                    cols_to_show.append('Local_Change')
                if f'Foreign_{prev}' in change_df.columns:
                    cols_to_show.append(f'Foreign_{prev}')
                if f'Foreign_{latest}' in change_df.columns:
                    cols_to_show.append(f'Foreign_{latest}')
                if 'Foreign_Change' in change_df.columns:
                    cols_to_show.append('Foreign_Change')
                st.dataframe(change_df[cols_to_show], width="stretch")

                # Top changes
                st.subheader("Saham dengan Perubahan Terbesar (Lokal)")
                top_local = change_df.nlargest(10, 'Local_Change')
                
                # Add investor types info
                latest_balance = balance_df[balance_df['Date'].dt.to_period('M') == latest]
                def get_top_investor_types(code, category='Local'):
                    stock_data = latest_balance[latest_balance['Code'] == code]
                    if stock_data.empty:
                        return "N/A"
                    investor_cols = [col for col in stock_data.columns if col.startswith(f'{category} ') and col != f'{category} Total']
                    totals = {}
                    for col in investor_cols:
                        total = stock_data[col].sum()
                        if total > 0:
                            code_type = col.replace(f'{category} ', '')
                            name = investor_mapping.get(code_type, code_type)
                            totals[name] = total
                    if not totals:
                        return "N/A"
                    # Top 3
                    top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:3]
                    return ", ".join([f"{name}: {val:,.0f}" for name, val in top])
                
                top_local['Top Local Investor Types'] = top_local['Code'].apply(lambda x: get_top_investor_types(x, 'Local'))
                
                fig_top_local = px.bar(
                    top_local,
                    x='Code',
                    y='Local_Change',
                    title="Top 10 Saham dengan Peningkatan Kepemilikan Lokal Terbesar",
                    color='Local_Change',
                    hover_data=['Top Local Investor Types']
                )
                st.plotly_chart(fig_top_local, width="stretch")

                st.subheader("Saham dengan Perubahan Terbesar (Asing)")
                top_foreign = change_df.nlargest(10, 'Foreign_Change')
                top_foreign['Top Foreign Investor Types'] = top_foreign['Code'].apply(lambda x: get_top_investor_types(x, 'Foreign'))
                
                fig_top_foreign = px.bar(
                    top_foreign,
                    x='Code',
                    y='Foreign_Change',
                    title="Top 10 Saham dengan Peningkatan Kepemilikan Asing Terbesar",
                    color='Foreign_Change',
                    hover_data=['Top Foreign Investor Types']
                )
                st.plotly_chart(fig_top_foreign, width="stretch")

        # Pie chart for investor types per stock
        st.subheader("Breakdown Tipe Investor per Saham")
        if change_df.empty or latest is None:
            st.info("Tidak ada data perubahan yang tersedia untuk menampilkan breakdown tipe investor.")
            return
        pie_stock_category = st.selectbox("Pilih Kategori Saham:", ["Local Top Changes", "Foreign Top Changes"], key="pie_stock_category")
        
        if pie_stock_category == "Local Top Changes":
            top_stocks = change_df.nlargest(10, 'Local_Change')['Code'].tolist()
            category = "Local"
        else:
            top_stocks = change_df.nlargest(10, 'Foreign_Change')['Code'].tolist()
            category = "Foreign"
        
        selected_stock = st.selectbox("Pilih Kode Saham:", top_stocks, key="selected_stock")
        
        # Get data for selected stock from latest balance
        latest_balance = balance_df[balance_df['Date'].dt.to_period('M') == latest]
        stock_data = latest_balance[latest_balance['Code'] == selected_stock]
        
        if not stock_data.empty:
            investor_cols = [col for col in stock_data.columns if col.startswith(f'{category} ') and col != f'{category} Total']
            investor_data = []
            for col in investor_cols:
                total = stock_data[col].sum()
                if total > 0:
                    code_type = col.replace(f'{category} ', '')
                    name = investor_mapping.get(code_type, code_type)
                    investor_data.append({'Type': name, 'Total': total})
            
            if investor_data:
                investor_df = pd.DataFrame(investor_data)
                fig_pie_investors = px.pie(
                    investor_df,
                    names='Type',
                    values='Total',
                    title=f"Breakdown Tipe Investor {category} untuk Saham {selected_stock} (Bulan Terakhir)"
                )
                st.plotly_chart(fig_pie_investors, width="stretch")
            else:
                st.info(f"Tidak ada data investor untuk saham {selected_stock}.")
        else:
            st.info(f"Data untuk saham {selected_stock} tidak ditemukan.")