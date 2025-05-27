# ✅ FULL DASHBOARD CODE – With Pending Registrations Tab Fully Updated
import streamlit as st
import pandas as pd
import os
from datetime import date, datetime, timedelta
from fpdf import FPDF
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import urllib.parse

# === PAGE CONFIG ===
st.set_page_config(page_title="Learn Language Education Academy Dashboard", layout="wide")

# === SCHOOL INFO ===
SCHOOL_NAME = "Learn Language Education Academy"
SCHOOL_EMAIL = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# === EMAIL CONFIG ===
school_sendgrid_key = st.secrets["general"].get("SENDGRID_API_KEY")
school_sender_email = st.secrets["general"].get("SENDER_EMAIL", SCHOOL_EMAIL)

# === SESSION STATE INIT ===
if "emailed_expiries" not in st.session_state:
    st.session_state["emailed_expiries"] = set()

# === PDF GENERATOR ===
def generate_receipt_and_contract_pdf(student_row, agreement_text, payment_amount, payment_date=None, first_instalment=1500, course_length=12):
    if payment_date is None:
        payment_date = date.today()
    try:
        second_instalment = float(student_row.get("Balance", 0))
    except:
        second_instalment = 0.0
    second_due_date = payment_date + timedelta(days=30)
    filled = agreement_text.replace("[STUDENT_NAME]", student_row["Name"]) \
        .replace("[DATE]", str(payment_date)) \
        .replace("[CLASS]", student_row["Level"]) \
        .replace("[AMOUNT]", str(student_row["Paid"])) \
        .replace("[FIRST_INSTALMENT]", str(first_instalment)) \
        .replace("[SECOND_INSTALMENT]", str(second_instalment)) \
        .replace("[SECOND_DUE_DATE]", str(second_due_date)) \
        .replace("[COURSE_LENGTH]", str(course_length))

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, f"{SCHOOL_NAME} Payment Receipt", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, f"Name: {student_row['Name']}", ln=True)
    pdf.cell(200, 10, f"Student Code: {student_row['StudentCode']}", ln=True)
    pdf.cell(200, 10, f"Phone: {student_row['Phone']}", ln=True)
    pdf.cell(200, 10, f"Level: {student_row['Level']}", ln=True)
    pdf.cell(200, 10, f"Amount Paid: GHS {payment_amount}", ln=True)
    pdf.cell(200, 10, f"Balance Due: GHS {second_instalment}", ln=True)
    pdf.cell(200, 10, f"Contract Start: {student_row['ContractStart']}", ln=True)
    pdf.cell(200, 10, f"Contract End: {student_row['ContractEnd']}", ln=True)
    pdf.cell(200, 10, f"Receipt Date: {payment_date}", ln=True)
    pdf.ln(10)
    pdf.cell(0, 10, "Thank you for your payment!", ln=True)
    pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)
    pdf.ln(15)
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, f"{SCHOOL_NAME} Student Contract", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    for line in filled.split("\n"):
        pdf.multi_cell(0, 10, line)
    pdf.ln(10)
    pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)

    filename = f"{student_row['Name'].replace(' ', '_')}_receipt_contract.pdf"
    pdf.output(filename)
    return filename

# === INITIALIZE STUDENT FILE ===
student_file = "students_simple.csv"
if os.path.exists(student_file):
    df_main = pd.read_csv(student_file)
else:
    df_main = pd.DataFrame(columns=[
        "Name", "Phone", "Location", "Level", "Paid", "Balance", "ContractStart", "ContractEnd", "StudentCode", "Email"
    ])
    df_main.to_csv(student_file, index=False)

# === GOOGLE SHEET REGISTRATION FORM (PENDING STUDENTS) ===
sheet_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"

# === AGREEMENT TEMPLATE STATE ===
if "agreement_template" not in st.session_state:
    st.session_state["agreement_template"] = """
PAYMENT AGREEMENT

This Payment Agreement is entered into on [DATE] for [CLASS] students of Learn Language Education Academy and Felix Asadu ("Teacher").

Terms of Payment:
1. Payment Amount: The student agrees to pay the teacher a total of [AMOUNT] cedis for the course.
2. Payment Schedule: The payment can be made in full or in two installments: a minimum of [FIRST_INSTALMENT] cedis for the first installment and the remaining [SECOND_INSTALMENT] cedis for the second installment. The second installment must be paid by [SECOND_DUE_DATE].
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

# === NOTIFICATIONS ===
today = date.today()
notifications = []

# Normalize data
df_main["ContractEnd"] = pd.to_datetime(df_main.get("ContractEnd"), errors="coerce")
df_main["Balance"] = pd.to_numeric(df_main.get("Balance", 0), errors="coerce").fillna(0.0)

def clean_phone(phone):
    phone = str(phone).replace(" ", "").replace("+", "")
    return "233" + phone[1:] if phone.startswith("0") else phone

# 1. Debtors
debtors = df_main[df_main["Balance"] > 0]
for _, row in debtors.iterrows():
    phone = clean_phone(row.get("Phone", ""))
    name = row.get("Name", "Unknown")
    balance = row["Balance"]
    student_code = row.get("StudentCode", "")
    msg = f"Dear {name}, you owe GHS {balance:.2f} for your course ({student_code}). Please settle it to remain active."
    wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
    notifications.append(
        f"💰 <b>{name}</b> owes GHS {balance:.2f} [<a href='{wa_url}' target='_blank'>📲 WhatsApp</a>]"
    )

# 2. Expiring contracts (only email once)
expiring = df_main[
    (df_main["ContractEnd"].notnull()) &
    (df_main["ContractEnd"].dt.date >= today) &
    (df_main["ContractEnd"].dt.date <= today + timedelta(days=30))
]
for _, row in expiring.iterrows():
    name = row.get("Name", "Unknown")
    end_date = row["ContractEnd"].date()
    email = row.get("Email", "")
    student_code = row.get("StudentCode", "")
    unique_key = f"{name}_{student_code}"

    message = f"⏳ <b>{name}</b>'s contract ends on {end_date}"

    if email and school_sendgrid_key and unique_key not in st.session_state["emailed_expiries"]:
        try:
            msg = Mail(
                from_email=school_sender_email,
                to_emails=email,
                subject=f"Your contract with {SCHOOL_NAME} ends soon",
                html_content=f"Dear {name},<br><br>Your contract ends on {end_date}. "
                             f"Please contact us to extend it.<br><br>{SCHOOL_NAME}"
            )
            client = SendGridAPIClient(school_sendgrid_key)
            client.send(msg)
            message += " ✅ Email sent"
            st.session_state["emailed_expiries"].add(unique_key)
        except Exception as e:
            message += f" ⚠️ Email failed: {e}"

    notifications.append(message)

# 3. Expired contracts
expired = df_main[(df_main["ContractEnd"].notnull()) & (df_main["ContractEnd"].dt.date < today)]
for _, row in expired.iterrows():
    name = row.get("Name", "Unknown")
    end_date = row["ContractEnd"].date()
    notifications.append(f"❌ <b>{name}</b>'s contract expired on {end_date}")

# Show notifications
if notifications:
    st.markdown(f"""
    <div style='background-color:#fff3cd;border:1px solid #ffc107;border-radius:10px;padding:15px;margin-top:10px'>
        <h4>🔔 <b>Notifications</b></h4>
        <ul>{"".join([f"<li>{n}</li>" for n in notifications])}</ul>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div style='background-color:#e8f5e9;border:1px solid #4caf50;border-radius:10px;padding:15px;margin-top:10px'>
        <h4>🔔 <b>Notifications</b></h4>
        <p>No urgent alerts. You're all caught up ✅</p>
    </div>
    """, unsafe_allow_html=True)

# ✅ Place this ABOVE any tab block
tabs = st.tabs([
    "📝 Pending Registrations",
    "👩‍🎓 All Students",
    "➕ Add Student",
    "💵 Expenses",
    "📲 WhatsApp Reminders",
    "📄 Generate Contract PDF",
    "📧 Send Email",
    "📊 Analytics & Export"
])

# === TAB 0: PENDING REGISTRATIONS ===
with tabs[0]:
    st.title("📝 Pending Student Registrations")

    # --- Load new pending students from form sheet ---
    try:
        new_students = pd.read_csv(sheet_url)

        def clean_col(c):
            return c.strip().lower().replace("(", "").replace(")", "").replace(",", "").replace("-", "").replace(" ", "_")

        new_students.columns = [clean_col(c) for c in new_students.columns]
        st.success("✅ Loaded columns: " + ", ".join(new_students.columns))
    except Exception as e:
        st.error(f"❌ Could not load registration sheet: {e}")
        new_students = pd.DataFrame()

    # --- Upload CSV overrides ---
    with st.expander("📤 Upload Data"):
        st.subheader("Upload Student CSV")
        uploaded_student_csv = st.file_uploader("Upload students_simple.csv", type=["csv"])
        if uploaded_student_csv:
            uploaded_df = pd.read_csv(uploaded_student_csv)
            uploaded_df.to_csv("students_simple.csv", index=False)
            st.success("✅ Student file replaced.")
            st.rerun()

        st.subheader("Upload Expenses CSV")
        uploaded_expenses_csv = st.file_uploader("Upload expenses_all.csv", type=["csv"])
        if uploaded_expenses_csv:
            exp = pd.read_csv(uploaded_expenses_csv)
            exp.to_csv("expenses_all.csv", index=False)
            st.success("✅ Expenses file replaced.")
            st.rerun()
        elif not os.path.exists("expenses_all.csv"):
            exp = pd.DataFrame(columns=["Type", "Item", "Amount", "Date"])
            exp.to_csv("expenses_all.csv", index=False)

    # --- Show and approve pending students ---
    if not new_students.empty:
        for i, row in new_students.iterrows():
            fullname = row.get("full_name") or row.get("name") or f"Student {i}"
            phone = row.get("phone_number") or row.get("phone") or ""
            email = row.get("email", "")
            level = row.get("class_a1a2_etc") or row.get("class") or row.get("level") or ""
            location = row.get("location", "")
            emergency = row.get("emergency_contact_phone_number") or row.get("emergency", "")

            with st.expander(f"{fullname} ({phone})"):
                st.write(f"**Email:** {email if email else '—'}")
                student_code = st.text_input("Assign Student Code", key=f"code_{i}")
                contract_start = st.date_input("Contract Start", value=date.today(), key=f"start_{i}")
                course_length = st.number_input("Course Length (weeks)", min_value=1, value=12, key=f"length_{i}")
                contract_end = st.date_input("Contract End", value=contract_start + timedelta(weeks=course_length), key=f"end_{i}")
                paid = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0, key=f"paid_{i}")
                balance = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0, key=f"bal_{i}")
                first_instalment = st.number_input("First Instalment", min_value=0.0, value=1500.0, key=f"firstinst_{i}")
                attach_pdf = st.checkbox("Attach PDF to Email?", value=True, key=f"pdf_{i}")
                send_email = st.checkbox("Send Welcome Email?", value=bool(email), key=f"email_{i}")

                if st.button("Approve & Add", key=f"approve_{i}") and student_code:
                    # ✅ Only load from file when needed
                    if os.path.exists("students_simple.csv"):
                        approved_df = pd.read_csv("students_simple.csv")
                    else:
                        approved_df = pd.DataFrame(columns=[
                            "Name", "Phone", "Email", "Location", "Level", "Paid", "Balance", "ContractStart", "ContractEnd", "StudentCode"
                        ])

                    if student_code in approved_df["StudentCode"].values:
                        st.warning("❗ This Student Code already exists. Choose a unique one.")
                        st.stop()

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
                        "StudentCode": student_code
                    }

                    approved_df = pd.concat([approved_df, pd.DataFrame([student_dict])], ignore_index=True)
                    approved_df.to_csv("students_simple.csv", index=False)

                    # Generate PDF
                    pdf_file = generate_receipt_and_contract_pdf(
                        student_dict,
                        st.session_state.get("agreement_template", ""),
                        paid,
                        contract_start,
                        first_instalment,
                        course_length
                    )

                    # Optionally send email
                    if send_email and email and school_sendgrid_key:
                        try:
                            msg = Mail(
                                from_email=school_sender_email,
                                to_emails=email,
                                subject=f"Welcome to {SCHOOL_NAME}",
                                html_content=f"""
Dear {fullname},<br><br>
Welcome to {SCHOOL_NAME}!<br>
Student Code: <b>{student_code}</b><br>
Class: {level}<br>
Contract: {contract_start} to {contract_end}<br>
Paid: GHS {paid}<br>
Balance: GHS {balance}<br><br>
For help, contact us at {SCHOOL_EMAIL} or {SCHOOL_PHONE}.
"""
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
                            client = SendGridAPIClient(school_sendgrid_key)
                            client.send(msg)
                            st.success(f"📧 Email sent to {email}")
                        except Exception as e:
                            st.warning(f"⚠️ Email failed: {e}")
                    elif send_email:
                        st.warning("⚠️ Email skipped. Address missing or SendGrid not configured.")

                    st.success(f"✅ {fullname} approved and saved.")
                    st.rerun()


with tabs[1]:
    st.title("👩‍🎓 All Students (Edit, Update, Delete, Receipt)")
    today = date.today()

    # ✅ Always reload from CSV
    if os.path.exists(student_file):
        df_main = pd.read_csv(student_file)
    else:
        df_main = pd.DataFrame()

    # Ensure required columns exist
    required_cols = ["Name", "Phone", "Location", "Level", "Paid", "Balance", "ContractStart", "ContractEnd", "StudentCode"]
    for col in required_cols:
        if col not in df_main.columns:
            df_main[col] = ""

    # Status tagging
    if not df_main.empty and "ContractEnd" in df_main.columns:
        df_main["Status"] = df_main["ContractEnd"].apply(
            lambda x: "Completed" if pd.to_datetime(str(x), errors='coerce').date() < today else "Enrolled"
        )
    else:
        df_main["Status"] = "Unknown"

    status_filter = st.selectbox("Filter by Status", ["All", "Enrolled", "Completed"])
    view_df = df_main if status_filter == "All" else df_main[df_main["Status"] == status_filter]

    if not view_df.empty:
        for idx, row in view_df.iterrows():
            name = row.get("Name", "")
            phone = row.get("Phone", "")
            location = row.get("Location", "")
            level = row.get("Level", "")
            paid = float(row.get("Paid", 0))
            balance = float(row.get("Balance", 0))
            contract_start = str(row.get("ContractStart", ""))
            contract_end = str(row.get("ContractEnd", ""))
            student_code = row.get("StudentCode", "")
            status = row.get("Status", "Unknown")

            unique_key = f"{student_code}_{idx}"

            with st.expander(f"{name} ({student_code}) [{status}]"):
                name_input = st.text_input("Name", value=name, key=f"name_{unique_key}")
                phone_input = st.text_input("Phone", value=phone, key=f"phone_{unique_key}")
                location_input = st.text_input("Location", value=location, key=f"loc_{unique_key}")
                level_input = st.text_input("Level", value=level, key=f"level_{unique_key}")
                paid_input = st.number_input("Paid", value=paid, key=f"paid_{unique_key}")
                balance_input = st.number_input("Balance", value=balance, key=f"bal_{unique_key}")
                contract_start_input = st.text_input("Contract Start", value=contract_start, key=f"cs_{unique_key}")
                contract_end_input = st.text_input("Contract End", value=contract_end, key=f"ce_{unique_key}")
                student_code_input = st.text_input("Student Code", value=student_code, key=f"code_{unique_key}")

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("💾 Update", key=f"update_{unique_key}"):
                        df_main.at[idx, "Name"] = name_input
                        df_main.at[idx, "Phone"] = phone_input
                        df_main.at[idx, "Location"] = location_input
                        df_main.at[idx, "Level"] = level_input
                        df_main.at[idx, "Paid"] = paid_input
                        df_main.at[idx, "Balance"] = balance_input
                        df_main.at[idx, "ContractStart"] = contract_start_input
                        df_main.at[idx, "ContractEnd"] = contract_end_input
                        df_main.at[idx, "StudentCode"] = student_code_input
                        df_main.to_csv(student_file, index=False)
                        st.success("✅ Student updated.")
                        st.rerun()

                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{unique_key}"):
                        df_main = df_main.drop(idx).reset_index(drop=True)
                        df_main.to_csv(student_file, index=False)
                        st.success("❌ Student deleted.")
                        st.rerun()

                with col3:
                    if st.button("📄 Receipt", key=f"receipt_{unique_key}"):
                        pdf_path = generate_receipt_and_contract_pdf(
                            row,
                            st.session_state.get("agreement_template", ""),
                            payment_amount=paid_input,
                            payment_date=today
                        )
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                            b64 = base64.b64encode(pdf_bytes).decode()
                            download_link = f'<a href="data:application/pdf;base64,{b64}" download="{name.replace(" ", "_")}_receipt.pdf">Download PDF</a>'
                            st.markdown(download_link, unsafe_allow_html=True)
    else:
        st.info("No students found in your database.")

with tabs[2]:
    st.title("➕ Add Student Manually")

    with st.form("add_student_form"):
        name = st.text_input("Full Name")
        phone = st.text_input("Phone Number")
        email = st.text_input("Email Address")
        location = st.text_input("Location")
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
                        "Name", "Phone", "Email", "Location", "Level", "Paid", "Balance", "ContractStart", "ContractEnd", "StudentCode"
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
                    "StudentCode": student_code
                }])

                updated_df = pd.concat([existing_df, new_row], ignore_index=True)
                updated_df.to_csv(student_file, index=False)
                st.success(f"✅ Student '{name}' added successfully.")
                st.rerun()

with tabs[3]:
    st.title("💵 Expenses and Financial Summary")

    # Load or initialize expenses file
    expenses_file = "expenses_all.csv"
    if os.path.exists(expenses_file):
        exp = pd.read_csv(expenses_file)
    else:
        exp = pd.DataFrame(columns=["Type", "Item", "Amount", "Date"])
        exp.to_csv(expenses_file, index=False)

    # Add new expense
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
            st.rerun()

    # Show full expense list
    st.write("### All Expenses")
    st.dataframe(exp, use_container_width=True)

    # Summary Calculations
    st.write("### Summary")
    total_paid = df_main["Paid"].sum() if not df_main.empty else 0.0
    total_expenses = exp["Amount"].sum() if not exp.empty else 0.0
    net_profit = total_paid - total_expenses

    st.info(f"💰 **Total Collected:** GHS {total_paid:,.2f}")
    st.info(f"💸 **Total Expenses:** GHS {total_expenses:,.2f}")
    st.success(f"📈 **Net Profit:** GHS {net_profit:,.2f}")

    # Monthly & Yearly Breakdown
    if not exp.empty:
        exp["Date"] = pd.to_datetime(exp["Date"], errors='coerce')
        exp["Year"] = exp["Date"].dt.year
        exp["Month"] = exp["Date"].dt.strftime("%B %Y")

        st.write("### Expenses by Month")
        st.dataframe(exp.groupby("Month")["Amount"].sum().reset_index())

        st.write("### Expenses by Year")
        st.dataframe(exp.groupby("Year")["Amount"].sum().reset_index())
with tabs[4]:
    st.title("📲 WhatsApp Reminders for Debtors")

    if not df_main.empty and "Balance" in df_main.columns and "Phone" in df_main.columns:
        # Ensure balance is numeric
        df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0.0)

        debtors = df_main[df_main["Balance"] > 0]

        if not debtors.empty:
            st.write("### Students with Outstanding Balances")

            for _, row in debtors.iterrows():
                name = row["Name"]
                balance = row["Balance"]
                student_code = row["StudentCode"]
                phone = row["Phone"]

                message = (
                    f"Dear {name}, your current balance with {SCHOOL_NAME} is GHS {balance:.2f}. "
                    f"Your student code is {student_code}. "
                    f"Please pay as soon as possible to remain active. Thank you!"
                )
                encoded_msg = urllib.parse.quote(message)
                phone_clean = str(phone).replace(" ", "").replace("+", "")
                if phone_clean.startswith("0"):
                    phone_clean = "233" + phone_clean[1:]

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
            student_row = df_main[df_main["Name"] == selected_name].iloc[0]

            pdf_file = generate_receipt_and_contract_pdf(
                student_row,
                st.session_state.get("agreement_template", ""),
                payment_amount=student_row.get("Paid", 0),
                payment_date=student_row.get("ContractStart", date.today())
            )

            with open(pdf_file, "rb") as f:
                pdf_bytes = f.read()
                b64 = base64.b64encode(pdf_bytes).decode()
                download_link = f'<a href="data:application/pdf;base64,{b64}" download="{selected_name.replace(" ", "_")}_contract.pdf">📄 Download PDF</a>'
                st.markdown(download_link, unsafe_allow_html=True)
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

    st.subheader("📈 Enrollment Over Time")
    if not df_main.empty and "ContractStart" in df_main.columns:
        try:
            df_main["EnrollDate"] = pd.to_datetime(df_main["ContractStart"], errors="coerce")
            monthly = df_main.groupby(df_main["EnrollDate"].dt.to_period("M")).size().reset_index(name="Count")
            monthly["EnrollDate"] = monthly["EnrollDate"].astype(str)
            st.line_chart(monthly.set_index("EnrollDate")["Count"])
        except Exception as e:
            st.warning(f"⚠️ Unable to generate chart: {e}")
    else:
        st.info("No enrollment data to visualize.")

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
