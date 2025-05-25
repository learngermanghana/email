# ✅ Imports, Config, Secrets, GSheet Setup
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

# === PAGE CONFIG ===
st.set_page_config(page_title="Learn Language Education Academy Dashboard", layout="wide")

# === SCHOOL CONFIG ===
SCHOOL_NAME = "Learn Language Education Academy"
SCHOOL_EMAIL = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# === EMAIL CONFIG ===
school_sendgrid_key = st.secrets["general"].get("SENDGRID_API_KEY")
school_sender_email = st.secrets["general"].get("SENDER_EMAIL", SCHOOL_EMAIL)

# === GOOGLE SHEET SETUP ===
GOOGLE_SHEET_NAME = "YourStudentSheet"  # Change to your actual sheet file name

def get_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    service_account_info = st.secrets["gspread_service_account"]  # already a dict!
    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    client = gspread.authorize(creds)
    sheet = client.open(GOOGLE_SHEET_NAME)
    worksheet = sheet.sheet1
    return worksheet

# ✅ Student Helpers, Error Handling, PDF Generator

def clean_phone(phone):
    phone_str = str(phone).strip().replace(" ", "").replace("+", "")
    if phone_str.startswith("0"):
        phone_str = "233" + phone_str[1:]
    return phone_str

def read_students():
    try:
        worksheet = get_gsheet()
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        df.columns = [col.strip() for col in df.columns]  # Clean headers
        return df
    except Exception as e:
        st.error(f"❌ Failed to read students from Google Sheets: {e}")
        return pd.DataFrame()

def add_student_to_gsheet(student_dict):
    try:
        worksheet = get_gsheet()
        worksheet.append_row(list(student_dict.values()))
    except Exception as e:
        st.error(f"❌ Failed to add student to Google Sheets: {e}")

def generate_receipt_and_contract_pdf(
        student_row, agreement_text, payment_amount, payment_date=None,
        first_instalment=1500, course_length=12):

    if payment_date is None:
        payment_date = date.today()
    try:
        second_instalment = float(student_row.get("Balance", 0))
    except Exception:
        second_instalment = 0.0

    try:
        if hasattr(payment_date, 'date'):
            payment_date_obj = payment_date.date()
        else:
            payment_date_obj = payment_date
        second_due_date = payment_date_obj + timedelta(days=30)
    except Exception:
        second_due_date = ""

    get_val = lambda x: student_row[x] if x in student_row else ""
    filled_agreement = (
        agreement_text
        .replace("[STUDENT_NAME]", get_val("Name"))
        .replace("[DATE]", str(payment_date))
        .replace("[CLASS]", get_val("Level"))
        .replace("[AMOUNT]", str(get_val("Paid")))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(second_instalment))
        .replace("[SECOND_DUE_DATE]", str(second_due_date))
        .replace("[COURSE_LENGTH]", str(course_length))
    )

    pdf = FPDF()
    pdf.add_page()
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
    pdf.cell(200, 10, f"Name: {get_val('Name')}", ln=True)
    pdf.cell(200, 10, f"Student Code: {get_val('StudentCode')}", ln=True)
    pdf.cell(200, 10, f"Phone: {get_val('Phone')}", ln=True)
    pdf.cell(200, 10, f"Level: {get_val('Level')}", ln=True)
    pdf.cell(200, 10, f"Amount Paid: GHS {payment_amount}", ln=True)
    pdf.cell(200, 10, f"Balance Due: GHS {second_instalment}", ln=True)
    pdf.cell(200, 10, f"Contract Start: {get_val('ContractStart')}", ln=True)
    pdf.cell(200, 10, f"Contract End: {get_val('ContractEnd')}", ln=True)
    pdf.cell(200, 10, f"Second Payment Due: {second_due_date}", ln=True)
    pdf.ln(10)
    pdf.cell(0, 10, "Thank you for your payment!", ln=True)
    pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)

    pdf.ln(15)
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, f"{SCHOOL_NAME} Student Contract", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    for line in filled_agreement.split("\n"):
        pdf.multi_cell(0, 10, line)
    pdf.ln(10)
    pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)

    pdf_name = f"{get_val('Name').replace(' ', '_')}_receipt_and_contract.pdf"
    pdf.output(pdf_name)
    return pdf_name

# ✅ UI Header, Agreement Template Editor, Preview Download
sheet_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"
st.title(f"\U0001F3EB {SCHOOL_NAME} Dashboard")
st.caption(f"\U0001F4CD {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

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

# PDF Preview
pdf_preview = FPDF()
pdf_preview.add_page()
pdf_preview.set_font("Arial", size=12)
for line in agreement_text.split("\n"):
    pdf_preview.multi_cell(0, 10, line)
pdf_preview.output("preview_agreement.pdf")

with open("preview_agreement.pdf", "rb") as f:
    preview_bytes = f.read()
    preview_b64 = base64.b64encode(preview_bytes).decode()
    st.markdown(f'<a href="data:application/pdf;base64,{preview_b64}" download="Agreement_Preview.pdf">📄 Download Agreement Preview PDF</a>', unsafe_allow_html=True)

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

# ✅ Pending Registrations Tab (Tab 0)
with tabs[0]:
    st.title("📝 Pending Student Registrations (Approve & Auto-Email)")
    try:
        new_students = pd.read_csv(sheet_url)
        new_students.columns = [c.strip().lower().replace(" ", "_").replace("(", "").replace(")", "") for c in new_students.columns]
    except Exception as e:
        st.error(f"❌ Could not load registrations: {e}")
        new_students = pd.DataFrame()

    if not new_students.empty:
        for i, row in new_students.iterrows():
            fullname = row.get('full_name', '')
            phone = row.get('phone_number', '')
            email = row.get('email', '')
            level = row.get('class_a1a2_etc', '')
            location = row.get('location', '')
            student_code = st.text_input("Assign Student Code", key=f"code_{i}")
            contract_start = st.date_input("Contract Start", value=date.today(), key=f"start_{i}")
            course_length = st.number_input("Course Length (weeks)", min_value=1, value=12, key=f"length_{i}")
            contract_end = st.date_input("Contract End", value=contract_start + timedelta(weeks=int(course_length)), key=f"end_{i}")
            paid = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0, key=f"paid_{i}")
            balance = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0, key=f"bal_{i}")
            attach_pdf = st.checkbox("Attach Receipt & Contract PDF to Email?", value=True, key=f"pdf_{i}")

            if st.button("Approve & Add to Main List", key=f"approve_{i}") and student_code:
                df_existing = read_students()
                if not df_existing.empty and "StudentCode" in df_existing.columns:
                    existing_codes = df_existing["StudentCode"].tolist()
                    if student_code in existing_codes:
                        st.error("❌ This student code already exists. Please choose another.")
                        st.stop()
                student_dict = {
                    "Name": fullname,
                    "Phone": phone,
                    "Location": location,
                    "Level": level,
                    "Paid": paid,
                    "Balance": balance,
                    "ContractStart": str(contract_start),
                    "ContractEnd": str(contract_end),
                    "StudentCode": student_code,
                    "Email": email
                }
                add_student_to_gsheet(student_dict)

                pdf_file = generate_receipt_and_contract_pdf(
                    student_dict, agreement_text, payment_amount=paid, payment_date=contract_start,
                    first_instalment=1500, course_length=course_length
                )

                if school_sendgrid_key and school_sender_email and email:
                    try:
                        msg = Mail(
                            from_email=school_sender_email,
                            to_emails=email,
                            subject=f"Welcome to {SCHOOL_NAME} – Your Registration Details",
                            html_content=f"""
Dear {fullname},<br><br>
Welcome to {SCHOOL_NAME}! Please find your personalized agreement and receipt attached.<br>
Student Code: {student_code}<br>
Class: {level}<br>
Contract: {contract_start} to {contract_end}<br>
Amount Paid: GHS {paid}<br>
Balance Due: GHS {balance}<br><br>
Second payment is due by: {(contract_start + timedelta(days=30))}<br><br>
Best regards,<br>
{SCHOOL_NAME}<br>
<a href='https://{SCHOOL_WEBSITE}'>{SCHOOL_WEBSITE}</a>
"""
                        )
                        if attach_pdf and pdf_file:
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
                        st.success(f"✅ Student {fullname} added and email sent!")
                    except Exception as e:
                        st.warning(f"⚠️ Failed to send email to {email}: {e}")
                else:
                    st.success(f"✅ Student {fullname} added to dashboard.")

# ✅ All Students Tab (Tab 1)
with tabs[1]:
    st.title("👩‍🎓 All Students (Edit & Generate Receipt)")
    df_main = read_students()
    if not df_main.empty:
        today = datetime.today().date()
        if "ContractEnd" in df_main.columns:
            def parse_status(x):
                try:
                    d = pd.to_datetime(str(x), errors='coerce').date()
                    return "Completed" if d < today else "Enrolled"
                except:
                    return "Unknown"
            df_main["Status"] = df_main["ContractEnd"].apply(parse_status)
        else:
            df_main["Status"] = "Unknown"
        status_filter = st.selectbox("Filter by Status", ["All", "Enrolled", "Completed"])
        view_df = df_main if status_filter == "All" else df_main[df_main["Status"] == status_filter]
        for idx, row in view_df.iterrows():
            unique_id = f"{row.get('StudentCode', idx)}_{idx}"
            with st.expander(f"{row.get('Name')} (Code: {row.get('StudentCode')}) [{row.get('Status', '')}]"):
                name = st.text_input("Name", value=row.get("Name", ""), key=f"name_{unique_id}")
                phone = st.text_input("Phone", value=row.get("Phone", ""), key=f"phone_{unique_id}")
                location = st.text_input("Location", value=row.get("Location", ""), key=f"loc_{unique_id}")
                level = st.text_input("Level", value=row.get("Level", ""), key=f"level_{unique_id}")
                paid = st.number_input("Paid", value=float(row.get("Paid", 0)), key=f"paid_{unique_id}")
                balance = st.number_input("Balance", value=float(row.get("Balance", 0)), key=f"bal_{unique_id}")
                contract_start = st.text_input("Contract Start", value=str(row.get("ContractStart", "")), key=f"cs_{unique_id}")
                contract_end = st.text_input("Contract End", value=str(row.get("ContractEnd", "")), key=f"ce_{unique_id}")
                student_code = st.text_input("Student Code", value=row.get("StudentCode", ""), key=f"code_{unique_id}")

                if st.button("Generate Receipt", key=f"genreceipt_{unique_id}"):
                    pay_amt = st.number_input("Enter New Payment Amount", min_value=0.0, value=paid, key=f"payamt_{unique_id}")
                    pay_date = st.date_input("Enter Payment Date", value=date.today(), key=f"paydate_{unique_id}")
                    receipt_pdf = generate_receipt_and_contract_pdf(
                        row,
                        agreement_text,
                        payment_amount=pay_amt,
                        payment_date=pay_date
                    )
                    with open(receipt_pdf, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                        download_link = f'<a href="data:application/pdf;base64,{b64}" download="{name.replace(" ", "_")}_receipt.pdf">📄 Download Receipt PDF</a>'
                        st.markdown(download_link, unsafe_allow_html=True)
                    st.success("✅ Standalone payment receipt generated!")
    else:
        st.info("No student data available.")

# ✅ Add Student Manually Tab (Tab 2)
with tabs[2]:
    st.title("➕ Add Student Manually")
    with st.form("add_student_form"):
        name = st.text_input("Name")
        phone = st.text_input("Phone Number")
        location = st.text_input("Location")
        level = st.selectbox("Level", ["A1", "A2", "B1", "B2", "C1", "C2"])
        paid = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0)
        balance = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0)
        contract_start = st.date_input("Contract Start", value=date.today())
        course_length = st.number_input("Course Length (weeks)", min_value=1, value=12)
        contract_end = contract_start + timedelta(weeks=int(course_length))
        student_code = st.text_input("Student Code (unique)")
        email = st.text_input("Email (optional)")
        submitted = st.form_submit_button("Add Student")
        if submitted:
            df_existing = read_students()
            if not df_existing.empty and "StudentCode" in df_existing.columns:
                existing_codes = df_existing["StudentCode"].tolist()
                if student_code in existing_codes:
                    st.error("❌ This student code already exists.")
                    st.stop()
            student_dict = {
                "Name": name,
                "Phone": phone,
                "Location": location,
                "Level": level,
                "Paid": paid,
                "Balance": balance,
                "ContractStart": str(contract_start),
                "ContractEnd": str(contract_end),
                "StudentCode": student_code,
                "Email": email
            }
            add_student_to_gsheet(student_dict)
            st.success(f"✅ Student {name} added successfully.")
            st.experimental_rerun()

# ✅ Expenses Tab (Tab 3)
with tabs[3]:
    st.title("💵 Expenses (Manual for now)")
    st.info("🛠 Expense tracking via Google Sheets can be added later. Currently not wired.")

# ✅ WhatsApp Reminders for Debtors (Tab 4)
with tabs[4]:
    st.title("📲 WhatsApp Reminders for Debtors")
    df_main = read_students()
    if not df_main.empty and "Balance" in df_main.columns and "Phone" in df_main.columns:
        try:
            df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0)
            debtors = df_main[(df_main["Balance"] > 0) & (~df_main["Phone"].astype(str).str.contains("@"))]
            if not debtors.empty:
                st.write("### Debtors List")
                for _, row in debtors.iterrows():
                    message = (
                        f"Dear {row['Name']}, your balance at {SCHOOL_NAME} is GHS {row['Balance']}. "
                        f"Student Code: {row['StudentCode']}. Please pay soon to remain active. Thank you!\n\n"
                        f"{SCHOOL_NAME} – {SCHOOL_PHONE}"
                    )
                    encoded_msg = urllib.parse.quote(message)
                    wa_link = f"https://wa.me/{clean_phone(row['Phone'])}?text={encoded_msg}"
                    st.markdown(f"**{row['Name']}** – GHS {row['Balance']} due – [Send WhatsApp](<{wa_link}>)")
            else:
                st.success("✅ No debtors currently.")
        except Exception as e:
            st.error(f"❌ Error while processing debtors: {e}")
    else:
        st.warning("⚠️ 'Balance' or 'Phone' column missing in Google Sheet.")

# ✅ Generate Contract PDF (Tab 5)
with tabs[5]:
    st.title("📄 Generate Contract PDF for Any Student")
    df_main = read_students()
    if not df_main.empty and "Name" in df_main.columns:
        selected_name = st.selectbox("Select Student", df_main["Name"].unique())
        selected_row = df_main[df_main["Name"] == selected_name].iloc[0]
        if st.button("Generate PDF"):
            pdf_file = generate_receipt_and_contract_pdf(
                selected_row,
                agreement_text,
                payment_amount=selected_row.get("Paid", 0),
                payment_date=selected_row.get("ContractStart", date.today())
            )
            with open(pdf_file, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                download_link = f'<a href="data:application/pdf;base64,{b64}" download="{selected_name.replace(" ", "_")}_contract.pdf">📄 Download PDF</a>'
                st.markdown(download_link, unsafe_allow_html=True)
            st.success("✅ PDF generated!")
    else:
        st.warning("No students available.")

# ✅ Send Email to Students (Tab 6)
with tabs[6]:
    st.title("📧 Send Email to Students")
    df_main = read_students()
    if not df_main.empty:
        df_main.columns = [col.strip().lower() for col in df_main.columns]
        if "email" not in df_main.columns:
            st.warning("⚠️ Column 'email' not found.")
        else:
            email_list = [(row["name"], row["email"]) for _, row in df_main.iterrows()
                          if isinstance(row.get("email"), str) and "@" in row.get("email")]
            options = [f"{n} ({e})" for n, e in email_list]
            email_dict = {f"{n} ({e})": e for n, e in email_list}
            if not options:
                st.info("No students with valid email.")
            else:
                mode = st.radio("Send To", ["Individual", "All with Email"])
                if mode == "Individual":
                    selected = st.selectbox("Choose student", options)
                    recipients = [email_dict[selected]]
                else:
                    recipients = [e for _, e in email_list]
                subject = st.text_input("Email Subject", value="Info from Learn Language Education Academy")
                message = st.text_area("Message Body", value="Dear student,\n\n...", height=200)
                file = st.file_uploader("Attach file (optional)", type=["pdf", "doc", "jpg", "png"])
                if st.button("Send Email"):
                    sent, failed = 0, []
                    attachment = None
                    if file:
                        encoded = base64.b64encode(file.read()).decode()
                        attachment = Attachment(
                            FileContent(encoded),
                            FileName(file.name),
                            FileType(file.type),
                            Disposition("attachment")
                        )
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
                    st.success(f"✅ Sent to {sent} students.")
                    if failed:
                        st.warning(f"⚠️ Failed to send to: {', '.join(failed)}")
    else:
        st.warning("No students in database.")

# ✅ Analytics & Export (Tab 7)
with tabs[7]:
    st.title("📊 Analytics & Export")
    df_main = read_students()
    st.subheader("📈 Enrollment Over Time")
    if not df_main.empty and "ContractStart" in df_main.columns:
        try:
            df_main["EnrollDate"] = pd.to_datetime(df_main["ContractStart"], errors="coerce")
            monthly = df_main.groupby(df_main["EnrollDate"].dt.to_period("M")).size().reset_index(name="Count")
            monthly["EnrollDate"] = monthly["EnrollDate"].astype(str)
            st.line_chart(monthly.set_index("EnrollDate")["Count"])
        except Exception as e:
            st.warning(f"⚠️ Could not parse dates: {e}")
    else:
        st.info("No contract start dates to display.")
    st.subheader("⬇️ Export All Student Data")
    if not df_main.empty:
        csv = df_main.to_csv(index=False)
        st.download_button("📁 Download CSV", data=csv, file_name="students_export.csv", mime="text/csv")
    else:
        st.info("No data to export.")
