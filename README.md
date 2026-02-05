# email

## Streamlit Pages

Launch the app with `streamlit run email.py`.

Available pages:

- **Course schedule generator** for A1/A2/B1, with TXT/JSON/PDF downloads.
- **Class attendance** tracking with Firestore-backed persistence.

## Firestore Announcement Writing Guide (External Streamlit Page)

If you want a separate Streamlit page to create announcements that this app can read, write a new document to the **`announcements`** collection in Firestore.

### Minimum fields to include

The app expects these fields (with fallbacks) when reading announcements:

- `title` (fallbacks: `headline`)
- `message` (fallbacks: `body`, `description`)
- `linkUrl` (fallbacks: `link`, `url`)
- `className` (fallbacks: `class`, `classname`)
- `language` (fallbacks: `program`, `lang`) or `languages` array
- `audience` (fallbacks: `scope`, `target`)
- `createdAt` (Firestore timestamp for correct ordering)

### Recommended payload

```json
{
  "title": "New course update",
  "message": "We’ve added fresh lessons this week.",
  "linkUrl": "https://example.com/update",
  "linkLabel": "Read more",
  "language": "all",
  "audience": "all",
  "className": "",
  "createdAt": "<Firestore serverTimestamp>"
}
```

### Targeting rules

Announcements are filtered by:

- **Language** (`language` or `languages` array; use `"all"` for everyone)
- **Class** (`className` when present)
- **Audience** (`audience` values like `all`, `global`, or `everyone` show to all users)

### Streamlit/Firebase recommendation

Use the Firebase Admin SDK from your external Streamlit app and set `createdAt` to `firestore.SERVER_TIMESTAMP` when creating the announcement document.

## Removed Pages

Contract alerts, all-student listings, reminders, contract PDFs, and send-email workflows were removed from the Streamlit navigation.
