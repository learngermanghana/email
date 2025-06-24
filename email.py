import os
import base64
import urllib.parse
from datetime import date, datetime, timedelta

import pandas as pd
import numpy as np
import streamlit as st

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

from datetime import date
import pandas as pd
import numpy as np
import streamlit as st
from fpdf import FPDF

def safe_latin1(text):
    return text.encode("latin1", "replace").decode("latin1")

import os
import pandas as pd
import numpy as np
import streamlit as st
from datetime import date

# --- TAB 1: All Students (View, Contracts, Receipts) ---
with tabs[1]:
    st.title("👩‍🎓 All Students (View, Contracts, Receipts)")

    github_csv = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
    try:
        df_students = pd.read_csv(github_csv)
        st.success(f"Loaded {len(df_students)} students from GitHub.")
    except Exception as e:
        st.error(f"Could not load students from GitHub: {e}")
        st.stop()

    # --- Normalize columns for easier code ---
    df_students.columns = [
        c.strip().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_").replace("/", "_").lower()
        for c in df_students.columns
    ]

    # --- Fill missing columns if necessary ---
    for col in ["fees", "paid"]:
        if col not in df_students.columns:
            df_students[col] = 0.0

    # --- Filter/search controls ---
    search_term = st.text_input("🔍 Search Student by Name or Code")
    levels = ["All"] + sorted(df_students["level"].dropna().unique().tolist()) if "level" in df_students.columns else ["All"]
    selected_level = st.selectbox("📋 Filter by Class Level", levels)
    statuses = ["All", "Enrolled", "Completed", "Unknown"]
    status_filter = st.selectbox("Filter by Status", statuses)

    # --- Status assignment ---
    today = date.today()
    if "contractend" in df_students.columns:
        df_students["contractend"] = pd.to_datetime(df_students["contractend"], errors="coerce")
        df_students["status"] = "Unknown"
        mask_valid = df_students["contractend"].notna()
        df_students.loc[mask_valid, "status"] = np.where(
            df_students.loc[mask_valid, "contractend"].dt.date < today,
            "Completed",
            "Enrolled"
        )
    else:
        df_students["status"] = "Unknown"

    # --- Apply filters ---
    view_df = df_students.copy()
    if search_term:
        view_df = view_df[
            view_df["name"].astype(str).str.lower().str.contains(search_term.lower()) |
            view_df["studentcode"].astype(str).str.lower().str.contains(search_term.lower())
        ]
    if selected_level != "All" and "level" in df_students.columns:
        view_df = view_df[view_df["level"] == selected_level]
    if status_filter != "All":
        view_df = view_df[view_df["status"] == status_filter]

    if view_df.empty:
        st.info("No students found for this filter/search.")
    else:
        st.dataframe(view_df, use_container_width=True)

        # -- Pick a student for contract/receipt/payment edit --
        st.markdown("### 🔎 Select Student For Payment Edit, Contract or Receipt")
        pick_list = view_df["name"].astype(str) + " (" + view_df["studentcode"].astype(str) + ")"
        pick = st.selectbox("Select Student", pick_list)
        selected_code = pick.split("(")[-1].replace(")", "").strip()
        student_row = view_df[view_df["studentcode"].astype(str).str.lower() == selected_code.lower()].iloc[0]

        # --- Payment Editing Section ---
        st.markdown("#### 💵 Payment Information")
        total_fees = float(student_row.get('fees', 0.0) or 0.0)
        paid = float(student_row.get('paid', 0.0) or 0.0)
        st.info(f"Tuition/Total Fees: GHS {total_fees:,.2f}")

        # To avoid StreamlitMixedNumericTypesError, always use floats
        max_value = float(total_fees)
        min_value = 0.0
        first_instalment = st.number_input(
            "First Installment Paid (GHS)",
            min_value=min_value,
            max_value=max_value,
            value=paid,
            step=1.0,
            key=f"instalment_{selected_code}"
        )
        remaining = total_fees - first_instalment
        st.write(f"**Remaining Balance:** GHS {remaining:,.2f}")

        # --- Update paid value in DataFrame (session only) ---
        if st.button("💾 Update Payment Info for Student"):
            idx = df_students.index[df_students["studentcode"].astype(str).str.lower() == selected_code.lower()]
            if not idx.empty:
                df_students.at[idx[0], "paid"] = first_instalment
                st.success(f"Updated payment for {student_row['name']} to GHS {first_instalment:,.2f}.")
            else:
                st.error("Could not find student in DataFrame.")

        # --- Download updated students.csv for GitHub re-upload ---
        st.download_button(
            "⬇️ Download Updated Students CSV",
            data=df_students.to_csv(index=False),
            file_name="students_updated.csv"
        )

        # -- Generate Payment Contract PDF --
        if st.button("📝 Generate Payment Contract"):
            from fpdf import FPDF

            # Clean contract text for PDF (no unicode, avoid strange symbols)
            contract_text = (
                f"This payment contract is made between {student_row['name']} ({student_row['studentcode']}) and Learn Language Education Academy.\n\n"
                f"Student Level: {student_row.get('level', '')}\n"
                f"Contract Start: {student_row.get('contractstart', '')}\n"
                f"Contract End: {student_row.get('contractend', '')}\n"
                f"Tuition: GHS {total_fees:,.2f}\n"
                f"First Installment: GHS {first_instalment:,.2f}\n"
                f"Remaining Balance: GHS {remaining:,.2f}\n"
                f"Phone: {student_row.get('phone', '')}\n"
                f"Email: {student_row.get('email', '')}\n"
                f"Address: {student_row.get('address', '')}\n\n"
                "By signing, the student agrees to pay all required fees and abide by the Academy's policies.\n\n"
                "Signed: ______________________      Date: ________________\n\n"
                "For: Learn Language Education Academy\n"
                "Felix Asadu"
            )

            class PDF(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 14)
                    self.cell(0, 12, "Learn Language Education Academy – Payment Contract", ln=1, align='C')
            pdf = PDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            # Only use ascii to avoid unicode issues
            pdf.multi_cell(0, 8, contract_text.encode("ascii", "ignore").decode())
            pdf.set_font("Arial", "I", 11)
            pdf.cell(0, 10, "Signed: Felix Asadu", ln=1, align='R')
            pdf_out = f"{student_row['name'].replace(' ', '_')}_contract.pdf"
            pdf.output(pdf_out)
            with open(pdf_out, "rb") as f:
                pdf_bytes = f.read()
            st.download_button("⬇️ Download Payment Contract", data=pdf_bytes, file_name=pdf_out, mime="application/pdf")

        # -- Generate Receipt PDF --
        if st.button("📄 Generate Payment Receipt"):
            from fpdf import FPDF
            # Payment status
            status = "Full Payment Received" if remaining == 0 else f"Installment Payment: GHS {first_instalment:,.2f} paid, GHS {remaining:,.2f} remaining"
            receipt_text = (
                "RECEIPT OF PAYMENT\n\n"
                f"Received from: {student_row['name']} ({student_row['studentcode']})\n"
                f"Level: {student_row.get('level', '')}\n"
                f"Date: {date.today().strftime('%Y-%m-%d')}\n"
                f"Amount Paid: GHS {first_instalment:,.2f}\n"
                f"Payment Method: ____________________\n\n"
                f"Status: {status}\n\n"
                "Thank you for your payment!\n\n"
                "For: Learn Language Education Academy\n"
                "Felix Asadu"
            )

            class PDFReceipt(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 14)
                    self.cell(0, 12, "Learn Language Education Academy – Payment Receipt", ln=1, align='C')
            pdf_r = PDFReceipt()
            pdf_r.add_page()
            pdf_r.set_font("Arial", size=12)
            pdf_r.multi_cell(0, 8, receipt_text.encode("ascii", "ignore").decode())
            pdf_r.set_font("Arial", "I", 11)
            pdf_r.cell(0, 10, "Signed: Felix Asadu", ln=1, align='R')
            receipt_out = f"{student_row['name'].replace(' ', '_')}_receipt.pdf"
            pdf_r.output(receipt_out)
            with open(receipt_out, "rb") as f:
                rec_bytes = f.read()
            st.download_button("⬇️ Download Payment Receipt", data=rec_bytes, file_name=receipt_out, mime="application/pdf")

with tabs[1]:
student_file = "students.csv"

def safe(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

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

