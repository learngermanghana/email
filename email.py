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

        # -- Pick a student for contract/receipt --
        st.markdown("### 🔎 Select Student For Contract or Receipt")
        pick_list = view_df["name"].astype(str) + " (" + view_df["studentcode"].astype(str) + ")"
        pick = st.selectbox("Select Student", pick_list)
        selected_code = pick.split("(")[-1].replace(")", "").strip()
        student_row = view_df[view_df["studentcode"].astype(str).str.lower() == selected_code.lower()].iloc[0]

        # --- SAFE float conversion function ---
        import math
        def to_float(val):
            try:
                f = float(val)
                if math.isnan(f):
                    return 0.0
                return f
            except:
                return 0.0

        # --- Payment logic ---
        total_fees = to_float(student_row.get("fees", 0))
        paid = to_float(student_row.get("paid", 0))
        max_value = float(total_fees)
        min_value = 0.0
        default_paid = min(max(paid, 0.0), total_fees)

        st.markdown("#### 💵 Payment Info")
        st.write(f"**Total Fees:** GHS {total_fees:,.2f}")

        first_instalment = st.number_input(
            "First Installment Paid (GHS)",
            min_value=min_value,
            max_value=max_value,
            value=default_paid,
            step=1.0,
            key="instalment_input"
        )

        remaining_balance = total_fees - first_instalment
        remaining_balance = max(0.0, remaining_balance)
        st.info(f"**Remaining Balance:** GHS {remaining_balance:,.2f}")

        # ============ PDF HELPER ==============
        def safe_ascii(text):
            return text.encode("latin1", "replace").decode("latin1")

        # -- Generate Payment Contract PDF --
        if st.button("📝 Generate Payment Contract"):
            from fpdf import FPDF

            contract_text = f"""
            PAYMENT AGREEMENT

            This Payment Agreement is entered into on {date.today().strftime('%Y-%m-%d')} for students of Learn Language Education Academy and Felix Asadu ("Teacher").

            Student: {student_row['name']} ({student_row['studentcode']})
            Student Level: {student_row.get('level','')}
            Contract Start: {student_row.get('contractstart','')}
            Contract End: {student_row.get('contractend','')}
            Tuition: GHS {total_fees:,.2f}
            First Installment: GHS {first_instalment:,.2f}
            Remaining Balance: GHS {remaining_balance:,.2f}

            Terms:
            1. Payment can be made in full or in two installments. Second installment is due before end of contract.
            2. No refunds after payment. Access revoked if payment is overdue.
            3. Attendance and communication required by both parties.

            Signatures:
            Student: ______________________      Date: ________________

            For: Learn Language Education Academy
            Felix Asadu
            """

            class PDF(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 14)
                    self.cell(0, 12, safe_ascii("Learn Language Education Academy – Payment Contract"), ln=1, align='C')
            pdf = PDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.multi_cell(0, 8, safe_ascii(contract_text))
            pdf.set_font("Arial", "I", 11)
            pdf.cell(0, 10, safe_ascii("Signed: Felix Asadu"), ln=1, align='R')
            pdf_out = f"{student_row['name'].replace(' ', '_')}_contract.pdf"
            pdf.output(pdf_out)
            with open(pdf_out, "rb") as f:
                pdf_bytes = f.read()
            st.download_button("⬇️ Download Payment Contract", data=pdf_bytes, file_name=pdf_out, mime="application/pdf")

        # -- Generate Receipt PDF --
        if st.button("📄 Generate Payment Receipt"):
            from fpdf import FPDF

            if remaining_balance == 0.0:
                payment_status = "Full Payment Received"
            elif first_instalment == 0.0:
                payment_status = "No Payment Made"
            else:
                payment_status = f"Part Payment: GHS {first_instalment:,.2f} paid, GHS {remaining_balance:,.2f} outstanding"

            receipt_text = f"""
            RECEIPT OF PAYMENT

            Received from: {student_row['name']} ({student_row['studentcode']})
            Level: {student_row.get('level','')}
            Date: {date.today().strftime('%Y-%m-%d')}
            Amount Paid: GHS {first_instalment:,.2f}
            Payment Status: {payment_status}

            Thank you for your payment!

            For: Learn Language Education Academy
            Felix Asadu
            """

            class PDFReceipt(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 14)
                    self.cell(0, 12, safe_ascii("Learn Language Education Academy – Payment Receipt"), ln=1, align='C')
            pdf_r = PDFReceipt()
            pdf_r.add_page()
            pdf_r.set_font("Arial", size=12)
            pdf_r.multi_cell(0, 8, safe_ascii(receipt_text))
            pdf_r.set_font("Arial", "I", 11)
            pdf_r.cell(0, 10, safe_ascii("Signed: Felix Asadu"), ln=1, align='R')
            receipt_out = f"{student_row['name'].replace(' ', '_')}_receipt.pdf"
            pdf_r.output(receipt_out)
            with open(receipt_out, "rb") as f:
                rec_bytes = f.read()
            st.download_button("⬇️ Download Payment Receipt", data=rec_bytes, file_name=receipt_out, mime="application/pdf")


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

