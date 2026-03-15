import csv
import io
import re
from functools import lru_cache
from pathlib import Path

import pdfplumber
import pandas as pd

HEADER = [
    "DATE",
    "SHARE_CODE",
    "ISSUER_NAME",
    "INVESTOR_NAME",
    "INVESTOR_TYPE",
    "LOCAL_FOREIGN",
    "NATIONALITY",
    "DOMICILE",
    "HOLDINGS_SCRIPLESS",
    "HOLDINGS_SCRIP",
    "TOTAL_HOLDING_SHARES",
    "PERCENTAGE",
]

TICKER_MAP_PATH = Path(__file__).resolve().parents[1] / "data" / "ticker_map.csv"


def _load_ticker_map():
    """Load mapping from issuer_name -> share_code from CSV."""

    if not TICKER_MAP_PATH.exists():
        return {}

    mapping = {}
    with open(TICKER_MAP_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            issuer = row.get("ISSUER_NAME")
            code = row.get("SHARE_CODE")
            if not issuer or not code:
                continue
            mapping[issuer.strip().upper()] = code.strip().upper()
    return mapping


@lru_cache(maxsize=1)
def get_ticker_map():
    return _load_ticker_map()

def parse_stock_summary(file_path):
    df = pd.read_csv(file_path, sep='|', dtype=str, encoding='latin1')
    df.columns = df.columns.str.strip()
    df['Date'] = pd.to_datetime(df['Date'], format='%d-%b-%Y', errors='coerce')
    df['Local (%)'] = pd.to_numeric(df['Local (%)'], errors='coerce')
    df['Foreign (%)'] = pd.to_numeric(df['Foreign (%)'], errors='coerce')
    df['Total (%)'] = pd.to_numeric(df['Total (%)'], errors='coerce')
    df['Closing Price'] = pd.to_numeric(df['Closing Price'], errors='coerce')
    df['Num. of Sec'] = pd.to_numeric(df['Num. of Sec'], errors='coerce')
    df['Total Scripless'] = pd.to_numeric(df['Total Scripless'], errors='coerce')
    return df

INVESTOR_TYPE_SET = {"CP", "ID", "IS", "IB", "MF", "OT", "PF", "SC"}
LOCAL_FOREIGN_SET = {"D", "F"}

DATE_PATTERN = re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$")
NUMERIC_PATTERN = re.compile(r"^[\d\.]+,\d+$|^[\d\.]+$|^0$")

def clean_bigint(val):
    if val is None:
        return None
    val = str(val).strip()
    if not val or val == "0":
        return 0
    return int(val.replace(".", ""))

def clean_decimal(val):
    if val is None:
        return None
    val = str(val).strip()
    if not val:
        return None
    return float(val.replace(".", "").replace(",", "."))

def normalize_text_line(line: str) -> str:
    line = line.replace("\xa0", " ")
    line = re.sub(r"\s+", " ", line).strip()
    return line

def is_disclaimer_line(line: str) -> bool:
    lower = line.lower()
    return (
        lower.startswith("*penafian")
        or lower.startswith("*disclaimer")
        or lower.startswith("1. sumber data")
        or lower.startswith("1. scripless share")
        or lower.startswith("2. pada c-best")
        or lower.startswith("2. within c-best")
        or lower.startswith("3. pada sistem ebae")
        or lower.startswith("3. within the ebae")
        or lower.startswith("4. dalam hal terdapat")
        or lower.startswith("4. in instances where")
        or lower.startswith("5. persentase atas saham")
        or lower.startswith("5. the percentage of")
    )

def is_header_line(line: str) -> bool:
    return line.startswith("DATE SHARE_CODE ISSUER_NAME INVESTOR_NAME")

def line_looks_like_data(line: str) -> bool:
    parts = line.split()
    return len(parts) > 8 and DATE_PATTERN.match(parts[0]) is not None

def parse_line(line: str):
    """
    Format target:
    DATE SHARE_CODE ISSUER_NAME INVESTOR_NAME INVESTOR_TYPE LOCAL_FOREIGN
    NATIONALITY DOMICILE HOLDINGS_SCRIPLESS HOLDINGS_SCRIP TOTAL_HOLDING_SHARES PERCENTAGE

    Strategi:
    - ambil 4 token terakhir = angka + percentage
    - cari investor_type dari belakang
    - cari local_foreign setelah investor_type
    - sisanya dipecah antara issuer_name dan investor_name
    """
    parts = line.split()

    if len(parts) < 12:
        return None

    # Extract snapshot_date if present anywhere in the line
    snapshot_date = None
    for i, tok in enumerate(parts):
        if DATE_PATTERN.match(tok):
            snapshot_date = tok
            parts.pop(i)
            break

    # Remove optional leading row number (e.g. "441")
    if parts and parts[0].isdigit():
        parts = parts[1:]

    # Share code is expected to be the first token after optional row number.
    share_code = parts[0].upper().strip() if parts else ""

    percentage = parts[-1]
    total_holding_shares = parts[-2]
    holdings_scrip = parts[-3]
    holdings_scripless = parts[-4]

    if not NUMERIC_PATTERN.match(percentage):
        return None

    middle = parts[1:-4]

    # cari investor_type dari belakang
    investor_type_idx = None
    for i in range(len(middle) - 1, -1, -1):
        if middle[i] in INVESTOR_TYPE_SET:
            investor_type_idx = i
            break

    if investor_type_idx is None:
        return None

    investor_type = middle[investor_type_idx]

    local_foreign = None
    lf_idx = investor_type_idx + 1
    if lf_idx < len(middle) and middle[lf_idx] in LOCAL_FOREIGN_SET:
        local_foreign = middle[lf_idx]
        meta_start = lf_idx + 1
    else:
        meta_start = investor_type_idx + 1

    trailing_meta = middle[meta_start:]
    nationality = None
    domicile = None

    # heuristik: token terakhir biasanya domicile, sisanya nationality
    if trailing_meta:
        domicile = trailing_meta[-1]
        if len(trailing_meta) > 1:
            nationality = " ".join(trailing_meta[:-1])

    left_side = middle[:investor_type_idx]

    # pisah issuer_name dan investor_name:
    # issuer biasanya berakhir dengan Tbk
    tbk_idx = None
    for i, tok in enumerate(left_side):
        if tok.lower() == "tbk":
            tbk_idx = i
            break

    if tbk_idx is None:
        return None

    issuer_name = " ".join(left_side[: tbk_idx + 1]).strip()
    investor_name = " ".join(left_side[tbk_idx + 1 :]).strip()

    if not issuer_name or not investor_name:
        return None

    share_code = (share_code or "").strip().upper()

    # If share_code isn't a valid ticker, try to find it from issuer_name.
    if not re.fullmatch(r"[A-Z0-9]{1,6}", share_code):
        share_code = get_ticker_map().get(issuer_name.strip().upper(), share_code)

    return {
        "snapshot_date": pd.to_datetime(snapshot_date, format="%d-%b-%Y", errors="coerce").date() if snapshot_date else None,
        "share_code": share_code,
        "issuer_name": issuer_name,
        "investor_name": investor_name,
        "investor_type": investor_type,
        "local_foreign": local_foreign,
        "nationality": nationality,
        "domicile": domicile,
        "holdings_scripless": clean_bigint(holdings_scripless),
        "holdings_scrip": clean_bigint(holdings_scrip),
        "total_holding_shares": clean_bigint(total_holding_shares),
        "percentage": clean_decimal(percentage),
    }

def parse_pdf_to_dataframe(uploaded_file, source_file_name: str) -> pd.DataFrame:
    rows = []

    with pdfplumber.open(io.BytesIO(uploaded_file.getvalue())) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.split("\n"):
                line = normalize_text_line(raw_line)

                if not line:
                    continue
                if is_header_line(line):
                    continue
                if is_disclaimer_line(line):
                    continue
                if not line_looks_like_data(line):
                    continue

                parsed = parse_line(line)
                if parsed:
                    parsed["source_file"] = source_file_name
                    rows.append(parsed)

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # bersihkan text kosong
    text_cols = [
        "share_code",
        "issuer_name",
        "investor_name",
        "investor_type",
        "local_foreign",
        "nationality",
        "domicile",
        "source_file",
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].mask(df[col].isin(["None", "nan", ""]), None)

    return df