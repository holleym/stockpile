# Google Sheets Setup Guide

One-time configuration to allow the script to write to your Google Sheet.

---

## What you'll need

- A Google account
- About 20 minutes
- The script already downloaded and Python packages installed

---

## Step 1 — Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown at the top → **New Project**
3. Name it anything (e.g. "Position Tracker") and click **Create**
4. Make sure the new project is selected in the dropdown before continuing

---

## Step 2 — Enable the Google Sheets API

1. In the left menu go to **APIs & Services → Library**
2. Search for **Google Sheets API**
3. Click it and click **Enable**

---

## Step 3 — Configure the OAuth Consent Screen

You only need to do this if Google prompts you — it may appear when you try to create credentials.

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** and click **Create**
3. Fill in:
   - **App name:** anything (e.g. "Position Tracker")
   - **User support email:** your email
   - **Developer contact email:** your email
4. Click **Save and Continue** through the remaining screens (no changes needed)

---

## Step 4 — Create OAuth Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Under Application type choose **Desktop app**
4. Give it a name (anything) and click **Create**
5. Click **Download JSON** on the confirmation dialog

---

## Step 5 — Save the Credentials File

Move the downloaded JSON file to:

**Mac / Linux:**
```
~/.config/google-sheets-oauth.json
```

**Windows:**
```
C:\Users\YourName\.config\google-sheets-oauth.json
```

If the `.config` folder doesn't exist, create it.

---

## Step 6 — Create Your Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a new blank spreadsheet
2. Name it anything (e.g. "Position Tracker")
3. Copy the spreadsheet ID from the URL — it's the long string between `/d/` and `/edit`:
   ```
   https://docs.google.com/spreadsheets/d/THIS-IS-THE-ID/edit
   ```

---

## Step 7 — Set Your Spreadsheet ID

Set the `GOOGLE_SHEETS_ID` environment variable to your spreadsheet ID. This keeps your ID
out of the code so you never have to edit the script.

**Mac / Linux** — add to `~/.bashrc` or `~/.zshrc`:
```bash
export GOOGLE_SHEETS_ID="your-id-here"
```

**PowerShell (Windows)** — add to your `$PROFILE`:
```powershell
$env:GOOGLE_SHEETS_ID="your-id-here"
```

After editing your profile file, restart your terminal (or run `source ~/.bashrc`) for the
change to take effect. The script will print a clear error if the variable is not set.

---

## Step 8 — Authorize on First Run

The first time you run the script, a browser window will open asking you to sign in to your Google account and allow access to Google Sheets. Click **Allow**.

The script saves an auth token locally so you won't be prompted again unless the token expires or is revoked.

---

## Troubleshooting

**"Token has been expired or revoked"**
Delete `~/.config/google-sheets-token.json` (Windows: `C:\Users\YourName\.config\google-sheets-token.json`) and run the script again. The browser prompt will reappear.

**"The caller does not have permission"**
Make sure you're using the same Google account for both the Cloud project and the Google Sheet. If you created the Sheet under a different account, either move it or redo the credentials under the correct account.

**"Unable to parse range"**
The spreadsheet ID is wrong, or the sheet was deleted. Double-check the value of `GOOGLE_SHEETS_ID` against the ID in the sheet's URL, and make sure the spreadsheet still exists.

**Consent screen asks to verify the app**
You don't need to verify it — this is your own personal app. Click **Continue** (or **Advanced → Go to [app name] (unsafe)**) to proceed.
