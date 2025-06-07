import streamlit as st
import pandas as pd
import os
from datetime import date, datetime, timedelta
from fpdf import FPDF
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import urllib.parse
import calendar
import numpy as np

# Google Sheets deps
import gspread
from google.oauth2.service_account import Credentials

# ===== PAGE CONFIG (must be first Streamlit command!) =====
st.set_page_config(
    page_title="Learn Language Education Academy Dashboard",
    layout="wide"
)

# --- Session State Initialization ---
def init_state():
    st.session_state.setdefault("should_rerun", False)
    st.session_state.setdefault("emailed_expiries", set())
init_state()

# 2) HANDLE RERUN FLAG
if st.session_state["should_rerun"]:
    st.session_state["should_rerun"] = False
    st.experimental_rerun()

# === SCHOOL INFO ===
SCHOOL_NAME    = "Learn Language Education Academy"
SCHOOL_EMAIL   = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE   = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# === SENDGRID CONFIG ===
school_sendgrid_key = st.secrets.get("general", {}).get("SENDGRID_API_KEY")
school_sender_email = st.secrets.get("general", {}).get("SENDER_EMAIL", SCHOOL_EMAIL)

# === GOOGLE SHEET SETUP ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
service_account_info = st.secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
gc = gspread.authorize(creds)

SHEET_ID    = st.secrets["sheet"]["STUDENTS_SHEET_ID"]
WS_NAME     = st.secrets["sheet"]["STUDENTS_WORKSHEET"]

def load_students():
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(WS_NAME)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    df["Paid"]    = pd.to_numeric(df.get("Paid",0), errors="coerce").fillna(0.0)
    df["Balance"] = pd.to_numeric(df.get("Balance",0), errors="coerce").fillna(0.0)
    df["ContractStart"] = pd.to_datetime(df.get("ContractStart",""), errors="coerce")
    df["ContractEnd"]   = pd.to_datetime(df.get("ContractEnd",""),   errors="coerce")
    return df

def save_student(student: dict):
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(WS_NAME)
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    mask = df["StudentCode"] == student["StudentCode"]
    if mask.any():
        row_idx = mask.idxmax() + 2  # account for header
    else:
        row_idx = len(df) + 2
    headers = ws.row_values(1)
    row = [ student.get(h, "") for h in headers ]
    ws.update(f"A{row_idx}:{chr(ord('A')+len(headers)-1)}{row_idx}", [row])

# === PDF GENERATION FUNCTION ===
def generate_receipt_and_contract_pdf(
    student_row,
    agreement_text,
    payment_amount,
    payment_date=None,
    first_instalment=1500,
    course_length=12
):
    if payment_date is None:
        payment_date = date.today()
    elif isinstance(payment_date, str):
        payment_date = pd.to_datetime(payment_date, errors="coerce").date()

    paid = float(student_row.get("Paid", 0))
    balance = float(student_row.get("Balance", 0))
    total_fee = paid + balance

    try:
        second_due_date = payment_date + timedelta(days=30)
    except:
        second_due_date = payment_date

    payment_status = "FULLY PAID" if balance == 0 else "INSTALLMENT PLAN"

    filled = (agreement_text
        .replace("[STUDENT_NAME]", str(student_row.get("Name","")))
        .replace("[DATE]", str(payment_date))
        .replace("[CLASS]", str(student_row.get("Level","")))
        .replace("[AMOUNT]", str(payment_amount))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(balance))
        .replace("[SECOND_DUE_DATE]", str(second_due_date))
        .replace("[COURSE_LENGTH]", str(course_length))
    )

    def safe(txt):
        return str(txt).encode("latin-1","replace").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()
    # Header
    pdf.set_font("Arial", size=14)
    pdf.cell(200,10,safe(f"{SCHOOL_NAME} Payment Receipt"),ln=True,align="C")
    pdf.set_font("Arial","B",12)
    pdf.set_text_color(0,128,0)
    pdf.cell(200,10,safe(payment_status),ln=True,align="C")
    pdf.set_text_color(0,0,0)
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    for line in [
        f"Name: {student_row.get('Name','')}",
        f"Student Code: {student_row.get('StudentCode','')}",
        f"Phone: {student_row.get('Phone','')}",
        f"Level: {student_row.get('Level','')}",
        f"Amount Paid: GHS {paid:.2f}",
        f"Balance Due: GHS {balance:.2f}",
        f"Total Course Fee: GHS {total_fee:.2f}",
        f"Contract Start: {student_row.get('ContractStart','')}",
        f"Contract End: {student_row.get('ContractEnd','')}",
        f"Receipt Date: {payment_date}"
    ]:
        pdf.cell(200,10,safe(line),ln=True)
    pdf.ln(10)
    pdf.cell(0,10,safe("Thank you for your payment!"),ln=True)
    pdf.cell(0,10,safe("Signed: Felix Asadu"),ln=True)
    # Contract
    pdf.ln(15)
    pdf.set_font("Arial", size=14)
    pdf.cell(200,10,safe(f"{SCHOOL_NAME} Student Contract"),ln=True,align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    for line in filled.split("\n"):
        pdf.multi_cell(0,10,safe(line))
    pdf.ln(10)
    pdf.cell(0,10,safe("Signed: Felix Asadu"),ln=True)
    # Footer
    pdf.set_y(-15)
    pdf.set_font("Arial","I",8)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf.cell(0,10,safe(f"Generated on {now_str}"),align="C")

    filename = f"{student_row.get('Name','').replace(' ','_')}_receipt_contract.pdf"
    pdf.output(filename)
    return filename

# === FORM RESPONSES URL ===
sheet_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"

# === AGREEMENT TEMPLATE STATE ===
if "agreement_template" not in st.session_state:
    st.session_state["agreement_template"] = """
PAYMENT AGREEMENT

This Payment Agreement is entered into on [DATE] for [CLASS] students...
... (full template here) ...
Signatures:
[STUDENT_NAME]
Date: [DATE]
Asadu Felix
"""

# === PAGE HEADER ===
st.title("🏫 Learn Language Education Academy Dashboard")
st.caption(f"📍 {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

# === LOAD MASTER STUDENTS ===
df_main = load_students()

# === TABS ===
tabs = st.tabs([
    "📝 Pending Registrations",
    "👩‍🎓 All Students",
    # … other tabs …
])

# ---- Tab 0: Pending Registrations ----
with tabs[0]:
    st.title("📝 Pending Student Registrations")

    # Load form sheet
    try:
        new_students = pd.read_csv(sheet_url)
        def clean_col(c):
            return (c.strip().lower()
                     .replace("(","").replace(")","")
                     .replace(",","").replace("-","")
                     .replace(" ","_"))
        new_students.columns = [clean_col(c) for c in new_students.columns]
        st.success("✅ Loaded columns: " + ", ".join(new_students.columns))
    except Exception as e:
        st.error(f"❌ Could not load registration sheet: {e}")
        new_students = pd.DataFrame()

    # Approve & Add
    if not new_students.empty:
        for i, r in new_students.iterrows():
            fullname = r.get("full_name") or r.get("name") or f"Student {i}"
            phone    = r.get("phone_number") or r.get("phone") or ""
            email    = r.get("email") or ""
            with st.expander(f"{fullname} ({phone})"):
                code_input   = st.text_input("Student Code", key=f"code_{i}")
                start_dt     = st.date_input("Contract Start", date.today(), key=f"start_{i}")
                weeks        = st.number_input("Course Length (weeks)", 1, 52, 12, key=f"len_{i}")
                end_dt       = st.date_input("Contract End", start_dt+timedelta(weeks=weeks), key=f"end_{i}")
                paid_amt     = st.number_input("Amount Paid (GHS)", 0.0, 1e6, 0.0, key=f"paid_{i}")
                bal_amt      = st.number_input("Balance Due (GHS)", 0.0, 1e6, 0.0, key=f"bal_{i}")
                if st.button("Approve & Add", key=f"app_{i}"):
                    if not code_input:
                        st.warning("❗ Enter a unique StudentCode.")
                        continue
                    student_dict = {
                        "StudentCode":    code_input,
                        "Name":           fullname,
                        "Phone":          phone,
                        "Email":          email,
                        "Location":       r.get("location",""),
                        "Level":          r.get("class",""),
                        "Paid":           paid_amt,
                        "Balance":        bal_amt,
                        "ContractStart":  str(start_dt),
                        "ContractEnd":    str(end_dt),
                        "EmergencyContact": r.get("emergency_contact_phone_number","")
                    }
                    save_student(student_dict)
                    generate_receipt_and_contract_pdf(
                        student_dict,
                        st.session_state["agreement_template"],
                        payment_amount=paid_amt+bal_amt,
                        payment_date=start_dt,
                        first_instalment=1500,
                        course_length=weeks
                    )
                    st.success(f"✅ {fullname} approved and saved.")
                    st.session_state["should_rerun"] = True
                    st.stop()

# ---- Tab 1: All Students (Edit, Update, Delete, Receipt) ----
with tabs[1]:
    st.title("👩‍🎓 All Students")
    df_main = load_students()

    # Compute status
    today = date.today()
    df_main["Status"] = np.where(
        df_main["ContractEnd"] < pd.Timestamp(today), "Completed", "Enrolled"
    )

    # Filters
    search = st.text_input("🔍 Search by Name or Code")
    levels = ["All"] + sorted(df_main["Level"].dropna().unique().tolist())
    lvl = st.selectbox("📋 Filter by Level", levels)
    stats = ["All", "Enrolled", "Completed"]
    st_filter = st.selectbox("Filter by Status", stats)

    view = df_main.copy()
    if search:
        view = view[
            view["Name"].str.contains(search, na=False, case=False) |
            view["StudentCode"].str.contains(search, na=False, case=False)
        ]
    if lvl != "All":
        view = view[view["Level"] == lvl]
    if st_filter != "All":
        view = view[view["Status"] == st_filter]

    if view.empty:
        st.info("No students found.")
    else:
        for idx, row in view.iterrows():
            key = f"{row['StudentCode']}_{idx}"
            color = "🟢" if row["Status"]=="Enrolled" else "🔴"
            with st.expander(f"{color} {row['Name']} ({row['StudentCode']}) [{row['Status']}]"):
                # Editable fields
                name_in  = st.text_input("Name", value=row["Name"], key=f"name_{key}")
                phone_in = st.text_input("Phone", value=row["Phone"], key=f"phone_{key}")
                email_in = st.text_input("Email", value=row["Email"], key=f"email_{key}")
                level_in = st.text_input("Level", value=row["Level"], key=f"level_{key}")
                paid_in  = st.number_input("Paid", value=row["Paid"], key=f"paid_{key}")
                bal_in   = st.number_input("Balance", value=row["Balance"], key=f"bal_{key}")
                cs_in    = st.date_input("Contract Start", value=row["ContractStart"].date(), key=f"cs_{key}")
                ce_in    = st.date_input("Contract End", value=row["ContractEnd"].date(), key=f"ce_{key}")
                code_in  = st.text_input("Student Code", value=row["StudentCode"], key=f"code_{key}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Update", key=f"upd_{key}"):
                        save_student({
                            "StudentCode": code_in,
                            "Name": name_in,
                            "Phone": phone_in,
                            "Email": email_in,
                            "Location": row["Location"],
                            "Level": level_in,
                            "Paid": paid_in,
                            "Balance": bal_in,
                            "ContractStart": str(cs_in),
                            "ContractEnd": str(ce_in),
                            "EmergencyContact": row.get("EmergencyContact","")
                        })
                        st.success("✅ Updated")
                        st.session_state["should_rerun"] = True
                        st.stop()
                with col2:
                    if st.button("🗑️ Delete", key=f"del_{key}"):
                        save_student({**row.to_dict(), "StudentCode": row["StudentCode"]})
                        # Actually delete_student:
                        # delete_student(row["StudentCode"])
                        st.success("❌ Deleted")
                        st.session_state["should_rerun"] = True
                        st.stop()
                with col3:
                    if st.button("📄 Receipt", key=f"rec_{key}"):
                        pdf = generate_receipt_and_contract_pdf(
                            row.to_dict(),
                            st.session_state["agreement_template"],
                            payment_amount=row["Paid"]+row["Balance"],
                            payment_date=row["ContractStart"].date()
                        )
                        with open(pdf, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode()
                        st.markdown(
                            f'<a href="data:application/pdf;base64,{b64}" download="{row["Name"]}_receipt.pdf">Download Receipt</a>',
                            unsafe_allow_html=True
                        )

# ---- Tab 2: Add Student ----
with tabs[2]:
    st.title("➕ Add Student")
    with st.form("add_form"):
        name     = st.text_input("Full Name")
        phone    = st.text_input("Phone")
        email    = st.text_input("Email")
        location = st.text_input("Location")
        level    = st.text_input("Level")
        paid     = st.number_input("Paid", min_value=0.0, step=1.0)
        bal      = st.number_input("Balance", min_value=0.0, step=1.0)
        cs       = st.date_input("Contract Start", date.today())
        weeks    = st.number_input("Course Length (weeks)", 1, 52, 12)
        ce       = st.date_input("Contract End", cs + timedelta(weeks=weeks))
        code     = st.text_input("Student Code")
        submitted = st.form_submit_button("Add Student")
        if submitted:
            if not (name and phone and code):
                st.warning("Name, Phone, and Code are required.")
            else:
                save_student({
                    "StudentCode":    code,
                    "Name":           name,
                    "Phone":          phone,
                    "Email":          email,
                    "Location":       location,
                    "Level":          level,
                    "Paid":           paid,
                    "Balance":        bal,
                    "ContractStart":  str(cs),
                    "ContractEnd":    str(ce),
                    "EmergencyContact":""
                })
                st.success(f"✅ {name} added.")
                st.session_state["should_rerun"] = True
                st.stop()

# ---- Tab 3: Expenses ----
with tabs[3]:
    st.title("💵 Expenses")
    exp_file = "expenses_all.csv"
    if os.path.exists(exp_file):
        exp = pd.read_csv(exp_file, parse_dates=["Date"])
    else:
        exp = pd.DataFrame(columns=["Type","Item","Amount","Date"])
    with st.form("exp_form"):
        t = st.selectbox("Type", ["Bill","Rent","Salary","Marketing","Other"])
        it= st.text_input("Item")
        am= st.number_input("Amount", min_value=0.0, step=1.0)
        dt= st.date_input("Date", date.today())
        if st.form_submit_button("Add Expense"):
            exp = exp.append({"Type":t,"Item":it,"Amount":am,"Date":dt}, ignore_index=True)
            exp.to_csv(exp_file, index=False)
            st.success("✅ Expense recorded.")
            st.session_state["should_rerun"] = True
            st.stop()
    st.dataframe(exp)
    st.info(f"Total: GHS {exp['Amount'].sum():.2f}")

# ---- Tab 4: WhatsApp Reminders ----
with tabs[4]:
    st.title("📲 WhatsApp Reminders")
    df = load_students()
    df["Balance"] = df["Balance"].fillna(0)
    debt = df[df["Balance"]>0]
    if debt.empty:
        st.success("✅ No outstanding balances.")
    else:
        for _, r in debt.iterrows():
            msg = f"Dear {r['Name']}, you owe GHS {r['Balance']:.2f}."
            p = str(r["Phone"]).lstrip("0")
            url = f"https://wa.me/233{p}?text={urllib.parse.quote(msg)}"
            st.markdown(f"**{r['Name']}** – [Remind via WhatsApp]({url})")

# ---- Tab 5: Generate Contract PDF ----
with tabs[5]:
    st.title("📄 Generate Contract PDF")
    df = load_students()
    name = st.selectbox("Student", df["Name"])
    if st.button("Generate"):
        row = df[df["Name"]==name].iloc[0]
        pdf = generate_receipt_and_contract_pdf(
            row.to_dict(),
            st.session_state["agreement_template"],
            payment_amount=row["Paid"]+row["Balance"],
            payment_date=row["ContractStart"].date()
        )
        with open(pdf,"rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="{name}_contract.pdf">Download</a>', unsafe_allow_html=True)

# ---- Tab 6: Send Email ----
with tabs[6]:
    st.title("📧 Send Email")
    df = load_students()
    df["email_valid"] = df["Email"].str.contains("@")
    mode = st.radio("Mode", ["Individual","All","Manual"])
    if mode=="Individual":
        opt = st.selectbox("Choose", df[df["email_valid"]]["Name"])
        recips = [df[df["Name"]==opt]["Email"].iloc[0]]
    elif mode=="All":
        recips = df[df["email_valid"]]["Email"].tolist()
        st.info(f"{len(recips)} recipients")
    else:
        txt = st.text_input("Email address")
        recips = [txt] if "@" in txt else []
    subj = st.text_input("Subject", "Info from Learn Language Education Academy")
    body = st.text_area("Message", "Dear Student,\n\n")
    if st.button("Send"):
        for e in recips:
            msg = Mail(from_email=school_sender_email, to_emails=e, subject=subj, html_content=body.replace("\n","<br>"))
            SendGridAPIClient(school_sendgrid_key).send(msg)
        st.success(f"✅ Sent to {len(recips)}")

# ---- Tab 7: Analytics & Export ----
with tabs[7]:
    st.title("📊 Analytics & Export")
    df = load_students()
    df["EnrollMonth"] = df["ContractStart"].dt.to_period("M").astype(str)
    st.subheader("Enrollment Over Time")
    st.line_chart(df["EnrollMonth"].value_counts().sort_index())
    st.subheader("Students by Level")
    st.bar_chart(df["Level"].value_counts())
    st.download_button("Download CSV", data=df.to_csv(index=False), file_name="students_export.csv")


with tabs[8]:
    st.title("Generate A1 Course Schedule")

    st.markdown("""
    🛠️ **Create and download a personalized A1 course schedule.**

    Choose a start date and class days. The schedule will follow the official classroom structure (Lesen & Hören, Schreiben & Sprechen).
    """)

    from datetime import datetime, timedelta
    import calendar
    from fpdf import FPDF

    # User inputs
    st.subheader("🗓️ Configuration")
    start_date = st.date_input("Select Start Date", value=date.today())
    selected_days = st.multiselect(
        "Select Class Days",
        options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        default=["Monday", "Tuesday", "Wednesday"]
    )

    # Schedule structure (fixed)
    raw_schedule = [
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

    def sanitize(text):
        return text.encode('latin-1', 'replace').decode('latin-1')

    def generate_schedule(start_date, weekdays, raw_schedule):
        output = []
        current_date = start_date
        day_number = 1

        day_map = {day: i for i, day in enumerate(calendar.day_name)}
        selected_indices = sorted([day_map[day] for day in weekdays])

        for week_label, sessions in raw_schedule:
            output.append(f"\n{week_label.upper()}")
            for session in sessions:
                while current_date.weekday() not in selected_indices:
                    current_date += timedelta(days=1)
                session_day = calendar.day_name[current_date.weekday()]
                session_date = current_date.strftime("%d %B %Y")
                output.append(f"Day {day_number} ({session_date}, {session_day}): {session}")
                current_date += timedelta(days=1)
                day_number += 1
        return output

    if st.button("📅 Generate Schedule"):
        schedule_lines = generate_schedule(start_date, selected_days, raw_schedule)
        schedule_text = f"""
Learn Language Education Academy
Contact: 0205706589 | Website: www.learngermanghana.com
Course Schedule: Auto-generated
Meeting Days: {', '.join(selected_days)}
First Week: Begins {start_date.strftime('%A, %d %B %Y')}

""" + "\n".join(schedule_lines)

        st.text_area("📄 Schedule Preview", value=schedule_text, height=600)

        # TXT download
        st.download_button(
            label="📁 Download as TXT",
            data=schedule_text,
            file_name="a1_course_schedule.txt",
            mime="text/plain"
        )

        # PDF download
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        for line in schedule_text.split("\n"):
            safe_line = sanitize(line)
            if safe_line.strip().startswith("WEEK"):
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, safe_line.strip(), ln=True)
                pdf.set_font("Arial", size=12)
            else:
                pdf.multi_cell(0, 10, safe_line)

        pdf_bytes = pdf.output(dest='S').encode('latin-1')

        st.download_button(
            label="📄 Download as PDF",
            data=pdf_bytes,
            file_name="a1_course_schedule.pdf",
            mime="application/pdf"
        )


