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

        # -- Generate Payment Contract PDF --
        if st.button("📝 Generate Payment Contract"):
            from fpdf import FPDF

            contract_text = f"""
                This payment contract is made between {student_row['name']} ({student_row['studentcode']}) and Learn Language Education Academy.

                Student Level: {student_row.get('level','')}
                Contract Start: {student_row.get('contractstart','')}
                Contract End: {student_row.get('contractend','')}
                Tuition: GHS {student_row.get('fees','')}
                Phone: {student_row.get('phone','')}
                Email: {student_row.get('email','')}
                Address: {student_row.get('address','')}
                
                By signing, the student agrees to pay all required fees and abide by the Academy's policies.

                Signed: ______________________      Date: ________________

                For: Learn Language Education Academy
                Felix Asadu
            """

            class PDF(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 14)
                    self.cell(0, 12, "Learn Language Education Academy – Payment Contract", ln=1, align='C')
            pdf = PDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.multi_cell(0, 8, contract_text)
            pdf.set_font("Arial", "I", 11)
            pdf.cell(0, 10, "Signed: Felix Asadu", ln=1, align='R')
            pdf_out = f"{student_row['name'].replace(' ', '_')}_contract.pdf"
            pdf.output(pdf_out)
            with open(pdf_out, "rb") as f:
                pdf_bytes = f.read()
            st.download_button("⬇️ Download Payment Contract", data=pdf_bytes, file_name=pdf_out, mime="application/pdf")

        # -- Generate Receipt PDF --
        if st.button("📄 Generate Payment Receipt"):
            receipt_text = f"""
                RECEIPT OF PAYMENT

                Received from: {student_row['name']} ({student_row['studentcode']})
                Level: {student_row.get('level','')}
                Date: {date.today().strftime('%Y-%m-%d')}
                Amount Paid: GHS {student_row.get('fees','')}
                Payment Method: ____________________
                
                Thank you for your payment!

                For: Learn Language Education Academy
                Felix Asadu
            """

            class PDFReceipt(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 14)
                    self.cell(0, 12, "Learn Language Education Academy – Payment Receipt", ln=1, align='C')
            pdf_r = PDFReceipt()
            pdf_r.add_page()
            pdf_r.set_font("Arial", size=12)
            pdf_r.multi_cell(0, 8, receipt_text)
            pdf_r.set_font("Arial", "I", 11)
            pdf_r.cell(0, 10, "Signed: Felix Asadu", ln=1, align='R')
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

with tabs[3]:
    st.title("📲 Reminders for Debtors (WhatsApp & Email)")

    # --- Load students from GitHub ---
    github_csv_url = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
    try:
        df = pd.read_csv(github_csv_url)
        st.info("Loaded student data from GitHub backup.")
    except Exception:
        st.error("No student data found on GitHub.")
        st.stop()

    # --- Normalize columns ---
    df.columns = [c.strip().lower() for c in df.columns]
    def col_lookup(x):
        x = str(x).strip().lower()
        for c in df.columns:
            if x == c.strip().lower():
                return c
        return x

    # --- Quick filter/search bar ---
    st.markdown("#### 🔎 Filter or Search")
    name_search = st.text_input("Search by name or code", key="remind_search_unique")
    if "level" in df.columns:
        levels = ["All"] + sorted(df["level"].dropna().unique().tolist())
        selected_level = st.selectbox("Filter by Level", levels, key="remind_level_unique")
    else:
        selected_level = "All"

    filtered_df = df.copy()
    if name_search:
        filtered_df = filtered_df[
            filtered_df[col_lookup("name")].astype(str).str.contains(name_search, case=False, na=False) |
            filtered_df[col_lookup("studentcode")].astype(str).str.contains(name_search, case=False, na=False)
        ]
    if selected_level != "All" and "level" in df.columns:
        filtered_df = filtered_df[filtered_df["level"] == selected_level]

    # --- Outstanding balances ---
    st.markdown("---")
    st.subheader("Students with Outstanding Balances")

    if col_lookup("balance") not in filtered_df.columns or col_lookup("phone") not in filtered_df.columns:
        st.warning("Missing required columns: 'Balance' or 'Phone'")
        st.stop()

    filtered_df[col_lookup("balance")] = pd.to_numeric(filtered_df[col_lookup("balance")], errors="coerce").fillna(0.0)
    filtered_df[col_lookup("phone")] = filtered_df[col_lookup("phone")].astype(str)

    debtors = filtered_df[filtered_df[col_lookup("balance")] > 0]

    def clean_phone(phone):
        phone = str(phone).replace(" ", "").replace("+", "").replace("-", "")
        if phone.startswith("0"):
            phone = "233" + phone[1:]
        return ''.join(filter(str.isdigit, phone))

    if not debtors.empty:
        for i, (_, row) in enumerate(debtors.iterrows()):
            name = row.get(col_lookup("name"), "Unknown")
            level = row.get(col_lookup("level"), "")
            balance = float(row.get(col_lookup("balance"), 0.0))
            code = row.get(col_lookup("studentcode"), "")
            phone = clean_phone(row.get(col_lookup("phone"), ""))

            # Dates
            contract_start = row.get(col_lookup("contractstart"), "")
            try:
                if contract_start and not pd.isnull(contract_start):
                    contract_start_dt = pd.to_datetime(contract_start, errors="coerce")
                    contract_start_fmt = contract_start_dt.strftime("%d %B %Y")
                    due_date_dt = contract_start_dt + timedelta(days=30)
                    due_date_fmt = due_date_dt.strftime("%d %B %Y")
                else:
                    contract_start_fmt = "N/A"
                    due_date_fmt = "soon"
            except Exception:
                contract_start_fmt = "N/A"
                due_date_fmt = "soon"

            # WhatsApp payment message
            message = (
                f"Dear {name}, this is a reminder that your balance for your {level} class is GHS {balance:.2f} "
                f"and is due by {due_date_fmt}. "
                f"Contract start: {contract_start_fmt}.\n"
                "Kindly make the payment to continue learning with us. Thank you!\n\n"
                "Payment Methods:\n"
                "1. Mobile Money\n"
                "   Number: 0245022743\n"
                "   Name: Felix Asadu\n"
                "2. Access Bank (Cedis)\n"
                "   Account Number: 1050000008017\n"
                "   Name: Learn Language Education Academy"
            )
            encoded_msg = urllib.parse.quote(message)
            wa_url = f"https://wa.me/{phone}?text={encoded_msg}"

            st.markdown(
                f"🔔 <b>{name}</b> (<i>{level}</i>, <b>{balance:.2f} GHS due</b>) — "
                f"<a href='{wa_url}' target='_blank'>📲 Remind via WhatsApp</a>",
                unsafe_allow_html=True
            )

            # --- Optional: Email Reminder Button (if student has email) ---
            if "email" in row and isinstance(row["email"], str) and "@" in row["email"]:
                if st.button(f"✉️ Email {name}", key=f"remind_email_{code}_{i}"):
                    try:
                        from sendgrid import SendGridAPIClient
                        from sendgrid.helpers.mail import Mail
                        SENDGRID_API_KEY = st.secrets.get("SENDGRID_API_KEY")
                        SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "Learngermanghana@gmail.com")
                        msg = Mail(
                            from_email=SENDER_EMAIL,
                            to_emails=row["email"],
                            subject="Payment Reminder",
                            html_content=message.replace("\n", "<br>")
                        )
                        sg = SendGridAPIClient(SENDGRID_API_KEY)
                        sg.send(msg)
                        st.success(f"Email sent to {name} ({row['email']})")
                    except Exception as e:
                        st.warning(f"Email failed for {name}: {e}")

    else:
        st.success("✅ No students with unpaid balances.")
with tabs[4]:
    st.markdown("""
    <div style='background:#e3f2fd;padding:1.2em 1em 0.8em 1em;border-radius:12px;margin-bottom:1em'>
      <h2 style='color:#1565c0;'>📆 <b>Intelligenter Kursplan-Generator (A1, A2, B1)</b></h2>
      <p style='font-size:1.08em;color:#333'>Erstellen Sie einen vollständigen, individuell angepassten Kursplan zum Download (TXT oder PDF) – <b>mit Ferien und flexiblem Wochenrhythmus!</b></p>
    </div>
    """, unsafe_allow_html=True)

    # ---- Schedule templates ----
    raw_schedule_a1 = [
        ("Week One", ["Chapter 0.1 - Lesen & Hören"]),
        ("Week Two", [
            "Chapters 0.2 and 1.1 - Lesen & Hören",
            "Chapter 1.1 - Schreiben & Sprechen and Chapter 1.2 - Lesen & Hören",
            "Chapter 2 - Lesen & Hören"
        ]),
        ("Week Three", [
            "Chapter 1.2 - Schreiben & Sprechen (Recap)",
            "Chapter 2.3 - Schreiben & Sprechen",
            "Chapter 3 - Lesen & Hören"
        ]),
        ("Week Four", [
            "Chapter 4 - Lesen & Hören",
            "Chapter 5 - Lesen & Hören",
            "Chapter 6 - Lesen & Hören and Chapter 2.4 - Schreiben & Sprechen"
        ]),
        ("Week Five", [
            "Chapter 7 - Lesen & Hören",
            "Chapter 8 - Lesen & Hören",
            "Chapter 3.5 - Schreiben & Sprechen"
        ]),
        ("Week Six", [
            "Chapter 3.6 - Schreiben & Sprechen",
            "Chapter 4.7 - Schreiben & Sprechen",
            "Chapter 9 and 10 - Lesen & Hören"
        ]),
        ("Week Seven", [
            "Chapter 11 - Lesen & Hören",
            "Chapter 12.1 - Lesen & Hören and Schreiben & Sprechen (including 5.8)",
            "Chapter 5.9 - Schreiben & Sprechen"
        ]),
        ("Week Eight", [
            "Chapter 6.10 - Schreiben & Sprechen (Intro to letter writing)",
            "Chapter 13 - Lesen & Hören and Chapter 6.11 - Schreiben & Sprechen",
            "Chapter 14.1 - Lesen & Hören and Chapter 7.12 - Schreiben & Sprechen"
        ]),
        ("Week Nine", [
            "Chapter 14.2 - Lesen & Hören and Chapter 7.12 - Schreiben & Sprechen",
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
            self.cell(0,12,"Learn Language Education Academy – Course Schedule",ln=1,align='C',fill=True)
            self.ln(2)
            self.set_text_color(0,0,0)

    pdf = ColorHeaderPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0,8, f"Schedule: {selected_level}")
    pdf.multi_cell(0,8, f"Start: {start_date.strftime('%Y-%m-%d')}")
    if holiday_dates:
        pdf.multi_cell(0,8, "Holidays: " + ", ".join(d.strftime("%d.%m.%Y") for d in holiday_dates))
    pdf.ln(2)
    for r in rows:
        pdf.multi_cell(0,8, f"{r['Day']} ({r['Date']}): {r['Topic']}")
    pdf.ln(6)
    pdf.set_font("Arial",'I',11)
    pdf.cell(0,10, "Signed: Felix Asadu", ln=1, align='R')

    st.download_button("📄 PDF Download",
                       data=pdf.output(dest='S').encode('latin-1'),
                       file_name=f"{file_prefix}.pdf",
                       mime="application/pdf")

a1_answers = {
    "Lesen und Hören 0.2": [
        "1. C) 26", "2. A) A, O, U, B", "3. A) Eszett", "4. A) K", "5. A) A-Umlaut",
        "6. A) A, O, U, B", "7. B 4",
        "1. Wasser", "2. Kaffee", "3. Blume", "4. Schule", "5. Tisch"
    ],
    "Lesen und Hören 1.1": [
        "1. C", "2. C", "3. A", "4. B"
    ],
    "Lesen und Hören 1.2": [
        "1. Ich heiBe Anna", "2. Du heiBt Max", "3. Er heiBt Peter",
        "4. Wir Kommen aus Italien", "5. Ihr kommt aus Brasilien",
        "6. Sie Kommt/Kommen aus Russland", "7. Ich wohne in Berlin",
        "8. Du wohnst in Madrid", "9. Sie wohnst on wien",
        "1. A) Anna", "2. C) Aus Italien", "3. D) In Berlin",
        "4. B) Tom", "5. A) In Berlin"
    ],
    "Lesen und Hören 2": [
        "1. A) sieben", "2. B) Drei", "3. B) Sechs", "4. B) Neun", "5. B) Sieben",
        "6. C) Funf", "7. B) zweihundertzweiundzwanzig", "8. A) Funfhundertneun",
        "9. A) zweitausendvierzig", "10. A) funftausendfunfhundertneun",
        "1. 16 – sechzehn", "2. 98 – achtundneunzig", "3. 555 – funfhundertfunfundfunfzig",
        "4. 1020 – tausendzwanzig", "5. 8553 – achttausendfunfhundertdreiundfundzig"
    ],
    "Lesen und Hören 4": [
        "Lesen ubung (Deutschland und seine Nachbarlander)",
        "1. C) Neun", "2. B) Polnisch", "3. D) Niederlandisch", "4. A) Deutsch",
        "5. C) Paris", "6. B) Amsterdam", "7. C) In der Schweiz",
        "Horen Ubung (Rund um die Welt)",
        "1. C) In italien und Frankreich", "2. C) Rom", "3. B) Das Essen",
        "4. B) Paris", "5. A) Nach Spanien"
    ],
    "Lesen und Hören 5": [
        "Part 1: Vocabulary Review",
        "1. Der Tisch – j. the table", "2. Die Lampe – c. the lamp", "3. Das Buch – g. the book",
        "4. Der Stuhl – e. the chair", "5. Der Katze – f. the cat", "6. Das Auto – h. the car",
        "7. Der Hund – a. the dog", "8. Die Blume – d. the flower", "9. Das Fenster – d. the window",
        "10. Der Computer – i. The computer",
        "Part 2: Nominative Case",
        "1. Der tisch ist GroB", "2. Die Lampe ist neu", "3. Das Buch ist interessant",
        "4. Der Stuhl ist bequem", "5. Die Katze ist suB", "6. Das Auto ist Schnell",
        "7. Der Hund ist Freundlich", "8. Die Blume ist schon", "9. Das Fenster ist offen",
        "10. Der Computer ist teuer",
        "Part 3: Accusative Case",
        "1. Ich sehe den Tisch", "2. Sie Kauft die Lampe", "3. Er liest das Buch",
        "4. Wir brauchen den Stuhl", "5. Du futterst die Katze", "6. Ich fahre das Auto",
        "7. Sie Streichelt den Hund", "8. Er pfluckt die Blume", "9. Wir putzen das Fenster",
        "10. Sie benutzen computer"
    ],
    "Lesen und Hören 6": [
        "Teil 1",
        "1. Das Wohnzimmer – the living room", "2. Die Kuche - the kitchen", "3. Das Schlafzimmer – the bedroom",
        "4. Das Badezimmer - the bathroom", "5. Der Balkon – the balcony", "6. Der Flur – the hallway",
        "7. Das Bett – the bed", "8. Der Tisch - the table", "9. Der Stuhl – the chair", "10. Der Schrank – the wardrobe",
        "Teil 2",
        "1. B) Vier", "2. A) Ein Sofa und ein Fernseher",
        "3. B) Einen Herd, einen Kuhlschrank und einen Tisch mit vier Stuhlen",
        "4. C) Ein groBes Bett", "5. D) Eine Dusche, eine Badewanne und ein Waschbecken",
        "6. D) Klein und Schon", "7. C) Blumen und einen Kleinen Tisch mit zwei Stuhlen",
        "Teil3",
        "1. B", "2. B", "3. B", "4. C", "5. D", "6. B", "7. C"
    ],
    "Lesen und Hören 7": [
        "Teil 1 (Lesen)",
        "1. B) Um sieben Uhr", "2. B) Um acht Uhr", "3. B) Um sechs Uhr", "4. B) Um zehn Uhr", "5. B) Um neun Uhr",
        "6. C) Nachmittags", "7. A) Um sieben Uhr", "8. A) Montag", "9. B) Am Dienstag und Donnerstag", "10. B) Er ruht sich aus",
        "Teil 2 – Horen",
        "1. B) Um neun Uhr", "2. B) Er geht in die Bibliothek", "3. B) Bis zwei Uhr nachmittags",
        "4. B) Um drei Uhr nachmittags", "5. A)", "6. B) Um neun Uhr", "7. B) Er geht in die Bibliothek",
        "8. B) Bis zwei Uhr nachmittags", "9. B) Um drei Uhr nachmittags", "10. B) Um sieben Uhr"
    ],
    "Lesen und Hören 8": [
        "Teil 1 (Lesen)",
        "1. B) Zwei Uhr nachmittags", "2. B) 29 Tage", "3. B) April", "4. C) 03.02.2024", "5. C) Mittwoch",
        "Teil 2 (Lesen)",
        "1. Falsch", "2. Richtig", "3. Richtig", "4. Falsch", "5. Richtig",
        "Teil – Horen",
        "1. B) Um Mitternacht", "2. B) Vier Uhr nachmittags", "3. C) 28 Tage", "4. B) Tag. Monat. Jahr", "5. D) Montag"
    ],
    "Lesen und Hören 9": [
        "Teil 1",
        "1. B) Apfel und Karotten", "2. C) karotten", "3. A) Weil er Vegetarier ist",
        "4. C) Kase", "5. B) Fleisch", "6. B) Kekse", "7. A) Kase", "8. C) Kuchen", "9. C) Schokolade",
        "10. B) Der Bruder des Autors",
        "Teil 2",
        "1. A) Apfel, Bananen, und Karotten", "2. A) Musli mit Joghurt", "3. D) Karotten",
        "4. A) Kase", "5. C) Schokoladen kuchen"
    ],
    "Lesen und Hören 10": [
        "Lesen",
        "1. Falsch", "2. Wahr", "3. Falsch", "4. Wahr", "5. Wahr", "6. Falsch", "7. Wahr", "8. Falsch", "9. Falsch", "10. Falsch",
        "Horen",
        "1. B) Einmal Pro Woche", "2. C) Apfel und Bananen", "3. A) Ein halbes Kilo",
        "4. B) 10 Euro", "5. B) Einen schonen Tag"
    ],
    "Lesen und Hören 11": [
        "Teil 1",
        "1. B) Entschuldigung, wo ist der Bahnhof?", "2. B) Links abbiegen",
        "3. B) Akuf der rechten Seite, direk neben dem groBen Supermarkt",
        "4. B) Wie Komme ich zur nachsten Apotheke?", "5. C) Gute Reise und einen schonen Tag noch",
        "Tiel 2",
        "1. C) Wie Komme ich zur Nachsten Apotheke?", "2. C) Rechts abbiegen",
        "3. B) Auf der linken Seite, direct neben der Backerei",
        "4. A) Gehen Sie geradeaus bis zur kreuzung, dann links", "5. C) Einen schonen tag noch",
        "Teil 3",
        "1. Fragen nach dem Weg: “Entschuldigung, wie komme ich zum Bahnhof”",
        "2. Die StraBe Uberqueren: “Uberqueren Sie die StraBe”",
        "3. Geradeaus gehen: “Gehen Sie geradeaus ”",
        "4. Links abbiegen: “Biegen Sie rechts ab”",
        "5. Rechts abbiegen: “Biegen Sie rechts ab”",
        "6. On the left side: “Das Kino ist auf der linken Seite ”"
    ],
    "Lesen und Hören 12.1": [
        "Teil 1",
        "1. B) Arztin", "2. A) Weil sie keine Zeit hat", "3. B) Um 8 Uhr", "4. C) Viele verschiedene Facher", "5. C) Einen Sprachkurs besuchen",
        "Tiel 2",
        "1. Der Supermarkt ist nur am Wochenende geoffnet. Antwort: B) Falsch (Der Supermrkt hat jeden tag von 8 Uhr bis 20 Uhr geoffnet.)",
        "2. Die Theoriestunden sind jeden Tag. Antwort: B) Falsch (Die Theoriestunden finden dienstags und donnerstage statt.)",
        "3. Das Buro ist auch am Wochenende geoffnet. Antwort: B) Falsch (Das Buro ist von Montag bis Freitag geoffnet.)",
        "4. Der Englischkurs ist zweimal pro Woche. Antwort: B) Falsch (Der Engldischkurs findet dreimal pro Woche statt)",
        "5. Das Fitnessstudio ist nur vormittags geoffnet. Antwort: B) Falsch (Das Fitnessstudio ist jeden tag von 6 Uhr bis 22 geoffnet.)",
        "Teil 3",
        "1. A) Richtig", "2. A) Richtig", "3. A) Richtig", "4. A) Richtig", "5. A) Richtig"
    ],
    "Lesen und Hören 12.2": [
        "Teil 1",
        "In Berlin", "Mit seiner Frau und seinen drei Kindern", "Mit seinem Auto", "Um 7:30 Uhr", "a) Barzahlung (cash)",
        "Teil 2",
        "1. B) Um 9:00 Uhr", "2. B) Um 12:00 Uhr", "3. B) Um 18:00 Uhr", "4. B) Um 21:00 Uhr", "5. D) Alles Genannte",
        "Teil 3",
        "1. B) Um 9 Uhr", "2. B) Um 12 Uhr", "3. A) ein Computer and ein Drucker", "4. C) in einem bar", "5. C) bar"
    ],
    "Lesen und Hören 13": [
        "Teil 1",
        "1. A", "2. B", "3. A", "4. A", "5. B", "6. B",
        "Teil 2",
        "1. A", "2. B", "3. B",
        "Teil 3",
        "1. B", "2. B", "3. B"
    ],
    "Lesen und Hören 14.1": [
        "Teil 1",
        "Frage 1: Anzeige A", "Frage 2: Anzeige B", "Frage 3: Anzeige B",
        "Frage 4: Anzeige A", "Frage 5: Anzeige A",
        "Teil 2",
        "1. C) Guten tag, Herr Doktor", "2. B) Halsschmerzen und Fieber", "3. C) Seit gestern",
        "4. C) Kopfschmerzen und Mudigkeit", "5. A) Ich verschreibe innen Medikamente",
        "A) Kopf – Head", "B) Arm – Arm", "C) Bein – Leg", "D) Auge – Eye", "E) Nase – Nose",
        "F) Ohr – Ear", "G) Mund – Mouth", "H) Hand – Hand", "I) FuB – Foot", "J) Bauch - Stomach"
    ],
}

a2_answers = {
    "1.1 Small Talk (Exercise) - Lesen": [
        "1. C) In einer Schule",
        "2. B) Weil sie gerne mit Kindern arbeitet",
        "3. A) In einem Buro",
        "4. B) Tennis",
        "5. B) Es war sonnig und warm",
        "6. B) Italien und Spanien",
        "7. C) Weil die Baume so schon bunt sind"
    ],
    "1.1 Small Talk (Exercise) - Hören": [
        "1. B) Ins Kino gehen",
        "2. A) Weil sie spannende Geschichten liebt",
        "3. A) Tennis",
        "4. B) Es war sonnig und warm",
        "5. C) Einen Spaziergang Machen"
    ],
    "1.2 Personen Beschreiben (Exercise) - Lesen": [
        "1. B) Ein Jahr",
        "2. B) Er ist immer gut gelaunt und organisiert",
        "3. C) Einen Anzug und eine Brille",
        "4. B) Er geht geduldig auf ihre Anliegen ein",
        "5. B) Weil er seine Mitarbeiter regelmaBig lobt",
        "6. A) Wenn eine Aufgabe nicht rechtzeitig erledigt wird",
        "7. B) Dass er fair ist und die Leistungen der Mitarbeiter wertschatzt"
    ],
    "1.2 Personen Beschreiben (Exercise) - Hören": [
        "1. B) Weil er",
        "2. C) Sprachkurse",
        "3. A) Jeden tag"
    ],
    "1.3 Dinge und Personen vergleichen - Lesen": [
        "1. B) Anna ist 25 Jahre alt",
        "2. B) In ihrer Freizeit liest Anna Bucher und geht spazieren",
        "3. C) Anna arbeitet in einem Krankenhaus",
        "4. C) Anna hat einen Hund",
        "5. B) Max unterrichtet Mathematik",
        "6. A) Max spielt oft FuBball mit seinen Freunden",
        "7. B) Am Wochenende machen Anna und Max Ausfluge oder besuchen Museen"
    ],
    "1.3 Dinge und Personen vergleichen - Hören": [
        "1. B) Julia ist 26 Jahre alt",
        "2. C) Julia arbeitet als Architektin",
        "3. B) Tobias lebt in Frankfurt",
        "4. A) Tobias mochte ein eigenes Restaurant eroffnen",
        "5. B) Julia und Tobias kochen am Wochenende oft mit Sophie"
    ],
    "2.4 Wo möchten wir uns treffen? - Lesen": [
        "1. B) faul sein",
        "2. d) Hockey spielen",
        "3. a) schwimmen gehen",
        "4. d) zum See fahren und dort im Zelt übernachten",
        "5. b) eine Route mit dem Zug durch das ganze Land"
    ],
    "2.4 Wo möchten wir uns treffen? - Hören": [
        "1. B) Um 10 Uhr",
        "2. B) Eine Rucksack",
        "3. B) Ein Piknik",
        "4. C) in eienem restaurant",
        "5. A) Spielen und Spazieren gehen"
    ],
    # 27 BLANK SPACES FOR YOU TO FILL LATER
    "2.5 <EMPTY>": [],
    "2.6 <EMPTY>": [],
    "2.7 <EMPTY>": [],
    "2.8 <EMPTY>": [],
    "2.9 <EMPTY>": [],
    "2.10 <EMPTY>": [],
    "2.11 <EMPTY>": [],
    "2.12 <EMPTY>": [],
    "2.13 <EMPTY>": [],
    "2.14 <EMPTY>": [],
    "2.15 <EMPTY>": [],
    "2.16 <EMPTY>": [],
    "2.17 <EMPTY>": [],
    "2.18 <EMPTY>": [],
    "2.19 <EMPTY>": [],
    "2.20 <EMPTY>": [],
    "2.21 <EMPTY>": [],
    "2.22 <EMPTY>": [],
    "2.23 <EMPTY>": [],
    "2.24 <EMPTY>": [],
    "2.25 <EMPTY>": [],
    "2.26 <EMPTY>": [],
    "2.27 <EMPTY>": [],
    "2.28 <EMPTY>": [],
    "2.29 <EMPTY>": [],
    "2.30 <EMPTY>": [],
    "2.31 <EMPTY>": []
}

# ==== 3. B1 ANSWERS (TEMPLATE – 26 CHAPTERS) ====
b1_answers = {
    "1.1 Small Talk (Übung)": {
        "Lesen": [
            "1. ", "2. ", "3. ", "4. ", "5. ", "6. ", "7. "
        ],
        "Hören": [
            "1. ", "2. ", "3. ", "4. ", "5. "
        ]
    },
    "1.2 Personen Beschreiben (Übung)": {
        "Lesen": [
            "1. ", "2. ", "3. ", "4. ", "5. ", "6. ", "7. "
        ],
        "Hören": [
            "1. ", "2. ", "3. "
        ]
    },
    "1.3 Dinge und Personen vergleichen": {
        "Lesen": [
            "1. ", "2. ", "3. ", "4. ", "5. ", "6. ", "7. "
        ],
        "Hören": [
            "1. ", "2. ", "3. ", "4. ", "5. "
        ]
    },
    "2.4 (Übung)": {
        "Lesen": [
            "1. ", "2. ", "3. ", "4. ", "5. "
        ],
        "Hören": [
            "1. ", "2. ", "3. ", "4. ", "5. "
        ]
    },
    # ...repeat for all chapters up to 26...
}

# --- Merge all answer keys ---
ref_answers = {}
ref_answers.update(a1_answers)
ref_answers.update(a2_answers)
ref_answers.update(b1_answers)

# --- Marking Tab ---
st.title("📝 Assignment Marking & Scores")

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

df_students.columns = [col.lower().strip().replace(" ", "_") for col in df_students.columns]

# --- Filter/Search UI ---
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

# --- Student selection ---
student_list = view_df["name"].astype(str) + " (" + view_df["studentcode"].astype(str) + ")"
selected = st.selectbox("Select a student", student_list, key="select_student_detail")
selected_code = selected.split("(")[-1].replace(")", "").strip()
student_row = view_df[view_df["studentcode"].astype(str).str.lower() == selected_code.lower()].iloc[0]

# --- Assignment Entry ---
st.markdown("---")
st.subheader(f"📝 Record Assignment Score for **{student_row['name']}** ({student_row['studentcode']})")

# Choose Level/Assignment (A1, A2, B1)
level_choice = st.selectbox("Select Level", ["A1", "A2", "B1"])
if level_choice == "A1":
    answer_dict = a1_answers
elif level_choice == "A2":
    answer_dict = a2_answers
else:
    answer_dict = b1_answers

assignment_name = st.selectbox("Assignment", list(answer_dict.keys()))
score = st.number_input("Score", min_value=0, max_value=100, value=0)
comments = st.text_area("Comments/Feedback (visible to student)", "")

# --- Show Reference Answers ---
if assignment_name in answer_dict:
    st.markdown("**Reference Answers:**")
    ans = answer_dict[assignment_name]
    if isinstance(ans, dict):  # For A2/B1 answers
        with st.expander("Lesen"):
            for item in ans.get("Lesen", []):
                st.markdown(item)
        with st.expander("Hören"):
            for item in ans.get("Hören", []):
                st.markdown(item)
    else:  # For A1 answers (list)
        for item in ans:
            st.markdown(item)

# --- SCORES DB ---
scores_file = "scores.csv"
if os.path.exists(scores_file):
    scores_df = pd.read_csv(scores_file)
else:
    scores_df = pd.DataFrame(columns=["StudentCode", "Name", "Assignment", "Score", "Comments", "Date", "Level"])

# --- SAVE SCORE ---
if st.button("💾 Save Score"):
    new_row = {
        "StudentCode": student_row["studentcode"],
        "Name": student_row["name"],
        "Assignment": assignment_name,
        "Score": score,
        "Comments": comments,
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Level": level_choice
    }
    scores_df = pd.concat([scores_df, pd.DataFrame([new_row])], ignore_index=True)
    scores_df.to_csv(scores_file, index=False)
    st.success("Score saved.")

# --- DOWNLOAD ALL SCORES ---
score_csv = scores_df.to_csv(index=False).encode()
st.download_button("📁 Download All Scores CSV", data=score_csv, file_name="scores_backup.csv", mime="text/csv", key="download_scores")

# --- Student Score History ---
student_scores = scores_df[scores_df["StudentCode"].astype(str).str.lower() == student_row["studentcode"].lower()]
if not student_scores.empty:
    st.markdown("### 🗂️ Student's Score History")
    st.dataframe(student_scores[["Assignment", "Score", "Comments", "Date", "Level"]])

    avg_score = student_scores["Score"].mean()
    st.markdown(f"**Average Score:** `{avg_score:.1f}`")
    st.markdown(f"**Total Assignments Submitted:** `{len(student_scores)}`")

    # --- Download PDF Report (with answers) ---
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
            # Attach answers
            answers = ref_answers.get(row["Assignment"], None)
            if answers:
                pdf.set_font("Arial", "I", 11)
                pdf.multi_cell(0, 8, "Reference Answers:")
                if isinstance(answers, dict):
                    pdf.multi_cell(0, 8, "[Lesen]")
                    for ref in answers.get("Lesen", []):
                        pdf.multi_cell(0, 8, ref)
                    pdf.multi_cell(0, 8, "[Hören]")
                    for ref in answers.get("Hören", []):
                        pdf.multi_cell(0, 8, ref)
                else:
                    for ref in answers:
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

# --- Reference Answers Table (for review) ---
with st.expander("📖 Show/Update Reference Answers (A1/A2/B1)", expanded=False):
    st.write("**A1 Answers:**")
    for k, v in a1_answers.items():
        st.write(f"**{k}:**")
        st.write(v if isinstance(v, list) else v)
    st.write("**A2 Answers:**")
    for k, v in a2_answers.items():
        st.write(f"**{k}:**")
        st.write(v if isinstance(v, dict) else v)
    st.write("**B1 Answers:**")
    for k, v in b1_answers.items():
        st.write(f"**{k}:**")
        st.write(v if isinstance(v, dict) else v)

# =======================
# Stage 3: Scoring, Comments, PDF, Email, WhatsApp
# =======================

# --- ASSIGNMENT INPUT UI ---
st.markdown("---")
st.subheader(f"📝 Record Assignment Score for **{student_row['name']}** ({student_row['studentcode']})")

assignment_name = st.text_input("Assignment Name (e.g., Lesen und Hören 0.2, Test 1, etc.)")
score = st.number_input("Score", min_value=0, max_value=100, value=0)
comments = st.text_area("Comments/Feedback (visible to student)", "")

# --- Reference Answers ---
answers = {}
answers.update(a1_answers)
answers.update(a2_answers)
answers.update(b1_answers)
if assignment_name in answers:
    st.markdown("**Reference Answers:**")
    st.markdown("<br>".join(answers[assignment_name]), unsafe_allow_html=True)

# --- SCORE DB ---
scores_file = "scores.csv"
if os.path.exists(scores_file):
    scores_df = pd.read_csv(scores_file)
else:
    scores_df = pd.DataFrame(columns=["StudentCode", "Name", "Assignment", "Score", "Comments", "Date"])

# --- SAVE SCORE ---
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

# --- STUDENT SCORE HISTORY & SHARING ---
student_scores = scores_df[scores_df["StudentCode"].astype(str).str.lower() == student_row["studentcode"].lower()]
if not student_scores.empty:
    st.markdown("### 🗂️ Student's Score History")
    st.dataframe(student_scores[["Assignment", "Score", "Comments", "Date"]])

    avg_score = student_scores["Score"].mean()
    st.markdown(f"**Average Score:** `{avg_score:.1f}`")
    st.markdown(f"**Total Assignments Submitted:** `{len(student_scores)}`")

    # --- Download PDF Report (with answers) ---
    if st.button("📄 Download Student Report PDF"):
        from fpdf import FPDF
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
            # Attach answers
            if row['Assignment'] in answers:
                pdf.set_font("Arial", "I", 11)
                pdf.multi_cell(0, 8, "Reference Answers:")
                for ref in answers[row['Assignment']]:
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

    # --- Custom message for email ---
    default_message = (
        f"Dear {student_row['name']},<br><br>"
        "Attached is your latest assignment report with official answers.<br>"
        "If you have any questions, reply to this email.<br><br>"
        "Best regards,<br>"
        "Felix Asadu<br>"
        "Learn Language Education Academy"
    )
    custom_message = st.text_area("📧 Custom Email Message", value=default_message, height=180)

    # --- Email with PDF ---
    SENDGRID_API_KEY = st.secrets.get("SENDGRID_API_KEY")
    SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "Learngermanghana@gmail.com")
    if pd.notna(student_row.get("email", "")) and student_row["email"]:
        if st.button("✉️ Email Student Report PDF"):
            try:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
                import base64

                msg = Mail(
                    from_email=SENDER_EMAIL,
                    to_emails=student_row["email"],
                    subject=f"Your Assignment Report – {student_row['name']}",
                    html_content=custom_message,
                )
                encoded_pdf = base64.b64encode(pdf_bytes).decode()
                msg.attachment = Attachment(
                    FileContent(encoded_pdf),
                    FileName(pdf_out),
                    FileType("application/pdf"),
                    Disposition("attachment"),
                )
                sg = SendGridAPIClient(SENDGRID_API_KEY)
                sg.send(msg)
                st.success("✅ Student report sent by email!")
            except Exception as e:
                st.warning(f"⚠️ Email failed: {e}")

    # --- WhatsApp Share Button ---
    def clean_phone(phone):
        phone = str(phone).replace(" ", "").replace("-", "").replace("+", "")
        if phone.startswith("0"):
            phone = "233" + phone[1:]
        if not phone.startswith("233"):
            phone = "233" + phone  # fallback if not already handled
        return phone
    wa_phone = clean_phone(student_row.get("phone", ""))
    wa_message = (
        f"Hello {student_row['name']}, here is your assignment report.\n"
        f"Score: {score}/100\n"
        f"Assignment: {assignment_name}\n"
        f"Comments: {comments}\n"
        "If you need the full report, please check your email."
    )
    wa_url = f"https://wa.me/{wa_phone}?text={urllib.parse.quote(wa_message)}"
    st.markdown(f"[💬 Share on WhatsApp]({wa_url})", unsafe_allow_html=True)

else:
    st.info("No scores for this student yet. Enter and save a new one above!")
# =======================
# Stage 4: Backup, Restore, Reference Editing
# =======================

# --- UPLOAD/RESTORE SCORES DB ---
with st.expander("⬆️ Restore/Upload Scores Backup"):
    uploaded_scores = st.file_uploader("Upload scores.csv", type="csv", key="score_restore")
    if uploaded_scores is not None:
        scores_df = pd.read_csv(uploaded_scores)
        scores_df.to_csv(scores_file, index=False)
        st.success("Scores restored from uploaded file.")

# --- DOWNLOAD ALL SCORES ---
score_csv = scores_df.to_csv(index=False).encode()
st.download_button("📁 Download All Scores CSV", data=score_csv, file_name="scores_backup.csv", mime="text/csv", key="download_scores")

# --- DOWNLOAD STUDENT SCORES ONLY (for current student) ---
if not student_scores.empty:
    student_only_csv = student_scores.to_csv(index=False).encode()
    st.download_button(
        "📥 Download Student Scores Only",
        data=student_only_csv,
        file_name=f"{student_row['name'].replace(' ', '_')}_scores.csv",
        mime="text/csv",
        key="download_student_scores"
    )

# --- Reference Answers Table (to update/copy in your Python code) ---
with st.expander("📖 Show/Update Reference Answers (A1/A2/B1)", expanded=False):
    st.write("**A1 Answers:**")
    for k, v in a1_answers.items():
        st.write(f"**{k}:**")
        st.write(", ".join(v))
    st.write("**A2 Answers:**")
    for k, v in a2_answers.items():
        st.write(f"**{k}:**")
        st.write(", ".join(v))
    st.write("**B1 Answers:**")
    for k, v in b1_answers.items():
        st.write(f"**{k}:**")
        st.write(", ".join(v))
    st.info("To update: Edit your answer keys in the Python dictionaries at the top of this file.")

# (END OF MARKING/REPORT TAB)
