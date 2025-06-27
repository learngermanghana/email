import json
import requests
import re
import sqlite3
import base64
import urllib.parse 
from datetime import date, datetime, timedelta
import os
import traceback



import pandas as pd
import streamlit as st
from fpdf import FPDF

import gspread
from google.oauth2.service_account import Credentials

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

# ===== PAGE CONFIG =====
st.set_page_config(
    page_title="Learn Language Education Academy Dashboard",
    layout="wide"
)

# ===== Helper: Make PDF text safe (no Unicode crash) =====
def safe_pdf(text):
    try:
        replacements = {
            "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
            "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
            "é": "e", "è": "e", "à": "a", "ô": "o", "ê": "e"
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        return text.encode("latin-1", "ignore").decode("latin-1", "ignore")
    except Exception:
        return str(text)

# ===== Reference Answers: Load from GitHub JSON =====
REF_ANSWERS_URL = "https://raw.githubusercontent.com/learngermanghana/email/main/ref_answers.json"

@st.cache_data(show_spinner=False)
def load_ref_answers():
    resp = requests.get(REF_ANSWERS_URL)
    resp.raise_for_status()
    return json.loads(resp.text)

ref_answers = load_ref_answers()

# ===== Helper: Normalize DataFrame columns =====
def normalize_cols(df):
    df.columns = [
        c.strip().lower()
         .replace(' ', '')
         .replace('-', '')
         .replace('/', '')
         .replace('(', '')
         .replace(')', '')
        for c in df.columns
    ]
    return df

# ====== SQLite Sync & Load Helpers ======
def sync_scores_to_sqlite(df):
    conn = sqlite3.connect("students_backup.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            studentcode TEXT,
            name TEXT,
            assignment TEXT,
            score REAL,
            comments TEXT,
            date TEXT,
            level TEXT
        )
    ''')
    c.execute("DELETE FROM scores")
    for _, row in df.iterrows():
        c.execute('''
            INSERT OR REPLACE INTO scores
            (studentcode, name, assignment, score, comments, date, level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            row.get("studentcode", ""), row.get("name", ""), row.get("assignment", ""),
            float(row.get("score", 0) or 0), row.get("comments", ""), row.get("date", ""), row.get("level", "")
        ))
    conn.commit()
    conn.close()

def load_scores_from_sqlite():
    conn = sqlite3.connect("students_backup.db")
    df = pd.read_sql_query("SELECT * FROM scores", conn)
    conn.close()
    return df

def send_email_with_pdf(student_email, student_name, pdf_bytes, sendgrid_api_key, sender_email):
    message = Mail(
        from_email=sender_email,
        to_emails=student_email,
        subject="Your Assignment Results – Learn Language Education Academy",
        html_content=f"<p>Hello {student_name},<br><br>Your report is attached.</p>"
    )
    encoded = base64.b64encode(pdf_bytes).decode()
    attached = Attachment(
        FileContent(encoded),
        FileName(f"{student_name.replace(' ', '_')}_report.pdf"),
        FileType('application/pdf'),
        Disposition('attachment')
    )
    message.attachment = attached
    sg = SendGridAPIClient(sendgrid_api_key)
    response = sg.send(message)
    return response.status_code  # Add this line!


def build_simple_pdf(student, history_df, ref_answers, total):
    pdf = FPDF(format='A4')
    pdf.add_page()
    pdf.set_font('Arial', size=12)
    pdf.cell(0, 10, 'Learn Language Education Academy', ln=True, align='C')
    pdf.ln(4)
    pdf.cell(0, 8, f"Student: {student['name']} ({student['studentcode']})", ln=True)
    pdf.cell(0, 8, f"Level: {student['level']}", ln=True)
    pdf.cell(0, 8, f"Date: {datetime.now():%Y-%m-%d}", ln=True)
    pdf.ln(4)
    pdf.cell(0, 8, f"Assignments completed: {history_df['assignment'].nunique()} / {total}", ln=True)
    pdf.ln(4)

    col_widths = [60, 20, 30, 80]
    headers = ['Assignment', 'Score', 'Date', 'Reference']
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=1)
    pdf.ln()

    for _, row in history_df.iterrows():
        assignment = row['assignment']
        score = str(row['score'])
        date_str = row['date']
        reference = '; '.join(ref_answers.get(assignment, []))
        pdf.cell(col_widths[0], 6, assignment[:40], border=1)
        pdf.cell(col_widths[1], 6, score, border=1)
        pdf.cell(col_widths[2], 6, date_str, border=1)
        pdf.multi_cell(col_widths[3], 6, reference, border=1)
    return pdf.output(dest='S').encode('latin-1')


def sync_google_sheet_to_sqlite(df):
    conn = sqlite3.connect("students_backup.db")
    df.to_sql("students", conn, if_exists="replace", index=False)
    conn.close()

# =========== TABS ===========
tabs = st.tabs([
    "Dashboard",           # tab 0
    "All Students",        # tab 1
    "Pending",             # tab 2
    "Add Student",         # tab 3
    "Assignments",         # tab 4
    "Payments",            # tab 5
    "Attendance",          # tab 6
    "Reports",             # tab 7
    "Financials",          # tab 8
    "Marking & Scores"     # tab 9
])
#end


# ====== PAGE CONFIG ======
st.set_page_config(
    page_title="Learn Language Education Academy Dashboard",
    layout="wide"
)

# ===== School Info (constants) =====
SCHOOL_NAME    = "Learn Language Education Academy"
SCHOOL_EMAIL   = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE   = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"


# ====== MAIN TABS ======
tabs = st.tabs([
    "📝 Pending",
    "👩‍🎓 All Students",
    "➕ Add Student",
    "💵 Expenses",
    "📲 Reminders",
    "📄 Contract",
    "📧 Send Email",
    "📊 Analytics & Export",
    "📆 Schedule",
    "📝 Marking"
])

with tabs[0]:
    st.title("📝 Pending")

    # 1) Fetch registrations from Google Sheets (CSV export)
    sheet_csv = (
        "https://docs.google.com/spreadsheets/d/"
        "1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo"
        "/export?format=csv"
    )
    try:
        new_students = pd.read_csv(sheet_csv)
        def clean_col(c):
            return (
                c.strip()
                 .lower()
                 .replace("(", "")
                 .replace(")", "")
                 .replace(",", "")
                 .replace("-", "")
                 .replace(" ", "_")
            )
        new_students.columns = [clean_col(c) for c in new_students.columns]
        st.success("✅ Loaded columns: " + ", ".join(new_students.columns))
    except Exception as e:
        st.error(f"❌ Could not load registration sheet: {e}")
        new_students = pd.DataFrame()

    # 2) Approve & add each new student
    if new_students.empty:
        st.info("No new registrations to process.")
    else:
        for i, row in new_students.iterrows():
            fullname  = row.get("full_name") or row.get("name") or f"Student {i}"
            phone     = row.get("phone_number") or row.get("phone") or ""
            email     = str(row.get("email") or row.get("email_address") or "").strip()
            level     = str(row.get("class") or row.get("class_a1a2_etc") or row.get("level") or "").strip()
            location  = str(row.get("location") or "").strip()
            emergency = str(row.get("emergency_contact_phone_number") or row.get("emergency") or "").strip()

            with st.expander(f"{fullname} — {phone}"):
                st.write(f"**Email:** {email or '—'}")
                student_code    = st.text_input("Assign Student Code", key=f"code_{i}")
                contract_start  = st.date_input("Contract Start", value=date.today(), key=f"start_{i}")
                course_length   = st.number_input("Course Length (weeks)", min_value=1, value=12, key=f"length_{i}")
                contract_end    = st.date_input(
                    "Contract End",
                    value=contract_start + timedelta(weeks=course_length),
                    key=f"end_{i}"
                )
                paid            = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0, key=f"paid_{i}")
                balance         = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0, key=f"bal_{i}")
                first_instalment= st.number_input("First Instalment (GHS)", min_value=0.0, value=1500.0, key=f"firstinst_{i}")
                send_email      = st.checkbox("Send Welcome Email?", value=bool(email), key=f"email_{i}")
                attach_pdf      = st.checkbox("Attach PDF to Email?", value=True, key=f"pdf_{i}")

                if st.button("Approve & Add", key=f"approve_{i}"):
                    if not student_code:
                        st.warning("❗ Please enter a unique student code.")
                    else:
                        # Load or create students.csv
                        if os.path.exists("students.csv"):
                            approved_df = pd.read_csv("students.csv")
                        else:
                            approved_df = pd.DataFrame(columns=[
                                "Name", "Phone", "Email", "Location", "Level",
                                "Paid", "Balance", "ContractStart", "ContractEnd",
                                "StudentCode", "Emergency Contact (Phone Number)"
                            ])

                        if student_code in approved_df["StudentCode"].astype(str).values:
                            st.warning("❗ Student code already exists.")
                        else:
                            student_dict = {
                                "Name": fullname,
                                "Phone": phone,
                                "Email": email,
                                "Location": location,
                                "Level": level,
                                "Paid": paid,
                                "Balance": balance,
                                "ContractStart": contract_start.isoformat(),
                                "ContractEnd": contract_end.isoformat(),
                                "StudentCode": student_code,
                                "Emergency Contact (Phone Number)": emergency
                            }
                            approved_df = pd.concat([approved_df, pd.DataFrame([student_dict])], ignore_index=True)
                            approved_df.to_csv("students.csv", index=False)

                            total_fee = paid + balance

                            # --- Generate PDF as bytes (no file save!) ---
                            pdf_bytes = generate_receipt_and_contract_pdf(
                                student_dict,
                                st.session_state["agreement_template"],
                                payment_amount=total_fee,
                                payment_date=contract_start,
                                first_instalment=first_instalment,
                                course_length=course_length
                            )

                            # --- Show download button for PDF ---
                            filename = f"{fullname.replace(' ', '_')}_receipt.pdf"
                            st.download_button(
                                "📄 Download Receipt PDF",
                                data=pdf_bytes,
                                file_name=filename,
                                mime="application/pdf"
                            )

                            # --- (Optional: Add email logic here, using pdf_bytes for attachment) ---

                            st.success(f"✅ {fullname} approved and saved.")
                            st.rerun()

# --- All Students (Edit, Update, Delete, Receipt) ---
with tabs[1]:
    st.title("👩‍🎓 All Students (Edit, Update, Delete, Receipt)")

    STUDENTS_SHEET_CSV = "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    try:
        df_main = pd.read_csv(STUDENTS_SHEET_CSV)
    except Exception as e:
        st.error(f"❌ Could not load students sheet: {e}")
        df_main = pd.DataFrame(columns=[
            "Name", "Phone", "Email", "Location", "Level",
            "Paid", "Balance", "ContractStart", "ContractEnd",
            "StudentCode", "Emergency Contact (Phone Number)"
        ])
    # Sync Google Sheet → SQLite (every page load)
    sync_google_sheet_to_sqlite(df_main)

    # Normalize columns and build lookup
    df_main.columns = [
        c.strip().lower()
         .replace(' ', '_')
         .replace('(', '')
         .replace(')', '')
         .replace('-', '_')
         .replace('/', '_')
        for c in df_main.columns
    ]
    col_map = {c.replace('_', ''): c for c in df_main.columns}
    def col_lookup(key):
        k = key.strip().lower().replace(' ', '_').replace('_', '')
        return col_map.get(k, key)

    today    = date.today()
    start_col = col_lookup('contractstart')
    end_col   = col_lookup('contractend')
    for dt_field in (start_col, end_col):
        if dt_field in df_main.columns:
            df_main[dt_field] = pd.to_datetime(df_main[dt_field], errors='coerce')

    df_main['status'] = 'Unknown'
    if end_col in df_main.columns:
        mask = df_main[end_col].notna()
        df_main.loc[mask, 'status'] = (
            df_main.loc[mask, end_col]
                   .dt.date
                   .apply(lambda d: 'Completed' if d < today else 'Enrolled')
        )

    search      = st.text_input('🔍 Search by Name or Code').lower()
    lvl_col     = col_lookup('level')
    level_opts  = ['All'] + sorted(df_main[lvl_col].dropna().unique().tolist()) if lvl_col in df_main.columns else ['All']
    sel_level   = st.selectbox('📋 Filter by Class Level', level_opts)
    status_opts = ['All', 'Enrolled', 'Completed', 'Unknown']
    sel_status  = st.selectbox('Filter by Status', status_opts)

    view_df = df_main.copy()
    name_col = col_lookup('name')
    code_col = col_lookup('studentcode')
    if search:
        m1 = view_df[name_col].astype(str).str.lower().str.contains(search)
        m2 = view_df[code_col].astype(str).str.lower().str.contains(search)
        view_df = view_df[m1 | m2]
    if sel_level != 'All':
        view_df = view_df[view_df[lvl_col] == sel_level]
    if sel_status != 'All':
        view_df = view_df[view_df['status'] == sel_status]

    if view_df.empty:
        st.info('No students found.')
    else:
        per_page = 10
        total    = len(view_df)
        pages    = (total - 1) // per_page + 1
        page     = st.number_input(f'Page (1-{pages})', 1, pages, 1, key='students_page')
        start    = (page - 1) * per_page
        end      = start + per_page
        page_df  = view_df.iloc[start:end]

        display_cols = [
            name_col, code_col, lvl_col,
            col_lookup('phone'), col_lookup('paid'), col_lookup('balance'), 'status'
        ]
        st.dataframe(page_df[display_cols], use_container_width=True)

        selected   = st.selectbox('Select a student', page_df[name_col].tolist(), key='sel_student')
        row        = page_df[page_df[name_col] == selected].iloc[0]
        idx_main   = view_df[view_df[name_col] == selected].index[0]
        unique_key = f"{row[code_col]}_{idx_main}"
        status_emoji = '🟢' if row['status'] == 'Enrolled' else ('🔴' if row['status'] == 'Completed' else '⚪')

        with st.expander(f"{status_emoji} {selected} ({row[code_col]}) [{row['status']}]", expanded=True):
            schema = {
                'name': ('text_input', 'Name'),
                'phone': ('text_input', 'Phone'),
                'email': ('text_input', 'Email'),
                'location': ('text_input', 'Location'),
                'level': ('text_input', 'Level'),
                'paid': ('number_input', 'Paid'),
                'balance': ('number_input', 'Balance'),
                'contractstart': ('date_input', 'Contract Start'),
                'contractend': ('date_input', 'Contract End'),
                'studentcode': ('text_input', 'Student Code'),
                'emergencycontactphonenumber': ('text_input', 'Emergency Contact')
            }
            inputs = {}
            for field, (widget, label) in schema.items():
                col = col_lookup(field)
                val = row.get(col)
                key_widget = f"{field}_{unique_key}"
                if widget == 'text_input':
                    inputs[field] = st.text_input(label, value=str(val) if pd.notna(val) else '', key=key_widget)
                elif widget == 'number_input':
                    inputs[field] = st.number_input(label, value=float(val or 0), key=key_widget)
                elif widget == 'date_input':
                    default = val.date() if pd.notna(val) and hasattr(val, "date") else today
                    inputs[field] = st.date_input(label, value=default, key=key_widget)

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button('💾 Update', key=f'upd{unique_key}'):
                    for f, v in inputs.items():
                        df_main.at[idx_main, col_lookup(f)] = v
                    st.success('✅ Student updated.')
                    st.download_button(
                        '⬇️ Download Updated Students CSV (Upload to Google Sheets!)',
                        data=df_main.to_csv(index=False).encode(),
                        file_name='students.csv',
                        mime='text/csv'
                    )
                    st.stop()
            with c2:
                if st.button('🗑️ Delete', key=f'del{unique_key}'):
                    df_main = df_main.drop(idx_main).reset_index(drop=True)
                    st.success('❌ Student deleted.')
                    st.download_button(
                        '⬇️ Download Updated Students CSV (Upload to Google Sheets!)',
                        data=df_main.to_csv(index=False).encode(),
                        file_name='students.csv',
                        mime='text/csv'
                    )
                    st.stop()
            with c3:
                if st.button('📄 Receipt', key=f'rct{unique_key}'):
                    total_fee = inputs['paid'] + inputs['balance']
                    pay_date  = inputs['contractstart']
                    student_dict = {k: inputs.get(k, '') for k in schema.keys()}
                    pdf_bytes = generate_receipt_and_contract_pdf(
                        student_dict,
                        st.session_state['agreement_template'],
                        payment_amount=total_fee,
                        payment_date=pay_date
                    )
                    st.download_button(
                        "📄 Download Receipt PDF",
                        data=pdf_bytes,
                        file_name=f"{selected.replace(' ', '_')}_receipt.pdf",
                        mime="application/pdf"
                    )

        export_cols = [
            name_col, code_col, lvl_col,
            col_lookup('phone'), col_lookup('paid'), col_lookup('balance'), 'status'
        ]
        export_df = df_main[export_cols]
        st.download_button(
            '📁 Download Students CSV',
            export_df.to_csv(index=False).encode('utf-8'),
            file_name='students_backup.csv',
            mime='text/csv'
        )

        # Download the SQLite DB as a backup
        with open("students_backup.db", "rb") as f:
            st.download_button(
                "⬇️ Download SQLite DB Backup",
                data=f,
                file_name="students_backup.db",
                mime="application/octet-stream"
            )


with tabs[2]:
    st.title("➕ Add Student Manually")

    with st.form("add_student_form"):
        name = st.text_input("Full Name")
        phone = st.text_input("Phone Number")
        email = st.text_input("Email Address")
        location = st.text_input("Location")
        emergency = st.text_input("Emergency Contact (Phone Number)")
        level = st.selectbox("Class Level", ["A1", "A2", "B1", "B2", "C1", "C2"])
        paid = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0)
        balance = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0)
        contract_start = st.date_input("Contract Start", value=date.today())
        course_length = st.number_input("Course Length (weeks)", min_value=1, value=12)
        contract_end = contract_start + timedelta(weeks=course_length)
        student_code = st.text_input("Student Code (must be unique)")

        submit_btn = st.form_submit_button("Add Student")

        if submit_btn:
            if not name or not phone or not student_code:
                st.warning("❗ Name, Phone, and Student Code are required.")
            else:
                # Always work with fresh CSV
                if os.path.exists(student_file):
                    existing_df = pd.read_csv(student_file)
                else:
                    existing_df = pd.DataFrame(columns=[
                        "Name", "Phone", "Email", "Location", "Level", "Paid", "Balance",
                        "ContractStart", "ContractEnd", "StudentCode", "Emergency Contact (Phone Number)"
                    ])

                if student_code in existing_df["StudentCode"].values:
                    st.error("❌ This Student Code already exists.")
                    st.stop()

                new_row = pd.DataFrame([{
                    "Name": name,
                    "Phone": phone,
                    "Email": email,
                    "Location": location,
                    "Level": level,
                    "Paid": paid,
                    "Balance": balance,
                    "ContractStart": str(contract_start),
                    "ContractEnd": str(contract_end),
                    "StudentCode": student_code,
                    "Emergency Contact (Phone Number)": emergency
                }])

                updated_df = pd.concat([existing_df, new_row], ignore_index=True)
                updated_df.to_csv(student_file, index=False)
                st.success(f"✅ Student '{name}' added successfully.")

# --- Tab 3: Expenses and Financial Summary (Google Sheets) ---
with tabs[3]:
    st.title("💵 Expenses and Financial Summary")

    # 1) Load expenses from Google Sheets CSV export
    sheet_id   = "1I5mGFcWbWdK6YQrJtabTg_g-XBEVaIRK1aMFm72vDEM"
    sheet_csv  = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        df_expenses = pd.read_csv(sheet_csv)
        df_expenses.columns = [c.strip().lower().replace(" ", "_") for c in df_expenses.columns]
        st.success("✅ Loaded expenses from Google Sheets.")
    except Exception as e:
        st.error(f"❌ Could not load expenses sheet: {e}")
        df_expenses = pd.DataFrame(columns=["type", "item", "amount", "date"])

    # 2) Add new expense via form
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
            st.experimental_rerun()

    # 3) Display all expenses with pagination
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

    # 4) Expense summary
    total_expenses = df_expenses["amount"].sum() if not df_expenses.empty else 0.0
    st.info(f"💸 **Total Expenses:** GHS {total_expenses:,.2f}")

    # 5) Export to CSV
    csv_data = df_expenses.to_csv(index=False)
    st.download_button(
        "📁 Download Expenses CSV",
        data=csv_data,
        file_name="expenses_data.csv",
        mime="text/csv"
    )


# Helper: load student data from multiple sources
def load_student_data(path, google_url, github_url):
    if os.path.exists(path):
        return pd.read_csv(path)
    for url in (google_url, github_url):
        try:
            return pd.read_csv(url)
        except Exception:
            continue
    st.warning("No student data found. Please provide students.csv locally or ensure the remote sheet is accessible.")
    st.stop()

# --- Tab 4: WhatsApp Reminders for Debtors (with Expenses) ---
with tabs[4]:
    st.title("📲 WhatsApp Reminders for Debtors")

    # 1) Load Expenses from Google Sheets
    exp_sheet_id = "1I5mGFcWbWdK6YQrJtabTg_g-XBEVaIRK1aMFm72vDEM"
    exp_csv_url  = f"https://docs.google.com/spreadsheets/d/{exp_sheet_id}/export?format=csv"
    try:
        df_exp = pd.read_csv(exp_csv_url)
        df_exp.columns = [c.strip().lower().replace(" ", "_") for c in df_exp.columns]
        total_expenses = pd.to_numeric(df_exp.get("amount", []), errors="coerce").fillna(0).sum()
    except Exception:
        total_expenses = 0.0

        # 2) Load Students
    student_file = "students.csv"
    google_csv   = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    )
    github_csv   = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
    df = load_student_data(student_file, google_csv, github_csv)
    df = load_student_data(student_file, google_csv, github_csv)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    col_map = {c.replace("_", ""): c for c in df.columns}
    def col_lookup(key):
        return col_map.get(key.strip().lower().replace(" ", "_").replace("_", ""), key)

    cs  = col_lookup("contractstart")
    paid = col_lookup("paid")
    bal  = col_lookup("balance")

    # Parse dates & amounts
    df[cs]   = pd.to_datetime(df.get(cs, pd.NaT), errors="coerce").fillna(pd.Timestamp.today())
    df[paid] = pd.to_numeric(df.get(paid, 0), errors="coerce").fillna(0)
    df[bal]  = pd.to_numeric(df.get(bal, 0), errors="coerce").fillna(0)

    # 3) Financial Metrics
    total_collected = df[paid].sum()
    net_profit      = total_collected - total_expenses

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Students", len(df))
    m2.metric("Total Collected (GHS)", f"{total_collected:,.2f}")
    m3.metric("Total Expenses (GHS)",  f"{total_expenses:,.2f}")
    m4.metric("Net Profit (GHS)",      f"{net_profit:,.2f}")

    st.markdown("---")

    # 4) Filters
    search = st.text_input("Search by name or code", key="wa_search")
    lvl    = col_lookup("level")
    if lvl in df.columns:
        opts     = ["All"] + sorted(df[lvl].dropna().unique().tolist())
        selected = st.selectbox("Filter by Level", opts, key="wa_level")
    else:
        selected = "All"

    # 5) Compute Due Dates
    df["due_date"]  = df[cs] + timedelta(days=30)
    df["days_left"] = (df["due_date"] - pd.Timestamp.today()).dt.days.astype(int)

    # 6) Identify Debtors
    filt = df[df[bal] > 0]
    if search:
        mask1 = filt[col_lookup("name")].str.contains(search, case=False, na=False)
        mask2 = filt[col_lookup("studentcode")].str.contains(search, case=False, na=False)
        filt  = filt[mask1 | mask2]
    if selected != "All":
        filt = filt[filt[lvl] == selected]

    st.markdown("---")

    if filt.empty:
        st.success("✅ No students currently owing a balance.")
    else:
        st.metric("Number of Debtors", len(filt))
        tbl_cols = [col_lookup("name"), lvl, bal, "due_date", "days_left"]
        tbl = filt[tbl_cols].rename(columns={
            col_lookup("name"): "Name",
            lvl:                 "Level",
            bal:                 "Balance (GHS)",
            "due_date":          "Due Date",
            "days_left":         "Days Until Due"
        })
        st.dataframe(tbl, use_container_width=True)

        # 7) Build WhatsApp links
        def clean_phone(s):
            p = s.astype(str).str.replace(r"[+\- ]", "", regex=True)
            p = p.where(~p.str.startswith("0"), "233" + p.str[1:])
            return p.str.extract(r"(\d+)")[0]

        ws = filt.assign(
            phone    = clean_phone(filt[col_lookup("phone")]),
            due_str  = filt["due_date"].dt.strftime("%d %b %Y"),
            bal_str  = filt[bal].map(lambda x: f"GHS {x:.2f}"),
            days     = filt["days_left"].astype(int)
        )

        def make_link(row):
            if row.days >= 0:
                msg = f"You have {row.days} {'day' if row.days==1 else 'days'} left to settle the {row.bal_str} balance."
            else:
                od = abs(row.days)
                msg = f"Your payment is overdue by {od} {'day' if od==1 else 'days'}. Please settle as soon as possible."
            text = (
                f"Hi {row[col_lookup('name')]}! Friendly reminder: your payment for the {row[lvl]} class "
                f"is due by {row.due_str}. {msg} Thank you!"
            )
            return f"https://wa.me/{row.phone}?text={urllib.parse.quote(text)}"

        ws["link"] = ws.apply(make_link, axis=1)
        for nm, lk in ws[[col_lookup("name"), "link"]].itertuples(index=False):
            st.markdown(f"- **{nm}**: [Send Reminder]({lk})")

        dl = ws[[col_lookup("name"), "link"]].rename(columns={
            col_lookup("name"): "Name", "link": "WhatsApp URL"
        })
        st.download_button(
            "📁 Download Reminder Links CSV",
            dl.to_csv(index=False).encode("utf-8"),
            file_name="debtor_whatsapp_links.csv",
            mime="text/csv"
        )



# === AGREEMENT TEMPLATE STATE ===
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

@st.cache_data(show_spinner=False)
def load_students_sheet(sheet_url):
    try:
        return pd.read_csv(sheet_url)
    except Exception:
        return pd.DataFrame()


# --- Tab 5 ---
with tabs[5]:
    st.title("📄 Generate Contract & Receipt PDF for Any Student")

    STUDENTS_CSV_URL = "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    df = load_students_sheet(STUDENTS_CSV_URL)
    if df.empty:
        st.error("Couldn't load student data from Google Sheets.")
        st.stop()

    # 2) Normalize columns
    df.columns = [
        c.strip().lower()
         .replace("(", "")
         .replace(")", "")
         .replace(" ", "_")
         .replace("-", "_")
         .replace("/", "_")
        for c in df.columns
    ]

    # 3) Convert contract dates up front
    def lookup(col_key):
        k = col_key.replace("_", "").lower()
        for c in df.columns:
            if c.replace("_", "").lower() == k:
                return c
        return None
    start_col = lookup("contractstart")
    end_col   = lookup("contractend")
    if start_col:
        df[start_col] = pd.to_datetime(df[start_col], errors="coerce").dt.date
    if end_col:
        df[end_col]   = pd.to_datetime(df[end_col],   errors="coerce").dt.date

    # 4) Lookup core fields
    name_col  = lookup("name")
    code_col  = lookup("studentcode")
    paid_col  = lookup("paid")
    bal_col   = lookup("balance")
    if not name_col or not code_col:
        st.error("Missing essential 'name' or 'studentcode' columns.")
        st.stop()

    # 5) Search & select student
    search = st.text_input("🔎 Search student by name or code").strip().lower()
    df_search = df if not search else df[
        df[name_col].str.lower().str.contains(search) |
        df[code_col].astype(str).str.lower().str.contains(search)
    ]
    if df_search.empty:
        st.info("No students match your search.")
        st.stop()
    selected_name = st.selectbox("Select Student", df_search[name_col].tolist())
    row = df[df[name_col] == selected_name].iloc[0]

    # 6) Defaults
    default_start = row[start_col] if start_col and pd.notna(row[start_col]) else date.today()
    default_end   = row[end_col]   if end_col   and pd.notna(row[end_col])   else default_start + timedelta(days=30)
    default_paid  = float(row.get(paid_col, 0) or 0)
    default_bal   = float(row.get(bal_col, 0) or 0)

    st.subheader("🧾 Receipt Details")
    paid_input    = st.number_input("Amount Paid (GHS)", min_value=0.0, value=default_paid, step=1.0)
    balance_input = st.number_input("Balance Due (GHS)", min_value=0.0, value=default_bal, step=1.0)
    receipt_date  = st.date_input("Receipt Date", value=date.today())
    signature     = st.text_input("Signature Text", value="Felix Asadu")

    st.subheader("📜 Contract Details")
    contract_start = st.date_input("Contract Start Date", value=default_start)
    contract_end   = st.date_input("Contract End Date",   value=default_end)

    st.subheader("🖼️ Logo (optional)")
    logo_file      = st.file_uploader("Upload logo image", type=["png","jpg","jpeg"])

    # 7) PDF builder
    def build_pdf(r, paid, bal, start, end, receipt_dt, sign, logo):
        pdf = FPDF()
        pdf.add_page()
        if logo:
            ext = logo.name.split('.')[-1]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
            tmp.write(logo.getbuffer()); tmp.close()
            pdf.image(tmp.name, x=10, y=8, w=33); pdf.ln(25)
        status = "FULLY PAID" if bal == 0 else "INSTALLMENT PLAN"
        pdf.set_font("Arial","B",12); pdf.set_text_color(0,128,0)
        pdf.cell(0,10,status,ln=True,align="C"); pdf.ln(5); pdf.set_text_color(0,0,0)
        pdf.set_font("Arial",size=14)
        pdf.cell(0,10,f"{SCHOOL_NAME} Payment Receipt",ln=True,align="C"); pdf.ln(10)
        pdf.set_font("Arial",size=12)
        for label, val in [
            ("Name", r[name_col]), ("Student Code", r[code_col]),
            ("Contract Start", start), ("Contract End", end),
            ("Amount Paid", f"GHS {paid:.2f}"), ("Balance Due", f"GHS {bal:.2f}"),
            ("Receipt Date", receipt_dt)
        ]:
            pdf.cell(0,8,f"{label}: {val}",ln=True)
        pdf.ln(10)
        pdf.set_font("Arial",size=14)
        pdf.cell(0,10,f"{SCHOOL_NAME} Student Contract",ln=True,align="C"); pdf.ln(8)
        template = st.session_state.get("agreement_template", "")
        filled = (
            template
            .replace("[STUDENT_NAME]", selected_name)
            .replace("[DATE]", str(receipt_date))
            .replace("[CLASS]", str(r.get(lookup("level"), "")))
            .replace("[AMOUNT]", str(paid+bal))
            .replace("[FIRST_INSTALLMENT]", f"{paid:.2f}")
            .replace("[SECOND_INSTALLMENT]", f"{bal:.2f}")
            .replace("[SECOND_DUE_DATE]", str(end))
            .replace("[COURSE_LENGTH]", f"{(end-start).days} days")
        )
        for line in filled.split("\n"):
            safe = line.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0,8,safe)
        pdf.ln(10)
        pdf.cell(0,8,f"Signed: {sign}",ln=True)
        return pdf

    # 8a) Generate PDF bytes on demand
    sheet_key = f"pdf_{selected_name.replace(' ','_')}"
    if st.button("Generate PDF"):
        pdf = build_pdf(row, paid_input, balance_input, contract_start, contract_end, receipt_date, signature, logo_file)
        st.session_state[sheet_key] = pdf.output(dest='S').encode("latin-1","replace")
        st.success("✅ PDF generated and stored for download.")

    # 8b) Offer download if available
    if sheet_key in st.session_state:
        st.download_button(
            "📄 Download PDF", 
            st.session_state[sheet_key],
            file_name=f"{selected_name.replace(' ','_')}_receipt_contract.pdf",
            mime="application/pdf"
        )

with tabs[6]:
    st.title("📧 Send Email")
    st.info("Email-sending UI coming soon")

with tabs[7]:
    st.title("📊 Analytics & Export")
    st.info("Analytics dashboard and export options coming soon")

with tabs[8]:

    # ---- Helper for safe PDF encoding ----
    def safe_pdf(text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')

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

with tabs[9]:
    st.title("Assignment Marking & Scores (Email, Reference, PDF)")

    # Load and normalize students
    try:
        df_students = pd.read_csv("students.csv")
        df_students = normalize_cols(df_students)
    except Exception:
        st.error("Could not load student list.")
        df_students = pd.DataFrame(columns=['name', 'studentcode', 'email', 'level'])

    # Load and normalize scores
    try:
        df_scores = pd.read_csv(
            "https://docs.google.com/spreadsheets/d/1BRb8p3Rq0VpFCLSwL4eS9tSgXBo9hSWzfW_J_7W36NQ/export?format=csv"
        )
        df_scores = normalize_cols(df_scores)
    except Exception:
        st.error("Could not load score history.")
        df_scores = pd.DataFrame(columns=['studentcode', 'name', 'assignment', 'score', 'comments', 'date', 'level'])

    # Reference answers and assignment totals
    LEVEL_TOTALS = {'A1': 18, 'A2': 28, 'B1': 26, 'B2': 30}
    ref_answers = load_ref_answers()

    @st.cache_data
    def all_assignments(df, ref_answers):
        return sorted(set(df['assignment'].dropna()) | set(ref_answers.keys()))

    all_assigns = all_assignments(df_scores, ref_answers)

    # Mode switch
    mode = st.radio("Marking Mode", ["Classic", "Batch"], horizontal=True)

    # Student search/select
    st.subheader("Find Student")
    search = st.text_input("Search name or code")
    filtered = df_students.copy()
    if search:
        mask = (
            filtered['name'].str.lower().str.contains(search.lower(), na=False) |
            filtered['studentcode'].astype(str).str.lower().str.contains(search.lower(), na=False)
        )
        filtered = filtered[mask]
    if filtered.empty:
        st.info("No students found.")
        st.stop()
    sel = st.selectbox("Select Student", filtered['name'] + " (" + filtered['studentcode'] + ")")
    code = sel.split('(')[-1].strip(')')
    student = filtered[filtered['studentcode'] == code].iloc[0]
    level = student.get('level', '').upper()
    total = LEVEL_TOTALS.get(level, 0)

    # Classic mode: single assignment
    if mode == "Classic":
        st.markdown("---")
        st.subheader("Classic: Mark Single Assignment")
        af = st.text_input("Filter assignments")
        opts = [a for a in all_assigns if af.lower() in a.lower()]
        sel_a = st.selectbox("Assignment", opts)
        prev = df_scores[(df_scores['studentcode'] == code) & (df_scores['assignment'] == sel_a)]
        ds = int(prev['score'].iloc[0]) if not prev.empty else 0
        dc = prev['comments'].iloc[0] if not prev.empty else ''
        if sel_a in ref_answers:
            st.subheader("Reference Answers")
            for ans in ref_answers[sel_a]:
                st.write(f"- {ans}")
        with st.form("mark_form"):
            score = st.number_input("Score", 0, 100, ds)
            comments = st.text_area("Comments", dc)
            if st.form_submit_button("Save Score"):
                now = datetime.now().strftime("%Y-%m-%d")
                row = dict(studentcode=code, name=student['name'], assignment=sel_a,
                           score=score, comments=comments, date=now, level=student['level'])
                df_scores = df_scores[~(
                    (df_scores['studentcode'] == code) & (df_scores['assignment'] == sel_a)
                )]
                df_scores = pd.concat([df_scores, pd.DataFrame([row])], ignore_index=True)
                sync_scores_to_sqlite(df_scores)
                st.success("Score saved.")
                st.experimental_rerun()
    else:
        # Batch mode: all assignments of level
        st.markdown("---")
        st.subheader("Batch: Mark Assignments")
        stu_scores = df_scores[df_scores['studentcode'] == code]
        with st.form("batch_form"):
            batch = {}
            for a in [x for x in all_assigns if x.startswith(level)]:
                pr = stu_scores[stu_scores['assignment'] == a]
                val = int(pr['score'].iloc[0]) if not pr.empty else 0
                batch[a] = st.number_input(a, 0, 100, val)
            if st.form_submit_button("Save All"):
                now = datetime.now().strftime("%Y-%m-%d")
                new = [dict(studentcode=code, name=student['name'], assignment=a,
                            score=v, comments='', date=now, level=student['level'])
                       for a, v in batch.items()]
                df_scores = df_scores[~(
                    (df_scores['studentcode'] == code) & df_scores['assignment'].isin(batch)
                )]
                df_scores = pd.concat([df_scores, pd.DataFrame(new)], ignore_index=True)
                sync_scores_to_sqlite(df_scores)
                st.success("All scores saved.")
                st.experimental_rerun()

    # History and PDF
    st.markdown("### Score History & PDF Report")
    history = df_scores[df_scores['studentcode'] == code].sort_values('date', ascending=False)
    st.write(f"Completed: {history['assignment'].nunique()} / {total}")
    if not history.empty:
        dfh = history[['assignment', 'score', 'comments', 'date']].copy()
        dfh['reference'] = dfh['assignment'].apply(lambda x: "; ".join(ref_answers.get(x, [])))
        st.dataframe(dfh)
    else:
        st.info("No records.")

    pdf_bytes = build_simple_pdf(student, history, ref_answers, total)
    st.download_button("Download PDF Report", pdf_bytes,
                       f"{student['studentcode']}_report.pdf", "application/pdf")
    if student.get('email'):
        if st.button(f"Email PDF to {student['email']}"):
            send_email_with_pdf(student['email'], student['name'], pdf_bytes,
                                st.secrets['general']['SENDGRID_API_KEY'],
                                st.secrets['general']['SENDER_EMAIL'])
            )
            st.success("✅ Email sent successfully!")
            except Exception as e:
            st.error(f"❌ Email failed to send: {e}")
#end


