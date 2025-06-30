# ==== 1. IMPORTS ====
import os
import base64
import re
from datetime import datetime, date, timedelta
import pandas as pd
from dateutil.relativedelta import relativedelta
import streamlit as st
from fpdf import FPDF
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import sqlite3
import urllib.parse  

# ==== 1.a. CSV & COLUMN HELPERS ====
def safe_read_csv(local_path: str, remote_url: str) -> pd.DataFrame:
    """Try local CSV first, else fall back to remote URL."""
    if os.path.exists(local_path):
        return pd.read_csv(local_path)
    return pd.read_csv(remote_url)

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, strip and de-space all column names."""
    df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
    return df

def col_lookup(df: pd.DataFrame, name: str) -> str:
    """Find the actual column name for a logical key."""
    key = name.lower().replace(" ", "").replace("_", "")
    for c in df.columns:
        if c.lower().replace(" ", "").replace("_", "") == key:
            return c
    raise KeyError(f"Column '{name}' not found in DataFrame")

def safe_pdf(text: str) -> str:
    """Ensure strings are PDF-safe (Latin-1)."""
    return text.encode("latin-1", "replace").decode("latin-1")

# ==== 2. CONFIG / CONSTANTS ====
SCHOOL_NAME         = "Learn Language Education Academy"
school_sendgrid_key = st.secrets.get("general", {}).get("SENDGRID_API_KEY")
school_sender_email = st.secrets.get("general", {}).get("SENDER_EMAIL") or "Learngermanghana@gmail.com"

# ==== 3. REFERENCE ANSWERS ====
ref_answers = {
    # Put your full dictionary of ref_answers here...
}

# ==== 4. SQLITE DB HELPERS ====
@st.cache_resource
def init_sqlite_connection():
    conn = sqlite3.connect('students_scores.db', check_same_thread=False)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            studentcode TEXT UNIQUE,
            name TEXT,
            email TEXT,
            level TEXT
        )''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY,
            studentcode TEXT,
            assignment TEXT,
            score REAL,
            comments TEXT,
            date TEXT,
            level TEXT
        )''')
    conn.commit()
    return conn

def save_score_to_sqlite(score: dict):
    conn = init_sqlite_connection()
    cur = conn.cursor()
    cols = ",".join(score.keys())
    vals = tuple(score.values())
    q = f"INSERT INTO scores ({cols}) VALUES ({','.join(['?']*len(vals))})"
    cur.execute(q, vals)
    conn.commit()

@st.cache_data(ttl=600)
def fetch_scores_from_sqlite() -> pd.DataFrame:
    conn = init_sqlite_connection()
    df = pd.read_sql("SELECT studentcode,assignment,score,comments,date,level FROM scores", conn)
    df.columns = [c.lower() for c in df.columns]
    return df

def fetch_students_from_sqlite() -> pd.DataFrame:
    conn = init_sqlite_connection()
    df = pd.read_sql("SELECT studentcode,name,email,level FROM students", conn)
    df.columns = [c.lower() for c in df.columns]
    return df

# ==== 5. GENERAL HELPERS ====
def extract_code(selection: str, label: str = "student") -> str:
    if not selection:
        st.warning(f"Please select a {label}.")
        st.stop()
    match = re.search(r"\(([^()]+)\)\s*$", selection)
    if not match:
        st.warning(f"Could not parse {label} code.")
        st.stop()
    return match.group(1)

def choose_student(df: pd.DataFrame, levels: list, key_suffix: str) -> tuple:
    lvl = st.selectbox("Level", ["All"] + levels, key=f"level_{key_suffix}")
    filtered = df if lvl == "All" else df[df['level'] == lvl]
    sel = st.selectbox("Student", filtered['name'] + " (" + filtered['studentcode'] + ")", key=f"student_{key_suffix}")
    code = extract_code(sel)
    row = filtered[filtered['studentcode'] == code].iloc[0]
    return code, row

def safe_pdf(text):
    # Remove or replace any character not in latin-1
    return "".join(c if ord(c) < 256 else "?" for c in str(text))

def generate_pdf_report(
    name: str,
    level: str,
    history: pd.DataFrame,
    assignment: str = None,
    score_name: str = "",
    tutor_name: str = "",
    school_name: str = "",
    footer_text: str = "",
) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 15)
    # Header with school, student, level, tutor, etc.
    if school_name:
        pdf.cell(0, 10, safe_pdf(school_name), ln=True, align="C")
        pdf.ln(2)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 10, safe_pdf(f"Report for: {name} (Level: {level})"), ln=True)
    if tutor_name:
        pdf.set_font("Arial", "I", 11)
        pdf.cell(0, 8, safe_pdf(f"Tutor: {tutor_name}"), ln=True)
    if score_name:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, safe_pdf(f"Score/Assignment: {score_name}"), ln=True)
    pdf.ln(4)
    
    # Reference answers section
    if assignment and assignment in ref_answers and ref_answers[assignment]:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, safe_pdf(f"Reference Answers for: {assignment}"), ln=True)
        pdf.set_font("Arial", "", 11)
        for idx, ref in enumerate(ref_answers[assignment], 1):
            pdf.multi_cell(0, 8, safe_pdf(f"{idx}. {ref}"))
        pdf.ln(2)
    
    # Score history section
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Score History:", ln=True)
    pdf.set_font("Arial", "", 11)
    report_lines = [
        f"{row.assignment}: {row.score}/100"
        + (f" - Comments: {row.comments}" if row.comments else "")
        for row in history.itertuples()
    ]
    for line in report_lines:
        pdf.multi_cell(0, 8, safe_pdf(line))
        pdf.ln(1)
    pdf.ln(6)
    
    # Footer/Remark
    if footer_text:
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 10, safe_pdf(footer_text), ln=True, align="C")
    return pdf.output(dest="S").encode("latin-1", "replace")

def send_email_report(pdf_bytes: bytes, to: str, subject: str, html_content: str):
    try:
        msg = Mail(from_email=school_sender_email, to_emails=to, subject=subject, html_content=html_content)
        attachment = Attachment(
            FileContent(base64.b64encode(pdf_bytes).decode()),
            FileName(f"{to.replace('@','_')}_report.pdf"),
            FileType('application/pdf'),
            Disposition('attachment')
        )
        msg.attachment = attachment
        SendGridAPIClient(school_sendgrid_key).send(msg)
    except Exception as e:
        st.error(f"Email send failed: {e}")

        
# ==== 8. REFERENCE ANSWERS ====
#def ref_answers
ref_answers = {
    # --- A1 Section ---
    "A1 0.1": [
        "1. C) Guten Morgen",
        "2. D) Guten Tag",
        "3. B) Guten Abend",
        "4. B) Gute Nacht",
        "5. C) Guten Morgen",
        "6. C) Wie geht es Ihnen",
        "7. B) Auf Wiedersehen",
        "8. C) Tschuss",
        "9. C) Guten Abend",
        "10. D) Guten Nacht"
    ],
    "A1 0.2": [
        "1. C) 26",
        "2. A) A, O, U, B",
        "3. A) Eszett",
        "4. A) K",
        "5. A) A-Umlaut",
        "6. A) A, O, U, B",
        "7. B 4",
        "",
        "Wasser", "Kaffee", "Blume", "Schule", "Tisch"
    ],
    "A1 1.1": [
        "1. C",
        "2. C",
        "3. A",
        "4. B"
    ],
    "A1 1.2": [
        "1. Ich heiße Anna",
        "2. Du heißt Max",
        "3. Er heißt Peter",
        "4. Wir kommen aus Italien",
        "",
        "5. Ihr kommt aus Brasilien",
        "6. Sie kommt/k kommen aus Russland",
        "7. Ich wohne in Berlin",
        "",
        "8. Du wohnst in Madrid",
        "9. Sie wohnt in Wien",
        "",
        "1. A) Anna",
        "2. C) Aus Italien",
        "3. D) In Berlin",
        "4. B) Tom",
        "5. A) In Berlin"
    ],
    "A1 2": [
        "1. A) sieben",
        "2. B) Drei",
        "3. B) Sechs",
        "4. B) Neun",
        "5. B) Sieben",
        "6. C) Fünf",
        "",
        "7. B) zweihundertzweiundzwanzig",
        "8. A) fünfhundertneun",
        "9. A) zweitausendvierzig",
        "10. A) fünftausendfünfhundertneun",
        "",
        "1. 16 – sechzehn",
        "2. 98 – achtundneunzig",
        "3. 555 – fünfhundertfünfundfünfzig",
        "",
        "4. 1020 – tausendzwanzig",
        "5. 8553 – achttausendfünfhundertdreiundfünfzig"
    ],
    "A1 4": [
        "1. C) Neun",
        "2. B) Polnisch",
        "3. D) Niederländisch",
        "4. A) Deutsch",
        "5. C) Paris",
        "6. B) Amsterdam",
        "7. C) In der Schweiz",
        "",
        "1. C) In Italien und Frankreich",
        "2. C) Rom",
        "3. B) Das Essen",
        "4. B) Paris",
        "5. A) Nach Spanien"
    ],
    "A1 5": [
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
        "",
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
        "",
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
    "A1 6": [
        "Das Wohnzimmer – the living room",
        "Die Küche – the kitchen",
        "Das Schlafzimmer – the bedroom",
        "Das Badezimmer – the bathroom",
        "Der Balkon – the balcony",
        "",
        "Der Flur – the hallway",
        "Das Bett – the bed",
        "Der Tisch – the table",
        "Der Stuhl – the chair",
        "Der Schrank – the wardrobe",
        "",
        "1. B) Vier",
        "2. A) Ein Sofa und ein Fernseher",
        "3. B) Einen Herd, einen Kühlschrank und einen Tisch mit vier Stühlen",
        "4. C) Ein großes Bett",
        "5. D) Eine Dusche, eine Badewanne und ein Waschbecken",
        "",
        "6. D) Klein und schön",
        "7. C) Blumen und einen kleinen Tisch mit zwei Stühlen",
        "",
        "1. B", "2. B", "3. B", "4. C", "5. D", "6. B", "7. C"
    ],
    "A1 7": [
        "1. B) Um sieben Uhr",
        "2. B) Um acht Uhr",
        "3. B) Um sechs Uhr",
        "4. B) Um zehn Uhr",
        "5. B) Um neun Uhr",
        "",
        "6. C) Nachmittags",
        "7. A) Um sieben Uhr",
        "8. A) Montag",
        "9. B) Am Dienstag und Donnerstag",
        "10. B) Er ruht sich aus",
        "",
        "1. B) Um neun Uhr",
        "2. B) Er geht in die Bibliothek",
        "3. B) Bis zwei Uhr nachmittags",
        "4. B) Um drei Uhr nachmittags",
        "5. A) ",
        "",
        "6. B) Um neun Uhr",
        "7. B) Er geht in die Bibliothek",
        "8. B) Bis zwei Uhr nachmittags",
        "9. B) Um drei Uhr nachmittags",
        "10. B) Um sieben Uhr"
    ],
    "A1 8": [
        "1. B) Zwei Uhr nachmittags",
        "2. B) 29 Tage",
        "3. B) April",
        "4. C) 03.02.2024",
        "5. C) Mittwoch",
        "",
        "1. Falsch", "2. Richtig", "3. Richtig", "4. Falsch", "5. Richtig",
        "",
        "1. B) Um Mitternacht", "2. B) Vier Uhr nachmittags", "3. C) 28 Tage", "4. B) Tag. Monat. Jahr", "5. D) Montag"
    ],
    "A1 9": [
        "1. B) Apfel und Karotten", "2. C) Karotten", "3. A) Weil er Vegetarier ist", "4. C) Käse", "5. B) Fleisch",
        "", "6. B) Kekse", "7. A) Käse", "8. C) Kuchen", "9. C) Schokolade", "10. B) Der Bruder des Autors",
        "", "1. A) Apfel, Bananen und Karotten", "2. A) Müsli mit Joghurt", "3. D) Karotten", "4. A) Käse", "5. C) Schokoladenkuchen"
    ],
    "A1 10": [
        "1. Falsch", "2. Wahr", "3. Falsch", "4. Wahr", "5. Wahr", "6. Falsch", "Wahr", "7. Falsch", "8. Falsch", "9. Falsch",
        "1. B) Einmal pro Woche", "2. C) Apfel und Bananen", "3. A) Ein halbes Kilo", "4. B) 10 Euro", "5. B) Einen schönen Tag"
    ],
    "A1 11": [
        "1. B) Entschuldigung, wo ist der Bahnhof?",
        "2. B) Links abbiegen",
        "3. B) Auf der rechten Seite, direkt neben dem großen Supermarkt",
        "4. B) Wie komme ich zur nächsten Apotheke?",
        "5. C) Gute Reise und einen schönen Tag noch",
        "",
        "1. C) Wie komme ich zur nächsten Apotheke?",
        "2. C) Rechts abbiegen",
        "3. B) Auf der linken Seite, direkt neben der Bäckerei",
        "4. A) Gehen Sie geradeaus bis zur Kreuzung, dann links",
        "5. C) Einen schönen Tag noch",
        "",
        "1. Fragen nach dem Weg: 'Entschuldigung, wie komme ich zum Bahnhof'",
        "2. Die Straße überqueren: 'Überqueren Sie die Straße'",
        "3. Geradeaus gehen: 'Gehen Sie geradeaus'",
        "4. Links abbiegen: 'Biegen Sie links ab'",
        "5. Rechts abbiegen: 'Biegen Sie rechts ab'",
        "6. On the left side: 'Das Kino ist auf der linken Seite'"
    ],

    "A1 12.1": [
        "1. B) Ärztin",
        "2. A) Weil sie keine Zeit hat",
        "3. B) Um 8 Uhr",
        "4. C) Viele verschiedene Fächer",
        "5. C) Einen Sprachkurs besuchen",
        "",
        "1. Der Supermarkt ist nur am Wochenende geöffnet. Antwort: B) Falsch (Der Supermarkt hat jeden Tag von 8 Uhr bis 20 Uhr geöffnet.)",
        "2. Die Theoriestunden sind jeden Tag. Antwort: B) Falsch (Die Theoriestunden finden dienstags und donnerstags statt.)",
        "3. Das Büro ist auch am Wochenende geöffnet. Antwort: B) Falsch (Das Büro ist von Montag bis Freitag geöffnet.)",
        "4. Der Englischkurs ist zweimal pro Woche. Antwort: B) Falsch (Der Englischkurs findet dreimal pro Woche statt.)",
        "5. Das Fitnessstudio ist nur vormittags geöffnet. Antwort: B) Falsch (Das Fitnessstudio ist jeden Tag von 6 Uhr bis 22 Uhr geöffnet.)",
        "",
        "1. A) Richtig",
        "2. A) Richtig",
        "3. A) Richtig",
        "4. A) Richtig",
        "5. A) Richtig"
    ],

    "A1 12.2": [
        "1. In Berlin",
        "2. Mit seiner Frau und seinen drei Kindern",
        "3. Mit seinem Auto",
        "4. Um 7:30 Uhr",
        "5. a) Barzahlung (cash)",
        "",
        "1. B) Um 9:00 Uhr",
        "2. B) Um 12:00 Uhr",
        "3. B) Um 18:00 Uhr",
        "4. B) Um 21:00 Uhr",
        "5. D) Alles Genannte",
        "",
        "1. B) Um 9 Uhr",
        "2. B) Um 12 Uhr",
        "3. A) ein Computer und ein Drucker",
        "4. C) in einer Bar",
        "5. C) bar"
    ],

    "A1 13": [
        "1. A",
        "2. B",
        "3. A",
        "4. A",
        "5. B",
        "6. B",
        "",
        "1. A",
        "2. B",
        "3. B",
        "",
        "1. B",
        "2. B",
        "3. B"
    ],

    "A1 14.1": [
        "Frage 1: Anzeige A",
        "Frage 2: Anzeige B",
        "Frage 3: Anzeige B",
        "Frage 4: Anzeige A",
        "Frage 5: Anzeige A",
        "",
        "1. C) Guten Tag, Herr Doktor",
        "2. B) Halsschmerzen und Fieber",
        "3. C) Seit gestern",
        "4. C) Kopfschmerzen und Müdigkeit",
        "5. A) Ich verschreibe Ihnen Medikamente",
        "",
        "A) Kopf – Head",
        "B) Arm – Arm",
        "C) Bein – Leg",
        "D) Auge – Eye",
        "E) Nase – Nose",
        "F) Ohr – Ear",
        "G) Mund – Mouth",
        "H) Hand – Hand",
        "I) Fuß – Foot",
        "J) Bauch – Stomach"
         "",
        "1. A) Liebe Anna, wie geht es dir?",
        "2. B) Halsschmerzen und Fieber",
        "3.C)Ich habe Kopfschmerzen",
        "4. D) Den Mund zu offnen",
        "5. C) Viel Wasser zu trinken und sich auszuruhen",
    ],
    # --- A2 Section ---
    "A2 1.1": [
        "1. C) In einer Schule",
        "2. B) Weil sie gerne mit Kindern arbeitet",
        "3. A) In einem Buro",
        "4. B) Tennis",
        "5. B) Es war sonnig und warm",
        "6. B) Italien und Spanien",
        "7. C) Weil die Baume so schon bunt sind",
        "",
        "1. B) Ins Kino gehen",
        "2. A) Weil sie spannende Geschichten liebt",
        "3. A) Tennis",
        "4. B) Es war sonnig und warm",
        "5. C) Einen Spaziergang Machen"
    ],
    "A2 1.2": [
        "1. B) Ein Jahr",
        "2. B) Er ist immer gut gelaunt und organisiert",
        "3. C) Einen Anzug und eine Brille",
        "4. B) Er geht geduldig auf ihre Anliegen ein",
        "5. B) Weil er seine Mitarbeiter regelmaBig lobt",
        "6. A) Wenn eine Aufgabe nicht rechtzeitig erledigt wird",
        "7. B) Dass er fair ist und die Leistungen der Mitarbeiter wertschatzt",
        "",
        "1. B) Weil er",
        "2. C) Sprachkurse",
        "3. A) Jeden tag"
    ],
    "A2 1.3": [
        "1. B) Anna ist 25 Jahre alt",
        "2. B) In ihrer Freizeit liest Anna Bucher und geht spazieren",
        "3. C) Anna arbeitet in einem Krankenhaus",
        "4. C) Anna hat einen Hund",
        "5. B) Max unterrichtet Mathematik",
        "6. A) Max spielt oft FuBball mit seinen Freunden",
        "7. B) Am Wochenende machen Anna und Max Ausfluge oder besuchen Museen",
        "",
        "1. B) Julia ist 26 Jahre alt",
        "2. C) Julia arbeitet als Architektin",
        "3. B) Tobias lebt in Frankfurt",
        "4. A) Tobias mochte ein eigenes Restaurant eroffnen",
        "5. B) Julia und Tobias kochen am Wochenende oft mit Sophie"
    ],
    "A2 2.4": [
        "1. B) faul sein",
        "2. d) Hockey spielen",
        "3. a) schwimmen gehen",
        "4. d) zum See fahren und dort im Zelt übernachten",
        "5. b) eine Route mit dem Zug durch das ganze Land",
        "",
        "1. B) Um 10 Uhr",
        "2. B) Eine Rucksack",
        "3. B) Ein Piknik",
        "4. C) in eienem restaurant",
        "5. A) Spielen und Spazieren gehen"
        
     ],
    "A2 2.5": [
        "1. c) Nudeln, Pizza und Salat",
        "2. c) Den grünen Salat",
        "3. c) Schokoladenkuchen und Tiramisu",
        "4. b) Die Suppe ist kalt",
        "5. c) In bar",
        "",
        "1. A)  Sie trinkt Tee",
        "2. B) Mensch aregre",
        "3. A) Sie geht jogeen ",
        "4. B) in den Bergen",
        "5. B) Klassische Musik"
    ],
    "A2 3.6": [
        "1. b) Weil ich studiere",
        "2. b) Wenn es nicht regnet, stürmt oder schneit → Formuliert im Text als:",
        "3. d) Es ist billig",
        "4. d) Haustiere",
        "5. c) Im Zoo",
        "",
        "1. A",
        "2. A",
        "3. B",
        "4. B",
        "5. B"
    ],
    "A2 3.7": [
        "1. b) In Zeitungen und im Internet",
        "2. c) Eine Person, die bei der Wohnungssuche hilft",
        "3. c) Kaltmiete und Nebenkosten",
        "4. b) Ein Betrag, den man beim Auszug zurückbekommt",
        "5. c) Ein Formular, das Schäden in der Wohnung zeigt",
        "6. c) Von 22–7 Uhr und 13–15 Uhr",
        "7. c) Zum Wertstoffcontainer bringen"
    ],
    "A2 3.8": [
        "1. B) Brot, Brotchen, Aufschnitt, Kase und Marmelade",
        "2. B) Ein Kaltes Abendessen",
        "3. A) Fischgerichte",
        "4. B) Oktoberfest",
        "5. B) Gerichte aus aller Welt",
        "6. C) Sauerkraut und Bratwurst",
        "7. A) Eine zentrale Rolle",
        "",
        "1. B) Samstag",
        "2. B) Obst und Gemuse",
        "3. B) Mozzarella",
        "4. B) Sie gehen in ein Café",
        "5. A) Gemuselasagne"
    ],
    "A2 4.9": [
        "1. B) Italien",
        "2. A) Eine Woche",
        "3. C) Kolosseum",
        "4. B) Pasta Carbonara und Tiramisu",
        "5. B) Amalfikuste",
        "6. B) Am strand verbracht und geschwommen",
        "7. C) Wegen des perfekten Urlaubs",
        "",
        "1. B) Griechenland",
        "2. A) Eine woche",
        "3. B) Der strand von Elafonissi",
        "4. B) Eine Bootstour",
        "5. A) Nach Kreta zu reisen"
    ],
    "A2 4.10": [
        "1. C) Barcelona",
        "2. B) Sagrada Familia und Park Guell",
        "3. C) Tapas",
        "4. B) Bunol",
        "5. C) Tomaten werfen",
        "6. B) Wiel er die spanische kultur erleben konnte",
        "7. D) Wieder nach Spanien reisen zu Konnen",
        "",
        "1. C) Munchen",
        "2. B) Zwei Wochen",
        "3. B) Brezeln. Bratwurst und Schweinebraten",
        "4. B) Lederhosen und Dirndl",
        "5. B) Fahrgeschafte und Spiele"
    ],
    "A2 4.11": [
        # Unterwegs: Verkehrsmittel vergleichen
        "1. b) In Italien",
        "2. b) Weil sie in der Stadt fahren wird",
        "3. a) Eine gute Versicherung",
        "4. b) Führerschein und Personalausweis",
        "5. b) Der Angestellte der Autovermietung",
        "6. a) Viele Städte zu besuchen",
        "7. b) Sehr zufrieden",
        "",
        "1. B) in die Berge",
        "2. B) Ein Mittel..",
        "3. B) 50 Euro",
        "4. C) Führerschein und Kreditkarte",
        "5. B) Das Auto auf mögliche Schäden prüfen"
    ],

    "A2 5.12": [
        # Ein Tag im Leben (Übung)
        "1. C) Eine Behörde prüft, ob das Dokument echt ist",
        "2. b) Auf der Internetseite „Anerkennung in Deutschland“",
        "3. b) Die Zeitung",
        "4. c) Berufsinformationszentrum",
        "5. b) Ein Praktikum",
        "6. c) Ein Kochrezept",
        "7. c) Menschen unter 27 Jahren",
        "",
        "1. B) um 6 Uhr beginnt die Visite",
        "2. B) um 9 Uhr",
        "3. B) führt wichtige Untersuchungen durch",
        "4. C) Vor 18 Uhr",
        "5. C) Vor 18 Uhr"
    ],

    "A2 5.13": [
        # Ein Vorstellungsgespräch (Exercise)
        "1. c) Ein Ort für kleine Kinder bis 3 Jahre",
        "2. c) Ab 3 Jahren",
        "3. d) Sie spielen, singen und basteln",
        "4. d) Sie spielen, singen und basteln",
        "5. c) Mittagessen",
        "6. a) Reiche Familien",
        "7. b) Es bekommt Hilfe beim Deutschlernen",
        "",
        "1. B) Um Interesse zu zeigen",
        "2. B) Pünktlich sein",
        "3. C) Um Interesse zu zeigen",
        "4. A) Eine Dankes-E-Mail",
        "5. B) Klar und deutlich sprechen"
    ],

    "A2 5.14": [
        # Beruf und Karriere (Exercise)
        "1. B) Die Kollegen und die Arbeit",
        "2. C) Mit „Sie“",
        "3. C) Eine Arbeitnehmervertretung",
        "4. C) Arbeitskleidung, Pausen und feste Arbeitszeiten",
        "5. C) Man kann Arbeitsbeginn und -ende flexibel wählen",
        "6. C) 38–40 Stunden",
        "7. B) Den Urlaub eintragen und genehmigen lassen",
        "8. D) Weiter das Gehalt oder den Lohn",
        "9. C) Sofort den Arbeitgeber informieren und zum Arzt gehen",
        "10. C) Auf der Baustelle oder am Flughafen",
        "11. C) Die Kündigung schriftlich und mit Frist einreichen",
        "12. C) In der Volkshochschule"
    ],

    "A2 6.15": [
        # Mein Lieblingssport
        "1. A) Yoga und Zumba",
        "2. B) Fußball, Handball und Volleyball",
        "3. C) Die Spenden an lokale Wohltätigkeitsorganisationen",
        "4. B) Im Stadtpark",
        "5. B) Fitnessprogramme",
        "6. B) Die Eröffnung eines neuen Kletterparks",
        "7. B) Eine wichtige Rolle zur Förderung der Lebensqualität",
        "",
        "1. B) Pilates- und Aerobic-Kurse",
        "2. A) Kostenlose Yoga-Kurse",
        "3. A) Wassergymnastik und Aqua-Zumba",
        "4. C) Für Anfänger und Fortgeschrittene",
        "5. B) Volleyball und Basketball"
    ],

    "A2 6.16": [
        # Wohlbefinden und Entspannung
        "1. C) Anzeige",
        "2. B) Anzeige",
        "3. E) Anzeige",
        "4. F) Anzeige",
        "5. A) Anzeige",
        "",
        "1. B) Mehr Obst und Gemüse essen",
        "2. C) 30 Minuten",
        "3. A) Der Besuch eines Fitnessstudios",
        "4. B) Um Krankheiten frühzeitig zu erkennen",
        "5. A) Yoga und Pilates"
    ],

    "A2 6.17": [
        # In die Apotheke gehen
        "1. B) Weil sie sich krank fühlte",
        "2. B) Hustensaft",
        "3. C) Hilfsbereit",
        "4. B) Broschüren mit Tipps",
        "5. C) Besser",
        "6. B) Nach einigen Stunden",
        "7. A) Sie kann sich auf den Rat der Apotheker verlassen",
        "",
        "1. B) Wegen Kopfschmerzen",
        "2. C) Ibuprofen",
        "3. B) Trockene Haut",
        "4. B) Sie war erleichtert",
        "5. B) Proben von Produkten"
    ],

    "A2 7.18": [
        # Die Bank anrufen
        "1. Sparkasse",
        "2. ING-DiBa",
        "3. Sparkasse",
        "4. Volksbank",
        "5. Commerzbank",
        "",
        "1. B) Reisepass, Meldebescheinigung, Einkommensnachweis",
        "2. B) Eine Stunde",
        "3. B) Drei",
        "4. A) Basiskonto",
        "5. D) Die Formulare vor dem Termin online ausfüllen"
    ],

    "A2 7.19": [
        # Einkaufen – Wo und wie? (Exercise)
        "1. B) Die Zunahme von Online-Shopping und Werbung",
        "2. B) Wegen der ständigen Verfügbarkeit und einfachen Bestellung",
        "3. B) Nachhaltiger Konsum",
        "4. B) Weniger Plastik verwenden und lokale Produkte kaufen",
        "5. B) Umweltverschmutzung und schlechte Arbeitsbedingungen",
        "6. A) Sich gut informieren",
        "7. B) Als komplexes Thema mit positiven und negativen Auswirkungen",
        "",
        "1. B) Bequeme Möglichkeit Produkte nach Hause zu bestellen",
        "2. B) Hohe Anzahl von Rücksendungen und Umweltbelastung",
        "3. A) Auf vertrauenswürdige Websites und Schutz persönlicher Daten",
        "4. A) Aus nachhaltigen Quellen und fairen Bedingungen",
        "5. B) Es hat den Konsum revolutioniert und neue Möglichkeiten geschaffen"
    ],

    "A2 7.20": [
        # Typische Reklamationssituationen üben
        "1. C) Man sollte seine Qualifikationen und Erfahrungen erwähnen, weil sie die Eignung für die Stelle zeigen",
        "2. A) Man sollte die Firma recherchieren, um gut informiert zu sein",
        "B) Man sollte den Arbeitsweg üben, um pünktlich zu sein",
        "3. A) Die Bezahlung, weil man finanziell abgesichert sein möchte",
        "B) Die Arbeitszeiten, weil man eine gute Work-Life-Balance haben möchte",
        "4. A) Frauen haben oft geringere Aufstiegschancen. Eine Lösung wäre eine Frauenquote.",
        "B) Frauen verdienen häufig weniger als Männer. Transparente Gehaltsstrukturen könnten helfen.",
        "C) Frauen müssen oft Beruf und Familie vereinbaren. Flexible Arbeitszeiten könnten eine Lösung sein.",
        "5. A) Es gab weniger technische Geräte im Haushalt",
        "B) Die Menschen waren weniger mobil und reisten seltener.",
        "D) Die Arbeitszeiten waren länger und härter",
        "",
        "1. B) Die Berufliche",
        "2. B) Man informiert sich",
        "3. A) Die Bezahlung",
        "4. A) Man sammelt",
        "5. A) Geringere",
        "6. A) Flexible Arbeitszeiten",
        "7. A) Es gab weniger",
        "8. B) Sie arbeiteten mehr und hatten weniger Freizeit"
    ],

    "A2 8.21": [
        # Ein Wochenende planen
        "1. C) Sollen Plätze reservieren",
        "2. C) Nur ein Restaurant haben",
        "3. C) Machte er eine lange Reise",
        "4. A) Eine Fernsehsendung",
        "5. A) Den Berufsweg eines Kochs"
    ],

    "A2 8.22": [
        # Die Woche Planung
        "1. C) Im Moment ist vieles neu für sie.",
        "2. B) Für neue Studenten eine Stadtführung gemacht.",
        "3. C) Kocht jeder einmal für die anderen.",
        "4. B) Deutsch zu sprechen.",
        "5. C) Übernachtet Sonja in Marios Zimmer."
    ],

    "A2 9.23": [
        # Wie kommst du zur Schule / zur Arbeit?
        "1. C) An die Nordsee",
        "2. B) Auf einer Insel",
        "3. A) Aus der Schweiz",
        "4. A) Mit der U-Bahn",
        "5. D) Die Berge und die Natur"
    ],

    "A2 9.24": [
        # Einen Urlaub planen
        "1. Anzeige: f",
        "2. Anzeige: c",
        "3. Anzeige: X",
        "4. Anzeige: b",
        "5. Anzeige: a"
    ],

    "A2 9.25": [
        # Tagesablauf (Exercise)
        "1. a) kurz vor 7 Uhr",
        "2. d) Müsli oder Toast mit Marmelade",
        "3. b) Hausaufgaben",
        "4. a) am Nachmittag",
        "5. b) Freunde treffen",
        "6. c) die Schweiz",
        "7. d) mit dem Zug",
        "8. a) an einem kleinen Bahnhof",
        "9. d) einen Zimmerschlüssel",
        "10. b) das Zimmer ist zu klein"
    ],

    "A2 10.26": [
        # Gefühle in verschiedenen Situationen beschreiben
        "1. b) Er beantwortet Fragen und kontrolliert die Gesundheit des Kindes.",
        "2. c) 14 Wochen",
        "3. c) 14 Monate",
        "4. a) Man muss einen festen Arbeitsvertrag haben.",
        "5. a) Impfungen und Vorsorgeuntersuchungen",
        "6. c) Ab 3 Jahren",
        "7. b) An speziellen Freizeitangeboten in der Stadt teilnehmen"
    ],

    "A2 10.27": [
        # Digitale Kommunikation
        "1. b) Sie sind oft sehr teuer oder funktionieren nicht.",
        "2. c) Ein deutsches Bankkonto und einen Ausweis.",
        "3. C) 1 bis 2 Jahre",
        "4. c) Drei Monate vor Vertragsende",
        "5. c) In Supermärkten, Tankstellen oder Kiosken",
        "6. b) Name, Adresse, Geburtsdatum und ein Ausweisdokument",
        "7. d) Mit öffentlichem WLAN"
    ],

    "A2 10.28": [
        # Über die Zukunft sprechen
        "1. c) Einen gültigen Reisepass",
        "2. b) Bei der Deutschen Botschaft im Heimatland",
        "3. c) Einen Aufenthaltstitel",
        "4. b) Ein Kurs für Deutsch und Leben in Deutschland",
        "5. c) Man muss sie übersetzen und anerkennen lassen",
        "6. c) Die Arbeitsagentur",
        "7. c) Kranken-, Renten- und Pflegeversicherung"
    ]
}  # End of A2 4.11–10.28 update


# ==== 5. TABS LAYOUT ====
tabs = st.tabs([
    "📝 Pending",                 # 0
    "👩‍🎓 All Students",            # 1
    "💵 Expenses",                # 2
    "📲 Reminders",               # 3
    "📄 Contract",                # 4
    "📧 Send Email",              # 5 
    "📆 Schedule",                # 6
    "📝 Marking"                  # 7
])

# ==== 6. AGREEMENT TEMPLATE (Persisted in Session State) ====
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

# --- End of Stage 2 ---

with tabs[0]:
    st.title("🕒 Pending Students")

    # --- 1. LOAD DATA ---
    pending_csv_url = (
        "https://docs.google.com/spreadsheets/d/"
        "1HwB2yCW782pSn6UPRU2J2jUGUhqnGyxu0tOXi0F0Azo/export?format=csv"
    )
    @st.cache_data(ttl=0)
    def load_pending():
        df = pd.read_csv(pending_csv_url, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        return df
    df = load_pending()
    st.caption("Preview of pending students loaded from Google Sheet:")
    st.dataframe(df, use_container_width=True)

    # --- 2. COLUMN LOOKUP ---
    def col_lookup(df, name):
        key = name.lower().replace(" ", "").replace("_", "")
        for c in df.columns:
            if c.lower().replace(" ", "").replace("_", "") == key:
                return c
        raise KeyError(f"Column '{name}' not found in DataFrame")

    # Try to auto-detect column names
    try:
        name_col = col_lookup(df, "name")
    except:
        name_col = df.columns[0]
    try:
        code_col = col_lookup(df, "studentcode") if "studentcode" in df.columns else col_lookup(df, "student_code")
    except:
        code_col = df.columns[1]
    try:
        phone_col = col_lookup(df, "phone")
    except:
        phone_col = df.columns[-1]

    # --- 3. SEARCH ---
    search = st.text_input("Search by name, code, or phone", key="pending_search")
    filt = df.copy()
    if search:
        mask1 = filt[name_col].str.contains(search, case=False, na=False)
        mask2 = filt[code_col].str.contains(search, case=False, na=False)
        mask3 = filt[phone_col].str.contains(search, case=False, na=False)
        filt = filt[mask1 | mask2 | mask3]

    st.dataframe(filt, use_container_width=True)

    # --- 4. DOWNLOAD ---
    st.download_button(
        "⬇️ Download Pending Students as CSV",
        filt.to_csv(index=False),
        file_name="pending_students.csv"
    )

# ==== 9. ALL STUDENTS TAB ====
with tabs[1]:
    st.title("👩‍🎓 All Students")

    # -- Google Sheets CSV Export Link --
    students_csv_url = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U"
        "/export?format=csv"
    )

    # --- Load Students Helper ---
    @st.cache_data(show_spinner=False)
    def load_students():
        df = pd.read_csv(students_csv_url)
        # Normalize columns (same helper as before)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df

    df_students = load_students()

    # --- Optional: Search/Filter ---
    search = st.text_input("🔍 Search students by name, code, or email...")
    if search:
        search = search.lower().strip()
        df_students = df_students[
            df_students.apply(lambda row: search in str(row).lower(), axis=1)
        ]

    # --- Show Student Table ---
    st.dataframe(df_students, use_container_width=True)

# ==== 10. TAB 2: EXPENSES AND FINANCIAL SUMMARY ====
with tabs[2]:
    st.title("💵 Expenses and Financial Summary")

    # 1. Load expenses from Google Sheets CSV (edit link as needed)
    sheet_id   = "1I5mGFcWbWdK6YQrJtabTg_g-XBEVaIRK1aMFm72vDEM"
    sheet_csv  = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        df_expenses = pd.read_csv(sheet_csv)
        df_expenses = normalize_columns(df_expenses)
        st.success("✅ Loaded expenses from Google Sheets.")
    except Exception as e:
        st.error(f"❌ Could not load expenses sheet: {e}")
        df_expenses = pd.DataFrame(columns=["type", "item", "amount", "date"])

    # 2. Add new expense via form
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
            # Optionally, save to a local backup file:
            df_expenses.to_csv("expenses_all.csv", index=False)
            st.experimental_rerun()

    # 3. Display all expenses with pagination
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

    # 4. Expense summary
    total_expenses = pd.to_numeric(df_expenses["amount"], errors="coerce").fillna(0).sum() if not df_expenses.empty else 0.0
    st.info(f"💸 **Total Expenses:** GHS {total_expenses:,.2f}")

    # 5. Export to CSV
    csv_data = df_expenses.to_csv(index=False)
    st.download_button(
        "📁 Download Expenses CSV",
        data=csv_data,
        file_name="expenses_data.csv",
        mime="text/csv"
    )

with tabs[3]:
    st.title("📲 WhatsApp Reminders for Debtors")

    # --- 1. LOAD STUDENT DATA FROM GOOGLE SHEET ---
    students_csv_url = "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    @st.cache_data(ttl=0)
    def load_students():
        df = pd.read_csv(students_csv_url, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        return df
    df = load_students()
    st.caption("Preview of student data loaded from Google Sheet:")
    st.dataframe(df)

    def col_lookup(df, name):
        key = name.lower().replace(" ", "").replace("_", "")
        for c in df.columns:
            if c.lower().replace(" ", "").replace("_", "") == key:
                return c
        raise KeyError(f"Column '{name}' not found in DataFrame")

    # --- 2. FINANCIAL COLUMN LOOKUPS ---
    name_col  = col_lookup(df, "name")
    code_col  = col_lookup(df, "studentcode")
    phone_col = col_lookup(df, "phone")
    bal_col   = col_lookup(df, "balance")
    paid_col  = col_lookup(df, "paid")
    lvl_col   = col_lookup(df, "level")
    cs_col    = col_lookup(df, "contractstart")

    # --- 3. CLEAN DATA TYPES ---
    df[bal_col] = pd.to_numeric(df[bal_col], errors="coerce").fillna(0)
    df[paid_col] = pd.to_numeric(df[paid_col], errors="coerce").fillna(0)
    df[cs_col] = pd.to_datetime(df[cs_col], errors="coerce")
    df[phone_col] = df[phone_col].astype(str).str.replace(r"[^\d+]", "", regex=True)

    # --- 4. CALCULATE DUE DATE & DAYS LEFT ---
    df["due_date"] = df[cs_col] + pd.Timedelta(days=30)
    df["due_date_str"] = df["due_date"].dt.strftime("%d %b %Y")
    df["days_left"] = (df["due_date"] - pd.Timestamp.today()).dt.days

    # --- 5. FINANCIAL SUMMARY ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Students", len(df))
    m2.metric("Total Collected (GHS)", f"{df[paid_col].sum():,.2f}")
    m3.metric("Total Outstanding (GHS)", f"{df[bal_col].sum():,.2f}")

    st.markdown("---")

    # --- 6. FILTER/SEARCH ---
    show_all = st.toggle("Show all students (not just debtors)", value=False)
    search = st.text_input("Search by name, code, or phone", key="wa_search")
    selected_level = st.selectbox("Filter by Level", ["All"] + sorted(df[lvl_col].dropna().unique()), key="wa_level")

    filt = df.copy()
    if not show_all:
        filt = filt[filt[bal_col] > 0]
    if search:
        mask1 = filt[name_col].str.contains(search, case=False, na=False)
        mask2 = filt[code_col].str.contains(search, case=False, na=False)
        mask3 = filt[phone_col].str.contains(search, case=False, na=False)
        filt = filt[mask1 | mask2 | mask3]
    if selected_level != "All":
        filt = filt[filt[lvl_col] == selected_level]

    st.markdown("---")

    # --- 7. TABLE PREVIEW ---
    tbl = filt[[name_col, code_col, phone_col, lvl_col, bal_col, "due_date_str", "days_left"]].rename(columns={
        name_col: "Name", code_col: "Student Code", phone_col: "Phone",
        lvl_col: "Level", bal_col: "Balance (GHS)", "due_date_str": "Due Date", "days_left": "Days Left"
    })
    st.dataframe(tbl, use_container_width=True)

    # --- 8. PHONE FORMAT FUNCTION ---
    def clean_phone(phone):
        phone = str(phone).replace(" ", "").replace("-", "")
        if phone.startswith("+233"):
            return phone[1:]
        if phone.startswith("233"):
            return phone
        if phone.startswith("0") and len(phone) == 10:
            return "233" + phone[1:]
        # fallback: return as is
        return phone

    # --- 9. WHATSAPP LINK AND MESSAGE ---
    wa_template = st.text_area(
        "Custom WhatsApp Message Template",
        value="Hi {name}! Friendly reminder: your payment for the {level} class is due by {due}. {msg} Thank you!",
        help="You can use {name}, {level}, {due}, {bal}, {days}, {msg}"
    )

    links = []
    for _, row in filt.iterrows():
        phone = clean_phone(row[phone_col])
        # Balance & msg
        bal = f"GHS {row[bal_col]:,.2f}"
        due = row["due_date_str"]
        days = int(row["days_left"])
        if days >= 0:
            msg = f"You have {days} {'day' if days == 1 else 'days'} left to settle the {bal} balance."
        else:
            msg = f"Your payment is overdue by {abs(days)} {'day' if abs(days)==1 else 'days'}. Please settle as soon as possible."
        # Format the template
        text = wa_template.format(
            name=row[name_col],
            level=row[lvl_col],
            due=due,
            bal=bal,
            days=days,
            msg=msg
        )
        link = f"https://wa.me/{phone}?text={urllib.parse.quote(text)}" if phone else ""
        links.append({
            "Name": row[name_col],
            "Student Code": row[code_col],
            "Level": row[lvl_col],
            "Balance (GHS)": bal,
            "Due Date": due,
            "Days Left": days,
            "Phone": phone,
            "WhatsApp Link": link
        })

    df_links = pd.DataFrame(links)
    st.markdown("---")
    st.dataframe(df_links[["Name", "Level", "Balance (GHS)", "Due Date", "Days Left", "WhatsApp Link"]], use_container_width=True)

    # --- 10. LIST LINKS ---
    st.markdown("### Send WhatsApp Reminders")
    for i, row in df_links.iterrows():
        if row["WhatsApp Link"]:
            st.markdown(f"- **{row['Name']}** ([Send WhatsApp]({row['WhatsApp Link']}))")

    st.download_button(
        "📁 Download Reminder Links CSV",
        df_links[["Name", "Student Code", "Phone", "Level", "Balance (GHS)", "Due Date", "Days Left", "WhatsApp Link"]].to_csv(index=False),
        file_name="debtor_whatsapp_links.csv"
    )


# ==== 12. TAB 5: GENERATE CONTRACT & RECEIPT PDF FOR ANY STUDENT ====
with tabs[4]:
    st.title("📄 Generate Contract & Receipt PDF for Any Student")

    # 1. Google Sheet as main source, fallback to local file if offline
    student_file = "students.csv"
    google_csv   = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    )
    df = safe_read_csv(student_file, google_csv)
    df = normalize_columns(df)

    if df.empty:
        st.warning("No student data available.")
    else:
        def getcol(col): return col_lookup(df, col)

        name_col    = getcol("name")
        start_col   = getcol("contractstart")
        end_col     = getcol("contractend")
        paid_col    = getcol("paid")
        bal_col     = getcol("balance")
        code_col    = getcol("studentcode")
        phone_col   = getcol("phone")
        level_col   = getcol("level")

        # 3. Select student (dropdown)
        student_names = df[name_col].tolist()
        selected_name = st.selectbox("Select Student", student_names)
        row = df[df[name_col] == selected_name].iloc[0]

        # 4. Editable fields before PDF generation
        default_paid    = float(row.get(paid_col, 0))
        default_balance = float(row.get(bal_col, 0))
        default_start   = pd.to_datetime(row.get(start_col, ""), errors="coerce").date() \
            if not pd.isnull(pd.to_datetime(row.get(start_col, ""), errors="coerce")) else date.today()
        default_end     = pd.to_datetime(row.get(end_col,   ""), errors="coerce").date() \
            if not pd.isnull(pd.to_datetime(row.get(end_col,   ""), errors="coerce")) else default_start + timedelta(days=30)

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

        # 5. Generate PDF
        if st.button("Generate & Download PDF"):
            # Use current inputs
            paid    = paid_input
            balance = balance_input
            total   = total_input
            contract_start = contract_start_input
            contract_end   = contract_end_input

            pdf = FPDF()
            pdf.add_page()

            # Add logo if uploaded
            if logo_file:
                import tempfile
                ext = logo_file.name.split('.')[-1]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                tmp.write(logo_file.getbuffer())
                tmp.close()
                pdf.image(tmp.name, x=10, y=8, w=33)
                pdf.ln(25)

            # Payment status banner
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
                safe = safe_pdf(line)
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

with tabs[5]:
    st.title("📧 Send Email (Quick)")

    # --- 1. Load student list from Google Sheets ---
    students_csv_url = (
        "https://docs.google.com/spreadsheets/d/"
        "12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/"
        "export?format=csv"
    )
    try:
        df_students = pd.read_csv(students_csv_url)
    except Exception as e:
        st.error(f"❌ Could not load student list: {e}")
        df_students = pd.DataFrame(columns=["name", "email", "level", "contractstart", "student_code"])
    df_students = normalize_columns(df_students)
    name_col  = col_lookup(df_students, "name")
    email_col = col_lookup(df_students, "email")
    level_col = col_lookup(df_students, "level")
    code_col  = col_lookup(df_students, "student_code") if "student_code" in df_students.columns else "studentcode"
    start_col = col_lookup(df_students, "contractstart") if "contractstart" in df_students.columns else ""

    # --- 1b. Load score sheet (for assignment results) ---
    scores_csv_url = (
        "https://docs.google.com/spreadsheets/d/1BRb8p3Rq0VpFCLSwL4eS9tSgXBo9hSWzfW_J_7W36NQ/export?format=csv"
    )
    try:
        df_scores = pd.read_csv(scores_csv_url)
        df_scores = normalize_columns(df_scores)
    except Exception as e:
        df_scores = pd.DataFrame(columns=["studentcode","assignment","score","comments","date","level"])
        st.warning("⚠️ Could not load assignment scores. Assignment Results will be empty.")

    # --- 2. Template selector ---
    template_opts = ["Custom", "Welcome", "Payment Reminder", "Assignment Results"]
    selected_template = st.selectbox(
        "Template", template_opts, key="tab6_template"
    )

    # --- 3. Defaults per template ---
    subj_def = ""
    body_def = ""
    if selected_template == "Welcome":
        subj_def = "Welcome to Learn Language Education Academy!"
        body_def = (
            "Hello {name},<br><br>"
            "Welcome to Learn Language Education Academy! We have helped many students succeed, and we’re excited to support you as well.<br><br>"
            "<b>Your contract starts on the date indicated in the attached course schedule.</b> "
            "Please refer to the schedule for both your class start and end dates.<br><br>"
            "You can join your <b>{level}</b> class either in person or online via Zoom (link will be shared before class).<br><br>"
            "Attached is your course outline, so you can preview how the class will progress.<br><br>"
            "You will use our Falowen App (<a href='https://falowen.streamlit.app/'>falowen.streamlit.app</a>) "
            "to track your progress, see assignments, and practice your skills (log in with your student code or email).<br><br>"
            "Assignments, course books, and recorded lectures are all available in Google Classroom.<br><br>"
            "We wish you a great start and look forward to seeing your progress!<br><br>"
            "Best regards,<br>"
            "Felix Asadu<br>"
            "Learn Language Education Academy"
        )
    elif selected_template == "Payment Reminder":
        subj_def = "Friendly Payment Reminder"
        body_def = (
            "Hi {name},<br><br>"
            "Just a reminder: your balance for {level} is due soon.<br><br>"
            "Thank you!"
        )
    elif selected_template == "Assignment Results":
        subj_def = "Your Assignment Results"
        body_def = (
            "Hello {name},<br><br>"
            "Below are your latest assignment scores:<br><br>"
            "{results_table}<br><br>"
            "Best,<br>Learn Language Education Academy"
        )
    else:
        subj_def = ""
        body_def = ""

    # --- 4. Student search/filter at the bottom ---
    st.subheader("🔎 Search for Student")
    search_val = st.text_input("Search by name, email, or code", value="", key="tab6_search")
    if search_val:
        df_students_filtered = df_students[
            df_students[name_col].str.contains(search_val, case=False, na=False) |
            df_students[email_col].str.contains(search_val, case=False, na=False) |
            df_students[code_col].astype(str).str.contains(search_val, case=False, na=False)
        ]
    else:
        df_students_filtered = df_students

    student_options = [
        f"{row[name_col]} <{row[email_col]}>"
        for _, row in df_students_filtered.iterrows()
        if pd.notna(row[email_col]) and row[email_col] != ""
    ]
    selected_recipients = st.multiselect(
        "Recipients", student_options, key="tab6_recipients"
    )

    # --- 5. Compose ---
    st.subheader("Email Subject & Body")
    email_subject = st.text_input(
        "Email Subject",
        value=subj_def,
        key="tab6_email_subject"
    )
    email_body = st.text_area(
        "Email Body (HTML)",
        value=body_def,
        key="tab6_email_body",
        height=200
    )

    # --- 6. Preview before sending ---
    if selected_recipients:
        preview_nm = selected_recipients[0].split("<")[0].strip()
        preview_lvl = df_students.loc[df_students[name_col]==preview_nm, level_col].iloc[0] if preview_nm in df_students[name_col].values else ""
        preview_code = df_students.loc[df_students[name_col]==preview_nm, code_col].iloc[0] if preview_nm in df_students[name_col].values else ""
        results_table = ""
        if selected_template == "Assignment Results" and preview_code in df_scores['studentcode'].values:
            results = df_scores[df_scores['studentcode']==preview_code][["assignment","score"]].dropna()
            if not results.empty:
                results_table = "<table border=1><tr><th>Assignment</th><th>Score</th></tr>"
                for _, row in results.iterrows():
                    results_table += f"<tr><td>{row['assignment']}</td><td>{row['score']}</td></tr>"
                results_table += "</table>"
        else:
            results_table = ""
        st.markdown("##### Preview (for first recipient):")
        st.markdown(email_body.format(
            name=preview_nm,
            level=preview_lvl,
            results_table=results_table,
            start_date=""
        ), unsafe_allow_html=True)

    # --- 7. Attachment ---
    st.subheader("Attachment (optional)")
    attachment_file = st.file_uploader(
        "Upload file", type=None, key="tab6_attachment"
    )

    # --- 8. SendGrid config
    sendgrid_key = st.secrets["general"]["SENDGRID_API_KEY"]
    sender_email = st.secrets["general"]["SENDER_EMAIL"]

    # --- 9. Send button
    if st.button("Send Emails", key="tab6_send"):
        if not selected_recipients:
            st.warning("Select at least one recipient.")
        elif not email_subject or not email_body:
            st.warning("Subject and body cannot be empty.")
        else:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
            import base64

            successes, failures = [], []
            for pick in selected_recipients:
                nm, addr = pick.split("<")
                nm = nm.strip()
                addr = addr.strip(">").strip()
                lvl = df_students.loc[df_students[name_col]==nm, level_col].iloc[0] if nm in df_students[name_col].values else ""
                code = df_students.loc[df_students[name_col]==nm, code_col].iloc[0] if nm in df_students[name_col].values else ""
                results_table = ""
                if selected_template == "Assignment Results" and code in df_scores['studentcode'].values:
                    results = df_scores[df_scores['studentcode']==code][["assignment","score"]].dropna()
                    if not results.empty:
                        results_table = "<table border=1><tr><th>Assignment</th><th>Score</th></tr>"
                        for _, row in results.iterrows():
                            results_table += f"<tr><td>{row['assignment']}</td><td>{row['score']}</td></tr>"
                        results_table += "</table>"
                else:
                    results_table = ""

                # Always provide start_date as an empty string for format()
                try:
                    msg = Mail(
                        from_email=sender_email,
                        to_emails=addr,
                        subject=email_subject,
                        html_content=email_body.format(
                            name=nm,
                            level=lvl,
                            results_table=results_table,
                            start_date=""
                        )
                    )
                    # attach if present
                    if attachment_file:
                        data = attachment_file.read()
                        enc  = base64.b64encode(data).decode()
                        ftype = __import__("mimetypes").guess_type(attachment_file.name)[0] or "application/octet-stream"
                        attach = Attachment(
                            FileContent(enc),
                            FileName(attachment_file.name),
                            FileType(ftype),
                            Disposition("attachment")
                        )
                        msg.attachment = attach

                    sg = SendGridAPIClient(sendgrid_key)
                    sg.send(msg)
                    successes.append(addr)
                except Exception as e:
                    failures.append(f"{addr}: {e}")

            if successes:
                st.success(f"Sent to: {', '.join(successes)}")
            if failures:
                st.error(f"Failures: {', '.join(failures)}")

# ==== 14. TAB 6: COURSE SCHEDULE GENERATOR ====
with tabs[6]:
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

with tabs[7]:
    st.title("📝 Assignment Marking & Scores")

    # --- URLs ---
    students_csv_url = (
        "https://docs.google.com/spreadsheets/d/12NXf5FeVHr7JJT47mRHh7Jp-TC1yhPS7ZG6nzZVTt1U/export?format=csv"
    )
    scores_csv_url = (
        "https://docs.google.com/spreadsheets/d/1BRb8p3Rq0VpFCLSwL4eS9tSgXBo9hSWzfW_J_7W36NQ/export?format=csv"
    )

    # --- Load Students ---
    @st.cache_data(show_spinner=False)
    def load_students():
        df = pd.read_csv(students_csv_url)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        if "student_code" in df.columns:
            df = df.rename(columns={"student_code": "studentcode"})
        return df
    df_students = load_students()

    # --- Load Scores (Sheet & SQLite) ---
    @st.cache_data(ttl=0)
    def load_sheet_scores():
        df = pd.read_csv(scores_csv_url)
        df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
        if "student_code" in df.columns:
            df = df.rename(columns={"student_code": "studentcode"})
        if "level" not in df.columns:
            df["level"] = None
        return df

    @st.cache_data(ttl=0)
    def fetch_sqlite_scores():
        conn = init_sqlite_connection()
        df = pd.read_sql("SELECT studentcode,assignment,score,comments,date,level FROM scores", conn)
        df.columns = [c.lower() for c in df.columns]
        return df

    df_sheet_scores = load_sheet_scores()
    df_sqlite_scores = fetch_sqlite_scores()

    # --- Harmonize (guarantee "studentcode", "level" in both) ---
    for df in [df_sheet_scores, df_sqlite_scores]:
        if "studentcode" not in df.columns:
            if "student_code" in df.columns:
                df["studentcode"] = df["student_code"]
        if "level" not in df.columns:
            df["level"] = None

    # --- Combine and Deduplicate (most recent by student+assignment) ---
    df_scores = pd.concat([df_sheet_scores, df_sqlite_scores], ignore_index=True)
    df_scores["date"] = pd.to_datetime(df_scores["date"], errors="coerce")
    df_scores = df_scores.sort_values("date").drop_duplicates(["studentcode", "assignment"], keep="last")
    df_scores = df_scores.reset_index(drop=True)

    # --- Merge in NAME and LEVEL for all rows, fallback to sheet's name if missing ---
    df_scores_with_name = df_scores.merge(
        df_students[["studentcode", "name", "level"]],
        on="studentcode", how="left", suffixes=("", "_student")
    )
    # If name missing, fill from name_student
    if "name_student" in df_scores_with_name.columns:
        df_scores_with_name["name"] = df_scores_with_name["name"].combine_first(df_scores_with_name["name_student"])
        df_scores_with_name = df_scores_with_name.drop(columns=["name_student"])
    # For robustness, fill name from original sheet if also available there (rare edge case)
    if "name" in df_sheet_scores.columns:
        df_scores_with_name = df_scores_with_name.merge(
            df_sheet_scores[["studentcode", "assignment", "name"]],
            on=["studentcode", "assignment"], how="left", suffixes=("", "_sheet")
        )
        df_scores_with_name["name"] = df_scores_with_name["name"].combine_first(df_scores_with_name["name_sheet"])
        if "name_sheet" in df_scores_with_name.columns:
            df_scores_with_name = df_scores_with_name.drop(columns=["name_sheet"])

    # --- Clean column order for display/download ---
    wanted_cols = ['studentcode', 'name', 'assignment', 'score', 'comments', 'date', 'level']
    for c in wanted_cols:
        if c not in df_scores_with_name.columns:
            df_scores_with_name[c] = ""
    df_scores_with_name = df_scores_with_name[wanted_cols]

    st.markdown("#### 📚 All Score History (Sheet + App)")
    st.dataframe(df_scores_with_name, use_container_width=True)

    st.download_button(
        "⬇️ Download All Scores as CSV (with Name & Level)",
        data=df_scores_with_name.to_csv(index=False),
        file_name="all_scores_with_name_level.csv"
    )



    # --- Student search and select ---
    st.subheader("🔎 Search Student")
    name_col, code_col = col_lookup(df_students, "name"), col_lookup(df_students, "studentcode")
    search_student = st.text_input("Type student name or code...")
    students_filtered = df_students[
        df_students[name_col].str.contains(search_student, case=False, na=False) |
        df_students[code_col].astype(str).str.contains(search_student, case=False, na=False)
    ] if search_student else df_students

    student_list = students_filtered[name_col] + " (" + students_filtered[code_col].astype(str) + ")"
    chosen = st.selectbox("Select Student", student_list, key="single_student")

    if not chosen or "(" not in chosen:
        st.warning("No student selected or wrong student list format.")
        st.stop()
    student_code = chosen.split("(")[-1].replace(")", "").strip()
    student_row = students_filtered[students_filtered[code_col] == student_code].iloc[0]
    st.markdown(f"**Selected:** {student_row[name_col]} ({student_code})")
    student_level = student_row['level'] if 'level' in student_row else ""

    # --- Assignment search and select ---
    st.subheader("🔎 Search Assignment")
    search_assign = st.text_input("Type assignment title...", key="search_assign")
    assignments = sorted(set(df_scores['assignment']).union(ref_answers.keys()))
    filtered = [a for a in assignments if search_assign.lower() in a.lower()]
    if not filtered:
        st.info("No assignments match your search.")
        st.stop()
    assignment = st.selectbox("Select Assignment", filtered, key="assign_select")

    # --- Reference Answers (if available) ---
    st.markdown("**Reference Answers:**")
    for ans in ref_answers.get(assignment, []):
        st.write(f"- {ans}")

    # --- Score entry form (pre-fills previous score/comment if exists) ---
    prev = df_scores[
        (df_scores['studentcode'] == student_code) &
        (df_scores['assignment'] == assignment)
    ]
    default_score   = int(prev['score'].iloc[0]) if not prev.empty else 0
    default_comment = prev['comments'].iloc[0] if not prev.empty else ""

    with st.form(f"form_single_{student_code}_{assignment}"):
        score   = st.number_input("Score (0–100)", 0, 100, default_score, key="score_single")
        comment = st.text_area("Comments", value=default_comment, key="comment_single")
        submitted = st.form_submit_button("Save Score")

    if submitted:
        save_score_to_sqlite({
            'studentcode': student_code,
            'assignment' : assignment,
            'score'      : float(score),
            'comments'   : comment,
            'date'       : datetime.now().strftime("%Y-%m-%d"),
            'level'      : student_row.get('level', '')
        })
        st.success("Score saved! Refreshing...")
        st.rerun()

    # --- Show Score History for this student ---
    student_history = df_scores[df_scores['studentcode'] == student_code].sort_values('date', ascending=False)
    st.markdown(f"### 📋 Score History for {student_row[name_col]} (Level: {student_level})")
    st.dataframe(student_history[['assignment','score','comments','date','level']], use_container_width=True)

    # --- PDF GENERATION & DOWNLOAD BUTTON ---
    pdf_bytes = generate_pdf_report(
        name=student_row[name_col],
        level=student_row.get('level', ''),
        history=student_history,
        assignment=assignment,
        score_name=assignment,
        tutor_name="Mr. Felix Asadu",
        school_name="Learn Language Education Academy",
        footer_text="Thank you for your hard work! Contact your tutor if you have any questions."
    )
    pdf_filename = f"{student_row[name_col].replace(' ', '_')}_{assignment.replace(' ', '_')}_report.pdf"

    st.download_button(
        "Download Report PDF",
        data=pdf_bytes,
        file_name=pdf_filename,
        mime="application/pdf"
    )
    
    # --- EMAIL REPORT BUTTON ---
    # Get student's email (robustly, fallback to empty if missing)
    student_email_col = None
    for c in student_row.index:
        if "email" in c:
            student_email_col = c
            break
    student_email = student_row[student_email_col] if student_email_col else ""

    if student_email:
        st.markdown("---")
        st.subheader("📧 Email this Report")

        default_subject = f"{assignment} – Your Progress Report"

        # --- Format Reference Answers as HTML (if any) ---
        ref_ans_list = ref_answers.get(assignment, [])
        if ref_ans_list:
            ref_ans_html = "<b>Reference Answers:</b><br><ol>"
            for a in ref_ans_list:
                if not a.strip():
                    ref_ans_html += "<br>"
                else:
                    ref_ans_html += f"<li>{a}</li>"
            ref_ans_html += "</ol><br>"
        else:
            ref_ans_html = ""

        default_body = f"""Hello {student_row[name_col]},<br><br>
Please find attached your score report for <b>{assignment}</b>.<br><br>
{ref_ans_html}
If you have any questions, reply directly to this email.<br><br>
Best regards,<br>
Mr. Felix Asadu<br>
Learn Language Education Academy
"""
        email_subject = st.text_input("Email Subject", value=default_subject, key="pdf_email_subject")
        email_body = st.text_area("Email Body (HTML)", value=default_body, key="pdf_email_body", height=300)

        if st.button("📧 Send Email with Report PDF", key="send_pdf_email"):
            try:
                send_email_report(
                    pdf_bytes,
                    to=student_email,
                    subject=email_subject,
                    html_content=email_body
                )
                st.success(f"Email sent to {student_email}!")
            except Exception as e:
                st.error(f"Failed to send email: {e}")
    else:
        st.info("No student email found to send report.")

    # --- WHATSAPP SHARE BUTTON ---
    def clean_ghana_phone(phone):
        phone = str(phone).strip().replace(" ", "").replace("-", "")
        phone = phone.replace("+", "")
        if phone.startswith("0") and len(phone) == 10:
            phone = "233" + phone[1:]
        elif phone.startswith("233") and len(phone) == 12:
            pass
        elif len(phone) == 9:
            phone = "233" + phone
        elif not phone.startswith("233") and len(phone) == 10:
            phone = "233" + phone[1:]
        return phone if phone.startswith("233") and len(phone) == 12 else ""

    student_phone_col = None
    for c in student_row.index:
        if "phone" in c:
            student_phone_col = c
            break
    student_phone_raw = student_row[student_phone_col] if student_phone_col else ""
    wa_phone = clean_ghana_phone(student_phone_raw)

    # --- Format reference answers for WhatsApp ---
    ref_ans_list = ref_answers.get(assignment, [])
    if ref_ans_list:
        wa_ref_txt = "\nReference Answers:\n"
        i = 1
        for a in ref_ans_list:
            if not a.strip():
                wa_ref_txt += "\n"
            else:
                wa_ref_txt += f"{i}. {a}\n"
                i += 1
    else:
        wa_ref_txt = ""

    if wa_phone:
        st.markdown("---")
        st.subheader("💬 WhatsApp this Report")

        default_wa_msg = (
            f"Hi {student_row[name_col]}, your report for *{assignment}* is ready!\n"
            f"Score: {default_score}/100\n"
            f"{comment if comment else ''}\n"
            f"{wa_ref_txt}\n"
            "Contact your tutor if you have questions.\n"
            "Learn Language Education Academy."
        )
        wa_msg = st.text_area("WhatsApp Message", value=default_wa_msg, key="wa_msg_box", height=180)
        wa_link = f"https://wa.me/{wa_phone}?text={urllib.parse.quote(wa_msg)}"
        st.markdown(f"[📲 Share on WhatsApp]({wa_link})", unsafe_allow_html=True)
    else:
        st.info("No valid phone number to send WhatsApp message.")

