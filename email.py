import os
import base64
import urllib.parse
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from fpdf import FPDF

# --- Universal: Load any CSV from GitHub ---
def load_csv_from_github(github_url, columns=None):
    try:
        df = pd.read_csv(github_url)
        if columns:
            for col in columns:
                if col not in df.columns:
                    df[col] = ""
        return df
    except Exception as e:
        st.error(f"Could not load data from GitHub: {e}")
        return pd.DataFrame(columns=columns or [])

# --- Clean/standardize phone numbers for WhatsApp ---
def clean_phone(phone):
    phone = str(phone).replace(" ", "").replace("+", "").replace("-", "")
    if phone.startswith("0"):
        phone = "233" + phone[1:]
    return ''.join(filter(str.isdigit, phone))

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

# --- Tab Titles (Only reduced set!) ---
tabs = st.tabs([
    "📝 Pending",
    "👩‍🎓 All Students",
    "📲 Reminders",
    "📆 Course Schedule",
    "📝 Marking"
])

with tabs[0]:
    st.title("📝 Pending Students (Registration Sheet)")
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"
    # Attempt to load from Google Sheet (registration form)
    try:
        df_pending = pd.read_csv(SHEET_URL)
        # Normalize column names for display
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
    st.title("👩‍🎓 All Students (View Only)")

    # --- Always load from GitHub ---
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

    # --- Status assignment (contract end logic, optional) ---
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

    # --- Show table and download ---
    if view_df.empty:
        st.info("No students found for this filter/search.")
    else:
        st.dataframe(view_df, use_container_width=True)
        st.download_button(
            "📁 Download All Students CSV",
            data=view_df.to_csv(index=False),
            file_name="students_backup.csv",
            mime="text/csv"
        )
with tabs[2]:
    st.title("💵 Expenses and Financial Summary")

    # --- GitHub CSV source for expenses ---
    github_expenses_url = "https://raw.githubusercontent.com/learngermanghana/email/main/expenses.csv"
    try:
        df_expenses = pd.read_csv(github_expenses_url)
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
    name_search = st.text_input("Search by name or code", key="remind_search")
    if "level" in df.columns:
        levels = ["All"] + sorted(df["level"].dropna().unique().tolist())
        selected_level = st.selectbox("Filter by Level", levels, key="remind_level")
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
        for _, row in debtors.iterrows():
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
                if st.button(f"✉️ Email {name}", key=f"remind_email_{code}"):
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
    name_search = st.text_input("Search by name or code", key="remind_search")
    if "level" in df.columns:
        levels = ["All"] + sorted(df["level"].dropna().unique().tolist())
        selected_level = st.selectbox("Filter by Level", levels, key="remind_level")
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
        for _, row in debtors.iterrows():
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
                if st.button(f"✉️ Email {name}", key=f"remind_email_{code}"):
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

with tabs[5]:
    st.title("📝 Assignment Marking & Scores")

    # --- Load student database (always GitHub) ---
    github_students_url = "https://raw.githubusercontent.com/learngermanghana/email/main/students.csv"
    github_scores_url   = "https://raw.githubusercontent.com/learngermanghana/email/main/scores_backup.csv"
    SCHOOL_NAME = "Learn Language Education Academy"

    # --- Assignment totals per level ---
    assignment_totals = {"A1": 19, "A2": 28, "B1": 26}

    try:
        df_students = pd.read_csv(github_students_url)
    except Exception:
        st.error("Could not load student data from GitHub.")
        st.stop()

    try:
        scores_df = pd.read_csv(github_scores_url)
    except Exception:
        scores_df = pd.DataFrame(columns=["StudentCode", "Name", "Assignment", "Score", "Comments", "Date", "Level"])

    # --- Normalize columns for case insensitivity ---
    df_students.columns = [c.lower().strip() for c in df_students.columns]
    scores_df.columns   = [c.lower().strip() for c in scores_df.columns]

    # --- Student Filter/Search ---
    st.subheader("Filter/Search Students")
    search_term = st.text_input("🔍 Search Name or Code")
    level_options = ["All"] + sorted(df_students["level"].dropna().unique())
    level_select = st.selectbox("📚 Filter by Level", level_options)
    view_df = df_students.copy()
    if search_term:
        view_df = view_df[
            view_df["name"].astype(str).str.contains(search_term, case=False, na=False) |
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

    # --- ANSWERS BANK (EDIT HERE) ---
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
        # ... other A1 assignments ...
    }
    a2_answers = {
        # ... your A2 answers ...
    }
    b1_answers = {
        # ... your B1 answers ...
    }
    ref_answers = {**a1_answers, **a2_answers, **b1_answers}

    # --- Assignment Input ---
    st.markdown("---")
    st.subheader(f"📝 Record Assignment Score for **{student_row['name']}** ({student_row['studentcode']})")

    assignment_name = st.text_input("Assignment Name (e.g., Lesen und Hören 0.2, Test 1, etc.)")
    score = st.number_input("Score", min_value=0, max_value=100, value=0)
    comments = st.text_area("Comments/Feedback (visible to student)", "")

    if assignment_name in ref_answers:
        st.markdown("**Reference Answers:**")
        st.markdown("<br>".join(ref_answers[assignment_name]), unsafe_allow_html=True)

    # --- Save Score (append locally, not to GitHub yet) ---
    if st.button("💾 Save Score"):
        new_row = {
            "StudentCode": student_row["studentcode"],
            "Name": student_row["name"],
            "Assignment": assignment_name,
            "Score": score,
            "Comments": comments,
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Level": student_row["level"]
        }
        scores_df = pd.concat([scores_df, pd.DataFrame([new_row])], ignore_index=True)
        scores_df.to_csv("scores.csv", index=False)
        st.success("Score saved (local file).")

    # --- Download All Scores CSV ---
    score_csv = scores_df.to_csv(index=False).encode()
    st.download_button("📁 Download All Scores CSV", data=score_csv, file_name="scores_backup.csv", mime="text/csv", key="download_scores")

    # --- Student Score History & Reference Answers ---
    student_scores = scores_df[scores_df["studentcode"].astype(str).str.lower() == student_row["studentcode"].lower()]
    if not student_scores.empty:
        st.markdown("### 🗂️ Student's Score History")
        st.dataframe(student_scores[["Assignment", "Score", "Comments", "Date"]])

        level = student_row["level"].upper()
        total_required = assignment_totals.get(level, 0)
        completed = len(student_scores)
        avg_score = student_scores["score"].mean()
        remaining = max(0, total_required - completed)

        st.markdown(f"**Average Score:** `{avg_score:.1f}`")
        st.markdown(f"**Assignments Completed:** `{completed} / {total_required}`")
        st.markdown(f"**Assignments Remaining:** `{remaining}`")

        # --- Download Student PDF Report (school header, signed) ---
        if st.button("📄 Download Student Report PDF"):
            from fpdf import FPDF
            class PDF(FPDF):
                def header(self):
                    self.set_font("Arial", "B", 14)
                    self.cell(0, 12, SCHOOL_NAME, ln=1, align="C")
            pdf = PDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 13)
            pdf.cell(0, 10, f"Assignment Report – {student_row['name']} ({student_row['studentcode']})", ln=1)
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 8, f"Level: {level}", ln=1)
            pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=1)
            pdf.cell(0, 8, f"Completed: {completed} / {total_required}", ln=1)
            pdf.cell(0, 8, f"Average Score: {avg_score:.1f}", ln=1)
            pdf.ln(3)
            for idx, row in student_scores.iterrows():
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, f"{row['assignment']}:", ln=1)
                pdf.set_font("Arial", "", 12)
                pdf.cell(0, 8, f"Score: {row['score']}/100", ln=1)
                pdf.multi_cell(0, 8, f"Comments: {row['comments']}")
                # Reference answers
                if row['assignment'] in ref_answers:
                    pdf.set_font("Arial", "I", 11)
                    pdf.multi_cell(0, 8, "Reference Answers:")
                    for ref in ref_answers[row['assignment']]:
                        pdf.multi_cell(0, 8, ref)
                pdf.ln(3)
            pdf.ln(12)
            pdf.set_font("Arial", "I", 12)
            pdf.cell(0, 10, "Signed: Felix Asadu", ln=1)
            pdf_out = f"{student_row['name'].replace(' ', '_')}_assignment_report.pdf"
            pdf.output(pdf_out)
            with open(pdf_out, "rb") as f:
                pdf_bytes = f.read()
            st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name=pdf_out, mime="application/pdf")

        # --- WhatsApp Share (with answers & average & completion info) ---
        msg = (
            f"Hello {student_row['name']}, assignments completed: {completed}/{total_required}. "
            f"Average score: {avg_score:.1f}\n"
            f"Most recent: {student_scores.iloc[-1]['assignment']} – {student_scores.iloc[-1]['score']}/100.\n"
            f"Reference Answers: "
        )
        recent = student_scores.iloc[-1]["assignment"]
        if recent in ref_answers:
            msg += "\n" + "\n".join(ref_answers[recent])
        wa_phone = str(student_row.get("phone", ""))
        if wa_phone and not pd.isna(wa_phone):
            wa_phone = wa_phone.replace(" ", "").replace("+", "")
            if wa_phone.startswith("0"):
                wa_phone = "233" + wa_phone[1:]
            wa_url = f"https://wa.me/{wa_phone}?text={urllib.parse.quote(msg)}"
            st.markdown(f"[💬 Send result via WhatsApp]({wa_url})", unsafe_allow_html=True)

        # --- Download Student Scores Only (for official) ---
        student_only_csv = student_scores.to_csv(index=False).encode()
        st.download_button(
            "📥 Download Student Scores Only",
            data=student_only_csv,
            file_name=f"{student_row['name'].replace(' ', '_')}_scores.csv",
            mime="text/csv",
            key="download_student_scores"
        )

        # --- Email via SendGrid (with PDF attached, if created above) ---
        SENDGRID_API_KEY = st.secrets.get("SENDGRID_API_KEY")
        SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "Learngermanghana@gmail.com")
        if pd.notna(student_row.get("email", "")) and student_row["email"]:
            if st.button("✉️ Email Student Portal"):
                try:
                    from sendgrid import SendGridAPIClient
                    from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
                    import base64

                    msg_email = Mail(
                        from_email=SENDER_EMAIL,
                        to_emails=student_row["email"],
                        subject=f"Your Assignment Report – {student_row['name']}",
                        html_content=f"""
                            Dear {student_row['name']},<br><br>
                            Attached is your latest assignment report.<br><br>
                            Best regards,<br>
                            Felix Asadu<br>
                            Learn Language Education Academy
                        """
                    )
                    # Ensure PDF is available (force regenerate if needed)
                    pdf = PDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 13)
                    pdf.cell(0, 10, f"Assignment Report – {student_row['name']} ({student_row['studentcode']})", ln=1)
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 8, f"Level: {level}", ln=1)
                    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=1)
                    pdf.cell(0, 8, f"Completed: {completed} / {total_required}", ln=1)
                    pdf.cell(0, 8, f"Average Score: {avg_score:.1f}", ln=1)
                    pdf.ln(3)
                    for idx, row in student_scores.iterrows():
                        pdf.set_font("Arial", "B", 12)
                        pdf.cell(0, 8, f"{row['assignment']}:", ln=1)
                        pdf.set_font("Arial", "", 12)
                        pdf.cell(0, 8, f"Score: {row['score']}/100", ln=1)
                        pdf.multi_cell(0, 8, f"Comments: {row['comments']}")
                        if row['assignment'] in ref_answers:
                            pdf.set_font("Arial", "I", 11)
                            pdf.multi_cell(0, 8, "Reference Answers:")
                            for ref in ref_answers[row['assignment']]:
                                pdf.multi_cell(0, 8, ref)
                        pdf.ln(3)
                    pdf.ln(12)
                    pdf.set_font("Arial", "I", 12)
                    pdf.cell(0, 10, "Signed: Felix Asadu", ln=1)
                    pdf_bytes2 = pdf.output(dest="S").encode("latin-1")
                    encoded_pdf = base64.b64encode(pdf_bytes2).decode()
                    pdf_out_name = f"{student_row['name'].replace(' ', '_')}_assignment_report.pdf"
                    msg_email.attachment = Attachment(
                        FileContent(encoded_pdf),
                        FileName(pdf_out_name),
                        FileType("application/pdf"),
                        Disposition("attachment"),
                    )
                    sg = SendGridAPIClient(SENDGRID_API_KEY)
                    sg.send(msg_email)
                    st.success("✅ Student portal sent by email!")
                except Exception as e:
                    st.warning(f"⚠️ Email failed: {e}")

    else:
        st.info("No scores for this student yet. Enter and save a new one above!")

    # --- Reference Answers Table (at bottom, easy to update) ---
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

