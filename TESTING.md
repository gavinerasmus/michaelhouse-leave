# Michaelhouse Leave System - Testing & Validation Guide

**Version:** 1.0.0
**Last Updated:** November 11, 2025
**Status:** Production Ready

---

## Table of Contents

1. [Quick Start Testing](#quick-start-testing)
2. [Unit Testing](#unit-testing)
3. [Integration Testing](#integration-testing)
4. [API Testing](#api-testing)
5. [Database Testing](#database-testing)
6. [WhatsApp Integration Testing](#whatsapp-integration-testing)
7. [Email Integration Testing](#email-integration-testing)
8. [Performance Testing](#performance-testing)
9. [Security Testing](#security-testing)
10. [End-to-End Validation](#end-to-end-validation)
11. [Troubleshooting Test Failures](#troubleshooting-test-failures)

---

## Quick Start Testing

### 15-Minute Validation Test

```bash
# 1. Setup database
cd leave-system/database
./setup_database.sh --reset

# 2. Install dependencies
cd ..
pip3 install -r requirements.txt

# 3. Run all unit tests
pytest tests/ -v

# 4. Start API
python3 api_production.py &
API_PID=$!

# 5. Test health endpoint
curl http://localhost:8090/health

# 6. Test leave request
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can James Smith have overnight leave this Saturday?",
    "sender": "27603174174",
    "channel": "whatsapp"
  }'

# 7. Cleanup
kill $API_PID
```

**Expected Results:**
- ✅ All 110+ tests pass
- ✅ Health endpoint returns `{"status": "healthy"}`
- ✅ Leave request returns approval with date/time details

---

## Unit Testing

### Running All Tests

```bash
cd leave-system

# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_leave_parser.py -v

# Run specific test class
pytest tests/test_leave_processor.py::TestLeaveProcessor -v

# Run specific test
pytest tests/test_api.py::TestAPIEndpoints::test_health_endpoint -v
```

### Test Suite Breakdown

#### Parser Tests (50+ tests)

**File:** `tests/test_leave_parser.py`

**Coverage:**
- Student identifier extraction (admin numbers, names)
- Date parsing (relative dates: "this Saturday", "next weekend")
- Date parsing (absolute dates: "15 February", "2025-02-15")
- Leave type detection (overnight, Friday supper, day leave)
- Edge cases and error handling

**Run:**
```bash
pytest tests/test_leave_parser.py -v
```

**Expected Output:**
```
test_extract_admin_number ✓
test_extract_student_name ✓
test_parse_relative_dates ✓
test_parse_absolute_dates ✓
test_overnight_leave_detection ✓
test_friday_supper_detection ✓
... (50+ tests)
=================== 50 passed in 2.3s ===================
```

#### Processor Tests (40+ tests)

**File:** `tests/test_leave_processor.py`

**Coverage:**
- Parent authentication (WhatsApp, email)
- Student-parent linkage verification
- Leave eligibility checking (FR3)
- Balance management (overnight/supper leave)
- Closed weekend detection
- Restriction enforcement
- Special leave routing
- Housemaster functions

**Run:**
```bash
pytest tests/test_leave_processor.py -v
```

**Expected Output:**
```
test_parent_authentication ✓
test_student_parent_linkage ✓
test_leave_eligibility ✓
test_balance_checking ✓
test_closed_weekend_detection ✓
test_restriction_enforcement ✓
... (40+ tests)
=================== 40 passed in 3.1s ===================
```

#### API Tests (20+ tests)

**File:** `tests/test_api.py`

**Coverage:**
- Health endpoint
- Parent request processing
- Housemaster request processing
- Error handling
- Request validation

**Run:**
```bash
pytest tests/test_api.py -v
```

**Expected Output:**
```
test_health_endpoint ✓
test_process_parent_request ✓
test_process_housemaster_request ✓
test_invalid_request_handling ✓
... (20+ tests)
=================== 20 passed in 1.8s ===================
```

### Coverage Goals

- **Target:** >80% code coverage
- **Current:** Estimated 85%+ (parsers and processors fully covered)

**Generate Coverage Report:**
```bash
pytest tests/ --cov=processors --cov=models --cov-report=html
open htmlcov/index.html  # View in browser
```

---

## Integration Testing

### Database Integration Tests

Test the system with a real PostgreSQL database:

```bash
# 1. Setup test database
cd leave-system/database
./setup_database.sh --reset

# 2. Run integration tests
cd ..
python3 << 'EOF'
from tools.database_tools import DatabaseTools
from processors.leave_processor import LeaveProcessor
from models.leave_models import LeaveRequest

# Initialize with real database
tools = DatabaseTools()
processor = LeaveProcessor()
processor.tools = tools

# Test parent authentication
parent_id = tools.tool_parent_phone_check("27603174174")
print(f"✓ Parent authenticated: {parent_id}")

# Test student lookup
student = tools.tool_get_student_by_admin_number("12345")
print(f"✓ Student found: {student}")

# Test balance check
balances = tools.tool_check_leave_balance("student-uuid-here")
print(f"✓ Balances retrieved: {balances}")

# Test leave request processing
request = LeaveRequest(
    message="Can James Smith have overnight leave this Saturday?",
    sender_identifier="27603174174",
    channel="whatsapp"
)
response = processor.process_parent_request(request)
print(f"✓ Leave processed: {response.status}")
print(f"✓ Response: {response.response_message[:100]}...")

EOF
```

**Expected Results:**
- ✅ Parent authenticated successfully
- ✅ Student found with correct details
- ✅ Balances show 3 overnight, 3 supper
- ✅ Leave request approved with proper dates

### API + Database Integration

```bash
# 1. Start API with database tools
python3 api_production.py &
API_PID=$!
sleep 2

# 2. Test full request flow
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can student 12345 have Friday supper leave this week?",
    "sender": "27603174174",
    "channel": "whatsapp"
  }' | jq .

# 3. Verify in database
psql -U leave_user -d michaelhouse_leave -c \
  "SELECT * FROM leave_register ORDER BY created_at DESC LIMIT 1;"

# 4. Cleanup
kill $API_PID
```

**Expected Results:**
- ✅ API returns approval response
- ✅ Database has new leave record
- ✅ Balance decremented by 1

---

## API Testing

### Manual API Testing

#### Health Check

```bash
curl http://localhost:8090/health
```

**Expected:**
```json
{
  "status": "healthy",
  "timestamp": "2025-02-08T14:30:00",
  "database": "connected"
}
```

#### Parent Leave Request

```bash
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can James Smith have overnight leave this Saturday?",
    "sender": "27603174174",
    "channel": "whatsapp"
  }' | jq .
```

**Expected:**
```json
{
  "status": "approved",
  "response": "Thank you for submitting your request.\n\nI'm pleased to confirm that the exeat request for James Smith for Overnight leave has been approved.\n\nDates: Saturday 08 February 2025 at 14:00 to Sunday 09 February 2025 at 18:50\n\nRemaining overnight leave balance: 2",
  "leave_type": "overnight",
  "student_name": "James Smith"
}
```

#### Housemaster Query

```bash
curl -X POST http://localhost:8090/api/process_housemaster_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the balance for student 12345?",
    "sender": "hm.finningley@michaelhouse.org",
    "channel": "email"
  }' | jq .
```

**Expected:**
```json
{
  "status": "success",
  "response": "Leave Balance for Student 12345:\nOvernight Leave: 3 remaining\nFriday Supper Leave: 3 remaining"
}
```

### Automated API Test Script

```bash
#!/bin/bash
# save as test_api.sh

BASE_URL="http://localhost:8090"

echo "Testing API endpoints..."

# Test 1: Health check
echo -n "Test 1: Health check... "
HEALTH=$(curl -s $BASE_URL/health)
if echo "$HEALTH" | grep -q "healthy"; then
  echo "✓ PASSED"
else
  echo "✗ FAILED"
  exit 1
fi

# Test 2: Parent request
echo -n "Test 2: Parent leave request... "
RESPONSE=$(curl -s -X POST $BASE_URL/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can student 12345 have leave this Saturday?",
    "sender": "27603174174",
    "channel": "whatsapp"
  }')
if echo "$RESPONSE" | grep -q "approved"; then
  echo "✓ PASSED"
else
  echo "✗ FAILED"
  exit 1
fi

# Test 3: Housemaster query
echo -n "Test 3: Housemaster balance query... "
RESPONSE=$(curl -s -X POST $BASE_URL/api/process_housemaster_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "balance for 12345",
    "sender": "hm.finningley@michaelhouse.org",
    "channel": "email"
  }')
if echo "$RESPONSE" | grep -q "balance"; then
  echo "✓ PASSED"
else
  echo "✗ FAILED"
  exit 1
fi

echo "All API tests passed! ✓"
```

---

## Database Testing

### Schema Validation

```bash
# Connect to database
psql -U leave_user -d michaelhouse_leave

-- Verify tables exist
\dt

-- Expected output:
--  public | audit_log           | table | leave_user
--  public | closed_weekends     | table | leave_user
--  public | housemasters        | table | leave_user
--  public | leave_balances      | table | leave_user
--  public | leave_register      | table | leave_user
--  public | parents             | table | leave_user
--  public | restrictions        | table | leave_user
--  public | students            | table | leave_user
--  public | student_parents     | table | leave_user
--  public | term_config         | table | leave_user
--  public | whatsapp_numbers    | table | leave_user

-- Verify indexes
\di

-- Verify triggers
SELECT trigger_name, event_manipulation, event_object_table
FROM information_schema.triggers
WHERE trigger_schema = 'public';

-- Verify views
\dv
```

### Data Integrity Tests

```sql
-- Test 1: Parent-Student linkage
SELECT
  p.first_name || ' ' || p.last_name as parent_name,
  s.first_name || ' ' || s.last_name as student_name,
  sp.relationship
FROM parents p
JOIN student_parents sp ON p.id = sp.parent_id
JOIN students s ON s.id = sp.student_id
LIMIT 5;

-- Test 2: Leave balances initialized correctly
SELECT
  s.admin_number,
  s.first_name,
  lb.overnight_remaining,
  lb.friday_supper_remaining
FROM students s
JOIN leave_balances lb ON s.id = lb.student_id
WHERE lb.term = 'Term 1 2025';

-- Test 3: Closed weekends configured
SELECT block_letter, weekend_date, reason
FROM closed_weekends
WHERE weekend_date >= CURRENT_DATE
ORDER BY weekend_date;

-- Test 4: Audit log tracking
SELECT operation, table_name, changed_by, changed_at
FROM audit_log
ORDER BY changed_at DESC
LIMIT 10;
```

### Database Tool Function Tests

```bash
python3 << 'EOF'
from tools.database_tools import DatabaseTools

tools = DatabaseTools()

# Test 1: Parent authentication
print("Test 1: Parent phone check")
parent_id = tools.tool_parent_phone_check("27603174174")
assert parent_id is not None, "Parent not found!"
print(f"✓ Parent found: {parent_id}")

# Test 2: Student lookup by admin number
print("\nTest 2: Student lookup")
student = tools.tool_get_student_by_admin_number("12345")
assert student is not None, "Student not found!"
print(f"✓ Student found: {student['first_name']} {student['last_name']}")

# Test 3: Parent-student linkage
print("\nTest 3: Parent-student linkage")
is_linked = tools.tool_check_parent_student_linkage(parent_id, student['student_id'])
assert is_linked == True, "Linkage not found!"
print(f"✓ Linkage verified")

# Test 4: Balance check
print("\nTest 4: Balance check")
balances = tools.tool_check_leave_balance(student['student_id'])
assert balances is not None, "Balances not found!"
print(f"✓ Overnight: {balances['overnight_remaining']}, Supper: {balances['friday_supper_remaining']}")

# Test 5: Closed weekend check
print("\nTest 5: Closed weekend check")
from datetime import datetime, timedelta
next_saturday = datetime.now() + timedelta(days=(5 - datetime.now().weekday()))
is_closed = tools.tool_check_closed_weekend("E", next_saturday)
print(f"✓ Closed weekend check: {is_closed}")

print("\n✓ All database tool tests passed!")
EOF
```

---

## WhatsApp Integration Testing

### Prerequisites

1. Go WhatsApp bridge running
2. WhatsApp connected (QR scanned)
3. Flask API running
4. Test phone number registered as parent

### Testing Workflow

#### 1. Start Services

```bash
# Terminal 1: Start Flask API
cd leave-system
python3 api_production.py

# Terminal 2: Start WhatsApp bridge
cd ../whatsapp-bridge
export CGO_ENABLED=1
export LEAVE_API_URL=http://localhost:8090
go run main.go leave_integration.go
```

#### 2. Send Test Messages from WhatsApp

**Test Case 1: Basic Overnight Leave**
```
Send from registered parent phone:
"Can James Smith have overnight leave this Saturday?"

Expected response:
"Thank you for submitting your request.

I'm pleased to confirm that the exeat request for James Smith
for Overnight leave has been approved.

Dates: Saturday 08 February 2025 at 14:00 to
       Sunday 09 February 2025 at 18:50

Remaining overnight leave balance: 2"
```

**Test Case 2: Friday Supper Leave**
```
Send from registered parent phone:
"Can student 12345 have Friday supper leave this week?"

Expected response:
"Thank you for submitting your request.

I'm pleased to confirm that the exeat request for James Smith
for Friday Supper leave has been approved.

Dates: Friday 14 February 2025 at 17:30 to
       Friday 14 February 2025 at 21:00

Remaining Friday supper leave balance: 2"
```

**Test Case 3: Unauthenticated Parent**
```
Send from unregistered phone:
"Can John Doe have leave?"

Expected response:
"I'm sorry, but I was unable to verify your identity as a registered parent..."
```

**Test Case 4: Insufficient Balance**
```
Send from parent who has used all leave:
"Can James have overnight leave?"

Expected response:
"I regret to inform you that the exeat request cannot be approved.
Reason: Insufficient leave balance. Student has 0 overnight leave remaining."
```

#### 3. Monitor Logs

**Go Bridge Logs:**
```bash
# Watch for:
[DEBUG] Message received: content=Can James have leave
[DEBUG] Leave request detected - routing to Leave API
[DEBUG] Leave API response: {"status":"approved"...}
[DEBUG] Sent response to WhatsApp
```

**Flask API Logs:**
```bash
# Watch for:
INFO:werkzeug:127.0.0.1 - - [08/Feb/2025 14:30:00] "POST /api/process_parent_request HTTP/1.1" 200
INFO:leave_processor:Processing parent request from 27603174174
INFO:leave_processor:Leave request approved for James Smith
```

#### 4. Verify Database

```sql
-- Check leave was recorded
SELECT
  lr.leave_id,
  s.first_name || ' ' || s.last_name as student_name,
  lr.leave_type,
  lr.start_date,
  lr.end_date,
  lr.status
FROM leave_register lr
JOIN students s ON lr.student_id = s.id
ORDER BY lr.created_at DESC
LIMIT 5;

-- Check balance was decremented
SELECT
  s.admin_number,
  lb.overnight_remaining,
  lb.friday_supper_remaining
FROM students s
JOIN leave_balances lb ON s.id = lb.student_id
WHERE s.admin_number = '12345';
```

---

## Email Integration Testing

### Prerequisites

1. Email service configured in `.env`
2. IMAP/SMTP credentials set
3. Flask API running
4. Email monitoring service running

### Testing Workflow

#### 1. Start Services

```bash
# Terminal 1: Flask API
cd leave-system
python3 api_production.py

# Terminal 2: Email monitoring service
cd email-bridge
python3 email_service.py
```

#### 2. Send Test Emails

**Test Case 1: Parent Leave Request via Email**

```
From: parent@example.com
To: leave@michaelhouse.org
Subject: Leave Request

Hi, can James Smith (12345) have overnight leave this Saturday?

Thanks,
John Smith
```

**Expected:**
- Email service logs: "Processing email from parent@example.com"
- Email service logs: "Processing as parent request"
- Email service logs: "✓ Email sent to parent@example.com"
- Automated reply received within 2 seconds

**Test Case 2: Housemaster Balance Query**

```
From: hm.finningley@michaelhouse.org
To: leave@michaelhouse.org
Subject: Student Balance

What is the balance for student 12345?
```

**Expected:**
- Email service logs: "Processing email from hm.finningley@michaelhouse.org"
- Email service logs: "Processing as housemaster request"
- Automated reply with balance information

**Test Case 3: Housemaster Cancellation**

```
From: hm.finningley@michaelhouse.org
To: leave@michaelhouse.org
Subject: Cancel Leave

Please cancel leave LEAVE123456
```

**Expected:**
- Leave cancelled in database
- Balance restored
- Confirmation email sent

#### 3. Monitor Email Service Logs

```bash
# Watch logs
tail -f /var/log/leave-email-service.log

# Expected output:
Checking for new emails...
Found 1 unseen emails
Processing email from parent@example.com: Leave Request...
Processing as parent request
✓ Email sent to parent@example.com
✓ Processed email: status=approved
```

#### 4. Verify Email Delivery

- Check inbox for automated responses
- Verify "Re:" subject prefix
- Verify response content matches request
- Check email marked as read in inbox

---

## Performance Testing

### Response Time Testing

```bash
#!/bin/bash
# save as performance_test.sh

echo "Performance Testing - Response Times"
echo "===================================="

# Test API response time
for i in {1..10}; do
  START=$(date +%s%N)
  curl -s -X POST http://localhost:8090/api/process_parent_request \
    -H "Content-Type: application/json" \
    -d '{
      "message": "Can student 12345 have leave this Saturday?",
      "sender": "27603174174",
      "channel": "whatsapp"
    }' > /dev/null
  END=$(date +%s%N)
  DURATION=$((($END - $START) / 1000000))
  echo "Request $i: ${DURATION}ms"
done
```

**Expected:**
- Average response time: < 500ms
- 90th percentile: < 800ms
- 99th percentile: < 1000ms

### Concurrent Request Testing

```bash
# Install Apache Bench
# sudo apt-get install apache2-utils

# Test with 100 concurrent requests
ab -n 100 -c 10 -p request.json -T application/json \
  http://localhost:8090/api/process_parent_request

# Where request.json contains:
# {
#   "message": "Can student 12345 have leave this Saturday?",
#   "sender": "27603174174",
#   "channel": "whatsapp"
# }
```

**Expected:**
- Requests per second: > 20
- Failed requests: 0
- Mean time per request: < 500ms

### Database Query Performance

```sql
-- Enable query timing
\timing

-- Test 1: Student lookup (should be < 10ms)
SELECT * FROM students WHERE admin_number = '12345';

-- Test 2: Leave balance check (should be < 20ms)
SELECT * FROM leave_balances
WHERE student_id = (SELECT id FROM students WHERE admin_number = '12345')
AND term = 'Term 1 2025';

-- Test 3: Leave history (should be < 50ms)
SELECT * FROM leave_register
WHERE student_id = (SELECT id FROM students WHERE admin_number = '12345')
ORDER BY start_date DESC
LIMIT 10;

-- Test 4: Complex join (should be < 100ms)
SELECT
  s.admin_number,
  s.first_name || ' ' || s.last_name as student_name,
  p.first_name || ' ' || p.last_name as parent_name,
  lr.leave_type,
  lr.start_date,
  lr.end_date
FROM students s
JOIN student_parents sp ON s.id = sp.student_id
JOIN parents p ON p.id = sp.parent_id
JOIN leave_register lr ON lr.student_id = s.id
WHERE s.admin_number = '12345'
ORDER BY lr.start_date DESC
LIMIT 5;
```

---

## Security Testing

### Input Validation Testing

```bash
# Test 1: SQL Injection attempt
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can student '\'' OR '\''1'\''='\''1 have leave?",
    "sender": "27603174174",
    "channel": "whatsapp"
  }'

# Expected: Handled safely, no database error

# Test 2: XSS attempt
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "<script>alert(\"XSS\")</script>",
    "sender": "27603174174",
    "channel": "whatsapp"
  }'

# Expected: Script tags escaped/sanitized

# Test 3: Oversized payload
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$(python3 -c 'print(\"A\" * 100000)')\"}"

# Expected: Request rejected or handled gracefully
```

### Authentication Testing

```bash
# Test 1: Unregistered phone number
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can student 12345 have leave?",
    "sender": "27699999999",
    "channel": "whatsapp"
  }'

# Expected: Authentication failure response

# Test 2: Invalid parent-student linkage
# (Phone registered to different student)
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can student 99999 have leave?",
    "sender": "27603174174",
    "channel": "whatsapp"
  }'

# Expected: Linkage validation failure
```

### Database Security

```sql
-- Test 1: Verify encryption (should fail without key)
-- From command line without key:
sqlite3 whatsapp-bridge/store/messages.db "SELECT * FROM messages;"
-- Expected: "file is encrypted or is not a database"

-- Test 2: Verify row-level security (if implemented)
SET ROLE leave_user;
SELECT * FROM parents WHERE id = 'some-uuid';
-- Expected: Only returns data user has access to

-- Test 3: Verify audit logging
SELECT * FROM audit_log
WHERE operation = 'UPDATE'
AND table_name = 'leave_register'
ORDER BY changed_at DESC LIMIT 5;
-- Expected: All updates logged with timestamp and user
```

---

## End-to-End Validation

### Complete User Journey Test

#### Scenario 1: Successful Leave Request (WhatsApp)

**Setup:**
- Parent with phone 27603174174
- Student James Smith (12345)
- 3 overnight leave remaining
- Not a closed weekend

**Steps:**

1. **Parent sends WhatsApp message**
   ```
   "Can James have overnight leave this Saturday?"
   ```

2. **System processes request**
   - Bridge detects leave keywords
   - Routes to Flask API
   - Parser extracts: student="James", leave_type="overnight", date="this Saturday"
   - Processor authenticates parent via phone
   - Processor checks student-parent linkage
   - Processor checks leave balance (3 remaining)
   - Processor checks closed weekends (not closed)
   - Processor checks restrictions (none)
   - Processor approves and records leave
   - Processor decrements balance to 2

3. **Parent receives response**
   ```
   "Thank you for submitting your request.

   I'm pleased to confirm that the exeat request for James Smith
   for Overnight leave has been approved.

   Dates: Saturday 08 February 2025 at 14:00 to
          Sunday 09 February 2025 at 18:50

   Remaining overnight leave balance: 2"
   ```

4. **Verification**
   ```sql
   -- Check leave recorded
   SELECT * FROM leave_register WHERE student_id =
     (SELECT id FROM students WHERE admin_number = '12345')
   ORDER BY created_at DESC LIMIT 1;

   -- Check balance decremented
   SELECT overnight_remaining FROM leave_balances WHERE student_id =
     (SELECT id FROM students WHERE admin_number = '12345');
   ```

**Expected Results:**
- ✅ Leave recorded in database
- ✅ Balance shows 2 remaining
- ✅ Audit log entry created
- ✅ Parent receives confirmation < 2 seconds

#### Scenario 2: Housemaster Query (Email)

**Setup:**
- Housemaster email: hm.finningley@michaelhouse.org
- Student 12345 has 2 overnight, 3 supper remaining

**Steps:**

1. **HM sends email**
   ```
   From: hm.finningley@michaelhouse.org
   Subject: Balance Query
   Body: What is the balance for student 12345?
   ```

2. **System processes email**
   - Email service detects new email
   - Identifies as HM request (email prefix "hm.")
   - Routes to processor as HM query
   - Processor looks up balances

3. **HM receives response**
   ```
   From: leave@michaelhouse.org
   Subject: Re: Balance Query

   Leave Balance for Student 12345:
   Overnight Leave: 2 remaining
   Friday Supper Leave: 3 remaining
   ```

**Expected Results:**
- ✅ Email processed within 60 seconds
- ✅ Correct balance information returned
- ✅ No database changes made (query only)

#### Scenario 3: Rejected Request (Insufficient Balance)

**Setup:**
- Parent 27603174174
- Student 12345 has 0 overnight leave remaining

**Steps:**

1. **Parent requests leave**
   ```
   "Can James have overnight leave this Saturday?"
   ```

2. **System processes and rejects**
   - Authenticates parent ✓
   - Checks linkage ✓
   - Checks balance → 0 remaining
   - Request denied

3. **Parent receives rejection**
   ```
   "I regret to inform you that the exeat request cannot be approved.

   Reason: Insufficient leave balance. James Smith has 0 overnight
   leave remaining for this term."
   ```

**Expected Results:**
- ✅ No leave recorded
- ✅ Balance unchanged
- ✅ Clear rejection reason provided

---

## Troubleshooting Test Failures

### Common Test Failures

#### 1. Database Connection Failures

**Symptom:**
```
psycopg2.OperationalError: could not connect to server
```

**Solutions:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify database exists
psql -U postgres -l | grep michaelhouse_leave

# Check credentials
psql -U leave_user -d michaelhouse_leave -c "SELECT 1;"

# Reset database
cd leave-system/database
./setup_database.sh --reset
```

#### 2. Import Errors in Tests

**Symptom:**
```
ModuleNotFoundError: No module named 'processors'
```

**Solutions:**
```bash
# Ensure you're in correct directory
cd leave-system

# Check PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Install in development mode
pip3 install -e .
```

#### 3. API Not Responding

**Symptom:**
```
curl: (7) Failed to connect to localhost port 8090
```

**Solutions:**
```bash
# Check API is running
ps aux | grep api_production

# Check port is free
lsof -i :8090

# Restart API
killall python3
python3 api_production.py &
```

#### 4. Test Database Pollution

**Symptom:**
```
Tests fail due to existing data
```

**Solutions:**
```bash
# Reset test database before tests
cd leave-system/database
./setup_database.sh --reset

# Or use pytest fixtures with database cleanup
pytest tests/ --clean-db
```

#### 5. WhatsApp Bridge Not Routing

**Symptom:**
```
Messages sent but no response received
```

**Solutions:**
```bash
# Check LEAVE_API_URL is set
echo $LEAVE_API_URL

# Set if missing
export LEAVE_API_URL=http://localhost:8090

# Check bridge logs for routing
# Should see: "[DEBUG] Leave request detected - routing to Leave API"

# Verify API is accessible from bridge
curl http://localhost:8090/health
```

#### 6. Email Service Not Processing

**Symptom:**
```
Emails sent but not processed
```

**Solutions:**
```bash
# Check email credentials
python3 << 'EOF'
from dotenv import load_dotenv
import os
load_dotenv()
print("Email:", os.getenv('LEAVE_EMAIL'))
print("Password set:", bool(os.getenv('LEAVE_EMAIL_PASSWORD')))
EOF

# Test IMAP connection
python3 << 'EOF'
import imaplib
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login('your-email', 'your-password')
print("✓ IMAP connection successful")
mail.logout()
EOF

# Check email service logs
tail -f /var/log/leave-email-service.log
```

---

## Test Automation

### Pre-Commit Test Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash

echo "Running pre-commit tests..."

# Run unit tests
cd leave-system
pytest tests/ -v --tb=short

if [ $? -ne 0 ]; then
  echo "❌ Tests failed. Commit aborted."
  exit 1
fi

echo "✓ All tests passed"
exit 0
```

```bash
chmod +x .git/hooks/pre-commit
```

### Continuous Integration Script

Create `test_ci.sh`:

```bash
#!/bin/bash
set -e

echo "CI Test Pipeline"
echo "================"

# 1. Setup
echo "1. Setting up test environment..."
cd leave-system/database
./setup_database.sh --reset

# 2. Install dependencies
echo "2. Installing dependencies..."
cd ..
pip3 install -r requirements.txt

# 3. Run unit tests
echo "3. Running unit tests..."
pytest tests/ -v --cov=. --cov-report=term

# 4. Start API
echo "4. Starting API..."
python3 api_production.py &
API_PID=$!
sleep 2

# 5. Run API tests
echo "5. Running API tests..."
curl -f http://localhost:8090/health || exit 1

# 6. Cleanup
echo "6. Cleaning up..."
kill $API_PID

echo "✓ CI Pipeline Complete"
```

---

## Validation Checklist

### Pre-Deployment Validation

- [ ] All 110+ unit tests pass
- [ ] Database schema created successfully
- [ ] All indexes and triggers created
- [ ] Seed data loaded correctly
- [ ] API health endpoint responds
- [ ] Parent authentication works
- [ ] Student lookup works
- [ ] Leave balance checking works
- [ ] Leave processing and approval works
- [ ] Balance decrementation works
- [ ] Closed weekend detection works
- [ ] Restriction enforcement works
- [ ] Housemaster queries work
- [ ] WhatsApp integration routes correctly
- [ ] Email monitoring processes emails
- [ ] Email responses sent correctly
- [ ] Performance < 500ms response time
- [ ] No SQL injection vulnerabilities
- [ ] Authentication required for all requests
- [ ] Audit logging captures all changes

### Production Validation

After deployment:

- [ ] Services start automatically (systemd)
- [ ] Logs rotate properly
- [ ] Database backups configured
- [ ] Monitoring alerts configured
- [ ] SSL/TLS configured (if applicable)
- [ ] Firewall rules configured
- [ ] Rate limiting enabled
- [ ] Error tracking enabled
- [ ] Send real test message via WhatsApp
- [ ] Send real test email
- [ ] Verify response received
- [ ] Check database for correct records
- [ ] Monitor logs for 24 hours
- [ ] Performance testing under load

---

## Summary

This testing guide provides comprehensive coverage for validating the Michaelhouse Leave System:

- **Unit Tests:** 110+ tests covering all core logic
- **Integration Tests:** Database, API, and service integration
- **End-to-End Tests:** Complete user journeys
- **Performance Tests:** Response time and concurrency
- **Security Tests:** Input validation and authentication

**Estimated Testing Time:**
- Quick validation: 15 minutes
- Full unit test suite: 5 minutes
- Integration testing: 30 minutes
- End-to-end validation: 1 hour
- Performance testing: 30 minutes
- **Total comprehensive testing: ~2.5 hours**

For production deployment, allocate **1-2 days for complete testing and validation** including real-world usage scenarios.

---

**Next Steps:**
1. Run quick validation test (15 min)
2. Review any failures and fix
3. Run full test suite
4. Perform end-to-end validation
5. Deploy to staging for user acceptance testing

**Status:** 🟢 Testing infrastructure complete and ready
