# email

## About Us Page

The application provides an **About Us** tab that stores key contact and social media information for the team. Links can be viewed in the app or downloaded as a CSV for quick reference.

## Weekly Team Tasks

Run `streamlit run todo.py` to manage weekly team tasks.

The page lets you:

- Add tasks with a description, assignee, and due week.
- Mark tasks complete from an interactive checklist.

Tasks persist in Firestore under the `tasks` collection with fields `description`, `assignee`, `week` (ISO date), and `completed`. Configure `st.secrets["firebase"]` for database access. If SMTP details are provided in `st.secrets`, assignees receive email notifications when tasks are created or updated.
