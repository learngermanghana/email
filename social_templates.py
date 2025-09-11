import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

_db = None


def _get_db():
    """Initialize and cache the Firestore client."""
    global _db
    if _db is None:
        if not firebase_admin._apps:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
        _db = firestore.client()
    return _db


def add_template(title: str, platform: str, content: str):
    """Add a new social media template to Firestore."""
    db = _get_db()
    db.collection("templates").add(
        {"title": title, "platform": platform, "content": content}
    )


def load_templates():
    """Return all templates stored in Firestore using a snapshot listener."""
    db = _get_db()
    state = st.session_state

    if "template_listener" not in state:
        query = db.collection("templates").select(["title", "platform", "content"])

        def on_snapshot(col_snapshot, changes, read_time):
            templates = []
            for doc in col_snapshot:
                data = doc.to_dict() or {}
                data["id"] = doc.id
                templates.append(data)
            state["templates"] = templates
            st.experimental_rerun()

        state["template_listener"] = query.on_snapshot(on_snapshot)

    return state.get("templates", [])


def delete_template(template_id: str):
    """Delete a template by document id."""
    db = _get_db()
    db.collection("templates").document(template_id).delete()


if __name__ == "__main__":
    st.title("\U0001F4E3 Social Media Templates")
    st.info(
        "This module now serves as a helper. Run `streamlit run email.py` and open the 'Social Templates' page."
    )
