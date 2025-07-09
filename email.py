# ==== 1. IMPORTS ====
import os
import base64
import re
from datetime import datetime, date, timedelta
import pygsheets
import pandas as pd
import json
import io
from dateutil.relativedelta import relativedelta
import streamlit as st
import openai
from fpdf import FPDF
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import sqlite3
import urllib.parse  


openai.api_key = st.secrets["general"]["OPENAI_API_KEY"]

# ==== 1.a. CSV & COLUMN HELPERS ====
def safe_read_csv(local_path: str, remote_url: str) -> pd.DataFrame:
    """Try local CSV first, else fall back to remote URL."""
    if os.path.exists(local_path):
        return pd.read_csv(local_path)
    return pd.read_csv(remote_url)

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, strip and de-space all column names."""
    df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
    return df

def col_lookup(df: pd.DataFrame, name: str) -> str:
    """Find the actual column name for a logical key."""
    key = name.lower().replace(" ", "").replace("_", "")
    for c in df.columns:
        if c.lower().replace(" ", "").replace("_", "") == key:
            return c
    raise KeyError(f"Column '{name}' not found in DataFrame")

def safe_pdf(text: str) -> str:
    """Ensure strings are PDF-safe (Latin-1)."""
    return text.encode("latin-1", "replace").decode("latin-1")


def strip_leading_number(text):
    # Removes leading digits, dots, and spaces (e.g., "1. C" or "2) D" -> "C" or "D")
    return re.sub(r"^\s*\d+[\.\)]?\s*", "", text).strip()


# ==== 2. CONFIG / CONSTANTS ====
SCHOOL_NAME         = "Learn Language Education Academy"
school_sendgrid_key = st.secrets.get("general", {}).get("SENDGRID_API_KEY")
school_sender_email = st.secrets.get("general", {}).get("SENDER_EMAIL") or "Learngermanghana@gmail.com"

# ==== 3. REFERENCE ANSWERS ====
ref_answers = {
    # Put your full dictionary of ref_answers here...
}

# ==== 4. SQLITE DB HELPERS ====
@st.cache_resource
def init_sqlite_connection():
    conn = sqlite3.connect('students_scores.db', check_same_thread=False)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            studentcode TEXT UNIQUE,
            name TEXT,
            email TEXT,
            level TEXT
        )''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY,
            studentcode TEXT,
            assignment TEXT,
            score REAL,
            comments TEXT,
            date TEXT,
            level TEXT
        )''')
    conn.commit()
    return conn

def save_score_to_sqlite(score: dict):
    conn = init_sqlite_connection()
    cur = conn.cursor()
    cols = ",".join(score.keys())
    vals = tuple(score.values())
    q = f"INSERT INTO scores ({cols}) VALUES ({','.join(['?']*len(vals))})"
    cur.execute(q, vals)
    conn.commit()

@st.cache_data(ttl=600)
def fetch_scores_from_sqlite() -> pd.DataFrame:
    conn = init_sqlite_connection()
    df = pd.read_sql("SELECT studentcode,assignment,score,comments,date,level FROM scores", conn)
    df.columns = [c.lower() for c in df.columns]
    return df

def fetch_students_from_sqlite() -> pd.DataFrame:
    conn = init_sqlite_connection()
    df = pd.read_sql("SELECT studentcode,name,email,level FROM students", conn)
    df.columns = [c.lower() for c in df.columns]
    return df

# ==== 5. GENERAL HELPERS ====
def extract_code(selection: str, label: str = "student") -> str:
    if not selection:
        st.warning(f"Please select a {label}.")
        st.stop()
    match = re.search(r"\(([^()]+)\)\s*$", selection)
    if not match:
        st.warning(f"Could not parse {label} code.")
        st.stop()
    return match.group(1)

def choose_student(df: pd.DataFrame, levels: list, key_suffix: str) -> tuple:
    lvl = st.selectbox("Level", ["All"] + levels, key=f"level_{key_suffix}")
    filtered = df if lvl == "All" else df[df['level'] == lvl]
    sel = st.selectbox("Student", filtered['name'] + " (" + filtered['studentcode'] + ")", key=f"student_{key_suffix}")
    code = extract_code(sel)
    row = filtered[filtered['studentcode'] == code].iloc[0]
    return code, row

def safe_pdf(text):
    # Remove or replace any character not in latin-1
    return "".join(c if ord(c) < 256 else "?" for c in str(text))

def generate_pdf_report(
    name: str,
    level: str,
    history: pd.DataFrame,
    assignment: str = None,
    score_name: str = "",
    tutor_name: str = "",
    school_name: str = "",
    footer_text: str = "",
) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 15)
    # Header with school, student, level, tutor, etc.
    if school_name:
        pdf.cell(0, 10, safe_pdf(school_name), ln=True, align="C")
        pdf.ln(2)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 10, safe_pdf(f"Report for: {name} (Level: {level})"), ln=True)
    if tutor_name:
        pdf.set_font("Arial", "I", 11)
        pdf.cell(0, 8, safe_pdf(f"Tutor: {tutor_name}"), ln=True)
    if score_name:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, safe_pdf(f"Score/Assignment: {score_name}"), ln=True)
    pdf.ln(4)
    
    # Reference answers section
    if assignment and assignment in ref_answers and ref_answers[assignment]:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, safe_pdf(f"Reference Answers for: {assignment}"), ln=True)
        pdf.set_font("Arial", "", 11)
        for idx, ref in enumerate(ref_answers[assignment], 1):
            pdf.multi_cell(0, 8, safe_pdf(f"{idx}. {ref}"))
        pdf.ln(2)
    
    # Score history section
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Score History:", ln=True)
    pdf.set_font("Arial", "", 11)
    report_lines = [
        f"{row.assignment}: {row.score}/100"
        + (f" - Comments: {row.comments}" if row.comments else "")
        for row in history.itertuples()
    ]
    for line in report_lines:
        pdf.multi_cell(0, 8, safe_pdf(line))
        pdf.ln(1)
    pdf.ln(6)
    
    # Footer/Remark
    if footer_text:
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 10, safe_pdf(footer_text), ln=True, align="C")
    return pdf.output(dest="S").encode("latin-1", "replace")

def send_email_report(pdf_bytes: bytes, to: str, subject: str, html_content: str):
    try:
        msg = Mail(from_email=school_sender_email, to_emails=to, subject=subject, html_content=html_content)
        attachment = Attachment(
            FileContent(base64.b64encode(pdf_bytes).decode()),
            FileName(f"{to.replace('@','_')}_report.pdf"),
            FileType('application/pdf'),
            Disposition('attachment')
        )
        msg.attachment = attachment
        SendGridAPIClient(school_sendgrid_key).send(msg)
    except Exception as e:
        st.error(f"Email send failed: {e}")


# ==== 5. TABS LAYOUT ====
tabs = st.tabs([
    "📝 Pending",                 # 0
    "👩‍🎓 All Students",            # 1
    "💵 Expenses",                # 2
    "📲 Reminders",               # 3
    "📄 Contract",                # 4
    "📧 Send Email",              # 5 
    "📆 Schedule",                # 6
    "📝 Marking"                  # 7
])

# ==== 6. AGREEMENT TEMPLATE (Persisted in Session State) ====
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

# --- End of Stage 2 ---

with tabs[0]:

    st.title("🕒 Pending Students")

    # Load Data
    pending_csv_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"
    @st.cache_data(ttl=0)
    def load_pending():
        df = pd.read_csv(pending_csv_url, dtype=str)
        df_display = df.copy()
        df_search = df.copy()
        df_search.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df_search.columns]
        return df_display, df_search
    df_display, df_search = load_pending()

    # Universal Search
    search = st.text_input("🔎 Search any field (name, code, email, etc.)")
    if search:
        mask = df_search.apply(lambda row: row.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
        filt = df_display[mask]
    else:
        filt = df_display

    # Column Selector
    all_cols = list(filt.columns)
    selected_cols = st.multiselect(
        "Show columns (for easy viewing):", all_cols, default=all_cols[:6]
    )

    # Show Table (with scroll bar)
    st.dataframe(filt[selected_cols], use_container_width=True, height=400)

    # Download Always Includes All Columns
    st.download_button(
        "⬇️ Download all columns as CSV",
        filt.to_csv(index=False),
        file_name="pending_students.csv"
    )


# ==== 9. ALL STUDENTS TAB ====
with tabs[1]:
    st.title("👩‍🎓 All Students")

    # -- Google Sheets CSV Export Link --
    students_csv_url = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U"
        "/export?format=csv"
    )

    # --- Load Students Helper ---
    @st.cache_data(show_spinner=False)
    def load_students():
        df = pd.read_csv(students_csv_url)
        # Normalize columns (same helper as before)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df

    df_students = load_students()

    # --- Optional: Search/Filter ---
    search = st.text_input("🔍 Search students by name, code, or email...")
    if search:
        search = search.lower().strip()
        df_students = df_students[
            df_students.apply(lambda row: search in str(row).lower(), axis=1)
        ]

    # --- Show Student Table ---
    st.dataframe(df_students, use_container_width=True)
# ==== 10. TAB 2: EXPENSES AND FINANCIAL SUMMARY ====
with tabs[2]:
    st.title("💵 Expenses and Financial Summary")

    # ==== LOAD SHEETS ====
    # Expenses
    expenses_id = "1I5mGFcWbWdK6YQrJtabTg_g-XBEVaIRK1aMFm72vDEM"
    expenses_csv = f"https://docs.google.com/spreadsheets/d/{expenses_id}/export?format=csv"
    try:
        df_expenses = pd.read_csv(expenses_csv)
        df_expenses.columns = [c.strip().lower() for c in df_expenses.columns]
        st.success("✅ Loaded expenses from Google Sheets.")
    except Exception as e:
        st.error(f"❌ Could not load expenses sheet: {e}")
        df_expenses = pd.DataFrame(columns=["type", "item", "amount", "date"])

    # Students
    students_id = "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U"
    students_csv = f"https://docs.google.com/spreadsheets/d/{students_id}/export?format=csv"
    try:
        df_students = pd.read_csv(students_csv)
        df_students.columns = [c.strip().lower() for c in df_students.columns]
        st.success("✅ Loaded students from Google Sheets.")
    except Exception as e:
        st.error(f"❌ Could not load students sheet: {e}")
        df_students = pd.DataFrame(columns=["name", "paid", "balance"])

    # ==== ADD NEW EXPENSE ====
    with st.form("add_expense_form"):
        exp_type   = st.selectbox("Type", ["Bill","Rent","Salary","Marketing","Other"])
        exp_item   = st.text_input("Expense Item")
        exp_amount = st.number_input("Amount (GHS)", min_value=0.0, step=1.0)
        exp_date   = st.date_input("Date", value=date.today())
        submit     = st.form_submit_button("Add Expense")
        if submit and exp_item and exp_amount > 0:
            new_row = {"type": exp_type, "item": exp_item, "amount": exp_amount, "date": exp_date}
            df_expenses = pd.concat([df_expenses, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"✅ Recorded: {exp_type} – {exp_item}")
            df_expenses.to_csv("expenses_all.csv", index=False)
            st.experimental_rerun()

    # ==== FINANCIAL SUMMARY ====
    st.write("## 📊 Financial Summary")

    # Total Expenses
    total_expenses = pd.to_numeric(df_expenses["amount"], errors="coerce").fillna(0).sum() if not df_expenses.empty else 0.0

    # Total Income
    if "paid" in df_students.columns:
        total_income = pd.to_numeric(df_students["paid"], errors="coerce").fillna(0).sum()
    else:
        total_income = 0.0

    # Net Profit
    net_profit = total_income - total_expenses

    # Total Outstanding (Balance)
    if "balance" in df_students.columns:
        total_balance_due = pd.to_numeric(df_students["balance"], errors="coerce").fillna(0).sum()
    else:
        total_balance_due = 0.0

    # Student Count
    student_count = len(df_students) if not df_students.empty else 0

    # ==== DISPLAY SUMMARY ====
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Income (Paid)", f"GHS {total_income:,.2f}")
    col2.metric("💸 Total Expenses", f"GHS {total_expenses:,.2f}")
    col3.metric("🟢 Net Profit", f"GHS {net_profit:,.2f}")

    st.info(f"📋 **Students Enrolled:** {student_count}")
    st.info(f"🧾 **Outstanding Balances:** GHS {total_balance_due:,.2f}")

    # ==== PAGINATED EXPENSE TABLE ====
    st.write("### All Expenses")
    ROWS_PER_PAGE = 10
    total_rows    = len(df_expenses)
    total_pages   = (total_rows - 1) // ROWS_PER_PAGE + 1
    page = st.number_input(
        f"Page (1-{total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="exp_page"
    ) if total_pages > 1 else 1
    start = (page - 1) * ROWS_PER_PAGE
    end   = start + ROWS_PER_PAGE
    st.dataframe(df_expenses.iloc[start:end].reset_index(drop=True), use_container_width=True)

    # ==== EXPORT TO CSV ====
    csv_data = df_expenses.to_csv(index=False)
    st.download_button(
        "📁 Download Expenses CSV",
        data=csv_data,
        file_name="expenses_data.csv",
        mime="text/csv"
    )


with tabs[3]:
    st.title("📲 WhatsApp Reminders for Debtors")

    # --- 1. LOAD STUDENT DATA FROM GOOGLE SHEET ---
    students_csv_url = "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    @st.cache_data(ttl=0)
    def load_students():
        df = pd.read_csv(students_csv_url, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        return df
    df = load_students()
    st.caption("Preview of student data loaded from Google Sheet:")
    st.dataframe(df)

    def col_lookup(df, name):
        key = name.lower().replace(" ", "").replace("_", "")
        for c in df.columns:
            if c.lower().replace(" ", "").replace("_", "") == key:
                return c
        raise KeyError(f"Column '{name}' not found in DataFrame")

    # --- 2. FINANCIAL COLUMN LOOKUPS ---
    name_col  = col_lookup(df, "name")
    code_col  = col_lookup(df, "studentcode")
    phone_col = col_lookup(df, "phone")
    bal_col   = col_lookup(df, "balance")
    paid_col  = col_lookup(df, "paid")
    lvl_col   = col_lookup(df, "level")
    cs_col    = col_lookup(df, "contractstart")

    # --- 3. CLEAN DATA TYPES ---
    df[bal_col] = pd.to_numeric(df[bal_col], errors="coerce").fillna(0)
    df[paid_col] = pd.to_numeric(df[paid_col], errors="coerce").fillna(0)
    df[cs_col] = pd.to_datetime(df[cs_col], errors="coerce")
    df[phone_col] = df[phone_col].astype(str).str.replace(r"[^\d+]", "", regex=True)

    # --- 4. CALCULATE DUE DATE & DAYS LEFT ---
    df["due_date"] = df[cs_col] + pd.Timedelta(days=30)
    df["due_date_str"] = df["due_date"].dt.strftime("%d %b %Y")
    df["days_left"] = (df["due_date"] - pd.Timestamp.today()).dt.days

    # --- 5. FINANCIAL SUMMARY ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Students", len(df))
    m2.metric("Total Collected (GHS)", f"{df[paid_col].sum():,.2f}")
    m3.metric("Total Outstanding (GHS)", f"{df[bal_col].sum():,.2f}")

    st.markdown("---")

    # --- 6. FILTER/SEARCH ---
    show_all = st.toggle("Show all students (not just debtors)", value=False)
    search = st.text_input("Search by name, code, or phone", key="wa_search")
    selected_level = st.selectbox("Filter by Level", ["All"] + sorted(df[lvl_col].dropna().unique()), key="wa_level")

    filt = df.copy()
    if not show_all:
        filt = filt[filt[bal_col] > 0]
    if search:
        mask1 = filt[name_col].str.contains(search, case=False, na=False)
        mask2 = filt[code_col].str.contains(search, case=False, na=False)
        mask3 = filt[phone_col].str.contains(search, case=False, na=False)
        filt = filt[mask1 | mask2 | mask3]
    if selected_level != "All":
        filt = filt[filt[lvl_col] == selected_level]

    st.markdown("---")

    # --- 7. TABLE PREVIEW ---
    tbl = filt[[name_col, code_col, phone_col, lvl_col, bal_col, "due_date_str", "days_left"]].rename(columns={
        name_col: "Name", code_col: "Student Code", phone_col: "Phone",
        lvl_col: "Level", bal_col: "Balance (GHS)", "due_date_str": "Due Date", "days_left": "Days Left"
    })
    st.dataframe(tbl, use_container_width=True)

    # --- 8. PHONE FORMAT FUNCTION ---
    def clean_phone(phone):
        phone = str(phone).replace(" ", "").replace("-", "")
        if phone.startswith("+233"):
            return phone[1:]
        if phone.startswith("233"):
            return phone
        if phone.startswith("0") and len(phone) == 10:
            return "233" + phone[1:]
        # fallback: return as is
        return phone

    # --- 9. WHATSAPP LINK AND MESSAGE ---
    wa_template = st.text_area(
        "Custom WhatsApp Message Template",
        value="Hi {name}! Friendly reminder: your payment for the {level} class is due by {due}. {msg} Thank you!",
        help="You can use {name}, {level}, {due}, {bal}, {days}, {msg}"
    )

    links = []
    for _, row in filt.iterrows():
        phone = clean_phone(row[phone_col])
        # Balance & msg
        bal = f"GHS {row[bal_col]:,.2f}"
        due = row["due_date_str"]
        days = int(row["days_left"])
        if days >= 0:
            msg = f"You have {days} {'day' if days == 1 else 'days'} left to settle the {bal} balance."
        else:
            msg = f"Your payment is overdue by {abs(days)} {'day' if abs(days)==1 else 'days'}. Please settle as soon as possible."
        # Format the template
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

    # --- 10. LIST LINKS ---
    st.markdown("### Send WhatsApp Reminders")
    for i, row in df_links.iterrows():
        if row["WhatsApp Link"]:
            st.markdown(f"- **{row['Name']}** ([Send WhatsApp]({row['WhatsApp Link']}))")

    st.download_button(
        "📁 Download Reminder Links CSV",
        df_links[["Name", "Student Code", "Phone", "Level", "Balance (GHS)", "Due Date", "Days Left", "WhatsApp Link"]].to_csv(index=False),
        file_name="debtor_whatsapp_links.csv"
    )


# ==== 12. TAB 5: GENERATE CONTRACT & RECEIPT PDF FOR ANY STUDENT ====
with tabs[4]:
    st.title("📄 Generate Contract & Receipt PDF for Any Student")

    # --- Google Sheet as the ONLY source ---
    google_csv = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    )
    df = pd.read_csv(google_csv)
    df = normalize_columns(df)

    if df.empty:
        st.warning("No student data available.")
    else:
        def getcol(col): return col_lookup(df, col)

        name_col    = getcol("name")
        start_col   = getcol("contractstart")
        end_col     = getcol("contractend")
        paid_col    = getcol("paid")
        bal_col     = getcol("balance")
        code_col    = getcol("studentcode")
        phone_col   = getcol("phone")
        level_col   = getcol("level")

        # --- SEARCH BOX at the bottom (shown above dropdown) ---
        search_val = st.text_input(
            "Search students by name, code, phone, or level:", value="", key="pdf_tab_search"
        )

        # Filter students
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

        # 4. Editable fields before PDF generation
        default_paid    = float(row.get(paid_col, 0))
        default_balance = float(row.get(bal_col, 0))
        default_start   = pd.to_datetime(row.get(start_col, ""), errors="coerce").date() \
            if not pd.isnull(pd.to_datetime(row.get(start_col, ""), errors="coerce")) else date.today()
        default_end     = pd.to_datetime(row.get(end_col,   ""), errors="coerce").date() \
            if not pd.isnull(pd.to_datetime(row.get(end_col,   ""), errors="coerce")) else default_start + timedelta(days=30)

        st.subheader("Receipt Details")
        paid_input = st.number_input(
            "Amount Paid (GHS)", min_value=0.0, value=default_paid, step=1.0, key="paid_input"
        )
        balance_input = st.number_input(
            "Balance Due (GHS)", min_value=0.0, value=default_balance, step=1.0, key="balance_input"
        )
        total_input = paid_input + balance_input
        receipt_date = st.date_input("Receipt Date", value=date.today(), key="receipt_date")
        signature = st.text_input("Signature Text", value="Felix Asadu", key="receipt_signature")

        st.subheader("Contract Details")
        contract_start_input = st.date_input(
            "Contract Start Date", value=default_start, key="contract_start_input"
        )
        contract_end_input = st.date_input(
            "Contract End Date", value=default_end, key="contract_end_input"
        )
        course_length = (contract_end_input - contract_start_input).days

        st.subheader("Logo (optional)")
        logo_file = st.file_uploader(
            "Upload logo image", type=["png", "jpg", "jpeg"], key="logo_upload"
        )

        # 5. Generate PDF
        if st.button("Generate & Download PDF"):
            # Use current inputs
            paid    = paid_input
            balance = balance_input
            total   = total_input
            contract_start = contract_start_input
            contract_end   = contract_end_input

            pdf = FPDF()
            pdf.add_page()

            # Add logo if uploaded
            if logo_file:
                import tempfile
                ext = logo_file.name.split('.')[-1]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                tmp.write(logo_file.getbuffer())
                tmp.close()
                pdf.image(tmp.name, x=10, y=8, w=33)
                pdf.ln(25)

            # Payment status banner
            status = "FULLY PAID" if balance == 0 else "INSTALLMENT PLAN"
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(0, 128, 0)
            pdf.cell(0, 10, status, ln=True, align="C")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(5)

            # Receipt header
            pdf.set_font("Arial", size=14)
            pdf.cell(0, 10, f"{SCHOOL_NAME} Payment Receipt", ln=True, align="C")
            pdf.ln(10)

            # Receipt details
            pdf.set_font("Arial", size=12)
            for label, val in [
                ("Name",           selected_name),
                ("Student Code",   row.get(code_col, "")),
                ("Phone",          row.get(phone_col, "")),
                ("Level",          row.get(level_col, "")),
                ("Contract Start", contract_start),
                ("Contract End",   contract_end),
                ("Amount Paid",    f"GHS {paid:.2f}"),
                ("Balance Due",    f"GHS {balance:.2f}"),
                ("Total Fee",      f"GHS {total:.2f}"),
                ("Receipt Date",   receipt_date)
            ]:
                pdf.cell(0, 8, f"{label}: {val}", ln=True)
            pdf.ln(10)

            # Contract section
            pdf.ln(15)
            pdf.set_font("Arial", size=14)
            pdf.cell(0, 10, f"{SCHOOL_NAME} Student Contract", ln=True, align="C")
            pdf.set_font("Arial", size=12)
            pdf.ln(8)

            template = st.session_state.get("agreement_template", "")
            filled = (
                template
                .replace("[STUDENT_NAME]",     selected_name)
                .replace("[DATE]",             str(receipt_date))
                .replace("[CLASS]",            row.get(level_col, ""))
                .replace("[AMOUNT]",           str(total))
                .replace("[FIRST_INSTALLMENT]", f"{paid:.2f}")
                .replace("[SECOND_INSTALLMENT]",f"{balance:.2f}")
                .replace("[SECOND_DUE_DATE]",  str(contract_end))
                .replace("[COURSE_LENGTH]",    f"{course_length} days")
            )
            for line in filled.split("\n"):
                safe = safe_pdf(line)
                pdf.multi_cell(0, 8, safe)
            pdf.ln(10)

            # Signature
            pdf.cell(0, 8, f"Signed: {signature}", ln=True)

            # Download
            pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
            st.download_button(
                "📄 Download PDF",
                data=pdf_bytes,
                file_name=f"{selected_name.replace(' ', '_')}_receipt_contract.pdf",
                mime="application/pdf"
            )
            st.success("✅ PDF generated and ready to download.")


with tabs[5]:
    st.title("📧 Send Email (Quick)")

    # --- 1. Load student list from Google Sheets ---
    students_csv_url = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/"
        "export?format=csv"
    )
    try:
        df_students = pd.read_csv(students_csv_url)
    except Exception as e:
        st.error(f"❌ Could not load student list: {e}")
        df_students = pd.DataFrame(columns=["name", "email", "level", "contractstart", "student_code"])
    df_students = normalize_columns(df_students)
    name_col  = col_lookup(df_students, "name")
    email_col = col_lookup(df_students, "email")
    level_col = col_lookup(df_students, "level")
    code_col  = col_lookup(df_students, "student_code") if "student_code" in df_students.columns else "studentcode"
    start_col = col_lookup(df_students, "contractstart") if "contractstart" in df_students.columns else ""

    # --- 1b. Load score sheet (for assignment results) ---
    scores_csv_url = (
        "https://docs.google.com/spreadsheets/d/1BRb8p3Rq0VpFCLSwL4eS9tSgXBo9hSWzfW_J_7W36NQ/export?format=csv"
    )
    try:
        df_scores = pd.read_csv(scores_csv_url)
        df_scores = normalize_columns(df_scores)
    except Exception as e:
        df_scores = pd.DataFrame(columns=["studentcode","assignment","score","comments","date","level"])
        st.warning("⚠️ Could not load assignment scores. Assignment Results will be empty.")

    # --- 2. Template selector ---
    template_opts = ["Custom", "Welcome", "Payment Reminder", "Assignment Results"]
    selected_template = st.selectbox(
        "Template", template_opts, key="tab6_template"
    )

    # --- 3. Defaults per template ---
    subj_def = ""
    body_def = ""
    if selected_template == "Welcome":
        subj_def = "Welcome to Learn Language Education Academy!"
        body_def = (
            "Hello {name},<br><br>"
            "Welcome to Learn Language Education Academy! We have helped many students succeed, and we’re excited to support you as well.<br><br>"
            "<b>Your contract starts on the date indicated in the attached course schedule.</b> "
            "Please refer to the schedule for both your class start and end dates.<br><br>"
            "You can join your <b>{level}</b> class either in person or online via Zoom (link will be shared before class).<br><br>"
            "Attached is your course outline, so you can preview how the class will progress.<br><br>"
            "You will use our Falowen App (<a href='https://falowen.streamlit.app/'>falowen.streamlit.app</a>) "
            "to track your progress, see assignments, and practice your skills (log in with your student code or email).<br><br>"
            "Assignments, course books, and recorded lectures are all available in Google Classroom.<br><br>"
            "We wish you a great start and look forward to seeing your progress!<br><br>"
            "Best regards,<br>"
            "Felix Asadu<br>"
            "Learn Language Education Academy"
        )
    elif selected_template == "Payment Reminder":
        subj_def = "Friendly Payment Reminder"
        body_def = (
            "Hi {name},<br><br>"
            "Just a reminder: your balance for {level} is due soon.<br><br>"
            "Thank you!"
        )
    elif selected_template == "Assignment Results":
        subj_def = "Your Assignment Results"
        body_def = (
            "Hello {name},<br><br>"
            "Below are your latest assignment scores:<br><br>"
            "{results_table}<br><br>"
            "Best,<br>Learn Language Education Academy"
        )
    else:
        subj_def = ""
        body_def = ""

    # --- 4. Student search/filter at the bottom ---
    st.subheader("🔎 Search for Student")
    search_val = st.text_input("Search by name, email, or code", value="", key="tab6_search")
    if search_val:
        df_students_filtered = df_students[
            df_students[name_col].str.contains(search_val, case=False, na=False) |
            df_students[email_col].str.contains(search_val, case=False, na=False) |
            df_students[code_col].astype(str).str.contains(search_val, case=False, na=False)
        ]
    else:
        df_students_filtered = df_students

    student_options = [
        f"{row[name_col]} <{row[email_col]}>"
        for _, row in df_students_filtered.iterrows()
        if pd.notna(row[email_col]) and row[email_col] != ""
    ]
    selected_recipients = st.multiselect(
        "Recipients", student_options, key="tab6_recipients"
    )

    # --- 5. Compose ---
    st.subheader("Email Subject & Body")
    email_subject = st.text_input(
        "Email Subject",
        value=subj_def,
        key="tab6_email_subject"
    )
    email_body = st.text_area(
        "Email Body (HTML)",
        value=body_def,
        key="tab6_email_body",
        height=200
    )

    # --- 6. Preview before sending ---
    if selected_recipients:
        preview_nm = selected_recipients[0].split("<")[0].strip()
        preview_lvl = df_students.loc[df_students[name_col]==preview_nm, level_col].iloc[0] if preview_nm in df_students[name_col].values else ""
        preview_code = df_students.loc[df_students[name_col]==preview_nm, code_col].iloc[0] if preview_nm in df_students[name_col].values else ""
        results_table = ""
        if selected_template == "Assignment Results" and preview_code in df_scores['studentcode'].values:
            results = df_scores[df_scores['studentcode']==preview_code][["assignment","score"]].dropna()
            if not results.empty:
                results_table = "<table border=1><tr><th>Assignment</th><th>Score</th></tr>"
                for _, row in results.iterrows():
                    results_table += f"<tr><td>{row['assignment']}</td><td>{row['score']}</td></tr>"
                results_table += "</table>"
        else:
            results_table = ""
        st.markdown("##### Preview (for first recipient):")
        st.markdown(email_body.format(
            name=preview_nm,
            level=preview_lvl,
            results_table=results_table,
            start_date=""
        ), unsafe_allow_html=True)

    # --- 7. Attachment ---
    st.subheader("Attachment (optional)")
    attachment_file = st.file_uploader(
        "Upload file", type=None, key="tab6_attachment"
    )

    # --- 8. SendGrid config
    sendgrid_key = st.secrets["general"]["SENDGRID_API_KEY"]
    sender_email = st.secrets["general"]["SENDER_EMAIL"]

    # --- 9. Send button
    if st.button("Send Emails", key="tab6_send"):
        if not selected_recipients:
            st.warning("Select at least one recipient.")
        elif not email_subject or not email_body:
            st.warning("Subject and body cannot be empty.")
        else:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
            import base64

            successes, failures = [], []
            for pick in selected_recipients:
                nm, addr = pick.split("<")
                nm = nm.strip()
                addr = addr.strip(">").strip()
                lvl = df_students.loc[df_students[name_col]==nm, level_col].iloc[0] if nm in df_students[name_col].values else ""
                code = df_students.loc[df_students[name_col]==nm, code_col].iloc[0] if nm in df_students[name_col].values else ""
                results_table = ""
                if selected_template == "Assignment Results" and code in df_scores['studentcode'].values:
                    results = df_scores[df_scores['studentcode']==code][["assignment","score"]].dropna()
                    if not results.empty:
                        results_table = "<table border=1><tr><th>Assignment</th><th>Score</th></tr>"
                        for _, row in results.iterrows():
                            results_table += f"<tr><td>{row['assignment']}</td><td>{row['score']}</td></tr>"
                        results_table += "</table>"
                else:
                    results_table = ""

                # Always provide start_date as an empty string for format()
                try:
                    msg = Mail(
                        from_email=sender_email,
                        to_emails=addr,
                        subject=email_subject,
                        html_content=email_body.format(
                            name=nm,
                            level=lvl,
                            results_table=results_table,
                            start_date=""
                        )
                    )
                    # attach if present
                    if attachment_file:
                        data = attachment_file.read()
                        enc  = base64.b64encode(data).decode()
                        ftype = __import__("mimetypes").guess_type(attachment_file.name)[0] or "application/octet-stream"
                        attach = Attachment(
                            FileContent(enc),
                            FileName(attachment_file.name),
                            FileType(ftype),
                            Disposition("attachment")
                        )
                        msg.attachment = attach

                    sg = SendGridAPIClient(sendgrid_key)
                    sg.send(msg)
                    successes.append(addr)
                except Exception as e:
                    failures.append(f"{addr}: {e}")

            if successes:
                st.success(f"Sent to: {', '.join(successes)}")
            if failures:
                st.error(f"Failures: {', '.join(failures)}")

# ==== 14. TAB 6: COURSE SCHEDULE GENERATOR ====
with tabs[6]:
    st.markdown("""
    <div style='background:#e3f2fd;padding:1.2em 1em 0.8em 1em;border-radius:12px;margin-bottom:1em'>
      <h2 style='color:#1565c0;'>📆 <b>Intelligenter Kursplan-Generator (A1, A2, B1)</b></h2>
      <p style='font-size:1.08em;color:#333'>Erstellen Sie einen vollständigen, individuell angepassten Kursplan zum Download (TXT oder PDF) – <b>mit Ferien und flexiblem Wochenrhythmus!</b></p>
    </div>
    """, unsafe_allow_html=True)

    # ---- Schedule templates ----
    raw_schedule_a1 = [
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
    raw_schedule_a2 = [
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
    raw_schedule_b1 = [
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

    # ---- Step 1: Course level ----
    st.markdown("### 1️⃣ **Kursniveau wählen**")
    course_levels = {"A1": raw_schedule_a1, "A2": raw_schedule_a2, "B1": raw_schedule_b1}
    selected_level = st.selectbox("🗂️ **Kursniveau (A1/A2/B1):**", list(course_levels.keys()))
    topic_structure = course_levels[selected_level]
    st.markdown("---")

    # ---- Step 2: Basic info & breaks ----
    st.markdown("### 2️⃣ **Kursdaten, Ferien, Modus**")
    col1, col2 = st.columns([2,1])
    with col1:
        start_date = st.date_input("📅 **Kursstart**", value=date.today())
        holiday_dates = st.date_input("🔔 Ferien oder Feiertage (Holiday/Break Dates)", [], help="Kein Unterricht an diesen Tagen.")
    with col2:
        advanced_mode = st.toggle("⚙️ Erweiterter Wochen-Rhythmus (Custom weekly pattern)", value=False)
    st.markdown("---")

    # ---- Step 3: Weekly pattern ----
    st.markdown("### 3️⃣ **Unterrichtstage festlegen**")
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    default_days = ["Monday", "Tuesday", "Wednesday"]

    week_patterns = []
    if not advanced_mode:
        days_per_week = st.multiselect("📌 **Unterrichtstage wählen:**", options=days_of_week, default=default_days)
        for _ in topic_structure:
            week_patterns.append((len(_[1]), days_per_week))
    else:
        st.info("Für jede Woche individuelle Unterrichtstage einstellen.")
        for i, (week_label, sessions) in enumerate(topic_structure):
            with st.expander(f"{week_label}", expanded=True):
                week_days = st.multiselect(f"Unterrichtstage {week_label}", options=days_of_week, default=default_days, key=f"week_{i}_days")
                week_patterns.append((len(sessions), week_days or default_days))
    st.markdown("---")

    # ---- Generate dates skipping holidays ----
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

    if len(dates) < total_sessions:
        st.error("⚠️ **Nicht genug Unterrichtstage!** Passen Sie Ferien/Modus an.")

    # ---- Preview ----
    rows = [{"Week": wl, "Day": f"Day {i+1}", "Date": d.strftime("%A, %d %B %Y"), "Topic": tp}
            for i, ((wl, tp), d) in enumerate(zip(session_labels, dates))]
    df = pd.DataFrame(rows)
    st.markdown(f"""
    <div style='background:#fffde7;border:1px solid #ffe082;border-radius:10px;padding:1em;margin:1em 0'>
      <b>📝 Kursüberblick:</b>
      <ul>
        <li><b>Kurs:</b> {selected_level}</li>
        <li><b>Start:</b> {start_date.strftime('%A, %d %B %Y')}</li>
        <li><b>Sessions:</b> {total_sessions}</li>
        <li><b>Ferien:</b> {', '.join(d.strftime('%d.%m.%Y') for d in holiday_dates) or '–'}</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown("---")

    # ---- Filenames ----
    file_date = start_date.strftime("%Y-%m-%d")
    file_prefix = f"{selected_level}_{file_date}_course_schedule"

    # ---- TXT download ----
    txt = f"Learn Language Education Academy\nContact: 0205706589 | www.learngermanghana.com\nSchedule: {selected_level}\nStart: {start_date.strftime('%Y-%m-%d')}\n\n" + \
          "\n".join(f"- {r['Day']} ({r['Date']}): {r['Topic']}" for r in rows)
    st.download_button("📁 TXT Download", txt, file_name=f"{file_prefix}.txt")

    # ---- PDF download ----
    class ColorHeaderPDF(FPDF):
        def header(self):
            self.set_fill_color(21, 101, 192)
            self.set_text_color(255,255,255)
            self.set_font('Arial','B',14)
            self.cell(0,12,safe_pdf("Learn Language Education Academy – Course Schedule"),ln=1,align='C',fill=True)
            self.ln(2)
            self.set_text_color(0,0,0)

    pdf = ColorHeaderPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0,8, safe_pdf(f"Schedule: {selected_level}"))
    pdf.multi_cell(0,8, safe_pdf(f"Start: {start_date.strftime('%Y-%m-%d')}"))
    if holiday_dates:
        pdf.multi_cell(0,8, safe_pdf("Holidays: " + ", ".join(d.strftime("%d.%m.%Y") for d in holiday_dates)))
    pdf.ln(2)
    for r in rows:
        pdf.multi_cell(0,8, safe_pdf(f"{r['Day']} ({r['Date']}): {r['Topic']}"))
    pdf.ln(6)
    pdf.set_font("Arial",'I',11)
    pdf.cell(0,10, safe_pdf("Signed: Felix Asadu"), ln=1, align='R')

    st.download_button("📄 PDF Download",
                       data=pdf.output(dest='S').encode('latin-1'),
                       file_name=f"{file_prefix}.pdf",
                       mime="application/pdf")
    



# --- Google Sheet URLs (CSV export links) ---
students_csv_url = "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
ref_answers_url = "https://docs.google.com/spreadsheets/d/1CtNlidMfmE836NBh5FmEF5tls9sLmMmkkhewMTQjkBo/export?format=csv"

with tabs[7]:
    st.title("📝 Assignment Marking & Scores (AI Grading)")

    # --- Load Data ---
    @st.cache_data(show_spinner=False)
    def load_students():
        df = pd.read_csv(students_csv_url)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        if "student_code" in df.columns:
            df = df.rename(columns={"student_code": "studentcode"})
        return df

    @st.cache_data(show_spinner=False)
    def load_ref_answers():
        df = pd.read_csv(ref_answers_url, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        if "assignment" not in df.columns:
            raise Exception("No 'assignment' column found in reference answers sheet.")
        return df

    df_students = load_students()
    ref_df = load_ref_answers()

    # --- Select Assignment ---
    st.subheader("1. Choose Assignment")
    assignments = ref_df['assignment'].dropna().unique().tolist()
    assignment = st.selectbox("Assignment", assignments, key="tab7_assign")

    # --- Show Reference Answers ---
    if assignment:
        assignment_row = ref_df[ref_df['assignment'] == assignment]
        answer_cols = [col for col in assignment_row.columns if col.startswith('answer')]
        ref_answers = [str(assignment_row.iloc[0][col]) for col in answer_cols if pd.notnull(assignment_row.iloc[0][col]) and str(assignment_row.iloc[0][col]).strip() != '']
        if ref_answers:
            st.markdown("**Reference Answer(s):**")
            for i, ans in enumerate(ref_answers):
                st.info(f"**Answer {i+1}:** {ans}")
        else:
            st.warning("No reference answers for this assignment.")

    # --- Select Student ---
    st.subheader("2. Choose Student (for reporting only)")
    student_names = df_students['name'].dropna().tolist()
    student_name = st.selectbox("Student", student_names, key="tab7_student")

    # --- Paste Student Work ---
    st.subheader("3. Paste Student's Work")
    student_work = st.text_area("Paste student's answer here:", height=150, key="tab7_student_work")

    # --- AI Grading ---
    st.subheader("4. AI Marking")
    ai_feedback = ""
    if st.button("Mark with AI"):
        if not assignment or not student_work.strip():
            st.error("Select an assignment and paste student work first.")
        elif not ref_answers:
            st.error("No reference answer found for this assignment.")
        else:
            with st.spinner("AI is marking..."):
                ref_ans = ref_answers[0]  # Use first reference answer (customize as needed)
                prompt = f"""
You are a professional German language teacher. 
Reference answer for this assignment:

{ref_ans}

Here is the student's answer:

{student_work}

Please:
1. Give a mark out of 10 for content (does it answer the question?).
2. Give a mark out of 10 for grammar.
3. Give a mark out of 10 for vocabulary.
4. Briefly explain each score.
5. Give a total mark out of 100 with justification.
6. Suggest concrete improvements in 2-3 lines.

Output format:

Content: __/10 (explanation)
Grammar: __/10 (explanation)
Vocabulary: __/10 (explanation)
Suggestions: ...
Total: __/100 (explanation)
"""
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a professional German teacher and examiner."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=512,
                    temperature=0.3,
                )
                ai_feedback = response["choices"][0]["message"]["content"]
                st.success("AI marking complete!")

    if ai_feedback:
        st.markdown("### AI Grading Result")
        st.markdown(ai_feedback)

    # --- Allow copying or further use ---
    if ai_feedback:
        st.download_button(
            "Download Feedback as Text",
            data=ai_feedback,
            file_name=f"{student_name}_{assignment}_AI_marking.txt",
            key="tab7_dl_ai_feedback"
        )




