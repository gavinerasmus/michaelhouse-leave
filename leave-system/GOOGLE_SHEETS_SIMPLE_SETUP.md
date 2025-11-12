# Simple Google Sheets Setup (Personal Account)

**Use Google Sheets with your personal Google account - NO service account needed!**

This is the **simplified version** for local testing using your regular Google account.

---

## ⚡ Super Quick Setup (5 minutes)

### Step 1: Enable Google Sheets API (2 minutes)

1. **Go to Google Cloud Console:**
   https://console.cloud.google.com/

2. **Create a new project** (if you don't have one):
   - Click "Select a project" → "New Project"
   - Name: "Leave System Test"
   - Click "Create"

3. **Enable Google Sheets API:**
   - Go to "APIs & Services" → "Library"
   - Search for "Google Sheets API"
   - Click "Enable"

4. **Create OAuth credentials:**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - If prompted, configure OAuth consent screen:
     - User Type: "External"
     - App name: "Leave System"
     - Your email in required fields
     - Save
   - Application type: "Desktop app"
   - Name: "Leave System Local"
   - Click "Create"

5. **Download credentials:**
   - Click the download button (⬇️) next to your OAuth client
   - Save as `client_secrets.json` in your leave-system folder

---

### Step 2: Create Google Sheet (2 minutes)

1. **Go to Google Sheets:**
   https://sheets.google.com

2. **Create a new spreadsheet**
   - Name it: "Leave System Data"

3. **Add 9 sheets (tabs)** with these exact names:
   - `parents`
   - `students`
   - `student_parents`
   - `leave_balances`
   - `leave_register`
   - `restrictions`
   - `term_config`
   - `closed_weekends`
   - `housemasters`

4. **Add headers to each sheet:**

   **parents sheet (Sheet 1):**
   ```
   id | phone | email | first_name | last_name | active
   ```

   **students sheet (Sheet 2):**
   ```
   id | admin_number | first_name | last_name | house | block | active
   ```

   **student_parents sheet (Sheet 3):**
   ```
   student_id | parent_id
   ```

   **leave_balances sheet (Sheet 4):**
   ```
   student_id | year | term | overnight_remaining | friday_supper_remaining
   ```

   **leave_register sheet (Sheet 5):**
   ```
   leave_id | student_id | leave_type | start_datetime | end_datetime | status | requested_by | channel | created_at | active
   ```

   **restrictions sheet (Sheet 6):**
   ```
   student_id | restriction_id | start_date | end_date | reason | active
   ```

   **term_config sheet (Sheet 7):**
   ```
   year | term | start_date | end_date
   ```

   **closed_weekends sheet (Sheet 8):**
   ```
   block_letter | weekend_date | reason
   ```

   **housemasters sheet (Sheet 9):**
   ```
   id | email | phone | house | first_name | last_name | active
   ```

5. **Add sample data (optional but recommended):**

   **parents:**
   ```
   parent-001 | 27603174174 | john@example.com | John | Smith | true
   ```

   **students:**
   ```
   student-001 | 12345 | James | Smith | Finningley | E | true
   ```

   **student_parents:**
   ```
   student-001 | parent-001
   ```

   **leave_balances:**
   ```
   student-001 | 2025 | Term 1 | 3 | 3
   ```

   **term_config:**
   ```
   2025 | Term 1 | 2025-01-15 | 2025-03-20
   ```

6. **Get Sheet ID from URL:**
   ```
   https://docs.google.com/spreadsheets/d/1abc123def456/edit
                                        ^^^^^^^^^^^
                                        This is your Sheet ID
   ```

---

### Step 3: Configure Leave System (1 minute)

1. **Update .env file:**
   ```bash
   cd leave-system
   nano .env
   ```

2. **Add these lines:**
   ```env
   # Use Google Sheets backend
   USE_GOOGLE_SHEETS=true
   USE_SIMPLE_OAUTH=true

   # OAuth credentials (file you downloaded)
   GOOGLE_OAUTH_CREDENTIALS_PATH=/full/path/to/client_secrets.json

   # Your Sheet ID
   GOOGLE_SHEET_ID=your-sheet-id-from-url

   # Anthropic API key
   ANTHROPIC_API_KEY=your-anthropic-key
   ```

3. **Install dependencies (if not already done):**
   ```bash
   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
   ```

---

### Step 4: Run and Authenticate (1 minute)

1. **Start the API:**
   ```bash
   cd leave-system
   python3 api.py
   ```

2. **Browser will open automatically:**
   - Sign in with your Google account
   - Click "Allow" to grant access to Google Sheets
   - Browser will show: "The authentication flow has completed"
   - Close the browser tab

3. **API will continue starting:**
   ```
   ✅ Authentication successful!
   Token saved to: /path/to/token.pickle
   ✅ Using Google Sheets backend (Simple OAuth)
   Starting Michaelhouse Leave API on http://localhost:8090
   ```

4. **Done!** The token is saved - you won't need to authenticate again!

---

## 🎉 That's It!

**Next time you run the API, it will use the saved token automatically.**

No browser popup, no re-authentication needed!

---

## Testing

```bash
# Test the API
curl -X POST http://localhost:8090/api/conversation \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can James Smith have leave this Saturday?",
    "sender": "27603174174",
    "channel": "test",
    "chat_id": "test-123"
  }'
```

Check your Google Sheet - you should see a new row in the `leave_register` tab!

---

## Key Differences from Service Account

| Feature | Simple OAuth (This Guide) | Service Account |
|---------|---------------------------|-----------------|
| **Setup** | 5 minutes | 10 minutes |
| **Google Account** | Your personal account | Separate service account |
| **Authentication** | Browser popup (once) | JSON credentials file |
| **Sharing** | Not needed (it's your sheet) | Must share with service email |
| **Best For** | Local testing, personal use | Production, automation |
| **Token Management** | Auto-refresh | Always valid |

---

## File Structure

After setup, you'll have:

```
leave-system/
├── client_secrets.json       ← OAuth credentials (downloaded from Google)
├── token.pickle              ← Auto-created after first auth (saved token)
├── .env                      ← Your configuration
└── api.py                    ← Will auto-detect simple OAuth mode
```

**Important:** Add to `.gitignore`:
```
client_secrets.json
token.pickle
.env
```

---

## Troubleshooting

### "GOOGLE_OAUTH_CREDENTIALS_PATH not set"

**Solution:** Check your `.env` file has the full path to `client_secrets.json`

```bash
cd leave-system
echo "GOOGLE_OAUTH_CREDENTIALS_PATH=$(pwd)/client_secrets.json" >> .env
```

### Browser doesn't open

**Solution:** Check the terminal output for a URL and open it manually:
```
Please visit this URL to authorize: https://accounts.google.com/...
```

### "Access blocked: Leave System hasn't verified"

**Solution:** This is normal for testing. Click "Advanced" → "Go to Leave System (unsafe)"

This warning appears because the app isn't published. It's safe for personal testing.

### Token expired or invalid

**Solution:** Delete the token and re-authenticate:
```bash
rm token.pickle
python3 api.py  # Will prompt for authentication again
```

---

## Switching Between Backends

**Use Google Sheets (Simple OAuth):**
```env
USE_GOOGLE_SHEETS=true
USE_SIMPLE_OAUTH=true
GOOGLE_OAUTH_CREDENTIALS_PATH=...
```

**Use PostgreSQL:**
```env
USE_GOOGLE_SHEETS=false
# PostgreSQL settings...
```

**Use Placeholder (no backend):**
```env
USE_GOOGLE_SHEETS=false
# Don't set database settings
```

---

## Example Complete .env File

```env
# Backend
USE_GOOGLE_SHEETS=true
USE_SIMPLE_OAUTH=true

# Google Sheets (Simple OAuth)
GOOGLE_OAUTH_CREDENTIALS_PATH=/Users/you/leave-system/client_secrets.json
GOOGLE_SHEET_ID=1abc123def456ghi789

# AI
ANTHROPIC_API_KEY=sk-ant-api03-xxx...

# API
FLASK_PORT=8090
LOG_LEVEL=INFO
```

---

## Benefits of Simple OAuth

✅ **Easier Setup** - Just enable API and download credentials
✅ **No Sharing** - It's your sheet, you already have access
✅ **Personal Testing** - Perfect for local development
✅ **Auto-Refresh** - Token refreshes automatically
✅ **One-Time Auth** - Browser popup only happens once

---

## Next Steps

1. ✅ Start the API and authenticate
2. ✅ Test with curl
3. ✅ Check your Google Sheet for data
4. ✅ Connect WhatsApp bridge
5. ✅ Test real requests

---

**Status:** Ready to use Google Sheets with your personal account! 🎉

**Questions?** See the main [README.md](../README.md) or [QUICKSTART.md](../QUICKSTART.md)
