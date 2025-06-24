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
    st.title("👩‍🎓 All Students – Full List")

    import os
    import pandas as pd

    student_file = "students.csv"
    github_csv = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"

    # --- Load Data ---
    if os.path.exists(student_file):
        df_students = pd.read_csv(student_file)
    else:
        try:
            df_students = pd.read_csv(github_csv)
            st.info("Loaded students from GitHub backup.")
        except Exception:
            st.error("Could not load students.csv from local or GitHub.")
            st.stop()

    # --- Normalize columns ---
    df_students.columns = [
        c.strip().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_").replace("/", "_").lower()
        for c in df_students.columns
    ]

    # --- Filter/search controls ---
    search_term = st.text_input("🔍 Search by Name, Code, Phone, or Email").lower().strip()
    levels = ["All"] + sorted(df_students["level"].dropna().unique().tolist()) if "level" in df_students.columns else ["All"]
    selected_level = st.selectbox("📋 Filter by Class Level", levels)

    # --- Apply filters ---
    view_df = df_students.copy()
    if search_term:
        cols = ["name", "studentcode", "phone", "email"]
        view_df = view_df[
            view_df.apply(
                lambda row: any(
                    search_term in str(row.get(col, "")).lower() for col in cols
                ),
                axis=1
            )
        ]
    if selected_level != "All" and "level" in df_students.columns:
        view_df = view_df[view_df["level"] == selected_level]

    # --- Pagination ---
    ROWS_PER_PAGE = 15
    total_rows = len(view_df)
    total_pages = max(1, (total_rows - 1) // ROWS_PER_PAGE + 1)
    page = st.number_input(
        f"Page (1-{total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="students_page"
    )
    start_idx = (page - 1) * ROWS_PER_PAGE
    end_idx = start_idx + ROWS_PER_PAGE

    st.write(f"Showing {start_idx+1} to {min(end_idx, total_rows)} of {total_rows} students")

    # --- Display Table ---
    st.dataframe(view_df.iloc[start_idx:end_idx].reset_index(drop=True), use_container_width=True)



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

with tabs[4]:  
    st.title("📝 Assignment Marking & Scores")

# ---- Load student database ----
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

df_students.columns = [col.lower().strip().replace(" ", "_") for col in df_students.columns]

# ---- Filter/Search UI ----
st.subheader("Filter/Search Students")
search_term = st.text_input("🔍 Search Name or Code")
level_options = ["All"] + sorted(df_students["level"].dropna().unique().tolist())
level_select = st.selectbox("📚 Filter by Level", level_options)
view_df = df_students.copy()
if search_term:
    view_df = view_df[
        view_df["name"].str.contains(search_term, case=False, na=False) |
        view_df["studentcode"].astype(str).str.contains(search_term, case=False, na=False)
    ]
if level_select != "All":
    view_df = view_df[view_df["level"] == level_select]

if view_df.empty:
    st.warning("No students match your filter.")
    st.stop()

# ---- Student selection ----
student_list = view_df["name"].astype(str) + " (" + view_df["studentcode"].astype(str) + ")"
selected = st.selectbox("Select a student", student_list, key="select_student_detail")
selected_code = selected.split("(")[-1].replace(")", "").strip()
student_row = view_df[view_df["studentcode"].astype(str).str.lower() == selected_code.lower()].iloc[0]

# ---- Reference Answers (sample, expand as needed) ----
a1_answers = {
    "Lesen und Hören 0.2": [
        "1. C) 26",
        "2. A) A, O, U, B",
        "3. A) Eszett",
        "4. A) K",
        "5. A) A-Umlaut",
        "6. A) A, O, U, B",
        "7. B 4",
        "Wasser", "Kaffee", "Blume", "Schule", "Tisch"
    ],
}
a2_answers = {
    "Lesen": [
        "1. C In einer Schule",
        "2. B Weil sie gerne mit Kindern arbeitet",
        "3. A In einem Büro",
        "4. B Tennis",
        "5. B Es war sonnig und warm",
        "6. B Italien und Spanien",
        "7. C Weil die Blumen so schön bunt sind"
    ],
}
ref_answers = {**a1_answers, **a2_answers}

# ---- Load or create scores file ----
if os.path.exists(scores_file):
    scores_df = pd.read_csv(scores_file)
else:
    scores_df = pd.DataFrame(columns=["StudentCode", "Name", "Assignment", "Score", "Comments", "Date"])

# ---- Assignment Input ----
st.markdown("---")
st.subheader(f"📝 Record Assignment Score for **{student_row['name']}** ({student_row['studentcode']})")

assignment_name = st.text_input("Assignment Name (e.g., Lesen und Hören 0.2, Test 1, etc.)")
score = st.number_input("Score", min_value=0, max_value=100, value=0)
comments = st.text_area("Comments/Feedback (visible to student)", "")
if assignment_name in ref_answers:
    st.markdown("**Reference Answers:**")
    st.markdown("<br>".join(ref_answers[assignment_name]), unsafe_allow_html=True)

if st.button("💾 Save Score"):
    new_row = {
        "StudentCode": student_row["studentcode"],
        "Name": student_row["name"],
        "Assignment": assignment_name,
        "Score": score,
        "Comments": comments,
        "Date": datetime.now().strftime("%Y-%m-%d")
    }
    scores_df = pd.concat([scores_df, pd.DataFrame([new_row])], ignore_index=True)
    scores_df.to_csv(scores_file, index=False)
    st.success("Score saved.")

# ---- DOWNLOAD ALL SCORES CSV ----
score_csv = scores_df.to_csv(index=False).encode()
st.download_button(
    "📁 Download All Scores CSV",
    data=score_csv,
    file_name="scores_backup.csv",
    mime="text/csv",
    key="download_scores"
)

# ---- STUDENT SCORE HISTORY & SHARING ----
student_scores = scores_df[scores_df["StudentCode"].astype(str).str.lower() == student_row["studentcode"].lower()]
if not student_scores.empty:
    st.markdown("### 🗂️ Student's Score History")
    st.dataframe(student_scores[["Assignment", "Score", "Comments", "Date"]])

    avg_score = student_scores["Score"].mean()
    st.markdown(f"**Average Score:** `{avg_score:.1f}`")
    st.markdown(f"**Total Assignments Submitted:** `{len(student_scores)}`")

    # ---- Download PDF Report (with answers) ----
    if st.button("📄 Download Student Report PDF"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 12, f"Assignment Report – {student_row['name']} ({student_row['studentcode']})", ln=1)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"Level: {student_row['level']}", ln=1)
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=1)
        pdf.ln(5)
        for idx, row in student_scores.iterrows():
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, f"{row['Assignment']}:", ln=1)
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 8, f"Score: {row['Score']}/100", ln=1)
            pdf.multi_cell(0, 8, f"Comments: {row['Comments']}")
            if row['Assignment'] in ref_answers:
                pdf.set_font("Arial", "I", 11)
                pdf.multi_cell(0, 8, "Reference Answers:")
                for ref in ref_answers[row['Assignment']]:
                    pdf.multi_cell(0, 8, ref)
            pdf.ln(3)
        pdf.ln(10)
        pdf.set_font("Arial", "I", 11)
        pdf.cell(0, 8, f"Average Score: {avg_score:.1f}", ln=1)
        pdf.cell(0, 8, f"Total Assignments: {len(student_scores)}", ln=1)
        pdf.ln(15)
        pdf.cell(0, 10, "Signed: Felix Asadu", ln=1)
        pdf_out = f"{student_row['name'].replace(' ', '_')}_assignment_report.pdf"
        pdf.output(pdf_out)
        with open(pdf_out, "rb") as f:
            pdf_bytes = f.read()
        st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name=pdf_out, mime="application/pdf")

    # ---- WhatsApp Share (with answers & average) ----
    msg = (
        f"Hello {student_row['name']}, your average assignment score is {avg_score:.1f}.\n\n"
        f"Most recent: {student_scores.iloc[-1]['Assignment']} – {student_scores.iloc[-1]['Score']}/100.\n"
        f"Reference Answers: "
    )
    recent = student_scores.iloc[-1]["Assignment"]
    if recent in ref_answers:
        msg += "\n" + "\n".join(ref_answers[recent])
    wa_phone = str(student_row.get("phone", ""))
    if wa_phone and not pd.isna(wa_phone):
        wa_phone = wa_phone.replace(" ", "").replace("+", "")
        if wa_phone.startswith("0"):
            wa_phone = "233" + wa_phone[1:]
        wa_url = f"https://wa.me/{wa_phone}?text={urllib.parse.quote(msg)}"
        st.markdown(f"[💬 Send result via WhatsApp]({wa_url})", unsafe_allow_html=True)

    # ---- Download Student Scores Only (for official) ----
    student_only_csv = student_scores.to_csv(index=False).encode()
    st.download_button(
        "📥 Download Student Scores Only",
        data=student_only_csv,
        file_name=f"{student_row['name'].replace(' ', '_')}_scores.csv",
        mime="text/csv",
        key="download_student_scores"
    )

# ---- UPLOAD/RESTORE SCORES DB ----
with st.expander("⬆️ Restore/Upload Scores Backup"):
    uploaded_scores = st.file_uploader("Upload scores.csv", type="csv", key="score_restore")
    if uploaded_scores is not None:
        scores_df = pd.read_csv(uploaded_scores)
        scores_df.to_csv(scores_file, index=False)
        st.success("Scores restored from uploaded file.")

