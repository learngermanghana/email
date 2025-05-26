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

# === EMAIL CONFIG ===
school_sendgrid_key   = st.secrets["general"].get("SENDGRID_API_KEY")
school_sender_email   = st.secrets["general"].get("SENDER_EMAIL", SCHOOL_EMAIL)

# === HELPERS ===
def clean_phone(phone):
    s = str(phone)
    if s.endswith('.0'):
        s = s[:-2]
    return s.replace(" ", "").replace("+", "")

def generate_receipt_and_contract_pdf(
    student_row, agreement_text, payment_amount, payment_date=None,
    first_instalment=1500, course_length=12
):
    if payment_date is None:
        payment_date = date.today()
    # compute amounts
    try:
        paid    = float(student_row["Paid"])
        balance = float(student_row["Balance"])
        total   = paid + balance
    except:
        paid = balance = total = 0.0
    # due date 1 month later
    try:
        pd_obj = payment_date.date() if hasattr(payment_date, "date") else payment_date
        due2 = pd_obj + timedelta(days=30)
    except:
        due2 = ""
    # fill template
    filled = (
        agreement_text
        .replace("[STUDENT_NAME]", student_row["Name"])
        .replace("[DATE]", str(payment_date))
        .replace("[CLASS]", student_row["Level"])
        .replace("[AMOUNT]", str(total))
        .replace("[FIRST_INSTALMENT]", str(first_instalment))
        .replace("[SECOND_INSTALMENT]", str(balance))
        .replace("[SECOND_DUE_DATE]", str(due2))
        .replace("[COURSE_LENGTH]", str(course_length))
    )
    pdf = FPDF()
    pdf.add_page()
    # Receipt header
    pdf.set_font("Arial", size=14)
    pdf.cell(200,10,f"{SCHOOL_NAME} Payment Receipt",ln=True,align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(5)
    for label, val in [
        ("School", SCHOOL_NAME),
        ("Address", SCHOOL_ADDRESS),
        ("Phone", SCHOOL_PHONE),
        ("Email", SCHOOL_EMAIL),
        ("Website", SCHOOL_WEBSITE),
        ("Name", student_row["Name"]),
        ("Student Code", student_row["StudentCode"]),
        ("Phone", student_row["Phone"]),
        ("Level", student_row["Level"]),
        ("Amount Paid", f"GHS {paid}"),
        ("Balance Due", f"GHS {balance}"),
        ("Contract Start", student_row["ContractStart"]),
        ("Contract End", student_row["ContractEnd"]),
        ("Receipt Date", str(payment_date))
    ]:
        pdf.cell(0,8,f"{label}: {val}",ln=True)
    pdf.ln(5)
    pdf.cell(0,8,"Thank you for your payment!",ln=True)
    pdf.ln(10)
    # Agreement
    pdf.set_font("Arial", size=14)
    pdf.cell(200,10,f"{SCHOOL_NAME} Student Contract",ln=True,align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(5)
    for line in filled.split("\n"):
        pdf.multi_cell(0,8,line)
    pdf.ln(5)
    pdf.cell(0,8,"Signed: Felix Asadu",ln=True)
    fname = f"{student_row['Name'].replace(' ','_')}_receipt_and_contract.pdf"
    pdf.output(fname)
    return fname

# === FILES & DATABASE SETUP ===
student_file  = "students_simple.csv"
expenses_file = "expenses_all.csv"
needed_cols   = [
    "Name","Email","Phone","Location","Level","Paid","Balance",
    "ContractStart","ContractEnd","StudentCode"
]

# ensure students CSV exists
if not os.path.exists(student_file):
    pd.DataFrame(columns=needed_cols).to_csv(student_file,index=False)
df_main = pd.read_csv(student_file)

# normalize columns case‐insensitively
col_map = {col:needed for col in df_main.columns
           for needed in needed_cols
           if col.strip().lower()==needed.lower()}
df_main = df_main.rename(columns=col_map)

# add any missing student cols and reorder
for c in needed_cols:
    if c not in df_main.columns:
        df_main[c] = ""
df_main = df_main[needed_cols]

# ensure expenses CSV exists
if not os.path.exists(expenses_file):
    pd.DataFrame(columns=["Type","Item","Amount","Date"]).to_csv(expenses_file,index=False)
exp = pd.read_csv(expenses_file)

# google sheet URL for pending regs
sheet_url = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"

# === HEADER & OVERVIEW ===
st.title(f"🏫 {SCHOOL_NAME} Dashboard")
st.caption(f"📍 {SCHOOL_ADDRESS} | ✉️ {SCHOOL_EMAIL} | 🌐 {SCHOOL_WEBSITE} | 📞 {SCHOOL_PHONE}")

st.header("📊 Overview")
today = datetime.today().date()
# ensure numeric
df_main["Paid"]    = pd.to_numeric(df_main["Paid"],errors="coerce").fillna(0.0)
df_main["Balance"] = pd.to_numeric(df_main["Balance"],errors="coerce").fillna(0.0)
# status
df_main["Status"]  = df_main["ContractEnd"].apply(
    lambda x: "Completed" if pd.to_datetime(str(x),errors="coerce").date() < today else "Enrolled"
)
col1,col2,col3,col4 = st.columns(4)
col1.metric("👩‍🎓 Enrolled", (df_main["Status"]=="Enrolled").sum())
col2.metric("✅ Completed",(df_main["Status"]=="Completed").sum())
col3.metric("💰 Collected", f"GHS {df_main['Paid'].sum():,.2f}")
col4.metric("⏳ Outstanding",f"GHS {df_main['Balance'].sum():,.2f}")

# monthly income vs expenses
inc = (df_main.assign(Month=pd.to_datetime(df_main["ContractStart"],errors="coerce").dt.to_period("M"))
       .groupby("Month")["Paid"].sum().rename("Income"))
exp_m = (exp.assign(Month=pd.to_datetime(exp["Date"],errors="coerce").dt.to_period("M"))
         .groupby("Month")["Amount"].sum().rename("Expenses"))
df_me = pd.concat([inc,exp_m],axis=1).fillna(0)
df_me.index = df_me.index.astype(str)
st.subheader("Monthly Income vs Expenses")
st.bar_chart(df_me)

# === NOTIFICATIONS ===
st.markdown("---")
notifications = []
for _,r in df_main[df_main["Balance"]>0].iterrows():
    msg = urllib.parse.quote(
        f"Dear {r['Name']}, your balance is GHS {r['Balance']}. Code: {r['StudentCode']}. Please pay asap. "
        f"{SCHOOL_NAME} | {SCHOOL_PHONE}"
    )
    link = f"https://wa.me/{clean_phone(r['Phone'])}?text={msg}"
    notifications.append(f"💰 <b>{r['Name']}</b> owes GHS {r['Balance']} ([WhatsApp]({link}))")
st.markdown("🔔 **Notifications**  \n" + ("\n\n".join(notifications) if notifications else "No alerts."), unsafe_allow_html=True)

# === AGREEMENT TEMPLATE ===
if "agreement_template" not in st.session_state:
    st.session_state["agreement_template"] = """
PAYMENT AGREEMENT
...
[STUDENT_NAME], [DATE], [CLASS], [AMOUNT], [FIRST_INSTALMENT], [SECOND_INSTALMENT], [SECOND_DUE_DATE], [COURSE_LENGTH]
Signatures:
[STUDENT_NAME]  Date: [DATE]
Asadu Felix
"""
st.subheader("✍️ Edit Payment Agreement Template")
agreement_text = st.text_area("Agreement Template",value=st.session_state["agreement_template"],height=250)
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

# ============ 0. Pending Registrations ============
with tabs[0]:
    st.title("📝 Pending Student Registrations")
    try:
        new_students = pd.read_csv(sheet_url)
        def clean_col(c):
            return (c.strip().lower()
                    .replace("(","").replace(")","")
                    .replace(",","").replace("-","")
                    .replace(" ","_"))
        new_students.columns = [clean_col(c) for c in new_students.columns]
        st.info(f"Columns: {new_students.columns.tolist()}")
    except Exception as e:
        st.error(f"Could not fetch sheet: {e}")
        new_students = pd.DataFrame()

    for i,row in new_students.iterrows():
        with st.expander(f"{row.get('full_name','')} ({row.get('phone_number','')})"):
            st.write("Email:",row.get("email",""))
            code   = st.text_input("Assign Student Code",key=f"code_{i}")
            paid   = st.number_input("Amount Paid",min_value=0.0,step=1.0,key=f"paid_{i}")
            bal    = st.number_input("Balance Due",min_value=0.0,step=1.0,key=f"bal_{i}")
            start  = st.date_input("Contract Start",key=f"start_{i}")
            end    = st.date_input("Contract End",key=f"end_{i}")
            if st.button("Approve & Add",key=f"app_{i}") and code:
                new = pd.DataFrame([{
                    "Name":row.get("full_name",""),
                    "Email":row.get("email",""),
                    "Phone":row.get("phone_number",""),
                    "Location":row.get("location",""),
                    "Level":row.get("class_a1a2_etc",""),
                    "Paid":paid,"Balance":bal,
                    "ContractStart":start,"ContractEnd":end,
                    "StudentCode":code
                }])
                df_main=pd.concat([df_main,new],ignore_index=True)
                df_main.to_csv(student_file,index=False)
                st.success("Approved & added!")
                st.experimental_rerun()

# ============ 1. All Students ============
with tabs[1]:
    st.title("👩‍🎓 All Students (Search & Edit)")
    search     = st.text_input("🔍 Search by name or code")
    today      = datetime.today().date()
    df_main["_End"] = pd.to_datetime(df_main["ContractEnd"],errors="coerce").dt.date
    df_main["Status"] = df_main["_End"].apply(lambda d:"Completed" if pd.notna(d) and d<today else "Enrolled")
    status_opt = st.selectbox("Filter by status", ["All","Enrolled","Completed"])
    view = df_main.copy()
    if status_opt!="All":
        view = view[view["Status"]==status_opt]
    if search:
        mask = (
            view["Name"].str.contains(search,case=False,na=False)
            | view["StudentCode"].str.contains(search,case=False,na=False)
        )
        view = view[mask]
    if view.empty:
        st.info("No students match your filter.")
    else:
        for pos,(idx,row) in enumerate(view.iterrows()):
            uid = f"{row['StudentCode']}_{idx}_{pos}"
            with st.expander(f"{row['Name']} ({row['StudentCode']}) [{row['Status']}]"):
                name  = st.text_input("Name",row["Name"],key=f"name_{uid}")
                email = st.text_input("Email",row["Email"],key=f"email_{uid}")
                phone = st.text_input("Phone",row["Phone"],key=f"phone_{uid}")
                loc   = st.text_input("Location",row["Location"],key=f"loc_{uid}")
                lvl   = st.text_input("Level",row["Level"],key=f"lvl_{uid}")
                paid  = st.number_input("Paid",float(row["Paid"]),key=f"paid_{uid}")
                bal   = st.number_input("Balance",float(row["Balance"]),key=f"bal_{uid}")
                cs    = st.text_input("Contract Start",str(row["ContractStart"]),key=f"cs_{uid}")
                ce    = st.text_input("Contract End",str(row["ContractEnd"]),key=f"ce_{uid}")
                sc    = st.text_input("Student Code",row["StudentCode"],key=f"sc_{uid}")
                if st.button("Update",key=f"upd_{uid}"):
                    for c,v in [("Name",name),("Email",email),("Phone",phone),
                                ("Location",loc),("Level",lvl),
                                ("Paid",paid),("Balance",bal),
                                ("ContractStart",cs),("ContractEnd",ce),
                                ("StudentCode",sc)]:
                        df_main.at[idx,c]=v
                    df_main.to_csv(student_file,index=False)
                    st.success("Saved!") and st.experimental_rerun()
                if st.button("Delete",key=f"del_{uid}"):
                    df_main.drop(idx,inplace=True)
                    df_main.to_csv(student_file,index=False)
                    st.success("Deleted!") and st.experimental_rerun()

# ============ 2. Add Student ============
with tabs[2]:
    st.title("➕ Add Student")
    with st.form("add_student"):
        name  = st.text_input("Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        loc   = st.text_input("Location")
        lvl   = st.selectbox("Level",["A1","A2","B1","B2","C1","C2"])
        paid  = st.number_input("Paid",min_value=0.0,step=1.0)
        bal   = st.number_input("Balance",min_value=0.0,step=1.0)
        cs    = st.date_input("Contract Start",value=date.today())
        ce    = st.date_input("Contract End",value=date.today())
        sc    = st.text_input("Student Code")
        if st.form_submit_button("Add") and name and sc:
            new = pd.DataFrame([{
                "Name":name,"Email":email,"Phone":phone,
                "Location":loc,"Level":lvl,
                "Paid":paid,"Balance":bal,
                "ContractStart":cs,"ContractEnd":ce,
                "StudentCode":sc
            }])
            df_main=pd.concat([df_main,new],ignore_index=True)
            df_main.to_csv(student_file,index=False)
            st.success("Added!") and st.experimental_rerun()

# ============ 3. Expenses ============
with tabs[3]:
    st.title("💵 Expenses")
    with st.form("add_exp"):
        t = st.selectbox("Type",["Bill","Rent","Salary","Other"])
        it= st.text_input("Item")
        am= st.number_input("Amount",min_value=0.0,step=1.0)
        dt= st.date_input("Date",value=date.today())
        if st.form_submit_button("Add") and it:
            new = pd.DataFrame([{"Type":t,"Item":it,"Amount":am,"Date":dt}])
            exp=pd.concat([exp,new],ignore_index=True)
            exp.to_csv(expenses_file,index=False)
            st.success("Added!") and st.experimental_rerun()
    st.dataframe(exp,use_container_width=True)

# ============ 4. WhatsApp Reminders ============
with tabs[4]:
    st.title("📲 WhatsApp Reminders")
    owes = df_main[df_main["Balance"]>0]
    for _,r in owes.iterrows():
        msg=urllib.parse.quote(f"Dear {r['Name']}, your balance is GHS {r['Balance']}.")
        link=f"https://wa.me/{clean_phone(r['Phone'])}?text={msg}"
        st.markdown(f"**{r['Name']}** owes GHS {r['Balance']} → [WhatsApp]({link})")

# ============ 5. Contract PDF ============
with tabs[5]:
    st.title("📄 Generate Contract PDF")
    choice = st.selectbox("Select Student", df_main["Name"].tolist())
    if st.button("Generate"):
        row = df_main[df_main["Name"]==choice].iloc[0]
        fn  = generate_receipt_and_contract_pdf(row,agreement_text,row["Paid"],row["ContractStart"])
        b64=base64.b64encode(open(fn,"rb").read()).decode()
        st.markdown(f'[Download PDF](data:application/pdf;base64,{b64})',unsafe_allow_html=True)

# ============ 6. Send Email ============
with tabs[6]:
    st.title("📧 Send Email")

    # build list of “Name (email)” options
    options = [
        f"{n} ({e})"
        for n, e in zip(df_main["Name"], df_main["Email"])
        if e.strip()
    ]

    mode = st.radio("Mode", ["Individual", "All"])

    # choose recipients
    if mode == "Individual":
        recips = st.multiselect("Select recipient(s)", options)
    else:
        recips = options.copy()

    subj = st.text_input("Subject", "")
    body = st.text_area("Body", "")

    # allow multiple file attachments
    attachments = st.file_uploader(
        "Attachments",
        type=["pdf", "docx", "jpg", "png"],
        accept_multiple_files=True
    )

    if st.button("Send") and recips and subj and body:
        sent = 0
        failed = []

        for opt in recips:
            # extract email from "Name (email)"
            _, email = opt.rsplit(" ", 1)
            email = email.strip("()")

            # create base message
            msg = Mail(
                from_email=school_sender_email,
                to_emails=email,
                subject=subj,
                html_content=body.replace("\n", "<br>")
            )

            # attach any files
            for uploaded_file in attachments:
                data = uploaded_file.read()
                encoded = base64.b64encode(data).decode()
                attachment = Attachment(
                    FileContent(encoded),
                    FileName(uploaded_file.name),
                    FileType(uploaded_file.type),
                    Disposition("attachment")
                )
                msg.attachment = attachment

            # send
            try:
                SendGridAPIClient(school_sendgrid_key).send(msg)
                sent += 1
            except Exception as e:
                failed.append(email)

        # report results
        if sent:
            st.success(f"✅ Sent to {sent} recipient(s).")
        if failed:
            st.error(f"Failed to send to: {', '.join(failed)}")

# ============ 7. Analytics & Export ============
with tabs[7]:
    st.title("📊 Analytics & Export")
    # enrollment over time
    df_main["StartDT"]=pd.to_datetime(df_main["ContractStart"],errors="coerce")
    bymo=df_main.groupby(df_main["StartDT"].dt.to_period("M")).size().rename("Count")
    st.line_chart(bymo.astype(int))
    st.download_button("Download Students CSV",df_main.to_csv(index=False),"all_students.csv")
    st.download_button("Download Expenses CSV",exp.to_csv(index=False),"all_expenses.csv")
