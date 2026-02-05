# ==== IMPORTS ====
import os
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import tempfile
import urllib.parse
from datetime import datetime, date, timedelta
import smtplib
from email.message import EmailMessage
import base64
import textwrap

from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import streamlit as st
from fpdf import FPDF, HTMLMixin
import qrcode
from PIL import Image  # For logo image handling
from io import BytesIO
from utils import safe_pdf
from pdf_utils import generate_receipt_and_contract_pdf
from attendance_utils import save_attendance_to_firestore, load_attendance_from_firestore

# ==== CONSTANTS ====
SCHOOL_NAME = "Learn Language Education Academy"
SCHOOL_WEBSITE = "https://www.learngermanghana.com"
SCHOOL_PHONE = "0205706589"
SCHOOL_ADDRESS = "Accra, Ghana"
BUSINESS_REG = "BN173410224"
TUTOR_NAME = "Felix Asadu"
TUTOR_TITLE = "Director"

# --- Sheet IDs & URLs ---
STUDENTS_SHEET_ID = "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U"
REF_ANSWERS_SHEET_ID = "1CtNlidMfmE836NBh5FmEF5tls9sLmMmkkhewMTQjkBo"

STUDENTS_CSV_URL = f"https://docs.google.com/spreadsheets/d/{STUDENTS_SHEET_ID}/export?format=csv"
REF_ANSWERS_CSV_URL = f"https://docs.google.com/spreadsheets/d/{REF_ANSWERS_SHEET_ID}/export?format=csv"

SOCIAL_LINKS = {
    "Website": SCHOOL_WEBSITE,
    "Phone": SCHOOL_PHONE,
    "Facebook": "https://www.facebook.com/learngermanghana",
    "Instagram": "https://www.instagram.com/learngermanghana",
    "YouTube": "https://www.youtube.com/@learngermanghana",
}

# ==== EMAIL CONFIGURATION ====


def load_email_config():
    """Load SMTP configuration from Streamlit secrets or environment variables."""
    config = {
        "SENDER_EMAIL": None,
        "SMTP_HOST": None,
        "SMTP_PORT": None,
        "SMTP_USE_TLS": None,
        "SMTP_USERNAME": None,
        "SMTP_PASSWORD": None,
    }

    try:
        secrets = st.secrets
        config["SENDER_EMAIL"] = secrets["email_sender"]
        smtp = secrets["smtp"]
        config["SMTP_HOST"] = smtp["host"]
        config["SMTP_PORT"] = smtp.get("port")
        config["SMTP_USE_TLS"] = smtp.get("use_tls", True)
        config["SMTP_USERNAME"] = smtp.get("username")
        config["SMTP_PASSWORD"] = smtp.get("password")
    except Exception:
        config["SENDER_EMAIL"] = os.environ.get("EMAIL_SENDER")
        config["SMTP_HOST"] = os.environ.get("SMTP_HOST")
        config["SMTP_PORT"] = os.environ.get("SMTP_PORT")
        config["SMTP_USE_TLS"] = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
        config["SMTP_USERNAME"] = os.environ.get("SMTP_USERNAME")
        config["SMTP_PASSWORD"] = os.environ.get("SMTP_PASSWORD")

    try:
        config["SMTP_PORT"] = int(config["SMTP_PORT"]) if config["SMTP_PORT"] else None
    except (TypeError, ValueError):
        config["SMTP_PORT"] = None

    return (
        config["SENDER_EMAIL"],
        config["SMTP_HOST"],
        config["SMTP_PORT"],
        config["SMTP_USE_TLS"],
        config["SMTP_USERNAME"],
        config["SMTP_PASSWORD"],
    )


SENDER_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USE_TLS, SMTP_USERNAME, SMTP_PASSWORD = load_email_config()

# --- HTTP session with retries ---
DEFAULT_TIMEOUT = 10


def _requests_retry_session(
    retries=3,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
):
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


HTTP_SESSION = _requests_retry_session()


def fetch_url(url, timeout=DEFAULT_TIMEOUT):
    """Fetch ``url`` returning raw bytes or ``None`` on failure."""
    try:
        resp = HTTP_SESSION.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Exception as exc:  # pragma: no cover - network errors
        st.warning(f"Failed to fetch {url}: {exc}")
        return None


def read_csv_with_retry(url, **kwargs):
    """Read CSV from ``url`` using the retry-enabled session."""
    content = fetch_url(url)
    if content is None:
        st.warning(f"Unable to load data from {url}")
        return pd.DataFrame()
    return pd.read_csv(BytesIO(content), **kwargs)

# ==== UNIVERSAL HELPERS ====

def col_lookup(df: pd.DataFrame, name: str, default=None) -> str:
    """Find the actual column name for a logical key, case/space/underscore-insensitive."""
    key = name.lower().replace(" ", "").replace("_", "")
    for c in df.columns:
        if c.lower().replace(" ", "").replace("_", "") == key:
            return c
    return default

def make_qr_code(url):
    """Generate QR code image file for a given URL, return temp filename."""
    qr = qrcode.QRCode(box_size=3, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(tmp.name)
    return tmp.name

def clean_phone(phone):
    """Normalize Ghana phone numbers to the ``233XXXXXXXXX`` format.

    Acceptable inputs:
      - ``0XXXXXXXXX``
      - ``233XXXXXXXXX``
      - ``+233XXXXXXXXX``
      - ``XXXXXXXXX`` (9 digits starting with 2, 5, or 9)

    Any other value returns ``None``.
    """
    # Remove all non-digit characters (spaces, dashes, plus signs, etc.)
    digits = re.sub(r"\D", "", str(phone))

    # Handle 9-digit numbers missing the leading zero
    if len(digits) == 9 and digits[:1] in {"2", "5", "9"}:
        digits = "0" + digits

    if digits.startswith("0") and len(digits) == 10:
        return "233" + digits[1:]
    if digits.startswith("233") and len(digits) == 12:
        return digits
    return None

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize all DataFrame columns to snake_case (lower, underscores)."""
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df

def strip_leading_number(text):
    """Remove leading digits, dots, spaces (for question/answer lists)."""
    return re.sub(r"^\s*\d+[\.\)]?\s*", "", text).strip()



def compute_days_and_message(days_left_value, balance_display):
    """Return a tuple of ``(days, message)`` for reminder templates.

    ``days`` is an ``int`` when ``days_left_value`` is numeric, otherwise the
    string ``"N/A"`` to keep downstream formatting safe.
    """

    fallback_days = "N/A"
    fallback_msg = (
        "Please review your account and reach out if you have any questions "
        "about your balance."
    )

    if pd.isna(days_left_value):
        return fallback_days, fallback_msg

    try:
        numeric_value = float(days_left_value)
    except (TypeError, ValueError):
        return fallback_days, fallback_msg

    if pd.isna(numeric_value):
        return fallback_days, fallback_msg

    days_int = int(numeric_value)
    if days_int >= 0:
        message = (
            f"You have {days_int} {'day' if days_int == 1 else 'days'} left to "
            f"settle the {balance_display} balance."
        )
    else:
        overdue_days = abs(days_int)
        message = (
            "Your payment is overdue by "
            f"{overdue_days} {'day' if overdue_days == 1 else 'days'}. "
            "Please settle as soon as possible."
        )

    return days_int, message


def fetch_assets(url_map: dict) -> dict:
    """Download multiple URLs concurrently.

    Parameters
    ----------
    url_map: dict
        Mapping of logical name -> URL to fetch.

    Returns
    -------
    dict
        Mapping of logical name -> bytes content (or ``None`` if download failed).
    """
    results = {}
    if not url_map:
        return results
    with ThreadPoolExecutor() as executor:
        future_to_key = {executor.submit(fetch_url, url): key for key, url in url_map.items()}
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as exc:  # pragma: no cover - should be handled in fetch_url
                st.warning(f"Failed to fetch {key}: {exc}")
                results[key] = None
    return results


# The legacy Stage 2 tests expect these helpers to exist at module level.
def parse_datetime_flex(value):
    """Parse ``value`` into a :class:`pandas.Timestamp` with flexible formats."""

    if value is None:
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return value

    if isinstance(value, datetime):
        return pd.Timestamp(value)

    text = str(value).strip()
    if not text:
        return pd.NaT

    # ISO 8601 strings with ``Z`` or timezone offsets (e.g. 2025-12-21T22:08:01.624Z)
    iso_text = text
    iso_match = re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$",
        iso_text,
    )
    if iso_match:
        # Normalize trailing ``Z`` to an explicit UTC offset to help older parsers.
        if iso_text.endswith("Z"):
            iso_text = iso_text[:-1] + "+00:00"
        ts = pd.to_datetime(iso_text, errors="coerce")
        if pd.notna(ts):
            return ts

    ts = pd.to_datetime(text, errors="coerce")
    if pd.notna(ts):
        return ts

    normalized = text.replace("T", " ").strip()
    normalized = re.sub(r"[A-Za-z]+$", "", normalized).strip()
    if "." in normalized:
        normalized = normalized.split(".", 1)[0]

    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try:
            return pd.Timestamp(datetime.strptime(normalized, fmt))
        except ValueError:
            continue

    return pd.NaT


def parse_date_flex(value, default=""):
    """Parse ``value`` into ``YYYY-MM-DD`` or return ``default`` if invalid."""
    parser = globals().get("parse_datetime_flex")
    ts = parser(value) if callable(parser) else pd.to_datetime(value, errors="coerce")
    if pd.notna(ts):
        return ts.date().isoformat()
    return default


def build_main_row(src: dict) -> dict:
    """Minimal builder used in unit tests for backward compatibility."""
    # ``col_lookup_df`` is injected during tests
    key = col_lookup_df.get("enrolldate") or col_lookup_df.get("enroll_date")
    raw = src.get(key, "")
    row = {"EnrollDate": parse_date_flex(raw, date.today().isoformat())}
    # Only keep the columns requested in TARGET_COLUMNS if defined
    try:
        return {k: row.get(k, "") for k in TARGET_COLUMNS}
    except Exception:
        return row

# ==== EMAIL SENDER ====

def send_email_report(pdf_bytes: bytes, to_email: str, subject: str, html_content: str, extra_attachments=None):
    """
    Send an email with (optional) PDF and any extra attachments.
    extra_attachments: list of tuples (bytes, filename, mimetype)
    """
    required = {
        "SENDER_EMAIL": SENDER_EMAIL,
        "SMTP_HOST": SMTP_HOST,
        "SMTP_PORT": SMTP_PORT,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        st.error(f"Missing email configuration: {', '.join(missing)}")
        return False

    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(html_content, subtype="html")

    # Attach PDF if provided
    if pdf_bytes:
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename="report.pdf",
        )

    # Attach any extra files
    if extra_attachments:
        for bytes_data, filename, mimetype in extra_attachments:
            maintype, subtype = ("application", "octet-stream")
            if mimetype and "/" in mimetype:
                maintype, subtype = mimetype.split("/", 1)
            msg.add_attachment(bytes_data, maintype=maintype, subtype=subtype, filename=filename)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email send failed: {e}")
        return False


def render_reminder_html(body_text: str) -> str:
    """Inject the message into the branded HTML template."""
    base_dir = os.path.dirname(__file__)
    template_path = os.path.join(base_dir, "email_template.html")
    logo_path = os.path.join(base_dir, "logo.png")
    with open(logo_path, "rb") as lf:
        logo_b64 = base64.b64encode(lf.read()).decode("utf-8")
    with open(template_path, "r", encoding="utf-8") as tf:
        template = tf.read()
    return template.format(
        logo_base64=logo_b64,
        content=body_text.replace("\n", "<br/>") if body_text else "",
        school_name=SCHOOL_NAME,
        school_address=SCHOOL_ADDRESS,
        school_phone=SCHOOL_PHONE,
        school_website=SCHOOL_WEBSITE,
    )


def render_completion_html(student_name: str, level: str, completion_date: date) -> str:
    """Render the course completion letter using the certificate template."""
    base_dir = os.path.dirname(__file__)
    template_path = os.path.join(base_dir, "completion_letter_template.html")
    with open(template_path, "r", encoding="utf-8") as tf:
        template = tf.read()
    return template.format(
        student_name=student_name,
        level=level,
        completion_date=completion_date.strftime("%B %d, %Y"),
    )


def render_completion_message(student_name: str, level: str) -> str:
    """Generate the default congratulatory email body for course completion."""
    return (
        f"Congratulations on finishing your {level} course, {student_name}! "
        "You worked hard and made great progress.<br><br>"
        "Please think about whether you want to prepare for the exam or move on to the next level. "
        "I wish you continued success as you make your next decision!<br><br>"
        f"Best wishes,<br>{TUTOR_NAME}<br>{TUTOR_TITLE}"
    )



# ==== AGREEMENT TEMPLATE ====
if "agreement_template_raw" not in st.session_state:
    st.session_state["agreement_template_raw"] = """
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

AGREEMENT_LINE_LIMIT = 120

def wrap_template_lines(text: str, limit: int = AGREEMENT_LINE_LIMIT):
    """Wrap long lines lacking spaces and report affected line numbers."""
    wrapped_lines = []
    warn_lines = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if len(line) > limit and " " not in line:
            warn_lines.append(idx)
            wrapped_lines.extend(textwrap.wrap(line, limit))
        else:
            wrapped_lines.append(line)
    return "\n".join(wrapped_lines), warn_lines

# ==== END OF STAGE 1 ====

# ==== DATA LOADING HELPERS & CACHING ====
# Allow cache TTL to be configured via ``st.secrets['cache_ttl']``
try:
    CACHE_TTL = int(st.secrets.get("cache_ttl", 300))
except Exception:  # pragma: no cover - fallback when secrets aren't available
    CACHE_TTL = 300


def _prepare_students_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize student DataFrame column names and values."""

    df = normalize_columns(df)

    # Standardize any known column name variants
    if "student_code" in df.columns:
        df = df.rename(columns={"student_code": "studentcode"})

    # Trim key string columns to avoid duplicate class entries caused by stray whitespace
    for col in ["classname", "level", "name", "studentcode"]:
        if col in df.columns:
            # Avoid propagating missing values as the literal string "nan"
            df[col] = df[col].fillna("").astype(str).str.strip()

    # Keep levels in a consistent format for grouping/selection
    if "level" in df.columns:
        df["level"] = df["level"].str.upper()

    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner="Loading student data...")
def load_students():
    df = read_csv_with_retry(STUDENTS_CSV_URL, dtype=str)
    return _prepare_students_df(df)

@st.cache_data(ttl=CACHE_TTL, show_spinner="Loading reference answers...")
def load_ref_answers():
    df = read_csv_with_retry(REF_ANSWERS_CSV_URL, dtype=str)
    df = normalize_columns(df)
    if "assignment" not in df.columns:
        raise Exception("No 'assignment' column found in reference answers sheet.")
    return df


# Optional: SQLite or other local storage helpers here (for local persistence if desired)
# @st.cache_resource
# def init_sqlite_connection():
#     import sqlite3
#     conn = sqlite3.connect('students_scores.db', check_same_thread=False)
#     # ...table creation logic
#     return conn

# ==== SESSION STATE INITIALIZATION ====
if "tabs_loaded" not in st.session_state:
    st.session_state["tabs_loaded"] = False

# ==== MANUAL CACHE REFRESH ====
if st.button("Refresh data"):
    load_students.clear()
    load_ref_answers.clear()
    st.rerun()

# ==== LOAD MAIN DATAFRAMES ONCE ====
if os.getenv("EMAIL_SKIP_PRELOAD") == "1":
    df_students = pd.DataFrame()
    df_ref_answers = pd.DataFrame()
else:
    with ThreadPoolExecutor() as executor:
        student_future = executor.submit(load_students)
        ref_future = executor.submit(load_ref_answers)
        df_students = student_future.result()
        df_ref_answers = ref_future.result()

# ==== UNIVERSAL VARIABLES (for later use) ====
LEVELS = sorted(df_students["level"].dropna().unique().tolist()) if "level" in df_students.columns else []
STUDENT_CODES = df_students["studentcode"].dropna().unique().tolist() if "studentcode" in df_students.columns else []

# ==== END OF STAGE 2 ====

import textwrap

# ====== HELPERS ======
def wrap_lines(text, width=80):
    """Wrap text to avoid FPDF width errors."""
    lines = []
    for para in text.split("\n"):
        lines.extend(textwrap.wrap(para, width=width) or [""])
    return lines

# ====== COURSE SCHEDULE CONSTANTS ======
RAW_SCHEDULE_A1 = [
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
RAW_SCHEDULE_A2 = [
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
RAW_SCHEDULE_B1 = [
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
# ==== TABS SETUP ====
tab_titles = [
    "📧 Course",                 # 0
    "📘 Class Attendance",       # 1
]

if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = 0  # Course tab index

selected_tab = st.sidebar.radio(
    "Navigate",
    tab_titles,
    index=st.session_state.get("active_tab", 0),
)
st.session_state["active_tab"] = tab_titles.index(selected_tab)

# ==== TAB 0: COURSE SCHEDULE ====
if selected_tab == tab_titles[0]:
    import pandas as pd
    import textwrap
    from datetime import date, timedelta
    from fpdf import FPDF
    import json

    st.markdown("""
    <div style='background:#e3f2fd;padding:1.2em 1em 0.8em 1em;border-radius:12px;margin-bottom:1em'>
      <h2 style='color:#1565c0;'>📆 <b>Intelligenter Kursplan-Generator (A1, A2, B1)</b></h2>
      <p style='font-size:1.08em;color:#333'>Erstellen Sie einen vollständigen, individuell angepassten Kursplan zum Download (TXT oder PDF) – <b>mit Ferien und flexiblem Wochenrhythmus!</b></p>
    </div>
    """, unsafe_allow_html=True)

    # Step 1: Choose course level
    st.markdown("### 1️⃣ **Kursniveau wählen**")
    course_levels = {"A1": RAW_SCHEDULE_A1, "A2": RAW_SCHEDULE_A2, "B1": RAW_SCHEDULE_B1}
    selected_level = st.selectbox("🗂️ **Kursniveau (A1/A2/B1):**", list(course_levels.keys()))
    topic_structure = course_levels[selected_level]
    st.markdown("---")

    # Step 2: Basic info & breaks
    st.markdown("### 2️⃣ **Kursdaten, Ferien, Modus**")
    col1, col2 = st.columns([2,1])
    with col1:
        start_date = st.date_input("📅 **Kursstart**", value=date.today())
        holiday_dates = st.multiselect(
            "🔔 Ferien oder Feiertage (Holiday/Break Dates)",
            options=[start_date + timedelta(days=i) for i in range(120)],
            format_func=lambda d: d.strftime("%A, %d %B %Y"),
            help="Kein Unterricht an diesen Tagen."
        )
    with col2:
        advanced_mode = st.toggle("⚙️ Erweiterter Wochen-Rhythmus (Custom weekly pattern)", value=False)
    st.markdown("---")

    # Step 3: Weekly pattern
    st.markdown("### 3️⃣ **Unterrichtstage festlegen**")
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    default_days = ["Monday", "Tuesday", "Wednesday"]

    week_patterns = []
    if not advanced_mode:
        days_per_week = st.multiselect("📌 **Unterrichtstage wählen:**", options=days_of_week, default=default_days)
        for week_label, sessions in topic_structure:
            week_patterns.append((len(sessions), days_per_week))
    else:
        st.info("Für jede Woche individuelle Unterrichtstage einstellen.")
        for i, (week_label, sessions) in enumerate(topic_structure):
            with st.expander(f"{week_label}", expanded=True):
                week_days = st.multiselect(
                    f"Unterrichtstage {week_label}",
                    options=days_of_week,
                    default=default_days,
                    key=f"week_{i}_days"
                )
                week_patterns.append((len(sessions), week_days or default_days))
    st.markdown("---")

    # Generate session dates skipping holidays
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

    # Build preview table
    rows = []
    for i, ((week_label, topic), d) in enumerate(zip(session_labels, dates)):
        rows.append({
            "Week": week_label,
            "Day": f"Day {i+1}",
            "Date": d.strftime("%A, %d %B %Y"),
            "Topic": topic
        })
    df = pd.DataFrame(rows)
    st.markdown(f"""
    <div style='background:#fffde7;border:1px solid #ffe082;border-radius:10px;padding:1em;margin:1em 0'>
      <b>📝 Kursüberblick:</b>
      <ul>
        <li><b>Kurs:</b> {selected_level}</li>
        <li><b>Start:</b> {start_date.strftime('%A, %d %B %Y')}</li>
        <li><b>Sessions:</b> {total_sessions}</li>
        <li><b>Ferien:</b> {', '.join(d.strftime('%d.%m.%Y') for d in holiday_dates) if holiday_dates else '–'}</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown("---")

    # ---- TXT download ----
    file_date = start_date.strftime("%Y-%m-%d")
    file_prefix = f"{selected_level}_{file_date}_course_schedule"

    txt = (
        "Learn Language Education Academy\n"
        "Contact: 0205706589 | www.learngermanghana.com\n"
        f"Schedule: {selected_level}\n"
        f"Start: {start_date.strftime('%Y-%m-%d')}\n\n"
    )
    for row in rows:
        txt += f"- {row['Day']} ({row['Date']}): {row['Topic']}\n"

    st.download_button(
        "📁 TXT Download",
        txt,
        file_name=f"{file_prefix}.txt"
    )

    json_rows = [
        {
            "week": row["Week"],
            "day": row["Day"],
            "date": row["Date"],
            "date_iso": dates[i].isoformat(),
            "topic": row["Topic"],
        }
        for i, row in enumerate(rows)
    ]
    schedule_payload = {
        "course_level": selected_level,
        "start_date": start_date.isoformat(),
        "total_sessions": total_sessions,
        "holidays": [d.isoformat() for d in holiday_dates],
        "sessions": json_rows,
    }
    schedule_json = json.dumps(schedule_payload, ensure_ascii=False, indent=2)

    st.download_button(
        "🧾 JSON Download",
        schedule_json,
        file_name=f"{file_prefix}.json",
        mime="application/json"
    )

    # ---- PDF download (reliable logic, like Send Email tab) ----
    class SchedulePDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 9, safe_pdf("Learn Language Education Academy"), ln=True, align='C')
            self.set_font('Arial', '', 11)
            self.cell(0, 7, safe_pdf("www.learngermanghana.com | 0205706589 | Accra, Ghana"), ln=True, align='C')
            self.ln(6)
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.5)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(3)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, safe_pdf("Schedule generated by Learn Language Education Academy."), 0, 0, 'C')

    pdf = SchedulePDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, safe_pdf(f"Course Schedule: {selected_level}"), ln=True)
    pdf.cell(0, 8, safe_pdf(f"Start Date: {start_date.strftime('%A, %d %B %Y')}"), ln=True)
    pdf.ln(4)
    for row in rows:
        line = f"{row['Day']} ({row['Date']}): {row['Topic']}"
        pdf.multi_cell(0, 8, safe_pdf(line))
        pdf.ln(1)
    pdf.ln(3)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 8, safe_pdf("Felix Asadu (Director)"), ln=True, align='R')

    # --- Ensure PDF bytes are correct ---
    output_data = pdf.output(dest="S")
    if isinstance(output_data, bytes):
        pdf_bytes = output_data
    elif isinstance(output_data, str):
        pdf_bytes = output_data.encode("latin-1", "replace")
    else:
        # fallback via temp file
        import tempfile, os
        tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(tmpf.name)
        tmpf.close()
        with open(tmpf.name, "rb") as f:
            pdf_bytes = f.read()
        os.remove(tmpf.name)

    st.download_button(
        "📄 Download Schedule PDF",
        data=pdf_bytes,
        file_name=f"{file_prefix}.pdf",
        mime="application/pdf"
    )


# ==== TAB 1: CLASS ATTENDANCE ====
elif selected_tab == tab_titles[1]:
    st.title("📘 Class Attendance")

    df_students = load_students()

    if df_students.empty:
        st.info("No student data available.")
    else:
        class_groups = (
            df_students.groupby(["classname", "level"]).size().reset_index()[["classname", "level"]]
        )
        class_groups["label"] = class_groups.apply(
            lambda r: f"{r['classname']} ({r['level']})", axis=1
        )
        selection = st.selectbox("Select class", class_groups["label"].tolist())
        selected = class_groups[class_groups["label"] == selection].iloc[0]
        sel_class = selected["classname"]
        sel_level = selected["level"]

        class_df = df_students[
            (df_students["classname"] == sel_class) & (df_students["level"] == sel_level)
        ].copy()

        schedule_map = {
            "A1": RAW_SCHEDULE_A1,
            "A2": RAW_SCHEDULE_A2,
            "B1": RAW_SCHEDULE_B1,
        }
        schedule = schedule_map.get(sel_level.upper(), [])

        session_labels = []
        for week, topics in schedule:
            for topic in topics:
                session_labels.append(f"{week}: {topic}")

        if not session_labels:
            st.info("No schedule defined for this level.")
        else:
            st.write("### Attendance")
            existing_attendance = {}
            try:
                existing_attendance = load_attendance_from_firestore(sel_class)
            except Exception:
                st.info("Could not load existing attendance.")

            # Ensure session labels incorporate any stored labels and sessions
            max_existing = max((int(s) for s in existing_attendance.keys()), default=-1)
            if max_existing + 1 > len(session_labels):
                session_labels.extend(["" for _ in range(max_existing + 1 - len(session_labels))])
            for i in range(len(session_labels)):
                stored_label = existing_attendance.get(str(i), {}).get("label")
                if stored_label:
                    session_labels[i] = stored_label

            session_ids = [f"session_{i}" for i in range(len(session_labels))]
            session_display_labels = {}
            for i, label in enumerate(session_labels):
                session_display_labels[session_ids[i]] = label or f"Session {i + 1}"

            # Merge student codes and names from roster and existing attendance
            student_codes = list(class_df["studentcode"])
            for session in existing_attendance.values():
                for s_code in session.get("students", {}):
                    if s_code not in student_codes:
                        student_codes.append(s_code)

            student_names = {row["studentcode"]: row["name"] for _, row in class_df.iterrows()}
            for session in existing_attendance.values():
                for s_code, s_data in session.get("students", {}).items():
                    if s_data.get("name"):
                        student_names[s_code] = s_data["name"]

            data = {"Student": [student_names.get(code, "") for code in student_codes]}
            for i, session_id in enumerate(session_ids):
                data[session_id] = [
                    bool(
                        existing_attendance.get(str(i), {})
                        .get("students", {})
                        .get(code, {})
                        .get("present", False)
                    )
                    for code in student_codes
                ]

            att_df = pd.DataFrame(data, index=student_codes)
            att_df.index.name = "Student Code"

            editor_widget_key = "attendance_editor"
            editor_data_key = "attendance_editor_data"
            editor_class_key = "attendance_editor_class"
            editor_sessions_key = "attendance_editor_sessions"
            if (
                editor_data_key not in st.session_state
                or st.session_state.get(editor_class_key) != sel_class
                or st.session_state.get(editor_sessions_key) != session_ids
            ):
                st.session_state[editor_data_key] = att_df
                st.session_state[editor_class_key] = sel_class
                st.session_state[editor_sessions_key] = session_ids

            view_mode = st.radio(
                "Attendance view",
                ["All sessions", "Focus on a session"],
                key="attendance_view_mode",
                horizontal=True,
            )
            focus_label = None
            if view_mode == "Focus on a session":
                focus_label = st.selectbox(
                    "Select session to edit",
                    session_ids,
                    key="attendance_focus_label",
                    format_func=lambda session_id: session_display_labels.get(
                        session_id, session_id
                    ),
                )

            bulk_label = st.selectbox(
                "Mark everyone present for session",
                session_ids,
                key="attendance_bulk_label",
                format_func=lambda session_id: session_display_labels.get(
                    session_id, session_id
                ),
            )
            if st.button("Mark everyone present"):
                st.session_state[editor_data_key][bulk_label] = True

            if view_mode == "Focus on a session" and focus_label:
                focus_editor_key = f"{editor_widget_key}_focus_{focus_label}"
                focus_df = st.session_state[editor_data_key][["Student", focus_label]]
                edited_focus_df = st.data_editor(
                    focus_df,
                    key=focus_editor_key,
                    column_config={
                        "Student": st.column_config.TextColumn("Student", disabled=True),
                        focus_label: st.column_config.CheckboxColumn(
                            session_display_labels.get(focus_label, focus_label)
                        ),
                    },
                    use_container_width=True,
                )
                st.session_state[editor_data_key][focus_label] = edited_focus_df[focus_label]
            else:
                edited_att_df = st.data_editor(
                    st.session_state[editor_data_key],
                    key=f"{editor_widget_key}_all",
                    column_config={
                        "Student": st.column_config.TextColumn("Student", disabled=True),
                        **{
                            session_id: st.column_config.CheckboxColumn(
                                session_display_labels.get(session_id, session_id)
                            )
                            for session_id in session_ids
                        },
                    },
                    use_container_width=True,
                )
                st.session_state[editor_data_key] = edited_att_df

            if st.button("Save attendance"):
                attendance_map = {}
                for i, label in enumerate(session_labels):
                    attendance_map[str(i)] = {"label": label, "students": {}}

                for student_code, row in st.session_state[editor_data_key].iterrows():
                    student_name = row["Student"]
                    for i, label in enumerate(session_labels):
                        session_id = session_ids[i]
                        attendance_map[str(i)]["students"][student_code] = {
                            "name": student_name,
                            "present": bool(row[session_id]),
                        }

                save_attendance_to_firestore(sel_class, attendance_map)
                st.success("Attendance saved.")
