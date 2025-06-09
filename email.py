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

# === NOTIFICATIONS with Dismiss Buttons (no explicit rerun) ===
today = date.today()

# 1. Initialize dismissed set
st.session_state.setdefault("dismissed_notifs", set())

def clean_phone(phone):
    phone = str(phone).replace(" ", "").replace("+", "")
    return "233" + phone[1:] if phone.startswith("0") else phone

notifications = []

# 2. Debtors
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

# 3. Ensure ContractEnd exists & is datetime
if "ContractEnd" not in df_main.columns:
    df_main["ContractEnd"] = pd.NaT
df_main["ContractEnd"] = pd.to_datetime(df_main["ContractEnd"], errors="coerce")

# 4. Expiring soon (next 30 days)
for _, row in df_main[
    (df_main["ContractEnd"] >= pd.Timestamp(today)) &
    (df_main["ContractEnd"] <= pd.Timestamp(today + timedelta(days=30)))
].iterrows():
    name = row.get("Name", "Unknown")
    end_date = row["ContractEnd"].date()
    key = f"expiring_{row['StudentCode']}"
    html = f"⏳ <b>{name}</b>'s contract ends on {end_date}"
    notifications.append((key, html))

# 5. Expired contracts
for _, row in df_main[df_main["ContractEnd"] < pd.Timestamp(today)].iterrows():
    name = row.get("Name", "Unknown")
    end_date = row["ContractEnd"].date()
    key = f"expired_{row['StudentCode']}"
    html = f"❌ <b>{name}</b>'s contract expired on {end_date}"
    notifications.append((key, html))

# 6. Render
if notifications:
    st.markdown("""
    <div style='background-color:#fff3cd;border:1px solid #ffc107;
                border-radius:10px;padding:15px;margin-top:10px'>
      <h4>🔔 <b>Notifications</b></h4>
    </div>
    """, unsafe_allow_html=True)

    for key, html in notifications:
        if key in st.session_state["dismissed_notifs"]:
            continue

        col1, col2 = st.columns([9, 1])
        with col1:
            st.markdown(html, unsafe_allow_html=True)
        with col2:
            if st.button("Dismiss", key="dismiss_" + key):
                st.session_state["dismissed_notifs"].add(key)

else:
    st.markdown(f"""
    <div style='background-color:#e8f5e9;border:1px solid #4caf50;
                border-radius:10px;padding:15px;margin-top:10px'>
      <h4>🔔 <b>Notifications</b></h4>
      <p>No urgent alerts. You're all caught up ✅</p>
    </div>
    """, unsafe_allow_html=True)



# === TABS ===
tabs = st.tabs([
    "📝 Pending Registrations",
    "👩‍🎓 All Students",
    "➕ Add Student",
    "💵 Expenses",
    "📲 WhatsApp Reminders",
    "📄 Generate Contract PDF",
    "📧 Send Email",
    "📊 Analytics & Export",
    "📆 A1 Course Schedule"  
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

    # — Coerce numeric columns to avoid ValueError —
    df_main["Paid"] = pd.to_numeric(df_main["Paid"], errors="coerce").fillna(0.0)
    df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0.0)

    # — Coerce ContractEnd to datetime & compute Status vectorized —
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
        for idx, row in view_df.iterrows():
            name           = row["Name"]
            phone          = row["Phone"]
            email          = row["Email"]
            location       = row["Location"]
            level          = row["Level"]
            paid           = row["Paid"]
            balance        = row["Balance"]
            contract_start = str(row["ContractStart"])
            contract_end   = row["ContractEnd"].date() if pd.notna(row["ContractEnd"]) else ""
            student_code   = row["StudentCode"]
            emergency      = row["Emergency Contact (Phone Number)"]
            status         = row["Status"]

            unique_key = f"{student_code}_{idx}"
            status_color = (
                "🟢" if status == "Enrolled" else
                "🔴" if status == "Completed" else
                "⚪"
            )

            with st.expander(f"{status_color} {name} ({student_code}) [{status}]"):
                # Editable fields
                name_input           = st.text_input("Name", value=name, key=f"name_{unique_key}")
                phone_input          = st.text_input("Phone", value=phone, key=f"phone_{unique_key}")
                email_input          = st.text_input("Email", value=email, key=f"email_{unique_key}")
                location_input       = st.text_input("Location", value=location, key=f"loc_{unique_key}")
                level_input          = st.text_input("Level", value=level, key=f"level_{unique_key}")
                paid_input           = st.number_input("Paid", value=paid, key=f"paid_{unique_key}")
                balance_input        = st.number_input("Balance", value=balance, key=f"bal_{unique_key}")
                contract_start_input = st.text_input("Contract Start", value=contract_start, key=f"cs_{unique_key}")
                contract_end_input   = st.text_input("Contract End", value=contract_end, key=f"ce_{unique_key}")
                code_input           = st.text_input("Student Code", value=student_code, key=f"code_{unique_key}")
                emergency_input      = st.text_input("Emergency Contact", value=emergency, key=f"em_{unique_key}")

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
                            row,
                            st.session_state["agreement_template"],
                            payment_amount=total_fee,
                            payment_date=parsed_date
                        )
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        b64 = base64.b64encode(pdf_bytes).decode()
                        download_link = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{name.replace(" ", "_")}_receipt.pdf">Download Receipt</a>'
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

            # ✅ Reload fresh and convert date column
            exp = pd.read_csv(expenses_file)
            exp["Date"] = pd.to_datetime(exp["Date"], errors="coerce")
            exp["Month"] = exp["Date"].dt.strftime("%B %Y")
            exp["Year"] = exp["Date"].dt.year

            st.success(f"✅ Recorded: {exp_type} – {exp_item}")
            st.session_state["should_rerun"] = True

    # ✅ Convert dates if not done
    exp["Date"] = pd.to_datetime(exp["Date"], errors="coerce")
    exp["Month"] = exp["Date"].dt.strftime("%B %Y")
    exp["Year"] = exp["Date"].dt.year

    st.write("### All Expenses")
    st.dataframe(exp[["Type", "Item", "Amount", "Date"]], use_container_width=True)

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
                phone = row.get("Phone", "")

                contract_start = row.get("ContractStart", "")
                if contract_start and not pd.isnull(contract_start):
                    contract_start_dt = pd.to_datetime(contract_start, errors="coerce")
                    due_date_dt = contract_start_dt + timedelta(days=30)
                    due_date_fmt = due_date_dt.strftime("%d %B %Y")
                else:
                    due_date_fmt = "soon"

                message = (
                    f"Dear {name}, this is a reminder that your balance for your {level} class is GHS {balance:.2f} "
                    f"and is due by {due_date_fmt}. Kindly make the payment to continue learning with us. Thank you!\n\n"
                    "Payment Methods:\n"
                    "1. Mobile Money\n"
                    "   Number: 0245022743\n"
                    "   Name: Felix Asadu\n"
                    "2. Access Bank (Cedis)\n"
                    "   Account Number: 1050000008017\n"
                    "   Name: Learn Language Education Academy"
                )

                phone_clean = phone.replace(" ", "").replace("+", "")
                if phone_clean.startswith("0"):
                    phone_clean = "233" + phone_clean[1:]

                encoded_msg = urllib.parse.quote(message)
                wa_url = f"https://wa.me/{phone_clean}?text={encoded_msg}"

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

    if st.button("Send Email"):
        if not recipients:
            st.warning("❗ Please select or enter at least one email address.")
            st.stop()

        sent = 0
        failed = []
        attachment = None

        if file_upload:
            try:
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
                st.stop()

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
    st.title("Intelligenter Kursplan-Generator: A1, A2, B1 (Automatische Wochenzahl)")

    from datetime import timedelta, date
    import calendar
    from fpdf import FPDF

    def sanitize(text):
        return text.encode('latin-1', 'replace').decode('latin-1')

    def pick_dates(start_date, week_patterns, num_sessions):
        """Returns a flat list of all dates, matching num_sessions topics."""
        all_dates = []
        cur_date = start_date
        session_count = 0
        for week_idx, (num_classes, week_days) in enumerate(week_patterns):
            week_dates = []
            used_days = set()
            for _ in range(num_classes):
                if session_count >= num_sessions:
                    break
                attempts = 0
                while (calendar.day_name[cur_date.weekday()] not in week_days or
                       calendar.day_name[cur_date.weekday()] in used_days):
                    cur_date += timedelta(days=1)
                    attempts += 1
                    if attempts > 20:
                        break
                day_str = calendar.day_name[cur_date.weekday()]
                week_dates.append(cur_date)
                used_days.add(day_str)
                cur_date += timedelta(days=1)
                session_count += 1
            all_dates.extend(week_dates)
            if session_count >= num_sessions:
                break
        return all_dates

    def schedule_block(level_name, topic_structure):
        st.header(f"{level_name} Kursplan")
        start_date = st.date_input(f"{level_name} Startdatum", value=date.today(), key=f"{level_name}_start")
        default_days = ["Monday", "Tuesday", "Wednesday"]
        all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        # Flatten all sessions/topics
        all_sessions = []
        for week_label, sessions in topic_structure:
            all_sessions.extend(sessions)
        num_sessions = len(all_sessions)

        st.info(f"⚡ Du hast insgesamt **{num_sessions}** Themen/Sitzungen im {level_name} Kurs.")

        week_settings = []
        current_total = 0
        week_num = 1
        # Collect user settings for each week until we cover all topics
        while current_total < num_sessions:
            with st.expander(f"Woche {week_num} Einstellungen", expanded=True):
                week_days = st.multiselect(
                    f"Tage in Woche {week_num}",
                    options=all_days,
                    default=default_days if week_num == 1 else [],
                    key=f"{level_name}_days_{week_num}"
                )
                max_sessions = len(week_days) if week_days else 1
                num_classes = st.number_input(
                    f"Anzahl Klassen in Woche {week_num}",
                    min_value=1,
                    max_value=max_sessions,
                    value=max_sessions,
                    key=f"{level_name}_num_{week_num}"
                )
                week_settings.append((num_classes, week_days if week_days else default_days))
                current_total += num_classes
            week_num += 1

        if st.button(f"📅 {level_name} Kursplan generieren"):
            all_dates = pick_dates(start_date, week_settings, num_sessions)
            # Map topics to dates
            schedule_lines = []
            session_idx = 0
            day_counter = 1
            topic_pointer = 0
            for w, (week_label, sessions) in enumerate(topic_structure):
                schedule_lines.append(f"\n{week_label.upper()}")
                for s in sessions:
                    if session_idx < len(all_dates):
                        date_str = all_dates[session_idx].strftime("%d %B %Y")
                        day_name = calendar.day_name[all_dates[session_idx].weekday()]
                        schedule_lines.append(f"Day {day_counter} ({date_str}, {day_name}): {s}")
                        session_idx += 1
                        day_counter += 1
                    else:
                        schedule_lines.append(f"Day {day_counter}: {s} (Kein Datum zugewiesen)")
                        day_counter += 1
                    topic_pointer += 1
            preview = "\n".join(schedule_lines)
            st.text_area(f"📄 Vorschau {level_name} Kursplan", value=preview, height=420)
            st.download_button(f"📁 TXT Download ({level_name})", preview, file_name=f"{level_name.lower()}_course_schedule.txt", mime="text/plain")

            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12)
            for line in preview.split("\n"):
                if line.strip().startswith("WOCHE") or line.strip().startswith("WEEK"):
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(0, 10, sanitize(line.strip()), ln=True)
                    pdf.set_font("Arial", size=12)
                else:
                    pdf.multi_cell(0, 10, sanitize(line))
            st.download_button(
                f"📄 PDF Download ({level_name})",
                data=pdf.output(dest='S').encode('latin-1'),
                file_name=f"{level_name.lower()}_course_schedule.pdf", mime="application/pdf"
            )

    # === A1 Topics
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
    # === A2 Topics
    raw_schedule_a2 = [
        ("Woche 1", [
            "1.1. Small Talk (Exercise)",
            "1.2. Personen Beschreiben (Exercise)",
            "1.3. Dinge und Personen vergleichen"
        ]),
        ("Woche 2", [
            "2.4. Wo möchten wir uns treffen?",
            "2.5. Was machst du in deiner Freizeit?"
        ]),
        ("Woche 3", [
            "3.6. Möbel und Räume kennenlernen",
            "3.7. Eine Wohnung suchen (Übung)",
            "3.8. Rezepte und Essen (Exercise)"
        ]),
        ("Woche 4", [
            "4.9. Urlaub",
            "4.10. Tourismus und Traditionelle Feste",
            "4.11. Unterwegs: Verkehrsmittel vergleichen"
        ]),
        ("Woche 5", [
            "5.12. Ein Tag im Leben (Übung)",
            "5.13. Ein Vorstellungsgesprach (Exercise)",
            "5.14. Beruf und Karriere (Exercise)"
        ]),
        ("Woche 6", [
            "6.15. Mein Lieblingssport",
            "6.16. Wohlbefinden und Entspannung",
            "6.17. In die Apotheke gehen"
        ]),
        ("Woche 7", [
            "7.18. Die Bank Anrufen",
            "7.19. Einkaufen – Wo und wie? (Exercise)",
            "7.20. Typische Reklamationssituationen üben"
        ]),
        ("Woche 8", [
            "8.21. Ein Wochenende planen",
            "8.22. Die Woche Plannung"
        ]),
        ("Woche 9", [
            "9.23. Wie kommst du zur Schule / zur Arbeit?",
            "9.24. Einen Urlaub planen",
            "9.25. Tagesablauf (Exercise)"
        ]),
        ("Woche 10", [
            "10.26. Gefühle in verschiedenen Situationen beschr",
            "10.27. Digitale Kommunikation",
            "10.28. Über die Zukunft sprechen"
        ]),
    ]
    # === B1 Topics
    raw_schedule_b1 = [
        ("Woche 1", [
            "1.1. Traumwelten (Übung)",
            "1.2. Freundes für Leben (Übung)",
            "1.3. Erfolgsgeschichten (Übung)"
        ]),
        ("Woche 2", [
            "2.4. Wohnung suchen (Übung)",
            "2.5. Der Besichtigungstermin (Übung)",
            "2.6. Leben in der Stadt oder auf dem Land?"
        ]),
        ("Woche 3", [
            "3.7. Fast Food vs. Hausmannskost",
            "3.8. Alles für die Gesundheit",
            "3.9. Work-Life-Balance im modernen Arbeitsumfeld"
        ]),
        ("Woche 4", [
            "4.10. Digitale Auszeit und Selbstfürsorge",
            "4.11. Teamspiele und Kooperative Aktivitäten",
            "4.12. Abenteuer in der Natur",
            "4.13. Eigene Filmkritik schreiben"
        ]),
        ("Woche 5", [
            "5.14. Traditionelles vs. digitales Lernen",
            "5.15. Medien und Arbeiten im Homeoffice",
            "5.16. Prüfungsangst und Stressbewältigung",
            "5.17. Wie lernt man am besten?"
        ]),
        ("Woche 6", [
            "6.18. Wege zum Wunschberuf",
            "6.19. Das Vorstellungsgespräch",
            "6.20. Wie wird man …? (Ausbildung und Qu"
        ]),
        ("Woche 7", [
            "7.21. Lebensformen heute – Familie, Wohnge",
            "7.22. Was ist dir in einer Beziehung wichtig?",
            "7.23. Erstes Date – Typische Situationen"
        ]),
        ("Woche 8", [
            "8.24. Konsum und Nachhaltigkeit",
            "8.25. Online einkaufen – Rechte und Risiken"
        ]),
        ("Woche 9", [
            "9.26. Reiseprobleme und Lösungen"
        ]),
        ("Woche 10", [
            "10.27. Umweltfreundlich im Alltag",
            "10.28. Klimafreundlich leben"
        ])
    ]

    st.markdown("---")
    schedule_block("A1", raw_schedule_a1)
    st.markdown("---")
    schedule_block("A2", raw_schedule_a2)
    st.markdown("---")
    schedule_block("B1", raw_schedule_b1)

