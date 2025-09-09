import streamlit as st
from datetime import date, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
import smtplib

_db = None

def _get_db():
    global _db
    if _db is None:
        if not firebase_admin._apps:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
        _db = firestore.client()
    return _db

def add_task(description: str, assignee: str, week: str, due: str | None = None):
    db = _get_db()
    db.collection("tasks").add(
        {
            "description": description,
            "assignee": assignee,
            "week": week,
            "due": due,
            "completed": False,
        }
    )

def load_tasks(week: str):
    db = _get_db()
    docs = db.collection("tasks").where("week", "==", week).stream()
    tasks = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        tasks.append(data)
    return tasks

def update_task(task_id: str, updates: dict):
    db = _get_db()
    db.collection("tasks").document(task_id).update(updates)

def notify_assignee(email: str, subject: str, body: str):
    try:
        smtp_conf = st.secrets.get("smtp", {})
        sender = st.secrets.get("email_sender")
        host = smtp_conf.get("host")
        port = smtp_conf.get("port")
        username = smtp_conf.get("username")
        password = smtp_conf.get("password")
        if not all([sender, host, port, email]):
            return
        msg = f"Subject: {subject}\n\n{body}"
        with smtplib.SMTP(host, port) as server:
            if smtp_conf.get("use_tls", True):
                server.starttls()
            if username and password:
                server.login(username, password)
            server.sendmail(sender, [email], msg)
    except Exception as exc:
        st.warning(f"Notification failed: {exc}")

def main():
    st.title("📝 Weekly Team Tasks")

    selected_week = st.date_input("Select week", value=date.today())
    selected_week_start = selected_week - timedelta(days=selected_week.weekday())

    with st.form("task_form", clear_on_submit=True):
        desc = st.text_input("Task description")
        assignee = st.text_input("Assignee")
        due = st.date_input("Due date", value=selected_week)
        notify = st.checkbox("Email assignee", value=False)
        submitted = st.form_submit_button("Add task")

    if submitted and desc and assignee:
        week_start = due - timedelta(days=due.weekday())
        week_str = week_start.isoformat()
        due_str = due.isoformat()
        add_task(desc, assignee, week_str, due_str)
        if notify:
            notify_assignee(
                assignee,
                "New task assigned",
                f"'{desc}' due {due_str}",
            )
        st.success("Task added!")

    st.subheader(f"Tasks for week of {selected_week_start.isoformat()}")
    for task in load_tasks(selected_week_start.isoformat()):
        checked = st.checkbox(
            f"{task['description']} - {task['assignee']} (due {task.get('due', task['week'])})",
            value=task.get("completed", False),
            key=task["id"],
        )
        if checked != task.get("completed", False):
            update_task(task["id"], {"completed": checked})
            notify_assignee(
                task["assignee"],
                "Task updated",
                f"'{task['description']}' marked {'complete' if checked else 'incomplete'}",
            )


if __name__ == "__main__":
    main()

