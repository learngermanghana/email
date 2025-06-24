from datetime import date
import pandas as pd
import numpy as np
import streamlit as st
from fpdf import FPDF
import os
import pandas as pd
import numpy as np
import streamlit as st
from datetime import date

# --- Project Info ---
SCHOOL_NAME    = "Learn Language Education Academy"
SCHOOL_EMAIL   = "Learngermanghana@gmail.com"
SCHOOL_PHONE   = "233205706589"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# --- GitHub CSV Links ---
STUDENTS_CSV_URL = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
SCORES_CSV_URL   = "https://raw.githubusercontent.com/learngermanghana/email/main/scores_backup.csv"
EXPENSES_CSV_URL = "https://raw.githubusercontent.com/learngermanghana/email/main/expenses.csv"

# --- Top Notification (ALWAYS VISIBLE) ---
try:
    df_students_notify = pd.read_csv(STUDENTS_CSV_URL)
    df_students_notify.columns = [c.strip().lower() for c in df_students_notify.columns]
    if "balance" in df_students_notify.columns:
        df_students_notify["balance"] = pd.to_numeric(df_students_notify["balance"], errors="coerce").fillna(0)
        total_debtors = (df_students_notify["balance"] > 0).sum()
        if total_debtors > 0:
            st.warning(f"⚠️ <b>{total_debtors} students have unpaid balances.</b> [See details in Reminders tab!]", unsafe_allow_html=True)
except Exception:
    pass

# --- Tabs ---
tabs = st.tabs([
    "📝 Pending",
    "👩‍🎓 All Students",
    "📲 Reminders",
    "📆 Course Schedule",
    "📝 Marking",
    # "✉️ Send Email"   # (to be added when we reach that tab)
])

# ===================
# TAB 0: Pending Students
# ===================
with tabs[0]:
    st.title("📝 Pending Students (Registration Sheet)")
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"
    try:
        df_pending = pd.read_csv(SHEET_URL)
        df_pending.columns = [c.strip().replace(" ", "_").replace("(", "").replace(")", "").lower() for c in df_pending.columns]
        st.success(f"Loaded {len(df_pending)} new student(s) from registration sheet.")
        st.dataframe(df_pending, use_container_width=True)
        st.download_button(
            "📁 Download Pending Students CSV",
            data=df_pending.to_csv(index=False),
            file_name="pending_students.csv"
        )
    except Exception as e:
        st.warning(f"Could not load registration data: {e}")
        st.info("No pending students. All new students must fill the online registration form.")

def safe_latin1(text):
    # Replace unsupported Unicode with '?'
    return text.encode("latin1", "replace").decode("latin1")



with tabs[1]:

def generate_contract_and_receipt(student_row, contract_template, payment_date=None):
    if payment_date is None:
        payment_date = date.today()
    paid = float(student_row.get("Paid", 0) or 0)
    balance = float(student_row.get("Balance", 0) or 0)
    total_fee = paid + balance
    payment_status = "FULLY PAID" if balance == 0 else "INSTALLMENT PLAN"
    due_date = payment_date + timedelta(days=30)
    filled = contract_template \
        .replace("[STUDENT_NAME]", str(student_row.get("Name", ""))) \
        .replace("[DATE]", str(payment_date)) \
        .replace("[CLASS]", str(student_row.get("Level", ""))) \
        .replace("[AMOUNT]", f"{total_fee:.2f}") \
        .replace("[FIRST_INSTALMENT]", f"{paid:.2f}") \
        .replace("[SECOND_INSTALMENT]", f"{balance:.2f}") \
        .replace("[SECOND_DUE_DATE]", str(due_date)) \
        .replace("[COURSE_LENGTH]", str(12))
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, safe("Learn Language Education Academy Payment Receipt"), ln=True, align="C")
    pdf.set_font("Arial", 'B', 12)
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
    pdf.ln(15)
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, safe("Learn Language Education Academy Student Contract"), ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    for line in filled.split("\n"):
        pdf.multi_cell(0, 10, safe(line))
    pdf.ln(10)
    pdf.cell(0, 10, safe("Signed: Felix Asadu"), ln=True)
    pdf.set_y(-15)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 10, safe(f"Generated on {date.today()}"), align="C")
    filename = f"{student_row.get('Name','').replace(' ', '_')}_receipt_contract.pdf"
    pdf.output(filename)
    return filename

# === START OF TAB CODE ===
st.title("👩‍🎓 All Students (Edit, Update, Receipt/Contract)")

if os.path.exists(student_file):
    df_main = pd.read_csv(student_file)
else:
    st.warning("students.csv not found.")
    st.stop()

# Normalize columns for easier access
df_main.columns = [
    c.strip().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_").replace("/", "_").lower()
    for c in df_main.columns
]
def col_lookup(col):
    for c in df_main.columns:
        if c.replace("_", "").lower() == col.replace("_", "").lower():
            return c
    return col

# Filters
search_term = st.text_input("🔍 Search Student by Name or Code").lower()
levels = ["All"] + sorted(df_main[col_lookup("level")].dropna().unique().tolist())
selected_level = st.selectbox("📋 Filter by Class Level", levels)
view_df = df_main.copy()
if search_term:
    view_df = view_df[
        view_df[col_lookup("name")].astype(str).str.lower().str.contains(search_term) |
        view_df[col_lookup("studentcode")].astype(str).str.lower().str.contains(search_term)
    ]
if selected_level != "All":
    view_df = view_df[view_df[col_lookup("level")] == selected_level]

# Table
if view_df.empty:
    st.info("No students found.")
else:
    st.dataframe(view_df, use_container_width=True)

    # Select student to edit/view
    student_names = view_df[col_lookup("name")].tolist()
    if student_names:
        selected_student = st.selectbox(
            "Select a student to view/edit details", student_names, key="select_student_detail_all"
        )
        student_row = view_df[view_df[col_lookup("name")] == selected_student].iloc[0]
        idx = view_df[view_df[col_lookup("name")] == selected_student].index[0]
        unique_key = f"{student_row[col_lookup('studentcode')]}_{idx}"

        with st.expander(f"{student_row[col_lookup('name')]} ({student_row[col_lookup('studentcode')]})", expanded=True):
            name_input = st.text_input("Name", value=student_row[col_lookup("name")], key=f"name_{unique_key}")
            phone_input = st.text_input("Phone", value=student_row[col_lookup("phone")], key=f"phone_{unique_key}")
            email_input = st.text_input("Email", value=student_row.get(col_lookup("email"), ""), key=f"email_{unique_key}")
            location_input = st.text_input("Location", value=student_row.get(col_lookup("location"), ""), key=f"loc_{unique_key}")
            level_input = st.text_input("Level", value=student_row[col_lookup("level")], key=f"level_{unique_key}")
            paid_input = st.number_input("Paid", value=float(student_row[col_lookup("paid")]), key=f"paid_{unique_key}")
            balance_input = st.number_input("Balance", value=float(student_row[col_lookup("balance")]), key=f"bal_{unique_key}")
            contract_start_input = st.text_input("Contract Start", value=str(student_row.get(col_lookup("contractstart"), "")), key=f"cs_{unique_key}")
            contract_end_input = st.text_input("Contract End", value=str(student_row.get(col_lookup("contractend"), "")), key=f"ce_{unique_key}")
            code_input = st.text_input("Student Code", value=student_row[col_lookup("studentcode")], key=f"code_{unique_key}")
            emergency_input = st.text_input("Emergency Contact", value=student_row.get(col_lookup("emergencycontact_phonenumber"), ""), key=f"em_{unique_key}")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 Update", key=f"update_{unique_key}"):
                    df_main.at[idx, col_lookup("name")] = name_input
                    df_main.at[idx, col_lookup("phone")] = phone_input
                    df_main.at[idx, col_lookup("email")] = email_input
                    df_main.at[idx, col_lookup("location")] = location_input
                    df_main.at[idx, col_lookup("level")] = level_input
                    df_main.at[idx, col_lookup("paid")] = paid_input
                    df_main.at[idx, col_lookup("balance")] = balance_input
                    df_main.at[idx, col_lookup("contractstart")] = contract_start_input
                    df_main.at[idx, col_lookup("contractend")] = contract_end_input
                    df_main.at[idx, col_lookup("studentcode")] = code_input
                    df_main.at[idx, col_lookup("emergencycontact_phonenumber")] = emergency_input
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
                if st.button("📄 Contract & Receipt PDF", key=f"receipt_{unique_key}"):
                    # Use input values (latest edits)
                    contract_start = contract_start_input
                    # Get or set contract template
                    contract_template = st.session_state.get("agreement_template", "CONTRACT NOT FOUND")
                    # Compose student dict
                    stu_dict = {
                        "Name": name_input,
                        "Phone": phone_input,
                        "Email": email_input,
                        "Location": location_input,
                        "Level": level_input,
                        "Paid": paid_input,
                        "Balance": balance_input,
                        "ContractStart": contract_start,
                        "ContractEnd": contract_end_input,
                        "StudentCode": code_input,
                        "Emergency Contact (Phone Number)": emergency_input,
                    }
                    try:
                        payment_date = pd.to_datetime(contract_start, errors="coerce").date()
                    except Exception:
                        payment_date = date.today()
                    pdf_file = generate_contract_and_receipt(
                        stu_dict,
                        contract_template,
                        payment_date=payment_date
                    )
                    with open(pdf_file, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        "⬇️ Download Contract + Receipt PDF",
                        data=pdf_bytes,
                        file_name=pdf_file,
                        mime="application/pdf"
                    )



with tabs[2]:
    st.title("💵 Expenses and Financial Summary")

    # --- GitHub CSV source for expenses ---
    github_expenses_url = "https://raw.githubusercontent.com/learngermanghana/email/main/expenses.csv"
    try:
        df_expenses = pd.read_csv(github_expenses_url)
        st.success(f"Loaded {len(df_expenses)} expense records from GitHub.")
    except Exception:
        st.error("Could not load expenses data from GitHub.")
        df_expenses = pd.DataFrame(columns=["Type", "Item", "Amount", "Date"])

    if df_expenses.empty:
        st.info("No expense data available.")
    else:
        # Standardize columns for summary
        df_expenses.columns = [c.strip().capitalize() for c in df_expenses.columns]
        st.write("### All Expenses")
        st.dataframe(df_expenses, use_container_width=True)

        st.write("### Expense Summary")
        total_expenses = pd.to_numeric(df_expenses.get("Amount", []), errors="coerce").sum()
        st.info(f"💸 **Total Expenses:** GHS {total_expenses:,.2f}")

        exp_csv = df_expenses.to_csv(index=False).encode()
        st.download_button("📁 Download Expenses CSV", data=exp_csv, file_name="expenses_data.csv")

