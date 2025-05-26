import streamlit as st
import pandas as pd
import os
from datetime import date, datetime, timedelta
from fpdf import FPDF
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import urllib.parse

st.set_page_config(page_title="Learn Language Education Academy Dashboard", layout="wide")

SCHOOL_NAME    = "Learn Language Education Academy"
SCHOOL_EMAIL   = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE   = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# Securely pull from secrets.toml
school_sendgrid_key = st.secrets["general"].get("SENDGRID_API_KEY")
school_sender_email = st.secrets["general"].get("SENDER_EMAIL", SCHOOL_EMAIL)
def clean_phone(phone):
    s = str(phone)
    if s.endswith(".0"): s = s[:-2]
    return s.replace(" ", "").replace("+", "")

def generate_receipt_and_contract_pdf(
    student_row, agreement_text, payment_amount, payment_date=None,
    first_instalment=1500, course_length=12
):
    if payment_date is None:
        payment_date = date.today()

    # Calculate totals & due date
    paid = float(student_row.get("Paid", 0) or 0)
    balance = float(student_row.get("Balance", 0) or 0)
    total_amount = paid + balance

    try:
        pay_dt = payment_date.date()
    except:
        pay_dt = payment_date
    second_due = pay_dt + timedelta(days=30)

    filled = (
        agreement_text
        .replace("[STUDENT_NAME]", student_row["Name"])
        .replace("[DATE]", str(payment_date))
        .replace("[CLASS]", student_row["Level"])
        .replace("[AMOUNT]", str(total_amount))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(balance))
        .replace("[SECOND_DUE_DATE]", str(second_due))
        .replace("[COURSE_LENGTH]", str(course_length))
    )

    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(0, 10, f"{SCHOOL_NAME} Payment Receipt", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    for label, val in [
        ("Name", student_row["Name"]),
        ("Code", student_row["StudentCode"]),
        ("Paid", f"GHS {paid}"),
        ("Balance", f"GHS {balance}"),
        ("Contract", f"{student_row['ContractStart']} → {student_row['ContractEnd']}"),
        ("Receipt Date", str(payment_date))
    ]:
        pdf.cell(0, 8, f"{label}: {val}", ln=True)
    pdf.ln(6)
    pdf.cell(0, 8, "Thank you for your payment!", ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", size=14)
    pdf.cell(0, 10, f"{SCHOOL_NAME} Student Contract", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    for line in filled.split("\n"):
        pdf.multi_cell(0, 8, line)
    pdf.ln(8)
    pdf.cell(0, 8, "Signed: Felix Asadu", ln=True)

    fname = f"{student_row['Name'].replace(' ','_')}_receipt_contract.pdf"
    pdf.output(fname)
    return fname
student_file  = "students_simple.csv"
expenses_file = "expenses_all.csv"
needed_cols   = [
    "Name","Phone","Location","Level","Paid","Balance",
    "ContractStart","ContractEnd","StudentCode"
]

# Students
if not os.path.exists(student_file):
    pd.DataFrame(columns=needed_cols).to_csv(student_file, index=False)
df_main = pd.read_csv(student_file)

# Normalize columns
mapping = {c: nc for nc in df_main.columns 
           for nc in needed_cols if c.strip().lower()==nc.lower()}
df_main.rename(columns=mapping, inplace=True)
for c in needed_cols:
    if c not in df_main: df_main[c] = ""
df_main = df_main[needed_cols]

# Expenses
if not os.path.exists(expenses_file):
    pd.DataFrame(columns=["Type","Item","Amount","Date"]).to_csv(expenses_file, index=False)
exp = pd.read_csv(expenses_file)
st.title(f"🏫 {SCHOOL_NAME} Dashboard")
st.caption(f"📍 {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

# Quick metrics
today = datetime.today().date()
df_main["Paid"]    = pd.to_numeric(df_main["Paid"], errors="coerce").fillna(0)
df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0)
df_main["_End"]    = pd.to_datetime(df_main["ContractEnd"], errors="coerce").dt.date
df_main["Status"]  = df_main["_End"].apply(
    lambda d: "Completed" if pd.notna(d) and d < today else "Enrolled"
)

c1,c2,c3,c4 = st.columns(4)
c1.metric("👩‍🎓 Enrolled",  int((df_main.Status=="Enrolled").sum()))
c2.metric("✅ Completed", int((df_main.Status=="Completed").sum()))
c3.metric("💰 Collected", f"GHS {df_main.Paid.sum():,.2f}")
c4.metric("⏳ Outstanding", f"GHS {df_main.Balance.sum():,.2f}")

# Income vs expenses
inc = df_main.assign(Month=pd.to_datetime(df_main.ContractStart,errors="coerce").dt.to_period("M"))\
             .groupby("Month")["Paid"].sum()
exp_m = exp.assign(Month=pd.to_datetime(exp.Date,errors="coerce").dt.to_period("M"))\
           .groupby("Month")["Amount"].sum()
df_ie = pd.concat([inc, exp_m], axis=1).fillna(0)
df_ie.index = df_ie.index.astype(str)
st.subheader("Monthly Income vs Expenses")
st.bar_chart(df_ie)
# Notifications
notes=[]
for _,r in df_main[df_main.Balance>0].iterrows():
    msg=urllib.parse.quote(
        f"Dear {r.Name}, you owe GHS {r.Balance}. Code: {r.StudentCode}.")
    url=f"https://wa.me/{clean_phone(r.Phone)}?text={msg}"
    notes.append(f"💰 <b>{r.Name}</b> owes GHS {r.Balance} [WhatsApp]({url})")

for _,r in df_main.iterrows():
    try:
        end=pd.to_datetime(r.ContractEnd).date()
        if today<=end<=today+timedelta(30):
            msg=urllib.parse.quote(
                f"Dear {r.Name}, your contract ends on {r.ContractEnd}.")
            url=f"https://wa.me/{clean_phone(r.Phone)}?text={msg}"
            notes.append(f"⏳ <b>{r.Name}</b> ends {r.ContractEnd} [WhatsApp]({url})")
    except: pass

if notes:
    st.markdown("<br>".join(notes), unsafe_allow_html=True)
else:
    st.info("No notifications.")

# Editable agreement
if "agreement" not in st.session_state:
    st.session_state["agreement"] = """
PAYMENT AGREEMENT

This Payment Agreement is entered into on [DATE] for [CLASS] students of Learn Language Education Academy.

1. Payment Amount: Total [AMOUNT] cedis.
2. Schedule: First [FIRST_INSTALMENT] cedis on [DATE], remaining [SECOND_INSTALMENT] cedis by [SECOND_DUE_DATE].
3. Late: Access revoked; no refund.
4. Refund: None after receipt.
5. Duration: [COURSE_LENGTH] weeks; Goethe supervision if consistent.

Signatures:
[STUDENT_NAME]  Date: [DATE]
Asadu Felix
"""
st.subheader("✏️ Edit Payment Agreement Template")
agreement_text = st.text_area("Agreement", st.session_state.agreement, height=300)
st.session_state.agreement = agreement_text
tabs = st.tabs([
    "📝 Pending Registrations",
    "👩‍🎓 All Students",
    "➕ Add Student",
    "💵 Expenses",
    "📲 WhatsApp Reminders",
    "📄 Contract PDF",
    "📧 Send Email",
    "📊 Analytics & Export"
])

with tabs[0]:
    st.title("📝 Pending Student Registrations")
    sheet_url = "https://docs.google.com/spreadsheets/…/export?format=csv"
    try:
        new = pd.read_csv(sheet_url)
        # normalize…
        st.info("Loaded pending registrations.")
    except Exception as e:
        st.error(f"Cannot load: {e}")
        new = pd.DataFrame()

    for i,row in new.iterrows():
        with st.expander(f"{row.full_name}"):
            code  = st.text_input("Student Code", key=f"pc_{i}")
            start = st.date_input("Start", date.today(), key=f"ps_{i}")
            end   = st.date_input("End",   date.today(), key=f"pe_{i}")
            paid  = st.number_input("Paid", min_value=0.0, key=f"pp_{i}")
            bal   = st.number_input("Balance", min_value=0.0, key=f"pb_{i}")
            pdf_chk = st.checkbox("Attach PDF?", value=True, key=f"pchk_{i}")

            if st.button("Approve & Email", key=f"app_{i}") and code:
                df_main.loc[len(df_main)] = [
                    row.full_name, row.phone_number, row.location,
                    row.class_a1a2_etc, paid, bal, start, end, code
                ]
                df_main.to_csv(student_file, index=False)

                pdf_file = generate_receipt_and_contract_pdf(
                    df_main.iloc[-1], agreement_text,
                    payment_amount=paid, payment_date=start
                )
                attach = None
                if pdf_chk:
                    data = open(pdf_file,"rb").read()
                    enc  = base64.b64encode(data).decode()
                    attach = Attachment(
                        FileContent(enc), FileName(pdf_file),
                        FileType("application/pdf"), Disposition("attachment")
                    )
                if school_sendgrid_key and school_sender_email:
                    mail = Mail(
                        from_email=school_sender_email,
                        to_emails=row.email,
                        subject=f"Welcome to {SCHOOL_NAME}",
                        html_content=f"Dear {row.full_name}, see attached."
                    )
                    if attach: mail.attachment = attach
                    SendGridAPIClient(school_sendgrid_key).send(mail)
                    st.success("Approved & emailed!")
                else:
                    st.warning("Set SendGrid key/sender in secrets.")
with tabs[1]:
    st.title("👩‍🎓 All Students (Search/Filter/Edit)")

    search = st.text_input("🔍 Search by name or code", "")
    sel = st.selectbox("Filter by status", ["All","Enrolled","Completed"])
    df_view = df_main.copy()
    if sel!="All":
        df_view = df_view[df_view.Status==sel]
    if search:
        df_view = df_view[
            df_view.Name.str.contains(search,case=False,na=False)|
            df_view.StudentCode.str.contains(search,case=False,na=False)
        ]

    if df_view.empty:
        st.info("No students match your filter.")
    else:
        for pos,(i,r) in enumerate(df_view.iterrows()):
            uid=f"{r.StudentCode}_{i}_{pos}"
            with st.expander(f"{r.Name} [{r.Status}]"):
                n   = st.text_input("Name", r.Name, key=f"n_{uid}")
                p   = st.text_input("Phone",r.Phone, key=f"p_{uid}")
                pa  = st.number_input("Paid", float(r.Paid), key=f"pa_{uid}")
                ba  = st.number_input("Balance",float(r.Balance),key=f"ba_{uid}")
                if st.button("Update", key=f"u_{uid}"):
                    df_main.at[i,"Name"]   = n
                    df_main.at[i,"Phone"]  = p
                    df_main.at[i,"Paid"]   = pa
                    df_main.at[i,"Balance"]= ba
                    df_main.to_csv(student_file,index=False)
                    st.success("Updated!")
                    st.experimental_rerun()
                if st.button("Delete", key=f"d_{uid}"):
                    df_main.drop(i,inplace=True)
                    df_main.to_csv(student_file,index=False)
                    st.success("Deleted!")
                    st.experimental_rerun()

    # ── Backup & Restore ──
    with st.expander("🔄 Upload CSV Backup", expanded=False):
        su = st.file_uploader("students_simple.csv", type="csv", key="st_bak")
        eu = st.file_uploader("expenses_all.csv",  type="csv", key="ex_bak")
        if su:
            dfn=pd.read_csv(su)
            miss=set(needed_cols)-set(dfn.columns)
            if miss: st.error(f"Missing: {miss}")
            else:
                dfn[needed_cols].to_csv(student_file,index=False)
                st.success("Students restored. Refresh.")
        if eu:
            dfe=pd.read_csv(eu)
            m2={"Type","Item","Amount","Date"}-set(dfe.columns)
            if m2: st.error(f"Missing: {m2}")
            else:
                dfe.to_csv(expenses_file,index=False)
                st.success("Expenses restored. Refresh.")
with tabs[2]:
    st.title("➕ Add Student")
    with st.form("addf"):
        nm = st.text_input("Name"); ph = st.text_input("Phone")
        lv = st.selectbox("Level",["A1","A2","B1","B2","C1","C2"])
        pd_ = st.number_input("Paid",0.0); ba_ = st.number_input("Balance",0.0)
        cs = st.date_input("Start",date.today()); ce = st.date_input("End",date.today())
        cd = st.text_input("Code")
        if st.form_submit_button("Add") and nm and cd:
            df_main.loc[len(df_main)] = [nm,ph,"",lv,pd_,ba_,cs,ce,cd]
            df_main.to_csv(student_file,index=False)
            st.success("Added!"); st.experimental_rerun()

with tabs[3]:
    st.title("💵 Expenses")
    with st.form("expf"):
        t = st.selectbox("Type",["Bill","Rent","Salary","Other"])
        it= st.text_input("Item"); am=st.number_input("Amount",0.0)
        dt= st.date_input("Date", date.today())
        if st.form_submit_button("Add"):
            exp.loc[len(exp)] = [t,it,am,dt]
            exp.to_csv(expenses_file,index=False)
            st.success("Expense logged!"); st.experimental_rerun()
    st.dataframe(exp, use_container_width=True)

with tabs[4]:
    st.title("📲 WhatsApp Reminders")
    for _,r in df_main[df_main.Balance>0].iterrows():
        msg=urllib.parse.quote(f"Hi {r.Name}, you owe GHS {r.Balance}")
        url=f"https://wa.me/{clean_phone(r.Phone)}?text={msg}"
        st.markdown(f"**{r.Name}** owes GHS {r.Balance} → [WhatsApp]({url})")
with tabs[5]:
    st.title("📄 Contract PDF")
    sel = st.selectbox("Pick Student", df_main.Name.tolist())
    if st.button("Generate"):
        row = df_main[df_main.Name==sel].iloc[0]
        pdf = generate_receipt_and_contract_pdf(
            row, agreement_text, payment_amount=row.Paid, payment_date=row.ContractStart
        )
        b64 = base64.b64encode(open(pdf,"rb").read()).decode()
        st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="{sel}.pdf">Download</a>', unsafe_allow_html=True)

with tabs[6]:
    st.title("📧 Send Email")
    mode = st.radio("To", ["Individual","All"])
    if mode=="Individual":
        pick = st.selectbox("Student", df_main.Name + " (" + df_main.Phone + ")")
        recp = df_main[df_main.Name + " (" + df_main.Phone + ")"==pick].Phone.values[0]
        recps=[recp]
    else:
        recps = list(df_main.Phone)
    subj = st.text_input("Subject","")
    body = st.text_area("Message","")
    attach_file = st.file_uploader("Attach a file", type=["pdf","png","jpg","docx"])
    if st.button("Send"):
        att=None
        if attach_file:
            d=attach_file.read(); e=base64.b64encode(d).decode()
            att = Attachment(FileContent(e),FileName(attach_file.name),
                             FileType(attach_file.type),Disposition("attachment"))
        for to in recps:
            m=Mail(from_email=school_sender_email, to_emails=to,
                   subject=subj, html_content=body.replace("\n","<br>"))
            if att: m.attachment=att
            SendGridAPIClient(school_sendgrid_key).send(m)
        st.success("Email(s) sent!")

with tabs[7]:
    st.title("📊 Export")
    st.download_button("Students CSV", df_main.to_csv(index=False), file_name="all_students.csv")
    st.download_button("Expenses CSV", exp.to_csv(index=False),  file_name="all_expenses.csv")
