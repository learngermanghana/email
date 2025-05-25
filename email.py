import streamlit as st
import pandas as pd
import os
from datetime import date, datetime, timedelta
from fpdf import FPDF
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import urllib.parse

# === PAGE CONFIG FIRST! ===
st.set_page_config(page_title="Learn Language Education Academy Dashboard", layout="wide")

# === SCHOOL INFO ===
SCHOOL_NAME = "Learn Language Education Academy"
SCHOOL_EMAIL = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# === PHONE NUMBER CLEANER ===
def clean_phone(phone):
    phone_str = str(phone)
    if phone_str.endswith('.0'):
        phone_str = phone_str[:-2]
    return phone_str.replace(" ", "").replace("+", "")

def generate_receipt_and_contract_pdf(
        student_row, agreement_text, payment_amount, payment_date=None,
        first_instalment=1500, course_length=12):
    if payment_date is None:
        payment_date = date.today()
    # Second installment is the current balance (or Paid - first_instalment, as you like)
    # Use float for math safety
    balance = float(student_row["Balance"]) if "Balance" in student_row else 0.0
    second_instalment = balance
    filled_agreement = (
        agreement_text
        .replace("[STUDENT_NAME]", student_row["Name"])
        .replace("[DATE]", str(payment_date))
        .replace("[CLASS]", student_row["Level"])
        .replace("[AMOUNT]", str(student_row["Paid"]))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(second_instalment))
        .replace("[COURSE_LENGTH]", str(course_length))
    )
    pdf = FPDF()
    pdf.add_page()
    # RECEIPT FIRST
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
    pdf.cell(200, 10, f"Balance Due: GHS {student_row['Balance']}", ln=True)
    pdf.cell(200, 10, f"Contract Start: {student_row['ContractStart']}", ln=True)
    pdf.cell(200, 10, f"Contract End: {student_row['ContractEnd']}", ln=True)
    pdf.ln(10)
    pdf.cell(200, 10, f"Receipt Date: {payment_date}", ln=True)
    pdf.cell(0, 10, "Thank you for your payment!", ln=True)
    pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)
    # AGREEMENT BELOW
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

def generate_receipt_and_contract_pdf(
        student_row, agreement_text, payment_amount, payment_date=None,
        first_instalment=1500, course_length=12):
    if payment_date is None:
        payment_date = date.today()
    # Second installment is the current balance
    balance = 0.0
    try:
        balance = float(student_row["Balance"])
    except Exception:
        pass
    second_instalment = balance
    filled_agreement = (
        agreement_text
        .replace("[STUDENT_NAME]", student_row["Name"])
        .replace("[DATE]", str(payment_date))
        .replace("[CLASS]", student_row["Level"])
        .replace("[AMOUNT]", str(student_row["Paid"]))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(second_instalment))
        .replace("[COURSE_LENGTH]", str(course_length))
    )
    pdf = FPDF()
    pdf.add_page()
    # Receipt first
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
    pdf.cell(200, 10, f"Balance Due: GHS {balance}", ln=True)
    pdf.cell(200, 10, f"Contract Start: {student_row['ContractStart']}", ln=True)
    pdf.cell(200, 10, f"Contract End: {student_row['ContractEnd']}", ln=True)
    pdf.ln(10)
    pdf.cell(200, 10, f"Receipt Date: {payment_date}", ln=True)
    pdf.cell(0, 10, "Thank you for your payment!", ln=True)
    pdf.cell(0, 10, "Signed: Felix Asadu", ln=True)
    # Agreement below
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


# === FILES & DATABASE SETUP ===
student_file = "students_simple.csv"
expenses_file = "expenses_all.csv"
needed_cols = [
    "Name", "Phone", "Location", "Level", "Paid", "Balance",
    "ContractStart", "ContractEnd", "StudentCode"
]
if not os.path.exists(student_file):
    df_main = pd.DataFrame(columns=needed_cols)
    df_main.to_csv(student_file, index=False)
df_main = pd.read_csv(student_file)
for col in needed_cols:
    if col not in df_main.columns:
        df_main[col] = ""
df_main = df_main[needed_cols]

if not os.path.exists(expenses_file):
    exp = pd.DataFrame(columns=["Type", "Item", "Amount", "Date"])
    exp.to_csv(expenses_file, index=False)
exp = pd.read_csv(expenses_file)



# === GOOGLE SHEET: FORM RESPONSES ===
sheet_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"

# === PAGE HEADER ===
st.title(f"🏫 {SCHOOL_NAME} Dashboard")
st.caption(f"📍 {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

# === NOTIFICATION BELL ===
today = datetime.today().date()
notifications = []

debtors = df_main[df_main["Balance"].astype(float) > 0]
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
    email_link = f"mailto:{row['Phone']}" if "@" in str(row['Phone']) else ""
    contact_links = f"<a href='{wa_url}'>WhatsApp</a>"
    if email_link:
        contact_links += f" | <a href='{email_link}'>Email</a>"
    notifications.append(
        f"💰 Payment Due: <b>{row['Name']}</b> (GHS {row['Balance']} due) [{contact_links}]"
    )

soon_threshold = today + timedelta(days=30)
for idx, row in df_main.iterrows():
    try:
        end_date = pd.to_datetime(str(row["ContractEnd"])).date()
        if today <= end_date <= soon_threshold:
            whatsapp_msg = (
                f"Dear {row['Name']}, your contract with {SCHOOL_NAME} ends on {row['ContractEnd']}. "
                f"Please contact us if you wish to extend. {SCHOOL_PHONE}"
            )
            msg_encoded = urllib.parse.quote(whatsapp_msg)
            phone_str = clean_phone(row['Phone'])
            wa_url = f"https://wa.me/{phone_str}?text={msg_encoded}"
            notifications.append(
                f"⏳ Contract Ending: <b>{row['Name']}</b> (Ends {row['ContractEnd']}) [<a href='{wa_url}'>WhatsApp</a>]"
            )
    except Exception:
        continue

for idx, row in df_main.iterrows():
    try:
        end_date = pd.to_datetime(str(row["ContractEnd"])).date()
        if end_date < today:
            notifications.append(
                f"❗ <b>{row['Name']}</b>'s contract expired on {row['ContractEnd']}!"
            )
    except Exception:
        continue

if notifications:
    st.markdown(f"""<div style="background:#fffbe6;border:1px solid #ffd324;border-radius:8px;padding:10px;margin-bottom:15px;">
    <span style="font-size:1.3em;">🔔 <b>Notifications</b></span><br>
    {"<br>".join(notifications)}
    </div>""", unsafe_allow_html=True)
else:
    st.markdown(f"""<div style="background:#ecfff1;border:1px solid #3ecf8e;border-radius:8px;padding:10px;margin-bottom:15px;">
    <span style="font-size:1.3em;">🔔 <b>Notifications</b></span><br>
    No urgent payment or contract alerts at this time.
    </div>""", unsafe_allow_html=True)

# === Editable Payment Agreement Template ===
if "agreement_template" not in st.session_state:
    st.session_state["agreement_template"] = """
PAYMENT AGREEMENT

This Payment Agreement is entered into on [DATE] for [CLASS] students of Learn Language Education Academy and Felix Asadu ("Teacher").

Terms of Payment:
1. Payment Amount: The student agrees to pay the teacher a total of [AMOUNT] cedis for the course.
2. Payment Schedule: The payment can be made in full or in two installments: a minimum of [FIRST_INSTALMENT] cedis for the first installment and the remaining [SECOND_INSTALMENT] cedis for the second installment. The second installment must be paid within one month of the initial deposit.
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
    "📊 Analytics & Export"    # This is tab index 7
])


# ============ PENDING REGISTRATIONS TAB ============
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
                    # --- Add to main dashboard CSV ---
                    new_row = pd.DataFrame([{
                        "Name": fullname,
                        "Phone": phone,
                        "Location": location,
                        "Level": level,
                        "Paid": paid,
                        "Balance": balance,
                        "ContractStart": contract_start,
                        "ContractEnd": contract_end,
                        "StudentCode": student_code
                    }])
                    df_main = pd.concat([df_main, new_row], ignore_index=True)
                    df_main.to_csv(student_file, index=False)

                    # --- Generate combined receipt + contract PDF ---
                    pdf_file = generate_receipt_and_contract_pdf(
                        new_row.iloc[0], agreement_text, payment_amount=paid, payment_date=contract_start,
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
