# email

## Contract Alerts Page

The application provides a **Contract Alerts** tab that highlights students whose contracts are ending soon or have already ended. You can adjust the alert window and download the results as CSV files for quick follow-up.

## Weekly Team Tasks

Launch the main app with `streamlit run email.py` and open the **📝 Weekly Tasks** tab to manage weekly team tasks.

The page lets you:

- Add tasks with a description, assignee, and due week.
- Mark tasks complete from an interactive checklist.

Tasks persist in Firestore under the `tasks` collection with fields `description`, `assignee`, `week` (ISO date), and `completed`. Configure `st.secrets["firebase"]` for database access. If SMTP details are provided in `st.secrets`, assignees receive email notifications when tasks are created or updated.

## Social Media Templates

Launch the app with `streamlit run email.py` and open the **Social Templates** page to manage reusable social media templates.

The page lets you:

- Save template title, platform, and content.
- View existing templates in a table.
- Delete templates you no longer need.

Templates persist in Firestore under the `templates` collection with fields `title`, `platform`, and `content`.
