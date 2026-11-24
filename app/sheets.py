"""Optional Google Sheets export, with flagged safety content separated."""

import os


def export_results(rows, sheet_name=None, worksheet_name="Results"):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:
        raise RuntimeError("Install Google Sheets dependencies from requirements.txt") from exc

    credentials_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/service-account.json")
    sheet_name = sheet_name or os.getenv("GOOGLE_SHEET_NAME")
    worksheet_name = os.getenv("GOOGLE_WORKSHEET_NAME", worksheet_name)

    if not sheet_name:
        raise RuntimeError("Set GOOGLE_SHEET_NAME or choose a sheet name.")
    if not os.path.isfile(credentials_path):
        raise RuntimeError(f"Google service-account credential not found: {credentials_path}")

    credentials = Credentials.from_service_account_file(credentials_path, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])
    client = gspread.authorize(credentials)
    sheet = client.open(sheet_name)
    nsfw_rows = [row for row in rows if row.get("nsfw_detected") or row.get("minor_like_detected")]
    regular_rows = [row for row in rows if row not in nsfw_rows]

    _update_worksheet(sheet, worksheet_name, regular_rows)
    _update_worksheet(sheet, os.getenv("GOOGLE_NSFW_WORKSHEET_NAME", "NSFW"), nsfw_rows)
    return len(rows)


def _update_worksheet(sheet, title, rows):
    try:
        worksheet = sheet.worksheet(title)
    except Exception:
        worksheet = sheet.add_worksheet(
            title=title,
            rows=max(100, len(rows) + 10),
            cols=max(20, len(rows[0]) if rows else 20),
        )
    worksheet.clear()
    if rows:
        headers = list(dict.fromkeys(key for row in rows for key in row))
        values = [headers] + [[row.get(header, "") for header in headers] for row in rows]
        worksheet.update(values)
