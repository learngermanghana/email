# ==== IMPORTS ====
import os
import re
import base64
import requests
import tempfile
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
    "📝 Pending",                # 0
    "👩‍🎓 All Students",           # 1
    "💵 Expenses",               # 2
    "📲 Reminders",              # 3
    "📄 Contract",               # 4
    "📧 Send Email"              # 5 
    
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

# ==== TAB 3: WHATSAPP REMINDERS ====
with tabs[3]:
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

    # --- Table Preview ---
    tbl = filt[[name_col, code_col, phone_col, lvl_col, bal_col, "due_date_str", "days_left"]].rename(columns={
        name_col: "Name", code_col: "Student Code", phone_col: "Phone",
        lvl_col: "Level", bal_col: "Balance (GHS)", "due_date_str": "Due Date", "days_left": "Days Left"
    })
    st.dataframe(tbl, use_container_width=True)

    # --- WhatsApp Message Template ---
    wa_template = st.text_area(
        "Custom WhatsApp Message Template",
        value="Hi {name}! Friendly reminder: your payment for the {level} class is due by {due}. {msg} Thank you!",
        help="You can use {name}, {level}, {due}, {bal}, {days}, {msg}"
    )

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


with tabs[4]:
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

    search_val = st.text_input(
        "Search students by name, code, phone, or level:", 
        value="", key="pdf_tab_search_contract"
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

with tabs[5]:
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
    search_val = st.text_input(
        "Search students by name, code, or email",
        value="", key="student_search"
    )
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

    email_subject = st.text_input("Subject", value=f"{msg_type} - {student_name}", key="email_subject")
    email_body    = st.text_area("Email Body (HTML supported)", value=body_default, key="email_body", height=220)

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

    # ---- 6. Email Option ----
    st.subheader("Send Email (with or without PDF)")
    attach_pdf     = st.checkbox("Attach the generated PDF?", key="attach_pdf")
    recipient_email = st.text_input("Recipient Email", value=student_email, key="recipient_email")
    if st.button("Send Email Now", key="send_email"):
        msg = Mail(
            from_email=SENDER_EMAIL,
            to_emails=recipient_email,
            subject=email_subject,
            html_content=email_body
        )
        if attach_pdf:
            msg.add_attachment(
                Attachment(
                    FileContent(base64.b64encode(pdf_bytes).decode()),
                    FileName(f"{student_name.replace(' ','_')}_{msg_type.replace(' ','_')}.pdf"),
                    FileType("application/pdf"),
                    Disposition("attachment")
                )
            )
        if extra_attach:
            fb = extra_attach.read()
            msg.add_attachment(
                Attachment(
                    FileContent(base64.b64encode(fb).decode()),
                    FileName(extra_attach.name),
                    FileType(extra_attach.type or "application/octet-stream"),
                    Disposition("attachment")
                )
            )
        try:
            SendGridAPIClient(SENDGRID_KEY).send(msg)
            st.success(f"Email sent to {recipient_email}!")
        except Exception as e:
            st.error(f"Email send failed: {e}")

with tabs[5]:
    # ---- PDF-safe helper ----
    def safe_pdf(text):
        return "".join(c if ord(c)<256 else "?" for c in str(text or ""))

    # ---- QR code helper ----
    def make_qr_code(url):
        import qrcode, tempfile
        img = qrcode.make(url)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(tmp.name)
        return tmp.name

    st.title("📧 Send Email / Letter")
    # --- Select Student ---
    search_val = st.text_input("Search students by name/code/email", key="student_search")
    df = df_students.copy()
    if search_val:
        mask = (
            df["name"].str.contains(search_val, case=False, na=False) |
            df["studentcode"].str.contains(search_val, case=False, na=False) |
            df.get("email", pd.Series(dtype=str)).str.contains(search_val, case=False, na=False)
        )
        df = df[mask]
    student_list = df["name"].dropna().tolist()
    student_name = st.selectbox("Student Name", student_list, key="student_select")
    if not student_name:
        st.stop()
    row = df[df["name"]==student_name].iloc[0]
    level      = row["level"]
    email      = row.get("email","")
    start_date = pd.to_datetime(row.get("contractstart", date.today())).date()
    end_date   = pd.to_datetime(row.get("contractend",   date.today())).date()
    paid       = float(row.get("paid",0))
    bal        = float(row.get("balance",0))

    # --- Message Type ---
    msg_type = st.selectbox("Type", [
        "Welcome Message",
        "Letter of Enrollment",
        "Assignment Results",
        "Outstanding Balance Notice",
        "Course Completion Letter",
        "Custom Message"
    ], key="msg_type")

    # --- Default Bodies (plain‑ASCII) ---
    if msg_type=="Welcome Message":
        email_body = (
            f"Dear {student_name},\n\n"
            "Welcome to Learn Language Education Academy! We’re excited to support you.\n"
            f"Your {level} course starts on {start_date:%d %B %Y}.\n"
            f"Payment status: {'Full Payment' if bal==0 else 'Installment Plan'}. "
            f"Paid: GHS {paid:.2f} / Balance: GHS {bal:.2f}.\n"
            "Visit the Falowen App: https://falowen.streamlit.app/\n\n"
            "Best regards,\n"
            "Felix Asadu\n"
            "Director"
        )
    elif msg_type=="Letter of Enrollment":
        email_body = (
            "To Whom It May Concern,\n\n"
            f"This certifies that {student_name} is enrolled in the {level} programme.\n"
            f"Period: {start_date:%m/%d/%Y} to {end_date:%m/%d/%Y}.\n"
            f"Registered under BN173410224.\n\n"
            "If you require confirmation, please contact us at 0205706589 or office@learngermanghana.com.\n\n"
            "Yours sincerely,\n"
            "Felix Asadu\n"
            "Director"
        )
    elif msg_type=="Assignment Results":
        email_body = (
            f"Hello {student_name},\n\n"
            "Your latest assignment results:\n"
            " - Assignment 1: 85%\n"
            " - Assignment 2: 90%\n\n"
            "Keep up the great work!\n\n"
            "Regards,\n"
            "Learn Language Education Academy"
        )
    elif msg_type=="Outstanding Balance Notice":
        email_body = (
            f"Dear {student_name},\n\n"
            f"Our records show an outstanding balance of GHS {bal:.2f}. "
            "Please settle this at your earliest convenience.\n\n"
            "Thank you,\n"
            "Learn Language Education Academy"
        )
    elif msg_type=="Course Completion Letter":
        email_body = (
            f"Dear {student_name},\n\n"
            f"Congratulations on completing the {level} course! Your dedication has paid off.\n\n"
            "If you’re interested in advancing to the next level, "
            "please visit our upcoming classes page for the latest details and registration dates:\n"
            "https://www.learngermanghana.com/upcoming-classes\n\n"
            "Wishing you continued success!\n\n"
            "Warm regards,\n"
            "Felix Asadu\n"
            "Director"
        )
    else:
        email_body = ""

    # --- Subject & Preview ---
    subject = st.text_input("Subject", f"{msg_type} - {student_name}", key="email_subj")
    st.subheader("Preview:")
    st.code(email_body)

    # ---- PDF Generation & Download ----
    st.subheader("PDF Preview & Download")
    logo_url = "https://drive.google.com/uc?export=download&id=1xLTtiCbEeHJjrASvFjBgfFuGrgVzg6wU"
    class LetterPDF(FPDF):
        def header(self):
            # Logo from Drive
            try:
                r = requests.get(logo_url)
                if r.status_code==200:
                    img = Image.open(BytesIO(r.content)).convert("RGB")
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                    img.save(tmp.name)
                    self.image(tmp.name, x=10, y=8, w=28)
            except:
                pass
            self.ln(25)
        def footer(self):
            qr = make_qr_code(SCHOOL_WEBSITE)
            self.image(qr, x=180, y=275, w=18)
            self.set_y(-18)
            self.set_font("Arial","I",8)
            self.cell(0,10,safe_pdf("Valid without signature."),0,0,"C")

    if st.button("Generate PDF and Download", key="gen_pdf"):
        pdf = LetterPDF()
        pdf.add_page()
        pdf.set_font("Arial","",12)
        for line in email_body.split("\n"):
            pdf.multi_cell(0,8, safe_pdf(line))
        out = pdf.output(dest="S")
        pdf_bytes = out.encode("latin-1") if isinstance(out,str) else out
        st.download_button("Download PDF", pdf_bytes,
                           file_name=f"{student_name.replace(' ','_')}_{msg_type}.pdf",
                           mime="application/pdf")

    # ---- Send Email ----
    attach_pdf = st.checkbox("Attach PDF?", key="attach_pdf")
    recipient  = st.text_input("Recipient Email", value=email, key="recip")
    if st.button("Send Email", key="send_email"):
        msg = Mail(from_email=SENDER_EMAIL, to_emails=recipient,
                   subject=subject, html_content=email_body)
        if attach_pdf:
            msg.add_attachment(
                Attachment(
                    FileContent(base64.b64encode(pdf_bytes).decode()),
                    FileName(f"{student_name}_{msg_type}.pdf"),
                    FileType("application/pdf"),
                    Disposition("attachment")
                )
            )
        try:
            SendGridAPIClient(SENDGRID_KEY).send(msg)
            st.success("Email sent!")
        except Exception as e:
            st.error(f"Email send failed: {e}")









