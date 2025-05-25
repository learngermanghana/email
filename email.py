import streamlit as st
import pandas as pd
import os
from datetime import date, datetime, timedelta
from fpdf import FPDF
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import urllib.parse

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === PAGE CONFIG FIRST! ===
st.set_page_config(page_title="Learn Language Education Academy Dashboard", layout="wide")

# === SCHOOL INFO ===
SCHOOL_NAME = "Learn Language Education Academy"
SCHOOL_EMAIL = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# === EMAIL CONFIG (secrets only, secure) ===
school_sendgrid_key = st.secrets["general"].get("SENDGRID_API_KEY")
school_sender_email = st.secrets["general"].get("SENDER_EMAIL", SCHOOL_EMAIL)

# === PHONE NUMBER CLEANER ===
def clean_phone(phone):
    phone_str = str(phone)
    if phone_str.endswith('.0'):
        phone_str = phone_str[:-2]
    return phone_str.replace(" ", "").replace("+", "")

GOOGLE_SHEET_NAME = "YourStudentSheet"  # Replace with your actual sheet name

def get_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("gspread_service_account.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(GOOGLE_SHEET_NAME)
    worksheet = sheet.sheet1
    return worksheet

def read_students():
    worksheet = get_gsheet()
    records = worksheet.get_all_records()
    return pd.DataFrame(records)

def add_student_to_gsheet(student_dict):
    worksheet = get_gsheet()
    worksheet.append_row(list(student_dict.values()))

def generate_receipt_and_contract_pdf(
        student_row, agreement_text, payment_amount, payment_date=None,
        first_instalment=1500, course_length=12):
    if payment_date is None:
        payment_date = date.today()
    # Second installment is the current balance
    try:
        second_instalment = float(student_row["Balance"])
    except Exception:
        second_instalment = 0.0
    # Calculate due date (1 month after first payment/contract start)
    try:
        if hasattr(payment_date, 'date'):
            payment_date_obj = payment_date.date()
        else:
            payment_date_obj = payment_date
        second_due_date = payment_date_obj + timedelta(days=30)
    except Exception:
        second_due_date = ""
    filled_agreement = (
        agreement_text
        .replace("[STUDENT_NAME]", student_row["Name"])
        .replace("[DATE]", str(payment_date))
        .replace("[CLASS]", student_row["Level"])
        .replace("[AMOUNT]", str(student_row["Paid"]))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(second_instalment))
        .replace("[SECOND_DUE_DATE]", str(second_due_date))
        .replace("[COURSE_LENGTH]", str(course_length))
    )
    pdf = FPDF()
    pdf.add_page()
    # Receipt section
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, f"{SCHOOL_NAME} Payment Receipt", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, f"School: {SCHOOL_NAME}", ln=True)
    pdf.cell(200, 10, f"Location: {SCHOOL_ADDRESS}", ln=True)
    pdf.cell(200, 10, f"Phone: {SCHOOL_PHONE}", ln=True)
    pdf.cell(200, 10, f"Email: {SCHOOL_EMAIL}", ln=True)
    pdf.cell(200, 10, f"Website: {SCHOOL_WEBSITE}", ln=True)
    pdf.ln(10)
    pdf.cell(200, 10, f"Name: {student_row['Name']}", ln=True)
    pdf.cell(200, 10, f"Student Code: {student_row['StudentCode']}", ln=True)
    pdf.cell(200, 10, f"Phone: {student_row['Phone']}", ln=True)
    pdf.cell(200, 10, f"Level: {student_row['Level']}", ln=True)
    pdf.cell(200, 10, f"Amount Paid: GHS {payment_amount}", ln=True)
    pdf.cell(200, 10, f"Balance Due: GHS {second_instalment}", ln=True)
    pdf.cell(200, 10, f"Contract Start: {student_row['ContractStart']}", ln=True)
    pdf.cell(200, 10, f"Contract End: {student_row['ContractEnd']}", ln=True)
    pdf.cell(200, 10, f"Second Payment Due: {second_due_date}", ln=True)
    pdf.ln(10)
    pdf.cell(0, 10, "Thank you for your payment!", ln=True)
    pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)
    # Agreement section
    pdf.ln(15)
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, f"{SCHOOL_NAME} Student Contract", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    for line in filled_agreement.split("\n"):
        pdf.multi_cell(0, 10, line)
    pdf.ln(10)
    pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)
    pdf_name = f"{student_row['Name'].replace(' ', '_')}_receipt_and_contract.pdf"
    pdf.output(pdf_name)
    return pdf_name
sheet_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"
st.title(f"🏫 {SCHOOL_NAME} Dashboard")
st.caption(f"📍 {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

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
st.subheader("Edit Payment Agreement Template")
agreement_text = st.text_area("Agreement Template", value=st.session_state["agreement_template"], height=350)
st.session_state["agreement_template"] = agreement_text

# PDF Preview (admin only)
pdf_preview = FPDF()
pdf_preview.add_page()
pdf_preview.set_font("Arial", size=12)
for line in agreement_text.split("\n"):
    pdf_preview.multi_cell(0, 10, line)
pdf_preview.output("preview_agreement.pdf")
with open("preview_agreement.pdf", "rb") as f:
    preview_bytes = f.read()
    preview_b64 = base64.b64encode(preview_bytes).decode()
    st.markdown(f'<a href="data:application/pdf;base64,{preview_b64}" download="Agreement_Preview.pdf">Download Agreement Preview PDF</a>', unsafe_allow_html=True)

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

with tabs[0]:
    st.title("📝 Pending Student Registrations (Approve & Auto-Email)")
    try:
        new_students = pd.read_csv(sheet_url)
        def clean_col(c):
            c = c.strip().lower()
            c = c.replace("(", "").replace(")", "")
            c = c.replace(",", "").replace("-", "")
            c = c.replace(" ", "_")
            return c
        new_students.columns = [clean_col(c) for c in new_students.columns]
        st.info(f"Columns: {', '.join(new_students.columns)}")
    except Exception as e:
        st.error(f"Could not load registrations: {e}")
        new_students = pd.DataFrame()

    if not new_students.empty:
        for i, row in new_students.iterrows():
            fullname = row.get('full_name', '')
            phone = row.get('phone_number', '')
            email = row.get('email', '')
            level = row.get('class_a1a2_etc', '')
            location = row.get('location', '')
            emergency = row.get('emergency_contact_phone_number', '')
            with st.expander(f"{fullname} ({phone})"):
                st.write(f"**Email:** {email}")
                student_code = st.text_input("Assign Student Code", key=f"code_{i}")
                contract_start = st.date_input("Contract Start", value=date.today(), key=f"start_{i}")
                contract_end = st.date_input("Contract End", value=date.today(), key=f"end_{i}")
                paid = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0, key=f"paid_{i}")
                balance = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0, key=f"bal_{i}")
                first_instalment = st.number_input("First Instalment (GHS)", min_value=0.0, value=1500.0, key=f"firstinst_{i}")
                course_length = st.number_input("Course Length (weeks)", min_value=1, value=12, key=f"length_{i}")

                attach_pdf = st.checkbox("Attach Receipt & Contract PDF to Email?", value=True, key=f"pdf_{i}")

                if st.button("Approve & Add to Main List", key=f"approve_{i}") and student_code:
                    # --- Add to Google Sheets ---
                    student_dict = {
                        "Name": fullname,
                        "Phone": phone,
                        "Location": location,
                        "Level": level,
                        "Paid": paid,
                        "Balance": balance,
                        "ContractStart": str(contract_start),
                        "ContractEnd": str(contract_end),
                        "StudentCode": student_code
                    }
                    add_student_to_gsheet(student_dict)

                    # --- Generate combined receipt + contract PDF ---
                    pdf_file = generate_receipt_and_contract_pdf(
                        student_dict, agreement_text, payment_amount=paid, payment_date=contract_start,
                        first_instalment=first_instalment, course_length=course_length
                    )
                    attachment = None
                    if attach_pdf:
                        with open(pdf_file, "rb") as f:
                            pdf_bytes = f.read()
                            encoded = base64.b64encode(pdf_bytes).decode()
                            attachment = Attachment(
                                FileContent(encoded),
                                FileName(pdf_file),
                                FileType("application/pdf"),
                                Disposition("attachment")
                            )

                    # --- Send welcome/contract email ---
                    if school_sendgrid_key and school_sender_email:
                        subject = f"Welcome to {SCHOOL_NAME} – Your Registration Details"
                        body = f"""
Dear {fullname},

Welcome to {SCHOOL_NAME}! Please find your personalized payment agreement and receipt attached.
Student Code: {student_code}
Class: {level}
Contract: {contract_start} to {contract_end}
Amount Paid: GHS {paid}
Balance Due: GHS {balance}

Second payment (balance) is due: {(contract_start + timedelta(days=30))}

For any help, contact us at {SCHOOL_EMAIL} or call {SCHOOL_PHONE}.

Best regards,<br>
{SCHOOL_NAME}<br>
{SCHOOL_ADDRESS}<br>
<a href='https://{SCHOOL_WEBSITE}'>{SCHOOL_WEBSITE}</a>
"""
                        try:
                            if email:
                                msg = Mail(
                                    from_email=school_sender_email,
                                    to_emails=email,
                                    subject=subject,
                                    html_content=body.replace('\n', '<br>')
                                )
                                if attachment:
                                    msg.attachment = attachment
                                client = SendGridAPIClient(school_sendgrid_key)
                                client.send(msg)
                                st.info(f"Auto-email sent to {email}!")
                            else:
                                st.warning("No email detected for this student. Email not sent.")
                        except Exception as e:
                            st.error(f"Failed to send email: {e}")
                    else:
                        st.warning("Please enter SendGrid API Key and sender email in sidebar for auto-email.")

                    st.success(f"Student {fullname} added to your dashboard (and emailed if address available)!")

with tabs[1]:
    st.title("👩‍🎓 All Students (Edit & Update)")
    df_main = read_students()  # Always read latest from Google Sheets
    today = datetime.today().date()
    if not df_main.empty and "ContractEnd" in df_main.columns:
        df_main['Status'] = df_main['ContractEnd'].apply(
            lambda x: "Completed" if pd.to_datetime(str(x)).date() < today else "Enrolled"
        )
        statuses = ["All", "Enrolled", "Completed"]
        selected_status = st.selectbox("Filter by Status", statuses)
        if selected_status != "All":
            view_df = df_main[df_main["Status"] == selected_status]
        else:
            view_df = df_main
    else:
        view_df = df_main

    if not view_df.empty:
        for idx, row in view_df.iterrows():
            unique_id = f"{row['StudentCode']}_{idx}"
            with st.expander(f"{row['Name']} (Code: {row['StudentCode']}) [{row.get('Status', '')}]"):
                st.info(f"Status: {row.get('Status', '')}")
                name = st.text_input("Name", value=row['Name'], key=f"name_{unique_id}")
                phone = st.text_input("Phone", value=row['Phone'], key=f"phone_{unique_id}")
                location = st.text_input("Location", value=row['Location'], key=f"loc_{unique_id}")
                level = st.text_input("Level", value=row['Level'], key=f"level_{unique_id}")
                paid = st.number_input("Paid", value=float(row['Paid']), key=f"paid_{unique_id}")
                balance = st.number_input("Balance", value=float(row['Balance']), key=f"bal_{unique_id}")
                contract_start = st.text_input("Contract Start", value=str(row['ContractStart']), key=f"cs_{unique_id}")
                contract_end = st.text_input("Contract End", value=str(row['ContractEnd']), key=f"ce_{unique_id}")
                student_code = st.text_input("Student Code", value=row['StudentCode'], key=f"code_{unique_id}")

                # For Google Sheets, update logic can be added here if you want to edit in place!

                # Generate a new payment receipt (for new/extra payment)
                if st.button("Generate Payment Receipt", key=f"genreceipt_{unique_id}"):
                    pay_amt = st.number_input("Enter New Payment Amount", min_value=0.0, value=float(row["Paid"]), key=f"payamt_{unique_id}")
                    pay_date = st.date_input("Enter Payment Date", value=date.today(), key=f"paydate_{unique_id}")
                    receipt_pdf = generate_receipt_and_contract_pdf(row, agreement_text, payment_amount=pay_amt, payment_date=pay_date)
                    with open(receipt_pdf, "rb") as f:
                        pdf_bytes = f.read()
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="{row["Name"].replace(" ", "_")}_receipt.pdf">Download PDF Receipt</a>'
                        st.markdown(href, unsafe_allow_html=True)
                    st.success("Standalone receipt generated!")
    else:
        st.info("No students in the database for this filter.")

# ============ ADD STUDENT MANUALLY ============
with tabs[2]:
    st.title("➕ Add Student")
    with st.form("add_student"):
        name = st.text_input("Name")
        phone = st.text_input("Phone Number")
        location = st.text_input("Location")
        level = st.selectbox("Class/Level", ["A1", "A2", "B1", "B2", "C1", "C2"])
        paid = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0)
        balance = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0)
        contract_start = st.date_input("Contract Start", value=date.today())
        contract_end = st.date_input("Contract End", value=date.today())
        student_code = st.text_input("Student Code (unique, for software/app access)")
        if st.form_submit_button("Add Student") and name and phone and student_code:
            student_dict = {
                "Name": name,
                "Phone": phone,
                "Location": location,
                "Level": level,
                "Paid": paid,
                "Balance": balance,
                "ContractStart": str(contract_start),
                "ContractEnd": str(contract_end),
                "StudentCode": student_code
            }
            add_student_to_gsheet(student_dict)
            st.success(f"Added {name} (Code: {student_code})")
            st.experimental_rerun()

# ============ EXPENSES TAB ============
with tabs[3]:
    st.title("💵 Expenses and Financial Summary")
    st.info("Google Sheets persistence for expenses can be added using a similar helper as for students. (Let me know if you want this fully wired!)")
    # For now, keep using local CSV or display placeholder if desired.

# ============ WHATSAPP REMINDERS TAB ============
with tabs[4]:
    st.title("📲 WhatsApp Reminders for Debtors")
    df_main = read_students()
    debtors = df_main[(df_main["Balance"].astype(float) > 0) & (~df_main["Phone"].astype(str).str.contains("@"))]
    if not debtors.empty:
        st.write("### Students Owing (Click WhatsApp to Remind)")
        for idx, row in debtors.iterrows():
            whatsapp_msg = (
                f"Dear {row['Name']}, your current balance with {SCHOOL_NAME} is GHS {row['Balance']}. "
                f"Your student code: {row['StudentCode']}. "
                f"Please pay as soon as possible to maintain your active status. Thank you!\n"
                f"{SCHOOL_NAME} | {SCHOOL_PHONE}"
            )
            msg_encoded = urllib.parse.quote(whatsapp_msg)
            phone_str = clean_phone(row['Phone'])
            wa_url = f"https://wa.me/{phone_str}?text={msg_encoded}"
            st.markdown(
                f"**{row['Name']}** (GHS {row['Balance']} due) [Remind on WhatsApp](<{wa_url}>)"
            )
    else:
        st.info("No students currently owing.")

# ============ PDF CONTRACT TAB ============
with tabs[5]:
    st.title("📄 Generate Contract PDF for Any Student")
    df_main = read_students()
    if not df_main.empty:
        student_names = df_main["Name"].tolist()
        selected_for_pdf = st.selectbox("Select Student", student_names)
        if st.button("Generate Contract PDF"):
            student_row = df_main[df_main["Name"] == selected_for_pdf].iloc[0]
            contract_pdf = generate_receipt_and_contract_pdf(
                student_row, agreement_text, payment_amount=student_row["Paid"], payment_date=student_row["ContractStart"]
            )
            with open(contract_pdf, "rb") as f:
                pdf_bytes = f.read()
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/pdf;base64,{b64}" download="{student_row["Name"].replace(" ", "_")}_contract.pdf">Download {student_row["Name"]} Contract & Receipt PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
            st.success("PDF contract generated!")
    else:
        st.info("No students found.")

# ============ SEND EMAIL TAB ============
with tabs[6]:
    st.title("📧 Send Email to Student(s)")
    df_main = read_students()

    # Ensure 'Email' column exists and is cleaned in your DataFrame
    if "Email" not in df_main.columns:
        df_main.columns = [c.lower() for c in df_main.columns]
    email_col = "email" if "email" in df_main.columns else "Email"

    # List all students with a valid email address
    email_names = [(row['Name'], row[email_col]) for _, row in df_main.iterrows()
                   if isinstance(row.get(email_col, ''), str) and '@' in row.get(email_col, '')]
    email_options = [f"{name} ({email})" for name, email in email_names]
    email_dict = {f"{name} ({email})": email for name, email in email_names}

    email_mode = st.radio("Send email to", ["Individual student", "All students with email"])

    if email_mode == "Individual student":
        selected = st.selectbox("Select student", email_options)
        recipients = [email_dict[selected]] if selected else []
    else:
        recipients = [email for _, email in email_names]

    subject = st.text_input("Subject", value="Information from Learn Language Education Academy")
    message = st.text_area("Email Body (plain text or basic HTML)", height=200, value="Dear Student,\n\n...")
    uploaded_file = st.file_uploader("Attach a file (optional)", type=["pdf", "doc", "docx", "jpg", "png", "jpeg"])

    if st.button("Send Email"):
        from sendgrid.helpers.mail import Attachment, FileContent, FileName, FileType, Disposition
        sent, failed = 0, []
        attachment = None
        if uploaded_file is not None:
            data = uploaded_file.read()
            encoded = base64.b64encode(data).decode()
            attachment = Attachment(
                FileContent(encoded),
                FileName(uploaded_file.name),
                FileType(uploaded_file.type),
                Disposition("attachment")
            )
        for email in recipients:
            try:
                msg = Mail(
                    from_email=school_sender_email,
                    to_emails=email,
                    subject=subject,
                    html_content=message.replace('\n', '<br>')
                )
                if attachment:
                    msg.attachment = attachment
                client = SendGridAPIClient(school_sendgrid_key)
                client.send(msg)
                sent += 1
            except Exception as e:
                failed.append(email)
        st.success(f"Sent to {sent} student(s)!")
        if failed:
            st.warning(f"Failed to send to: {', '.join(failed)}")

# ============ ANALYTICS & EXPORT TAB ============
with tabs[7]:
    st.title("📊 Analytics & Export")
    df_main = read_students()
    st.subheader("Student Enrollment Over Time")
    if not df_main.empty and "ContractStart" in df_main.columns:
        df_main["EnrollDate"] = pd.to_datetime(df_main["ContractStart"], errors='coerce')
        enroll_by_month = df_main.groupby(df_main["EnrollDate"].dt.to_period("M")).size().reset_index(name='Count')
        enroll_by_month["EnrollDate"] = enroll_by_month["EnrollDate"].astype(str)
        st.line_chart(enroll_by_month.set_index("EnrollDate")["Count"])

    st.subheader("Export Data")
    st.download_button("Download All Students CSV", df_main.to_csv(index=False), file_name="all_students.csv")
    # For expenses, if moved to Google Sheets, do the same as students. For now:
    # st.download_button("Download All Expenses CSV", exp.to_csv(index=False), file_name="all_expenses.csv")
