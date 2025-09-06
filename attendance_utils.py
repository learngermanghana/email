import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

_db = None

def _get_db():
    global _db
    if _db is None:
        if not firebase_admin._apps:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
        _db = firestore.client()
    return _db

def save_attendance_to_firestore(class_name: str, attendance_map: dict):
    """Persist attendance data to Firestore.

    Parameters
    ----------
    class_name: str
        Name of the class grouping the sessions.
    attendance_map: dict
        Mapping of session_id -> {student_code: present_bool}.
    """
    db = _get_db()
    for session_id, session_data in attendance_map.items():
        (db.collection("attendance")
           .document(class_name)
           .collection("sessions")
           .document(str(session_id))
           .set(session_data))

def load_attendance_from_firestore(class_name: str) -> dict:
    """Load attendance data for a class from Firestore.

    Returns mapping of session_id -> {student_code: present_bool}.
    """
    db = _get_db()
    docs = (db.collection("attendance")
              .document(class_name)
              .collection("sessions")
              .stream())
    result = {}
    for doc in docs:
        result[doc.id] = doc.to_dict() or {}
    return result
