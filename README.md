# email

## Contract Alerts Page

The application provides a **Contract Alerts** tab that highlights students whose contracts are ending soon or have already ended. You can adjust the alert window and download the results as CSV files for quick follow-up.

## Social Media Templates

Launch the app with `streamlit run email.py` and open the **Social Templates** page to manage reusable social media templates.

The page lets you:

- Save template title, platform, and content.
- View existing templates in a table.
- Delete templates you no longer need.

Templates persist in Firestore under the `templates` collection with fields `title`, `platform`, and `content`.

## Removed Features

The leaderboard page and associated student statistics functionality have been removed.
