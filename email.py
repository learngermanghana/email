import os
import re
import base64
import tempfile
import random
import requests
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
from fpdf import FPDF
from PIL import Image
import qrcode
import urllib.parse

# For sending emails
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition




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

import streamlit as st
import sendgrid
from sendgrid.helpers.mail import Mail

def send_email_report(to_email, subject, body):
    sg = sendgrid.SendGridAPIClient(api_key=st.secrets["general"]["sendgrid_api_key"])
    sender_email = st.secrets["general"]["sender_email"]
    email = Mail(
        from_email=sender_email,
        to_emails=to_email,
        subject=subject,
        html_content=body
    )
    response = sg.send(email)
    return response


def header(self):
    try:
        import requests
        # Download logo file
        tmp_logo = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        r = requests.get(logo_url)
        if r.status_code == 200:
            tmp_logo.write(r.content)
            tmp_logo.flush()
            self.image(tmp_logo.name, x=10, y=8, w=36)
        tmp_logo.close()
    except Exception as e:
        # Logo failed, skip
        pass
    self.set_xy(50, 10)
    self.set_font("Arial", "B", 16)
    self.cell(0, 10, headline, ln=1, align="L")
    self.set_font("Arial", "", 12)
    self.cell(0, 8, school, ln=1, align="L")
    self.set_font("Arial", "", 10)
    self.cell(0, 6, f"{contact} | {email}", ln=1, align="L")
    self.ln(3)


# -- CONFIGURATION --
SCHOOL_NAME = "Learn Language Education Academy"
SCHOOL_WEBSITE = "https://www.learngermanghana.com"
SCHOOL_PHONE = "0205706589"
SCHOOL_ADDRESS = "Accra, Ghana"
BUSINESS_REG = "BN173410224"
TUTOR_NAME = "Felix Asadu"
TUTOR_TITLE = "Director"
SENDER_EMAIL = st.secrets["general"]["sender_email"]
SENDGRID_KEY = st.secrets["general"]["sendgrid_api_key"]

# --- Load student data from Google Sheets ---
students_csv_url = "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
df_students = pd.read_csv(students_csv_url)
df_students.columns = [c.strip().lower().replace(" ", "_") for c in df_students.columns]

# -- Utility: get student row --
def get_student_row(name):
    return df_students[df_students["name"] == name].iloc[0]

# -- QR Code generator --
def make_qr_code(url):
    qr = qrcode.QRCode(box_size=3, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(tmp.name)
    return tmp.name

# -- Safe PDF string --
def safe_pdf(text):
    return "".join(c if ord(c) < 256 else "?" for c in str(text))


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
    "📝 Brochure",                # 0
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

# Helpers (top of script – do not repeat if you already have)
@st.cache_data
def get_random_reviews(sheet_url, n=2):
    csv_url = sheet_url.replace("/edit?usp=sharing", "/export?format=csv") if "/edit" in sheet_url else sheet_url
    try:
        df = pd.read_csv(csv_url)
    except Exception:
        return []
    cols = [c for c in df.columns if "review" in c.lower() or "comment" in c.lower()]
    names = [c for c in df.columns if "name" in c.lower()]
    items = []
    for _, r in df.iterrows():
        text = str(r[cols[0]]) if cols else ""
        author = str(r[names[0]]) if names else ""
        if text.strip():
            items.append(f"“{text}” — {author}" if author else f"“{text}”")
    random.shuffle(items)
    return items[:min(n, len(items))]

def make_qr_code(url):
    img = qrcode.make(url)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(tmp.name)
    return tmp.name

def safe_pdf(txt):
    return "".join(c if ord(c) < 256 else "?" for c in str(txt))

def prepare_image_for_html(file_or_url):
    if not file_or_url:
        return ""
    if isinstance(file_or_url, str) and file_or_url.startswith("http"):
        return file_or_url
    try:
        img = Image.open(file_or_url)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        img.save(tmp.name, format="PNG")
        with open(tmp.name, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        os.remove(tmp.name)
        return f"data:image/png;base64,{data}"
    except Exception:
        return ""

def prepare_image_for_pdf(file_or_url):
    if not file_or_url:
        return None
    if isinstance(file_or_url, str) and file_or_url.startswith("http"):
        # Download the image first
        resp = requests.get(file_or_url)
        if resp.status_code == 200:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            tmp.write(resp.content)
            tmp.close()
            return tmp.name
        return None
    try:
        img = Image.open(file_or_url)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        img.save(tmp.name, format="PNG")
        return tmp.name
    except Exception:
        return None

REVIEWS_SHEET = "https://docs.google.com/spreadsheets/d/137HANmV9jmMWJEdcA1klqGiP8nYihkDugcIbA-2V1Wc/edit?usp=sharing"

with tabs[0]:
    st.title("🎓 Class Brochure / Flyer Generator")
    st.write("Generate a professional flyer or brochure for your upcoming German classes with dynamic reviews and Falowen app info.")

    # --- INPUTS ---
    title = st.text_input("Class Title", "German A1 Intensive")
    level = st.selectbox("Level", ["A1", "A2", "B1", "B2"])
    start_dt = st.date_input("Start Date", date.today())
    end_dt = st.date_input("End Date", date.today() + timedelta(days=30))
    times = st.text_input("Meeting Times", "Mon 7pm, Tue 6pm (edit as needed)")
    fee = st.text_input("School Fee (GHS)", "950")
    ge_dt = st.text_input("Goethe Exam Date", "")
    ge_fee = st.text_input("Goethe Exam Fee (GHS)", "")
    logo_url = st.text_input("Logo URL", "https://i.imgur.com/iFiehrp.png")
    class_img_url = st.text_input("Classroom Image URL", "")
    desc = st.text_area("Class Description", "Hybrid format: join in-person, online, or use recorded lectures on our Falowen app. All students receive full support, exercises, and guidance for exam success.")
    notes = st.text_area("Notes", "Register by the deadline to enjoy a discount.")
    extra_notes = st.text_area("Why Choose Us?", "We are an official Goethe partner with 98% pass rate. Only our fee is paid to us; exam fee goes to Goethe Institute. The Falowen app was built by us and is exclusive to our students.")
    n_reviews = st.number_input("How many reviews to show?", min_value=0, max_value=10, value=2)
    REVIEWS_SHEET = st.text_input("Google Reviews Sheet Link", "https://docs.google.com/spreadsheets/d/137HANmV9jmMWJEdcA1klqGiP8nYihkDugcIbA-2V1Wc/edit?usp=sharing")
    qr_url = "https://falowen.streamlit.app"
    # --- GET IMAGES, QR ---
    logo_pdf = prepare_image_for_pdf(logo_url) if logo_url else None
    class_pdf = prepare_image_for_pdf(class_img_url) if class_img_url else None
    qr_path = make_qr_code(qr_url) if qr_url else None

    # --- REVIEWS ---
    reviews = get_random_reviews(REVIEWS_SHEET, n=n_reviews)

    # --- PDF GENERATION ---
    if st.button("Download Brochure as PDF"):
        class PDF(FPDF):
            def header(self):
                if logo_pdf:
                    self.image(logo_pdf, x=10, y=8, w=36)
                self.set_font("Arial", "B", 16)
                self.cell(0, 10, safe_pdf(title), ln=True, align="C")
                self.ln(2)

            def footer(self):
                self.set_y(-20)
                self.set_font("Arial", "I", 8)
                self.cell(0, 8, safe_pdf("Falowen app: falowen.streamlit.app"), 0, 0, 'C')
                if qr_path:
                    self.image(qr_path, x=180, y=260, w=18)

        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, safe_pdf(f"{title} ({level})"), ln=True)
        pdf.cell(0, 8, safe_pdf(f"Dates: {start_dt.strftime('%d %b %Y')} – {end_dt.strftime('%d %b %Y')}"), ln=True)
        pdf.cell(0, 8, safe_pdf(f"Times: {times}"), ln=True)
        pdf.cell(0, 8, safe_pdf(f"School Fee: GHS {fee}"), ln=True)
        pdf.cell(0, 8, safe_pdf(f"Goethe Exam: {ge_dt} (GHS {ge_fee}, paid to Goethe Institute)"), ln=True)
        pdf.ln(2)
        pdf.set_font("Arial", "I", 11)
        pdf.multi_cell(0, 7, safe_pdf(desc))
        pdf.multi_cell(0, 7, safe_pdf(notes))
        pdf.multi_cell(0, 7, safe_pdf(extra_notes))
        pdf.ln(3)
        if class_pdf:
            try:
                pdf.image(class_pdf, x=15, w=170)
                pdf.ln(2)
            except Exception:
                pass
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Falowen App Features", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 7, safe_pdf(
            "• AI-powered writing correction\n"
            "• Speaking feedback with pronunciation scoring\n"
            "• Vocabulary & practice tools (exclusive for Falowen students)\n"
            "• Hybrid learning: attend in-person, online or catch up anytime!"
        ))
        pdf.ln(2)
        if reviews:
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, "Student Reviews:", ln=True)
            pdf.set_font("Arial", size=11)
            for rev in reviews:
                pdf.multi_cell(0, 7, safe_pdf(rev))
                pdf.ln(1)
        pdf.ln(2)
        pdf_data = pdf.output(dest="S")
        if isinstance(pdf_data, str):
            pdf_bytes = pdf_data.encode("latin-1", "replace")
        else:
            pdf_bytes = pdf_data  # already bytes, no need to encode

        st.download_button(
            "📄 Download PDF Brochure",
            data=pdf_bytes,
            file_name=f"{title.replace(' ', '_')}_brochure.pdf",
            mime="application/pdf"
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
    import tempfile
    # ---- Helper: Ensure all text in PDF is latin-1 safe ----
    def safe_pdf(text):
        """Remove non-latin-1 characters for PDF output."""
        if not text:
            return ""
        return text.encode("latin-1", "replace").decode("latin-1")

    # ---- Helper: QR Code generation ----
    def make_qr_code(url):
        import qrcode
        import tempfile
        qr_img = qrcode.make(url)
        qr_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        qr_img.save(qr_tmp)
        qr_tmp.close()
        return qr_tmp.name

    # ---- Student Search/Selection ----
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
    import re
    pdf.multi_cell(0, 8, safe_pdf(re.sub(r"<br\s*/?>", "\n", email_body)), align="L")
    pdf.ln(6)
    if msg_type == "Letter of Enrollment":
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, "Yours sincerely,", ln=True)
        pdf.cell(0, 7, "Felix Asadu", ln=True)
        pdf.cell(0, 7, "Director", ln=True)
        pdf.cell(0, 7, safe_pdf(SCHOOL_NAME), ln=True)
    pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")

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
        msg = Mail(
            from_email=SENDER_EMAIL,
            to_emails=recipient_email,
            subject=email_subject,
            html_content=email_body
        )
        # Attach PDF if selected
        if attach_pdf:
            pdf_attach = Attachment(
                FileContent(base64.b64encode(pdf_bytes).decode()),
                FileName(f"{student_name.replace(' ','_')}_{msg_type.replace(' ','_')}.pdf"),
                FileType("application/pdf"),
                Disposition("attachment")
            )
            msg.attachment = pdf_attach
        # Attach extra file if any
        if extra_attach:
            file_bytes = extra_attach.read()
            file_attach = Attachment(
                FileContent(base64.b64encode(file_bytes).decode()),
                FileName(extra_attach.name),
                FileType(extra_attach.type or "application/octet-stream"),
                Disposition("attachment")
            )
            msg.attachment = file_attach
        try:
            sg = SendGridAPIClient(SENDGRID_KEY)
            sg.send(msg)
            st.success(f"Email sent to {recipient_email}!")
        except Exception as e:
            st.error(f"Email send failed: {e}")




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
    


# --- 1. URLS ---
students_csv_url = "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
ref_answers_url = "https://docs.google.com/spreadsheets/d/1CtNlidMfmE836NBh5FmEF5tls9sLmMmkkhewMTQjkBo/export?format=csv"

with tabs[7]:
    st.title("📝 Reference & Student Work Share")

    # --- Load Data ---
    @st.cache_data(show_spinner=False)
    def load_students():
        df = pd.read_csv(students_csv_url)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
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



