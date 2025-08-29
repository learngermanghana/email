# ==== IMPORTS ====
import os
import re
import base64
import requests
import tempfile
import textwrap
import urllib.parse
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st
from fpdf import FPDF
import qrcode
from PIL import Image  # For logo image handling
from io import BytesIO



from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

# ==== CONSTANTS ====
SCHOOL_NAME = "Learn Language Education Academy"
SCHOOL_WEBSITE = "https://www.learngermanghana.com"
SCHOOL_PHONE = "0205706589"
SCHOOL_ADDRESS = "Accra, Ghana"
BUSINESS_REG = "BN173410224"
TUTOR_NAME = "Felix Asadu"
TUTOR_TITLE = "Director"

# --- Sheet IDs & URLs ---
STUDENTS_SHEET_ID = "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U"
REF_ANSWERS_SHEET_ID = "1CtNlidMfmE836NBh5FmEF5tls9sLmMmkkhewMTQjkBo"

STUDENTS_CSV_URL = f"https://docs.google.com/spreadsheets/d/{STUDENTS_SHEET_ID}/export?format=csv"
REF_ANSWERS_CSV_URL = f"https://docs.google.com/spreadsheets/d/{REF_ANSWERS_SHEET_ID}/export?format=csv"

# ==== STREAMLIT SECRETS ====
SENDER_EMAIL = st.secrets["general"].get("sender_email", "Learngermanghana@gmail.com")
SENDGRID_KEY = st.secrets["general"].get("sendgrid_api_key", "")



# ==== SIMPLE PASSWORD GATE ====
def password_gate(correct_password: str, key="app_pw"):
    """Show a password input. Returns True if correct, else stops the app."""
    if "pw_ok" not in st.session_state:
        st.session_state["pw_ok"] = False
    if not st.session_state["pw_ok"]:
        st.title("🔒 Enter Password")
        with st.form("pw_form"):
            pw = st.text_input("Password", type="password", key=key)
            submit_pw = st.form_submit_button("Submit")
        if submit_pw:
            if pw == correct_password:
                st.session_state["pw_ok"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()

# ==== PUT THIS NEAR THE VERY TOP OF YOUR MAIN SCRIPT! ====
password_gate("Xenomexpress7727/")  # Change to your desired password!

# ==== UNIVERSAL HELPERS ====

def safe_pdf(text):
    """Ensure all strings are PDF-safe (latin-1 only)."""
    return "".join(c if ord(c) < 256 else "?" for c in str(text or ""))

def col_lookup(df: pd.DataFrame, name: str) -> str:
    """Find the actual column name for a logical key, case/space/underscore-insensitive."""
    key = name.lower().replace(" ", "").replace("_", "")
    for c in df.columns:
        if c.lower().replace(" ", "").replace("_", "") == key:
            return c
    raise KeyError(f"Column '{name}' not found in DataFrame")

def make_qr_code(url):
    """Generate QR code image file for a given URL, return temp filename."""
    qr = qrcode.QRCode(box_size=3, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(tmp.name)
    return tmp.name

def clean_phone(phone):
    """Clean and format Ghana phone numbers for WhatsApp (233XXXXXXXXX)."""
    phone = str(phone).replace(" ", "").replace("-", "")
    if phone.startswith("+233"):
        return phone[1:]
    if phone.startswith("233"):
        return phone
    if phone.startswith("0") and len(phone) == 10:
        return "233" + phone[1:]
    return phone  # fallback

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize all DataFrame columns to snake_case (lower, underscores)."""
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df

def strip_leading_number(text):
    """Remove leading digits, dots, spaces (for question/answer lists)."""
    return re.sub(r"^\s*\d+[\.\)]?\s*", "", text).strip()

# ==== EMAIL SENDER ====

def send_email_report(pdf_bytes: bytes, to_email: str, subject: str, html_content: str, extra_attachments=None):
    """
    Send an email with (optional) PDF and any extra attachments.
    extra_attachments: list of tuples (bytes, filename, mimetype)
    """
    msg = Mail(
        from_email=SENDER_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )
    # Attach PDF if provided
    if pdf_bytes:
        pdf_attach = Attachment(
            FileContent(base64.b64encode(pdf_bytes).decode()),
            FileName("report.pdf"),
            FileType("application/pdf"),
            Disposition("attachment")
        )
        msg.add_attachment(pdf_attach)
    # Attach any extra files
    if extra_attachments:
        for bytes_data, filename, mimetype in extra_attachments:
            file_attach = Attachment(
                FileContent(base64.b64encode(bytes_data).decode()),
                FileName(filename),
                FileType(mimetype or "application/octet-stream"),
                Disposition("attachment")
            )
            msg.add_attachment(file_attach)
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        sg.send(msg)
        return True
    except Exception as e:
        st.error(f"Email send failed: {e}")
        return False



# ==== AGREEMENT TEMPLATE ====
if "agreement_template" not in st.session_state:
    st.session_state["agreement_template"] = """
PAYMENT AGREEMENT

This Payment Agreement is entered into on [DATE] for [CLASS] students of Learn Language Education Academy and Felix Asadu ("Teacher").

Terms of Payment:
1. Payment Amount: The student agrees to pay the teacher a total of [AMOUNT] cedis for the course.
2. Payment Schedule: The payment can be made in full or in two installments: GHS [FIRST_INSTALLMENT] for the first installment, and the remaining balance for the second installment after one month of payment. 
3. Late Payments: In the event of late payment, the school may revoke access to all learning platforms. No refund will be made.
4. Refunds: Once a deposit is made and a receipt is issued, no refunds will be provided.

Cancellation and Refund Policy:
1. If the teacher cancels a lesson, it will be rescheduled.

Miscellaneous Terms:
1. Attendance: The student agrees to attend lessons punctually.
2. Communication: Both parties agree to communicate changes promptly.
3. Termination: Either party may terminate this Agreement with written notice if the other party breaches any material term.

Signatures:
[STUDENT_NAME]
Date: [DATE]
Asadu Felix
"""

# ==== END OF STAGE 1 ====

# ==== DATA LOADING HELPERS & CACHING ====

@st.cache_data(ttl=300, show_spinner="Loading student data...")
def load_students():
    df = pd.read_csv(STUDENTS_CSV_URL, dtype=str)
    df = normalize_columns(df)
    # Standardize any known column name variants
    if "student_code" in df.columns:
        df = df.rename(columns={"student_code": "studentcode"})
    return df

@st.cache_data(ttl=300, show_spinner="Loading reference answers...")
def load_ref_answers():
    df = pd.read_csv(REF_ANSWERS_CSV_URL, dtype=str)
    df = normalize_columns(df)
    if "assignment" not in df.columns:
        raise Exception("No 'assignment' column found in reference answers sheet.")
    return df

# Optional: SQLite or other local storage helpers here (for local persistence if desired)
# @st.cache_resource
# def init_sqlite_connection():
#     import sqlite3
#     conn = sqlite3.connect('students_scores.db', check_same_thread=False)
#     # ...table creation logic
#     return conn

# ==== SESSION STATE INITIALIZATION ====
if "tabs_loaded" not in st.session_state:
    st.session_state["tabs_loaded"] = False

# ==== LOAD MAIN DATAFRAMES ONCE ====
df_students = load_students()
df_ref_answers = load_ref_answers()

# ==== UNIVERSAL VARIABLES (for later use) ====
LEVELS = sorted(df_students["level"].dropna().unique().tolist()) if "level" in df_students.columns else []
STUDENT_CODES = df_students["studentcode"].dropna().unique().tolist() if "studentcode" in df_students.columns else []

# ==== END OF STAGE 2 ====

# === UPDATE YOUR TABS LIST SO THE FIRST LABEL IS '🏆 Leaderboard' ===
tabs = st.tabs([
    "🏆 Leaderboard",           # 0  (replaces "📝 📘 PENDING ")
    "👩‍🎓 All Students",        # 1
    "📲 Reminders",             # 2
    "📄 Contract",              # 3
    "📧 Send Email",            # 4
    "📧 Course",                # 5
    "📝 Marking"                # 6
])


# ==== TAB 0: LEADERBOARD (A1–C1) ====
with tabs[0]:
    st.title("🏆 Leaderboard (A1–C1)")

    # ---------- Loaders ----------
    @st.cache_data(ttl=300, show_spinner="Loading assignment scores…")
    def load_assignment_scores():
        """
        Reads the assignment scores used by the student dashboard leaderboard.
        Expected columns (case-insensitive; spaces allowed): studentcode, name, level, assignment, score, date.
        """
        SHEET_ID = "1BRb8p3Rq0VpFCLSwL4eS9tSgXBo9hSWzfW_J_7W36NQ"  # same as student app
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet1"
        try:
            df = pd.read_csv(url, dtype=str)
        except Exception as e:
            st.error(f"Could not load assignment scores: {e}")
            return pd.DataFrame(columns=["studentcode","name","level","assignment","score","date"])

        # Normalize
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        for c in df.columns:
            df[c] = df[c].astype(str).str.strip()  # <-- FIX: use .str.strip()

        # Soft rename common variants
        rename_map = {
            "student_code": "studentcode",
            "student": "studentcode",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        # Keep only useful columns if present
        keep = [c for c in ["studentcode","name","level","assignment","score","date"] if c in df.columns]
        return df[keep] if keep else df

    # Fallback students loader if df_students isn't already in your script's scope
    def _ensure_students_df():
        # If your script already loaded df_students via load_students(), reuse it
        if "df_students" in globals() and isinstance(globals()["df_students"], pd.DataFrame) and not globals()["df_students"].empty:
            return globals()["df_students"]

        # Else try your existing loader if present
        if "load_students" in globals():
            try:
                return globals()["load_students"]()
            except Exception:
                pass

        # Final fallback: fetch the main students sheet directly
        try:
            STUDENTS_SHEET_ID = "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U"
            url = f"https://docs.google.com/spreadsheets/d/{STUDENTS_SHEET_ID}/export?format=csv"
            df = pd.read_csv(url, dtype=str)
            df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
            if "student_code" in df.columns:
                df = df.rename(columns={"student_code": "studentcode"})
            return df
        except Exception:
            return pd.DataFrame(columns=["studentcode","name","level"])

    # ---------- Helpers ----------
    def _norm_level(x: str) -> str:
        return (x or "").upper().replace(" ", "").strip()

    def build_leaderboard(df_assign: pd.DataFrame, df_students: pd.DataFrame, level: str, min_completed: int = 3) -> pd.DataFrame:
        """
        Build a leaderboard for one CEFR level.
        Ranking: total_score (desc) then completed unique assignments (desc).
        Only include students with >= min_completed unique assignments.
        """
        empty_cols = ["Rank","studentcode","name","level","completed","total_score","avg_score","last_submission"]
        if df_assign is None or df_assign.empty:
            return pd.DataFrame(columns=empty_cols)

        df = df_assign.copy()

        # Ensure required cols exist
        for col in ["studentcode","assignment","score"]:
            if col not in df.columns:
                df[col] = ""

        # If 'level' missing/empty in assignments, merge from students list
        need_merge = (
            "level" not in df.columns
            or df["level"].isna().all()
            or (df["level"].astype(str).str.len() == 0).all()
        )
        if need_merge and not df_students.empty:
            s = df_students.copy()
            s.columns = s.columns.str.strip().str.lower().str.replace(" ", "_")
            # Keep only the needed columns
            keep = [c for c in ["studentcode","level","name"] if c in s.columns]
            if keep:
                df = df.merge(s[keep], on="studentcode", how="left", suffixes=("","_from_students"))
                # Prefer assignment-provided values if present; otherwise take merged ones
                if "name_from_students" in df.columns:
                    df["name"] = df["name"].where(df["name"].astype(str).str.len() > 0, df["name_from_students"]).fillna("")
                if "level_from_students" in df.columns:
                    df["level"] = df["level"].where(df["level"].astype(str).str.len() > 0, df["level_from_students"]).fillna("")

        # Normalize
        df["studentcode"] = df["studentcode"].astype(str).str.strip().str.lower()
        if "name" in df.columns:
            df["name"] = df["name"].astype(str).str.strip()
        if "level" in df.columns:
            df["level"] = df["level"].astype(str).map(_norm_level)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # Score numeric
        df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)

        # Filter level
        lvl = _norm_level(level)
        if "level" not in df.columns:
            return pd.DataFrame(columns=empty_cols)
        df = df[df["level"] == lvl]
        if df.empty:
            return pd.DataFrame(columns=empty_cols)

        # Aggregate
        g = (
            df.groupby(["studentcode","name"], dropna=False)
              .agg(
                  total_score=("score","sum"),
                  completed=("assignment","nunique"),
                  avg_score=("score","mean"),
                  last_submission=("date","max") if "date" in df.columns else ("score","size")
              )
              .reset_index()
        )

        # Minimum unique assignments
        g = g[g["completed"] >= int(min_completed)]
        if g.empty:
            return pd.DataFrame(columns=empty_cols)

        # Sort & rank
        g = g.sort_values(["total_score","completed"], ascending=[False, False]).reset_index(drop=True)
        g.insert(0, "Rank", g.index + 1)
        g["level"] = lvl

        # Friendly formatting
        if "last_submission" in g.columns and pd.api.types.is_datetime64_any_dtype(g["last_submission"]):
            g["last_submission"] = g["last_submission"].dt.strftime("%Y-%m-%d")
        g["avg_score"] = g["avg_score"].round(2)
        g["total_score"] = g["total_score"].round(2)

        cols = ["Rank","studentcode","name","level","completed","total_score","avg_score","last_submission"]
        for c in cols:
            if c not in g.columns:
                g[c] = ""
        return g[cols]

    # ---------- Data & Controls ----------
    df_assign = load_assignment_scores()
    df_students_safe = _ensure_students_df()

    st.markdown(
        "Ranking per level uses **Total Score** (sum of scores). "
        "Tie-breaker is **Completed** (count of **unique** assignments). "
        "Students need a minimum number of unique assignments to qualify."
    )

    ca, cb, cc = st.columns([1,1,2])
    with ca:
        min_required = st.number_input("Minimum unique assignments", min_value=1, value=3, step=1)
    with cb:
        rows_to_show = st.number_input("Rows to show per table", min_value=5, value=20, step=5)
    with cc:
        st.caption("Tip: Download each table as CSV using the buttons below.")

    # ---------- Sub-tabs for each level ----------
    level_list = ["A1","A2","B1","B2","C1"]
    sub_tabs = st.tabs(level_list)

    for lvl, pane in zip(level_list, sub_tabs):
        with pane:
            lb = build_leaderboard(df_assign, df_students_safe, lvl, min_required)
            if lb.empty:
                st.info(f"No qualifying records for {lvl} yet (need ≥ {min_required} unique assignments).")
            else:
                # Avoid older Streamlit 'hide_index' kw—just show Rank as index.
                st.dataframe(lb.head(int(rows_to_show)).set_index("Rank"), use_container_width=True)
                st.download_button(
                    f"⬇️ Download {lvl} leaderboard (CSV)",
                    lb.to_csv(index=False),
                    file_name=f"leaderboard_{lvl.lower()}.csv",
                    mime="text/csv",
                    key=f"dl_{lvl}"
                )




# ==== TAB 1: ALL STUDENTS ====
with tabs[1]:
    st.title("👩‍🎓 All Students")

    # --- Optional: Search/Filter ---
    if "all_students_search" not in st.session_state:
        st.session_state["all_students_search"] = ""
    with st.form("all_students_search_form"):
        search_input = st.text_input(
            "🔍 Search students by name, code, or email...",
            value=st.session_state["all_students_search"],
        )
        search_submit = st.form_submit_button("Search")
    if search_submit:
        st.session_state["all_students_search"] = search_input
    search = st.session_state["all_students_search"]

    if search:
        search_lc = search.lower().strip()
        filt = df_students[
            df_students.apply(lambda row: search_lc in str(row).lower(), axis=1)
        ]
    else:
        filt = df_students.copy()

    # --- Add "Days Since Expiry" Column ---
    if "contractend" in filt.columns:
        filt = filt.copy()
        filt["contractend_dt"] = pd.to_datetime(filt["contractend"], errors="coerce")
        today = pd.Timestamp.today().normalize()
        filt["days_since_expiry"] = (today - filt["contractend_dt"]).dt.days
    else:
        filt["days_since_expiry"] = None

    # --- Show Student Table ---
    st.subheader("All Students")
    st.dataframe(filt, use_container_width=True)

    st.download_button(
        "⬇️ Download All Students CSV",
        filt.to_csv(index=False),
        file_name="all_students.csv"
    )

    # --- Display Expired Contracts (automatically) ---
    expired_filt = filt[filt["days_since_expiry"] > 0]
    if not expired_filt.empty:
        st.markdown("## ⏳ Students with Expired Contracts")
        st.dataframe(expired_filt, use_container_width=True)
        st.download_button(
            "⬇️ Download Expired Students CSV",
            expired_filt.to_csv(index=False),
            file_name="expired_students.csv"
        )
    else:
        st.info("No expired contracts found.")


# ==== TAB 2: WHATSAPP REMINDERS ====
with tabs[2]:
    st.title("📲 WhatsApp Reminders for Debtors")

    # --- Use cached df_students loaded at the top ---
    df = df_students.copy()

    # --- Column Lookups ---
    name_col  = col_lookup(df, "name")
    code_col  = col_lookup(df, "studentcode")
    phone_col = col_lookup(df, "phone")
    bal_col   = col_lookup(df, "balance")
    paid_col  = col_lookup(df, "paid")
    lvl_col   = col_lookup(df, "level")
    cs_col    = col_lookup(df, "contractstart")

    # --- Clean Data Types ---
    df[bal_col] = pd.to_numeric(df[bal_col], errors="coerce").fillna(0)
    df[paid_col] = pd.to_numeric(df[paid_col], errors="coerce").fillna(0)
    df[cs_col] = pd.to_datetime(df[cs_col], errors="coerce")
    df[phone_col] = df[phone_col].astype(str).str.replace(r"[^\d+]", "", regex=True)

    # --- Calculate Due Date & Days Left ---
    df["due_date"] = df[cs_col] + pd.Timedelta(days=30)
    df["due_date_str"] = df["due_date"].dt.strftime("%d %b %Y")
    df["days_left"] = (df["due_date"] - pd.Timestamp.today()).dt.days

    # --- Financial Summary ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Students", len(df))
    m2.metric("Total Collected (GHS)", f"{df[paid_col].sum():,.2f}")
    m3.metric("Total Outstanding (GHS)", f"{df[bal_col].sum():,.2f}")

    st.markdown("---")

    # --- Filter/Search UI ---
    if "wa_show_all" not in st.session_state:
        st.session_state["wa_show_all"] = False
    if "wa_search" not in st.session_state:
        st.session_state["wa_search"] = ""
    if "wa_level" not in st.session_state:
        st.session_state["wa_level"] = "All"
    level_options = ["All"] + sorted(df[lvl_col].dropna().unique())
    with st.form("wa_filter_form"):
        show_all_input = st.checkbox(
            "Show all students (not just debtors)",
            value=st.session_state["wa_show_all"],
        )
        search_input = st.text_input(
            "Search by name, code, or phone",
            value=st.session_state["wa_search"],
        )
        selected_level_input = st.selectbox(
            "Filter by Level",
            level_options,
            index=level_options.index(st.session_state["wa_level"])
            if st.session_state["wa_level"] in level_options
            else 0,
        )
        filter_submit = st.form_submit_button("Apply Filters")
    if filter_submit:
        st.session_state["wa_show_all"] = show_all_input
        st.session_state["wa_search"] = search_input
        st.session_state["wa_level"] = selected_level_input
    show_all = st.session_state["wa_show_all"]
    search = st.session_state["wa_search"]
    selected_level = st.session_state["wa_level"]

    filt = df.copy()
    if not show_all:
        filt = filt[filt[bal_col] > 0]
    if search:
        mask1 = filt[name_col].str.contains(search, case=False, na=False)
        mask2 = filt[code_col].astype(str).str.contains(search, case=False, na=False)
        mask3 = filt[phone_col].str.contains(search, case=False, na=False)
        filt = filt[mask1 | mask2 | mask3]
    if selected_level != "All":
        filt = filt[filt[lvl_col] == selected_level]

    st.markdown("---")

    # --- Table Preview ---
    tbl = filt[[name_col, code_col, phone_col, lvl_col, bal_col, "due_date_str", "days_left"]].rename(columns={
        name_col: "Name", code_col: "Student Code", phone_col: "Phone",
        lvl_col: "Level", bal_col: "Balance (GHS)", "due_date_str": "Due Date", "days_left": "Days Left"
    })
    st.dataframe(tbl, use_container_width=True)

    # --- WhatsApp Message Template ---
    if "wa_template" not in st.session_state:
        st.session_state["wa_template"] = (
            "Hi {name}! Friendly reminder: your payment for the {level} class is due by {due}. {msg} Thank you!"
        )
    with st.form("wa_template_form"):
        wa_template_input = st.text_area(
            "Custom WhatsApp Message Template",
            value=st.session_state["wa_template"],
            help="You can use {name}, {level}, {due}, {bal}, {days}, {msg}",
        )
        template_submit = st.form_submit_button("Update Template")
    if template_submit:
        st.session_state["wa_template"] = wa_template_input
    wa_template = st.session_state["wa_template"]

    # --- WhatsApp Links Generation ---
    links = []
    for _, row in filt.iterrows():
        phone = clean_phone(row[phone_col])
        bal = f"GHS {row[bal_col]:,.2f}"
        due = row["due_date_str"]
        days = int(row["days_left"])
        if days >= 0:
            msg = f"You have {days} {'day' if days == 1 else 'days'} left to settle the {bal} balance."
        else:
            msg = f"Your payment is overdue by {abs(days)} {'day' if abs(days)==1 else 'days'}. Please settle as soon as possible."
        text = wa_template.format(
            name=row[name_col],
            level=row[lvl_col],
            due=due,
            bal=bal,
            days=days,
            msg=msg
        )
        link = f"https://wa.me/{phone}?text={urllib.parse.quote(text)}" if phone else ""
        links.append({
            "Name": row[name_col],
            "Student Code": row[code_col],
            "Level": row[lvl_col],
            "Balance (GHS)": bal,
            "Due Date": due,
            "Days Left": days,
            "Phone": phone,
            "WhatsApp Link": link
        })

    df_links = pd.DataFrame(links)
    st.markdown("---")
    st.dataframe(df_links[["Name", "Level", "Balance (GHS)", "Due Date", "Days Left", "WhatsApp Link"]], use_container_width=True)

    # --- List links for quick access ---
    st.markdown("### Send WhatsApp Reminders")
    for i, row in df_links.iterrows():
        if row["WhatsApp Link"]:
            st.markdown(f"- **{row['Name']}** ([Send WhatsApp]({row['WhatsApp Link']}))")

    st.download_button(
        "📁 Download Reminder Links CSV",
        df_links[["Name", "Student Code", "Phone", "Level", "Balance (GHS)", "Due Date", "Days Left", "WhatsApp Link"]].to_csv(index=False),
        file_name="debtor_whatsapp_links.csv"
    )


with tabs[3]:
    st.title("📄 Generate Contract & Receipt PDF for Any Student")

    google_csv = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    )
    df = pd.read_csv(google_csv)
    df = normalize_columns(df)

    if df.empty:
        st.warning("No student data available.")
        st.stop()

    def getcol(col): 
        return col_lookup(df, col)

    name_col    = getcol("name")
    start_col   = getcol("contractstart")
    end_col     = getcol("contractend")
    paid_col    = getcol("paid")
    bal_col     = getcol("balance")
    code_col    = getcol("studentcode")
    phone_col   = getcol("phone")
    level_col   = getcol("level")

    if "pdf_search_contract" not in st.session_state:
        st.session_state["pdf_search_contract"] = ""
    with st.form("pdf_search_contract_form"):
        search_input = st.text_input(
            "Search students by name, code, phone, or level:",
            value=st.session_state["pdf_search_contract"],
        )
        search_submit = st.form_submit_button("Search")
    if search_submit:
        st.session_state["pdf_search_contract"] = search_input
    search_val = st.session_state["pdf_search_contract"]
    filtered_df = df.copy()
    if search_val:
        sv = search_val.strip().lower()
        filtered_df = df[
            df[name_col].str.lower().str.contains(sv, na=False)
            | df[code_col].astype(str).str.lower().str.contains(sv, na=False)
            | df[phone_col].astype(str).str.lower().str.contains(sv, na=False)
            | df[level_col].astype(str).str.lower().str.contains(sv, na=False)
        ]
    student_names = filtered_df[name_col].tolist()
    if not student_names:
        st.warning("No students match your search.")
        st.stop()
    selected_name = st.selectbox("Select Student", student_names)
    row = filtered_df[filtered_df[name_col] == selected_name].iloc[0]

    default_paid    = float(row.get(paid_col, 0))
    default_balance = float(row.get(bal_col, 0))
    default_start = pd.to_datetime(row.get(start_col, ""), errors="coerce").date()
    if pd.isnull(default_start):
        default_start = date.today()
    default_end = pd.to_datetime(row.get(end_col, ""), errors="coerce").date()
    if pd.isnull(default_end):
        default_end = default_start + timedelta(days=30)

    st.subheader("Receipt Details")
    paid_input    = st.number_input("Amount Paid (GHS)", min_value=0.0, value=default_paid, step=1.0)
    balance_input = st.number_input("Balance Due (GHS)", min_value=0.0, value=default_balance, step=1.0)
    total_input   = paid_input + balance_input
    receipt_date  = st.date_input("Receipt Date", value=date.today())
    signature     = st.text_input("Signature Text", value="Felix Asadu", key="pdf_signature_contract")

    st.subheader("Contract Details")
    contract_start_input = st.date_input("Contract Start Date", value=default_start, key="pdf_contract_start")
    contract_end_input   = st.date_input("Contract End Date", value=default_end, key="pdf_contract_end")
    course_length        = (contract_end_input - contract_start_input).days

    logo_url = "https://drive.google.com/uc?export=download&id=1xLTtiCbEeHJjrASvFjBgfFuGrgVzg6wU"

    def sanitize_text(text):
        cleaned = "".join(c if ord(c) < 256 else "?" for c in str(text))
        return " ".join(cleaned.split())

    def break_long_words(line, max_len=40):
        tokens = line.split(" ")
        out = []
        for tok in tokens:
            while len(tok) > max_len:
                out.append(tok[:max_len])
                tok = tok[max_len:]
            out.append(tok)
        return " ".join(out)

    def safe_for_fpdf(line):
        txt = line.strip()
        if len(txt) < 2: return False
        if len(txt) == 1 and not txt.isalnum(): return False
        return True

    if st.button("Generate & Download PDF"):
        paid    = paid_input
        balance = balance_input
        total   = total_input

        pdf = FPDF()
        pdf.add_page()

        try:
            response = requests.get(logo_url)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGB")
                img_path = "/tmp/school_logo.png"
                img.save(img_path)
                pdf.image(img_path, x=10, y=8, w=33)
                pdf.ln(25)
            else:
                st.warning("Could not download logo image from the URL.")
                pdf.ln(2)
        except Exception as e:
            st.warning(f"Logo insertion failed: {e}")
            pdf.ln(2)

        status = "FULLY PAID" if balance == 0 else "INSTALLMENT PLAN"
        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 10, status, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        pdf.set_font("Arial", size=14)
        pdf.cell(0, 10, "Learn Language Education Academy Payment Receipt", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)

        pdf.set_font("Arial", size=12)
        for label, val in [
            ("Name", selected_name),
            ("Student Code", row.get(code_col, "")),
            ("Phone", row.get(phone_col, "")),
            ("Level", row.get(level_col, "")),
            ("Contract Start", contract_start_input),
            ("Contract End", contract_end_input),
            ("Amount Paid", f"GHS {paid:.2f}"),
            ("Balance Due", f"GHS {balance:.2f}"),
            ("Total Fee", f"GHS {total:.2f}"),
            ("Receipt Date", receipt_date)
        ]:
            text = f"{label}: {sanitize_text(val)}"
            pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)

        pdf.ln(15)
        pdf.set_font("Arial", size=14)
        pdf.cell(0, 10, "Learn Language Education Academy Student Contract", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Arial", size=12)
        pdf.ln(8)

        template = st.session_state.get("agreement_template", """
PAYMENT AGREEMENT

This Payment Agreement is entered into on [DATE] for [CLASS] students of Learn Language Education Academy and Felix Asadu ("Teacher").
...
""")
        filled = (
            template
            .replace("[STUDENT_NAME]",     selected_name)
            .replace("[DATE]",             str(receipt_date))
            .replace("[CLASS]",            row.get(level_col, ""))
            .replace("[AMOUNT]",           str(total))
            .replace("[FIRST_INSTALLMENT]", f"{paid:.2f}")
            .replace("[SECOND_INSTALLMENT]",f"{balance:.2f}")
            .replace("[SECOND_DUE_DATE]",  str(contract_end_input))
            .replace("[COURSE_LENGTH]",    f"{course_length} days")
        )

        for line in filled.split("\n"):
            safe    = sanitize_text(line)
            wrapped = break_long_words(safe, max_len=40)
            if safe_for_fpdf(wrapped):
                try:
                    pdf.multi_cell(0, 8, wrapped)
                except:
                    pass
        pdf.ln(10)
        pdf.cell(0, 8, f"Signed: {signature}", new_x="LMARGIN", new_y="NEXT")

        output_data = pdf.output(dest="S")
        if isinstance(output_data, str):
            pdf_bytes = output_data.encode("latin-1")
        else:
            pdf_bytes = bytes(output_data)

        st.download_button(
            "📄 Download PDF",
            data=pdf_bytes,
            file_name=f"{selected_name.replace(' ', '_')}_receipt_contract.pdf",
            mime="application/pdf"
        )
        st.success("✅ PDF generated and ready to download.")

with tabs[4]:

    # ---- Helper: Ensure all text in PDF is latin-1 safe ----
    def safe_pdf(text):
        if not text:
            return ""
        return "".join(c if ord(c) < 256 else "?" for c in str(text))

    # ---- Helper: QR Code generation ----
    def make_qr_code(url):
        import qrcode, tempfile
        qr_img = qrcode.make(url)
        qr_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        qr_img.save(qr_tmp)
        qr_tmp.close()
        return qr_tmp.name

    # Watermark image from Google Drive (direct download)
    watermark_drive_url = "https://drive.google.com/uc?export=download&id=1dEXHtaPBmvnX941GKK-DsTmj3szz2Z5A"

    st.title("📧 Send Email / Letter (Templates, Attachments, PDF, Watermark, QR)")
    st.subheader("Select Student")
    if "student_search" not in st.session_state:
        st.session_state["student_search"] = ""
    with st.form("student_search_form"):
        search_input = st.text_input(
            "Search students by name, code, or email",
            value=st.session_state["student_search"],
        )
        search_submit = st.form_submit_button("Search")
    if search_submit:
        st.session_state["student_search"] = search_input
    search_val = st.session_state["student_search"]
    if search_val:
        filtered_students = df_students[
            df_students["name"].str.contains(search_val, case=False, na=False)
            | df_students.get("studentcode", pd.Series(dtype=str))
                          .astype(str).str.contains(search_val, case=False, na=False)
            | df_students.get("email", pd.Series(dtype=str))
                          .astype(str).str.contains(search_val, case=False, na=False)
        ]
    else:
        filtered_students = df_students

    student_names = filtered_students["name"].dropna().unique().tolist()
    student_name = st.selectbox("Student Name", student_names, key="student_select")
    if not student_name:
        st.stop()

    student_row = filtered_students[filtered_students["name"] == student_name].iloc[0]
    student_level = student_row["level"]
    student_email = student_row.get("email", "")
    enrollment_start = pd.to_datetime(student_row.get("contractstart", date.today()), errors="coerce").date()
    enrollment_end   = pd.to_datetime(student_row.get("contractend",   date.today()), errors="coerce").date()
    payment       = float(student_row.get("paid", 0))
    balance       = float(student_row.get("balance", 0))
    payment_status = "Full Payment" if balance == 0 else "Installment Plan"
    student_code   = student_row.get("studentcode", "")
    student_link   = f"https://falowen.streamlit.app/?code={student_code}" if student_code else "https://falowen.streamlit.app/"

    # ---- 2. Message Type Selection ----
    st.subheader("Choose Message Type")
    msg_type = st.selectbox("Type", [
        "Custom Message",
        "Welcome Message",
        "Assignment Results",
        "Letter of Enrollment",
        "Outstanding Balance Notice",
        "Course Completion Letter"
    ], key="msg_type_select")

    # ---- 3. Logo/Watermark/Extra Attachment ----
    st.subheader("Upload Logo and Watermark")
    logo_file = st.file_uploader("School Logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_up")
    watermark_file_path = None
    if msg_type == "Letter of Enrollment":
        try:
            import requests
            from PIL import Image
            from io import BytesIO
            resp = requests.get(watermark_drive_url)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content))
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                img.save(tmp.name)
                watermark_file_path = tmp.name
        except:
            watermark_file_path = None
    extra_attach = st.file_uploader("Additional Attachment (optional)", type=None, key="extra_attach")

    # ---- 4. Compose/Preview Message ----
    st.subheader("Compose/Preview Message")
    if msg_type == "Welcome Message":
        body_default = (
            f"Hello {student_name},<br><br>"
            "Welcome to Learn Language Education Academy! We have helped many students succeed, "
            "and we’re excited to support you as well.<br><br>"
            "Your contract starts on "
            f"{enrollment_start.strftime('%d %B %Y')}.<br>"
            f"Your payment status: {payment_status}. Paid: GHS {payment:.2f} / Balance: GHS {balance:.2f}<br><br>"
            f"All materials are on our <a href='{student_link}'>Falowen App</a>.<br><br>"
        )
    elif msg_type == "Letter of Enrollment":
        body_default = (
            f"To Whom It May Concern,<br><br>"
            f"{student_name} is officially enrolled in {student_level} at Learn Language Education Academy.<br>"
            f"Enrollment valid from {enrollment_start:%m/%d/%Y} to {enrollment_end:%m/%d/%Y}.<br><br>"
            f"Business Reg No: {BUSINESS_REG}.<br><br>"
        )
    elif msg_type == "Assignment Results":
        body_default = (
            f"Hello {student_name},<br><br>"
            "Here are your latest assignment results:<br>"
            "<ul><li>Assignment 1: 85 percent</li><li>Assignment 2: 90 percent</li></ul>"
        )
    elif msg_type == "Outstanding Balance Notice":
        body_default = (
            f"Dear {student_name},<br><br>"
            f"You have an outstanding balance of GHS {balance:.2f}. Please settle promptly.<br><br>"
        )
    elif msg_type == "Course Completion Letter":
        body_default = (
            f"Dear {student_name},<br><br>"
            f"Congratulations on completing the {student_level} course!<br><br>"
            "Best wishes,<br>Felix Asadu<br>Director"
        )
    else:
        body_default = ""

    if "email_subject" not in st.session_state:
        st.session_state["email_subject"] = f"{msg_type} - {student_name}"
    if "email_body" not in st.session_state:
        st.session_state["email_body"] = body_default
    if "recipient_email" not in st.session_state:
        st.session_state["recipient_email"] = student_email
    if "attach_pdf" not in st.session_state:
        st.session_state["attach_pdf"] = False

    st.subheader("Compose/Preview Message")
    with st.form("email_compose_form"):
        email_subject_input = st.text_input(
            "Subject",
            value=st.session_state["email_subject"],
        )
        email_body_input = st.text_area(
            "Email Body (HTML supported)",
            value=st.session_state["email_body"],
            height=220,
        )
        attach_pdf_input = st.checkbox(
            "Attach the generated PDF?",
            value=st.session_state["attach_pdf"],
        )
        recipient_email_input = st.text_input(
            "Recipient Email",
            value=st.session_state["recipient_email"],
        )
        preview_submit = st.form_submit_button("Update Preview")
        send_email_submit = st.form_submit_button("Send Email Now")
    if preview_submit or send_email_submit:
        st.session_state["email_subject"] = email_subject_input
        st.session_state["email_body"] = email_body_input
        st.session_state["attach_pdf"] = attach_pdf_input
        st.session_state["recipient_email"] = recipient_email_input
    email_subject = st.session_state["email_subject"]
    email_body = st.session_state["email_body"]
    attach_pdf = st.session_state["attach_pdf"]
    recipient_email = st.session_state["recipient_email"]

    st.markdown("**Preview Message:**")
    st.markdown(email_body, unsafe_allow_html=True)

    # ---- 5. Generate PDF Button (and preview) ----
    st.subheader("PDF Preview & Download")

    class LetterPDF(FPDF):
        def header(self):
            if logo_file:
                ext = logo_file.name.split('.')[-1]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                tmp.write(logo_file.read()); tmp.close()
                self.image(tmp.name, x=10, y=8, w=28)
            self.set_font('Arial', 'B', 16)
            self.cell(0, 9, safe_pdf(SCHOOL_NAME), ln=True, align='C')
            self.set_font('Arial', '', 11)
            self.cell(0, 7, safe_pdf(f"{SCHOOL_WEBSITE} | {SCHOOL_PHONE} | {SCHOOL_ADDRESS}"), ln=True, align='C')
            self.set_font('Arial', 'I', 10)
            self.cell(0, 7, safe_pdf(f"Business Reg No: {BUSINESS_REG}"), ln=True, align='C')
            self.ln(3)
            self.set_draw_color(200,200,200); self.set_line_width(0.5)
            self.line(10, self.get_y(), 200, self.get_y()); self.ln(6)
        def watermark(self):
            if watermark_file_path:
                self.image(watermark_file_path, x=38, y=60, w=130)
        def footer(self):
            qr = make_qr_code(SCHOOL_WEBSITE)
            self.image(qr, x=180, y=275, w=18)
            self.set_y(-18)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, safe_pdf("Generated without signature."), 0, 0, 'C')

    pdf = LetterPDF()
    pdf.add_page()
    pdf.watermark()
    pdf.set_font("Arial", size=12)
    import re
    pdf.multi_cell(0, 8, safe_pdf(re.sub(r"<br\s*/?>", "\n", email_body)))
    pdf.ln(6)
    if msg_type == "Letter of Enrollment":
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, safe_pdf("Yours sincerely,"), ln=True)
        pdf.cell(0, 7, safe_pdf("Felix Asadu"), ln=True)
        pdf.cell(0, 7, safe_pdf("Director"), ln=True)
        pdf.cell(0, 7, safe_pdf(SCHOOL_NAME), ln=True)

    # --- Safe PDF bytes output (universal fallback) ---
    output_data = pdf.output(dest="S")
    if isinstance(output_data, bytes):
        pdf_bytes = output_data
    elif isinstance(output_data, str):
        pdf_bytes = output_data.encode("latin-1", "replace")
    else:
        # fallback via temp file
        tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(tmpf.name); tmpf.close()
        with open(tmpf.name, "rb") as f: pdf_bytes = f.read()
        os.remove(tmpf.name)

    st.download_button(
        "📄 Download Letter/PDF",
        data=pdf_bytes,
        file_name=f"{student_name.replace(' ', '_')}_{msg_type.replace(' ','_')}.pdf",
        mime="application/pdf"
    )
    st.caption("You can share this PDF on WhatsApp or by email.")

    if send_email_submit:
        msg = Mail(
            from_email=SENDER_EMAIL,
            to_emails=recipient_email,
            subject=email_subject,
            html_content=email_body,
        )
        if attach_pdf:
            msg.add_attachment(
                Attachment(
                    FileContent(base64.b64encode(pdf_bytes).decode()),
                    FileName(f"{student_name.replace(' ','_')}_{msg_type.replace(' ','_')}.pdf"),
                    FileType("application/pdf"),
                    Disposition("attachment"),
                )
            )
        if extra_attach:
            fb = extra_attach.read()
            msg.add_attachment(
                Attachment(
                    FileContent(base64.b64encode(fb).decode()),
                    FileName(extra_attach.name),
                    FileType(extra_attach.type or "application/octet-stream"),
                    Disposition("attachment"),
                )
            )
        try:
            SendGridAPIClient(SENDGRID_KEY).send(msg)
            st.success(f"Email sent to {recipient_email}!")
        except Exception as e:
            st.error(f"Email send failed: {e}")


# ====== HELPERS ======
def safe_pdf(text):
    """Ensure all strings are PDF-safe (latin-1 only)."""
    return "".join(c if ord(c) < 256 else "?" for c in str(text or ""))

def wrap_lines(text, width=80):
    """Wrap text to avoid FPDF width errors."""
    lines = []
    for para in text.split("\n"):
        lines.extend(textwrap.wrap(para, width=width) or [""])
    return lines

# ====== COURSE SCHEDULE CONSTANTS ======
RAW_SCHEDULE_A1 = [
    ("Week One", ["Chapter 0.1 - Lesen & Horen"]),
    ("Week Two", [
        "Chapters 0.2 and 1.1 - Lesen & Horen",
        "Chapter 1.1 - Schreiben & Sprechen and Chapter 1.2 - Lesen & Horen",
        "Chapter 2 - Lesen & Horen"
    ]),
    ("Week Three", [
        "Chapter 1.2 - Schreiben & Sprechen (Recap)",
        "Chapter 2.3 - Schreiben & Sprechen",
        "Chapter 3 - Lesen & Horen"
    ]),
    ("Week Four", [
        "Chapter 4 - Lesen & Horen",
        "Chapter 5 - Lesen & Horen",
        "Chapter 6 - Lesen & Horen and Chapter 2.4 - Schreiben & Sprechen"
    ]),
    ("Week Five", [
        "Chapter 7 - Lesen & Horen",
        "Chapter 8 - Lesen & Horen",
        "Chapter 3.5 - Schreiben & Sprechen"
    ]),
    ("Week Six", [
        "Chapter 3.6 - Schreiben & Sprechen",
        "Chapter 4.7 - Schreiben & Sprechen",
        "Chapter 9 and 10 - Lesen & Horen"
    ]),
    ("Week Seven", [
        "Chapter 11 - Lesen & Horen",
        "Chapter 12.1 - Lesen & Horen and Schreiben & Sprechen (including 5.8)",
        "Chapter 5.9 - Schreiben & Sprechen"
    ]),
    ("Week Eight", [
        "Chapter 6.10 - Schreiben & Sprechen (Intro to letter writing)",
        "Chapter 13 - Lesen & Horen and Chapter 6.11 - Schreiben & Sprechen",
        "Chapter 14.1 - Lesen & Horen and Chapter 7.12 - Schreiben & Sprechen"
    ]),
    ("Week Nine", [
        "Chapter 14.2 - Lesen & Horen and Chapter 7.12 - Schreiben & Sprechen",
        "Chapter 8.13 - Schreiben & Sprechen",
        "Exam tips - Schreiben & Sprechen recap"
    ])
]

RAW_SCHEDULE_A2 = [
    ("Woche 1", ["1.1. Small Talk (Exercise)", "1.2. Personen Beschreiben (Exercise)", "1.3. Dinge und Personen vergleichen"]),
    ("Woche 2", ["2.4. Wo möchten wir uns treffen?", "2.5. Was machst du in deiner Freizeit?"]),
    ("Woche 3", ["3.6. Möbel und Räume kennenlernen", "3.7. Eine Wohnung suchen (Übung)", "3.8. Rezepte und Essen (Exercise)"]),
    ("Woche 4", ["4.9. Urlaub", "4.10. Tourismus und Traditionelle Feste", "4.11. Unterwegs: Verkehrsmittel vergleichen"]),
    ("Woche 5", ["5.12. Ein Tag im Leben (Übung)", "5.13. Ein Vorstellungsgesprach (Exercise)", "5.14. Beruf und Karriere (Exercise)"]),
    ("Woche 6", ["6.15. Mein Lieblingssport", "6.16. Wohlbefinden und Entspannung", "6.17. In die Apotheke gehen"]),
    ("Woche 7", ["7.18. Die Bank Anrufen", "7.19. Einkaufen – Wo und wie? (Exercise)", "7.20. Typische Reklamationssituationen üben"]),
    ("Woche 8", ["8.21. Ein Wochenende planen", "8.22. Die Woche Plannung"]),
    ("Woche 9", ["9.23. Wie kommst du zur Schule / zur Arbeit?", "9.24. Einen Urlaub planen", "9.25. Tagesablauf (Exercise)"]),
    ("Woche 10", ["10.26. Gefühle in verschiedenen Situationen beschr", "10.27. Digitale Kommunikation", "10.28. Über die Zukunft sprechen"])
]

# ——— FIXED: keep only this B1 definition (removed accidental overwrite) ———
RAW_SCHEDULE_B1 = [
    ("Woche 1", ["1.1. Traumwelten (Übung)", "1.2. Freundes für Leben (Übung)", "1.3. Erfolgsgeschichten (Übung)"]),
    ("Woche 2", ["2.4. Wohnung suchen (Übung)", "2.5. Der Besichtigungsg termin (Übung)", "2.6. Leben in der Stadt oder auf dem Land?"]),
    ("Woche 3", ["3.7. Fast Food vs. Hausmannskost", "3.8. Alles für die Gesundheit", "3.9. Work-Life-Balance im modernen Arbeitsumfeld"]),
    ("Woche 4", ["4.10. Digitale Auszeit und Selbstfürsorge", "4.11. Teamspiele und Kooperative Aktivitäten", "4.12. Abenteuer in der Natur", "4.13. Eigene Filmkritik schreiben"]),
    ("Woche 5", ["5.14. Traditionelles vs. digitales Lernen", "5.15. Medien und Arbeiten im Homeoffice", "5.16. Prüfungsangst und Stressbewältigung", "5.17. Wie lernt man am besten?"]),
    ("Woche 6", ["6.18. Wege zum Wunschberuf", "6.19. Das Vorstellungsgespräch", "6.20. Wie wird man …? (Ausbildung und Qu)"]),
    ("Woche 7", ["7.21. Lebensformen heute – Familie, Wohnge", "7.22. Was ist dir in einer Beziehung wichtig?", "7.23. Erstes Date – Typische Situationen"]),
    ("Woche 8", ["8.24. Konsum und Nachhaltigkeit", "8.25. Online einkaufen – Rechte und Risiken"]),
    ("Woche 9", ["9.26. Reiseprobleme und Lösungen"]),
    ("Woche 10", ["10.27. Umweltfreundlich im Alltag", "10.28. Klimafreundlich leben"])
]

RAW_SCHEDULE_B2 = [
    ("Woche 1", [
        "1. Persönliche Identität und Selbstverständnis",
        "2. Beziehungen und Kommunikation",
        "3. Öffentliches vs. Privates Leben"
    ]),
    ("Woche 2", [
        "4. Beruf und Karriere",
        "5. Bildung und Lernen",
        "6. Kultur und Gesellschaft"
    ]),
    ("Woche 3", [
        "7. Medien und digitale Welt",
        "8. Wissenschaft und Technologie",
        "9. Politik und Gesellschaft"
    ]),
    ("Woche 4", [
        "10. Wirtschaft und Finanzen",
        "11. Umwelt und Nachhaltigkeit",
        "12. Gesundheit und Wohlbefinden"
    ]),
    ("Woche 5", [
        "13. Ernährung und Lebensstil",
        "14. Reisen und Mobilität",
        "15. Wohnen und Lebensräume"
    ]),
    ("Woche 6", [
        "16. Freizeit, Hobbys und Interessen",
        "17. Feste und Traditionen",
        "18. Werte und Normen"
    ]),
    ("Woche 7", [
        "19. Migration und Integration",
        "20. Diskriminierung und Gleichstellung",
        "21. Recht und Ordnung"
    ]),
    ("Woche 8", [
        "22. Konfliktmanagement",
        "23. Globalisierung",
        "24. Zukunft und Innovation"
    ]),
    ("Woche 9", [
        "25. Kommunikation im Berufsleben",
        "26. Wissenschaftliches Arbeiten",
        "27. Zeitmanagement und Organisation",
        "28. Zusammenfassung & Prüfungsvorbereitung"
    ]),
]

# ====== TAB 6 CODE ======
with tabs[5]:

    st.markdown("""
    <div style='background:#e3f2fd;padding:1.2em 1em 0.8em 1em;border-radius:12px;margin-bottom:1em'>
      <h2 style='color:#1565c0;'>📆 <b>Intelligenter Kursplan-Generator (A1, A2, B1, B2)</b></h2>
      <p style='font-size:1.08em;color:#333'>Erstellen Sie einen vollständigen, individuell angepassten Kursplan zum Download (TXT oder PDF) – <b>mit Ferien und flexiblem Wochenrhythmus!</b></p>
    </div>
    """, unsafe_allow_html=True)

    # Step 1: Choose course level
    st.markdown("### 1️⃣ **Kursniveau wählen**")
    course_levels = {"A1": RAW_SCHEDULE_A1, "A2": RAW_SCHEDULE_A2, "B1": RAW_SCHEDULE_B1, "B2": RAW_SCHEDULE_B2}
    selected_level = st.selectbox("🗂️ **Kursniveau (A1/A2/B1/B2):**", list(course_levels.keys()))
    topic_structure = course_levels.get(selected_level, [])
    st.markdown("---")

    if not topic_structure or sum(len(sess) for _, sess in topic_structure) == 0:
        st.error(f"Für {selected_level} sind keine Themen vorhanden. Bitte prüfen Sie RAW_SCHEDULE_{selected_level}.")
        st.stop()

    # Step 2: Basic info & breaks
    st.markdown("### 2️⃣ **Kursdaten, Ferien, Modus**")
    col1, col2 = st.columns([2,1])
    with col1:
        start_date = st.date_input("📅 **Kursstart**", value=date.today())
        holiday_dates = st.multiselect(
            "🔔 Ferien oder Feiertage (Holiday/Break Dates)",
            options=[start_date + timedelta(days=i) for i in range(180)],
            format_func=lambda d: d.strftime("%A, %d %B %Y"),
            help="Kein Unterricht an diesen Tagen."
        )
    with col2:
        advanced_mode = st.toggle("⚙️ Erweiterter Wochen-Rhythmus (Custom weekly pattern)", value=False)
    st.markdown("---")

    # Step 3: Weekly pattern
    st.markdown("### 3️⃣ **Unterrichtstage festlegen**")
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    default_days = ["Monday", "Tuesday", "Wednesday"]

    week_patterns = []
    if not advanced_mode:
        days_per_week = st.multiselect("📌 **Unterrichtstage wählen:**", options=days_of_week, default=default_days)
        if not days_per_week:
            st.warning("Keine Wochentage ausgewählt – verwende Standard: Mo–Mi.")
            days_per_week = default_days
        for _, sessions in topic_structure:
            week_patterns.append((len(sessions), days_per_week))
    else:
        st.info("Für jede Woche individuelle Unterrichtstage einstellen.")
        for i, (week_label, sessions) in enumerate(topic_structure):
            with st.expander(f"{week_label}", expanded=True):
                week_days = st.multiselect(
                    f"Unterrichtstage {week_label}",
                    options=days_of_week,
                    default=default_days,
                    key=f"week_{i}_days"
                )
                week_patterns.append((len(sessions), week_days or default_days))
    st.markdown("---")

    # Generate session dates skipping holidays
    total_sessions = sum(wp[0] for wp in week_patterns)
    session_labels = [(w, s) for w, sess in topic_structure for s in sess]
    dates = []
    cur = start_date
    for num_classes, week_days in week_patterns:
        week_dates = []
        while len(week_dates) < num_classes:
            if cur.strftime("%A") in week_days and cur not in holiday_dates:
                week_dates.append(cur)
            cur += timedelta(days=1)
        dates.extend(week_dates)

    # Build preview table
    rows = []
    for i, ((week_label, topic), d) in enumerate(zip(session_labels, dates)):
        rows.append({
            "Week": week_label,
            "Day": f"Day {i+1}",
            "Date": d.strftime("%A, %d %B %Y"),
            "Topic": topic
        })

    if not rows:
        st.warning("Es konnten keine Termine erzeugt werden. Prüfen Sie die Wochentage, Ferien und den Starttermin.")
        st.stop()

    df = pd.DataFrame(rows)
    st.markdown(f"""
    <div style='background:#fffde7;border:1px solid #ffe082;border-radius:10px;padding:1em;margin:1em 0'>
      <b>📝 Kursüberblick:</b>
      <ul>
        <li><b>Kurs:</b> {selected_level}</li>
        <li><b>Start:</b> {start_date.strftime('%A, %d %B %Y')}</li>
        <li><b>Sessions:</b> {total_sessions}</li>
        <li><b>Ferien:</b> {', '.join(d.strftime('%d.%m.%Y') for d in holiday_dates) if holiday_dates else '–'}</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown("---")

    # ---- TXT download ----
    file_date = start_date.strftime("%Y-%m-%d")
    file_prefix = f"{selected_level}_{file_date}_course_schedule"

    txt = (
        "Learn Language Education Academy\n"
        "Contact: 0205706589 | www.learngermanghana.com\n"
        f"Schedule: {selected_level}\n"
        f"Start: {start_date.strftime('%Y-%m-%d')}\n\n"
    )
    for row in rows:
        txt += f"- {row['Day']} ({row['Date']}): {row['Topic']}\n"

    st.download_button(
        "📁 TXT Download",
        txt,
        file_name=f"{file_prefix}.txt"
    )

    # ---- PDF download (reliable logic) ----
    class SchedulePDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 9, safe_pdf("Learn Language Education Academy"), ln=True, align='C')
            self.set_font('Arial', '', 11)
            self.cell(0, 7, safe_pdf("www.learngermanghana.com | 0205706589 | Accra, Ghana"), ln=True, align='C')
            self.ln(6)
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.5)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(3)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, safe_pdf("Schedule generated by Learn Language Education Academy."), 0, 0, 'C')

    pdf = SchedulePDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, safe_pdf(f"Course Schedule: {selected_level}"), ln=True)
    pdf.cell(0, 8, safe_pdf(f"Start Date: {start_date.strftime('%A, %d %B %Y')}"), ln=True)
    pdf.ln(4)
    for row in rows:
        line = f"{row['Day']} ({row['Date']}): {row['Topic']}"
        pdf.multi_cell(0, 8, safe_pdf(line))
        pdf.ln(1)
    pdf.ln(3)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 8, safe_pdf("Felix Asadu (Director)"), ln=True, align='R')

    # --- Ensure PDF bytes are correct ---
    output_data = pdf.output(dest="S")
    if isinstance(output_data, bytes):
        pdf_bytes = output_data
    elif isinstance(output_data, str):
        pdf_bytes = output_data.encode("latin-1", "replace")
    else:
        # fallback via temp file
        import tempfile, os
        tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(tmpf.name)
        tmpf.close()
        with open(tmpf.name, "rb") as f:
            pdf_bytes = f.read()
        os.remove(tmpf.name)

    st.download_button(
        "📄 Download Schedule PDF",
        data=pdf_bytes,
        file_name=f"{file_prefix}.pdf",
        mime="application/pdf"
    )



# --- 1. URLS ---
students_csv_url = "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
ref_answers_url  = "https://docs.google.com/spreadsheets/d/1CtNlidMfmE836NBh5FmEF5tls9sLmMmkkhewMTQjkBo/export?format=csv"

def render_marking_tab():
    st.title("📝 Reference & Student Work Share")

    # --- Load Data (unique cache funcs to avoid collisions with other tabs) ---
    @st.cache_data(show_spinner=False)
    def load_marking_students(url: str):
        df = pd.read_csv(url, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        if "student_code" in df.columns:
            df = df.rename(columns={"student_code": "studentcode"})
        return df

    @st.cache_data(ttl=300, show_spinner=False)
    def load_marking_ref_answers(url: str):
        df = pd.read_csv(url, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        return df

    try:
        df_students = load_marking_students(students_csv_url)
    except Exception as e:
        st.error(f"Could not load students: {e}")
        return

    try:
        ref_df = load_marking_ref_answers(ref_answers_url)
        if "assignment" not in ref_df.columns:
            st.warning("No 'assignment' column found in reference answers sheet.")
            return
    except Exception as e:
        st.error(f"Could not load reference answers: {e}")
        return

    # --- Helpers ---
    def col_lookup(df, name):
        key = name.lower().replace(" ", "").replace("_", "")
        for c in df.columns:
            if c.lower().replace(" ", "").replace("_", "") == key:
                return c
        return None

    name_col = col_lookup(df_students, "name")
    code_col = col_lookup(df_students, "studentcode")
    if not name_col or not code_col:
        st.error("Required columns 'name' or 'studentcode' not found in students sheet.")
        return

    # --- Student search and select (no st.stop; we just return early if needed) ---
    st.subheader("1. Search & Select Student")

    with st.form("marking_student_form"):
        search_student = st.text_input("Type student name or code...", key="tab7_search_student")
        submitted_student = st.form_submit_button("Apply")

    if submitted_student and search_student:
        mask = (
            df_students[name_col].astype(str).str.contains(search_student, case=False, na=False) |
            df_students[code_col].astype(str).str.contains(search_student, case=False, na=False)
        )
        students_filtered = df_students[mask].copy()
    else:
        students_filtered = df_students.copy()

    if students_filtered.empty:
        st.info("No students match your search. Try a different query.")
        return

    # Build display list safely
    display_name = students_filtered[name_col].fillna("").astype(str)
    display_code = students_filtered[code_col].fillna("").astype(str)
    student_list = (display_name + " (" + display_code + ")").tolist()

    chosen = st.selectbox("Select Student", student_list, key="tab7_single_student")

    if not chosen or "(" not in chosen:
        st.warning("Select a student to continue.")
        return

    student_code = chosen.split("(")[-1].replace(")", "").strip()
    sel_rows = students_filtered[students_filtered[code_col] == student_code]
    if sel_rows.empty:
        st.warning("Selected student not found.")
        return
    student_row = sel_rows.iloc[0]

    st.markdown(f"**Selected:** {student_row.get(name_col, '')} ({student_code})")
    student_level = student_row.get('level', "")

    # --- Assignment search and select ---
    st.subheader("2. Select Assignment")

    available_assignments = (
        ref_df['assignment'].dropna().astype(str).unique().tolist()
        if 'assignment' in ref_df.columns else []
    )

    with st.form("marking_assignment_form"):
        search_assign = st.text_input("Type assignment title...", key="tab7_search_assign")
        submitted_assign = st.form_submit_button("Filter assignments")

    if submitted_assign and search_assign:
        filtered = [a for a in available_assignments if search_assign.lower() in a.lower()]
    else:
        filtered = available_assignments

    if not filtered:
        st.info("No assignments match your search.")
        return

    assignment = st.selectbox("Select Assignment", filtered, key="tab7_assign_select")
    if not assignment:
        st.info("Select an assignment to continue.")
        return

    # --- REFERENCE ANSWERS (TABS + COMBINED BOX) ---
    st.subheader("3. Reference Answer (from Google Sheet)")
    ref_answers = []
    if assignment:
        assignment_row = ref_df[ref_df['assignment'].astype(str) == assignment]
        if not assignment_row.empty:
            all_cols = assignment_row.columns.tolist()
            answer_cols = [c for c in all_cols if str(c).startswith("answer")]
            answer_cols = [c for c in answer_cols
                           if pd.notnull(assignment_row.iloc[0][c])
                           and str(assignment_row.iloc[0][c]).strip() != ""]
            ref_answers = [str(assignment_row.iloc[0][c]) for c in answer_cols]

    if ref_answers:
        if len(ref_answers) == 1:
            st.markdown("**Reference Answer:**")
            st.write(ref_answers[0])
        else:
            ans_tabs = st.tabs([f"Answer {i+1}" for i in range(len(ref_answers))])
            for i, ans in enumerate(ref_answers):
                with ans_tabs[i]:
                    st.write(ans)
        answers_combined_str  = "\n".join([f"{i+1}. {ans}" for i, ans in enumerate(ref_answers)])
        answers_combined_html = "<br>".join([f"{i+1}. {ans}" for i, ans in enumerate(ref_answers)])
    else:
        answers_combined_str  = "No answer available."
        answers_combined_html = "No answer available."
        st.info("No reference answer available for this assignment.")

    # --- STUDENT WORK + AI COPY ZONE ---
    st.subheader("4. Paste Student Work (for your manual cross-check or ChatGPT use)")
    student_work = st.text_area("Paste the student's answer here:", height=140, key="tab7_student_work")

    # --- Combined copy box ---
    st.subheader("5. Copy Zone (Reference + Student Work for AI/manual grading)")
    combined_text = (
        "Reference answer:\n"
        + answers_combined_str
        + "\n\nStudent answer:\n"
        + (student_work or "")
    )
    st.code(combined_text, language="markdown")
    st.info("Copy this block and paste into ChatGPT or your AI tool for checking.")

    # --- Copy buttons ---
    st.write("**Quick Copy:**")
    st.download_button(
        "📋 Copy Only Reference Answer (txt)",
        data=answers_combined_str,
        file_name="reference_answer.txt",
        mime="text/plain",
        key="tab7_copy_reference",
    )
    st.download_button(
        "📋 Copy Both (Reference + Student)",
        data=combined_text,
        file_name="ref_and_student.txt",
        mime="text/plain",
        key="tab7_copy_both",
    )

    st.divider()

    # --- EMAIL SECTION ---
    st.subheader("6. Send Reference Answer to Student by Email")
    default_email = student_row.get('email', '') if 'email' in student_row else ""
    ref_ans_email = f"<b>Reference Answers:</b><br>{answers_combined_html}<br>"
    with st.form("tab7_email_form"):
        to_email_input = st.text_input("Recipient Email", value=default_email)
        subject_input = st.text_input(
            "Subject",
            value=f"{student_row.get(name_col, '')} - {assignment} Reference Answer",
        )
        body_input = st.text_area(
            "Message (HTML allowed)",
            value=(
                f"Hello {student_row.get(name_col, '')},<br><br>"
                f"Here is the reference answer for your assignment <b>{assignment}</b>.<br><br>"
                f"{ref_ans_email}"
                "Thank you<br>Learn Language Education Academy"
            ),
            key="tab7_body",
        )
        email_submit = st.form_submit_button("📧 Email Reference")
    if email_submit:
        if not to_email_input or "@" not in to_email_input:
            st.error("Please enter a valid recipient email address.")
        else:
            try:
                send_email_report(None, to_email_input, subject_input, body_input)
                st.success(f"Reference sent to {to_email_input}!")
            except Exception as e:
                st.error(f"Failed to send email: {e}")

    # --- WhatsApp Share Section ---
    st.subheader("7. Share Reference via WhatsApp")
    wa_phone = ""
    wa_cols = [c for c in student_row.index if "phone" in c]
    for c in wa_cols:
        v = str(student_row[c])
        if v.startswith("233") or v.startswith("0") or v.isdigit():
            wa_phone = v
            break
    ref_ans_wa = "*Reference Answers:*\n" + answers_combined_str + "\n"
    default_wa_msg = (
        f"Hello {student_row.get(name_col, '')},\n\n"
        f"Here is the reference answer for your assignment: *{assignment}*\n"
        f"{ref_ans_wa}\n"
        "Open my results and resources on the Falowen app for scores and full comment.\n"
        "Don't forget to click refresh for latest results for your new scores to show.\n"
        "Thank you!\n"
        "Happy learning!"
    )
    with st.form("tab7_whatsapp_form"):
        wa_phone_input = st.text_input(
            "WhatsApp Number (International format, e.g., 233245022743)",
            value=wa_phone,
        )
        wa_message_input = st.text_area(
            "WhatsApp Message (edit before sending):",
            value=default_wa_msg,
            height=180,
            key="tab7_wa_message_edit",
        )
        wa_submit = st.form_submit_button("Generate WhatsApp Link")
    if wa_submit:
        wa_num_formatted = (wa_phone_input or "").strip().replace(" ", "").replace("-", "")
        if wa_num_formatted.startswith("0"):
            wa_num_formatted = "233" + wa_num_formatted[1:]
        elif wa_num_formatted.startswith("+"):
            wa_num_formatted = wa_num_formatted[1:]
        elif not wa_num_formatted.startswith("233") and wa_num_formatted.isdigit() and len(wa_num_formatted) >= 9:
            wa_num_formatted = "233" + wa_num_formatted[-9:]

        if wa_num_formatted.isdigit() and len(wa_num_formatted) >= 11:
            wa_link = f"https://wa.me/{wa_num_formatted}?text={urllib.parse.quote(wa_message_input)}"
            st.markdown(
                f'<a href="{wa_link}" target="_blank">'
                f'<button style="background-color:#25d366;color:white;border:none;padding:10px 20px;border-radius:5px;font-size:16px;cursor:pointer;">'
                '📲 Share Reference on WhatsApp'
                '</button></a>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Enter a valid WhatsApp number (233XXXXXXXXX or 0XXXXXXXXX).")

# Call it inside your tabs container
with tabs[6]:
    render_marking_tab()





