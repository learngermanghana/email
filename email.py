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
    "👩‍🎓 All Students",          # 1
    "💵 Expenses",                # 2
    "📲 Reminders",               # 3
    "📄 Contract",                # 4
    "📧 Send Email",              # 5 
    "📆 Schedule",                # 6
    "📝 Reference & Student Work" # 7
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

# ==== TAB 3: WHATSAPP REMINDERS FOR DEBTORS ====
with tabs[3]:
    st.title("📲 WhatsApp Reminders for Debtors")

    # --- Use the main student DataFrame (already loaded/cached) ---
    df = df_students.copy()

    # --- Clean and ensure correct columns ---
    try:
        name_col  = col_lookup(df, "name")
        code_col  = col_lookup(df, "studentcode")
        phone_col = col_lookup(df, "phone")
        bal_col   = col_lookup(df, "balance")
        paid_col  = col_lookup(df, "paid")
        lvl_col   = col_lookup(df, "level")
        cs_col    = col_lookup(df, "contractstart")
    except Exception as e:
        st.error(f"Missing column: {e}")
        st.stop()

    # --- Clean data types ---
    df[bal_col] = pd.to_numeric(df[bal_col], errors="coerce").fillna(0)
    df[paid_col] = pd.to_numeric(df[paid_col], errors="coerce").fillna(0)
    df[cs_col] = pd.to_datetime(df[cs_col], errors="coerce")
    df[phone_col] = df[phone_col].astype(str).str.replace(r"[^\d+]", "", regex=True)

    # --- Calculate due date and days left ---
    df["due_date"] = df[cs_col] + pd.Timedelta(days=30)
    df["due_date_str"] = df["due_date"].dt.strftime("%d %b %Y")
    df["days_left"] = (df["due_date"] - pd.Timestamp.today()).dt.days

    # --- Financial summary metrics ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Students", len(df))
    m2.metric("Total Collected (GHS)", f"{df[paid_col].sum():,.2f}")
    m3.metric("Total Outstanding (GHS)", f"{df[bal_col].sum():,.2f}")

    st.markdown("---")

    # --- Filter/search ---
    show_all = st.toggle("Show all students (not just debtors)", value=False)
    search = st.text_input("Search by name, code, or phone", key="wa_search")
    selected_level = st.selectbox("Filter by Level", ["All"] + sorted(df[lvl_col].dropna().unique()), key="wa_level")

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

    # --- Table preview ---
    tbl = filt[[name_col, code_col, phone_col, lvl_col, bal_col, "due_date_str", "days_left"]].rename(columns={
        name_col: "Name", code_col: "Student Code", phone_col: "Phone",
        lvl_col: "Level", bal_col: "Balance (GHS)", "due_date_str": "Due Date", "days_left": "Days Left"
    })
    st.dataframe(tbl, use_container_width=True)

    # --- WhatsApp message template ---
    wa_template = st.text_area(
        "Custom WhatsApp Message Template",
        value="Hi {name}! Friendly reminder: your payment for the {level} class is due by {due}. {msg} Thank you!",
        help="You can use {name}, {level}, {due}, {bal}, {days}, {msg}"
    )

    # --- WhatsApp links for all filtered students ---
    links = []
    for _, row in filt.iterrows():
        phone = clean_phone(row[phone_col])
        bal = f"GHS {row[bal_col]:,.2f}"
        due = row["due_date_str"]
        days = int(row["days_left"])
        msg = (f"You have {days} {'day' if days == 1 else 'days'} left to settle the {bal} balance."
               if days >= 0 else
               f"Your payment is overdue by {abs(days)} {'day' if abs(days)==1 else 'days'}. Please settle as soon as possible.")
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

    # --- Send WhatsApp Reminders links ---
    st.markdown("### Send WhatsApp Reminders")
    for i, row in df_links.iterrows():
        if row["WhatsApp Link"]:
            st.markdown(f"- **{row['Name']}** ([Send WhatsApp]({row['WhatsApp Link']}))")

    # --- Download links as CSV ---
    st.download_button(
        "📁 Download Reminder Links CSV",
        df_links[["Name", "Student Code", "Phone", "Level", "Balance (GHS)", "Due Date", "Days Left", "WhatsApp Link"]].to_csv(index=False),
        file_name="debtor_whatsapp_links.csv"
    )

# ==== TAB 4: CONTRACT & RECEIPT PDF GENERATOR ====
with tabs[4]:
    st.title("📄 Generate Contract & Receipt PDF for Any Student")

    # --- Use loaded student DataFrame ---
    df = df_students.copy()

    if df.empty:
        st.warning("No student data available.")
        st.stop()

    # --- Columns ---
    try:
        name_col    = col_lookup(df, "name")
        start_col   = col_lookup(df, "contractstart")
        end_col     = col_lookup(df, "contractend")
        paid_col    = col_lookup(df, "paid")
        bal_col     = col_lookup(df, "balance")
        code_col    = col_lookup(df, "studentcode")
        phone_col   = col_lookup(df, "phone")
        level_col   = col_lookup(df, "level")
    except Exception as e:
        st.error(f"Column lookup error: {e}")
        st.stop()

    # --- Search/filter box ---
    search_val = st.text_input(
        "Search students by name, code, phone, or level:", value="", key="pdf_tab_search"
    )

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

    # --- Editable fields before PDF generation ---
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

    # --- Generate PDF Button (and download) ---
    if st.button("Generate & Download PDF"):
        paid    = paid_input
        balance = balance_input
        total   = total_input
        contract_start = contract_start_input
        contract_end   = contract_end_input

        pdf = FPDF()
        pdf.add_page()

        # Add logo if uploaded
        if logo_file:
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
        
# ==== TAB 5: SEND EMAIL / LETTER (TEMPLATES, ATTACHMENTS, PDF, WATERMARK, QR) ====
with tabs[5]:
    import re

    st.title("📧 Send Email / Letter (Templates, Attachments, PDF, Watermark, QR)")
    st.subheader("Select Student")
    search_val = st.text_input(
        "Search students by name, code, or email", 
        value="", key="student_search"
    )
    # Filter the DataFrame based on search input
    if search_val:
        filtered_students = df_students[
            df_students["name"].str.contains(search_val, case=False, na=False)
            | df_students.get("studentcode", pd.Series(dtype=str)).astype(str).str.contains(search_val, case=False, na=False)
            | df_students.get("email", pd.Series(dtype=str)).astype(str).str.contains(search_val, case=False, na=False)
        ]
    else:
        filtered_students = df_students

    student_names = filtered_students["name"].dropna().unique().tolist()
    student_name = st.selectbox("Student Name", student_names)
    if not student_name:
        st.stop()
    # Use the filtered DataFrame to find the selected row
    student_row = filtered_students[filtered_students["name"] == student_name].iloc[0]
    student_level = student_row["level"]
    student_email = student_row.get("email", "")
    enrollment_start = pd.to_datetime(student_row.get("contractstart", date.today()), errors="coerce").date()
    enrollment_end = pd.to_datetime(student_row.get("contractend", date.today()), errors="coerce").date()
    payment = float(student_row.get("paid", 0))
    balance = float(student_row.get("balance", 0))
    payment_status = "Full Payment" if balance == 0 else "Installment Plan"
    student_code = student_row.get("studentcode", "")  # Adjust if your column is named differently
    student_link = f"https://falowen.streamlit.app/?code={student_code}" if student_code else "https://falowen.streamlit.app/"

    # ---- 2. Message Type Selection ----
    st.subheader("Choose Message Type")
    msg_type = st.selectbox("Type", [
        "Custom Message",
        "Welcome Message",
        "Assignment Results",
        "Letter of Enrollment"
    ])

    # ---- 3. Logo/Watermark/Extra Attachment ----
    st.subheader("Upload Logo and Watermark")
    logo_file = st.file_uploader("School Logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_up")
    watermark_file = st.file_uploader("Watermark Image (faded PNG recommended)", type=["png"], key="watermark_up")
    extra_attach = st.file_uploader("Additional Attachment (optional)", type=None, key="extra_attach")

    # ---- 4. Compose/Preview Message ----
    st.subheader("Compose/Preview Message")
    if msg_type == "Welcome Message":
        body_default = (
            f"Hello {student_name},<br><br>"
            f"Welcome to Learn Language Education Academy! We have helped many students succeed, and we’re excited to support you as well.<br><br>"
            f"We have attached your letter of enrollment in this document<br><br>"
            f"<b>Your contract starts on {enrollment_start.strftime('%d %B %Y')}.</b> "
            f"You can join your <b>{student_level}</b> class in person or online (Zoom link will be shared before class).<br><br>"
            f"<b>Your payment status: {payment_status}.</b> Paid: GHS {payment:.2f} / Balance: GHS {balance:.2f}<br><br>"
            f"All your course materials and assignments are on our <a href='{student_link}'>Falowen App</a>.<br><br>"
            f"We wish you a great start and look forward to your progress!<br><br>"
        )
    elif msg_type == "Letter of Enrollment":
        body_default = (
            f"To Whom It May Concern,<br><br>"
            f"This is to certify that {student_name} is officially enrolled in the {student_level} programme at Learn Language Education Academy.<br>"
            f"Enrollment valid from {enrollment_start.strftime('%-m/%-d/%Y')} to {enrollment_end.strftime('%-m/%-d/%Y')}.<br><br>"
            f"Our institution is officially registered with Business Registration Number {BUSINESS_REG},<br>"
            f"in accordance with the Registration of Business Names Act, 1962 (No.151).<br><br>"
            f"If you require further confirmation, please contact us.<br><br>"
        )
    elif msg_type == "Assignment Results":
        # Assignment details placeholder
        body_default = (
            f"Hello {student_name},<br><br>"
            f"Below are your latest assignment results (please check the Falowen App for full details):<br>"
            f"<ul><li>Assignment 1: 85%</li><li>Assignment 2: 90%</li></ul>"
            f"Best regards,<br>Learn Language Education Academy"
        )
    else:
        body_default = ""

    email_subject = st.text_input("Subject", value=f"{msg_type} - {student_name}")
    email_body = st.text_area("Email Body (HTML supported)", value=body_default, height=220)

    # ---- 4b. Message Preview ----
    st.markdown("**Preview Message (as student will see):**")
    st.markdown(email_body, unsafe_allow_html=True)

    # ---- 5. Generate PDF Button (and preview) ----
    st.subheader("PDF Preview & Download")

    class LetterPDF(FPDF):
        def header(self):
            # Logo (if uploaded)
            if logo_file is not None:
                ext = logo_file.name.split('.')[-1]
                logo_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                logo_tmp.write(logo_file.read())
                logo_tmp.close()
                self.image(logo_tmp.name, x=10, y=8, w=28)
            # School name, info
            self.set_font('Arial', 'B', 16)
            self.cell(0, 9, safe_pdf(SCHOOL_NAME), ln=True, align='C')
            self.set_font('Arial', '', 11)
            self.cell(0, 7, safe_pdf(f"{SCHOOL_WEBSITE} | {SCHOOL_PHONE} | {SCHOOL_ADDRESS}"), ln=True, align='C')
            self.set_font('Arial', 'I', 10)
            self.cell(0, 7, safe_pdf(f"Business Registration Number: {BUSINESS_REG}"), ln=True, align='C')
            self.ln(3)
            # Thin gray line
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.5)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(6)
        def watermark(self):
            if watermark_file is not None:
                ext = watermark_file.name.split('.')[-1]
                watermark_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                watermark_tmp.write(watermark_file.read())
                watermark_tmp.close()
                # Faint watermark in the center (width=110mm)
                self.image(watermark_tmp.name, x=48, y=75, w=110)
        def footer(self):
            # QR Code
            qr_tmp = make_qr_code(SCHOOL_WEBSITE)
            self.image(qr_tmp, x=180, y=275, w=18)  # Bottom right
            self.set_y(-18)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, safe_pdf("This letter is computer generated and valid without a signature."), 0, 0, 'C')

    pdf = LetterPDF()
    pdf.add_page()
    pdf.watermark()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 8, safe_pdf(re.sub(r"<br\s*/?>", "\n", email_body)), align="L")
    pdf.ln(6)
    if msg_type == "Letter of Enrollment":
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, "Yours sincerely,", ln=True)
        pdf.cell(0, 7, "Felix Asadu", ln=True)
        pdf.cell(0, 7, "Director", ln=True)
        pdf.cell(0, 7, safe_pdf(SCHOOL_NAME), ln=True)

    # FIX: fpdf2 returns bytes directly; no encode needed!
    pdf_bytes = pdf.output(dest="S")

    st.download_button(
        "📄 Download Letter/PDF", 
        data=pdf_bytes, 
        file_name=f"{student_name.replace(' ', '_')}_{msg_type.replace(' ','_')}.pdf", 
        mime="application/pdf"
    )
    st.caption("You can share this PDF on WhatsApp or by email.")

    # ---- 6. Email Option ----
    st.subheader("Send Email (with or without PDF)")
    attach_pdf = st.checkbox("Attach the generated PDF?")
    recipient_email = st.text_input("Recipient Email", value=student_email)
    if st.button("Send Email Now"):
        # Extra attachment if any
        extra_files = []
        if extra_attach:
            file_bytes = extra_attach.read()
            extra_files.append((file_bytes, extra_attach.name, extra_attach.type or "application/octet-stream"))

        # Compose attachments
        pdf_to_attach = pdf_bytes if attach_pdf else None
        # Use improved helper for attachments
        success = send_email_report(
            pdf_to_attach,
            recipient_email,
            email_subject,
            email_body,
            extra_attachments=extra_files
        )
        if success:
            st.success(f"Email sent to {recipient_email}!")
            
# ==== TAB 6: COURSE SCHEDULE GENERATOR ====
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

#
    
# ==== TAB 7: REFERENCE & STUDENT WORK SHARE ====
with tabs[7]:
    st.title("📝 Reference & Student Work Share")

    # --- Load Data ---
    @st.cache_data(show_spinner=False)
    def load_students():
        df = pd.read_csv(students_csv_url)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        if "student_code" in df.columns:
            df = df.rename(columns={"student_code": "studentcode"})
        return df
    df_students = load_students()

    @st.cache_data(ttl=0)
    def load_ref_answers():
        df = pd.read_csv(ref_answers_url, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        if "assignment" not in df.columns:
            raise Exception("No 'assignment' column found in reference answers sheet.")
        return df
    ref_df = load_ref_answers()

    # --- Student search and select ---
    st.subheader("1. Search & Select Student")
    def col_lookup(df, name):
        key = name.lower().replace(" ", "").replace("_", "")
        for c in df.columns:
            if c.lower().replace(" ", "").replace("_", "") == key:
                return c
        raise KeyError(f"Column '{name}' not found in DataFrame")

    name_col, code_col = col_lookup(df_students, "name"), col_lookup(df_students, "studentcode")
    search_student = st.text_input("Type student name or code...")
    students_filtered = df_students[
        df_students[name_col].str.contains(search_student, case=False, na=False) |
        df_students[code_col].astype(str).str.contains(search_student, case=False, na=False)
    ] if search_student else df_students

    student_list = students_filtered[name_col] + " (" + students_filtered[code_col].astype(str) + ")"
    chosen = st.selectbox("Select Student", student_list, key="tab7_single_student")

    if not chosen or "(" not in chosen:
        st.warning("No student selected or wrong student list format.")
        st.stop()
    student_code = chosen.split("(")[-1].replace(")", "").strip()
    student_row = students_filtered[students_filtered[code_col] == student_code].iloc[0]
    st.markdown(f"**Selected:** {student_row[name_col]} ({student_code})")
    student_level = student_row['level'] if 'level' in student_row else ""

    # --- Assignment search and select ---
    st.subheader("2. Select Assignment")
    available_assignments = ref_df['assignment'].dropna().unique().tolist()
    search_assign = st.text_input("Type assignment title...", key="tab7_search_assign")
    filtered = [a for a in available_assignments if search_assign.lower() in str(a).lower()]
    if not filtered:
        st.info("No assignments match your search.")
        st.stop()
    assignment = st.selectbox("Select Assignment", filtered, key="tab7_assign_select")

    # --- REFERENCE ANSWERS (TABS + COMBINED BOX) ---
    st.subheader("3. Reference Answer (from Google Sheet)")
    ref_answers = []
    answer_cols = []
    if assignment:
        assignment_row = ref_df[ref_df['assignment'] == assignment]
        if not assignment_row.empty:
            answer_cols = [col for col in assignment_row.columns if col.startswith('answer')]
            answer_cols = [col for col in answer_cols if pd.notnull(assignment_row.iloc[0][col]) and str(assignment_row.iloc[0][col]).strip() != '']
            ref_answers = [str(assignment_row.iloc[0][col]) for col in answer_cols]

    # Show dynamic tabs if multiple answers, else single box
    if ref_answers:
        if len(ref_answers) == 1:
            st.markdown("**Reference Answer:**")
            st.write(ref_answers[0])
        else:
            tab_objs = st.tabs([f"Answer {i+1}" for i in range(len(ref_answers))])
            for i, ans in enumerate(ref_answers):
                with tab_objs[i]:
                    st.write(ans)
        answers_combined_str = "\n".join([f"{i+1}. {ans}" for i, ans in enumerate(ref_answers)])
        answers_combined_html = "<br>".join([f"{i+1}. {ans}" for i, ans in enumerate(ref_answers)])
    else:
        answers_combined_str = "No answer available."
        answers_combined_html = "No answer available."
        st.info("No reference answer available.")

    # --- STUDENT WORK + AI COPY ZONE ---
    st.subheader("4. Paste Student Work (for your manual cross-check or ChatGPT use)")
    student_work = st.text_area("Paste the student's answer here:", height=140, key="tab7_student_work")

    # --- Combined copy box ---
    st.subheader("5. Copy Zone (Reference + Student Work for AI/manual grading)")
    combined_text = (
        "Reference answer:\n" +
        answers_combined_str +
        "\n\nStudent answer:\n" +
        student_work
    )
    st.code(combined_text, language="markdown")
    st.info("Copy this block and paste into ChatGPT or your AI tool for checking.")

    # --- Copy buttons ---
    st.write("**Quick Copy:**")
    st.download_button("📋 Copy Only Reference Answer (txt)", data=answers_combined_str, file_name="reference_answer.txt", mime="text/plain", key="copy_reference")
    st.download_button("📋 Copy Both (Reference + Student)", data=combined_text, file_name="ref_and_student.txt", mime="text/plain", key="copy_both")

    st.divider()

    # --- EMAIL SECTION ---
    st.subheader("6. Send Reference Answer to Student by Email")
    default_email = student_row.get('email', '') if 'email' in student_row else ""
    to_email = st.text_input("Recipient Email", value=default_email, key="tab7_email")
    subject = st.text_input("Subject", value=f"{student_row[name_col]} - {assignment} Reference Answer", key="tab7_subject")

    ref_ans_email = f"<b>Reference Answers:</b><br>{answers_combined_html}<br>"

    # Only share reference, not the student work!
    body = st.text_area(
        "Message (HTML allowed)",
        value=(
            f"Hello {student_row[name_col]},<br><br>"
            f"Here is the reference answer for your assignment <b>{assignment}</b>.<br><br>"
            f"{ref_ans_email}"
            "Thank you<br>Learn Language Education Academy"
        ),
        key="tab7_body"
    )
    send_email = st.button("📧 Email Reference", key="tab7_send_email")

    if send_email:
        if not to_email or "@" not in to_email:
            st.error("Please enter a valid recipient email address.")
        else:
            try:
                # Make sure you have your send_email_report function ready!
                send_email_report(None, to_email, subject, body)  # No PDF attached, just reference
                st.success(f"Reference sent to {to_email}!")
            except Exception as e:
                st.error(f"Failed to send email: {e}")

    # --- WhatsApp Share Section ---
    st.subheader("7. Share Reference via WhatsApp")
    # Try to get student's phone automatically from any relevant column
    wa_phone = ""
    wa_cols = [c for c in student_row.index if "phone" in c]
    for c in wa_cols:
        v = str(student_row[c])
        if v.startswith("233") or v.startswith("0") or v.isdigit():
            wa_phone = v
            break
    wa_phone = st.text_input("WhatsApp Number (International format, e.g., 233245022743)", value=wa_phone, key="tab7_wa_number")

    ref_ans_wa = "*Reference Answers:*\n" + answers_combined_str + "\n"

    default_wa_msg = (
        f"Hello {student_row[name_col]},\n\n"
        f"Here is the reference answer for your assignment: *{assignment}*\n"
        f"{ref_ans_wa}\n"
        "Open my results and resources on the Falowen app for scores and full comment.\n"
        "Don't forget to click refresh for latest results for your new scores to show.\n"
        "Thank you!\n"
        "Happy learning!"
    )
    wa_message = st.text_area(
        "WhatsApp Message (edit before sending):",
        value=default_wa_msg, height=180, key="tab7_wa_message_edit"
    )

    wa_num_formatted = wa_phone.strip().replace(" ", "").replace("-", "")
    if wa_num_formatted.startswith("0"):
        wa_num_formatted = "233" + wa_num_formatted[1:]
    elif wa_num_formatted.startswith("+"):
        wa_num_formatted = wa_num_formatted[1:]
    elif not wa_num_formatted.startswith("233"):
        wa_num_formatted = "233" + wa_num_formatted[-9:]  # fallback for local numbers

    wa_link = (
        f"https://wa.me/{wa_num_formatted}?text={urllib.parse.quote(wa_message)}"
        if wa_num_formatted.isdigit() and len(wa_num_formatted) >= 11 else None
    )

    if wa_link:
        st.markdown(
            f'<a href="{wa_link}" target="_blank">'
            f'<button style="background-color:#25d366;color:white;border:none;padding:10px 20px;border-radius:5px;font-size:16px;cursor:pointer;">'
            '📲 Share Reference on WhatsApp'
            '</button></a>',
            unsafe_allow_html=True
        )
    else:
        st.info("Enter a valid WhatsApp number (233XXXXXXXXX or 0XXXXXXXXX).")

# ==== TAB 8: MARKING & STUDENT RESULTS (with WhatsApp sharing) ====
with tabs[8]:
    st.title("📝 Marking & Student Results (Quick Mark, Save, Export)")

    # --- Load Data ---
    @st.cache_data(show_spinner=False)
    def load_students():
        df = pd.read_csv(students_csv_url)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        if "student_code" in df.columns:
            df = df.rename(columns={"student_code": "studentcode"})
        return df
    df_students = load_students()

    # --- Student Search and Selection ---
    st.subheader("1. Search & Select Student")
    search = st.text_input("Student name, code or email...", key="mark_search")
    if search:
        filtered = df_students[
            df_students["name"].str.contains(search, case=False, na=False) |
            df_students.get("studentcode", pd.Series(dtype=str)).astype(str).str.contains(search, case=False, na=False) |
            df_students.get("email", pd.Series(dtype=str)).astype(str).str.contains(search, case=False, na=False)
        ]
    else:
        filtered = df_students

    if filtered.empty:
        st.warning("No students match your search.")
        st.stop()
    names = filtered["name"].tolist()
    selected_name = st.selectbox("Select Student", names)
    student_row = filtered[filtered["name"] == selected_name].iloc[0]
    student_code = student_row.get("studentcode", "")
    student_email = student_row.get("email", "")
    student_level = student_row.get("level", "")
    student_phone = student_row.get("phone", "")

    # --- Assignment/Assessment ---
    st.subheader("2. Assignment/Assessment Title")
    assignment = st.text_input("Assignment Title (e.g. 'Schreiben 1', 'Quiz 3')", key="mark_assignment")
    if not assignment:
        st.stop()

    # --- Scoring & Comment ---
    st.subheader("3. Mark & Comment")
    score = st.slider("Score (0-100%)", min_value=0, max_value=100, value=80, step=1)
    comments = st.text_area("Comments (optional)", height=100, key="mark_comment")
    mark_date = st.date_input("Date", value=date.today(), key="mark_date")
    mark_level = st.text_input("Level", value=student_level, key="mark_level")

    # --- Save Mark ---
    if st.button("💾 Save Mark to Database"):
        record = {
            "studentcode": student_code,
            "assignment": assignment,
            "score": float(score),
            "comments": comments,
            "date": mark_date.strftime("%Y-%m-%d"),
            "level": mark_level
        }
        try:
            save_score_to_sqlite(record)
            st.success("Score saved successfully.")
        except Exception as e:
            st.error(f"Error saving score: {e}")

    st.markdown("---")

    # --- View All Marks for This Student ---
    st.subheader("4. Student's Results History")
    @st.cache_data(ttl=600)
    def fetch_scores(studentcode):
        df = fetch_scores_from_sqlite()
        return df[df['studentcode'] == studentcode].sort_values("date", ascending=False)
    if student_code:
        df_scores = fetch_scores(student_code)
        if not df_scores.empty:
            st.dataframe(df_scores, use_container_width=True)
        else:
            st.info("No previous results found for this student.")

    # --- Export to CSV ---
    if not df_scores.empty:
        csv_data = df_scores.to_csv(index=False)
        st.download_button(
            "📁 Download Student's Results CSV",
            data=csv_data,
            file_name=f"{selected_name.replace(' ', '_')}_results.csv",
            mime="text/csv"
        )

    # --- Quick PDF Report ---
    if st.button("📄 Generate PDF Report"):
        pdf_bytes = generate_pdf_report(
            name=selected_name,
            level=mark_level,
            history=df_scores,
            assignment=assignment,
            score_name=assignment,
            tutor_name="Felix Asadu",
            school_name=SCHOOL_NAME,
            footer_text=f"Report generated on {mark_date.strftime('%d %B %Y')}"
        )
        st.download_button(
            "📄 Download PDF",
            data=pdf_bytes,
            file_name=f"{selected_name.replace(' ', '_')}_report.pdf",
            mime="application/pdf"
        )

    # --- Quick Email Send ---
    if st.button("📧 Email Report to Student"):
        email_subject = f"{selected_name} - {assignment} Results"
        email_body = (
            f"Hello {selected_name},<br><br>"
            f"Here is your results report for the assignment <b>{assignment}</b>.<br>"
            f"See attached PDF for full details.<br><br>"
            "Thank you!<br>Learn Language Education Academy"
        )
        pdf_bytes = generate_pdf_report(
            name=selected_name,
            level=mark_level,
            history=df_scores,
            assignment=assignment,
            score_name=assignment,
            tutor_name="Felix Asadu",
            school_name=SCHOOL_NAME,
            footer_text=f"Report generated on {mark_date.strftime('%d %B %Y')}"
        )
        try:
            send_email_report(pdf_bytes, student_email, email_subject, email_body)
            st.success(f"Report emailed to {student_email}!")
        except Exception as e:
            st.error(f"Error sending email: {e}")

    # --- Quick WhatsApp Share ---
    st.markdown("---")
    st.subheader("📲 Share Results via WhatsApp")

    # WhatsApp number (allow user to edit)
    wa_num_input = st.text_input("WhatsApp Number (233XXXXXXXXX or 0XXXXXXXXX)", value=student_phone, key="wa_marking_number")
    # Format number
    wa_num = wa_num_input.strip().replace(" ", "").replace("-", "")
    if wa_num.startswith("0"):
        wa_num = "233" + wa_num[1:]
    elif wa_num.startswith("+"):
        wa_num = wa_num[1:]
    elif not wa_num.startswith("233"):
        wa_num = "233" + wa_num[-9:]

    # WhatsApp message
    wa_message = (
        f"Hello {selected_name},\n\n"
        f"Here are your results for *{assignment}* ({mark_level}):\n"
        f"Score: {score}/100\n"
        f"Comments: {comments or '-'}\n\n"
        "Check your email for the detailed PDF report!\n"
        "Thank you!\n"
        "Learn Language Education Academy"
    )

    wa_link = (
        f"https://wa.me/{wa_num}?text={urllib.parse.quote(wa_message)}"
        if wa_num.isdigit() and len(wa_num) >= 11 else None
    )

    if wa_link:
        st.markdown(
            f'<a href="{wa_link}" target="_blank">'
            f'<button style="background-color:#25d366;color:white;border:none;padding:10px 20px;border-radius:5px;font-size:16px;cursor:pointer;">'
            '📲 Share Results on WhatsApp'
            '</button></a>',
            unsafe_allow_html=True
        )
    else:
        st.info("Enter a valid WhatsApp number (233XXXXXXXXX or 0XXXXXXXXX).")
