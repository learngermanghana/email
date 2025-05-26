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

# === EMAIL CONFIG (secrets only, secure) ===
school_sendgrid_key = st.secrets["general"].get("SENDGRID_API_KEY")
school_sender_email = st.secrets["general"].get("SENDER_EMAIL", SCHOOL_EMAIL)

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
    try:
        paid = float(student_row["Paid"])
        balance = float(student_row["Balance"])
        total_amount = paid + balance
    except Exception:
        paid = 0.0
        balance = 0.0
        total_amount = 0.0
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
        .replace("[AMOUNT]", str(total_amount))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(balance))
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
    pdf.cell(200, 10, f"Amount Paid: GHS {paid}", ln=True)
    pdf.cell(200, 10, f"Balance Due: GHS {balance}", ln=True)
    pdf.cell(200, 10, f"Contract Start: {student_row['ContractStart']}", ln=True)
    pdf.cell(200, 10, f"Contract End: {student_row['ContractEnd']}", ln=True)
    pdf.ln(10)
    pdf.cell(200, 10, f"Receipt Date: {payment_date}", ln=True)
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
# === FILES & DATABASE SETUP ===
student_file = "students_simple.csv"
expenses_file = "expenses_all.csv"
needed_cols = [
    "Name", "Phone", "Location", "Level", "Paid", "Balance",
    "ContractStart", "ContractEnd", "StudentCode"
]

# Ensure the student CSV exists, then load it
if not os.path.exists(student_file):
    df_main = pd.DataFrame(columns=needed_cols)
    df_main.to_csv(student_file, index=False)

df_main = pd.read_csv(student_file)

# --- Normalize column names by case-insensitive matching ---
col_map = {}
for needed in needed_cols:
    for col in df_main.columns:
        if col.strip().lower() == needed.lower():
            col_map[col] = needed
df_main = df_main.rename(columns=col_map)

# Fill any missing needed columns
for col in needed_cols:
    if col not in df_main.columns:
        df_main[col] = ""

# Enforce column order
df_main = df_main[needed_cols]

# === EXPENSES SETUP ===
if not os.path.exists(expenses_file):
    exp = pd.DataFrame(columns=["Type", "Item", "Amount", "Date"])
    exp.to_csv(expenses_file, index=False)
exp = pd.read_csv(expenses_file)

# === GOOGLE SHEET: FORM RESPONSES ===
sheet_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"

# === PAGE HEADER ===
st.title(f"🏫 {SCHOOL_NAME} Dashboard")
st.caption(f"📍 {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

# --- SUMMARY KPIs & CHARTS ---
st.header("📊 Overview")

# Compute basic metrics
# Ensure you’ve already computed df_main and exp as DataFrames above
today = datetime.today().date()
# Add Status column if not already there
df_main['Status'] = df_main['ContractEnd'].apply(
    lambda x: "Completed" if pd.to_datetime(str(x), errors='coerce').date() < today else "Enrolled"
)

total_enrolled  = int((df_main['Status']=="Enrolled").sum())
total_completed = int((df_main['Status']=="Completed").sum())
total_collected = float(df_main['Paid'].astype(float).sum())
total_outstanding = float(df_main['Balance'].astype(float).sum())

col1, col2, col3, col4 = st.columns(4)
col1.metric("👩‍🎓 Enrolled",  total_enrolled)
col2.metric("✅ Completed", total_completed)
col3.metric("💰 Collected (GHS)", f"{total_collected:,.2f}")
col4.metric("⏳ Outstanding (GHS)", f"{total_outstanding:,.2f}")

# Monthly income vs. expenses chart
st.subheader("Monthly Income vs Expenses")
# prepare income
inc = (
    df_main
    .assign(Month=pd.to_datetime(df_main['ContractStart'], errors='coerce').dt.to_period("M"))
    .groupby("Month")["Paid"]
    .sum()
    .rename("Income")
)
# prepare expenses
exp_monthly = (
    exp
    .assign(Month=pd.to_datetime(exp['Date'], errors='coerce').dt.to_period("M"))
    .groupby("Month")["Amount"]
    .sum()
    .rename("Expenses")
)
df_me = pd.concat([inc, exp_monthly], axis=1).fillna(0)
df_me.index = df_me.index.astype(str)
st.bar_chart(df_me)

# === NOTIFICATION BELL ===
today = datetime.today().date()
notifications = []

# Fix: Ensure "Balance" is numeric and safe for comparison
df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0)

debtors = df_main[df_main["Balance"] > 0]
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

# === TABS ===
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

# ============ PENDING REGISTRATIONS TAB ============
with tabs[0]:
    st.title("📝 Pending Student Registrations (Approve & Auto-Email)")
    try:
        new_students = pd.read_csv(sheet_url)
        def clean_col(c):
            c = c.strip().lower().replace("(", "").replace(")", "") \
                 .replace(",", "").replace("-", "").replace(" ", "_")
            return c
        new_students.columns = [clean_col(c) for c in new_students.columns]
        st.info(f"Columns: {', '.join(new_students.columns)}")
    except Exception as e:
        st.error(f"Could not load registrations: {e}")
        new_students = pd.DataFrame()

    if not new_students.empty:
        for i, row in new_students.iterrows():
            fullname = row.get('full_name', '')
            phone    = row.get('phone_number', '')
            email    = row.get('email', '')
            level    = row.get('class_a1a2_etc', '')
            location = row.get('location', '')
            emergency= row.get('emergency_contact_phone_number', '')

            with st.expander(f"{fullname} ({phone})"):
                st.write(f"**Email:** {email}")
                student_code    = st.text_input("Assign Student Code", key=f"code_{i}")
                contract_start  = st.date_input("Contract Start", value=date.today(), key=f"start_{i}")
                contract_end    = st.date_input("Contract End",   value=date.today(), key=f"end_{i}")
                paid            = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0, key=f"paid_{i}")
                balance         = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0, key=f"bal_{i}")
                first_inst      = st.number_input("First Instalment (GHS)", min_value=0.0, value=1500.0, key=f"firstinst_{i}")
                course_length   = st.number_input("Course Length (weeks)", min_value=1, value=12, key=f"length_{i}")

                attach_pdf = st.checkbox("Attach Receipt & Contract PDF to Email?", value=True, key=f"pdf_{i}")

                if st.button("Approve & Add to Main List", key=f"approve_{i}") and student_code:
                    # — Add to students CSV —
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

                    # — Generate & attach PDF —
                    pdf_file = generate_receipt_and_contract_pdf(
                        new_row.iloc[0], agreement_text,
                        payment_amount=paid,
                        payment_date=contract_start,
                        first_instalment=first_inst,
                        course_length=course_length
                    )
                    attachment = None
                    if attach_pdf:
                        with open(pdf_file, "rb") as f:
                            data = f.read()
                        encoded = base64.b64encode(data).decode()
                        attachment = Attachment(
                            FileContent(encoded),
                            FileName(pdf_file),
                            FileType("application/pdf"),
                            Disposition("attachment")
                        )

                    # — Send Email —
                    if school_sendgrid_key and school_sender_email:
                        subject = f"Welcome to {SCHOOL_NAME} – Your Registration Details"
                        body = f"""
Dear {fullname},

Welcome to {SCHOOL_NAME}! Your payment agreement & receipt are attached.
Student Code: {student_code}
Class: {level}
Contract: {contract_start} to {contract_end}
Amount Paid: GHS {paid}
Balance Due: GHS {balance}

For help, contact us at {SCHOOL_EMAIL} or {SCHOOL_PHONE}.

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
                                SendGridAPIClient(school_sendgrid_key).send(msg)
                                st.info(f"Email sent to {email}!")
                            else:
                                st.warning("No email on file; skipped.")
                        except Exception as e:
                            st.error(f"Email failed: {e}")
                    else:
                        st.warning("Set your SendGrid key & sender in secrets.")

                    st.success(f"{fullname} approved & added.")

# ============ ALL STUDENTS TAB ============
with tabs[1]:
    st.title("👩‍🎓 All Students (Search, Filter, Edit & Update)")

    # ── Search & Status Filter ──
    search = st.text_input("🔍 Search by name or code", "")
    today = datetime.today().date()
    df_main["_EndDate"] = pd.to_datetime(df_main["ContractEnd"], errors="coerce").dt.date
    df_main["Status"] = df_main["_EndDate"].apply(
        lambda d: "Completed" if pd.notna(d) and d < today else "Enrolled"
    )

    sel_status = st.selectbox("Filter by status", ["All", "Enrolled", "Completed"])
    view_df = df_main.copy()
    if sel_status != "All":
        view_df = view_df[view_df["Status"] == sel_status]
    if search:
        mask = (
            view_df["Name"].str.contains(search, case=False, na=False)
            | view_df["StudentCode"].str.contains(search, case=False, na=False)
        )
        view_df = view_df[mask]

    if view_df.empty:
        st.info("No students match your filter.")
    else:
        for idx, row in view_df.iterrows():
            uid = f"{row['StudentCode']}_{idx}"
            with st.expander(f"{row['Name']} ({row['StudentCode']}) [{row['Status']}]"):
                st.info(f"Status: {row['Status']}")
                name    = st.text_input("Name", row["Name"], key=f"name_{uid}")
                phone   = st.text_input("Phone", row["Phone"], key=f"phone_{uid}")
                loc     = st.text_input("Location", row["Location"], key=f"loc_{uid}")
                lvl     = st.text_input("Level", row["Level"], key=f"level_{uid}")
                paid    = st.number_input("Paid", float(row["Paid"]), key=f"paid_{uid}")
                bal     = st.number_input("Balance", float(row["Balance"]), key=f"bal_{uid}")
                cs      = st.text_input("Contract Start", str(row["ContractStart"]), key=f"cs_{uid}")
                ce      = st.text_input("Contract End", str(row["ContractEnd"]), key=f"ce_{uid}")
                stcode  = st.text_input("Student Code", row["StudentCode"], key=f"code_{uid}")

                if st.button("Update Student", key=f"upd_{uid}"):
                    for col, val in [
                        ("Name", name), ("Phone", phone), ("Location", loc),
                        ("Level", lvl), ("Paid", paid), ("Balance", bal),
                        ("ContractStart", cs), ("ContractEnd", ce),
                        ("StudentCode", stcode)
                    ]:
                        df_main.at[idx, col] = val
                    df_main.to_csv(student_file, index=False)
                    st.success("Student updated!")
                    st.experimental_rerun()

                if st.button("Delete Student", key=f"del_{uid}"):
                    df_main.drop(idx, inplace=True)
                    df_main.to_csv(student_file, index=False)
                    st.success("Student deleted!")
                    st.experimental_rerun()

                if st.button("Generate Payment Receipt", key=f"rcpt_{uid}"):
                    amt = st.number_input(
                        "Payment amount", min_value=0.0, value=float(row["Paid"]), key=f"amt_{uid}"
                    )
                    dt  = st.date_input(
                        "Payment date", value=date.today(), key=f"dt_{uid}"
                    )
                    pdf_file = generate_receipt_and_contract_pdf(
                        row, agreement_text, payment_amount=amt, payment_date=dt
                    )
                    with open(pdf_file, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    st.markdown(
                        f'<a href="data:application/pdf;base64,{b64}" '
                        f'download="{row["Name"].replace(" ","_")}_receipt.pdf">Download Receipt</a>',
                        unsafe_allow_html=True
                    )
                    st.success("Receipt ready!")

    # ── Admin: Restore from CSV Backup ──
    with st.expander("🔄 Admin: Upload Student/Expense CSV Backup", expanded=False):
        st.write("Overwrite current records by uploading your CSVs:")

        uploaded_students = st.file_uploader(
            "Upload students_simple.csv", type="csv", key="upload_students"
        )
        uploaded_expenses = st.file_uploader(
            "Upload expenses_all.csv", type="csv", key="upload_expenses"
        )

        if uploaded_students:
            df_new = pd.read_csv(uploaded_students)
            missing = set(needed_cols) - set(df_new.columns)
            if missing:
                st.error(f"Missing columns in students CSV: {missing}")
            else:
                df_new[needed_cols].to_csv(student_file, index=False)
                st.success("Student records restored. Refresh to reload.")

        if uploaded_expenses:
            df_new_exp = pd.read_csv(uploaded_expenses)
            exp_cols = {"Type", "Item", "Amount", "Date"}
            if not exp_cols.issubset(df_new_exp.columns):
                st.error(f"Missing columns in expenses CSV: {exp_cols - set(df_new_exp.columns)}")
            else:
                df_new_exp.to_csv(expenses_file, index=False)
                st.success("Expense records restored. Refresh to reload.")


    # Parse ContractEnd safely
    df_main["ContractEnd"] = pd.to_datetime(df_main["ContractEnd"], errors="coerce")
    today = datetime.today().date()

    def get_status(end_dt):
        if pd.isna(end_dt):
            return "Enrolled"
        return "Completed" if end_dt.date() < today else "Enrolled"

    df_main["Status"] = df_main["ContractEnd"].apply(get_status)
    statuses = ["All"] + sorted(df_main["Status"].unique())
    selected_status = st.selectbox("Filter by Status", statuses)

    if selected_status == "All":
        view_df = df_main
    else:
        view_df = df_main[df_main["Status"] == selected_status]

    if view_df.empty:
        st.info("No students in the database for this filter.")
    else:
        for idx, row in view_df.iterrows():
            unique_id = f"{row['StudentCode']}_{idx}"
            with st.expander(f"{row['Name']} (Code: {row['StudentCode']}) [{row['Status']}]"):
                st.info(f"Status: {row['Status']}")

                name = st.text_input("Name", value=row["Name"], key=f"name_{unique_id}")
                phone = st.text_input("Phone", value=row["Phone"], key=f"phone_{unique_id}")
                location = st.text_input("Location", value=row["Location"], key=f"loc_{unique_id}")
                level = st.text_input("Level", value=row["Level"], key=f"level_{unique_id}")

                # Safe defaults for Paid & Balance
                try:
                    paid_default = float(row.get("Paid", 0))
                except Exception:
                    paid_default = 0.0
                paid = st.number_input("Paid", value=paid_default, key=f"paid_{unique_id}")

                try:
                    bal_default = float(row.get("Balance", 0))
                except Exception:
                    bal_default = 0.0
                balance = st.number_input("Balance", value=bal_default, key=f"bal_{unique_id}")

                contract_start = st.text_input(
                    "Contract Start", value=str(row["ContractStart"]), key=f"cs_{unique_id}"
                )
                contract_end = st.text_input(
                    "Contract End", value=str(row["ContractEnd"]), key=f"ce_{unique_id}"
                )
                student_code = st.text_input(
                    "Student Code", value=row["StudentCode"], key=f"code_{unique_id}"
                )

                # Update Button
                if st.button("Update Student", key=f"update_{unique_id}"):
                    df_main.at[idx, "Name"] = name
                    df_main.at[idx, "Phone"] = phone
                    df_main.at[idx, "Location"] = location
                    df_main.at[idx, "Level"] = level
                    df_main.at[idx, "Paid"] = paid
                    df_main.at[idx, "Balance"] = balance
                    df_main.at[idx, "ContractStart"] = contract_start
                    df_main.at[idx, "ContractEnd"] = contract_end
                    df_main.at[idx, "StudentCode"] = student_code
                    df_main.to_csv(student_file, index=False)
                    st.success("Student updated!")
                    st.experimental_rerun()

                # Delete Button
                if st.button("Delete Student", key=f"delete_{unique_id}"):
                    df_main = df_main.drop(idx).reset_index(drop=True)
                    df_main.to_csv(student_file, index=False)
                    st.success("Student deleted!")
                    st.rerun()

                # Generate a new payment receipt
                if st.button("Generate Payment Receipt", key=f"genreceipt_{unique_id}"):
                    pay_amt = st.number_input(
                        "Enter New Payment Amount",
                        min_value=0.0,
                        value=0.0,
                        key=f"payamt_{unique_id}"
                    )
                    pay_date = st.date_input(
                        "Enter Payment Date",
                        value=date.today(),
                        key=f"paydate_{unique_id}"
                    )
                    receipt_pdf = generate_receipt_and_contract_pdf(
                        row, agreement_text, payment_amount=pay_amt, payment_date=pay_date
                    )
                    with open(receipt_pdf, "rb") as f:
                        pdf_bytes = f.read()
                        b64 = base64.b64encode(pdf_bytes).decode()
                        st.markdown(
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{row["Name"].replace(" ", "_")}_receipt.pdf">'
                            "Download PDF Receipt</a>",
                            unsafe_allow_html=True
                        )
                    st.success("Standalone receipt generated!")


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
            new_row = pd.DataFrame([{
                "Name": name,
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
            st.success(f"Added {name} (Code: {student_code})")
            st.rerun()

# ============ EXPENSES TAB ============
with tabs[3]:
    st.title("💵 Expenses and Financial Summary")
    # -- Add Expense Form --
    with st.form("add_expense"):
        exp_type = st.selectbox("Type", ["Bill", "Rent", "Salary", "Other"])
        exp_item = st.text_input("Expense Item / Purpose")
        exp_amount = st.number_input("Amount (GHS)", min_value=0.0, step=1.0)
        exp_date = st.date_input("Date", value=date.today(), key="exp_date")
        if st.form_submit_button("Add Expense") and exp_item and exp_amount > 0:
            new_exp_row = pd.DataFrame([{
                "Type": exp_type,
                "Item": exp_item,
                "Amount": exp_amount,
                "Date": exp_date
            }])
            exp = pd.concat([exp, new_exp_row], ignore_index=True)
            exp.to_csv(expenses_file, index=False)
            st.success(f"Added expense: {exp_type} - {exp_item}")
            st.experimental_rerun()

    st.write("### Expenses List")
    st.dataframe(exp, use_container_width=True)

    # -- Make sure Paid column is numeric --
    df_main["Paid"] = pd.to_numeric(df_main["Paid"], errors="coerce").fillna(0.0)
    # Safely compute total paid
    total_paid = float(df_main["Paid"].sum())

    if not exp.empty:
        exp["Date"] = pd.to_datetime(exp["Date"], errors="coerce")
        exp["Year"] = exp["Date"].dt.year
        exp["Month"] = exp["Date"].dt.strftime("%B %Y")
        monthly_exp = exp.groupby("Month")["Amount"].sum().reset_index()
        st.write("#### Expenses Per Month")
        st.dataframe(monthly_exp)
        yearly_exp = exp.groupby("Year")["Amount"].sum().reset_index()
        st.write("#### Expenses Per Year")
        st.dataframe(yearly_exp)
        total_expenses = float(exp["Amount"].sum())
        net_profit = total_paid - total_expenses
        st.info(
            f"💰 **Total Money Collected:** GHS {total_paid:,.2f} | "
            f"**Total Expenses:** GHS {total_expenses:,.2f} | "
            f"**Net Profit:** GHS {net_profit:,.2f}"
        )
    else:
        st.info(f"💰 **Total Money Collected:** GHS {total_paid:,.2f} | No expenses recorded yet.")

    # Financial summary
    total_paid = df_main["Paid"].sum() if not df_main.empty else 0.0
    if not exp.empty:
        exp["Date"] = pd.to_datetime(exp["Date"], errors='coerce')
        exp["Year"] = exp["Date"].dt.year
        exp["Month"] = exp["Date"].dt.strftime("%B %Y")
        monthly_exp = exp.groupby("Month")["Amount"].sum().reset_index()
        st.write("#### Expenses Per Month")
        st.dataframe(monthly_exp)
        yearly_exp = exp.groupby("Year")["Amount"].sum().reset_index()
        st.write("#### Expenses Per Year")
        st.dataframe(yearly_exp)
        total_expenses = exp["Amount"].sum()
        net_profit = total_paid - total_expenses
        st.info(f"💰 **Total Money Collected:** GHS {total_paid:,.2f} | **Total Expenses:** GHS {total_expenses:,.2f} | **Net Profit:** GHS {net_profit:,.2f}")
    else:
        st.info(f"💰 **Total Money Collected:** GHS {total_paid:,.2f} | No expenses recorded yet.")

# ============ WHATSAPP REMINDERS TAB ============
with tabs[4]:
    st.title("📲 WhatsApp Reminders for Debtors")

    # Fix: Ensure Balance is numeric, treat bad values as zero
    df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0)

    debtors = df_main[(df_main["Balance"] > 0) & (~df_main["Phone"].astype(str).str.contains("@"))]
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

    # Ensure 'Email' column exists and is cleaned in your DataFrame
    if "Email" not in df_main.columns:
        df_main.columns = [c.lower() for c in df_main.columns]
    email_col = "email" if "email" in df_main.columns else "Email"

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

    st.subheader("Student Enrollment Over Time")
    if not df_main.empty and "ContractStart" in df_main.columns:
        df_main["EnrollDate"] = pd.to_datetime(df_main["ContractStart"], errors='coerce')
        enroll_by_month = df_main.groupby(df_main["EnrollDate"].dt.to_period("M")).size().reset_index(name='Count')
        enroll_by_month["EnrollDate"] = enroll_by_month["EnrollDate"].astype(str)
        st.line_chart(enroll_by_month.set_index("EnrollDate")["Count"])

    st.subheader("Export Data")
    st.download_button("Download All Students CSV", df_main.to_csv(index=False), file_name="all_students.csv")
    st.download_button("Download All Expenses CSV", exp.to_csv(index=False), file_name="all_expenses.csv")
