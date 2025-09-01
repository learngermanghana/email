# email

## Pending Students View

When reviewing pending students, the app preselects a set of columns for quick viewing and editing. The default columns are:

- Name
- Phone
- Email
- Location
- Level
- Paid
- Balance
- ContractStart
- ContractEnd
- StudentCode
- ClassName

All default columns, including **ClassName**, can be edited directly in the interface.

## Configuration

The app posts selected rows to a Google Apps Script Web App. Provide the endpoint and optional API key through Streamlit secrets or environment variables.

Example `secrets.toml`:

```
[apps_script]
pending_to_main_webapp_url = "https://script.google.com/macros/s/.../exec"
app_key = "optional-api-key"
```

Environment variables can be used as a fallback:

- `PENDING_TO_MAIN_WEBAPP_URL` – Apps Script Web App URL
- `APP_KEY` – optional API key
