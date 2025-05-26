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
SCHOOL_NAME    = "Learn Language Education Academy"
SCHOOL_EMAIL   = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE   = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# === SENDGRID / EMAIL CONFIG ===
school_sendgrid_key   = st.secrets["general"].get("SENDGRID_API_KEY")
school_sender_email   = st.secrets["general"].get("SENDER_EMAIL", SCHOOL_EMAIL)

# === UTILITIES ===
def clean_phone(phone):
    s = str(phone)
    if s.endswith(".0"):
        s = s[:-2]
    return s.replace(" ", "").replace("+", "")

def generate_receipt_and_contract_pdf(student_row, agreement_text,
                                      payment_amount, payment_date=None,
                                      first_instalment=1500, course_length=12):
    if payment_date is None:
        payment_date = date.today()
    # compute paid / balance / total
    try:
        paid    = float(student_row["Paid"])
        bal     = float(student_row["Balance"])
        total   = paid + bal
    except:
        paid, bal, total = 0.0, 0.0, 0.0
    # due date = 30 days after
    try:
        pdobj = payment_date.date() if hasattr(payment_date, "date") else payment_date
        due2  = pdobj + timedelta(days=30)
    except:
        due2 = ""
    filled = (agreement_text
        .replace("[STUDENT_NAME]", student_row["Name"])
        .replace("[DATE]", str(payment_date))
        .replace("[CLASS]", student_row["Level"])
        .replace("[AMOUNT]", str(total))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(bal))
        .replace("[SECOND_DUE_DATE]", str(due2))
        .replace("[COURSE_LENGTH]", str(course_length))
    )
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, f"{SCHOOL_NAME} Payment Receipt", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    for label, val in [
        ("School", SCHOOL_NAME),
        ("Location", SCHOOL_ADDRESS),
        ("Phone", SCHOOL_PHONE),
        ("Email", SCHOOL_EMAIL),
        ("Website", SCHOOL_WEBSITE),
        ("Name", student_row["Name"]),
        ("Student Code", student_row["StudentCode"]),
        ("Phone", student_row["Phone"]),
        ("Level", student_row["Level"]),
        ("Amount Paid", f"GHS {paid}"),
        ("Balance Due", f"GHS {bal}"),
        ("Contract Start", student_row["ContractStart"]),
        ("Contract End", student_row["ContractEnd"]),
        ("Receipt Date", payment_date),
    ]:
        pdf.cell(0, 10, f"{label}: {val}", ln=True)
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
    fname = f"{student_row['Name'].replace(' ', '_')}_receipt_and_contract.pdf"
    pdf.output(fname)
    return fname

# === FILES & DATABASE SETUP ===
student_file  = "students_simple.csv"
expenses_file = "expenses_all.csv"
needed_cols   = ["Name","Phone","Location","Level","Paid","Balance",
                 "ContractStart","ContractEnd","StudentCode"]

# create + load students
if not os.path.exists(student_file):
    pd.DataFrame(columns=needed_cols).to_csv(student_file, index=False)
df_main = pd.read_csv(student_file)
# normalize any lowercase/pascal mismatches on Email later
# ensure all needed columns exist
for c in needed_cols:
    if c not in df_main.columns:
        df_main[c] = ""
df_main = df_main[needed_cols]

# create + load expenses
if not os.path.exists(expenses_file):
    pd.DataFrame(columns=["Type","Item","Amount","Date"]).to_csv(expenses_file, index=False)
exp = pd.read_csv(expenses_file)

# === GOOGLE SHEET URL (if used) ===
sheet_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"

# === PAGE HEADER ===
st.title(f"🏫 {SCHOOL_NAME} Dashboard")
st.caption(f"📍 {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

# === AGREEMENT TEMPLATE EDITOR ===
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
"""
st.subheader("Edit Payment Agreement Template")
agreement_text = st.text_area("Agreement Template", height=300,
                              value=st.session_state["agreement_template"])
st.session_state["agreement_template"] = agreement_text

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

# ============ 1. PENDING REGISTRATIONS ============
with tabs[0]:
    st.title("📝 Pending Student Registrations (Approve & Auto-Email)")
    try:
        new_students = pd.read_csv(sheet_url)
        def clean_col(c):
            return (c.strip().lower()
                      .replace("(", "").replace(")","")
                      .replace(",", "").replace("-","")
                      .replace(" ","_"))
        new_students.columns = [clean_col(c) for c in new_students.columns]
        st.info(f"Columns: {', '.join(new_students.columns)}")
    except Exception as e:
        st.error(f"Could not load registrations: {e}")
        new_students = pd.DataFrame()

    if not new_students.empty:
        for i, row in new_students.iterrows():
            fn  = row.get("full_name","")
            ph  = row.get("phone_number","")
            em  = row.get("email","")
            lvl = row.get("class_a1a2_etc","")
            loc = row.get("location","")
            with st.expander(f"{fn} ({ph})"):
                st.write(f"**Email:** {em}")
                code   = st.text_input("Assign Student Code", key=f"code_{i}")
                cstart = st.date_input("Contract Start", date.today(), key=f"cs_{i}")
                cend   = st.date_input("Contract End",   date.today(), key=f"ce_{i}")
                paid   = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0, key=f"pd_{i}")
                bal    = st.number_input("Balance Due (GHS)",   min_value=0.0, step=1.0, key=f"bl_{i}")
                firsti = st.number_input("First Instalment (GHS)", min_value=0.0, value=1500.0, key=f"fi_{i}")
                length = st.number_input("Course Length (weeks)", min_value=1, value=12, key=f"le_{i}")
                attach = st.checkbox("Attach PDF?", value=True, key=f"at_{i}")

                if st.button("Approve & Add", key=f"ap_{i}") and code:
                    new = pd.DataFrame([{
                        "Name": fn, "Phone": ph, "Location": loc,
                        "Level": lvl, "Paid": paid, "Balance": bal,
                        "ContractStart": cstart, "ContractEnd": cend,
                        "StudentCode": code
                    }])
                    df_main = pd.concat([df_main, new], ignore_index=True)
                    df_main.to_csv(student_file, index=False)

                    pdf_file = generate_receipt_and_contract_pdf(
                        new.iloc[0], agreement_text,
                        payment_amount=paid,
                        payment_date=cstart,
                        first_instalment=firsti,
                        course_length=length
                    )
                    attachment = None
                    if attach:
                        with open(pdf_file, "rb") as f:
                            b = f.read()
                        enc = base64.b64encode(b).decode()
                        attachment = Attachment(
                            FileContent(enc),
                            FileName(pdf_file),
                            FileType("application/pdf"),
                            Disposition("attachment")
                        )

                    if school_sendgrid_key and school_sender_email:
                        subject = f"Welcome to {SCHOOL_NAME}"
                        body    = (
                            f"Dear {fn},<br><br>"
                            f"Welcome! Your contract and receipt are attached.<br>"
                            f"Code: {code}<br>"
                            f"Paid: GHS {paid}<br>"
                            f"Balance: GHS {bal}<br><br>"
                            f"– {SCHOOL_NAME}"
                        )
                        try:
                            if em and "@" in em:
                                msg = Mail(
                                    from_email=school_sender_email,
                                    to_emails=em,
                                    subject=subject,
                                    html_content=body
                                )
                                if attachment:
                                    msg.attachment = attachment
                                SendGridAPIClient(school_sendgrid_key).send(msg)
                                st.success(f"✔️ Emailed {em}")
                            else:
                                st.warning("No valid email provided; skipped email.")
                        except Exception as e:
                            st.error(f"Email error: {e}")
                    else:
                        st.warning("Set your SendGrid key in Streamlit secrets.")

# ============ 2. ALL STUDENTS ============
with tabs[1]:
    st.title("👩‍🎓 All Students (Search · Filter · Edit)")

    # prepare status + filtering
    today = datetime.today().date()
    df_main["_EndDate"] = pd.to_datetime(df_main["ContractEnd"], errors="coerce").dt.date
    df_main["Status"]   = df_main["_EndDate"].apply(
        lambda d: "Completed" if pd.notna(d) and d < today else "Enrolled"
    )

    search   = st.text_input("🔍 Search by name or code", "")
    sel_stat = st.selectbox("Filter by status", ["All","Enrolled","Completed"])
    view_df  = df_main.copy()
    if sel_stat != "All":
        view_df = view_df[view_df["Status"]==sel_stat]
    if search:
        mask = (
            view_df["Name"].str.contains(search, case=False, na=False)
            | view_df["StudentCode"].str.contains(search, case=False, na=False)
        )
        view_df = view_df[mask]

    if view_df.empty:
        st.info("No students match your filter.")
    else:
        for pos, (idx, row) in enumerate(view_df.iterrows()):
            uid = f"{row['StudentCode']}_{idx}_{pos}"
            with st.expander(f"{row['Name']} ({row['StudentCode']}) [{row['Status']}]"):
                name  = st.text_input("Name", row["Name"], key=f"name_{uid}")
                phone = st.text_input("Phone", row["Phone"], key=f"phone_{uid}")
                loc   = st.text_input("Location", row["Location"], key=f"loc_{uid}")
                lvl   = st.text_input("Level", row["Level"], key=f"level_{uid}")
                paid  = st.number_input("Paid", float(row["Paid"]), key=f"paid_{uid}")
                bal   = st.number_input("Balance", float(row["Balance"]), key=f"bal_{uid}")
                cs    = st.text_input("Contract Start", str(row["ContractStart"]), key=f"cs_{uid}")
                ce    = st.text_input("Contract End",   str(row["ContractEnd"]),   key=f"ce_{uid}")
                codei = st.text_input("Student Code", row["StudentCode"], key=f"code_{uid}")

                if st.button("Update", key=f"upd_{uid}"):
                    for c,v in [("Name",name),("Phone",phone),("Location",loc),
                                ("Level",lvl),("Paid",paid),("Balance",bal),
                                ("ContractStart",cs),("ContractEnd",ce),
                                ("StudentCode",codei)]:
                        df_main.at[idx,c] = v
                    df_main.to_csv(student_file, index=False)
                    st.success("✔️ Updated")
                    st.experimental_rerun()

                if st.button("Delete", key=f"del_{uid}"):
                    df_main.drop(idx, inplace=True)
                    df_main.to_csv(student_file, index=False)
                    st.success("🗑 Deleted")
                    st.experimental_rerun()

                if st.button("Generate Receipt", key=f"rcpt_{uid}"):
                    amt = st.number_input("Payment amount", min_value=0.0,
                                          value=float(row["Paid"]), key=f"amt_{uid}")
                    dt  = st.date_input("Payment date", value=date.today(), key=f"dt_{uid}")
                    pdf = generate_receipt_and_contract_pdf(
                        row, agreement_text, payment_amount=amt, payment_date=dt
                    )
                    with open(pdf, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    st.markdown(
                        f'<a href="data:application/pdf;base64,{b64}" '
                        f'download="{row["Name"].replace(" ","_")}_receipt.pdf">'
                        "Download Receipt</a>",
                        unsafe_allow_html=True
                    )
                    st.success("📄 Ready")

# ============ 3. ADD STUDENT ============
with tabs[2]:
    st.title("➕ Add Student")
    with st.form("add_student"):
        n   = st.text_input("Name")
        p   = st.text_input("Phone Number")
        loc = st.text_input("Location")
        lvl = st.selectbox("Class/Level", ["A1","A2","B1","B2","C1","C2"])
        pd_ = st.number_input("Amount Paid", min_value=0.0, step=1.0)
        bl = st.number_input("Balance Due",   min_value=0.0, step=1.0)
        cs = st.date_input("Contract Start", value=date.today())
        ce = st.date_input("Contract End",   value=date.today())
        cd = st.text_input("Student Code (unique)")
        if st.form_submit_button("Add") and n and p and cd:
            new = pd.DataFrame([{
                "Name":n,"Phone":p,"Location":loc,"Level":lvl,
                "Paid":pd_,"Balance":bl,
                "ContractStart":cs,"ContractEnd":ce,
                "StudentCode":cd
            }])
            df_main = pd.concat([df_main,new], ignore_index=True)
            df_main.to_csv(student_file, index=False)
            st.success(f"Added {n}")
            st.experimental_rerun()

# ============ 4. EXPENSES ============
with tabs[3]:
    st.title("💵 Expenses & Summary")
    with st.form("add_exp"):
        t  = st.selectbox("Type", ["Bill","Rent","Salary","Other"])
        it = st.text_input("Item / Purpose")
        am = st.number_input("Amount", min_value=0.0, step=1.0)
        dt= st.date_input("Date", value=date.today())
        if st.form_submit_button("Add Expense") and it and am>0:
            new = pd.DataFrame([{"Type":t,"Item":it,"Amount":am,"Date":dt}])
            exp = pd.concat([exp,new], ignore_index=True)
            exp.to_csv(expenses_file, index=False)
            st.success("Added expense")
            st.experimental_rerun()

    st.subheader("All Expenses")
    st.dataframe(exp, use_container_width=True)

# ============ 5. WHATSAPP REMINDERS ============
with tabs[4]:
    st.title("📲 WhatsApp Reminders")
    df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0)
    debtors = df_main[(df_main["Balance"]>0)
               & (~df_main["Phone"].astype(str).str.contains("@"))]
    if debtors.empty:
        st.info("No debtors.")
    else:
        for _,r in debtors.iterrows():
            msg = (f"Dear {r['Name']}, your balance GHS{r['Balance']}. "
                   f"Please pay. Code: {r['StudentCode']}.")
            url = f"https://wa.me/{clean_phone(r['Phone'])}?text={urllib.parse.quote(msg)}"
            st.markdown(f"**{r['Name']}** (GHS {r['Balance']}) [Remind](<{url}>)")

# ============ 6. PDF CONTRACT ============
with tabs[5]:
    st.title("📄 Generate Contract PDF")
    if not df_main.empty:
        sel = st.selectbox("Select Student", df_main["Name"].tolist())
        if st.button("Generate"):
            rr = df_main[df_main["Name"]==sel].iloc[0]
            pdf = generate_receipt_and_contract_pdf(
                rr, agreement_text,
                payment_amount=rr["Paid"],
                payment_date=rr["ContractStart"]
            )
            with open(pdf,"rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="{sel}.pdf">Download</a>', unsafe_allow_html=True)

# ============ 7. SEND EMAIL ============
with tabs[6]:
    st.title("📧 Send Email to Student(s)")

    # normalize Email column
    if "Email" not in df_main.columns:
        if "email" in df_main.columns:
            df_main = df_main.rename(columns={"email":"Email"})
        else:
            df_main["Email"] = ""

    valid = df_main[df_main["Email"].str.contains("@", na=False)]
    if valid.empty:
        st.warning("No valid student emails found.")
    else:
        opts = valid.apply(lambda r: f"{r['Name']} ({r['Email']})", axis=1).tolist()
        mp   = {opt:valid.iloc[i]["Email"] for i,opt in enumerate(opts)}

        mode = st.radio("Send to", ["Individual student","All students"])
        if mode=="Individual student":
            pick = st.selectbox("Select student", opts)
            recs = [ mp[pick] ] if pick else []
        else:
            recs = list(mp.values())

        subject = st.text_input("Subject", f"Hello from {SCHOOL_NAME}")
        body    = st.text_area("Body (HTML ok)", value="Dear Student,\n\n...")
        up      = st.file_uploader("Attach file (optional)", type=["pdf","docx","jpg","png"])

        if st.button("Send Email"):
            sent,failed=0,[]
            attach=None
            if up:
                d = up.read(); enc=base64.b64encode(d).decode()
                attach = Attachment(
                    FileContent(enc),
                    FileName(up.name),
                    FileType(up.type),
                    Disposition("attachment")
                )
            for to in recs:
                try:
                    msg = Mail(
                        from_email=school_sender_email,
                        to_emails=to,
                        subject=subject,
                        html_content=body.replace("\n","<br>")
                    )
                    if attach: msg.attachment=attach
                    SendGridAPIClient(school_sendgrid_key).send(msg)
                    sent+=1
                except:
                    failed.append(to)
            st.success(f"Sent to {sent} student(s)")
            if failed:
                st.error(f"Failed: {', '.join(failed)}")

# ============ 8. ANALYTICS & EXPORT ============
with tabs[7]:
    st.title("📊 Analytics & Export")
    if not df_main.empty:
        df_main["Enroll"] = pd.to_datetime(df_main["ContractStart"],errors="coerce").dt.to_period("M")
        bym = df_main.groupby("Enroll").size().rename("Count")
        st.line_chart(bym)

    st.download_button("Download students CSV", df_main.to_csv(index=False), file_name="all_students.csv")
    st.download_button("Download expenses CSV", exp.to_csv(index=False), file_name="all_expenses.csv")
