# Google Sheets Backend Setup Guide

**Use Google Sheets as a database alternative for testing and demos!**

## Why Use Google Sheets?

✅ **No database installation** - No PostgreSQL setup required
✅ **Easy to view/edit** - View and modify data directly in browser
✅ **Quick setup** - Running in 10 minutes
✅ **Perfect for demos** - Great for prototyping and presentations
✅ **Easy collaboration** - Share with team members

## Prerequisites

- Google Cloud account (free tier works)
- Google Drive account
- Python 3.8+

---

## Step 1: Create Google Cloud Project (5 minutes)

### 1.1 Go to Google Cloud Console
https://console.cloud.google.com/

### 1.2 Create New Project
- Click "Select a project" → "New Project"
- Name: "Michaelhouse Leave System"
- Click "Create"

### 1.3 Enable Google Sheets API
- Go to "APIs & Services" → "Library"
- Search for "Google Sheets API"
- Click "Enable"

### 1.4 Create Service Account
- Go to "APIs & Services" → "Credentials"
- Click "Create Credentials" → "Service Account"
- Name: "leave-system-sa"
- Click "Create and Continue"
- Role: "Editor" (or "Basic Editor")
- Click "Done"

### 1.5 Create Service Account Key
- Click on the service account you just created
- Go to "Keys" tab
- Click "Add Key" → "Create new key"
- Choose "JSON"
- Click "Create"
- **Save the downloaded JSON file** (e.g., `credentials.json`)

---

## Step 2: Create Google Sheets Template (3 minutes)

### 2.1 Create New Google Sheet
- Go to https://sheets.google.com
- Create a new blank spreadsheet
- Name it: "Michaelhouse Leave System Data"

### 2.2 Add Sheets (Tabs)

Create 9 sheets with these exact names:

1. **parents**
2. **students**
3. **student_parents**
4. **leave_balances**
5. **leave_register**
6. **restrictions**
7. **term_config**
8. **closed_weekends**
9. **housemasters**

### 2.3 Add Headers to Each Sheet

#### Sheet 1: "parents"
```
id | phone | email | first_name | last_name | active
```

#### Sheet 2: "students"
```
id | admin_number | first_name | last_name | house | block | active
```

#### Sheet 3: "student_parents"
```
student_id | parent_id
```

#### Sheet 4: "leave_balances"
```
student_id | year | term | overnight_remaining | friday_supper_remaining
```

#### Sheet 5: "leave_register"
```
leave_id | student_id | leave_type | start_datetime | end_datetime | status | requested_by | channel | created_at | active
```

#### Sheet 6: "restrictions"
```
student_id | restriction_id | start_date | end_date | reason | active
```

#### Sheet 7: "term_config"
```
year | term | start_date | end_date
```

#### Sheet 8: "closed_weekends"
```
block_letter | weekend_date | reason
```

#### Sheet 9: "housemasters"
```
id | email | phone | house | first_name | last_name | active
```

### 2.4 Add Sample Data

**parents sheet:**
```
parent-001 | 27603174174 | john.smith@example.com | John | Smith | true
parent-002 | 27603174175 | jane.doe@example.com | Jane | Doe | true
```

**students sheet:**
```
student-001 | 12345 | James | Smith | Finningley | E | true
student-002 | 67890 | Michael | Doe | Clark | D | true
```

**student_parents sheet:**
```
student-001 | parent-001 | father
student-002 | parent-002 | mother
```

**leave_balances sheet:**
```
student-001 | 2025 | Term 1 | 3 | 3
student-002 | 2025 | Term 1 | 3 | 3
```

**term_config sheet:**
```
2025 | Term 1 | 2025-01-15 | 2025-03-20
2025 | Term 2 | 2025-04-01 | 2025-06-15
```

**closed_weekends sheet:**
```
E | 2025-02-15 | Inter-house competition
D | 2025-03-01 | Sports weekend
```

**housemasters sheet:**
```
hm-001 | hm.finningley@michaelhouse.org | 27831112222 | Finningley | David | Jones | true
```

### 2.5 Get Sheet ID

From the URL of your Google Sheet:
```
https://docs.google.com/spreadsheets/d/1abc...xyz/edit
                                        ^^^^^^^^^
                                        This is your SHEET_ID
```

Copy the Sheet ID (the long string between `/d/` and `/edit`)

### 2.6 Share with Service Account

- Click "Share" button in Google Sheets
- Paste the service account email from `credentials.json`:
  - Look for `"client_email"` field
  - Should look like: `leave-system-sa@project-name.iam.gserviceaccount.com`
- Give "Editor" access
- Click "Send"

---

## Step 3: Configure Leave System (2 minutes)

### 3.1 Install Google Sheets Dependencies

```bash
cd leave-system
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

Or use requirements.txt:
```bash
pip install -r requirements.txt
```

### 3.2 Create/Update .env File

```bash
cd leave-system
nano .env
```

Add these lines:
```env
# Google Sheets Backend (for testing)
USE_GOOGLE_SHEETS=true
GOOGLE_SHEETS_CREDENTIALS_PATH=/absolute/path/to/your/credentials.json
GOOGLE_SHEET_ID=your-sheet-id-from-step-2.5

# Anthropic API (for AI features)
ANTHROPIC_API_KEY=your-anthropic-key
```

**Replace:**
- `/absolute/path/to/your/credentials.json` with actual path
- `your-sheet-id-from-step-2.5` with your Sheet ID
- `your-anthropic-key` with your Anthropic API key

### 3.3 Update api.py to Use Sheets

The API will automatically use Google Sheets if `USE_GOOGLE_SHEETS=true` in `.env`.

Or manually specify in code:

```python
# In api.py
from dotenv import load_dotenv
import os

load_dotenv()

# Check if we should use Google Sheets
if os.getenv('USE_GOOGLE_SHEETS', 'false').lower() == 'true':
    from tools.google_sheets_tools import GoogleSheetsTools
    tools = GoogleSheetsTools()
    print("✅ Using Google Sheets backend")
else:
    from tools.database_tools import DatabaseTools
    tools = DatabaseTools()
    print("✅ Using PostgreSQL backend")

# Initialize processor with tools
from processors.leave_processor import LeaveProcessor
processor = LeaveProcessor()
processor.tools = tools
```

---

## Step 4: Test the System (2 minutes)

### 4.1 Start the API

```bash
cd leave-system
python3 api.py
```

**Expected output:**
```
✅ Using Google Sheets backend
Starting Michaelhouse Leave API on http://localhost:8090
Endpoints:
  GET  /health - Health check
  POST /api/conversation - Conversational AI agent
```

### 4.2 Test API

```bash
curl -X POST http://localhost:8090/api/conversation \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can James Smith have leave this Saturday?",
    "sender": "27603174174",
    "channel": "test",
    "chat_id": "test-123"
  }'
```

### 4.3 Check Google Sheets

- Open your Google Sheet
- Go to "leave_register" tab
- You should see a new row with the approved leave!

---

## Advantages

| Feature | Google Sheets | PostgreSQL |
|---------|---------------|------------|
| Setup Time | 10 minutes | 30+ minutes |
| Database Install | ❌ Not needed | ✅ Required |
| View Data | ✅ Browser | Command line |
| Edit Data | ✅ Direct edit | SQL commands |
| Collaboration | ✅ Easy sharing | Harder |
| Performance | Good for demos | Better for production |
| Scalability | Limited | Excellent |

## When to Use Each

### Use Google Sheets For:
- ✅ Quick demos and presentations
- ✅ Prototyping and testing
- ✅ Non-technical user testing
- ✅ Small data sets (<1000 requests/month)
- ✅ Easy data inspection

### Use PostgreSQL For:
- ✅ Production deployment
- ✅ High volume (>1000 requests/month)
- ✅ Better security
- ✅ Complex queries
- ✅ Data integrity

---

## Troubleshooting

### Error: "GOOGLE_SHEETS_CREDENTIALS_PATH not set"

**Solution:** Check your `.env` file has the correct path to `credentials.json`

```bash
echo $GOOGLE_SHEETS_CREDENTIALS_PATH
# Should show the full path to your credentials.json
```

### Error: "The caller does not have permission"

**Solution:** Make sure you shared the Google Sheet with the service account email

1. Check `credentials.json` for `"client_email"`
2. Go to Google Sheets → Share
3. Add that email with Editor access

### Error: "Unable to find sheet"

**Solution:** Check the GOOGLE_SHEET_ID in `.env` matches your Sheet ID from the URL

### Data Not Updating

**Solution:**
1. Check Sheet tab names match exactly (case-sensitive)
2. Check column headers are correct
3. Refresh the Google Sheet in browser

### API Running But Can't Authenticate

**Solution:** Add more sample data to the `parents` sheet with the phone number you're testing with

---

## Switching Back to PostgreSQL

To switch back to database:

```bash
# In .env file, change:
USE_GOOGLE_SHEETS=false

# Or remove the line entirely

# Restart API
python3 api.py
```

---

## Next Steps

1. ✅ Test with WhatsApp bridge
2. ✅ Add more sample students/parents
3. ✅ Test all leave types
4. ✅ Export data to PostgreSQL when ready for production

---

## Example Complete .env File

```env
# Backend Selection
USE_GOOGLE_SHEETS=true

# Google Sheets Configuration
GOOGLE_SHEETS_CREDENTIALS_PATH=/Users/you/michaelhouse/credentials.json
GOOGLE_SHEET_ID=1abc123def456ghi789jkl012mno345pqr678stu

# AI Configuration
ANTHROPIC_API_KEY=sk-ant-api03-xxx...

# Email (if using email bridge)
LEAVE_EMAIL=leave@michaelhouse.org
LEAVE_EMAIL_PASSWORD=your-app-password
IMAP_SERVER=imap.gmail.com
SMTP_SERVER=smtp.gmail.com
```

---

**Status:** Ready to use Google Sheets as your database! 🎉

**Questions?** Check the main [README.md](../README.md) or [QUICKSTART.md](../QUICKSTART.md)
