# scores_loading.py
from __future__ import annotations

import io
import time
import logging
from urllib.parse import quote
import pandas as pd
import requests
import streamlit as st

# --- Your sheet config (defaults to the one you shared) ---
DEFAULT_SHEET_ID = "1BRb8p3Rq0VpFCLSwL4eS9tSgXBo9hSWzfW_J_7W36NQ"
# Change this to the actual tab name if it's not "Scores" or "Sheet1"
TAB_CANDIDATES = [
    st.secrets.get("SCORES_TAB", "Scores"),
    "scores", "SCORES", "Sheet1",
]

_HEADERS = {
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "User-Agent": "Mozilla/5.0 (compatible; tutor-dashboard/1.0; +streamlit)",
}

def _csv_url(sheet_id: str, tab_name: str) -> str:
    # gviz endpoint returns just the CSV of a named tab
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(tab_name)}"

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_csv(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=12, headers=_HEADERS)
    resp.raise_for_status()
    txt = resp.text
    if "<html" in txt[:512].lower():
        raise ValueError(
            "Expected CSV but received HTML. Ensure the sheet/tab is shared: "
            "Anyone with the link (Viewer), or publish the tab."
        )
    return pd.read_csv(io.StringIO(txt))

def load_scores(*, version: int | None = None) -> pd.DataFrame:
    """Load the raw scores sheet and normalize column names/types."""
    sheet_id = st.secrets.get("SCORES_SHEET_ID", DEFAULT_SHEET_ID)
    minute_buster = int(time.time() // 60)
    v = version or 0

    last_err = None
    df = pd.DataFrame()
    for tab in TAB_CANDIDATES:
        try:
            base = _csv_url(sheet_id, tab)
            url = f"{base}&cb={minute_buster}&v={v}"
            df = _fetch_csv(url)
            if not df.empty:
                break
        except Exception as e:
            last_err = e
            continue

    if df.empty and last_err:
        logging.exception("Failed to load scores from Google Sheet: %s", last_err)
        return pd.DataFrame()

    # --- Normalize expected columns ---
    # incoming headers: studentcode, name, assignment, score, comments, date, level, link
    cols = {c.lower().strip(): c for c in df.columns}

    def pick(name: str) -> str | None:
        return cols.get(name)

    # Rename to canonical
    ren = {}
    if pick("studentcode"): ren[pick("studentcode")] = "StudentCode"
    if pick("name"):        ren[pick("name")]        = "Name"
    if pick("assignment"):  ren[pick("assignment")]  = "Assignment"
    if pick("score"):       ren[pick("score")]       = "Score"
    if pick("comments"):    ren[pick("comments")]    = "Comments"
    if pick("date"):        ren[pick("date")]        = "Date"
    if pick("level"):       ren[pick("level")]       = "Level"
    if pick("link"):        ren[pick("link")]        = "Link"
    df = df.rename(columns=ren)

    # Ensure required columns exist
    for col in ["StudentCode", "Name", "Assignment", "Score", "Date", "Level"]:
        if col not in df.columns:
            df[col] = pd.NA

    # Types / cleanup
    df["StudentCode"] = df["StudentCode"].astype(str).str.strip().str.lower()
    df["Name"]        = df["Name"].astype(str).str.strip()
    df["Assignment"]  = df["Assignment"].astype(str).str.strip()
    df["Score"]       = pd.to_numeric(df["Score"], errors="coerce").fillna(0).astype(float)
    df["Level"]       = df["Level"].astype(str).str.upper().str.strip()
    df["Date"]        = pd.to_datetime(df["Date"], errors="coerce")

    # Keep sane rows only
    df = df[df["StudentCode"].notna() & (df["StudentCode"].str.len() > 0)]
    df = df[df["Assignment"].notna() & (df["Assignment"].str.len() > 0)]

    return df

def clear_scores_cache():
    try:
        _fetch_csv.clear()
    except Exception:
        pass
