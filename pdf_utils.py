# utils/pdf_utils.py

from fpdf import FPDF
from fpdf.enums import WrapMode
from fpdf.errors import FPDFException
from datetime import date, datetime, timedelta
from utils import safe_pdf

def generate_receipt_and_contract_pdf(
    student_row,
    agreement_text,
    payment_amount,
    payment_date=None,
    first_instalment=1500,
    course_length=12,
    school_name="Learn Language Education Academy"
):
    if payment_date is None:
        payment_date = date.today()
    elif isinstance(payment_date, str):
        from pandas import to_datetime
        payment_date = to_datetime(payment_date, errors="coerce").date()

    paid = float(student_row.get("Paid", 0))
    balance = float(student_row.get("Balance", 0))
    total_fee = paid + balance

    try:
        second_due_date = payment_date + timedelta(days=30)
    except Exception:
        second_due_date = payment_date

    payment_status = "FULLY PAID" if balance == 0 else "INSTALLMENT PLAN"

    filled = agreement_text.replace("[STUDENT_NAME]", str(student_row.get("Name", ""))) \
        .replace("[DATE]", str(payment_date)) \
        .replace("[CLASS]", str(student_row.get("Level", ""))) \
        .replace("[AMOUNT]", str(payment_amount)) \
        .replace("[FIRST_INSTALLMENT]", str(first_instalment)) \
        .replace("[SECOND_INSTALLMENT]", str(balance)) \
        .replace("[SECOND_DUE_DATE]", str(second_due_date)) \
        .replace("[COURSE_LENGTH]", str(course_length))

    pdf = FPDF()
    pdf.add_page()

    # Register a Unicode-capable font so we can display characters
    # beyond the limited Latin-1 set.  If the font file is missing
    # we silently fall back to the built-in fonts.
    try:
        pdf.add_font("DejaVu", "", "font/DejaVuSans.ttf", uni=True)
        # Register the same file for bold and italic variants so that
        # style changes do not trigger missing font errors even if the
        # visual appearance remains regular.
        pdf.add_font("DejaVu", "B", "font/DejaVuSans.ttf", uni=True)
        pdf.add_font("DejaVu", "I", "font/DejaVuSans.ttf", uni=True)
        pdf.set_font("DejaVu", size=14)
    except Exception:
        pdf.set_font("Arial", size=14)

    pdf.cell(200, 10, safe_pdf(f"{school_name} Payment Receipt"), ln=True, align="C")
    pdf.set_font(pdf.font_family, 'B', size=12)
    pdf.set_text_color(0, 128, 0)
    pdf.cell(200, 10, safe_pdf(payment_status), ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font(pdf.font_family, size=12)
    pdf.ln(10)
    pdf.cell(200, 10, safe_pdf(f"Name: {student_row.get('Name','')}"), ln=True)
    pdf.cell(200, 10, safe_pdf(f"Student Code: {student_row.get('StudentCode','')}"), ln=True)
    pdf.cell(200, 10, safe_pdf(f"Phone: {student_row.get('Phone','')}"), ln=True)
    pdf.cell(200, 10, safe_pdf(f"Level: {student_row.get('Level','')}"), ln=True)
    pdf.cell(200, 10, f"Amount Paid: GHS {paid:.2f}", ln=True)
    pdf.cell(200, 10, f"Balance Due: GHS {balance:.2f}", ln=True)
    pdf.cell(200, 10, f"Total Course Fee: GHS {total_fee:.2f}", ln=True)
    pdf.cell(200, 10, safe_pdf(f"Contract Start: {student_row.get('ContractStart','')}"), ln=True)
    pdf.cell(200, 10, safe_pdf(f"Contract End: {student_row.get('ContractEnd','')}"), ln=True)
    pdf.cell(200, 10, f"Receipt Date: {payment_date}", ln=True)
    pdf.ln(10)
    pdf.cell(0, 10, safe_pdf("Thank you for your payment!"), ln=True)
    pdf.cell(0, 10, safe_pdf("Signed: Felix Asadu"), ln=True)
    pdf.ln(15)
    pdf.set_font(pdf.font_family, size=14)
    pdf.cell(200, 10, safe_pdf(f"{school_name} Student Contract"), ln=True, align="C")
    pdf.set_font(pdf.font_family, size=12)
    pdf.ln(10)
    try:
        # Build the notes string and sanitize it so only Latin-1
        # characters are sent to the PDF engine.  Characters outside
        # the range are replaced with '?' by ``safe_pdf``.
        notes_to_show = safe_pdf(filled)
        pdf.multi_cell(0, 10, notes_to_show, wrapmode=WrapMode.CHAR)
    except FPDFException:
        pdf.set_text_color(255, 0, 0)
        pdf.multi_cell(0, 10, safe_pdf("Error: Unable to wrap contract text."))
        pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    pdf.cell(0, 10, safe_pdf("Signed: Felix Asadu"), ln=True)
    pdf.set_y(-15)
    pdf.set_font(pdf.font_family, "I", 8)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf.cell(0, 10, safe_pdf(f"Generated on {now_str}"), align="C")

    # Return as bytes (for Streamlit or emailing)
    data = pdf.output(dest="S")
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        data = data.decode("latin-1")
    return data.encode("latin-1")
