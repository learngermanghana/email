import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

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
    """Return all templates stored in Firestore."""
    db = _get_db()
    docs = db.collection("templates").stream()
    templates = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        templates.append(data)
    return templates

def delete_template(template_id: str):
    """Delete a template by document id."""
    db = _get_db()
    db.collection("templates").document(template_id).delete()

st.title("\U0001F4E3 Social Media Templates")

with st.form("template_form", clear_on_submit=True):
    title = st.text_input("Title")
    platform = st.text_input("Platform")
    content = st.text_area("Template")
    submitted = st.form_submit_button("Save template")

if submitted and title and platform and content:
    add_template(title, platform, content)
    st.success("Template saved!")

templates = load_templates()
if templates:
    df = pd.DataFrame(templates).drop(columns=["id"]) if templates else pd.DataFrame()
    st.dataframe(df)
    for tmpl in templates:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.write(f"**{tmpl['title']}** ({tmpl['platform']})")
        with col2:
            st.write(tmpl["content"])
        with col3:
            if st.button("Delete", key=f"del_{tmpl['id']}"):
                delete_template(tmpl["id"])
                st.experimental_rerun()
else:
    st.info("No templates yet.")
