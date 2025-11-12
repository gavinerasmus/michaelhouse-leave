# Quick Start - Michaelhouse Leave System

Get the leave system running in 15 minutes!

## Prerequisites

- PostgreSQL 12+ installed
- Python 3.8+
- Go 1.19+ (for WhatsApp bridge)

## Step-by-Step Setup

### 1. Database Setup (5 minutes)

```bash
# Navigate to database directory
cd leave-system/database

# Run automated setup (creates DB, loads schema & seed data)
./setup_database.sh --reset

# Verify it worked
psql -U leave_user -d michaelhouse_leave -c "SELECT COUNT(*) FROM students;"
# Should show: 6
```

### 2. Install Python Dependencies (2 minutes)

```bash
cd ../  # Back to leave-system/
pip3 install -r requirements.txt
```

### 3. Configure Environment (2 minutes)

The setup script created a `.env` file. Update it with your email credentials:

```bash
nano .env
```

Update these lines:
```env
LEAVE_EMAIL=your-email@michaelhouse.org
LEAVE_EMAIL_PASSWORD=your-app-specific-password
```

### 4. Test the System (3 minutes)

```bash
# Run the demo (uses placeholder tools)
python3 demo.py

# Test the Flask API
python3 api.py &

# Test health check
curl http://localhost:8090/health

# Test a leave request
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can James have overnight leave this Saturday?",
    "sender": "27603174174",
    "channel": "whatsapp"
  }'
```

### 5. Switch to Real Database (1 minute)

Update `api.py` to use database tools instead of placeholders:

```python
# In api.py, replace:
from processors.leave_processor import LeaveProcessor
processor = LeaveProcessor()

# With:
from processors.leave_processor import LeaveProcessor
from tools.database_tools import DatabaseTools

tools = DatabaseTools()
processor = LeaveProcessor()
processor.tools = tools
```

### 6. Start All Services (2 minutes)

Open 3 terminals:

**Terminal 1 - Flask API:**
```bash
cd leave-system
python3 api.py
```

**Terminal 2 - WhatsApp Bridge:**
```bash
cd whatsapp-bridge
CGO_ENABLED=1 go run main.go
```

**Terminal 3 - Email Bridge (optional):**
```bash
cd leave-system/email-bridge
python3 run_email_bridge.py
```

## ✅ System Ready!

The system is now running and ready to process leave requests.

## Test Scenarios

### Test 1: WhatsApp Leave Request

Send a WhatsApp message to the connected number:
```
"Hi, can James have overnight leave this Saturday?"
```

### Test 2: Email Leave Request

Send an email to your configured leave email:
```
Subject: Leave Request
Body: Please approve leave for Michael Doe (67890) on 14th February
```

### Test 3: Housemaster Query

Email from housemaster email:
```
What is the leave balance for student 12345?
```

## Troubleshooting

### Database Connection Error
```bash
# Check PostgreSQL is running
brew services list | grep postgresql  # macOS
sudo systemctl status postgresql      # Linux

# Test connection
psql -U leave_user -d michaelhouse_leave
```

### Import Errors
```bash
# Make sure you're in the right directory
cd leave-system
python3 -c "from processors.leave_processor import LeaveProcessor; print('OK')"
```

### API Not Responding
```bash
# Check if port is already in use
lsof -i :8090

# Try different port
FLASK_PORT=8091 python3 api.py
```

## Database Access

### View All Students
```sql
psql -U leave_user -d michaelhouse_leave
SELECT admin_number, first_name, last_name, house, block FROM students;
```

### Check Leave Balances
```sql
SELECT s.admin_number, s.first_name, s.last_name,
       lb.overnight_remaining, lb.friday_supper_remaining
FROM students s
JOIN leave_balances lb ON s.id = lb.student_id
WHERE lb.year = 2025 AND lb.term_number = 1;
```

### View Active Leaves
```sql
SELECT * FROM active_leaves;
```

## Production Deployment

For production deployment:

1. **Set up HTTPS/TLS**
2. **Configure Gunicorn**:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8090 api:app
   ```
3. **Set up Nginx reverse proxy**
4. **Create systemd services**
5. **Set up automated backups**

See `INTEGRATION_GUIDE.md` for full deployment instructions.

## Next Steps

1. ✅ System is running
2. 📱 Integrate with WhatsApp bridge (see `INTEGRATION_GUIDE.md`)
3. 📧 Configure email monitoring
4. 🧪 Add comprehensive tests
5. 📱 Build Guard Flutter app
6. 🚀 Deploy to production

## Support

- **Full Documentation:** `leave-system/README.md`
- **Build Status:** `leave-system/BUILD_STATUS.md`
- **Integration Guide:** `INTEGRATION_GUIDE.md`
- **Requirements:** `requirements/michaelhouse-leave-requirements.md`

---

**Ready to process leave requests! 🎉**
