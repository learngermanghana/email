import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore


st.set_page_config(page_title="Announcements", page_icon="📣")


def get_firestore_client():
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()


def parse_languages(raw: str) -> list[str]:
    if not raw:
        return []
    return [lang.strip() for lang in raw.split(",") if lang.strip()]


st.title("📣 Announcement Creator")
st.markdown(
    """
Create announcements that the web app can read from Firestore. Use the form below
to post directly to the `announcements` collection with the correct fields.
"""
)

with st.expander("Firestore writing guide for external Streamlit pages", expanded=True):
    st.markdown(
        """
**Where to write:** create a document in the `announcements` collection, ordered by
`createdAt` descending.

**Minimum fields the app reads (with fallbacks):**
- **Title:** `title` (fallbacks: `headline`)
- **Body:** `message` (fallbacks: `body`, `description`)
- **Link:** `linkUrl` (fallbacks: `link`, `url`)
- **Class targeting:** `className` (fallbacks: `class`, `classname`)
- **Language targeting:** `language` (fallbacks: `program`, `lang`) or `languages` array
- **Audience scope:** `audience` (fallbacks: `scope`, `target`)
- **Timestamp:** `createdAt` (Firestore timestamp)

**Targeting rules:**
- **Language:** matches `language` (e.g., `german`, `french`, or `all`) or `languages` array.
- **Class name:** matches `className` if present.
- **Audience:** `all`, `global`, or `everyone` shows for everyone.

**Important:** Creating a document triggers the `onAnnouncementCreated` Cloud Function
and sends push notifications.
"""
    )
    st.markdown("**Recommended payload:**")
    st.code(
        """{
  "title": "New course update",
  "message": "We’ve added fresh lessons this week.",
  "linkUrl": "https://example.com/update",
  "linkLabel": "Read more",
  "language": "all",
  "audience": "all",
  "className": "",
  "createdAt": "<Firestore serverTimestamp>"
}""",
        language="json",
    )

st.markdown("---")

with st.form("announcement_form"):
    title = st.text_input("Title", placeholder="New course update")
    message = st.text_area("Message", placeholder="We’ve added fresh lessons this week.")
    link_url = st.text_input("Link URL", placeholder="https://example.com/update")
    link_label = st.text_input("Link label (optional)", placeholder="Read more")
    class_name = st.text_input("Class name (optional)", placeholder="A1 Evening")
    audience = st.selectbox(
        "Audience",
        ["all", "global", "everyone", "students", "staff"],
        index=0,
    )
    language = st.text_input("Language (use 'all' for everyone)", value="all")
    languages_raw = st.text_input(
        "Languages list (optional, comma-separated)",
        placeholder="german, french",
    )
    submitted = st.form_submit_button("Publish announcement")

if submitted:
    languages = parse_languages(languages_raw)
    payload = {
        "title": title.strip(),
        "message": message.strip(),
        "linkUrl": link_url.strip(),
        "linkLabel": link_label.strip(),
        "language": language.strip() or "all",
        "audience": audience,
        "className": class_name.strip(),
        "createdAt": firestore.SERVER_TIMESTAMP,
    }
    if languages:
        payload["languages"] = languages

    db = get_firestore_client()
    db.collection("announcements").add(payload)
    st.success("Announcement published to Firestore.")
