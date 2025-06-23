"""
Learn Language Education Academy Dashboard

This Streamlit app manages student information, issues receipts/contracts,
sends email notifications, and generates course schedules.

Dependencies
------------
* streamlit>=1.14.0
* pandas>=1.5.0
* fpdf>=1.7.2
* sendgrid>=6.9.1

Run the app in a Python 3 environment with these packages installed, e.g.:
    streamlit run email.py
"""

# ===== Standard Library Imports =====
import base64
import calendar
import json
import os
import urllib.parse
from datetime import date, datetime, timedelta

# ===== Third-Party Imports =====
import numpy as np
import pandas as pd
import streamlit as st
from fpdf import FPDF
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    Attachment,
    FileContent,
    FileName,
    FileType,
    Disposition,
)
import openai  # <-- For AI marking (Schreiben correction/feedback)

# ===== Project-Specific Imports =====
from pdf_utils import generate_receipt_and_contract_pdf
from email_utils import send_emails

# ===== Helper Functions =====
def clean_phone(phone):
    """
    Convert any Ghanaian phone number to WhatsApp-friendly format:
    - Remove spaces, dashes, and '+'
    - If starts with '0', replace with '233'
    - If starts with '233', leave as is
    - Returns only digits
    """
    phone = str(phone).replace(" ", "").replace("+", "").replace("-", "")
    if phone.startswith("0"):
        phone = "233" + phone[1:]
    phone = ''.join(filter(str.isdigit, phone))
    return phone


# ===== PAGE CONFIG (must be first Streamlit command!) =====
st.set_page_config(
    page_title="Learn Language Education Academy Dashboard",
    layout="wide"
)

# === Session State Initialization ===
st.session_state.setdefault("emailed_expiries", set())
st.session_state.setdefault("dismissed_notifs", set())


# === SCHOOL INFO ===
SCHOOL_NAME    = "Learn Language Education Academy"
SCHOOL_EMAIL   = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE   = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# === EMAIL CONFIG ===
school_sendgrid_key = st.secrets.get("general", {}).get("SENDGRID_API_KEY")
school_sender_email = st.secrets.get("general", {}).get("SENDER_EMAIL", SCHOOL_EMAIL)

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
    except Exception:
        second_due_date = payment_date

    payment_status = "FULLY PAID" if balance == 0 else "INSTALLMENT PLAN"

    # Replace placeholders in agreement
    filled = agreement_text.replace("[STUDENT_NAME]", str(student_row.get("Name", ""))) \
        .replace("[DATE]", str(payment_date)) \
        .replace("[CLASS]", str(student_row.get("Level", ""))) \
        .replace("[AMOUNT]", str(payment_amount)) \
        .replace("[FIRST_INSTALMENT]", str(first_instalment)) \
        .replace("[SECOND_INSTALMENT]", str(balance)) \
        .replace("[SECOND_DUE_DATE]", str(second_due_date)) \
        .replace("[COURSE_LENGTH]", str(course_length))

    def safe(txt):
        return str(txt).encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()

    # Header
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, safe(f"{SCHOOL_NAME} Payment Receipt"), ln=True, align="C")

    pdf.set_font("Arial", 'B', size=12)
    pdf.set_text_color(0, 128, 0)
    pdf.cell(200, 10, safe(payment_status), ln=True, align="C")
    pdf.set_text_color(0, 0, 0)

    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, safe(f"Name: {student_row.get('Name','')}"), ln=True)
    pdf.cell(200, 10, safe(f"Student Code: {student_row.get('StudentCode','')}"), ln=True)
    pdf.cell(200, 10, safe(f"Phone: {student_row.get('Phone','')}"), ln=True)
    pdf.cell(200, 10, safe(f"Level: {student_row.get('Level','')}"), ln=True)
    pdf.cell(200, 10, f"Amount Paid: GHS {paid:.2f}", ln=True)
    pdf.cell(200, 10, f"Balance Due: GHS {balance:.2f}", ln=True)
    pdf.cell(200, 10, f"Total Course Fee: GHS {total_fee:.2f}", ln=True)
    pdf.cell(200, 10, safe(f"Contract Start: {student_row.get('ContractStart','')}"), ln=True)
    pdf.cell(200, 10, safe(f"Contract End: {student_row.get('ContractEnd','')}"), ln=True)
    pdf.cell(200, 10, f"Receipt Date: {payment_date}", ln=True)
    pdf.ln(10)
    pdf.cell(0, 10, safe("Thank you for your payment!"), ln=True)
    pdf.cell(0, 10, safe("Signed: Felix Asadu"), ln=True)

    # Contract Section
    pdf.ln(15)
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, safe(f"{SCHOOL_NAME} Student Contract"), ln=True, align="C")

    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    for line in filled.split("\n"):
        pdf.multi_cell(0, 10, safe(line))

    pdf.ln(10)
    pdf.cell(0, 10, safe("Signed: Felix Asadu"), ln=True)

    # Footer timestamp
    pdf.set_y(-15)
    pdf.set_font("Arial", "I", 8)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf.cell(0, 10, safe(f"Generated on {now_str}"), align="C")

    filename = f"{student_row.get('Name','').replace(' ', '_')}_receipt_contract.pdf"
    pdf.output(filename)
    return filename

# === INITIALIZE STUDENT FILE ===
student_file = "students_simple.csv"
def load_students():
    if os.path.exists(student_file):
        return pd.read_csv(student_file)
    else:
        df = pd.DataFrame(columns=[
            "Name", "Phone", "Location", "Level", "Paid", "Balance", "ContractStart", "ContractEnd", "StudentCode", "Email"
        ])
        df.to_csv(student_file, index=False)
        return df

df_main = load_students()

# === GOOGLE SHEET REGISTRATION FORM (PENDING STUDENTS) ===
sheet_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"

# === AGREEMENT TEMPLATE STATE ===
if "agreement_template" not in st.session_state:
    st.session_state["agreement_template"] = """
PAYMENT AGREEMENT

This Payment Agreement is entered into on [DATE] for [CLASS] students of Learn Language Education Academy and Felix Asadu ("Teacher").

Terms of Payment:
1. Payment Amount: The student agrees to pay the teacher a total of [AMOUNT] cedis for the course.
2. Payment Schedule: The payment can be made in full or in two installments: GHS [FIRST_INSTALMENT] for the first installment, and the remaining balance for the second installment. The second installment must be paid by [SECOND_DUE_DATE].
3. Late Payments: In the event of late payment, the school may revoke access to all learning platforms. No refund will be made.
4. Refunds: Once a deposit is made and a receipt is issued, no refunds will be provided.
5. Additional Service: The course lasts [COURSE_LENGTH] weeks. Free supervision for Goethe Exams is valid only if the student remains consistent.

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

st.title("🏫 Learn Language Education Academy Dashboard")
st.caption(f"📍 {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

# 📊 Summary Stats
total_students = len(df_main)
total_paid = df_main["Paid"].sum() if "Paid" in df_main.columns else 0.0

# Load expenses if available
expenses_file = "expenses_all.csv"
if os.path.exists(expenses_file):
    exp_df = pd.read_csv(expenses_file)
    total_expenses = exp_df["Amount"].sum() if "Amount" in exp_df.columns else 0.0
else:
    total_expenses = 0.0

net_profit = total_paid - total_expenses

# === SUMMARY BOX ===
st.markdown(f"""
<div style='background-color:#f9f9f9;border:1px solid #ccc;border-radius:10px;padding:15px;margin-top:10px'>
    <h4>📋 Summary</h4>
    <ul>
        <li>👨‍🎓 <b>Total Students:</b> {total_students}</li>
        <li>💰 <b>Total Collected:</b> GHS {total_paid:,.2f}</li>
        <li>💸 <b>Total Expenses:</b> GHS {total_expenses:,.2f}</li>
        <li>📈 <b>Net Profit:</b> GHS {net_profit:,.2f}</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# --- Persistent Dismissed Notifications Helper ---

def clean_phone(phone):
    phone = str(phone).replace(" ", "").replace("+", "")
    # Converts '024XXXXXXX' to '23324XXXXXXX'
    return "233" + phone[1:] if phone.startswith("0") else phone

DISMISSED_FILE = "dismissed_notifs.json"

def load_dismissed():
    if os.path.exists(DISMISSED_FILE):
        try:
            with open(DISMISSED_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    else:
        return set()

def save_dismissed(dismissed_set):
    with open(DISMISSED_FILE, "w") as f:
        json.dump(list(dismissed_set), f)

# --- Load or create the dismissed set ---
dismissed_notifs = load_dismissed()

# --- Your notification creation logic ---
notifications = []

# Example: Debtors
if "Balance" not in df_main.columns:
    df_main["Balance"] = 0.0
else:
    df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0.0)

for _, row in df_main[df_main["Balance"] > 0].iterrows():
    phone = clean_phone(row.get("Phone", ""))
    name = row.get("Name", "Unknown")
    balance = row["Balance"]
    code = row.get("StudentCode", "")
    message_text = (
        f"Dear {name}, you owe GHS {balance:.2f} for your course ({code}). "
        "Please settle it to remain active."
    )
    wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message_text)}"
    html = (
        f"💰 <b>{name}</b> owes GHS {balance:.2f} "
        f"[<a href='{wa_url}' target='_blank'>📲 WhatsApp</a>]"
    )
    notifications.append((f"debtor_{code}", html))

# Example: Expiries and expired contracts...
# (your code to populate notifications continues here)

# --- Render notifications ---
if notifications:
    st.markdown("""
    <div style='background-color:#fff3cd;border:1px solid #ffc107;
                border-radius:10px;padding:15px;margin-top:10px'>
      <h4>🔔 <b>Notifications</b></h4>
    </div>
    """, unsafe_allow_html=True)

    for key, html in notifications:
        if key in dismissed_notifs:
            continue

        col1, col2 = st.columns([9, 1])
        with col1:
            st.markdown(html, unsafe_allow_html=True)
        with col2:
            if st.button("Dismiss", key="dismiss_" + key):
                dismissed_notifs.add(key)
                save_dismissed(dismissed_notifs)
                st.experimental_rerun()
else:
    st.markdown(f"""
    <div style='background-color:#e8f5e9;border:1px solid #4caf50;
                border-radius:10px;padding:15px;margin-top:10px'>
      <h4>🔔 <b>Notifications</b></h4>
      <p>No urgent alerts. You're all caught up ✅</p>
    </div>
    """, unsafe_allow_html=True)


tabs = st.tabs([
    "📝 Pending Registrations",
    "👩‍🎓 All Students",
    "➕ Add Student",
    "💵 Expenses",
    "📲 WhatsApp Reminders",
    "📄 Generate Contract PDF",
    "📧 Send Email",
    "📊 Analytics & Export",
    "📆 A1 Course Schedule",
    "📝 Assessment & Marking"   # <--- New tab!
])

with tabs[0]:
    st.title("📝 Pending Student Registrations")

    # --- Load new pending students from form sheet ---
    try:
        new_students = pd.read_csv(sheet_url)
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

    # --- Upload Data (only uploads!) ---
    with st.expander("📤 Upload Data"):
        st.subheader("Upload Student CSV")
        uploaded_student_csv = st.file_uploader("Upload students_simple.csv", type=["csv"])
        if uploaded_student_csv is not None:
            df = pd.read_csv(uploaded_student_csv)
            df.to_csv("students_simple.csv", index=False)
            st.success("✅ Student file replaced. (No reload required!)")

        st.subheader("Upload Expenses CSV")
        uploaded_expenses_csv = st.file_uploader("Upload expenses_all.csv", type=["csv"])
        if uploaded_expenses_csv is not None:
            df = pd.read_csv(uploaded_expenses_csv)
            df.to_csv("expenses_all.csv", index=False)
            st.success("✅ Expenses file replaced. (No reload required!)")

    # --- Helper: Clean any email source ---
    def get_clean_email(row):
        raw = row.get("email") or row.get("email_address") or row.get("Email Address") or ""
        return "" if pd.isna(raw) else str(raw).strip()

    # --- Show and approve pending students ---
    if not new_students.empty:
        for i, row in new_students.iterrows():
            fullname   = row.get("full_name") or row.get("name") or f"Student {i}"
            phone      = row.get("phone_number") or row.get("phone") or ""
            email      = get_clean_email(row)
            level      = row.get("class_a1a2_etc") or row.get("class") or row.get("level") or ""
            location   = row.get("location", "")
            emergency  = row.get("emergency_contact_phone_number") or row.get("emergency", "")

            with st.expander(f"{fullname} ({phone})"):
                st.write(f"**Email:** {email or '—'}")
                emergency_input  = st.text_input("Emergency Contact (optional)", value=emergency, key=f"emergency_{i}")
                student_code     = st.text_input("Assign Student Code", key=f"code_{i}")
                contract_start   = st.date_input("Contract Start", value=date.today(), key=f"start_{i}")
                course_length    = st.number_input("Course Length (weeks)", min_value=1, value=12, key=f"length_{i}")
                contract_end     = st.date_input("Contract End", value=contract_start + timedelta(weeks=course_length), key=f"end_{i}")
                paid             = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0, key=f"paid_{i}")
                balance          = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0, key=f"bal_{i}")
                first_instalment = st.number_input("First Instalment", min_value=0.0, value=1500.0, key=f"firstinst_{i}")
                attach_pdf       = st.checkbox("Attach PDF to Email?", value=True, key=f"pdf_{i}")
                send_email       = st.checkbox("Send Welcome Email?", value=bool(email), key=f"email_{i}")

                if st.button("Approve & Add", key=f"approve_{i}"):
                    if not student_code:
                        st.warning("Enter a unique student code.")
                        continue

                    # load or init approved_df
                    if os.path.exists("students_simple.csv"):
                        approved_df = pd.read_csv("students_simple.csv")
                    else:
                        approved_df = pd.DataFrame(columns=[
                            "Name","Phone","Email","Location","Level",
                            "Paid","Balance","ContractStart","ContractEnd",
                            "StudentCode","Emergency Contact (Phone Number)"
                        ])

                    if student_code in approved_df["StudentCode"].values:
                        st.warning("❗ Student Code exists. Choose another.")
                        continue

                    student_dict = {
                        "Name": fullname,
                        "Phone": phone,
                        "Email": email,
                        "Location": location,
                        "Level": level,
                        "Paid": paid,
                        "Balance": balance,
                        "ContractStart": str(contract_start),
                        "ContractEnd": str(contract_end),
                        "StudentCode": student_code,
                        "Emergency Contact (Phone Number)": emergency_input
                    }

                    approved_df = pd.concat([approved_df, pd.DataFrame([student_dict])], ignore_index=True)
                    approved_df.to_csv("students_simple.csv", index=False)

                    total_fee = paid + balance
                    pdf_file = generate_receipt_and_contract_pdf(
                        student_dict,
                        st.session_state["agreement_template"],
                        payment_amount=total_fee,
                        payment_date=contract_start,
                        first_instalment=first_instalment,
                        course_length=course_length
                    )

                    # optional welcome email
                    if send_email and email and school_sendgrid_key:
                        try:
                            msg = Mail(
                                from_email=school_sender_email,
                                to_emails=email,
                                subject=f"Welcome to {SCHOOL_NAME}",
                                html_content=(
                                    f"Dear {fullname},<br><br>"
                                    f"Welcome to {SCHOOL_NAME}!<br>"
                                    f"Student Code: <b>{student_code}</b><br>"
                                    f"Class: {level}<br>"
                                    f"Contract: {contract_start} to {contract_end}<br>"
                                    f"Paid: GHS {paid}<br>"
                                    f"Balance: GHS {balance}<br><br>"
                                    f"For help, contact us at {SCHOOL_EMAIL} or {SCHOOL_PHONE}."
                                )
                            )
                            if attach_pdf:
                                with open(pdf_file, "rb") as f:
                                    encoded = base64.b64encode(f.read()).decode()
                                    msg.attachment = Attachment(
                                        FileContent(encoded),
                                        FileName(pdf_file),
                                        FileType("application/pdf"),
                                        Disposition("attachment")
                                    )
                            SendGridAPIClient(school_sendgrid_key).send(msg)
                            st.success(f"📧 Email sent to {email}")
                        except Exception as e:
                            st.warning(f"⚠️ Email failed: {e}")

                    st.success(f"✅ {fullname} approved and saved.")
                    st.stop()

with tabs[1]:
    st.title("👩‍🎓 All Students (Edit, Update, Delete, Receipt)")
    today = date.today()

    # Load or initialize students
    if os.path.exists(student_file):
        df_main = pd.read_csv(student_file)
    else:
        df_main = pd.DataFrame()

    # Ensure required columns exist
    required_cols = [
        "Name", "Phone", "Email", "Location", "Level",
        "Paid", "Balance", "ContractStart", "ContractEnd",
        "StudentCode", "Emergency Contact (Phone Number)"
    ]
    for col in required_cols:
        if col not in df_main.columns:
            df_main[col] = ""

    # Numeric/Date conversions
    df_main["Paid"] = pd.to_numeric(df_main["Paid"], errors="coerce").fillna(0.0)
    df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0.0)
    df_main["ContractEnd"] = pd.to_datetime(df_main["ContractEnd"], errors="coerce")
    df_main["Status"] = "Unknown"
    mask_valid = df_main["ContractEnd"].notna()
    df_main.loc[mask_valid, "Status"] = np.where(
        df_main.loc[mask_valid, "ContractEnd"].dt.date < today,
        "Completed",
        "Enrolled"
    )

    # 🔄 Live Search and Filters
    search_term    = st.text_input("🔍 Search Student by Name or Code")
    levels         = ["All"] + sorted(df_main["Level"].dropna().unique().tolist())
    selected_level = st.selectbox("📋 Filter by Class Level", levels)
    statuses       = ["All", "Enrolled", "Completed", "Unknown"]
    status_filter  = st.selectbox("Filter by Status", statuses)

    view_df = df_main.copy()
    if search_term:
        view_df = view_df[
            view_df["Name"].str.contains(search_term, case=False, na=False) |
            view_df["StudentCode"].str.contains(search_term, case=False, na=False)
        ]
    if selected_level != "All":
        view_df = view_df[view_df["Level"] == selected_level]
    if status_filter != "All":
        view_df = view_df[view_df["Status"] == status_filter]

    if view_df.empty:
        st.info("No students found in your database.")
    else:
        # -------- Pagination setup --------
        ROWS_PER_PAGE = 10
        total_rows = len(view_df)
        total_pages = (total_rows - 1) // ROWS_PER_PAGE + 1

        page = st.number_input(
            f"Page (1-{total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="students_page"
        )
        start_idx = (page - 1) * ROWS_PER_PAGE
        end_idx = start_idx + ROWS_PER_PAGE

        paged_df = view_df.iloc[start_idx:end_idx].reset_index(drop=True)
        st.dataframe(
            paged_df[["Name", "StudentCode", "Level", "Phone", "Paid", "Balance", "Status"]],
            use_container_width=True
        )

        # --- Select a student for details ---
        student_names = paged_df["Name"].tolist()
        if student_names:
            selected_student = st.selectbox("Select a student to view/edit details", student_names, key="select_student_detail")
            student_row = paged_df[paged_df["Name"] == selected_student].iloc[0]

            idx = view_df[view_df["Name"] == selected_student].index[0]
            unique_key = f"{student_row['StudentCode']}_{idx}"
            status_color = (
                "🟢" if student_row["Status"] == "Enrolled" else
                "🔴" if student_row["Status"] == "Completed" else
                "⚪"
            )

            with st.expander(f"{status_color} {student_row['Name']} ({student_row['StudentCode']}) [{student_row['Status']}]", expanded=True):
                # Editable fields
                name_input           = st.text_input("Name", value=student_row["Name"], key=f"name_{unique_key}")
                phone_input          = st.text_input("Phone", value=student_row["Phone"], key=f"phone_{unique_key}")
                email_input          = st.text_input("Email", value=student_row["Email"], key=f"email_{unique_key}")
                location_input       = st.text_input("Location", value=student_row["Location"], key=f"loc_{unique_key}")
                level_input          = st.text_input("Level", value=student_row["Level"], key=f"level_{unique_key}")
                paid_input           = st.number_input("Paid", value=float(student_row["Paid"]), key=f"paid_{unique_key}")
                balance_input        = st.number_input("Balance", value=float(student_row["Balance"]), key=f"bal_{unique_key}")
                contract_start_input = st.text_input("Contract Start", value=str(student_row["ContractStart"]), key=f"cs_{unique_key}")
                contract_end_input   = st.text_input("Contract End", value=str(student_row["ContractEnd"].date()) if pd.notna(student_row["ContractEnd"]) else "", key=f"ce_{unique_key}")
                code_input           = st.text_input("Student Code", value=student_row["StudentCode"], key=f"code_{unique_key}")
                emergency_input      = st.text_input("Emergency Contact", value=student_row["Emergency Contact (Phone Number)"], key=f"em_{unique_key}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Update", key=f"update_{unique_key}"):
                        df_main.at[idx, "Name"]  = name_input
                        df_main.at[idx, "Phone"] = phone_input
                        df_main.at[idx, "Email"] = email_input
                        df_main.at[idx, "Location"] = location_input
                        df_main.at[idx, "Level"] = level_input
                        df_main.at[idx, "Paid"] = paid_input
                        df_main.at[idx, "Balance"] = balance_input
                        df_main.at[idx, "ContractStart"] = contract_start_input
                        df_main.at[idx, "ContractEnd"] = contract_end_input
                        df_main.at[idx, "StudentCode"] = code_input
                        df_main.at[idx, "Emergency Contact (Phone Number)"] = emergency_input
                        df_main.to_csv(student_file, index=False)
                        st.success("✅ Student updated.")
                        st.experimental_rerun()
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{unique_key}"):
                        df_main = df_main.drop(idx).reset_index(drop=True)
                        df_main.to_csv(student_file, index=False)
                        st.success("❌ Student deleted.")
                        st.experimental_rerun()
                with col3:
                    if st.button("📄 Receipt", key=f"receipt_{unique_key}"):
                        total_fee   = paid_input + balance_input
                        parsed_date = pd.to_datetime(contract_start_input, errors="coerce").date()
                        pdf_path    = generate_receipt_and_contract_pdf(
                            student_row,
                            st.session_state["agreement_template"],
                            payment_amount=total_fee,
                            payment_date=parsed_date
                        )
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        b64 = base64.b64encode(pdf_bytes).decode()
                        download_link = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{name_input.replace(" ", "_")}_receipt.pdf">Download Receipt</a>'
                        )
                        st.markdown(download_link, unsafe_allow_html=True)

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
                st.rerun()

with tabs[3]:
    st.title("💵 Expenses and Financial Summary")

    expenses_file = "expenses_all.csv"

    # ✅ Load or initialize expense data
    if os.path.exists(expenses_file):
        exp = pd.read_csv(expenses_file)
    else:
        exp = pd.DataFrame(columns=["Type", "Item", "Amount", "Date"])
        exp.to_csv(expenses_file, index=False)

    # ✅ Add new expense
    with st.form("add_expense_form"):
        exp_type = st.selectbox("Type", ["Bill", "Rent", "Salary", "Marketing", "Other"])
        exp_item = st.text_input("Expense Item")
        exp_amount = st.number_input("Amount (GHS)", min_value=0.0, step=1.0)
        exp_date = st.date_input("Date", value=date.today())
        submit_exp = st.form_submit_button("Add Expense")

        if submit_exp and exp_item and exp_amount > 0:
            new_exp = pd.DataFrame([{
                "Type": exp_type,
                "Item": exp_item,
                "Amount": exp_amount,
                "Date": exp_date
            }])
            exp = pd.concat([exp, new_exp], ignore_index=True)
            exp.to_csv(expenses_file, index=False)
            st.success(f"✅ Recorded: {exp_type} – {exp_item}")
            st.session_state["should_rerun"] = True
            st.experimental_rerun()

    # ✅ Convert dates if not done
    exp["Date"] = pd.to_datetime(exp["Date"], errors="coerce")
    exp["Month"] = exp["Date"].dt.strftime("%B %Y")
    exp["Year"] = exp["Date"].dt.year

    st.write("### All Expenses")

    # --- Pagination for expenses ---
    ROWS_PER_PAGE = 10
    total_exp_rows = len(exp)
    total_exp_pages = (total_exp_rows - 1) // ROWS_PER_PAGE + 1

    if total_exp_pages > 1:
        exp_page = st.number_input(
            f"Page (1-{total_exp_pages})",
            min_value=1, max_value=total_exp_pages, value=1, step=1,
            key="expenses_page"
        )
    else:
        exp_page = 1

    exp_start_idx = (exp_page - 1) * ROWS_PER_PAGE
    exp_end_idx = exp_start_idx + ROWS_PER_PAGE

    exp_paged = exp.iloc[exp_start_idx:exp_end_idx].reset_index()  # Keep index for delete/edit reference

    for i, row in exp_paged.iterrows():
        with st.expander(
            f"{row['Type']} | {row['Item']} | GHS {row['Amount']} | {row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else ''}"
        ):
            edit_col, delete_col = st.columns([2, 1])
            with edit_col:
                # Pre-fill values for editing
                new_type = st.selectbox("Type", ["Bill", "Rent", "Salary", "Marketing", "Other"], index=["Bill", "Rent", "Salary", "Marketing", "Other"].index(row['Type']) if row['Type'] in ["Bill", "Rent", "Salary", "Marketing", "Other"] else 0, key=f"type_{exp_start_idx+i}")
                new_item = st.text_input("Item", value=row['Item'], key=f"item_{exp_start_idx+i}")
                new_amount = st.number_input("Amount (GHS)", min_value=0.0, step=1.0, value=float(row['Amount']), key=f"amount_{exp_start_idx+i}")
                new_date = st.date_input("Date", value=row['Date'].date() if pd.notna(row['Date']) else date.today(), key=f"date_{exp_start_idx+i}")
                if st.button("💾 Update", key=f"update_exp_{exp_start_idx+i}"):
                    # Update in main exp DataFrame (use row['index'] for real index in exp)
                    exp.at[row['index'], "Type"] = new_type
                    exp.at[row['index'], "Item"] = new_item
                    exp.at[row['index'], "Amount"] = new_amount
                    exp.at[row['index'], "Date"] = pd.to_datetime(new_date)
                    exp.to_csv(expenses_file, index=False)
                    st.success("✅ Expense updated.")
                    st.experimental_rerun()
            with delete_col:
                if st.button("🗑️ Delete", key=f"delete_exp_{exp_start_idx+i}"):
                    exp = exp.drop(row['index']).reset_index(drop=True)
                    exp.to_csv(expenses_file, index=False)
                    st.success("❌ Expense deleted.")
                    st.experimental_rerun()

    # ✅ Summary Section
    st.write("### Summary")
    if os.path.exists("students_simple.csv"):
        df_main = pd.read_csv("students_simple.csv")
        total_paid = df_main["Paid"].sum() if "Paid" in df_main.columns else 0.0
    else:
        total_paid = 0.0

    total_expenses = exp["Amount"].sum() if not exp.empty else 0.0
    net_profit = total_paid - total_expenses

    st.info(f"💰 **Total Collected:** GHS {total_paid:,.2f}")
    st.info(f"💸 **Total Expenses:** GHS {total_expenses:,.2f}")
    st.success(f"📈 **Net Profit:** GHS {net_profit:,.2f}")

    # ✅ Monthly and Yearly Groupings
    if not exp.empty:
        st.write("### Expenses by Month")
        st.dataframe(exp.groupby("Month")["Amount"].sum().reset_index())

        st.write("### Expenses by Year")
        st.dataframe(exp.groupby("Year")["Amount"].sum().reset_index())

with tabs[4]:
    st.title("📲 WhatsApp Reminders for Debtors")

    def clean_phone(phone):
        """
        Convert any Ghanaian phone number to WhatsApp-friendly format:
        - Remove spaces, dashes, and '+'
        - If starts with '0', replace with '233'
        - Returns only digits
        """
        phone = str(phone).replace(" ", "").replace("+", "").replace("-", "")
        if phone.startswith("0"):
            phone = "233" + phone[1:]
        phone = ''.join(filter(str.isdigit, phone))
        return phone

    # Load student data
    if os.path.exists("students_simple.csv"):
        df_main = pd.read_csv("students_simple.csv")
    else:
        df_main = pd.DataFrame()

    if not df_main.empty and "Balance" in df_main.columns and "Phone" in df_main.columns:
        df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0.0)
        df_main["Phone"] = df_main["Phone"].astype(str)

        debtors = df_main[df_main["Balance"] > 0]

        if not debtors.empty:
            st.write("### Students with Outstanding Balances")

            for _, row in debtors.iterrows():
                name = row.get("Name", "Unknown")
                level = row.get("Level", "")
                balance = float(row.get("Balance", 0.0))
                code = row.get("StudentCode", "")
                phone = clean_phone(row.get("Phone", ""))

                # Date logic: contract start and due date (one month after)
                contract_start = row.get("ContractStart", "")
                if contract_start and not pd.isnull(contract_start):
                    contract_start_dt = pd.to_datetime(contract_start, errors="coerce")
                    contract_start_fmt = contract_start_dt.strftime("%d %B %Y")
                    due_date_dt = contract_start_dt + timedelta(days=30)
                    due_date_fmt = due_date_dt.strftime("%d %B %Y")
                else:
                    contract_start_fmt = "N/A"
                    due_date_fmt = "soon"

                message = (
                    f"Dear {name}, this is a reminder that your balance for your {level} class is GHS {balance:.2f} "
                    f"and is due by {due_date_fmt}. "
                    f"Contract start: {contract_start_fmt}.\n"
                    "Kindly make the payment to continue learning with us. Thank you!\n\n"
                    "Payment Methods:\n"
                    "1. Mobile Money\n"
                    "   Number: 0245022743\n"
                    "   Name: Felix Asadu\n"
                    "2. Access Bank (Cedis)\n"
                    "   Account Number: 1050000008017\n"
                    "   Name: Learn Language Education Academy"
                )

                encoded_msg = urllib.parse.quote(message)
                wa_url = f"https://wa.me/{phone}?text={encoded_msg}"

                st.markdown(
                    f"**{name}** (GHS {balance:.2f} due) – "
                    f"[📲 Remind via WhatsApp](<{wa_url}>)"
                )
        else:
            st.success("✅ No students with unpaid balances.")
    else:
        st.warning("⚠️ Required columns 'Balance' or 'Phone' are missing in your data.")


with tabs[5]:
    st.title("📄 Generate Contract PDF for Any Student")

    if not df_main.empty and "Name" in df_main.columns:
        student_names = df_main["Name"].tolist()
        selected_name = st.selectbox("Select Student", student_names)

        if st.button("Generate PDF"):
            # Fetch student data
            student_row = df_main[df_main["Name"] == selected_name].iloc[0]

            # Parse ContractStart date safely
            raw_date = student_row.get("ContractStart", date.today())
            pd_date = pd.to_datetime(raw_date, errors="coerce")
            payment_date = pd_date.date() if not pd.isnull(pd_date) else date.today()

            # Calculate amounts
            paid = float(student_row.get("Paid", 0))
            balance = float(student_row.get("Balance", 0))
            total_fee = paid + balance

            # Create PDF (no logo)
            pdf = FPDF()
            pdf.add_page()

            # 1) Payment status banner
            payment_status = "FULLY PAID" if balance == 0 else "INSTALLMENT PLAN"
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(0, 128, 0)
            pdf.cell(200, 10, payment_status, ln=True, align="C")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(5)

            # 2) Receipt header
            pdf.set_font("Arial", size=14)
            pdf.cell(200, 10, f"{SCHOOL_NAME} Payment Receipt", ln=True, align="C")

            # 3) Receipt details
            pdf.set_font("Arial", size=12)
            pdf.ln(10)
            pdf.cell(200, 10, f"Name: {student_row.get('Name','')}", ln=True)
            pdf.cell(200, 10, f"Student Code: {student_row.get('StudentCode','')}", ln=True)
            pdf.cell(200, 10, f"Phone: {student_row.get('Phone','')}", ln=True)
            pdf.cell(200, 10, f"Level: {student_row.get('Level','')}", ln=True)
            pdf.cell(200, 10, f"Amount Paid: GHS {paid:.2f}", ln=True)
            pdf.cell(200, 10, f"Balance Due: GHS {balance:.2f}", ln=True)
            pdf.cell(200, 10, f"Total Course Fee: GHS {total_fee:.2f}", ln=True)
            pdf.cell(200, 10, f"Contract Start: {student_row.get('ContractStart','')}", ln=True)
            pdf.cell(200, 10, f"Contract End: {student_row.get('ContractEnd','')}", ln=True)
            pdf.cell(200, 10, f"Receipt Date: {payment_date}", ln=True)

            # 4) Thank-you and signature
            pdf.ln(10)
            pdf.cell(0, 10, "Thank you for your payment!", ln=True)
            pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)

            # 5) Contract section
            pdf.ln(15)
            pdf.set_font("Arial", size=14)
            pdf.cell(200, 10, f"{SCHOOL_NAME} Student Contract", ln=True, align="C")

            pdf.set_font("Arial", size=12)
            pdf.ln(10)
            contract_text = st.session_state.get("agreement_template", "")
            filled = (
                contract_text
                .replace("[STUDENT_NAME]", str(student_row.get("Name","")))
                .replace("[DATE]", str(payment_date))
                .replace("[CLASS]", str(student_row.get("Level","")))
                .replace("[AMOUNT]", str(total_fee))
                .replace("[FIRST_INSTALMENT]", "1500")
                .replace("[SECOND_INSTALMENT]", str(balance))
                .replace("[SECOND_DUE_DATE]", str(payment_date + timedelta(days=30)))
                .replace("[COURSE_LENGTH]", "12")
            )
            for line in filled.split("\n"):
                safe_line = line.encode("latin-1", "replace").decode("latin-1")
                pdf.multi_cell(0, 10, safe_line)

            pdf.ln(10)
            pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)

            # 6) Download button
            pdf_bytes = pdf.output(dest="S").encode("latin-1", errors="replace")
            st.download_button(
                "📄 Download PDF",
                data=pdf_bytes,
                file_name=f"{selected_name.replace(' ', '_')}_contract.pdf",
                mime="application/pdf"
            )
            st.success("✅ PDF contract generated.")
    else:
        st.warning("No student data available.")

with tabs[6]:
    st.title("📧 Send Email to Student(s)")

    # Normalize column names
    df_main.columns = [c.strip().lower() for c in df_main.columns]

    # Ensure 'email' column exists
    if "email" not in df_main.columns:
        df_main["email"] = ""

    # Get students with valid emails
    email_entries = [(row["name"], row["email"]) for _, row in df_main.iterrows()
                     if isinstance(row.get("email", ""), str) and "@" in row.get("email", "")]
    email_options = [f"{name} ({email})" for name, email in email_entries]
    email_lookup = {f"{name} ({email})": email for name, email in email_entries}

    st.markdown("### 👤 Choose Recipients")

    mode = st.radio("Send email to:", ["Individual student", "All students with email", "Manual entry"])

    recipients = []

    if mode == "Individual student":
        if email_options:
            selected = st.selectbox("Select student", email_options)
            recipients = [email_lookup[selected]]
        else:
            st.warning("⚠️ No valid student emails found in your database.")

    elif mode == "All students with email":
        if email_entries:
            recipients = [email for _, email in email_entries]
            st.info(f"✅ {len(recipients)} student(s) will receive this email.")
        else:
            st.warning("⚠️ No student emails found. Upload a proper student file or update emails.")

    elif mode == "Manual entry":
        manual_email = st.text_input("Enter email address manually")
        if "@" in manual_email:
            recipients = [manual_email]
        else:
            st.warning("Enter a valid email address to proceed.")

    st.markdown("### ✍️ Compose Message")
    subject = st.text_input("Email Subject", value="Information from Learn Language Education Academy")
    message = st.text_area("Message Body (HTML or plain text)", value="Dear Student,\n\n...", height=200)

    file_upload = st.file_uploader("📎 Attach a file (optional)", type=["pdf", "doc", "jpg", "png", "jpeg"])

    MAX_ATTACHMENT_MB = 5  # maximum file size allowed (MB)
    ALLOWED_MIME_TYPES = [
        "application/pdf",
        "image/jpeg", "image/png",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]

    if st.button("Send Email"):
        if not recipients:
            st.warning("❗ Please select or enter at least one email address.")
            st.stop()

        sent = 0
        failed = []
        attachment = None

        if file_upload:
            try:
                # File size check
                file_upload.seek(0, os.SEEK_END)
                file_size_mb = file_upload.tell() / (1024 * 1024)
                file_upload.seek(0)
                if file_size_mb > MAX_ATTACHMENT_MB:
                    st.error(f"Attachment is too large (>{MAX_ATTACHMENT_MB}MB). Please upload a smaller file.")
                    file_upload = None

                # File type check
                if file_upload and file_upload.type not in ALLOWED_MIME_TYPES:
                    st.error("Unsupported file type! Please upload PDF, JPG, PNG, or DOC/DOCX files only.")
                    file_upload = None

                # Attach only if checks passed
                if file_upload:
                    file_data = file_upload.read()
                    encoded = base64.b64encode(file_data).decode()
                    attachment = Attachment(
                        FileContent(encoded),
                        FileName(file_upload.name),
                        FileType(file_upload.type),
                        Disposition("attachment")
                    )
            except Exception as e:
                st.error(f"❌ Failed to process attachment: {e}")
                attachment = None
                file_upload = None

        for email in recipients:
            try:
                msg = Mail(
                    from_email=school_sender_email,
                    to_emails=email,
                    subject=subject,
                    html_content=message.replace("\n", "<br>")
                )
                if attachment:
                    msg.attachment = attachment

                client = SendGridAPIClient(school_sendgrid_key)
                client.send(msg)
                sent += 1
            except Exception as e:
                failed.append(email)

        st.success(f"✅ Sent to {sent} student(s).")
        if failed:
            st.warning(f"⚠️ Failed to send to: {', '.join(failed)}")


with tabs[7]:
    st.title("📊 Analytics & Export")

    if os.path.exists("students_simple.csv"):
        df_main = pd.read_csv("students_simple.csv")
    else:
        df_main = pd.DataFrame()

    st.subheader("📈 Enrollment Over Time")

    if not df_main.empty and "ContractStart" in df_main.columns:
        df_main["EnrollDate"] = pd.to_datetime(df_main["ContractStart"], errors="coerce")

        # ✅ Filter by year
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

with tabs[9]:  # Assignment Marking & Scores Tab

    st.title("📝 Assignment Marking & Scores")

    # ---- Assignment lists ----
    A1_ASSIGNMENTS = [
        "Lesen and Horen 0.1",
        "Lesen and Horen 0.2",
        "Lesen and Horen 1.1",
        "Lesen and Horen 1.2",
        "Lesen and Horen 2",
        "Lesen and Horen 3",
        "Lesen and Horen 4",
        "Lesen and Horen 5",
        "Lesen and Horen 6",
        "Lesen and Horen 7",
        "Lesen and Horen 8",
        "Lesen and Horen 9",
        "Lesen and Horen 10",
        "Lesen and Horen 11",
        "Lesen and Horen 12.1",
        "Lesen and Horen 12.2",
        "Lesen and Horen 13",
        "Lesen and Horen 14",
        "Mock Test Lesen",
        "Mock Test Lesen and Horen"
    ]
    # Reuse your existing code for A2/B1/B2
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
    raw_schedule_b2 = []  # Add later if needed

    def flatten_assignments(schedule):
        assignments = []
        for week, topics in schedule:
            for t in topics:
                assignments.append(f"{week}: {t}")
        return assignments

    LEVELS = ["A1", "A2", "B1", "B2"]
    ASSIGNMENTS = {
        "A1": A1_ASSIGNMENTS,
        "A2": flatten_assignments(raw_schedule_a2),
        "B1": flatten_assignments(raw_schedule_b1),
        "B2": []  # Placeholder for B2
    }

    # ---- Reference answers dicts (edit/expand as needed) ----
    A1_REFERENCE_ANSWERS = {
        "Lesen and Horen 0.1": {
            "Lesen": """1. C Guten Morgen
2. D Guten Tag
3. B Guten Abend 
4. B Gute Nacht
5. C Guten Morgen
6. C Wie geht es Ihnen
7. B Auf wiedersehen
8. A Tschüss 
9. C Guten Abend 
10. D Gute Nacht""",
            "Hören": ""
        },
        # Add for others as needed...
    }
    A2_REFERENCE_ANSWERS = {
        "Woche 1: 1.1. Small Talk (Exercise)": {
            "Lesen": """1. C In einer Schule 
2. B Weil sie gerne mit Kindem arbeitet
3. A In einem Buro
4. B Tennis
5. B Es war sonnig und warm
6. B Italien und Spanien
7. C Weil die Blaume so schön bunt sind""",
            "Hören": """1. B Ins Kino gehen
2. A Weil sie spannende Geschichten liebt 
3. A Tennis
4. B Es war sonnig und warm 
5. Einen Spaziergang machen""",
            "Schreiben": "",
            "Sprechen": ""
        },
        # Add for others as needed...
    }
    B1_REFERENCE_ANSWERS = {}
    B2_REFERENCE_ANSWERS = {}

    def get_default_ref(level, assignment, skill):
        refs = {
            "A1": A1_REFERENCE_ANSWERS,
            "A2": A2_REFERENCE_ANSWERS,
            "B1": B1_REFERENCE_ANSWERS,
            "B2": B2_REFERENCE_ANSWERS,
        }
        return refs.get(level, {}).get(assignment, {}).get(skill, "")

    # ---- Load students from your main file ----
    student_file = "students_simple.csv"
    if os.path.exists(student_file):
        df_students = pd.read_csv(student_file)
        student_names = df_students["Name"].dropna().unique().tolist()
    else:
        student_names = []

    # ---- Score storage file ----
    SCORE_FILE = "student_assignment_scores.csv"
    SCORE_COLUMNS = [
        "Date", "Student", "Level", "Assignment",
        "Reference_Lesen", "Reference_Horen", "Reference_Schreiben", "Reference_Sprechen",
        "Student_Lesen", "Student_Horen", "Student_Schreiben", "Student_Sprechen",
        "Lesen_Score", "Horen_Score", "Schreiben_Score", "Sprechen_Score",
        "AI_Feedback", "AI_Correction"
    ]
    if not os.path.exists(SCORE_FILE):
        pd.DataFrame(columns=SCORE_COLUMNS).to_csv(SCORE_FILE, index=False)

    st.subheader("Record Assignment Scores")
    level = st.selectbox("Select Level", LEVELS)
    student = st.selectbox("Select Student", student_names)
    assignment = st.selectbox("Assignment", ASSIGNMENTS[level] if ASSIGNMENTS[level] else ["No assignments (add later)"])

    with st.expander("Reference Answers (auto-filled, editable for each assignment)"):
        ref_lesen = st.text_area("Reference Answer: Lesen", value=get_default_ref(level, assignment, "Lesen"))
        ref_horen = st.text_area("Reference Answer: Hören", value=get_default_ref(level, assignment, "Hören"))
        ref_schreiben = st.text_area("Reference Answer: Schreiben", value=get_default_ref(level, assignment, "Schreiben")) if level != "A1" else ""
        ref_sprechen = st.text_area("Reference Answer: Sprechen", value=get_default_ref(level, assignment, "Sprechen")) if level != "A1" else ""

    with st.expander("Student Answers & Scores"):
        student_lesen = st.text_area("Student's Lesen Answer")
        student_horen = st.text_area("Student's Hören Answer")
        student_schreiben = st.text_area("Student's Schreiben Answer") if level != "A1" else ""
        student_sprechen = st.text_area("Student's Sprechen Answer") if level != "A1" else ""

        lesen_score = st.number_input("Lesen Score", 0, 20, step=1)
        horen_score = st.number_input("Hören Score", 0, 20, step=1)
        schreiben_score = st.number_input("Schreiben Score", 0, 20, step=1) if level != "A1" else ""
        sprechen_score = st.number_input("Sprechen Score", 0, 20, step=1) if level != "A1" else ""

    # --- AI Mark Schreiben (A2/B1/B2 only) ---
    ai_feedback = ""
    ai_correction = ""
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if level != "A1" and student_schreiben and OPENAI_API_KEY:
        if st.button("Auto-Mark Schreiben (OpenAI)"):
            with st.spinner("Marking with OpenAI..."):
                try:
                    openai.api_key = OPENAI_API_KEY
                    prompt = (
                        f"Correct this German {level} Schreiben assignment, give clear feedback in simple German, and assign a score out of 20. "
                        f"Student answer:\n{student_schreiben}\n"
                        "Respond as:\nKorrigierter Text:\n[correction]\n\nFeedback:\n[feedback]\n\nPunktzahl: [score]/20"
                    )
                    resp = openai.ChatCompletion.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0
                    )
                    result = resp.choices[0].message.content
                    try:
                        ai_correction = result.split("Korrigierter Text:")[1].split("Feedback:")[0].strip()
                        ai_feedback = result.split("Feedback:")[1].split("Punktzahl:")[0].strip()
                        score_part = result.split("Punktzahl:")[1].split("/")[0].strip()
                        schreiben_score = int("".join([c for c in score_part if c.isdigit()]))
                    except Exception:
                        ai_correction = result
                        ai_feedback = ""
                    st.success(f"Correction:\n{ai_correction}\n\nFeedback:\n{ai_feedback}\n\nScore: {schreiben_score}/20")
                except Exception as e:
                    st.error(f"OpenAI Error: {e}")

    if st.button("Save Assignment Score"):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        score_df = pd.read_csv(SCORE_FILE)
        new_row = {
            "Date": now, "Student": student, "Level": level, "Assignment": assignment,
            "Reference_Lesen": ref_lesen, "Reference_Horen": ref_horen, "Reference_Schreiben": ref_schreiben, "Reference_Sprechen": ref_sprechen,
            "Student_Lesen": student_lesen, "Student_Horen": student_horen, "Student_Schreiben": student_schreiben, "Student_Sprechen": student_sprechen,
            "Lesen_Score": lesen_score, "Horen_Score": horen_score,
            "Schreiben_Score": schreiben_score if schreiben_score != "" else "",
            "Sprechen_Score": sprechen_score if sprechen_score != "" else "",
            "AI_Feedback": ai_feedback,
            "AI_Correction": ai_correction
        }
        score_df = pd.concat([score_df, pd.DataFrame([new_row])], ignore_index=True)
        score_df.to_csv(SCORE_FILE, index=False)
        st.success("✅ Score recorded!")

    st.subheader("Student Assignment History")
    hist_df = pd.read_csv(SCORE_FILE)
    filt = (hist_df["Student"] == student) & (hist_df["Level"] == level)
    st.dataframe(hist_df[filt].sort_values("Date", ascending=False), use_container_width=True)

    if not hist_df[filt].empty:
        avg = hist_df[filt][["Lesen_Score", "Horen_Score", "Schreiben_Score", "Sprechen_Score"]].apply(pd.to_numeric, errors="coerce").mean(axis=1).mean()
        st.info(f"**Overall Average Score for {student} ({level}): {avg:.2f}**")

    # ---- Export options ----
    st.subheader("Export Scores")
    st.download_button("Export Full CSV", data=hist_df.to_csv(index=False), file_name="student_assignment_scores.csv")

    # Export only this chapter (Lesen & Hören)
    chapter_mask = (hist_df["Level"] == level) & (hist_df["Assignment"] == assignment)
    chapter_df = hist_df[chapter_mask]
    lesen_hoeren_cols = [
        "Student", "Level", "Assignment",
        "Reference_Lesen", "Student_Lesen", "Lesen_Score",
        "Reference_Horen", "Student_Horen", "Horen_Score"
    ]
    chapter_export = chapter_df[lesen_hoeren_cols]
    st.download_button(
        f"Export Only '{assignment}' (Lesen & Hören)",
        data=chapter_export.to_csv(index=False),
        file_name=f"{assignment.replace(' ', '_')}_lesen_hoeren.csv"
    )

    # Export all students for current assignment (Lesen & Hören)
    st.download_button(
        f"Export All Students '{assignment}' (Lesen & Hören)",
        data=chapter_export.to_csv(index=False),
        file_name=f"all_{assignment.replace(' ', '_')}_lesen_hoeren.csv"
    )
