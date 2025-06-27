# ==== 1. IMPORTS ====
import os
import json
import base64
import urllib.parse
from datetime import date, datetime, timedelta
import pandas as pd
import numpy as np
import streamlit as st
import sqlite3
from fpdf import FPDF
from supabase import create_client, Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

# ==== 2. CONFIG / CONSTANTS ====
SCHOOL_NAME    = "Learn Language Education Academy"
SCHOOL_EMAIL   = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE   = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# Streamlit Page Config
st.set_page_config(
    page_title="Learn Language Education Academy Dashboard",
    layout="wide"
)

# === Email API from secrets ===
school_sendgrid_key = st.secrets.get("general", {}).get("SENDGRID_API_KEY")
school_sender_email = st.secrets.get("general", {}).get("SENDER_EMAIL", SCHOOL_EMAIL)

# ==== SUPABASE CONFIG ====
SUPABASE_URL = "https://uzwgfvxrtagmmoaebxye.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV6d2dmdnhydGFnbW1vYWVieHllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTEwNDY4OTEsImV4cCI6MjA2NjYyMjg5MX0.g6gSYYxuMICK2zcaru8wULPjpAMbSo0oC4VfOTz4a2U"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==== 3. HELPER FUNCTIONS (KEEP ALL THESE ABOVE DATA LOADING) ====

def safe_read_csv(local_path, backup_url=None):
    """Try to read local file, then optional backup url."""
    if os.path.exists(local_path):
        return pd.read_csv(local_path)
    if backup_url:
        try:
            return pd.read_csv(backup_url)
        except Exception:
            pass
    st.warning(f"Could not load file: {local_path}")
    st.stop()

def normalize_columns(df):
    """Make all DataFrame columns lowercase, replace spaces/dashes/slashes/parentheses with underscores."""
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_").replace("(", "").replace(")", "")
        for c in df.columns
    ]
    return df

def col_lookup(df, name):
    """Lookup column in df, ignoring underscores and case."""
    key = name.strip().lower().replace("_", "")
    for c in df.columns:
        if c.replace("_", "").lower() == key:
            return c
    return name  # fallback, but will raise error if not present

def getcol(df, name):
    return col_lookup(df, name)

def clean_phone(phone):
    """Format Ghana numbers for WhatsApp."""
    phone = str(phone).replace(" ", "").replace("+", "").replace("-", "")
    if phone.startswith("0"):
        phone = "233" + phone[1:]
    return ''.join(filter(str.isdigit, phone))

def safe_pdf(text):
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def safe_text(s):
    """Ensure text can be written to PDF without Unicode errors."""
    if isinstance(s, str):
        return s.encode("latin-1", "replace").decode("latin-1")
    return str(s)

# ==== 4. SESSION STATE INITIALIZATION ====
# (Ensures notification/email state is not lost on reruns)
st.session_state.setdefault("emailed_expiries", set())
st.session_state.setdefault("dismissed_notifs", set())

# ==== 5. DATABASE SETUP ====

# --- Optionally keep SQLite for local backup, but you can remove if using only Supabase ---
conn = sqlite3.connect('scores.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_code TEXT,
        name TEXT,
        assignment TEXT,
        score REAL,
        comments TEXT,
        date TEXT,
        level TEXT
    )
''')
conn.commit()

def fetch_scores_from_db():
    return pd.read_sql_query("SELECT * FROM scores", conn)

def save_score_to_db(student_code, name, assignment, score, comments, date, level):
    c.execute('''
        SELECT id FROM scores WHERE student_code=? AND assignment=?
    ''', (student_code, assignment))
    result = c.fetchone()
    if result:
        c.execute('''
            UPDATE scores SET score=?, comments=?, name=?, date=?, level=?
            WHERE id=?
        ''', (score, comments, name, date, level, result[0]))
    else:
        c.execute('''
            INSERT INTO scores (student_code, name, assignment, score, comments, date, level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_code, name, assignment, score, comments, date, level))
    conn.commit()

def delete_score_from_db(row_id):
    c.execute('DELETE FROM scores WHERE id=?', (row_id,))
    conn.commit()

# ==== 6. SUPABASE DB HELPERS ====

def fetch_scores_supabase():
    """Read all scores from Supabase 'scores' table."""
    res = supabase.table("scores").select("*").execute()
    df = pd.DataFrame(res.data)
    return df

def save_score_supabase(student_code, name, assignment, score, comments, date, level):
    """Insert or update one score in Supabase."""
    data = {
        "student_code": student_code,
        "name": name,
        "assignment": assignment,
        "score": score,
        "comments": comments,
        "date": date,
        "level": level
    }
    supabase.table("scores").upsert(data, on_conflict=["student_code", "assignment"]).execute()

def delete_score_supabase(student_code, assignment):
    """Delete a score from Supabase."""
    supabase.table("scores").delete().eq("student_code", student_code).eq("assignment", assignment).execute()

# ==== 7. DATA LOAD (after all helpers!) ====
student_file = "students.csv"
github_csv = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
df_students = safe_read_csv(student_file, github_csv)
df_students = normalize_columns(df_students)

name_col = getcol(df_students, 'name')
code_col = getcol(df_students, 'studentcode')
level_col = getcol(df_students, 'level')
email_col = getcol(df_students, 'email')

# --- All Assignments (from your reference answers, define ref_answers earlier or import from file) ---
# ref_answers = {...}  # make sure this exists in your code!
all_assignments = sorted(list(ref_answers.keys()))

# ==== Ready for the rest of your main code / tabs ====

# ==== 8. Reference Answers (no indent, just after your configs and before you use all_assignments) ====

ref_answers = {
    # --- A1 Section ---
    "A1 0.1": [
        "1. C) Guten Morgen",
        "2. D) Guten Tag",
        "3. B) Guten Abend",
        "4. B) Gute Nacht",
        "5. C) Guten Morgen",
        "6. C) Wie geht es Ihnen",
        "7. B) Auf Wiedersehen",
        "8. C) Tschuss",
        "9. C) Guten Abend",
        "10. D) Guten Nacht"
    ],
    "A1 0.2": [
        "1. C) 26",
        "2. A) A, O, U, B",
        "3. A) Eszett",
        "4. A) K",
        "5. A) A-Umlaut",
        "6. A) A, O, U, B",
        "7. B 4",
        "",
        "Wasser", "Kaffee", "Blume", "Schule", "Tisch"
    ],
    "A1 1.1": [
        "1. C",
        "2. C",
        "3. A",
        "4. B"
    ],
    "A1 1.2": [
        "1. Ich heiße Anna",
        "2. Du heißt Max",
        "3. Er heißt Peter",
        "4. Wir kommen aus Italien",
        "",
        "5. Ihr kommt aus Brasilien",
        "6. Sie kommt/k kommen aus Russland",
        "7. Ich wohne in Berlin",
        "",
        "8. Du wohnst in Madrid",
        "9. Sie wohnt in Wien",
        "",
        "1. A) Anna",
        "2. C) Aus Italien",
        "3. D) In Berlin",
        "4. B) Tom",
        "5. A) In Berlin"
    ],
    "A1 2": [
        "1. A) sieben",
        "2. B) Drei",
        "3. B) Sechs",
        "4. B) Neun",
        "5. B) Sieben",
        "6. C) Fünf",
        "",
        "7. B) zweihundertzweiundzwanzig",
        "8. A) fünfhundertneun",
        "9. A) zweitausendvierzig",
        "10. A) fünftausendfünfhundertneun",
        "",
        "1. 16 – sechzehn",
        "2. 98 – achtundneunzig",
        "3. 555 – fünfhundertfünfundfünfzig",
        "",
        "4. 1020 – tausendzwanzig",
        "5. 8553 – achttausendfünfhundertdreiundfünfzig"
    ],
    "A1 4": [
        "1. C) Neun",
        "2. B) Polnisch",
        "3. D) Niederländisch",
        "4. A) Deutsch",
        "5. C) Paris",
        "6. B) Amsterdam",
        "7. C) In der Schweiz",
        "",
        "1. C) In Italien und Frankreich",
        "2. C) Rom",
        "3. B) Das Essen",
        "4. B) Paris",
        "5. A) Nach Spanien"
    ],
    # ... (all your other keys) ...
    "A2 10.28": [
        "1. c) Einen gültigen Reisepass",
        "2. b) Bei der Deutschen Botschaft im Heimatland",
        "3. c) Einen Aufenthaltstitel",
        "4. b) Ein Kurs für Deutsch und Leben in Deutschland",
        "5. c) Man muss sie übersetzen und anerkennen lassen",
        "6. c) Die Arbeitsagentur",
        "7. c) Kranken-, Renten- und Pflegeversicherung"
    ]
}




    st.write("Assignments in scores:", df_scores[assign_col].unique())
    st.write("Reference answer keys:", list(ref_answers.keys()))
    
    all_assignments = sorted(list({*df_scores[assign_col].dropna().unique(), *ref_answers.keys()}))
    all_levels = sorted(df_students[level_col].dropna().unique())

# ==== 5. TABS LAYOUT ====
tabs = st.tabs([
    "📝 Pending",                 # 0
    "👩‍🎓 All Students",          # 1
    "➕ Add Student",             # 2
    "💵 Expenses",                # 3
    "📲 Reminders",               # 4
    "📄 Contract",                # 5
    "📧 Send Email",              # 6 (placeholder, for future use)
    "📊 Analytics & Export",      # 7
    "📆 Schedule",                # 8
    "📝 Marking"                  # 9
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

# ==== 7. TAB 0: PENDING REGISTRATIONS ====
with tabs[0]:
    st.title("📝 Pending Registrations")

    # 1. Load registrations from Google Sheets CSV export (change the link as needed)
    sheet_csv_url = (
        "https://docs.google.com/spreadsheets/d/"
        "1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo"
        "/export?format=csv"
    )

    try:
        new_students = pd.read_csv(sheet_csv_url)
        new_students = normalize_columns(new_students)
        st.success("✅ Loaded columns: " + ", ".join(new_students.columns))
    except Exception as e:
        st.error(f"❌ Could not load registration sheet: {e}")
        new_students = pd.DataFrame()

    # 2. Approve & add each new student
    if new_students.empty:
        st.info("No new registrations to process.")
    else:
        for i, row in new_students.iterrows():
            fullname  = row.get("full_name") or row.get("name") or f"Student {i+1}"
            phone     = row.get("phone_number") or row.get("phone") or ""
            email     = str(row.get("email") or row.get("email_address") or "").strip()
            level     = str(row.get("class") or row.get("level") or "").strip()
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
                        continue

                    # Load or initialize approved students CSV
                    student_file = "students.csv"
                    if os.path.exists(student_file):
                        approved_df = pd.read_csv(student_file)
                    else:
                        approved_df = pd.DataFrame(columns=[
                            "Name","Phone","Email","Location","Level",
                            "Paid","Balance","ContractStart","ContractEnd",
                            "StudentCode","Emergency Contact (Phone Number)"
                        ])

                    # Prevent duplicate codes
                    if student_code in approved_df["StudentCode"].astype(str).values:
                        st.warning("❗ Student code already exists.")
                        continue

                    # Compose student dict for saving
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

                    # Append to CSV
                    approved_df = pd.concat([approved_df, pd.DataFrame([student_dict])], ignore_index=True)
                    approved_df.to_csv(student_file, index=False)

                    # TODO: Add PDF generation and optional email sending if desired
                    # pdf_file = generate_receipt_and_contract_pdf(...) # Fill in as needed

                    st.success(f"✅ {fullname} approved and saved.")
                    st.experimental_rerun()  # Update tab to reflect new student

# --- End of Stage 3 ---

# ==== 8. TAB 1: ALL STUDENTS (VIEW, EDIT, DELETE, RECEIPT) ====
with tabs[1]:
    st.title("👩‍🎓 All Students (Edit, Update, Delete, Receipt)")

    # 1. Load students CSV (local, fallback to GitHub backup)
    student_file = "students.csv"
    github_csv   = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
    df_main      = safe_read_csv(student_file, github_csv)
    df_main = normalize_columns(df_main)

    # 2. Build lookup helper for flexible column access
    def getcol(name):
        return col_lookup(df_main, name)

    # 3. Parse date columns & compute status
    today    = date.today()
    start_col = getcol('contractstart')
    end_col   = getcol('contractend')
    for dt_field in (start_col, end_col):
        if dt_field in df_main.columns:
            df_main[dt_field] = pd.to_datetime(df_main[dt_field], errors='coerce')
    # Compute student status: Enrolled/Completed
    df_main['status'] = 'Unknown'
    if end_col in df_main.columns:
        mask = df_main[end_col].notna()
        df_main.loc[mask, 'status'] = (
            df_main.loc[mask, end_col]
                   .dt.date
                   .apply(lambda d: 'Completed' if d < today else 'Enrolled')
        )

    # 4. Search & filters
    name_col = getcol('name')
    code_col = getcol('studentcode')
    lvl_col  = getcol('level')

    search      = st.text_input('🔍 Search by Name or Code').lower()
    level_opts  = ['All'] + sorted(df_main[lvl_col].dropna().unique().tolist()) if lvl_col in df_main.columns else ['All']
    sel_level   = st.selectbox('📋 Filter by Class Level', level_opts)
    status_opts = ['All', 'Enrolled', 'Completed', 'Unknown']
    sel_status  = st.selectbox('Filter by Status', status_opts)

    # Filter DataFrame
    view_df = df_main.copy()
    if search:
        m1 = view_df[name_col].astype(str).str.lower().str.contains(search)
        m2 = view_df[code_col].astype(str).str.lower().str.contains(search)
        view_df = view_df[m1 | m2]
    if sel_level != 'All':
        view_df = view_df[view_df[lvl_col] == sel_level]
    if sel_status != 'All':
        view_df = view_df[view_df['status'] == sel_status]

    # 5. Table & pagination
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
            getcol('phone'), getcol('paid'), getcol('balance'), 'status'
        ]
        st.dataframe(page_df[display_cols], use_container_width=True)

        # 6. Detail editing
        selected   = st.selectbox('Select a student', page_df[name_col].tolist(), key='sel_student')
        row        = page_df[page_df[name_col] == selected].iloc[0]
        idx_main   = view_df[view_df[name_col] == selected].index[0]
        unique_key = f"{row[code_col]}_{idx_main}"
        status_emoji = '🟢' if row['status'] == 'Enrolled' else ('🔴' if row['status'] == 'Completed' else '⚪')

        with st.expander(f"{status_emoji} {selected} ({row[code_col]}) [{row['status']}]", expanded=True):
            # Schema-driven form for editing
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
                'emergency_contact_phone_number': ('text_input', 'Emergency Contact')
            }
            inputs = {}
            for field, (widget, label) in schema.items():
                col = getcol(field)
                val = row.get(col)
                key_widget = f"{field}_{unique_key}"
                if widget == 'text_input':
                    inputs[field] = st.text_input(label, value=str(val) if pd.notna(val) else '', key=key_widget)
                elif widget == 'number_input':
                    inputs[field] = st.number_input(label, value=float(val or 0), key=key_widget)
                elif widget == 'date_input':
                    default = val.date() if pd.notna(val) and hasattr(val, 'date') else today
                    inputs[field] = st.date_input(label, value=default, key=key_widget)

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button('💾 Update', key=f'upd{unique_key}'):
                    for f, v in inputs.items():
                        df_main.at[idx_main, getcol(f)] = v
                    df_main.to_csv(student_file, index=False)
                    st.success('✅ Student updated.')
                    st.experimental_rerun()
            with c2:
                if st.button('🗑️ Delete', key=f'del{unique_key}'):
                    df_main = df_main.drop(idx_main).reset_index(drop=True)
                    df_main.to_csv(student_file, index=False)
                    st.success('❌ Student deleted.')
                    st.experimental_rerun()
            with c3:
                if st.button('📄 Receipt', key=f'rct{unique_key}'):
                    # PDF generation logic (or call helper)
                    st.info("Receipt generation coming soon!")

        # Export limited columns for download
        export_cols = [
            name_col, code_col, lvl_col,
            getcol('phone'), getcol('paid'), getcol('balance'), 'status'
        ]
        export_df = df_main[export_cols]
        st.download_button(
            '📁 Download Students CSV',
            export_df.to_csv(index=False).encode('utf-8'),
            file_name='students_backup.csv',
            mime='text/csv'
        )
# --- End of Stage 4 ---

# ==== 9. TAB 2: ADD STUDENT MANUALLY ====
with tabs[2]:
    st.title("➕ Add Student Manually")

    student_file = "students.csv"

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
                # Load or initialize students file
                if os.path.exists(student_file):
                    existing_df = pd.read_csv(student_file)
                    existing_df = normalize_columns(existing_df)
                else:
                    existing_df = pd.DataFrame(columns=[
                        "name", "phone", "email", "location", "level", "paid", "balance",
                        "contractstart", "contractend", "studentcode", "emergency_contact_phone_number"
                    ])

                # Check uniqueness of code
                if student_code in existing_df["studentcode"].astype(str).values:
                    st.error("❌ This Student Code already exists.")
                    st.stop()

                # Compose and append new row
                new_row = pd.DataFrame([{
                    "name": name,
                    "phone": phone,
                    "email": email,
                    "location": location,
                    "level": level,
                    "paid": paid,
                    "balance": balance,
                    "contractstart": str(contract_start),
                    "contractend": str(contract_end),
                    "studentcode": student_code,
                    "emergency_contact_phone_number": emergency
                }])

                updated_df = pd.concat([existing_df, new_row], ignore_index=True)
                updated_df.to_csv(student_file, index=False)
                st.success(f"✅ Student '{name}' added successfully.")
                st.experimental_rerun()
# --- End of Stage 5 ---

# ==== 10. TAB 3: EXPENSES AND FINANCIAL SUMMARY ====
with tabs[3]:
    st.title("💵 Expenses and Financial Summary")

    # 1. Load expenses from Google Sheets CSV (edit link as needed)
    sheet_id   = "1I5mGFcWbWdK6YQrJtabTg_g-XBEVaIRK1aMFm72vDEM"
    sheet_csv  = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        df_expenses = pd.read_csv(sheet_csv)
        df_expenses = normalize_columns(df_expenses)
        st.success("✅ Loaded expenses from Google Sheets.")
    except Exception as e:
        st.error(f"❌ Could not load expenses sheet: {e}")
        df_expenses = pd.DataFrame(columns=["type", "item", "amount", "date"])

    # 2. Add new expense via form
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
            # Optionally, save to a local backup file:
            df_expenses.to_csv("expenses_all.csv", index=False)
            st.experimental_rerun()

    # 3. Display all expenses with pagination
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

    # 4. Expense summary
    total_expenses = pd.to_numeric(df_expenses["amount"], errors="coerce").fillna(0).sum() if not df_expenses.empty else 0.0
    st.info(f"💸 **Total Expenses:** GHS {total_expenses:,.2f}")

    # 5. Export to CSV
    csv_data = df_expenses.to_csv(index=False)
    st.download_button(
        "📁 Download Expenses CSV",
        data=csv_data,
        file_name="expenses_data.csv",
        mime="text/csv"
    )
# --- End of Stage 6 ---

# ==== 11. TAB 4: WHATSAPP REMINDERS FOR DEBTORS ====
with tabs[4]:
    st.title("📲 WhatsApp Reminders for Debtors")

    # 1. Load Expenses for financial summary
    exp_sheet_id = "1I5mGFcWbWdK6YQrJtabTg_g-XBEVaIRK1aMFm72vDEM"
    exp_csv_url  = f"https://docs.google.com/spreadsheets/d/{exp_sheet_id}/export?format=csv"
    try:
        df_exp = pd.read_csv(exp_csv_url)
        df_exp = normalize_columns(df_exp)
        total_expenses = pd.to_numeric(df_exp.get("amount", []), errors="coerce").fillna(0).sum()
    except Exception:
        total_expenses = 0.0

    # 2. Load Students
    student_file = "students.csv"
    google_csv   = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    )
    github_csv   = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
    df = safe_read_csv(student_file, google_csv or github_csv)
    df = normalize_columns(df)
    def getcol(key): return col_lookup(df, key)

    cs  = getcol("contractstart")
    paid = getcol("paid")
    bal  = getcol("balance")

    # Parse dates & amounts
    df[cs]   = pd.to_datetime(df.get(cs, pd.NaT), errors="coerce").fillna(pd.Timestamp.today())
    df[paid] = pd.to_numeric(df.get(paid, 0), errors="coerce").fillna(0)
    df[bal]  = pd.to_numeric(df.get(bal, 0), errors="coerce").fillna(0)

    # 3. Financial Metrics
    total_collected = df[paid].sum()
    net_profit      = total_collected - total_expenses

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Students", len(df))
    m2.metric("Total Collected (GHS)", f"{total_collected:,.2f}")
    m3.metric("Total Expenses (GHS)",  f"{total_expenses:,.2f}")
    m4.metric("Net Profit (GHS)",      f"{net_profit:,.2f}")

    st.markdown("---")

    # 4. Filters
    search = st.text_input("Search by name or code", key="wa_search")
    lvl    = getcol("level")
    opts   = ["All"] + sorted(df[lvl].dropna().unique().tolist()) if lvl in df.columns else ["All"]
    selected = st.selectbox("Filter by Level", opts, key="wa_level")

    # 5. Compute Due Dates
    df["due_date"]  = df[cs] + timedelta(days=30)
    df["days_left"] = (df["due_date"] - pd.Timestamp.today()).dt.days.astype(int)

    # 6. Identify Debtors
    filt = df[df[bal] > 0]
    if search:
        mask1 = filt[getcol("name")].str.contains(search, case=False, na=False)
        mask2 = filt[getcol("studentcode")].str.contains(search, case=False, na=False)
        filt  = filt[mask1 | mask2]
    if selected != "All":
        filt = filt[filt[lvl] == selected]

    st.markdown("---")

    if filt.empty:
        st.success("✅ No students currently owing a balance.")
    else:
        st.metric("Number of Debtors", len(filt))
        tbl_cols = [getcol("name"), lvl, bal, "due_date", "days_left"]
        tbl = filt[tbl_cols].rename(columns={
            getcol("name"): "Name",
            lvl:            "Level",
            bal:            "Balance (GHS)",
            "due_date":     "Due Date",
            "days_left":    "Days Until Due"
        })
        st.dataframe(tbl, use_container_width=True)

        # 7. Build WhatsApp links
        def clean_phone_series(s):
            p = s.astype(str).str.replace(r"[+\- ]", "", regex=True)
            p = p.where(~p.str.startswith("0"), "233" + p.str[1:])
            return p.str.extract(r"(\d+)")[0]

        ws = filt.assign(
            phone    = clean_phone_series(filt[getcol("phone")]),
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
                f"Hi {row[getcol('name')]}! Friendly reminder: your payment for the {row[lvl]} class "
                f"is due by {row.due_str}. {msg} Thank you!"
            )
            return f"https://wa.me/{row.phone}?text={urllib.parse.quote(text)}"

        ws["link"] = ws.apply(make_link, axis=1)
        for nm, lk in ws[[getcol("name"), "link"]].itertuples(index=False):
            st.markdown(f"- **{nm}**: [Send Reminder]({lk})")

        dl = ws[[getcol("name"), "link"]].rename(columns={
            getcol("name"): "Name", "link": "WhatsApp URL"
        })
        st.download_button(
            "📁 Download Reminder Links CSV",
            dl.to_csv(index=False).encode("utf-8"),
            file_name="debtor_whatsapp_links.csv",
            mime="text/csv"
        )
# --- End of Stage 7 ---


# ==== 12. TAB 5: GENERATE CONTRACT & RECEIPT PDF FOR ANY STUDENT ====
with tabs[5]:
    st.title("📄 Generate Contract & Receipt PDF for Any Student")

    student_file = "students.csv"
    github_csv   = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"

    # 1. Load students DataFrame (local → GitHub fallback)
    df = safe_read_csv(student_file, github_csv)
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

        # 3. Select student
        student_names = df[name_col].tolist()
        selected_name = st.selectbox("Select Student", student_names)
        row = df[df[name_col] == selected_name].iloc[0]

        # 4. Editable fields before generation
        default_paid    = float(row.get(paid_col, 0))
        default_balance = float(row.get(bal_col, 0))
        default_start = pd.to_datetime(row.get(start_col, ""), errors="coerce").date() if not pd.isnull(pd.to_datetime(row.get(start_col, ""), errors="coerce")) else date.today()
        default_end   = pd.to_datetime(row.get(end_col,   ""), errors="coerce").date() if not pd.isnull(pd.to_datetime(row.get(end_col,   ""), errors="coerce")) else default_start + timedelta(days=30)

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

        # 5. Generate PDF on button click
        if st.button("Generate & Download PDF"):
            # Use inputs
            paid    = paid_input
            balance = balance_input
            total   = total_input
            contract_start = contract_start_input
            contract_end   = contract_end_input

            pdf = FPDF()
            pdf.add_page()

            # Add logo if provided
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
# --- End of Stage 8 ---

# ==== TAB 6: QUICK EMAIL SENDER ====
with tabs[6]:
    st.title("📧 Send Email (Quick)")

    # 1. Load student emails for easy selection
    student_file = "students.csv"
    github_csv   = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
    try:
        df = pd.read_csv(student_file)
    except FileNotFoundError:
        df = pd.read_csv(github_csv)
    df = normalize_columns(df)
    name_col = col_lookup(df, "name")
    email_col = col_lookup(df, "email")

    # 2. Pick students (multi-select)
    student_names = df[name_col].tolist()
    student_emails = df[email_col].tolist()
    student_options = [f"{n} <{e}>" for n, e in zip(student_names, student_emails) if pd.notna(e) and e != ""]
    selected_recipients = st.multiselect("Recipients (student)", student_options)

    # 3. Compose
    st.subheader("Compose Email")
    subject = st.text_input("Subject", value="Message from Learn Language Education Academy")
    body = st.text_area("Body (HTML allowed)", value="Hello,<br>This is a message from the school.<br>Best regards,<br>Felix Asadu")

    # 4. Attachments (optional)
    st.subheader("Attach File (Optional)")
    file = st.file_uploader("Upload file (PDF, DOCX, TXT, JPG, PNG, etc)", type=None, key="quick_email_file")

    # 5. SendGrid config
    sendgrid_key = st.secrets["general"]["SENDGRID_API_KEY"]
    sender_email = st.secrets["general"]["SENDER_EMAIL"]

    # 6. Send
    if st.button("📧 Send Email(s) Now"):
        if not selected_recipients:
            st.warning("Please select at least one recipient.")
        elif not subject or not body:
            st.warning("Please fill in subject and body.")
        else:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
            import base64

            # Extract real emails from label
            recipients = [s.split("<")[-1].replace(">", "").strip() for s in selected_recipients if "@" in s]
            success, fail = [], []
            for email in recipients:
                try:
                    msg = Mail(
                        from_email=sender_email,
                        to_emails=email,
                        subject=subject,
                        html_content=body
                    )
                    # Attach uploaded file if present
                    if file is not None:
                        fdata = file.read()
                        encoded = base64.b64encode(fdata).decode()
                        filename = file.name
                        # Guess filetype for common formats
                        import mimetypes
                        ftype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                        attach = Attachment(
                            FileContent(encoded),
                            FileName(filename),
                            FileType(ftype),
                            Disposition("attachment")
                        )
                        msg.attachment = attach

                    sg = SendGridAPIClient(sendgrid_key)
                    sg.send(msg)
                    success.append(email)
                except Exception as e:
                    fail.append((email, str(e)))
            if success:
                st.success(f"Sent to: {', '.join(success)}")
            if fail:
                st.error(f"Failed: {', '.join([f'{em} ({err})' for em, err in fail])}")

    # 7. Email Log (just shows the most recent action, session only)
    # If you want a persistent log, write to a file/db here.

# --- End of Tab 6 ---


# ==== 13. TAB 7: ANALYTICS & EXPORT ====
with tabs[7]:
    st.title("📊 Analytics & Export")

    # 1. Load students summary (use students_simple.csv if available, else main)
    if os.path.exists("students_simple.csv"):
        df_main = pd.read_csv("students_simple.csv")
    elif os.path.exists("students.csv"):
        df_main = pd.read_csv("students.csv")
    else:
        df_main = pd.DataFrame()

    st.subheader("📈 Enrollment Over Time")
    if not df_main.empty and "ContractStart" in df_main.columns:
        df_main["EnrollDate"] = pd.to_datetime(df_main["ContractStart"], errors="coerce")
        valid_years = df_main["EnrollDate"].dt.year.dropna().unique()
        valid_years = sorted([int(y) for y in valid_years if not pd.isna(y)])
        selected_year = st.selectbox("📆 Filter by Year", valid_years) if valid_years else None

        if df_main["EnrollDate"].notna().sum() == 0:
            st.info("No valid enrollment dates found in 'ContractStart'. Please check your data.")
        else:
            try:
                filtered_df = df_main[df_main["EnrollDate"].dt.year == selected_year] if selected_year else df_main
                monthly = (
                    filtered_df.groupby(filtered_df["EnrollDate"].dt.to_period("M"))
                    .size()
                    .reset_index(name="Count")
                )
                monthly["EnrollDate"] = monthly["EnrollDate"].astype(str)
                st.line_chart(monthly.set_index("EnrollDate")["Count"])
            except Exception as e:
                st.warning(f"⚠️ Unable to generate enrollment chart: {e}")
    else:
        st.info("No enrollment data to visualize.")

    st.subheader("📊 Students by Level")
    if "Level" in df_main.columns and not df_main["Level"].dropna().empty:
        level_counts = df_main["Level"].value_counts()
        st.bar_chart(level_counts)
    else:
        st.info("No level information available to display.")

    st.subheader("⬇️ Export CSV Files")
    student_csv = df_main.to_csv(index=False)
    st.download_button("📁 Download Students CSV", data=student_csv, file_name="students_data.csv")

    expenses_file = "expenses_all.csv"
    if os.path.exists(expenses_file):
        exp_data = pd.read_csv(expenses_file)
        expense_csv = exp_data.to_csv(index=False)
        st.download_button("📁 Download Expenses CSV", data=expense_csv, file_name="expenses_data.csv")
    else:
        st.info("No expenses file found to export.")
# --- End of Stage 9 ---

# ==== 14. TAB 8: COURSE SCHEDULE GENERATOR ====
with tabs[8]:
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
    st.title("📝 Assignment Marking & Scores (with Email)")

    # === 1. Load data (students and scores) ===
    students_csv_url = "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"

    def normalize_columns(df):
        return df.rename(columns={c: c.strip().lower().replace(' ', '_') for c in df.columns})

    @st.cache_data(show_spinner=False)
    def load_students():
        df = pd.read_csv(students_csv_url)
        return normalize_columns(df)

    df_students = load_students()

    # === 2. Load all scores from Supabase ===
    def fetch_scores_supabase():
        res = supabase.table("scores").select("*").execute()
        df = pd.DataFrame(res.data)
        return normalize_columns(df)

    def save_score_supabase(student_code, name, assignment, score, comments, date, level):
        data = {
            "student_code": student_code,
            "name": name,
            "assignment": assignment,
            "score": score,
            "comments": comments,
            "date": date,
            "level": level
        }
        supabase.table("scores").upsert(data, on_conflict=["student_code", "assignment"]).execute()

    def delete_score_supabase(student_code, assignment):
        supabase.table("scores").delete().eq("student_code", student_code).eq("assignment", assignment).execute()

    df_scores = fetch_scores_supabase()

    # --- Show columns for debugging (optional) ---
    st.write("df_students columns:", df_students.columns.tolist())
    st.write("df_scores columns:", df_scores.columns.tolist())

    # === Column lookups ===
    def col_lookup(df, key):
        key = key.strip().lower().replace(" ", "_")
        for col in df.columns:
            if col.strip().lower().replace(" ", "_") == key:
                return col
        raise KeyError(f"Column {key} not found in {df.columns}")

    def get_safe_col(df, keys, label="Column"):
        for key in keys:
            try:
                return col_lookup(df, key)
            except KeyError:
                continue
        st.error(f"{label} not found! Tried: {keys}. Found columns: {df.columns.tolist()}")
        st.stop()

    name_col        = get_safe_col(df_students, ["name", "fullname"], "Name column")
    code_col        = get_safe_col(df_students, ["studentcode", "code"], "Student Code")
    level_col       = get_safe_col(df_students, ["level", "class", "course"], "Level")
    assign_col      = get_safe_col(df_scores, ["assignment", "title"], "Assignment")
    studentcode_col = get_safe_col(df_scores, ["student_code", "studentcode", "code"], "StudentCode in scores")
    comments_col    = get_safe_col(df_scores, ["comments", "feedback"], "Comments")
    score_col       = get_safe_col(df_scores, ["score", "marks"], "Score")
    date_col        = get_safe_col(df_scores, ["date"], "Date")
    email_col       = get_safe_col(df_students, ["email"], "Email")

    # Load all assignments (supplied by you)
    all_assignments = sorted(list(ref_answers.keys()))
    all_levels = sorted(df_students[level_col].dropna().unique())

    # === 3. Marking Modes ===
    mode = st.radio(
        "Select marking mode:",
        ["Mark single assignment (classic)", "Batch mark (all assignments for one student)"],
        key="marking_mode"
    )

    # --- SINGLE CLASSIC MODE ---
    if mode == "Mark single assignment (classic)":
        st.subheader("Classic Mode: Mark One Assignment")
        sel_level = st.selectbox("Filter by Level", ["All"] + all_levels, key="single_level")
        filtered_students = df_students if sel_level == "All" else df_students[df_students[level_col] == sel_level]
        student_list = filtered_students[name_col] + " (" + filtered_students[code_col].astype(str) + ")"
        chosen = st.selectbox("Select Student", student_list, key="single_student")
        student_code = chosen.split("(")[-1].replace(")", "").strip()
        stu_row = filtered_students[filtered_students[code_col] == student_code].iloc[0]

        assign_filter = st.text_input("Filter assignment titles", key="assign_filter")
        assignment_choices = [a for a in all_assignments if assign_filter.lower() in str(a).lower()]
        assignment = st.selectbox("Select Assignment", assignment_choices, key="assignment_sel")
        prev = df_scores[(df_scores[studentcode_col] == student_code) & (df_scores[assign_col] == assignment)]
        default_score = int(prev[score_col].iloc[0]) if not prev.empty else 0
        default_comment = prev[comments_col].iloc[0] if not prev.empty else ""
        score = st.number_input("Score", 0, 100, value=default_score, key="score_input")
        comments = st.text_area("Comments / Feedback", value=default_comment, key="comments_input")
        if assignment in ref_answers:
            st.markdown("**Reference Answers:**")
            st.markdown("<br>".join(ref_answers[assignment]), unsafe_allow_html=True)

        if st.button("💾 Save Score", key="save_score_btn"):
            now = pd.Timestamp.now().strftime("%Y-%m-%d")
            save_score_supabase(
                student_code, stu_row[name_col], assignment, score, comments, now, stu_row[level_col]
            )
            st.success("Score saved to Supabase!")
            # Refresh table immediately after save
            df_scores = fetch_scores_supabase()

        hist = df_scores[df_scores[studentcode_col] == student_code].sort_values(date_col, ascending=False)
        st.markdown("### Student Score History")
        st.dataframe(hist[[assign_col, score_col, comments_col, date_col]])

    # --- BATCH MODE ---
    if mode == "Batch mark (all assignments for one student)":
        st.subheader("Batch Mode: Enter all assignments for one student (fast)")
        sel_level = st.selectbox("Select Level", all_levels, key="batch_level")
        filtered_students = df_students[df_students[level_col] == sel_level]
        student_list = filtered_students[name_col] + " (" + filtered_students[code_col].astype(str) + ")"
        chosen = st.selectbox("Select Student", student_list, key="batch_student")
        student_code = chosen.split("(")[-1].replace(")", "").strip()
        stu_row = filtered_students[filtered_students[code_col] == student_code].iloc[0]
        st.markdown(f"#### Enter scores for all assignments for {stu_row[name_col]} ({stu_row[code_col]})")
        scored = df_scores[df_scores[studentcode_col] == student_code]
        batch_scores = {}
        for assignment in all_assignments:
            prev = scored[scored[assign_col] == assignment]
            val = int(prev[score_col].iloc[0]) if not prev.empty else 0
            batch_scores[assignment] = st.number_input(
                f"{assignment}", 0, 100, value=val, key=f"batch_score_{assignment}"
            )
        if st.button("💾 Save All Scores (Batch)", key="save_all_batch"):
            now = pd.Timestamp.now().strftime("%Y-%m-%d")
            for assignment, score_val in batch_scores.items():
                save_score_supabase(
                    student_code, stu_row[name_col], assignment, score_val, "", now, stu_row[level_col]
                )
            st.success("All scores saved to Supabase!")
            df_scores = fetch_scores_supabase()
        st.markdown("##### Summary of entered scores:")
        st.dataframe(pd.DataFrame({
            "Assignment": all_assignments,
            "Score": [batch_scores[a] for a in all_assignments]
        }))

    # === 4. Edit/Delete/Export ===
    st.markdown("---")
    st.header("✏️ Edit, Delete, or Export Scores")
    edit_student = st.selectbox(
        "Pick student for history export/edit",
        df_students[name_col] + " (" + df_students[code_col].astype(str) + ")",
        key="edit_student"
    )
    edit_code = edit_student.split("(")[-1].replace(")", "").strip()
    stu_row = df_students[df_students[code_col] == edit_code].iloc[0]
    hist = df_scores[df_scores[studentcode_col] == edit_code].sort_values(date_col, ascending=False)
    st.dataframe(hist[[assign_col, score_col, comments_col, date_col]])

    for idx, row in hist.iterrows():
        with st.expander(f"{row[assign_col]} – {row[score_col]}/100 ({row[date_col]})", expanded=False):
            new_score = st.number_input("Edit Score", 0, 100, int(row[score_col]), key=f"edit_score_{idx}")
            new_comments = st.text_area("Edit Comments", row[comments_col], key=f"edit_comments_{idx}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Update", key=f"update_{idx}"):
                    save_score_supabase(
                        row[studentcode_col], row[name_col], row[assign_col], new_score, new_comments, row[date_col], row[level_col]
                    )
                    st.success("Score updated in Supabase!")
                    df_scores = fetch_scores_supabase()
            with col2:
                if st.button("Delete", key=f"delete_{idx}"):
                    delete_score_supabase(row[studentcode_col], row[assign_col])
                    st.success("Deleted from Supabase!")
                    df_scores = fetch_scores_supabase()

    # === 5. Download CSV ===
    st.download_button(
        "📁 Download All Scores CSV",
        data=df_scores.to_csv(index=False).encode(),
        file_name="all_scores_export.csv",
        mime="text/csv"
    )

    # === 6. PDF & EMAIL (with Reference Answers in PDF) ===
    st.markdown("### 📄 PDF/Email Student Full Report (with Reference Answers)")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, safe_text(f"Report for {stu_row[name_col]}"), ln=True)
    pdf.ln(5)
    for _, r in hist.iterrows():
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, safe_text(f"{r[assign_col]}: {r[score_col]}/100"), ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 8, safe_text(f"Comments: {r[comments_col]}"))
        ref_ans = ref_answers.get(r[assign_col])
        pdf.ln(1)
        pdf.set_font("Arial", "I", 10)
        if ref_ans:
            pdf.multi_cell(0, 8, safe_text("Reference Answers:"))
            pdf.set_font("Arial", "", 10)
            for ans in ref_ans:
                pdf.multi_cell(0, 7, safe_text(ans))
        else:
            pdf.multi_cell(0, 7, safe_text("Reference Answers: N/A"))
        pdf.ln(3)

    pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
    st.download_button(
        "📄 Download Student Report PDF (with Reference Answers)",
        data=pdf_bytes,
        file_name=f"{stu_row[name_col].replace(' ', '_')}_report_with_ref.pdf",
        mime="application/pdf"
    )

    # === 7. SendGrid Email Button ===
    st.markdown("#### 📧 Email this report to the student")
    student_email = stu_row.get(email_col, "")
    sender_email = st.secrets["general"]["SENDER_EMAIL"]
    sendgrid_key = st.secrets["general"]["SENDGRID_API_KEY"]

    if student_email and st.button(f"📧 Send PDF to {student_email}"):
        try:
            sg = SendGridAPIClient(sendgrid_key)
            message = Mail(
                from_email=sender_email,
                to_emails=student_email,
                subject=f"Your Assignment Results from Learn Language Education Academy",
                html_content=f"""
                <p>Hello {safe_text(stu_row[name_col])},<br><br>
                Please find attached your latest assignment scores <b>with official reference answers</b>.<br><br>
                Best regards,<br>Learn Language Education Academy
                </p>
                """
            )
            encoded = base64.b64encode(pdf_bytes).decode()
            attached = Attachment(
                FileContent(encoded),
                FileName(f"{stu_row[name_col].replace(' ', '_')}_report_with_ref.pdf"),
                FileType('application/pdf'),
                Disposition('attachment')
            )
            message.attachment = attached
            sg.send(message)
            st.success(f"Email sent to {student_email}!")
        except Exception as e:
            st.error(f"Failed to send email: {e}")
    elif not student_email:
        st.info("No email found for this student.")

# --- End of Tab 9 ---
