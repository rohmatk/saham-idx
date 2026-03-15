import streamlit as st
from app.parser_pdf import parse_pdf_to_dataframe
from app.db import replace_snapshot, clear_cache

def upload_section():
    st.subheader("Upload PDF ke Database")

    uploaded_file = st.file_uploader(
        "Upload PDF Pemegang Saham",
        type=["pdf"],
        help="Upload file PDF daftar pemegang saham di atas 1%"
    )

    if uploaded_file is None:
        return

    if st.button("Proses PDF"):
        with st.spinner("Membaca PDF dan parsing data..."):
            df = parse_pdf_to_dataframe(uploaded_file, uploaded_file.name)

        if df.empty:
            st.error("Tidak ada data yang berhasil diparsing dari PDF.")
            return

        st.success(f"Berhasil parsing {len(df):,} baris.")
        st.dataframe(df.head(50), width="stretch")

        snapshot_date = df["snapshot_date"].dropna().iloc[0] if not df["snapshot_date"].dropna().empty else None

        if st.button("Simpan / Update ke Database"):
            with st.spinner("Menyimpan ke PostgreSQL..."):
                replace_snapshot(df, uploaded_file.name, snapshot_date)
                clear_cache()

            st.success("Data berhasil di-update ke database.")