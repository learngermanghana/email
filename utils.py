"""Utility functions for PDF generation and text handling."""


def safe_pdf(text):
    """Return a PDF-safe latin-1 string, replacing unsupported characters."""
    return "".join(c if ord(c) < 256 else "?" for c in str(text or ""))

