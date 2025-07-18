# ==== IMPORTS ====
import os
import re
import base64
import tempfile
import urllib.parse
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st
from fpdf import FPDF
import qrcode


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
EXPENSES_SHEET_ID = "1I5mGFcWbWdK6YQrJtabTg_g-XBEVaIRK1aMFm72vDEM"
REF_ANSWERS_SHEET_ID = "1CtNlidMfmE836NBh5FmEF5tls9sLmMmkkhewMTQjkBo"

STUDENTS_CSV_URL = f"https://docs.google.com/spreadsheets/d/{STUDENTS_SHEET_ID}/export?format=csv"
EXPENSES_CSV_URL = f"https://docs.google.com/spreadsheets/d/{EXPENSES_SHEET_ID}/export?format=csv"
REF_ANSWERS_CSV_URL = f"https://docs.google.com/spreadsheets/d/{REF_ANSWERS_SHEET_ID}/export?format=csv"

# ==== STREAMLIT SECRETS ====
SENDER_EMAIL = st.secrets["general"].get("sender_email", "Learngermanghana@gmail.com")
SENDGRID_KEY = st.secrets["general"].get("sendgrid_api_key", "")

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

@st.cache_data(ttl=300, show_spinner="Loading expenses...")
def load_expenses():
    try:
        df = pd.read_csv(EXPENSES_CSV_URL, dtype=str)
        df = normalize_columns(df)
    except Exception as e:
        st.error(f"Could not load expenses: {e}")
        df = pd.DataFrame(columns=["type", "item", "amount", "date"])
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
df_expenses = load_expenses()
df_ref_answers = load_ref_answers()

# ==== UNIVERSAL VARIABLES (for later use) ====
LEVELS = sorted(df_students["level"].dropna().unique().tolist()) if "level" in df_students.columns else []
STUDENT_CODES = df_students["studentcode"].dropna().unique().tolist() if "studentcode" in df_students.columns else []

# ==== END OF STAGE 2 ====

# ==== TABS SETUP ====
tabs = st.tabs([
    "📝 Pending",                 # 0
    "👩‍🎓 All Students"          # 1
    "💵 Expenses"                # 2
    
])

# ==== TAB 0: PENDING STUDENTS ====
with tabs[0]:
    st.title("🕒 Pending Students")

    # -- Define/Load Pending Students Google Sheet URL --
    PENDING_SHEET_ID = "1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo"
    PENDING_CSV_URL = f"https://docs.google.com/spreadsheets/d/{PENDING_SHEET_ID}/export?format=csv"

    @st.cache_data(ttl=0)
    def load_pending():
        df = pd.read_csv(PENDING_CSV_URL, dtype=str)
        df = normalize_columns(df)
        df_display = df.copy()
        df_search = df.copy()
        return df_display, df_search

    df_display, df_search = load_pending()

    # --- Universal Search ---
    search = st.text_input("🔎 Search any field (name, code, email, etc.)")
    if search:
        mask = df_search.apply(
            lambda row: row.astype(str).str.contains(search, case=False, na=False).any(),
            axis=1
        )
        filt = df_display[mask]
    else:
        filt = df_display

    # --- Column Selector ---
    all_cols = list(filt.columns)
    selected_cols = st.multiselect(
        "Show columns (for easy viewing):", all_cols, default=all_cols[:6]
    )

    # --- Show Table (with scroll bar) ---
    st.dataframe(filt[selected_cols], use_container_width=True, height=400)

    # --- Download Button (all columns always) ---
    st.download_button(
        "⬇️ Download all columns as CSV",
        filt.to_csv(index=False),
        file_name="pending_students.csv"
    )

# ==== END OF STAGE 3 (TAB 0) ====

# ==== TAB 1: ALL STUDENTS ====
with tabs[1]:
    st.title("👩‍🎓 All Students")

    # --- Optional: Search/Filter ---
    search = st.text_input("🔍 Search students by name, code, or email...")
    if search:
        search = search.lower().strip()
        filt = df_students[
            df_students.apply(lambda row: search in str(row).lower(), axis=1)
        ]
    else:
        filt = df_students

    # --- Show Student Table ---
    st.dataframe(filt, use_container_width=True)

    # --- Download Button ---
    st.download_button(
        "⬇️ Download All Students CSV",
        filt.to_csv(index=False),
        file_name="all_students.csv"
    )

# ==== TAB 2: EXPENSES AND FINANCIAL SUMMARY ====
with tabs[2]:
    st.title("💵 Expenses and Financial Summary")

    # --- Use cached data loaded at top ---
    df_exp = df_expenses.copy()
    df_stu = df_students.copy()

    # --- Add New Expense Form ---
    with st.form("add_expense_form"):
        exp_type   = st.selectbox("Type", ["Bill","Rent","Salary","Marketing","Other"])
        exp_item   = st.text_input("Expense Item")
        exp_amount = st.number_input("Amount (GHS)", min_value=0.0, step=1.0)
        exp_date   = st.date_input("Date", value=date.today())
        submit     = st.form_submit_button("Add Expense")
        if submit and exp_item and exp_amount > 0:
            # Append new row to the expenses dataframe (local, not Google Sheet)
            new_row = {"type": exp_type, "item": exp_item, "amount": exp_amount, "date": exp_date}
            df_exp = pd.concat([df_exp, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"✅ Recorded: {exp_type} – {exp_item}")
            # Save locally so that session users can download the updated file
            df_exp.to_csv("expenses_all.csv", index=False)
            st.experimental_rerun()

    # --- Financial Summary ---
    st.write("## 📊 Financial Summary")

    # Total Expenses
    total_expenses = pd.to_numeric(df_exp["amount"], errors="coerce").fillna(0).sum() if not df_exp.empty else 0.0

    # Total Income
    if "paid" in df_stu.columns:
        total_income = pd.to_numeric(df_stu["paid"], errors="coerce").fillna(0).sum()
    else:
        total_income = 0.0

    # Net Profit
    net_profit = total_income - total_expenses

    # Total Outstanding (Balance)
    if "balance" in df_stu.columns:
        total_balance_due = pd.to_numeric(df_stu["balance"], errors="coerce").fillna(0).sum()
    else:
        total_balance_due = 0.0

    # Student Count
    student_count = len(df_stu) if not df_stu.empty else 0

    # --- Display Summary Metrics ---
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Income (Paid)", f"GHS {total_income:,.2f}")
    col2.metric("💸 Total Expenses", f"GHS {total_expenses:,.2f}")
    col3.metric("🟢 Net Profit", f"GHS {net_profit:,.2f}")

    st.info(f"📋 **Students Enrolled:** {student_count}")
    st.info(f"🧾 **Outstanding Balances:** GHS {total_balance_due:,.2f}")

    # --- Paginated Expense Table ---
    st.write("### All Expenses")
    ROWS_PER_PAGE = 10
    total_rows    = len(df_exp)
    total_pages   = (total_rows - 1) // ROWS_PER_PAGE + 1
    page = st.number_input(
        f"Page (1-{total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="exp_page"
    ) if total_pages > 1 else 1
    start = (page - 1) * ROWS_PER_PAGE
    end   = start + ROWS_PER_PAGE
    st.dataframe(df_exp.iloc[start:end].reset_index(drop=True), use_container_width=True)

    # --- Export to CSV ---
    st.download_button(
        "📁 Download Expenses CSV",
        data=df_exp.to_csv(index=False),
        file_name="expenses_data.csv",
        mime="text/csv"
    )
