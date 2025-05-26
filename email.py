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

# School info & email config
SCHOOL_NAME        = "Learn Language Education Academy"
SCHOOL_EMAIL       = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE     = "www.learngermanghana.com"
SCHOOL_PHONE       = "233205706589"
SCHOOL_ADDRESS     = "Awoshie, Accra, Ghana"
school_sendgrid_key   = st.secrets["general"].get("SENDGRID_API_KEY")
school_sender_email   = st.secrets["general"].get("SENDER_EMAIL", SCHOOL_EMAIL)
def clean_phone(phone):
    s = str(phone)
    return s[:-2] if s.endswith(".0") else s.replace(" ", "").replace("+", "")

def generate_receipt_and_contract_pdf(
    student_row, agreement_text, payment_amount, payment_date=None,
    first_instalment=1500, course_length=12
):
    if payment_date is None:
        payment_date = date.today()
    paid    = float(student_row.get("Paid", 0) or 0)
    balance = float(student_row.get("Balance", 0) or 0)
    total   = paid + balance
    try:
        d0 = payment_date.date() if hasattr(payment_date, "date") else payment_date
        due = d0 + timedelta(days=30)
    except:
        due = ""
    filled = (agreement_text
        .replace("[STUDENT_NAME]", student_row["Name"])
        .replace("[DATE]", str(payment_date))
        .replace("[CLASS]", student_row["Level"])
        .replace("[AMOUNT]", str(total))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(balance))
        .replace("[SECOND_DUE_DATE]", str(due))
        .replace("[COURSE_LENGTH]", str(course_length))
    )
    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"{SCHOOL_NAME} Payment Receipt", ln=True, align="C")
    pdf.set_font("Arial", size=12); pdf.ln(5)
    for label, val in [
        ("Name", student_row["Name"]), ("Code", student_row["StudentCode"]),
        ("Phone", student_row["Phone"]), ("Level", student_row["Level"]),
        ("Paid", f"GHS {paid}"), ("Due", f"GHS {balance}"),
        ("Start", student_row["ContractStart"]), ("End", student_row["ContractEnd"])
    ]:
        pdf.cell(0, 8, f"{label}: {val}", ln=True)
    pdf.ln(8)
    pdf.cell(0, 8, "Thank you for your payment!", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Student Contract", ln=True, align="C")
    pdf.set_font("Arial", size=12); pdf.ln(5)
    for line in filled.split("\n"):
        pdf.multi_cell(0, 8, line)
    pdf_name = f"{student_row['Name'].replace(' ','_')}_receipt_contract.pdf"
    pdf.output(pdf_name)
    return pdf_name
# Files & columns
student_file  = "students_simple.csv"
expenses_file = "expenses_all.csv"
needed_cols   = [
    "Name","Phone","Location","Level","Paid","Balance",
    "ContractStart","ContractEnd","StudentCode"
]

# Ensure students CSV exists
if not os.path.exists(student_file):
    pd.DataFrame(columns=needed_cols).to_csv(student_file, index=False)
df_main = pd.read_csv(student_file)

# Normalize & rename columns case-insensitively
col_map = {col: need for col in df_main.columns for need in needed_cols
           if col.strip().lower()==need.lower()}
df_main.rename(columns=col_map, inplace=True)

# Add any missing columns & enforce order
for c in needed_cols:
    if c not in df_main: df_main[c] = ""
df_main = df_main[needed_cols]

# Expenses CSV
if not os.path.exists(expenses_file):
    pd.DataFrame(columns=["Type","Item","Amount","Date"]).to_csv(expenses_file, index=False)
exp = pd.read_csv(expenses_file)
sheet_url = (
    "https://docs.google.com/spreadsheets/d/"
    "1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"
)

st.title(f"🏫 {SCHOOL_NAME} Dashboard")
st.caption(f"📍 {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

# KPIs
today = datetime.today().date()
df_main["Balance"] = pd.to_numeric(df_main["Balance"], errors="coerce").fillna(0)
df_main["Paid"]    = pd.to_numeric(df_main["Paid"],    errors="coerce").fillna(0)
df_main["Status"]  = df_main["ContractEnd"].apply(
    lambda x: "Completed" if pd.to_datetime(x, errors="coerce").date() < today else "Enrolled"
)
c1,c2,c3,c4 = st.columns(4)
c1.metric("Enrolled",   int((df_main.Status=="Enrolled").sum()))
c2.metric("Completed",  int((df_main.Status=="Completed").sum()))
c3.metric("Collected", f"GHS {df_main.Paid.sum():,.2f}")
c4.metric("Outstanding",f"GHS {df_main.Balance.sum():,.2f}")

# Monthly income vs expenses
st.subheader("Monthly Income vs Expenses")
inc = (
    df_main.assign(
        Month=pd.to_datetime(df_main.ContractStart,errors="coerce")
                .dt.to_period("M")
    )
    .groupby("Month")["Paid"].sum()
)
exp_m = (
    exp.assign(
        Month=pd.to_datetime(exp.Date, errors="coerce").dt.to_period("M")
    )
    .groupby("Month")["Amount"].sum()
)
me = pd.concat([inc.rename("Income"), exp_m.rename("Expenses")], axis=1).fillna(0)
me.index = me.index.astype(str)
st.bar_chart(me)
# Notifications
notes = []
for _, r in df_main[df_main.Balance>0].iterrows():
    msg = urllib.parse.quote(
        f"Dear {r.Name}, GHS {r.Balance} due. Code {r.StudentCode}."
    )
    notes.append(f"💰 {r.Name}: [WA](https://wa.me/{clean_phone(r.Phone)}?text={msg})")
soon = today+timedelta(days=30)
for _, r in df_main.iterrows():
    d = pd.to_datetime(r.ContractEnd, errors="coerce").date()
    if today <= d <= soon:
        notes.append(f"⏳ {r.Name} ends {d}")
    if d < today:
        notes.append(f"❗ {r.Name} expired {d}")
if notes:
    st.warning("\n".join(notes))
else:
    st.info("No alerts.")

# Agreement editor
if "agreement_template" not in st.session_state:
    st.session_state.agreement_template = """\
PAYMENT AGREEMENT

Date: [DATE]
Class: [CLASS]
Total: [AMOUNT]
1. First instalment: [FIRST_INSTALMENT]
2. Second instalment ([SECOND_DUE_DATE]): [SECOND_INSTALMENT]
Duration: [COURSE_LENGTH] weeks
..."""
st.subheader("Edit Payment Agreement")
agreement_text = st.text_area(
    "Template", st.session_state.agreement_template, height=300
)
st.session_state.agreement_template = agreement_text
tabs = st.tabs([
    "📝 Pending Registrations",
    "👩‍🎓 All Students",
    "➕ Add Student",
    "💵 Expenses",
    "📲 WhatsApp Reminders",
    "📄 Generate Contract PDF",
    "📧 Send Email",
    "📊 Analytics & Export",
])

with tabs[0]:
    st.title("📝 Pending Student Registrations")
    try:
        new = pd.read_csv(sheet_url)
        def clean_col(c):
            return (c.strip().lower()
                       .replace(" ","_")
                       .replace("(", "").replace(")","")
                       .replace(",","").replace("-",""))
        new.columns = [clean_col(c) for c in new.columns]
    except Exception as e:
        st.error(f"Load failed: {e}")
        new = pd.DataFrame()
    if new.empty:
        st.info("No pending.")
    else:
        for i,r in new.iterrows():
            with st.expander(f"{r.full_name}"):
                st.write(r.to_dict())
                code = st.text_input("Assign Code", key=f"code_{i}")
                paid = st.number_input("Paid", min_value=0.0, key=f"paid_{i}")
                bal  = st.number_input("Balance", min_value=0.0, key=f"bal_{i}")
                if st.button("Approve", key=f"app_{i}") and code:
                    row = {
                        "Name": r.full_name, "Phone": r.phone_number,
                        "Location": r.location, "Level": r.class_a1a2_etc,
                        "Paid": paid, "Balance": bal,
                        "ContractStart": date.today(),
                        "ContractEnd": date.today()+timedelta(weeks=12),
                        "StudentCode": code
                    }
                    df_main = pd.concat([df_main, pd.DataFrame([row])], ignore_index=True)
                    df_main.to_csv(student_file, index=False)
                    st.success("Approved & added")
with tabs[1]:
    st.title("👩‍🎓 All Students")
    search = st.text_input("🔍 Search name or code")
    today  = datetime.today().date()
    df_main["_E"] = pd.to_datetime(df_main.ContractEnd, errors="coerce").dt.date
    df_main["Status"] = df_main["_E"].apply(
        lambda d: "Completed" if pd.notna(d) and d<today else "Enrolled"
    )
    sel = st.selectbox("Filter", ["All","Enrolled","Completed"])
    dfv = df_main if sel=="All" else df_main[df_main.Status==sel]
    if search:
        dfv = dfv[dfv.Name.str.contains(search,case=False,na=False)
                  | dfv.StudentCode.str.contains(search,case=False,na=False)]
    if dfv.empty:
        st.info("No match.")
    else:
        for pos,(i,r) in enumerate(dfv.iterrows()):
            uid = f"{r.StudentCode}_{i}_{pos}"
            with st.expander(f"{r.Name} [{r.Status}]"):
                name  = st.text_input("Name", r.Name, key=f"name_{uid}")
                phone = st.text_input("Phone",r.Phone,key=f"phone_{uid}")
                paid  = st.number_input("Paid",float(r.Paid),key=f"paid_{uid}")
                bal   = st.number_input("Balance",float(r.Balance),key=f"bal_{uid}")
                if st.button("Update", key=f"upd_{uid}"):
                    df_main.at[i,"Name"]=name
                    df_main.at[i,"Phone"]=phone
                    df_main.at[i,"Paid"]=paid
                    df_main.at[i,"Balance"]=bal
                    df_main.to_csv(student_file,index=False)
                    st.success("Saved")
                    st.experimental_rerun()
                if st.button("Delete",key=f"del_{uid}"):
                    df_main.drop(i,inplace=True)
                    df_main.to_csv(student_file,index=False)
                    st.success("Deleted")
                    st.experimental_rerun()
with tabs[2]:
    st.title("➕ Add Student")
    with st.form("f_add"):
        nm   = st.text_input("Name")
        em   = st.text_input("Email")
        ph   = st.text_input("Phone")
        lvl  = st.selectbox("Level", ["A1","A2","B1","B2","C1","C2"])
        pd   = st.number_input("Paid",min_value=0.0)
        bl   = st.number_input("Balance",min_value=0.0)
        cs   = st.date_input("Start", value=date.today())
        ce   = st.date_input("End",   value=date.today()+timedelta(weeks=12))
        cd   = st.text_input("Code")
        if st.form_submit_button("Add") and nm and cd:
            df_main = pd.concat([df_main,pd.DataFrame([{
                "Name":nm,"Phone":ph,"Location":"",
                "Level":lvl,"Paid":pd,"Balance":bl,
                "ContractStart":cs,"ContractEnd":ce,
                "StudentCode":cd
            }])],ignore_index=True)
            df_main.to_csv(student_file,index=False)
            st.success("Added")
            st.experimental_rerun()

with tabs[3]:
    st.title("💵 Expenses")
    with st.form("f_exp"):
        T = st.selectbox("Type",["Bill","Rent","Salary","Other"])
        I = st.text_input("Item")
        A = st.number_input("Amount",min_value=0.0)
        D = st.date_input("Date",value=date.today())
        if st.form_submit_button("Add") and I:
            exp = pd.concat([exp,pd.DataFrame([{"Type":T,"Item":I,"Amount":A,"Date":D}])],ignore_index=True)
            exp.to_csv(expenses_file,index=False)
            st.success("Added")
            st.experimental_rerun()
    st.dataframe(exp)

with tabs[4]:
    st.title("📲 WhatsApp Reminders")
    debt = df_main[df_main.Balance>0]
    if debt.empty:
        st.info("No debtors")
    else:
        for _,r in debt.iterrows():
            msg = urllib.parse.quote(
                f"Dear {r.Name}, you owe GHS {r.Balance}"
            )
            url = f"https://wa.me/{clean_phone(r.Phone)}?text={msg}"
            st.markdown(f"[{r.Name} → Remind]({url})")
with tabs[5]:
    st.title("📄 Generate Contract PDF")
    if not df_main.empty:
        sel = st.selectbox("Pick student", df_main.Name.unique())
        if st.button("Generate"):
            r = df_main[df_main.Name==sel].iloc[0]
            fn = generate_receipt_and_contract_pdf(r, agreement_text, payment_amount=r.Paid, payment_date=r.ContractStart)
            b64=base64.b64encode(open(fn,"rb").read()).decode()
            st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="{fn}">Download</a>', unsafe_allow_html=True)

with tabs[6]:
    st.title("📧 Send Email")

    # Build list of (display, email) pairs
    email_list = [
        (row["Name"], row["Email"])
        for _, row in df_main.iterrows()
        if isinstance(row.get("Email", ""), str) and "@" in row["Email"]
    ]

    mode = st.radio("Send to", ["Individual", "All"])
    recipients = []

    if mode == "Individual":
        if email_list:
            choices = [f"{name} <{email}>" for name, email in email_list]
            sel = st.selectbox("Pick a student", choices, index=0)
            # Only split if sel is non‐empty
            if sel:
                # extract the email between <> 
                recipients = [ sel.split("<",1)[1].rstrip(">") ]
        else:
            st.info("No student emails on file.")
    else:
        # all students
        recipients = [email for _, email in email_list]

    subject = st.text_input("Subject", value="Information from Learn Language Education Academy")
    body    = st.text_area("Body (HTML allowed)", height=150, value="Dear Student,\n\n")
    attach  = st.file_uploader("Attach a file (optional)", type=["pdf","jpg","png","docx"])

    if st.button("Send"):
        if not recipients:
            st.error("No recipients selected.")
        else:
            # build attachment if any
            attachment = None
            if attach:
                data = attach.read()
                enc  = base64.b64encode(data).decode()
                attachment = Attachment(
                    FileContent(enc),
                    FileName(attach.name),
                    FileType(attach.type),
                    Disposition("attachment")
                )

            sent, failed = 0, []
            for to_addr in recipients:
                msg = Mail(
                    from_email=school_sender_email,
                    to_emails=to_addr,
                    subject=subject,
                    html_content=body.replace("\n","<br>")
                )
                if attachment:
                    msg.attachment = attachment

                try:
                    SendGridAPIClient(school_sendgrid_key).send(msg)
                    sent += 1
                except Exception:
                    failed.append(to_addr)

            st.success(f"Sent: {sent}")
            if failed:
                st.warning(f"Failed: {', '.join(failed)}")

with tabs[7]:
    st.title("📊 Analytics & Export")
    st.subheader("Enrollments Over Time")
    df_main["Mon"]=pd.to_datetime(df_main.ContractStart,errors="coerce").dt.to_period("M")
    c = df_main.groupby("Mon").size().rename("Count")
    c.index=c.index.astype(str)
    st.line_chart(c)
    st.download_button("Download Students CSV", df_main.to_csv(index=False), file_name="all_students.csv")
    st.download_button("Download Expenses CSV", exp.to_csv(index=False), file_name="all_expenses.csv")
