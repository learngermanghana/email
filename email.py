import os
import json
import base64
import urllib.parse
from datetime import date, datetime, timedelta

import pandas as pd
import os
import json
import base64
import urllib.parse
from datetime import date, datetime, timedelta

import pandas as pd
import numpy as np
import streamlit as st
from fpdf import FPDF
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition
)
import openai

import numpy as np
import streamlit as st
from fpdf import FPDF
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition
)
import openai

# ===== Project-Specific Imports =====
from pdf_utils import generate_receipt_and_contract_pdf
from email_utils import send_emails

# ===== SQLite for Persistent Data Storage =====
import sqlite3

# ===== Helper Functions =====
def clean_phone(phone):
    """
    Convert any Ghanaian phone number to WhatsApp-friendly format:
    - Remove spaces, dashes, and '+'
    - If starts with '0', replace with '233'
    - If starts with '233', leave as is
    - Returns only digits
    """
    phone = str(phone).replace(" ", "").replace("+", "").replace("-", "")
    if phone.startswith("0"):
        phone = "233" + phone[1:]
    phone = ''.join(filter(str.isdigit, phone))
    return phone

# ===== PAGE CONFIG (must be first Streamlit command!) =====
st.set_page_config(
    page_title="Learn Language Education Academy Dashboard",
    layout="wide"
)

# === Session State Initialization ===
st.session_state.setdefault("emailed_expiries", set())
st.session_state.setdefault("dismissed_notifs", set())


# === SCHOOL INFO ===
SCHOOL_NAME    = "Learn Language Education Academy"
SCHOOL_EMAIL   = "Learngermanghana@gmail.com"
SCHOOL_WEBSITE = "www.learngermanghana.com"
SCHOOL_PHONE   = "233205706589"
SCHOOL_ADDRESS = "Awoshie, Accra, Ghana"

# === EMAIL CONFIG ===
school_sendgrid_key = st.secrets.get("general", {}).get("SENDGRID_API_KEY")
school_sender_email = st.secrets.get("general", {}).get("SENDER_EMAIL", SCHOOL_EMAIL)

tabs = st.tabs([
    "📝 Pending",
    "👩‍🎓 All Students",
    "➕ Add Student",
    "💵 Expenses",
    "📲 Reminders",
    "📄 Contract ",
    "📧 Send Email",
    "📊 Analytics & Export",
    "📆 Schedule",
    "📝 Marking"   # <--- New tab!
])

import os
import pandas as pd
import streamlit as st
from datetime import date, timedelta

with tabs[0]:
    st.title("📝 Pending")

    # 1) Fetch registrations from Google Sheets (CSV export)
    sheet_csv = (
        "https://docs.google.com/spreadsheets/d/"
        "1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo"
        "/export?format=csv"
    )
    try:
        new_students = pd.read_csv(sheet_csv)
        def clean_col(c):
            return (
                c.strip()
                 .lower()
                 .replace("(", "")
                 .replace(")", "")
                 .replace(",", "")
                 .replace("-", "")
                 .replace(" ", "_")
            )
        new_students.columns = [clean_col(c) for c in new_students.columns]
        st.success("✅ Loaded columns: " + ", ".join(new_students.columns))
    except Exception as e:
        st.error(f"❌ Could not load registration sheet: {e}")
        new_students = pd.DataFrame()

    # 2) Approve & add each new student
    if new_students.empty:
        st.info("No new registrations to process.")
    else:
        for i, row in new_students.iterrows():
            fullname  = row.get("full_name") or row.get("name") or f"Student {i}"
            phone     = row.get("phone_number") or row.get("phone") or ""
            email     = str(row.get("email") or row.get("email_address") or "").strip()
            level     = str(row.get("class") or row.get("class_a1a2_etc") or row.get("level") or "").strip()
            location  = str(row.get("location") or "").strip()
            emergency = str(row.get("emergency_contact_phone_number") or row.get("emergency") or "").strip()

            with st.expander(f"{fullname} — {phone}"):
                st.write(f"**Email:** {email or '—'}")
                student_code    = st.text_input("Assign Student Code", key=f"code_{i}")
                contract_start  = st.date_input("Contract Start", value=date.today(), key=f"start_{i}")
                course_length   = st.number_input("Course Length (weeks)", min_value=1, value=12, key=f"length_{i}")
                contract_end    = st.date_input(
                    "Contract End",
                    value=contract_start + timedelta(weeks=course_length),
                    key=f"end_{i}"
                )
                paid            = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0, key=f"paid_{i}")
                balance         = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0, key=f"bal_{i}")
                first_instalment= st.number_input("First Instalment (GHS)", min_value=0.0, value=1500.0, key=f"firstinst_{i}")
                send_email      = st.checkbox("Send Welcome Email?", value=bool(email), key=f"email_{i}")
                attach_pdf      = st.checkbox("Attach PDF to Email?", value=True, key=f"pdf_{i}")

                if st.button("Approve & Add", key=f"approve_{i}"):
                    if not student_code:
                        st.warning("❗ Please enter a unique student code.")
                        continue

                    if os.path.exists("students.csv"):
                        approved_df = pd.read_csv("students.csv")
                    else:
                        approved_df = pd.DataFrame(columns=[
                            "Name","Phone","Email","Location","Level",
                            "Paid","Balance","ContractStart","ContractEnd",
                            "StudentCode","Emergency Contact (Phone Number)"
                        ])

                    if student_code in approved_df["StudentCode"].astype(str).values:
                        st.warning("❗ Student code already exists.")
                        continue

                    student_dict = {
                        "Name": fullname,
                        "Phone": phone,
                        "Email": email,
                        "Location": location,
                        "Level": level,
                        "Paid": paid,
                        "Balance": balance,
                        "ContractStart": contract_start.isoformat(),
                        "ContractEnd": contract_end.isoformat(),
                        "StudentCode": student_code,
                        "Emergency Contact (Phone Number)": emergency
                    }

                    approved_df = pd.concat([approved_df, pd.DataFrame([student_dict])], ignore_index=True)
                    approved_df.to_csv("students.csv", index=False)

                    total_fee = paid + balance
                    pdf_file = generate_receipt_and_contract_pdf(
                        student_dict,
                        st.session_state["agreement_template"],
                        payment_amount=total_fee,
                        payment_date=contract_start,
                        first_instalment=first_instalment,
                        course_length=course_length
                    )
                    if send_email and email and 'school_sendgrid_key' in globals():
                        try:
                            # Email sending logic...
                            st.success(f"📧 Email sent to {email}")
                        except Exception as e:
                            st.warning(f"⚠️ Email failed: {e}")

                    st.success(f"✅ {fullname} approved and saved.")
                    st.rerun()



with tabs[1]:
    st.title("👩‍🎓 All Students (Edit, Update, Delete, Receipt)")

    # ---- Student Data: load from local or GitHub backup ----
    student_file = "students.csv"
    github_csv = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
    if os.path.exists(student_file):
        df_main = pd.read_csv(student_file)
    else:
        try:
            df_main = pd.read_csv(github_csv)
            st.info("Loaded students from GitHub backup.")
        except Exception:
            st.warning("⚠️ students.csv not found locally or on GitHub.")
            st.stop()

    # ---- Normalize columns ----
    df_main.columns = [
        c.strip().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_").replace("/", "_").lower()
        for c in df_main.columns
    ]
    def col_lookup(col):
        for c in df_main.columns:
            if c.replace("_", "").lower() == col.replace("_", "").lower():
                return c
        return col

    # ---- Status & Dates ----
    today = date.today()
    if col_lookup("contractend") in df_main.columns:
        df_main["contractend"] = pd.to_datetime(df_main[col_lookup("contractend")], errors="coerce")
        df_main["status"] = "Unknown"
        mask_valid = df_main["contractend"].notna()
        df_main.loc[mask_valid, "status"] = np.where(
            df_main.loc[mask_valid, "contractend"].dt.date < today,
            "Completed",
            "Enrolled"
        )

    # ---- Filters/Search ----
    search_term = st.text_input("🔍 Search Student by Name or Code").lower()
    levels = ["All"] + sorted(df_main[col_lookup("level")].dropna().unique().tolist())
    selected_level = st.selectbox("📋 Filter by Class Level", levels)
    statuses = ["All", "Enrolled", "Completed", "Unknown"]
    status_filter = st.selectbox("Filter by Status", statuses)

    view_df = df_main.copy()
    if search_term:
        view_df = view_df[
            view_df[col_lookup("name")].astype(str).str.lower().str.contains(search_term) |
            view_df[col_lookup("studentcode")].astype(str).str.lower().str.contains(search_term)
        ]
    if selected_level != "All":
        view_df = view_df[view_df[col_lookup("level")] == selected_level]
    if status_filter != "All":
        view_df = view_df[view_df["status"] == status_filter]

    # ---- Table & Pagination ----
    if view_df.empty:
        st.info("No students found.")
    else:
        ROWS_PER_PAGE = 10
        total_rows = len(view_df)
        total_pages = (total_rows - 1) // ROWS_PER_PAGE + 1
        page = st.number_input(
            f"Page (1-{total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="students_page"
        )
        start_idx = (page - 1) * ROWS_PER_PAGE
        end_idx = start_idx + ROWS_PER_PAGE

        paged_df = view_df.iloc[start_idx:end_idx].reset_index(drop=True)
        show_cols = [col_lookup(c) for c in ["name", "studentcode", "level", "phone", "paid", "balance", "status"]]
        st.dataframe(paged_df[show_cols], use_container_width=True)

        # --- Student Details (edit/update/delete/receipt) ---
        student_names = paged_df[col_lookup("name")].tolist()
        if student_names:
            selected_student = st.selectbox(
                "Select a student to view/edit details", student_names, key="select_student_detail_all"
            )
            student_row = paged_df[paged_df[col_lookup("name")] == selected_student].iloc[0]
            idx = view_df[view_df[col_lookup("name")] == selected_student].index[0]
            unique_key = f"{student_row[col_lookup('studentcode')]}_{idx}"
            status_color = (
                "🟢" if student_row["status"] == "Enrolled" else
                "🔴" if student_row["status"] == "Completed" else
                "⚪"
            )

            with st.expander(f"{status_color} {student_row[col_lookup('name')]} ({student_row[col_lookup('studentcode')]}) [{student_row['status']}]", expanded=True):
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
                    if st.button("📄 Receipt", key=f"receipt_{unique_key}"):
                        total_fee = paid_input + balance_input
                        parsed_date = pd.to_datetime(contract_start_input, errors="coerce").date()
                        pdf_path = generate_receipt_and_contract_pdf(
                            student_row,
                            st.session_state["agreement_template"],
                            payment_amount=total_fee,
                            payment_date=parsed_date
                        )
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        b64 = base64.b64encode(pdf_bytes).decode()
                        download_link = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{name_input.replace(" ", "_")}_receipt.pdf">Download Receipt</a>'
                        )
                        st.markdown(download_link, unsafe_allow_html=True)

        # --- Download students.csv (for backup/manual editing) ---
        backup_csv = df_main.to_csv(index=False).encode()
        st.download_button("📁 Download All Students CSV", data=backup_csv, file_name="students_backup.csv", mime="text/csv", key="download_students_all")



with tabs[2]:
    st.title("➕ Add Student Manually")

    with st.form("add_student_form"):
        name = st.text_input("Full Name")
        phone = st.text_input("Phone Number")
        email = st.text_input("Email Address")
        location = st.text_input("Location")
        emergency = st.text_input("Emergency Contact (Phone Number)")
        level = st.selectbox("Class Level", ["A1", "A2", "B1", "B2", "C1", "C2"])
        paid = st.number_input("Amount Paid (GHS)", min_value=0.0, step=1.0)
        balance = st.number_input("Balance Due (GHS)", min_value=0.0, step=1.0)
        contract_start = st.date_input("Contract Start", value=date.today())
        course_length = st.number_input("Course Length (weeks)", min_value=1, value=12)
        contract_end = contract_start + timedelta(weeks=course_length)
        student_code = st.text_input("Student Code (must be unique)")

        submit_btn = st.form_submit_button("Add Student")

        if submit_btn:
            if not name or not phone or not student_code:
                st.warning("❗ Name, Phone, and Student Code are required.")
            else:
                # Always work with fresh CSV
                if os.path.exists(student_file):
                    existing_df = pd.read_csv(student_file)
                else:
                    existing_df = pd.DataFrame(columns=[
                        "Name", "Phone", "Email", "Location", "Level", "Paid", "Balance",
                        "ContractStart", "ContractEnd", "StudentCode", "Emergency Contact (Phone Number)"
                    ])

                if student_code in existing_df["StudentCode"].values:
                    st.error("❌ This Student Code already exists.")
                    st.stop()

                new_row = pd.DataFrame([{
                    "Name": name,
                    "Phone": phone,
                    "Email": email,
                    "Location": location,
                    "Level": level,
                    "Paid": paid,
                    "Balance": balance,
                    "ContractStart": str(contract_start),
                    "ContractEnd": str(contract_end),
                    "StudentCode": student_code,
                    "Emergency Contact (Phone Number)": emergency
                }])

                updated_df = pd.concat([existing_df, new_row], ignore_index=True)
                updated_df.to_csv(student_file, index=False)
                st.success(f"✅ Student '{name}' added successfully.")

import pandas as pd
import urllib.parse
from datetime import date, timedelta
import streamlit as st

# --- Tab 3: Expenses and Financial Summary (Google Sheets) ---
with tabs[3]:
    st.title("💵 Expenses and Financial Summary")

    # 1) Load expenses from Google Sheets CSV export
    sheet_id   = "1I5mGFcWbWdK6YQrJtabTg_g-XBEVaIRK1aMFm72vDEM"
    sheet_csv  = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        df_expenses = pd.read_csv(sheet_csv)
        df_expenses.columns = [c.strip().lower().replace(" ", "_") for c in df_expenses.columns]
        st.success("✅ Loaded expenses from Google Sheets.")
    except Exception as e:
        st.error(f"❌ Could not load expenses sheet: {e}")
        df_expenses = pd.DataFrame(columns=["type", "item", "amount", "date"])

    # 2) Add new expense via form
    with st.form("add_expense_form"):
        exp_type   = st.selectbox("Type", ["Bill","Rent","Salary","Marketing","Other"])
        exp_item   = st.text_input("Expense Item")
        exp_amount = st.number_input("Amount (GHS)", min_value=0.0, step=1.0)
        exp_date   = st.date_input("Date", value=date.today())
        submit     = st.form_submit_button("Add Expense")
        if submit and exp_item and exp_amount > 0:
            new_row = {"type": exp_type, "item": exp_item, "amount": exp_amount, "date": exp_date}
            df_expenses = pd.concat([df_expenses, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"✅ Recorded: {exp_type} – {exp_item}")
            st.experimental_rerun()

    # 3) Display all expenses with pagination
    st.write("### All Expenses")
    ROWS_PER_PAGE = 10
    total_rows    = len(df_expenses)
    total_pages   = (total_rows - 1) // ROWS_PER_PAGE + 1
    page = st.number_input(
        f"Page (1-{total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="exp_page"
    ) if total_pages > 1 else 1
    start = (page - 1) * ROWS_PER_PAGE
    end   = start + ROWS_PER_PAGE
    st.dataframe(df_expenses.iloc[start:end].reset_index(drop=True), use_container_width=True)

    # 4) Expense summary
    total_expenses = df_expenses["amount"].sum() if not df_expenses.empty else 0.0
    st.info(f"💸 **Total Expenses:** GHS {total_expenses:,.2f}")

    # 5) Export to CSV
    csv_data = df_expenses.to_csv(index=False)
    st.download_button(
        "📁 Download Expenses CSV",
        data=csv_data,
        file_name="expenses_data.csv",
        mime="text/csv"
    )


# --- Tab 4: WhatsApp Reminders for Debtors (with Expenses) ---
with tabs[4]:
    st.title("📲 WhatsApp Reminders for Debtors")

    # 1) Load Expenses from Google Sheets
    exp_sheet_id = "1I5mGFcWbWdK6YQrJtabTg_g-XBEVaIRK1aMFm72vDEM"
    exp_csv_url  = f"https://docs.google.com/spreadsheets/d/{exp_sheet_id}/export?format=csv"
    try:
        df_exp = pd.read_csv(exp_csv_url)
        df_exp.columns = [c.strip().lower().replace(" ", "_") for c in df_exp.columns]
        total_expenses = pd.to_numeric(df_exp.get("amount", []), errors="coerce").fillna(0).sum()
    except Exception:
        total_expenses = 0.0

    # 2) Load Students
    df = load_student_data(student_file, google_csv, github_csv)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    col_map = {c.replace("_", ""): c for c in df.columns}
    def col_lookup(key):
        return col_map.get(key.strip().lower().replace(" ", "_").replace("_", ""), key)

    cs  = col_lookup("contractstart")
    paid = col_lookup("paid")
    bal  = col_lookup("balance")

    # Parse dates & amounts
    df[cs]   = pd.to_datetime(df.get(cs, pd.NaT), errors="coerce").fillna(pd.Timestamp.today())
    df[paid] = pd.to_numeric(df.get(paid, 0), errors="coerce").fillna(0)
    df[bal]  = pd.to_numeric(df.get(bal, 0), errors="coerce").fillna(0)

    # 3) Financial Metrics
    total_collected = df[paid].sum()
    net_profit      = total_collected - total_expenses

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Students", len(df))
    m2.metric("Total Collected (GHS)", f"{total_collected:,.2f}")
    m3.metric("Total Expenses (GHS)",  f"{total_expenses:,.2f}")
    m4.metric("Net Profit (GHS)",      f"{net_profit:,.2f}")

    st.markdown("---")

    # 4) Filters
    search = st.text_input("Search by name or code", key="wa_search")
    lvl    = col_lookup("level")
    if lvl in df.columns:
        opts     = ["All"] + sorted(df[lvl].dropna().unique().tolist())
        selected = st.selectbox("Filter by Level", opts, key="wa_level")
    else:
        selected = "All"

    # 5) Compute Due Dates
    df["due_date"]  = df[cs] + timedelta(days=30)
    df["days_left"] = (df["due_date"] - pd.Timestamp.today()).dt.days.astype(int)

    # 6) Identify Debtors
    filt = df[df[bal] > 0]
    if search:
        mask1 = filt[col_lookup("name")].str.contains(search, case=False, na=False)
        mask2 = filt[col_lookup("studentcode")].str.contains(search, case=False, na=False)
        filt  = filt[mask1 | mask2]
    if selected != "All":
        filt = filt[filt[lvl] == selected]

    st.markdown("---")

    if filt.empty:
        st.success("✅ No students currently owing a balance.")
    else:
        st.metric("Number of Debtors", len(filt))
        tbl_cols = [col_lookup("name"), lvl, bal, "due_date", "days_left"]
        tbl = filt[tbl_cols].rename(columns={
            col_lookup("name"): "Name",
            lvl:                 "Level",
            bal:                 "Balance (GHS)",
            "due_date":          "Due Date",
            "days_left":         "Days Until Due"
        })
        st.dataframe(tbl, use_container_width=True)

        # 7) Build WhatsApp links
        def clean_phone(s):
            p = s.astype(str).str.replace(r"[+\- ]", "", regex=True)
            p = p.where(~p.str.startswith("0"), "233" + p.str[1:])
            return p.str.extract(r"(\d+)")[0]

        ws = filt.assign(
            phone    = clean_phone(filt[col_lookup("phone")]),
            due_str  = filt["due_date"].dt.strftime("%d %b %Y"),
            bal_str  = filt[bal].map(lambda x: f"GHS {x:.2f}"),
            days     = filt["days_left"].astype(int)
        )

        def make_link(row):
            if row.days >= 0:
                msg = f"You have {row.days} {'day' if row.days==1 else 'days'} left to settle the {row.bal_str} balance."
            else:
                od = abs(row.days)
                msg = f"Your payment is overdue by {od} {'day' if od==1 else 'days'}. Please settle as soon as possible."
            text = (
                f"Hi {row[col_lookup('name')]}! Friendly reminder: your payment for the {row[lvl]} class "
                f"is due by {row.due_str}. {msg} Thank you!"
            )
            return f"https://wa.me/{row.phone}?text={urllib.parse.quote(text)}"

        ws["link"] = ws.apply(make_link, axis=1)
        for nm, lk in ws[[col_lookup("name"), "link"]].itertuples(index=False):
            st.markdown(f"- **{nm}**: [Send Reminder]({lk})")

        dl = ws[[col_lookup("name"), "link"]].rename(columns={
            col_lookup("name"): "Name", "link": "WhatsApp URL"
        })
        st.download_button(
            "📁 Download Reminder Links CSV",
            dl.to_csv(index=False).encode("utf-8"),
            file_name="debtor_whatsapp_links.csv",
            mime="text/csv"
        )

# === Tab 5: Generate Contract & Receipt PDF for Any Student ===
with tabs[5]:
    pass

# --- Tab 5: Generate Contract & Receipt PDF for Any Student ---
with tabs[5]:
    pass

# === AGREEMENT TEMPLATE STATE ===
if "agreement_template" not in st.session_state:
    st.session_state["agreement_template"] = """
PAYMENT AGREEMENT

This Payment Agreement is entered into on [DATE] for [CLASS] students of Learn Language Education Academy and Felix Asadu ("Teacher").

Terms of Payment:
1. Payment Amount: The student agrees to pay the teacher a total of [AMOUNT] cedis for the course.
2. Payment Schedule: The payment can be made in full or in two installments: GHS [FIRST_INSTALLMENT] for the first installment, and the remaining balance for the second installment after one month of payment. 
3. Late Payments: In the event of late payment, the school may revoke access to all learning platforms. No refund will be made.
4. Refunds: Once a deposit is made and a receipt is issued, no refunds will be provided.

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

# --- Tab 5: Generate & Edit Receipt/Contract PDF ---
with tabs[5]:
    st.title("📄 Generate Contract & Receipt PDF for Any Student")

    # Local file and GitHub backup URL
    student_file = "students.csv"
    github_csv   = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"

    # 1) Load students DataFrame (local → GitHub fallback)
    try:
        df = pd.read_csv(student_file)
    except FileNotFoundError:
        df = pd.read_csv(github_csv)
        st.info("Loaded students from GitHub backup.")

    # 2) Normalize columns to lowercase/underscores
    df.columns = [
        c.strip()
         .replace(" ", "_")
         .replace("(", "")
         .replace(")", "")
         .replace("-", "_")
         .replace("/", "_")
         .lower()
        for c in df.columns
    ]

    if df.empty:
        st.warning("No student data available.")
    else:
        # Helper to find actual column names
        def col_lookup(col):
            for c in df.columns:
                if c.replace("_", "").lower() == col.replace("_", "").lower():
                    return c
            return None

        name_col    = col_lookup("name")
        start_col   = col_lookup("contractstart")
        end_col     = col_lookup("contractend")
        paid_col    = col_lookup("paid")
        bal_col     = col_lookup("balance")
        code_col    = col_lookup("studentcode")
        phone_col   = col_lookup("phone")
        level_col   = col_lookup("level")

        # 3) Select student
        student_names = df[name_col].tolist()
        selected_name = st.selectbox("Select Student", student_names)
        row = df[df[name_col] == selected_name].iloc[0]

        # 4) Editable fields before generation
        default_paid    = float(row.get(paid_col, 0))
        default_balance = float(row.get(bal_col, 0))
        default_start = pd.to_datetime(row.get(start_col, ""), errors="coerce").date() if not pd.isnull(pd.to_datetime(row.get(start_col, ""), errors="coerce")) else date.today()
        default_end   = pd.to_datetime(row.get(end_col,   ""), errors="coerce").date() if not pd.isnull(pd.to_datetime(row.get(end_col,   ""), errors="coerce")) else default_start + timedelta(days=30)

        st.subheader("Receipt Details")
        paid_input = st.number_input(
            "Amount Paid (GHS)", min_value=0.0, value=default_paid, step=1.0, key="paid_input"
        )
        balance_input = st.number_input(
            "Balance Due (GHS)", min_value=0.0, value=default_balance, step=1.0, key="balance_input"
        )
        total_input = paid_input + balance_input
        receipt_date = st.date_input("Receipt Date", value=date.today(), key="receipt_date")
        signature = st.text_input("Signature Text", value="Felix Asadu", key="receipt_signature")

        st.subheader("Contract Details")
        contract_start_input = st.date_input(
            "Contract Start Date", value=default_start, key="contract_start_input"
        )
        contract_end_input = st.date_input(
            "Contract End Date", value=default_end, key="contract_end_input"
        )
        course_length = (contract_end_input - contract_start_input).days

        st.subheader("Logo (optional)")
        logo_file = st.file_uploader(
            "Upload logo image", type=["png", "jpg", "jpeg"], key="logo_upload"
        )

        # 5) Generate PDF on button click
        if st.button("Generate & Download PDF"):
            # Re-load CSV to get latest
            try:
                df_latest = pd.read_csv(student_file)
            except FileNotFoundError:
                df_latest = pd.read_csv(github_csv)
            df_latest.columns = [c.strip().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_").replace("/", "_").lower() for c in df_latest.columns]
            row = df_latest[df_latest[name_col] == selected_name].iloc[0]

            # Use inputs
            paid    = paid_input
            balance = balance_input
            total   = total_input
            contract_start = contract_start_input
            contract_end   = contract_end_input

            # Build PDF
            pdf = FPDF()
            pdf.add_page()

            # Add logo if provided: preserve original extension
            if logo_file:
                ext = logo_file.name.split('.')[-1]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                tmp.write(logo_file.getbuffer())
                tmp.close()
                pdf.image(tmp.name, x=10, y=8, w=33)
                pdf.ln(25)

            # Payment status banner: if balance==0 fully paid
            status = "FULLY PAID" if balance == 0 else "INSTALLMENT PLAN"
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(0, 128, 0)
            pdf.cell(0, 10, status, ln=True, align="C")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(5)

            # Receipt header
            pdf.set_font("Arial", size=14)
            pdf.cell(0, 10, f"{SCHOOL_NAME} Payment Receipt", ln=True, align="C")
            pdf.ln(10)

            # Receipt details
            pdf.set_font("Arial", size=12)
            for label, val in [
                ("Name",           selected_name),
                ("Student Code",   row.get(code_col, "")),
                ("Phone",          row.get(phone_col, "")),
                ("Level",          row.get(level_col, "")),
                ("Contract Start", contract_start),
                ("Contract End",   contract_end),
                ("Amount Paid",    f"GHS {paid:.2f}"),
                ("Balance Due",    f"GHS {balance:.2f}"),
                ("Total Fee",      f"GHS {total:.2f}"),
                ("Receipt Date",   receipt_date)
            ]:
                pdf.cell(0, 8, f"{label}: {val}", ln=True)
            pdf.ln(10)

            # Contract section
            pdf.ln(15)
            pdf.set_font("Arial", size=14)
            pdf.cell(0, 10, f"{SCHOOL_NAME} Student Contract", ln=True, align="C")
            pdf.set_font("Arial", size=12)
            pdf.ln(8)

            template = st.session_state.get("agreement_template", "")
            filled = (
                template
                .replace("[STUDENT_NAME]",     selected_name)
                .replace("[DATE]",             str(receipt_date))
                .replace("[CLASS]",            row.get(level_col, ""))
                .replace("[AMOUNT]",           str(total))
                .replace("[FIRST_INSTALLMENT]", f"{paid:.2f}")
                .replace("[SECOND_INSTALLMENT]",f"{balance:.2f}")
                .replace("[SECOND_DUE_DATE]",  str(contract_end))
                .replace("[COURSE_LENGTH]",    f"{course_length} days")
            )
            for line in filled.split("\n"):
                safe = line.encode("latin-1", "replace").decode("latin-1")
                pdf.multi_cell(0, 8, safe)
            pdf.ln(10)

            # Signature
            pdf.cell(0, 8, f"Signed: {signature}", ln=True)

            # Download
            pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
            st.download_button(
                "📄 Download PDF",
                data=pdf_bytes,
                file_name=f"{selected_name.replace(' ', '_')}_receipt_contract.pdf",
                mime="application/pdf"
            )
            st.success("✅ PDF generated and ready to download.")


with tabs[7]:
    st.title("📊 Analytics & Export")

    if os.path.exists("students_simple.csv"):
        df_main = pd.read_csv("students_simple.csv")
    else:
        df_main = pd.DataFrame()

    st.subheader("📈 Enrollment Over Time")

    if not df_main.empty and "ContractStart" in df_main.columns:
        df_main["EnrollDate"] = pd.to_datetime(df_main["ContractStart"], errors="coerce")

        # ✅ Filter by year
        valid_years = df_main["EnrollDate"].dt.year.dropna().unique()
        valid_years = sorted([int(y) for y in valid_years if not pd.isna(y)])
        selected_year = st.selectbox("📆 Filter by Year", valid_years) if valid_years else None

        if df_main["EnrollDate"].notna().sum() == 0:
            st.info("No valid enrollment dates found in 'ContractStart'. Please check your data.")
        else:
            try:
                filtered_df = df_main[df_main["EnrollDate"].dt.year == selected_year] if selected_year else df_main
                monthly = (
                    filtered_df.groupby(filtered_df["EnrollDate"].dt.to_period("M"))
                    .size()
                    .reset_index(name="Count")
                )
                monthly["EnrollDate"] = monthly["EnrollDate"].astype(str)
                st.line_chart(monthly.set_index("EnrollDate")["Count"])
            except Exception as e:
                st.warning(f"⚠️ Unable to generate enrollment chart: {e}")
    else:
        st.info("No enrollment data to visualize.")

    st.subheader("📊 Students by Level")

    if "Level" in df_main.columns and not df_main["Level"].dropna().empty:
        level_counts = df_main["Level"].value_counts()
        st.bar_chart(level_counts)
    else:
        st.info("No level information available to display.")

    st.subheader("⬇️ Export CSV Files")

    student_csv = df_main.to_csv(index=False)
    st.download_button("📁 Download Students CSV", data=student_csv, file_name="students_data.csv")

    expenses_file = "expenses_all.csv"
    if os.path.exists(expenses_file):
        exp_data = pd.read_csv(expenses_file)
        expense_csv = exp_data.to_csv(index=False)
        st.download_button("📁 Download Expenses CSV", data=expense_csv, file_name="expenses_data.csv")
    else:
        st.info("No expenses file found to export.")

with tabs[8]:

    # ---- Helper for safe PDF encoding ----
    def safe_pdf(text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    st.markdown("""
    <div style='background:#e3f2fd;padding:1.2em 1em 0.8em 1em;border-radius:12px;margin-bottom:1em'>
      <h2 style='color:#1565c0;'>📆 <b>Intelligenter Kursplan-Generator (A1, A2, B1)</b></h2>
      <p style='font-size:1.08em;color:#333'>Erstellen Sie einen vollständigen, individuell angepassten Kursplan zum Download (TXT oder PDF) – <b>mit Ferien und flexiblem Wochenrhythmus!</b></p>
    </div>
    """, unsafe_allow_html=True)

    # ---- Schedule templates ----
    raw_schedule_a1 = [
        ("Week One", ["Chapter 0.1 - Lesen & Horen"]),
        ("Week Two", [
            "Chapters 0.2 and 1.1 - Lesen & Horen",
            "Chapter 1.1 - Schreiben & Sprechen and Chapter 1.2 - Lesen & Horen",
            "Chapter 2 - Lesen & Horen"
        ]),
        ("Week Three", [
            "Chapter 1.2 - Schreiben & Sprechen (Recap)",
            "Chapter 2.3 - Schreiben & Sprechen",
            "Chapter 3 - Lesen & Horen"
        ]),
        ("Week Four", [
            "Chapter 4 - Lesen & Horen",
            "Chapter 5 - Lesen & Horen",
            "Chapter 6 - Lesen & Horen and Chapter 2.4 - Schreiben & Sprechen"
        ]),
        ("Week Five", [
            "Chapter 7 - Lesen & Horen",
            "Chapter 8 - Lesen & Horen",
            "Chapter 3.5 - Schreiben & Sprechen"
        ]),
        ("Week Six", [
            "Chapter 3.6 - Schreiben & Sprechen",
            "Chapter 4.7 - Schreiben & Sprechen",
            "Chapter 9 and 10 - Lesen & Horen"
        ]),
        ("Week Seven", [
            "Chapter 11 - Lesen & Horen",
            "Chapter 12.1 - Lesen & Horen and Schreiben & Sprechen (including 5.8)",
            "Chapter 5.9 - Schreiben & Sprechen"
        ]),
        ("Week Eight", [
            "Chapter 6.10 - Schreiben & Sprechen (Intro to letter writing)",
            "Chapter 13 - Lesen & Horen and Chapter 6.11 - Schreiben & Sprechen",
            "Chapter 14.1 - Lesen & Horen and Chapter 7.12 - Schreiben & Sprechen"
        ]),
        ("Week Nine", [
            "Chapter 14.2 - Lesen & Horen and Chapter 7.12 - Schreiben & Sprechen",
            "Chapter 8.13 - Schreiben & Sprechen",
            "Exam tips - Schreiben & Sprechen recap"
        ])
    ]
    raw_schedule_a2 = [
        ("Woche 1", ["1.1. Small Talk (Exercise)", "1.2. Personen Beschreiben (Exercise)", "1.3. Dinge und Personen vergleichen"]),
        ("Woche 2", ["2.4. Wo möchten wir uns treffen?", "2.5. Was machst du in deiner Freizeit?"]),
        ("Woche 3", ["3.6. Möbel und Räume kennenlernen", "3.7. Eine Wohnung suchen (Übung)", "3.8. Rezepte und Essen (Exercise)"]),
        ("Woche 4", ["4.9. Urlaub", "4.10. Tourismus und Traditionelle Feste", "4.11. Unterwegs: Verkehrsmittel vergleichen"]),
        ("Woche 5", ["5.12. Ein Tag im Leben (Übung)", "5.13. Ein Vorstellungsgesprach (Exercise)", "5.14. Beruf und Karriere (Exercise)"]),
        ("Woche 6", ["6.15. Mein Lieblingssport", "6.16. Wohlbefinden und Entspannung", "6.17. In die Apotheke gehen"]),
        ("Woche 7", ["7.18. Die Bank Anrufen", "7.19. Einkaufen – Wo und wie? (Exercise)", "7.20. Typische Reklamationssituationen üben"]),
        ("Woche 8", ["8.21. Ein Wochenende planen", "8.22. Die Woche Plannung"]),
        ("Woche 9", ["9.23. Wie kommst du zur Schule / zur Arbeit?", "9.24. Einen Urlaub planen", "9.25. Tagesablauf (Exercise)"]),
        ("Woche 10", ["10.26. Gefühle in verschiedenen Situationen beschr", "10.27. Digitale Kommunikation", "10.28. Über die Zukunft sprechen"])
    ]
    raw_schedule_b1 = [
        ("Woche 1", ["1.1. Traumwelten (Übung)", "1.2. Freundes für Leben (Übung)", "1.3. Erfolgsgeschichten (Übung)"]),
        ("Woche 2", ["2.4. Wohnung suchen (Übung)", "2.5. Der Besichtigungsg termin (Übung)", "2.6. Leben in der Stadt oder auf dem Land?"]),
        ("Woche 3", ["3.7. Fast Food vs. Hausmannskost", "3.8. Alles für die Gesundheit", "3.9. Work-Life-Balance im modernen Arbeitsumfeld"]),
        ("Woche 4", ["4.10. Digitale Auszeit und Selbstfürsorge", "4.11. Teamspiele und Kooperative Aktivitäten", "4.12. Abenteuer in der Natur", "4.13. Eigene Filmkritik schreiben"]),
        ("Woche 5", ["5.14. Traditionelles vs. digitales Lernen", "5.15. Medien und Arbeiten im Homeoffice", "5.16. Prüfungsangst und Stressbewältigung", "5.17. Wie lernt man am besten?"]),
        ("Woche 6", ["6.18. Wege zum Wunschberuf", "6.19. Das Vorstellungsgespräch", "6.20. Wie wird man …? (Ausbildung und Qu)"]),
        ("Woche 7", ["7.21. Lebensformen heute – Familie, Wohnge", "7.22. Was ist dir in einer Beziehung wichtig?", "7.23. Erstes Date – Typische Situationen"]),
        ("Woche 8", ["8.24. Konsum und Nachhaltigkeit", "8.25. Online einkaufen – Rechte und Risiken"]),
        ("Woche 9", ["9.26. Reiseprobleme und Lösungen"]),
        ("Woche 10", ["10.27. Umweltfreundlich im Alltag", "10.28. Klimafreundlich leben"])
    ]

    # ---- Step 1: Course level ----
    st.markdown("### 1️⃣ **Kursniveau wählen**")
    course_levels = {"A1": raw_schedule_a1, "A2": raw_schedule_a2, "B1": raw_schedule_b1}
    selected_level = st.selectbox("🗂️ **Kursniveau (A1/A2/B1):**", list(course_levels.keys()))
    topic_structure = course_levels[selected_level]
    st.markdown("---")

    # ---- Step 2: Basic info & breaks ----
    st.markdown("### 2️⃣ **Kursdaten, Ferien, Modus**")
    col1, col2 = st.columns([2,1])
    with col1:
        start_date = st.date_input("📅 **Kursstart**", value=date.today())
        holiday_dates = st.date_input("🔔 Ferien oder Feiertage (Holiday/Break Dates)", [], help="Kein Unterricht an diesen Tagen.")
    with col2:
        advanced_mode = st.toggle("⚙️ Erweiterter Wochen-Rhythmus (Custom weekly pattern)", value=False)
    st.markdown("---")

    # ---- Step 3: Weekly pattern ----
    st.markdown("### 3️⃣ **Unterrichtstage festlegen**")
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    default_days = ["Monday", "Tuesday", "Wednesday"]

    week_patterns = []
    if not advanced_mode:
        days_per_week = st.multiselect("📌 **Unterrichtstage wählen:**", options=days_of_week, default=default_days)
        for _ in topic_structure:
            week_patterns.append((len(_[1]), days_per_week))
    else:
        st.info("Für jede Woche individuelle Unterrichtstage einstellen.")
        for i, (week_label, sessions) in enumerate(topic_structure):
            with st.expander(f"{week_label}", expanded=True):
                week_days = st.multiselect(f"Unterrichtstage {week_label}", options=days_of_week, default=default_days, key=f"week_{i}_days")
                week_patterns.append((len(sessions), week_days or default_days))
    st.markdown("---")

    # ---- Generate dates skipping holidays ----
    total_sessions = sum(wp[0] for wp in week_patterns)
    session_labels = [(w, s) for w, sess in topic_structure for s in sess]
    dates = []
    cur = start_date
    for num_classes, week_days in week_patterns:
        week_dates = []
        while len(week_dates) < num_classes:
            if cur.strftime("%A") in week_days and cur not in holiday_dates:
                week_dates.append(cur)
            cur += timedelta(days=1)
        dates.extend(week_dates)

    if len(dates) < total_sessions:
        st.error("⚠️ **Nicht genug Unterrichtstage!** Passen Sie Ferien/Modus an.")

    # ---- Preview ----
    rows = [{"Week": wl, "Day": f"Day {i+1}", "Date": d.strftime("%A, %d %B %Y"), "Topic": tp}
            for i, ((wl, tp), d) in enumerate(zip(session_labels, dates))]
    df = pd.DataFrame(rows)
    st.markdown(f"""
    <div style='background:#fffde7;border:1px solid #ffe082;border-radius:10px;padding:1em;margin:1em 0'>
      <b>📝 Kursüberblick:</b>
      <ul>
        <li><b>Kurs:</b> {selected_level}</li>
        <li><b>Start:</b> {start_date.strftime('%A, %d %B %Y')}</li>
        <li><b>Sessions:</b> {total_sessions}</li>
        <li><b>Ferien:</b> {', '.join(d.strftime('%d.%m.%Y') for d in holiday_dates) or '–'}</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown("---")

    # ---- Filenames ----
    file_date = start_date.strftime("%Y-%m-%d")
    file_prefix = f"{selected_level}_{file_date}_course_schedule"

    # ---- TXT download ----
    txt = f"Learn Language Education Academy\nContact: 0205706589 | www.learngermanghana.com\nSchedule: {selected_level}\nStart: {start_date.strftime('%Y-%m-%d')}\n\n" + \
          "\n".join(f"- {r['Day']} ({r['Date']}): {r['Topic']}" for r in rows)
    st.download_button("📁 TXT Download", txt, file_name=f"{file_prefix}.txt")

    # ---- PDF download ----
    class ColorHeaderPDF(FPDF):
        def header(self):
            self.set_fill_color(21, 101, 192)
            self.set_text_color(255,255,255)
            self.set_font('Arial','B',14)
            self.cell(0,12,safe_pdf("Learn Language Education Academy – Course Schedule"),ln=1,align='C',fill=True)
            self.ln(2)
            self.set_text_color(0,0,0)

    pdf = ColorHeaderPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0,8, safe_pdf(f"Schedule: {selected_level}"))
    pdf.multi_cell(0,8, safe_pdf(f"Start: {start_date.strftime('%Y-%m-%d')}"))
    if holiday_dates:
        pdf.multi_cell(0,8, safe_pdf("Holidays: " + ", ".join(d.strftime("%d.%m.%Y") for d in holiday_dates)))
    pdf.ln(2)
    for r in rows:
        pdf.multi_cell(0,8, safe_pdf(f"{r['Day']} ({r['Date']}): {r['Topic']}"))
    pdf.ln(6)
    pdf.set_font("Arial",'I',11)
    pdf.cell(0,10, safe_pdf("Signed: Felix Asadu"), ln=1, align='R')

    st.download_button("📄 PDF Download",
                       data=pdf.output(dest='S').encode('latin-1'),
                       file_name=f"{file_prefix}.pdf",
                       mime="application/pdf")

with tabs[9]:
    st.title("📝 Assignment Marking & Scores")

    import sqlite3
    # === Initialize SQLite for Scores ===
    conn_scores = sqlite3.connect('scores.db')
    cursor_scores = conn_scores.cursor()
    cursor_scores.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            StudentCode TEXT,
            Name TEXT,
            Assignment TEXT,
            Score REAL,
            Comments TEXT,
            Date TEXT
        )
    ''')
    conn_scores.commit()

    # --- Load student database ---
    github_csv_url = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
    student_file = "students.csv"
    if os.path.exists(student_file):
        df_students = pd.read_csv(student_file)
    else:
        try:
            df_students = pd.read_csv(github_csv_url)
        except Exception:
            st.warning("Could not find student data. Please upload students.csv in 📝 Pending tab.")
            st.stop()
    df_students.columns = [c.lower().strip().replace(" ", "_") for c in df_students.columns]

    # --- Filter/Search Students ---
    st.subheader("🔍 Filter/Search Students")
    search_term = st.text_input("Search by name or code", key="search_term")
    levels = ["All"] + sorted(df_students['level'].dropna().unique().tolist())
    selected_level = st.selectbox("Filter by Level", levels, key="selected_level")
    view_df = df_students.copy()
    if search_term:
        view_df = view_df[
            view_df['name'].str.contains(search_term, case=False, na=False) |
            view_df['studentcode'].astype(str).str.contains(search_term, case=False, na=False)
        ]
    if selected_level != "All":
        view_df = view_df[view_df['level'] == selected_level]
    if view_df.empty:
        st.info("No students match your filter.")
        st.stop()

    # --- Select Student ---
    student_list = view_df['name'] + " (" + view_df['studentcode'] + ")"
    chosen = st.selectbox("Select a student", student_list, key="chosen_student")
    code = chosen.split("(")[-1].replace(")", "").strip().lower()
    student_row = view_df[view_df['studentcode'].str.lower() == code].iloc[0]

                    # --- Reference Answers ---
    ref_answers = {
        "Lesen und Horen 0.1": [
            "1. C) Guten Morgen", "2. D) Guten Tag", "3. B) Guten Abend", "4. B) Gute Nacht", "5. C) Guten Morgen", "6. C) Wie geht es Ihnen?", "7. B) Auf Wiedersehen",
            "8. C) Tschüss", "9. C) Guten Abend", "10. D) Gute Nacht"
        ],
        "Lesen und Horen 0.2": [
            "1. C) 26", "2. A) A, O, U, B", "3. A) Eszett", "4. A) K", "5. A) A-Umlaut", "6. A) A, O, U, B", "7. B) 4",
            "",  # blank line
            "Wasser", "Kaffee", "Blume", "Schule", "Tisch"
        ],
        "Lesen und Horen 1.1": ["1. C", "2. C", "3. A", "4. B"],
        "Lesen und Hören 1.2": [
            "1. Ich heiße Anna", "2. Du heißt Max", "3. Er heißt Peter", "4. Wir kommen aus Italien", "5. Ihr kommt aus Brasilien", "6. Sie kommen aus Russland",
            "7. Ich wohne in Berlin", "8. Du wohnst in Madrid", "9. Sie wohnt in Wien",
            "",  # blank line
            "1. A) Anna", "2. C) Aus Italien", "3. D) In Berlin", "4. B) Tom", "5. A) In Berlin"
        ],
        "Lesen und Horen 2": [
            "1. A) sieben", "2. B) Drei", "3. B) Sechs", "4. B) Neun", "5. B) Sieben", "6. C) Fünf", "6. B) zweihundertzweiundzwanzig ", "7.  B) zweihundertzweiundzwanzig ",
            "8.  B) zweihundertzweiundzwanzig ", "9.  A) zweitausendvierzig ", "10. A) funftausendfunfhundertneun ",
            "",  # blank line
            "1.  16 – sechzehn ", "2. 98 – achtundneunzig", "3. 555 – funfhundertfunfundfunfzig", "3. 1020 – tausendzwanzig", "3. 8553 – achttausendfunfhundertdreiundfundzig"
        ],
        "Lesen und Horen 3": [ 
            "1. Es kostet 20 Euro", "2. Sie kostet  15 Euro", "3. Es kostet 25,000 Euro", "4. Er kostet 50 Euro", "5. Sie kostet 100 Euro",       
        ],
        "Lesen und Horen 4": [
            "1. C) Neun", "2. B) Polnisch", "3. D) Niederländisch", "4. A) Deutsch", "5. C) Paris", "6. B) Amsterdam", "7. C) In der Schweiz",
            "",  # blank line
            "1. C) In Italien und Frankreich", "2. C) Rom", "3. B) Das Essen", "4. B) Paris", "5. A) Nach Spanien"
        ],
        "Lesen und Horen 5": [
            # Part 1 – Vocabulary Review
            "Der Tisch – the table",
            "Die Lampe – the lamp",
            "Das Buch – the book",
            "Der Stuhl – the chair",
            "Die Katze – the cat",
            "Das Auto – the car",
            "Der Hund – the dog",
            "Die Blume – the flower",
            "Das Fenster – the window",
            "Der Computer – the computer",
            "",  # blank line
            # Part 2 – Nominative Case
            "1. Der Tisch ist groß",
            "2. Die Lampe ist neu",
            "3. Das Buch ist interessant",
            "4. Der Stuhl ist bequem",
            "5. Die Katze ist süß",
            "6. Das Auto ist schnell",
            "7. Der Hund ist freundlich",
            "8. Die Blume ist schön",
            "9. Das Fenster ist offen",
            "10. Der Computer ist teuer",
            "",  # blank line
            # Part 3 – Accusative Case
            "1. Ich sehe den Tisch",
            "2. Sie kauft die Lampe",
            "3. Er liest das Buch",
            "4. Wir brauchen den Stuhl",
            "5. Du fütterst die Katze",
            "6. Ich fahre das Auto",
            "7. Sie streichelt den Hund",
            "8. Er pflückt die Blume",
            "9. Wir putzen das Fenster",
            "10. Sie benutzen den Computer"
        ],
        "Lesen und Horen 6": [
            "Das Wohnzimmer – the living room", "Die Küche – the kitchen", "Das Schlafzimmer – the bedroom", "Das Badezimmer – the bathroom", "Der Balkon – the balcony",
            "",  # blank line
            "Der Flur – the hallway", "Das Bett – the bed", "Der Tisch – the table", "Der Stuhl – the chair", "Der Schrank – the wardrobe",
            "",  # blank line
            "1. B) Vier", "2. A) Ein Sofa und ein Fernseher", "3. B) Einen Herd, einen Kühlschrank und einen Tisch mit vier Stühlen", "4. C) Ein großes Bett", "5. D) Eine Dusche, eine Badewanne und ein Waschbecken",    
            "6. D) Klein und schön", "7. C) Blumen und einen kleinen Tisch mit zwei Stühlen"
            "",  # blank line
            " 1. B", " 2.  B", " 3. B", " 4. C", " 5. D", " 6. B", " 7. C"
        ],
        "Lesen und Horen 7": [
            "1. B) Um sieben Uhr", "2. B) Um acht Uhr", "3. B) Um sechs Uhr", "4. B) Um zehn Uhr", "5. B) Um neun Uhr",
            "",  # blank line
            "6. C) Nachmittags", "7. A) Um sieben Uhr", "8. A) Montag", "9. B) Am Dienstag und Donnerstag", "10. B) Er ruht sich aus",
            "",  # blank line
            "1. B) Um neun Uhr", "2. B) Er geht in die Bibliothek", "3. B) Bis zwei Uhr nachmittags", "4. B) Um drei Uhr nachmittags", "5. A)",
            "",  # blank line
            "6. B) Um neun Uhr", "7. B) Er geht in die Bibliothek", "8. B) Bis zwei Uhr nachmittags", "9. B) Um drei Uhr nachmittags", "10. B) Um sieben Uhr"
        ],
        "Lesen und Horen 8": [
            "1. B) Zwei Uhr nachmittags", "2. B) 29 Tage", "3. B) April", "4. C) 03.02.2024", "5. C) Mittwoch",
            "",  # blank line
            "1. Falsch", "2. Richtig", "3. Richtig", "4. Falsch", "5. Richtig",
            "",  # blank line
            "1. B) Um Mitternacht", "2. B) Vier Uhr nachmittags", "3. C) 28 Tage", "4. B) Tag. Monat. Jahr", "5. D) Montag"
        ],
        "Lesen und Horen 9": [
            "1. B) Apfel und Karotten", "2. C) Karotten", "3. A) Weil er Vegetarier ist", "4. C) Käse", "5. B) Fleisch",
            "",  # blank line
            "6. B) Kekse", "7. A) Käse", "8. C) Kuchen", "9. C) Schokolade", "10. B) Der Bruder des Autors",
            "",  # blank line
            "1. A) Apfel, Bananen und Karotten", "2. A) Müsli mit Joghurt", "3. D) Karotten", "4. A) Käse", "5. C) Schokoladenkuchen"
        ],
        "Lesen und Horen 10": [
            "1. Falsch", "2. Wahr", "3. Falsch", "4. Wahr", "5. Wahr", "6. Falsch", "7. Wahr", "8. Falsch", "9. Falsch", "10. Falsch",
            "",  # blank line
            "1. B) Einmal pro Woche", "2. C) Apfel und Bananen", "3. A) Ein halbes Kilo", "4. B) 10 Euro", "5. B) Einen schönen Tag"
        ],
        "Lesen und Horen 11": [
            "1. B) Entschuldigung, wo ist der Bahnhof?", "2. B) Links abbiegen", "3. B) Auf der rechten Seite, direkt neben dem großen Supermarkt",
            "4. B) Wie komme ich zur nächsten Apotheke?", "5. C) Gute Reise und einen schönen Tag noch",
            "",  # blank line
            "1. C) Wie komme ich zur nächsten Apotheke?", "2. C) Rechts abbiegen", "3. B) Auf der linken Seite, direkt neben der Bäckerei",
            "4. A) Gehen Sie geradeaus bis zur Kreuzung, dann links", "5. C) Einen schönen Tag noch",
            "",  # blank line
            "Fragen nach dem Weg: Entschuldigung, wie komme ich zum Bahnhof", "Die Straße überqueren: Überqueren Sie die Straße",
            "Geradeaus gehen: Gehen Sie geradeaus", "Links abbiegen: Biegen Sie links ab", "Rechts abbiegen: Biegen Sie rechts ab",
            "On the left side: Das Kino ist auf der linken Seite"
        ],
        "Lesen und Horen 12.1": [
            "1. B) Ärztin", "2. A) Weil sie keine Zeit hat", "3. B) Um 8 Uhr", "4. C) Viele verschiedene Fächer", "5. C) Einen Sprachkurs besuchen",
            "",  # blank line
            "1. B) Falsch", "2. B) Falsch", "3. B) Falsch", "4. B) Falsch", "5. B) Falsch",
            "",  # blank line
            "A) Richtig", "A) Richtig", "A) Richtig", "A) Richtig", "A) Richtig"
        ],
        "Lesen und Horen 12.2": [
            "In Berlin", "Mit seiner Frau und seinen drei Kindern", "Mit seinem Auto", "Um 7:30 Uhr", "Barzahlung (cash)",
            "",  # blank line
            "1. B) Um 9:00 Uhr", "2. B) Um 12:00 Uhr", "3. B) Um 18:00 Uhr", "4. B) Um 21:00 Uhr", "5. D) Alles Genannte",
            "",  # blank line
            "1. B) Um 9 Uhr", "2. B) Um 12 Uhr", "3. A) ein Computer und ein Drucker", "4. C) in einer Bar", "5. C) bar"
        ],
        "Lesen und Horen 13": [
            "A", "B", "A", "A", "B", "B",
            "",  # blank line
            "A", "B", "B",
            "",  # blank line
            "B", "B", "B"
        ],
        "Lesen und Horen 14.1": [
            "Anzeige A", "Anzeige B", "Anzeige B", "Anzeige A", "Anzeige A",
            "",  # blank line
            "C) Guten Tag, Herr Doktor", "B) Halsschmerzen und Fieber", "C) Seit gestern", "C) Kopfschmerzen und Müdigkeit", "A) Ich verschreibe Ihnen Medikamente",
            "",  # blank line
            "Kopf – Head", "Arm – Arm", "Bein – Leg", "Auge – Eye", "Nase – Nose", "Ohr – Ear", "Mund – Mouth", "Hand – Hand", "Fuß – Foot", "Bauch – Stomach"
        ],
        "A2 1.1 Small Talk": [
            "1. C) In einer Schule", "2. B) Weil sie gerne mit Kindern arbeitet", "3. A) In einem Büro", "4. B) Tennis", "5. B) Es war sonnig und warm", "6. B) Italien und Spanien", "7. C) Weil die Bäume so schön bunt sind"
            "",  # blank line     
            "1. B) Ins Kino gehen", "2. A) Weil sie spannende Geschichten liebt", "3. A) Tennis", "4. B) Es war sonnig und warm", "5. C) Einen Spaziergang machen"
        ],
        "A2 1.2 Personen Beschreiben": [
            "1. B) Ein Jahr", "2. B) Er ist immer gut gelaunt und organisiert", "3. C) Einen Anzug und eine Brille", "4. B) Er geht geduldig auf ihre Anliegen ein", "5. B) Weil er seine Mitarbeiter regelmäßig lobt", "6. A) Wenn eine Aufgabe nicht rechtzeitig erledigt wird", "7. B) Dass er fair ist und die Leistungen der Mitarbeiter wertschätzt"
            "",  # blank line 
            "1. B) Weil er","2. C) Sprachkurse","3. A) Jeden Tag"
        ],
        "A2 1.3 Dinge und Personen Beschreiben": [
            "1. B) Anna ist 25 Jahre alt", "2. B) In ihrer Freizeit liest Anna Bücher und geht spazieren", "3. C) Anna arbeitet in einem Krankenhaus", "4. C) Anna hat einen Hund", "5. B) Max unterrichtet Mathematik", "6. A) Max spielt oft Fußball mit seinen Freunden", "7. B) Am Wochenende machen Anna und Max Ausflüge oder"
            "",  # blank line 
            "1. B) Julia ist 26 Jahre alt", "2. c) Julia arbeitet als Architektin", "3. B) Tobias lebt in Frankfurt", "4. A) Tobias mochte ein eigenes Restaurant ", "5. B) Julia und Tobias kochen am Wochenende oft mit Sophie"           
        ],
        "A2 2.4 Wo möchten wir uns treffen?": [
            "1. B) faul sein", "2. D) Hockey spielen", "3. A) schwimmen gehen", "4. D) zum See fahren und dort im Zelt übernachten", "5. B) eine Route mit dem Zug durch das ganze Land", "1. B) Um 10 Uhr", "2. B) Eine Rucksack", "3. B) Ein Piknik", "4. C) in einem Restaurant", "5. A) Spielen und Spazieren gehen"
        ],
        "A2 2.5 Was machst du in deiner Freizeit?": [
            "1. c) Nudeln, Pizza und Salat", "2. c) Den grünen Salat", "3. c) Schokoladenkuchen und Tiramisu", "4. b) in den Bergen", "5. c) In bar"
            "",  # blank line
            "1. A)  Sie trinkt Tee", "2. B) Mensch aregre", "3. A) Sie geht jogeen ", "4. B) Die Suppe ist kalt", "5. B) Klassische Musik"           
        ],
        "A2 3.6 Mobel und Raume Kennenlernen?": [
            "1. b) Weil ich studiere", "2. b) Wenn es nicht regnet, sturmt ", "3. d) Es ist billig", "4. D) Haustiere", "5. C) Im Zoo"
            "",  # blank line
            "1. B", "2. A", "3. B ", "4. B", "5. B"           
        ],
    }

    # --- Load Scores from Google Sheet CSV ---
    scores_sheet_url = (
        "https://docs.google.com/spreadsheets/d/"
        "1l66qurVjKkgM3YCYGN3GURT-Q86DEeHql8BL_Z6YfCY/export?format=csv"
    )
    try:
        remote_df = pd.read_csv(scores_sheet_url)
    except Exception:
        st.warning("Could not load scores from Google Sheet. Using local database only.")
        remote_df = pd.DataFrame(columns=["StudentCode", "Name", "Assignment", "Score", "Comments", "Date"])

    # --- Load Scores from SQLite ---
    rows = cursor_scores.execute(
        "SELECT StudentCode, Name, Assignment, Score, Comments, Date FROM scores"
    ).fetchall()
    local_df = pd.DataFrame(rows, columns=["StudentCode", "Name", "Assignment", "Score", "Comments", "Date"])

        # --- Combine remote and local scores ---
    scores_df = pd.concat([remote_df, local_df], ignore_index=True)
    # Normalize and dedupe by date
    scores_df['Date'] = pd.to_datetime(scores_df['Date'], errors='coerce')
    scores_df = scores_df.sort_values('Date').drop_duplicates(subset=['StudentCode','Assignment','Date'], keep='last')
    scores_df['Date'] = scores_df['Date'].dt.strftime('%Y-%m-%d')
    # --- Assignment Input UI ---
    st.markdown("---")
    st.subheader(f"Record Assignment Score for {student_row['name']} ({student_row['studentcode']})")
    # Filter/search assignment titles
    assign_filter = st.text_input("🔎 Filter assignment titles", key="assign_filter")
    assign_options = [k for k in ref_answers.keys() if assign_filter.lower() in k.lower()]
    assignment = st.selectbox("📋 Select Assignment", [""] + assign_options, key="assignment")
    if not assignment:
        assignment = st.text_input("Or enter assignment manually", key="assignment_manual")
    score = st.number_input("Score", min_value=0, max_value=100, value=0, key="score_input")
    comments = st.text_area("Comments / Feedback", key="comments_input")
    if assignment in ref_answers:
        st.markdown("**Reference Answers:**")
        st.markdown("<br>".join(ref_answers[assignment]), unsafe_allow_html=True)

    # --- Record New Score ---
    if st.button("💾 Save Score", key="save_score"):
        now = datetime.now().strftime("%Y-%m-%d")
        # Save to SQLite
        cursor_scores.execute(
            "INSERT INTO scores (StudentCode, Name, Assignment, Score, Comments, Date) VALUES (?,?,?,?,?,?)",
            (student_row['studentcode'], student_row['name'], assignment, score, comments, now)
        )
        conn_scores.commit()
        st.success("Score saved to database.")

        # --- Download All Scores CSV (from DB) ---
    if not scores_df.empty:
        # Merge in student level for export
        export_df = scores_df.merge(
            df_students[['studentcode','level']],
            left_on='StudentCode', right_on='studentcode', how='left'
        )
        export_df = export_df[['StudentCode','Name','Assignment','Score','Comments','Date','level']]
        export_df = export_df.rename(columns={'level':'Level'})

        # Properly indent download button
        st.download_button(
            "📁 Download All Scores CSV",
            data=export_df.to_csv(index=False).encode(),
            file_name="scores_backup.csv",
            mime="text/csv"
        )

    # --- Display & Edit Student History & PDF ---
    hist = scores_df[scores_df['StudentCode'].str.lower() == student_row['studentcode'].lower()]
    if not hist.empty:
        st.markdown("### Student Score History & Edit")
        # Show editable history
        for idx, row in hist.iterrows():
            with st.expander(f"{row['Assignment']} – {row['Score']}/100 ({row['Date']})", expanded=False):
                # Prefill inputs
                new_assignment = st.text_input("Assignment", value=row['Assignment'], key=f"edit_assign_{idx}")
                new_score = st.number_input("Score", min_value=0, max_value=100, value=int(row['Score']), key=f"edit_score_{idx}")
                new_comments = st.text_area("Comments", value=row['Comments'], key=f"edit_comments_{idx}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Update", key=f"update_score_{idx}"):
                        cursor_scores.execute(
                            "UPDATE scores SET Assignment=?, Score=?, Comments=? WHERE StudentCode=? AND Assignment=? AND Date=?",
                            (new_assignment, new_score, new_comments,
                             student_row['studentcode'], row['Assignment'], row['Date'])
                        )
                        conn_scores.commit()
                        st.success("Score updated.")
                        st.rerun()
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_score_{idx}"):
                        cursor_scores.execute(
                            "DELETE FROM scores WHERE StudentCode=? AND Assignment=? AND Date=?",
                            (student_row['studentcode'], row['Assignment'], row['Date'])
                        )
                        conn_scores.commit()
                        st.success("Score deleted.")
                        st.rerun()
        # Show PDF download as before
        hist['Score'] = pd.to_numeric(hist['Score'], errors='coerce')
        avg = hist['Score'].mean()
        st.markdown(f"**Average Score:** {avg:.1f}")
        pdf = FPDF()
        pdf.add_page()
        def safe(txt): return str(txt).encode('latin-1','replace').decode('latin-1')
        pdf.set_font("Arial","B",14)
        pdf.cell(0,10,safe(f"Report for {student_row['name']}"),ln=True)
        pdf.ln(5)
        for _, r in hist.iterrows():
            pdf.set_font("Arial","B",12)
            pdf.cell(0,8,safe(f"{r['Assignment']}: {r['Score']}/100"),ln=True)
            pdf.set_font("Arial","",11)
            pdf.multi_cell(0,8,safe(f"Comments: {r['Comments']}"))
            if r['Assignment'] in ref_answers:
                pdf.set_font("Arial","I",11)
                pdf.multi_cell(0,8,safe("Reference Answers:"))
                for ans in ref_answers.get(r['Assignment'], []): pdf.multi_cell(0,8,safe(ans))
            pdf.ln(3)
        pdf_bytes = pdf.output(dest='S').encode('latin-1','replace')
        st.download_button(
            "📄 Download Student Report PDF",
            data=pdf_bytes,
            file_name=f"{student_row['name']}_report.pdf",
            mime="application/pdf"
        )
    else:
        st.info("No scores found for this student.")



