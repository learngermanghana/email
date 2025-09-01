# ==== IMPORTS ====
import os
import re
import requests
import tempfile
import urllib.parse
from datetime import datetime, date, timedelta
import smtplib
from email.message import EmailMessage
import base64
import textwrap

import pandas as pd
import streamlit as st
from fpdf import FPDF, HTMLMixin
import qrcode
from PIL import Image  # For logo image handling
from io import BytesIO
from utils import safe_pdf
from pdf_utils import generate_receipt_and_contract_pdf

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
PENDING_SHEET_ID = "1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo"
PENDING_CSV_URL = f"https://docs.google.com/spreadsheets/d/{PENDING_SHEET_ID}/export?format=csv"

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

@st.cache_data(ttl=300, show_spinner="Loading student data...")
def load_students():
    df = pd.read_csv(STUDENTS_CSV_URL, dtype=str)
    df = normalize_columns(df)
    # Standardize any known column name variants
    if "student_code" in df.columns:
        df = df.rename(columns={"student_code": "studentcode"})
    return df

@st.cache_data(ttl=300, show_spinner="Loading reference answers...")
def load_ref_answers():
    df = pd.read_csv(REF_ANSWERS_CSV_URL, dtype=str)
    df = normalize_columns(df)
    if "assignment" not in df.columns:
        raise Exception("No 'assignment' column found in reference answers sheet.")
    return df

@st.cache_data(ttl=300, show_spinner="Loading pending students...")
def load_pending_students():
    df = pd.read_csv(PENDING_CSV_URL, dtype=str)
    df = normalize_columns(df)
    df_display = df.copy()
    df_search = df.copy()
    return df_display, df_search

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

# ==== LOAD MAIN DATAFRAMES ONCE ====
df_students = load_students()
df_ref_answers = load_ref_answers()

# ==== UNIVERSAL VARIABLES (for later use) ====
LEVELS = sorted(df_students["level"].dropna().unique().tolist()) if "level" in df_students.columns else []
STUDENT_CODES = df_students["studentcode"].dropna().unique().tolist() if "studentcode" in df_students.columns else []

# ==== END OF STAGE 2 ====

# ==== TABS SETUP ====
tab_titles = [
    "📝 Pending",                # 0
    "👩‍🎓 All Students",           # 1
    "📲 Reminders",              # 2
    "📄 Contract",               # 3
    "📧 Send Email",             # 4
    "📧 Course",                 # 5
    "🏆 Leadership Board"        # 6  <-- NEW
]

if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = 3  # Contract tab index

tabs = st.tabs(tab_titles)

# ==== TAB 0: PENDING STUDENTS (REWRITTEN) ====
with tabs[0]:
    import os
    import re
    import json
    import requests
    import pandas as pd
    from datetime import date, timedelta
    import streamlit as st

    st.title("🕒 Pending Students (Form Responses ➜ Review, Edit, Send)")

    # ---------- CONFIG ----------
    # Form responses (pending)
    PENDING_SHEET_ID = "1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo"
    PENDING_CSV_URL = f"https://docs.google.com/spreadsheets/d/{PENDING_SHEET_ID}/export?format=csv"

    # Apps Script Web App endpoint (same key name you used before).
    # You can also set ENV var PENDING_TO_MAIN_WEBAPP_URL
    APPS_SCRIPT_WEBAPP_URL = (
        st.secrets.get("apps_script", {}).get("pending_to_main_webapp_url")
        or os.getenv("PENDING_TO_MAIN_WEBAPP_URL")
        or ""  # put a literal URL string here if you prefer
    )

    # Optional API key (if your Apps Script checks ?key=...)
    DEFAULT_API_KEY = (
        st.secrets.get("apps_script", {}).get("app_key")
        or os.getenv("APP_KEY")
        or ""
    )

    # The exact target columns (order matters; must match Apps Script REQUIRED_HEADERS)
    TARGET_COLUMNS = [
        "Name", "Phone", "Location", "Level", "Paid", "Balance",
        "ContractStart", "ContractEnd", "StudentCode", "Email",
        "Emergency Contact (Phone Number)", "Status", "EnrollDate", "ClassName"
    ]

    # ---------- LOCAL HELPERS (safe fallbacks) ----------
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        if 'normalize_columns' in globals() and callable(normalize_columns):
            return normalize_columns(df)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df

    def _col_lookup(df: pd.DataFrame, key: str, default=None):
        if 'col_lookup' in globals() and callable(col_lookup):
            return col_lookup(df, key, default)
        k = key.lower().replace(" ", "").replace("_", "")
        for c in df.columns:
            if c.lower().replace(" ", "").replace("_", "") == k:
                return c
        return default

    def _clean_phone_gh(phone):
        # Prefer your global clean_phone if present
        if 'clean_phone' in globals() and callable(clean_phone):
            return clean_phone(phone)
        digits = re.sub(r"\D", "", str(phone or ""))
        if len(digits) == 9 and digits[0] in {"2", "5", "9"}:
            digits = "0" + digits
        if digits.startswith("0") and len(digits) == 10:
            return "233" + digits[1:]
        if digits.startswith("233") and len(digits) == 12:
            return digits
        return None

    def _to_float(s, default=0.0):
        try:
            return float(str(s).replace(",", "").strip())
        except Exception:
            return default

    def _parse_date_iso(s):
        """Return ISO yyyy-mm-dd or '' if invalid/empty."""
        ts = pd.to_datetime(s, errors="coerce")
        return ts.date().isoformat() if pd.notna(ts) else ""

    def _first_nonempty(d: dict, *keys):
        for k in keys:
            v = d.get(k, "")
            if v not in (None, ""):
                return v
        return ""

    @st.cache_data(ttl=0, show_spinner="Loading pending form submissions...")
    def load_pending():
        df = pd.read_csv(PENDING_CSV_URL, dtype=str)
        return _normalize_columns(df)

    def map_pending_row_to_target(src: dict) -> dict:
        """
        Build a single row in the TARGET_COLUMNS shape from a raw pending row.
        We try flexible key matching for robustness.
        """
        # Flexible column candidates:
        name   = _first_nonempty(src, _col_lookup_df.get("name",""), _col_lookup_df.get("full_name",""))
        phone  = _first_nonempty(src, _col_lookup_df.get("phone",""), _col_lookup_df.get("phone_number",""))
        email  = _first_nonempty(src, _col_lookup_df.get("email",""), _col_lookup_df.get("email_address",""))
        loc    = _first_nonempty(src, _col_lookup_df.get("location",""), _col_lookup_df.get("city",""))
        level  = _first_nonempty(src, _col_lookup_df.get("level",""), _col_lookup_df.get("class",""))
        paid   = _first_nonempty(src, _col_lookup_df.get("paid",""), _col_lookup_df.get("amount_paid",""))
        bal    = _first_nonempty(src, _col_lookup_df.get("balance",""), _col_lookup_df.get("outstanding",""))
        cstart = _first_nonempty(src, _col_lookup_df.get("contractstart",""), _col_lookup_df.get("start_date",""))
        cend   = _first_nonempty(src, _col_lookup_df.get("contractend",""), _col_lookup_df.get("end_date",""))
        code   = _first_nonempty(src, _col_lookup_df.get("studentcode",""), _col_lookup_df.get("student_code",""), _col_lookup_df.get("code",""))
        ecand  = _first_nonempty(
            src,
            _col_lookup_df.get("emergency_contact_phone_number",""),
            _col_lookup_df.get("emergency_contact",""),
            _col_lookup_df.get("emergency",""),
            _col_lookup_df.get("guardian_phone",""),
        )
        status = _first_nonempty(src, _col_lookup_df.get("status",""))
        enroll = _first_nonempty(src, _col_lookup_df.get("enrolldate",""), _col_lookup_df.get("enroll_date",""), _col_lookup_df.get("registration_date",""))
        cname  = _first_nonempty(src, _col_lookup_df.get("classname",""), _col_lookup_df.get("class_name",""), _col_lookup_df.get("course",""))

        # Coercions/cleanups
        phone_norm = _clean_phone_gh(phone) or ""
        ec_norm    = _clean_phone_gh(ecand) or ""

        paid_f = _to_float(paid, 0.0)
        bal_f  = _to_float(bal, 0.0)

        cs_iso = _parse_date_iso(cstart)
        ce_iso = _parse_date_iso(cend)
        en_iso = _parse_date_iso(enroll) or date.today().isoformat()

        # If no contract end but we have start, default +30 days
        if not ce_iso and cs_iso:
            try:
                y, m, d = [int(x) for x in cs_iso.split("-")]
                ce_iso = (date(y, m, d) + timedelta(days=30)).isoformat()
            except Exception:
                ce_iso = ""

        level_up = str(level).upper().strip() if level else ""

        # Build target
        row = {
            "Name": str(name).strip(),
            "Phone": phone_norm,
            "Location": str(loc).strip(),
            "Level": level_up,
            "Paid": paid_f,
            "Balance": bal_f,
            "ContractStart": cs_iso,
            "ContractEnd": ce_iso,
            "StudentCode": str(code).strip(),
            "Email": str(email).strip(),
            "Emergency Contact (Phone Number)": ec_norm,
            "Status": str(status or "Active").strip(),
            "EnrollDate": en_iso,
            "ClassName": str(cname or level_up).strip(),
        }
        # Only keep required keys & order
        return {k: row.get(k, "") for k in TARGET_COLUMNS}

    def post_rows(rows: list, api_key: str = "") -> tuple[bool, str, dict | None]:
        if not APPS_SCRIPT_WEBAPP_URL:
            return False, "Apps Script Web App URL is not configured.", None
        try:
            url = APPS_SCRIPT_WEBAPP_URL
            if api_key:
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}key={api_key}"
            resp = requests.post(url, json={"rows": rows}, timeout=30)
            # Apps Script can't set HTTP status reliably; parse JSON payload
            try:
                data = resp.json()
            except Exception:
                data = {"ok": False, "error": f"Non-JSON response (HTTP {resp.status_code})"}
            if data.get("ok"):
                return True, "OK", data
            else:
                # Include body snippet for debugging
                return False, data.get("error") or f"HTTP {resp.status_code}: {resp.text[:300]}", data
        except Exception as e:
            return False, f"Request failed: {e}", None

    # ---------- UI: Load + Review ----------
    df_pending = load_pending()
    if df_pending.empty:
        st.info("No pending form submissions found yet.")
        st.stop()

    # Resolve column lookups once
    _col_lookup_df = {}
    for k in [
        "name","full_name","phone","phone_number","email","email_address","location","city","class","level",
        "paid","amount_paid","balance","outstanding","contractstart","start_date","contractend","end_date",
        "studentcode","student_code","code","classname","class_name","course",
        "emergency_contact_phone_number","emergency_contact","emergency","guardian_phone",
        "status","enrolldate","enroll_date","registration_date"
    ]:
        _col_lookup_df[k] = _col_lookup(df_pending, k, default=None)

    # Free-text search over the raw pending table (to quickly find a form)
    st.markdown("### 1️⃣ Review those who filled the form")
    search = st.text_input("🔍 Search any field (name, email, phone, etc.)", "")
    view_df = df_pending.copy()
    if search:
        s = search.strip().lower()
        view_df = view_df[view_df.apply(lambda r: s in str(r.to_dict()).lower(), axis=1)]

    st.caption(f"Showing {len(view_df)} of {len(df_pending)} pending rows.")
    with st.expander("Show raw pending rows", expanded=False):
        st.dataframe(view_df, use_container_width=True, height=320)

    # ---------- Build editable TARGET table ----------
    st.markdown("### 2️⃣ Edit student info (normalized to main sheet columns)")
    mapped_rows = [map_pending_row_to_target(r._asdict() if hasattr(r, "_asdict") else r)
                   for r in view_df.to_dict(orient="records")]

    edit_df = pd.DataFrame(mapped_rows, columns=TARGET_COLUMNS)
    # Add a selection column for sending
    edit_df.insert(0, "Select", True)

    # Helpful defaults: if both Phone and Email are blank, de-select (won't pass validation)
    edit_df.loc[(edit_df["Phone"] == "") & (edit_df["Email"] == ""), "Select"] = False

    edited = st.data_editor(
        edit_df,
        use_container_width=True,
        height=460,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", help="Tick rows to send", default=True),
            "Paid": st.column_config.NumberColumn("Paid (GHS)", step=1.0, format="%.2f"),
            "Balance": st.column_config.NumberColumn("Balance (GHS)", step=1.0, format="%.2f"),
            "ContractStart": st.column_config.DateColumn("ContractStart"),
            "ContractEnd": st.column_config.DateColumn("ContractEnd"),
            "EnrollDate": st.column_config.DateColumn("EnrollDate"),
        },
        key="pending_editor_new",
    )

    # ---------- Validation preview ----------
    st.markdown("### 3️⃣ Validate & Send to Main Sheet")
    c1, c2 = st.columns([1,1])
    with c1:
        api_key_input = st.text_input("Optional API Key (Apps Script ?key=...)", value=DEFAULT_API_KEY or "")
    with c2:
        st.write("")  # spacing
        st.caption("If your script has APP_KEY set, provide it here; leave blank if not used.")

    # Build payload from the edited table
    to_send = []
    problems = []
    for idx, r in edited.iterrows():
        if not r.get("Select", False):
            continue

        # Ensure minimal validity
        name = str(r.get("Name", "")).strip()
        phone = str(r.get("Phone", "")).strip()
        email = str(r.get("Email", "")).strip()

        if not name:
            problems.append(f"Row {idx+1}: Name is required.")
            continue
        if not (phone or email):
            problems.append(f"Row {idx+1}: Provide at least Phone or Email.")
            continue

        # Clean/normalize values
        phone_norm = _clean_phone_gh(phone) or ""
        ec_norm    = _clean_phone_gh(r.get("Emergency Contact (Phone Number)", "")) or ""

        paid_f = _to_float(r.get("Paid", 0))
        bal_f  = _to_float(r.get("Balance", 0))

        cs_iso = _parse_date_iso(r.get("ContractStart", ""))
        ce_iso = _parse_date_iso(r.get("ContractEnd", ""))
        en_iso = _parse_date_iso(r.get("EnrollDate", "")) or date.today().isoformat()

        # If only start provided, auto-fill end = start + 30 days
        if cs_iso and not ce_iso:
            y, m, d = [int(x) for x in cs_iso.split("-")]
            ce_iso = (date(y, m, d) + timedelta(days=30)).isoformat()

        row_out = {
            "Name": name,
            "Phone": phone_norm,
            "Location": str(r.get("Location", "")).strip(),
            "Level": str(r.get("Level", "")).upper().strip(),
            "Paid": paid_f,
            "Balance": bal_f,
            "ContractStart": cs_iso,
            "ContractEnd": ce_iso,
            "StudentCode": str(r.get("StudentCode", "")).strip(),
            "Email": email,
            "Emergency Contact (Phone Number)": ec_norm,
            "Status": str(r.get("Status", "") or "Active").strip(),
            "EnrollDate": en_iso,
            "ClassName": str(r.get("ClassName", "")).strip(),
        }
        # Keep order strictly
        row_out = {k: row_out.get(k, "") for k in TARGET_COLUMNS}
        to_send.append(row_out)

    if problems:
        st.warning("Please fix these issues before sending:")
        for p in problems:
            st.markdown(f"- {p}")

    with st.expander("Preview JSON payload", expanded=False):
        st.code(json.dumps({"rows": to_send}, ensure_ascii=False, indent=2))

    left, right = st.columns([1,1])
    with left:
        send_btn = st.button("🚚 Send selected to Main Sheet", type="primary", disabled=(len(to_send) == 0))
    with right:
        st.download_button(
            "⬇️ Download edited CSV",
            pd.DataFrame(to_send)[TARGET_COLUMNS].to_csv(index=False),
            file_name="pending_to_send.csv"
        )

    if send_btn:
        with st.status("Sending rows to Apps Script…", expanded=True) as status:
            ok, msg, data = post_rows(to_send, api_key_input.strip())
            if ok:
                st.success(f"✅ Sent {len(to_send)} row(s).")
                if data and "results" in data:
                    st.json(data["results"])
                status.update(label="Done", state="complete")

                # Refresh main list & optionally jump to All Students tab
                try:
                    load_students.clear()
                except Exception:
                    pass
                try:
                    df_students = load_students()
                except Exception:
                    pass

                if st.button("👀 View in All Students"):
                    st.session_state["active_tab"] = 1
                    st.rerun()
            else:
                st.error(f"❌ Failed to send: {msg}")



# ==== TAB 1: ALL STUDENTS ====
with tabs[1]:
    st.title("👩‍🎓 All Students")

    # --- Optional: Search/Filter ---
    search = st.text_input("🔍 Search students by name, code, or email...")
    if search:
        search = search.lower().strip()
        filt = df_students[
            df_students.apply(lambda row: search in str(row).lower(), axis=1)
        ]
    else:
        filt = df_students

    # --- Show Student Table ---
    st.dataframe(filt, use_container_width=True)

    # --- Download Button ---
    st.download_button(
        "⬇️ Download All Students CSV",
        filt.to_csv(index=False),
        file_name="all_students.csv"
    )

# ==== TAB 2: WHATSAPP REMINDERS ====
with tabs[2]:
    st.title("📲 WhatsApp Reminders for Debtors")

    # --- Use cached df_students loaded at the top ---
    df = df_students.copy()

    # --- Column Lookup for legacy headers ---
    code_col = col_lookup(df, "studentcode")
    name_col = col_lookup(df, "name")
    phone_col = col_lookup(df, "phone")
    email_col = col_lookup(df, "email")
    bal_col = col_lookup(df, "balance")

    # --- Clean Data Types ---
    df[bal_col] = pd.to_numeric(df[bal_col], errors="coerce").fillna(0)
    df["paid"] = pd.to_numeric(df["paid"], errors="coerce").fillna(0)
    df["contractstart"] = pd.to_datetime(df["contractstart"], errors="coerce")
    df[phone_col] = df[phone_col].astype(str).str.replace(r"[^\d+]", "", regex=True)

    # --- Calculate Due Date & Days Left ---
    df["due_date"] = df["contractstart"] + pd.Timedelta(days=30)
    df["due_date_str"] = df["due_date"].dt.strftime("%d %b %Y")
    df["days_left"] = (df["due_date"] - pd.Timestamp.today()).dt.days

    # --- Financial Summary ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Students", len(df))
    m2.metric("Total Collected (GHS)", f"{df['paid'].sum():,.2f}")
    m3.metric("Total Outstanding (GHS)", f"{df[bal_col].sum():,.2f}")

    st.markdown("---")

    # --- Filter/Search UI ---
    show_all = st.toggle("Show all students (not just debtors)", value=False)
    search = st.text_input("Search by name, code, or phone", key="wa_search")
    selected_level = st.selectbox("Filter by Level", ["All"] + sorted(df["level"].dropna().unique()), key="wa_level")

    filt = df.copy()
    if not show_all:
        filt = filt[filt[bal_col] > 0]
    if search:
        mask1 = filt[name_col].str.contains(search, case=False, na=False)
        mask2 = filt[code_col].astype(str).str.contains(search, case=False, na=False)
        mask3 = filt[phone_col].str.contains(search, case=False, na=False)
        filt = filt[mask1 | mask2 | mask3]
    if selected_level != "All":
        filt = filt[filt["level"] == selected_level]

    st.markdown("---")

    # --- Table Preview ---
    tbl = filt[[name_col, code_col, phone_col, "level", bal_col, "due_date_str", "days_left"]].rename(columns={
        name_col: "Name", code_col: "Student Code", phone_col: "Phone",
        "level": "Level", bal_col: "Balance (GHS)", "due_date_str": "Due Date", "days_left": "Days Left"
    })
    st.dataframe(tbl, use_container_width=True)

    # --- WhatsApp Message Template ---
    wa_template = st.text_area(
        "Custom WhatsApp Message Template",
        value="Hi {name}! Friendly reminder: your payment for the {level} class is due by {due}. {msg} Thank you!",
        help="You can use {name}, {level}, {due}, {bal}, {days}, {msg}"
    )

    email_template = st.text_area(
        "Custom Email Message Template",
        value=(
            "Hello {name},\n\n"
            "This is a friendly reminder that your payment for the {level} class is due by {due}. {msg}\n\n"
            "Thank you!"
        ),
        help="You can use {name}, {level}, {due}, {bal}, {days}, {msg}"
    )

    email_mode = st.radio(
        "Email Mode",
        ["Mailto Links", "Send Branded Emails"],
        horizontal=True,
    )
    attachments = []
    if email_mode == "Send Branded Emails":
        uploaded_files = st.file_uploader(
            "Optional attachments",
            accept_multiple_files=True,
        )
        if uploaded_files:
            attachments = [(f.getvalue(), f.name, f.type) for f in uploaded_files]

    # --- WhatsApp Links Generation ---
    links = []
    invalid_numbers = set()
    for _, row in filt.iterrows():

        raw_phone = row[phone_col]
        raw_phone_str = str(raw_phone)
        phone = clean_phone(raw_phone)
        bal = f"GHS {row[bal_col]:,.2f}"

        due = row["due_date_str"]
        days = int(row["days_left"])
        if days >= 0:
            msg = f"You have {days} {'day' if days == 1 else 'days'} left to settle the {bal} balance."
        else:
            msg = f"Your payment is overdue by {abs(days)} {'day' if abs(days)==1 else 'days'}. Please settle as soon as possible."
        text = wa_template.format(
            name=row[name_col],
            level=row["level"],
            due=due,
            bal=bal,
            days=days,
            msg=msg
        )

        if pd.isna(raw_phone) or raw_phone_str.strip() == "":
            # No phone provided – build generic link
            link = f"https://wa.me/?text={urllib.parse.quote(text)}"
        elif phone:
            link = f"https://wa.me/{phone}?text={urllib.parse.quote(text)}"
        else:
            link = ""
            if raw_phone_str not in invalid_numbers:
                st.warning(f"Invalid phone number for {row[name_col]}: {raw_phone_str}")
                invalid_numbers.add(raw_phone_str)

        email_addr = row[email_col]
        mailto = ""
        body = ""
        subject = "Payment Reminder"
        if email_addr and pd.notna(email_addr):
            body = email_template.format(
                name=row[name_col],
                level=row["level"],
                due=due,
                bal=bal,
                days=days,
                msg=msg,
            )
            if email_mode == "Mailto Links":
                mailto = (
                    f"mailto:{email_addr}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
                )

        links.append({
            "Name": row[name_col],
            "Student Code": row[code_col],
            "Level": row["level"],
            "Balance (GHS)": bal,
            "Due Date": due,
            "Days Left": days,
            "Phone": phone or "",
            "WhatsApp Link": link,
            "Email": email_addr or "",
            "Email Link": mailto,
            "Email Body": body,
        })

    df_links = pd.DataFrame(links)
    st.markdown("---")
    cols = [
        "Name",
        "Level",
        "Balance (GHS)",
        "Due Date",
        "Days Left",
        "WhatsApp Link",
        "Email",
    ]
    if email_mode == "Mailto Links":
        cols.append("Email Link")
    st.dataframe(df_links[cols], use_container_width=True)

    # --- List links for quick access ---
    st.markdown("### Send WhatsApp Reminders")
    for i, row in df_links.iterrows():
        if row["WhatsApp Link"]:
            st.markdown(f"- **{row['Name']}** ([Send WhatsApp]({row['WhatsApp Link']}))")

    st.markdown("### Send Email Reminders")
    for _, row in df_links.iterrows():
        if email_mode == "Mailto Links":
            if row["Email Link"]:
                st.markdown(
                    f"- **{row['Name']}** ([Send Email]({row['Email Link']}))"
                )
        else:
            if row["Email"]:
                if st.button(
                    f"Send Email to {row['Name']}",
                    key=f"email_{row['Student Code']}",
                ):
                    html_body = render_reminder_html(row["Email Body"])
                    ok = send_email_report(
                        None,
                        row["Email"],
                        "Payment Reminder",
                        html_body,
                        attachments or None,
                    )
                    if ok:
                        st.success(f"Email sent to {row['Name']}")

    st.download_button(
        "📁 Download Reminder Links CSV",
        df_links[["Name", "Student Code", "Phone", "Email", "Level", "Balance (GHS)", "Due Date", "Days Left", "WhatsApp Link", "Email Link"]].to_csv(index=False),
        file_name="debtor_whatsapp_links.csv",
    )


# ==== TAB 3: CONTRACT & RECEIPT PDF ====
with tabs[3]:
    st.title("📄 Generate Contract & Receipt PDF for Any Student")

    google_csv = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    )
    df = pd.read_csv(google_csv)
    df = normalize_columns(df)

    if df.empty:
        st.warning("No student data available.")
        st.stop()

    code_col = col_lookup(df, "studentcode")

    search_val = st.text_input(
        "Search students by name, code, phone, or level:", 
        value="", key="pdf_tab_search_contract"
    )
    filtered_df = df.copy()
    if search_val:
        sv = search_val.strip().lower()
        filtered_df = df[
            df["name"].str.lower().str.contains(sv, na=False)
            | df[code_col].astype(str).str.lower().str.contains(sv, na=False)
            | df["phone"].astype(str).str.lower().str.contains(sv, na=False)
            | df["level"].astype(str).str.lower().str.contains(sv, na=False)
        ]
    student_names = filtered_df["name"].tolist()
    if not student_names:
        st.warning("No students match your search.")
        st.stop()
    selected_name = st.selectbox("Select Student", student_names)
    row = filtered_df[filtered_df["name"] == selected_name].iloc[0]

    default_paid    = float(row.get("paid", 0))
    default_balance = float(row.get("balance", 0))
    default_start = pd.to_datetime(row.get("contractstart", ""), errors="coerce").date()
    if pd.isnull(default_start):
        default_start = date.today()
    default_end = pd.to_datetime(row.get("contractend", ""), errors="coerce").date()
    if pd.isnull(default_end):
        default_end = default_start + timedelta(days=30)

    st.subheader("Receipt Details")
    paid_input    = st.number_input("Amount Paid (GHS)", min_value=0.0, value=default_paid, step=1.0)
    balance_input = st.number_input("Balance Due (GHS)", min_value=0.0, value=default_balance, step=1.0)
    total_input   = paid_input + balance_input
    receipt_date  = st.date_input("Receipt Date", value=date.today())
    signature     = st.text_input("Signature Text", value="Felix Asadu", key="pdf_signature_contract")

    st.subheader("Contract Details")
    contract_start_input = st.date_input("Contract Start Date", value=default_start, key="pdf_contract_start")
    contract_end_input   = st.date_input("Contract End Date", value=default_end, key="pdf_contract_end")
    course_length        = (contract_end_input - contract_start_input).days

    st.subheader("Agreement Template")

    def _wrap_agreement():
        tmpl = st.session_state["agreement_template_raw"]
        wrapped, warn_lines = wrap_template_lines(tmpl)
        st.session_state["agreement_template_raw"] = wrapped
        if warn_lines:
            st.warning(
                f"Lines {', '.join(map(str, warn_lines))} exceeded {AGREEMENT_LINE_LIMIT} characters without spaces and were wrapped."
            )

    st.text_area(
        "Payment Agreement Template",
        value=st.session_state.get("agreement_template_raw", ""),
        key="agreement_template_raw",
        on_change=_wrap_agreement,
        height=300,
        help=f"Lines over {AGREEMENT_LINE_LIMIT} characters without spaces will be wrapped automatically.",
    )

    logo_url = "https://drive.google.com/uc?export=download&id=1xLTtiCbEeHJjrASvFjBgfFuGrgVzg6wU"
    local_logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    cached_logo_path = "/tmp/school_logo.png"

    def sanitize_text(text):
        cleaned = "".join(c if ord(c) < 256 else "?" for c in str(text))
        return " ".join(cleaned.split())

    def break_long_words(line, max_len=40):
        tokens = line.split(" ")
        out = []
        for tok in tokens:
            while len(tok) > max_len:
                out.append(tok[:max_len])
                tok = tok[max_len:]
            out.append(tok)
        return " ".join(out)

    def safe_for_fpdf(line):
        txt = line.strip()
        if len(txt) < 2: return False
        if len(txt) == 1 and not txt.isalnum(): return False
        return True

    class ReceiptPDF(FPDF):
        def __init__(self, logo_path=None):
            super().__init__()
            self.logo_path = logo_path

        def header(self):
            if self.logo_path:
                try:
                    self.image(self.logo_path, x=10, y=8, w=28)
                except Exception:
                    pass
            self.set_font('Arial', 'B', 16)
            self.cell(0, 9, safe_pdf(SCHOOL_NAME), ln=True, align='C')
            self.set_font('Arial', '', 11)
            self.cell(0, 7, safe_pdf(f"{SCHOOL_WEBSITE} | {SCHOOL_PHONE} | {SCHOOL_ADDRESS}"), ln=True, align='C')
            self.set_font('Arial', 'I', 10)
            self.cell(0, 7, safe_pdf(f"Business Reg No: {BUSINESS_REG}"), ln=True, align='C')
            self.ln(3)
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.5)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(6)

        def footer(self):
            try:
                qr = make_qr_code(SCHOOL_WEBSITE)
                self.image(qr, x=180, y=275, w=18)
            except Exception:
                pass
            self.set_y(-18)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, safe_pdf("Generated by Learn Language Education Academy."), 0, 0, 'C')

    if st.button("Generate & Download PDF"):
        paid    = paid_input
        balance = balance_input
        total   = total_input

        logo_path = None
        try:
            img = Image.open(local_logo_path).convert("RGB")
            img.save(cached_logo_path)
            logo_path = cached_logo_path
        except Exception:
            if os.path.exists(cached_logo_path):
                logo_path = cached_logo_path
            else:
                try:
                    response = requests.get(logo_url)
                    if response.status_code == 200:
                        img = Image.open(BytesIO(response.content)).convert("RGB")
                        img.save(cached_logo_path)
                        logo_path = cached_logo_path
                    else:
                        st.warning("Could not download logo image from the URL.")
                except Exception as e:
                    st.warning(f"Logo insertion failed: {e}")

        pdf = ReceiptPDF(logo_path)
        pdf.add_page()

        status = "FULLY PAID" if balance == 0 else "INSTALLMENT PLAN"
        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 10, status, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        pdf.set_font("Arial", size=14)
        pdf.cell(0, 10, "Learn Language Education Academy Payment Receipt", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)

        pdf.set_font("Arial", size=12)
        for label, val in [
            ("Name", selected_name),
            ("Student Code", row.get(code_col, "")),
            ("Phone", row.get("phone", "")),
            ("Level", row.get("level", "")),
            ("Contract Start", contract_start_input),
            ("Contract End", contract_end_input),
            ("Amount Paid", f"GHS {paid:.2f}"),
            ("Balance Due", f"GHS {balance:.2f}"),
            ("Total Fee", f"GHS {total:.2f}"),
            ("Receipt Date", receipt_date)
        ]:
            text = f"{label}: {sanitize_text(val)}"
            pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)

        pdf.ln(15)
        pdf.set_font("Arial", size=14)
        pdf.cell(0, 10, "Learn Language Education Academy Student Contract", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Arial", size=12)
        pdf.ln(8)

        template_raw = st.session_state.get("agreement_template_raw", "")
        template, _ = wrap_template_lines(template_raw)
        filled = (
            template
            .replace("[STUDENT_NAME]",     selected_name)
            .replace("[DATE]",             str(receipt_date))
            .replace("[CLASS]",            row.get("level", ""))
            .replace("[AMOUNT]",           str(total))
            .replace("[FIRST_INSTALLMENT]", f"{paid:.2f}")
            .replace("[SECOND_INSTALLMENT]",f"{balance:.2f}")
            .replace("[SECOND_DUE_DATE]",  str(contract_end_input))
            .replace("[COURSE_LENGTH]",    f"{course_length} days")
        )

        for line in filled.split("\n"):
            safe    = sanitize_text(line)
            wrapped = break_long_words(safe, max_len=40)
            if safe_for_fpdf(wrapped):
                try:
                    pdf.multi_cell(0, 8, wrapped)
                except:
                    pass
        pdf.ln(10)
        pdf.cell(0, 8, f"Signed: {signature}", new_x="LMARGIN", new_y="NEXT")

        output_data = pdf.output(dest="S")
        if isinstance(output_data, str):
            pdf_bytes = output_data.encode("latin-1")
        else:
            pdf_bytes = bytes(output_data)

        st.download_button(
            "📄 Download PDF",
            data=pdf_bytes,
            file_name=f"{selected_name.replace(' ', '_')}_receipt_contract.pdf",
            mime="application/pdf"
        )
        st.success("✅ PDF generated and ready to download.")

# ==== TAB 4: SEND EMAIL / LETTER ====
with tabs[4]:
    from datetime import date, timedelta
    from fpdf import FPDF
    import tempfile, os


    # QR Code generation uses shared utility function make_qr_code


    # Watermark image from Google Drive (direct download)
    watermark_drive_url = "https://drive.google.com/uc?export=download&id=1dEXHtaPBmvnX941GKK-DsTmj3szz2Z5A"

    st.title("📧 Send Email / Letter (Templates, Attachments, PDF, Watermark, QR)")
    st.subheader("Select Student")
    search_val = st.text_input(
        "Search students by name, code, or email",
        value="", key="student_search"
    )
    if search_val:
        filtered_students = df_students[
            df_students["name"].str.contains(search_val, case=False, na=False)
            | df_students.get("studentcode", pd.Series(dtype=str))
                          .astype(str).str.contains(search_val, case=False, na=False)
            | df_students.get("email", pd.Series(dtype=str))
                          .astype(str).str.contains(search_val, case=False, na=False)
        ]
    else:
        filtered_students = df_students

    student_names = filtered_students["name"].dropna().unique().tolist()
    student_name = st.selectbox("Student Name", student_names, key="student_select")
    if not student_name:
        st.stop()

    student_row = filtered_students[filtered_students["name"] == student_name].iloc[0]
    student_level = student_row["level"]
    student_email = student_row.get("email", "")
    enrollment_start = pd.to_datetime(student_row.get("contractstart", date.today()), errors="coerce").date()
    enrollment_end   = pd.to_datetime(student_row.get("contractend",   date.today()), errors="coerce").date()
    payment       = float(student_row.get("paid", 0))
    balance       = float(student_row.get("balance", 0))
    payment_status = "Full Payment" if balance == 0 else "Installment Plan"
    student_code   = student_row.get("studentcode", "")
    student_link   = f"https://falowen.streamlit.app/?code={student_code}" if student_code else "https://falowen.streamlit.app/"

    # ---- 2. Message Type Selection ----
    st.subheader("Choose Message Type")

    msg_type = st.selectbox(
        "Type",
        [
            "Letter of Enrollment",
            "Course Completion Letter",
            "Payment Confirmation",
        ],
        key="msg_type_select",
    )


    # ---- 3. Branding Assets ----
    st.subheader("Upload Logo and Watermark")
    logo_file = st.file_uploader(
        "School Logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_up"
    )
    signature_file = st.file_uploader(
        "Signature Image (optional)", type=["png", "jpg", "jpeg"], key="sig_up"
    )

    # Prepare temp path for optional watermark (only used for enrollment letters)
    watermark_file_path = None
    if msg_type == "Letter of Enrollment":
        try:
            import requests
            from PIL import Image
            from io import BytesIO

            resp = requests.get(watermark_drive_url)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content))
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                img.save(tmp.name)
                watermark_file_path = tmp.name
        except Exception:
            watermark_file_path = None

    # Prepare temp path for optional signature image
    signature_file_path = None
    if signature_file:
        ext = signature_file.name.split(".")[-1]
        tmp_sig = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        tmp_sig.write(signature_file.read())
        tmp_sig.close()
        signature_file_path = tmp_sig.name


    # ---- 4. Compose/Preview Message ----
    st.subheader("Compose/Preview Message")
    payment_amount = None
    payment_date = None
    if msg_type == "Letter of Enrollment":
        body_default = (
            f"To Whom It May Concern,<br><br>"
            f"{student_name} is officially enrolled in {student_level} at Learn Language Education Academy.<br>"
            f"Enrollment valid from {enrollment_start:%m/%d/%Y} to {enrollment_end:%m/%d/%Y}.<br><br>"
            f"Business Reg No: {BUSINESS_REG}.<br><br>"
        )
        email_subject = st.text_input("Subject", value=f"{msg_type} - {student_name}", key="email_subject")
        email_body = st.text_area("Email Body (HTML supported)", value=body_default, key="email_body", height=220)
        st.markdown("**Preview Message:**")
        st.markdown(email_body, unsafe_allow_html=True)
    elif msg_type == "Payment Confirmation":
        body_default = (
            f"Hello {student_name},<br><br>"
            f"We have received your payment of GHS {payment:.2f}. "
            f"Your remaining balance is GHS {balance:.2f}.<br><br>"
            "Thank you for your prompt payment.<br><br>"
            f"{TUTOR_NAME}<br>{TUTOR_TITLE}"
        )
        email_subject = st.text_input("Subject", value=f"{msg_type} - {student_name}", key="email_subject")
        email_body = st.text_area("Email Body (HTML supported)", value=body_default, key="email_body", height=220)
        st.markdown("**Preview Message:**")
        st.markdown(email_body, unsafe_allow_html=True)
    elif msg_type == "Course Completion Letter":
        completion_date = st.date_input("Completion Date", value=date.today(), key="completion_date")
        body_default = render_completion_message(student_name, student_level)
        email_subject = st.text_input("Subject", value=f"{msg_type} - {student_name}", key="email_subject")
        email_body = st.text_area("Email Body (HTML supported)", value=body_default, key="email_body", height=220)
        st.markdown("**Preview Message:**")
        st.markdown(email_body, unsafe_allow_html=True)
    else:  # Payment Confirmation
        payment_amount = st.number_input(
            "Payment Amount", min_value=0.0, value=float(payment), key="payment_amount"
        )
        payment_date = st.date_input("Payment Date", value=date.today(), key="payment_date")
        body_default = (
            f"Dear {student_name},<br><br>"
            f"We confirm receipt of your payment of GHS {payment_amount:.2f} on {payment_date:%m/%d/%Y}. "
            "Please find your receipt and contract attached.<br><br>"
            f"Best regards,<br>{SCHOOL_NAME}"
        )
        email_subject = st.text_input("Subject", value=f"{msg_type} - {student_name}", key="email_subject")
        email_body = st.text_area(
            "Email Body (HTML supported)", value=body_default, key="email_body", height=220
        )
        st.markdown("**Preview Message:**")
        st.markdown(email_body, unsafe_allow_html=True)

    st.subheader("PDF Preview & Download")

    pdf_bytes = None
    if msg_type == "Course Completion Letter":
        class CompletionPDF(FPDF, HTMLMixin):
            pass
        pdf = CompletionPDF()
        pdf.add_page()
        certificate_html = render_completion_html(student_name, student_level, completion_date)
        pdf.write_html(certificate_html)
        output_data = pdf.output(dest="S")
        if isinstance(output_data, bytes):
            pdf_bytes = output_data
        elif isinstance(output_data, str):
            pdf_bytes = output_data.encode("latin-1", "replace")
        else:
            pdf_bytes = bytes(output_data)

    elif msg_type == "Payment Confirmation":
        student_row_dict = {
            "Name": student_row.get("name", ""),
            "StudentCode": student_row.get("studentcode", ""),
            "Phone": student_row.get("phone", ""),
            "Level": student_row.get("level", ""),
            "Paid": student_row.get("paid", 0),
            "Balance": student_row.get("balance", 0),
            "ContractStart": student_row.get("contractstart", ""),
            "ContractEnd": student_row.get("contractend", ""),
        }
        agreement_text, _ = wrap_template_lines(
            st.session_state.get("agreement_template_raw", "")
        )
        pdf_bytes = generate_receipt_and_contract_pdf(
            student_row_dict,
            agreement_text,
            payment_amount,
            payment_date,
            first_instalment=payment_amount,
        )
    else:

        class LetterPDF(FPDF):
            def header(self):
                if logo_file:
                    ext = logo_file.name.split('.')[-1]
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                    tmp.write(logo_file.read()); tmp.close()
                    self.image(tmp.name, x=10, y=8, w=28)
                self.set_font('Arial', 'B', 16)
                self.cell(0, 9, safe_pdf(SCHOOL_NAME), ln=True, align='C')
                self.set_font('Arial', '', 11)
                self.cell(0, 7, safe_pdf(f"{SCHOOL_WEBSITE} | {SCHOOL_PHONE} | {SCHOOL_ADDRESS}"), ln=True, align='C')
                self.set_font('Arial', 'I', 10)
                self.cell(0, 7, safe_pdf(f"Business Reg No: {BUSINESS_REG}"), ln=True, align='C')
                self.ln(3)
                self.set_draw_color(200,200,200); self.set_line_width(0.5)
                self.line(10, self.get_y(), 200, self.get_y()); self.ln(6)
            def watermark(self):
                if watermark_file_path:
                    self.image(watermark_file_path, x=38, y=60, w=130)
            def footer(self):
                qr = make_qr_code(SCHOOL_WEBSITE)
                self.image(qr, x=180, y=275, w=18)
                self.set_y(-18)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, safe_pdf("Generated without signature."), 0, 0, 'C')

        pdf = LetterPDF()
        pdf.add_page()
        pdf.watermark()
        pdf.set_font("Arial", size=12)
        import re
        pdf.multi_cell(0, 8, safe_pdf(re.sub(r"<br\s*/?>", "\n", email_body)))
        pdf.ln(6)

        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, safe_pdf("Yours sincerely,"), ln=True)
        pdf.cell(0, 7, safe_pdf("Felix Asadu"), ln=True)
        pdf.cell(0, 7, safe_pdf("Director"), ln=True)
        pdf.cell(0, 7, safe_pdf(SCHOOL_NAME), ln=True)

        output_data = pdf.output(dest="S")
        if isinstance(output_data, bytes):
            pdf_bytes = output_data
        elif isinstance(output_data, str):
            pdf_bytes = output_data.encode("latin-1", "replace")
        else:
            tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf.output(tmpf.name); tmpf.close()
            with open(tmpf.name, "rb") as f: pdf_bytes = f.read()
            os.remove(tmpf.name)

    if pdf_bytes:
        file_name = f"{student_name.replace(' ', '_')}_{msg_type.replace(' ','_')}.pdf"
        st.download_button(
            "📄 Download Letter/PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
        )
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        href = f'<a href="data:application/pdf;base64,{pdf_b64}" download="{file_name}">🔗 Click here to download the PDF</a>'
        st.markdown(href, unsafe_allow_html=True)
        st.caption("Download the PDF above; it is not attached to emails automatically.")
    # ---- 6. Email Option ----
    st.subheader("Send Email (with or without PDF)")
    recipient_email = st.text_input("Recipient Email", value=student_email, key="recipient_email")

    if msg_type == "Payment Confirmation":
        if st.button("Send Email with Receipt"):
            html_body = render_reminder_html(email_body)
            ok = send_email_report(pdf_bytes, recipient_email, email_subject, html_body)
            if ok:
                st.success("Email sent successfully.")
            else:
                st.error("Failed to send email.")
    elif msg_type == "Course Completion Letter":
        if st.button("Send Email without PDF"):
            html_body = render_reminder_html(email_body)
            ok = send_email_report(None, recipient_email, email_subject, html_body)
            if ok:
                st.success("Email sent successfully.")
            else:
                st.error("Failed to send email.")
        encoded_subject = urllib.parse.quote(email_subject)
        plain_body = email_body.replace("<br/>", "\n").replace("<br>", "\n")
        encoded_body = urllib.parse.quote(plain_body)
        mailto_url = f"mailto:{recipient_email}?subject={encoded_subject}&body={encoded_body}"
        st.markdown(f"[Open Email Client]({mailto_url})", unsafe_allow_html=True)
        st.caption(
            "The PDF must be downloaded separately and attached manually; it is not included in the email."
        )
    else:
        encoded_subject = urllib.parse.quote(email_subject)
        plain_body = email_body.replace("<br/>", "\n").replace("<br>", "\n")
        encoded_body = urllib.parse.quote(plain_body)
        mailto_url = f"mailto:{recipient_email}?subject={encoded_subject}&body={encoded_body}"

        st.markdown(f"[Open Email Client]({mailto_url})", unsafe_allow_html=True)
        st.caption(
            "The PDF must be downloaded separately and attached manually; it is not included in the email."
        )

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

# ====== TAB 5 CODE ======
with tabs[5]:
    import pandas as pd
    import textwrap
    from datetime import date, timedelta
    from fpdf import FPDF

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


# ==== TAB 6: LEADERSHIP BOARD ====
with tabs[6]:
    st.title("🏆 Student Leadership Board")

    # --- Config: the sheet you gave me (converted to CSV export) ---
    ASSIGNMENTS_CSV_URL = (
        "https://docs.google.com/spreadsheets/d/"
        "1BRb8p3Rq0VpFCLSwL4eS9tSgXBo9hSWzfW_J_7W36NQ/export?format=csv&gid=2121051612"
    )

    # --- Helpers (reuse your style) ---
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df

    def _match(colnames, *cands):
        s = set(colnames)
        for c in cands:
            if c in s: return c
        for c in colnames:
            if any(c.startswith(x) for x in cands): return c
        return None

    @st.cache_data(ttl=300, show_spinner="Loading assignment scores...")
    def load_assignment_scores():
        df = pd.read_csv(ASSIGNMENTS_CSV_URL, dtype=str)
        df = _normalize_columns(df)

        # Try to find expected columns with forgiving matching
        col_student  = _match(df.columns, "studentcode", "student_code", "code", "id")
        col_name     = _match(df.columns, "name", "student_name")
        col_level    = _match(df.columns, "level", "class_level")
        col_assign   = _match(df.columns, "assignment", "task", "paper", "exam")
        col_score    = _match(df.columns, "score", "points", "mark")
        col_date     = _match(df.columns, "date", "submitted", "timestamp")

        required = [col_student, col_name, col_level, col_assign, col_score]
        if any(c is None for c in required):
            missing = ["studentcode","name","level","assignment","score"]
            st.error(f"Missing one or more required columns in the sheet. Expected like: {missing}")
            return pd.DataFrame()

        # Standardize + clean
        df = df.rename(columns={
            col_student: "studentcode",
            col_name: "name",
            col_level: "level",
            col_assign: "assignment",
            col_score: "score",
            **({col_date: "date"} if col_date else {})
        })
        df["level"] = df["level"].astype(str).str.upper().str.strip()
        df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    df_scores = load_assignment_scores()
    if df_scores is None or df_scores.empty:
        st.info("No assignment score data available.")
        st.stop()

    # --- Filters (level + min assignments + optional date range + search) ---
    levels = sorted(df_scores["level"].dropna().unique().tolist())
    # default level from session if present
    default_level = (st.session_state.get("student_row", {}).get("Level", "") or "A1").upper()
    if default_level not in levels and levels:
        default_level = levels[0]

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        level_sel = st.selectbox("Level", levels, index=(levels.index(default_level) if default_level in levels else 0))
    with c2:
        min_assign = st.number_input("Min assignments to be ranked", min_value=1, value=3, step=1)
    with c3:
        search = st.text_input("Search name/code (optional)")

    # Optional date range if a date column exists
    date_from, date_to = None, None
    if "date" in df_scores.columns:
        df_min = pd.to_datetime(df_scores["date"], errors="coerce").min()
        df_max = pd.to_datetime(df_scores["date"], errors="coerce").max()
        with st.expander("Filter by date range"):
            colA, colB = st.columns(2)
            with colA:
                date_from = st.date_input("From", value=df_min.date() if pd.notna(df_min) else date.today())
            with colB:
                date_to = st.date_input("To", value=df_max.date() if pd.notna(df_max) else date.today())

    # --- Apply filters ---
    df_level = df_scores[df_scores["level"] == level_sel].copy()
    if "date" in df_level.columns and date_from and date_to:
        m = (df_level["date"].dt.date >= date_from) & (df_level["date"].dt.date <= date_to)
        df_level = df_level[m]

    if search:
        q = search.strip().lower()
        df_level = df_level[
            df_level["name"].astype(str).str.lower().str.contains(q, na=False) |
            df_level["studentcode"].astype(str).str.lower().str.contains(q, na=False)
        ]

    # --- OLD LOGIC: group, require ≥ min assignments, rank by total_score then completed ---
    if df_level.empty:
        st.info("No rows after filtering.")
        st.stop()

    grouped = (
        df_level
        .groupby(["studentcode", "name"], as_index=False)
        .agg(
            total_score=("score", "sum"),
            completed=("assignment", "nunique")
        )
    )
    ranked = grouped[grouped["completed"] >= int(min_assign)].copy()
    if ranked.empty:
        st.info("No students meet the minimum assignments requirement.")
        st.stop()

    ranked = ranked.sort_values(["total_score", "completed"], ascending=[False, False]).reset_index(drop=True)
    ranked["Rank"] = ranked.index + 1

    # Show your rank if known
    your_rank_text = ""
    _student_code = (st.session_state.get("student_code", "") or "").strip().lower()
    if _student_code:
        mine = ranked[ranked["studentcode"].astype(str).str.lower() == _student_code]
        if not mine.empty:
            r = int(mine.iloc[0]["Rank"])
            your_rank_text = f"Your rank: #{r} of {len(ranked)}"

    # --- Display ---
    m1, m2 = st.columns(2)
    m1.metric("Total ranked", f"{len(ranked)}")
    if your_rank_text:
        m2.success(your_rank_text)

    display_cols = ["Rank", "name", "studentcode", "completed", "total_score"]
    st.dataframe(ranked[display_cols], use_container_width=True)

    # --- Download ---
    st.download_button(
        "⬇️ Download leaderboard CSV",
        ranked[display_cols].to_csv(index=False),
        file_name=f"leaderboard_{level_sel}.csv"
    )




