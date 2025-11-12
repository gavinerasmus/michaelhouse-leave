# Michaelhouse Leave System

AI-Powered Student Leave Application System for Boarding Schools

## Overview

This system automates the processing of student leave (exeat) requests submitted by parents via **WhatsApp** or **Email**. It implements sophisticated business rules, authentication, balance management, and special approval workflows.

## Features

✅ **Dual-Channel Support**: WhatsApp and Email
✅ **Parent Authentication**: Automatic verification via phone/email
✅ **Student Linkage**: Confirms student-parent relationships
✅ **Leave Types**: Overnight, Friday Supper, Day Leave, Special
✅ **Balance Management**: Tracks 3 overnight + 3 supper leaves per term
✅ **Closed Weekends**: Automatic routing to special approval for E/D block
✅ **Restrictions**: Housemaster can block students from leave
✅ **Cancellations**: Housemasters can cancel with balance refund
✅ **Guard Integration**: Mobile app ready (FR8 - separate Flutter app)

## Architecture

```
leave-system/
├── tools/
│   └── placeholder_tools.py      # All tool call implementations
├── models/
│   └── leave_models.py            # Data models (Student, Leave, etc.)
├── processors/
│   ├── leave_parser.py            # Natural language request parser
│   └── leave_processor.py         # Core business logic (FR1-FR9)
├── email-bridge/
│   └── email_handler.py           # Email communication handler
├── __init__.py
├── demo.py                        # Demonstration script
└── README.md                      # This file
```

## Quick Start

### Run the Demo

```bash
cd leave-system
python3 demo.py
```

This will demonstrate all major workflows with placeholder data.

### Integration Example

```python
from leave_system import LeaveProcessor

# Initialize processor (single instance for all channels)
processor = LeaveProcessor()

# Process WhatsApp request
result = processor.process_parent_request(
    message_text="Can James have overnight leave this Saturday?",
    sender_identifier="27603174174",
    channel='whatsapp'
)

# Process Email request
result = processor.process_parent_request(
    message_text="Request leave for Michael Doe on 14th Feb",
    sender_identifier="parent@example.com",
    channel='email'
)

# Process Housemaster request
result = processor.process_housemaster_request(
    message_text="What is the balance for student 12345?",
    sender_identifier="hm.finningley@michaelhouse.org",
    channel='email'
)

print(result['status'])  # 'approved', 'rejected', 'special_pending', etc.
print(result['message']) # Response to send back
```

## Leave Types & Rules

| Leave Type | Definition | Limit | Auto-Approve |
|------------|-----------|-------|--------------|
| **Overnight** | Saturday post-sport to Sunday 18:50 | 3 per term | Yes (if balance available) |
| **Friday Supper** | Friday 17:00 to 21:00 | 3 per term | Yes (if balance available) |
| **Day Leave** | Saturday/Sunday, return before 17:00 | Unlimited | Yes (always) |
| **Special** | Any other time or closed weekend | N/A | No (requires Housemaster) |

### Closed Weekends

E Block and D Block students cannot take leave on:
- First weekend of term
- Weekend immediately after half term

These automatically route to **Special Leave** for Housemaster approval.

## Tool Calls (FR Requirements)

The system uses these tool calls (currently placeholders):

### Authentication
- `Tool_Parent_Phone_Check` - Verify parent by phone
- `Tool_Parent_Email_Check` - Verify parent by email
- `Tool_HM_Auth_House_Check` - Authenticate Housemaster

### Student Data
- `Tool_Student_Parent_Linkage` - Verify student belongs to parent
- `Tool_Leave_Balance_Check` - Check remaining leave count
- `Tool_Leave_Query_HM` - Query leave history/balance (HM only)

### Validation
- `Tool_Date_Validity_Check` - Check if dates are permissible
- `Tool_Restriction_Check` - Check if student is restricted

### Updates
- `Tool_Leave_Update` - Register leave, update balance, log departure, cancel
- `Tool_Restriction_Update` - Set/clear student restrictions

### Configuration
- `Tool_Term_Config_Read/Write` - Manage term dates and closed weekends

## Processing Flow (Sequential)

For **Parent Requests**:

1. **Authentication** (FR2)
   - Verify parent via phone/email
   - ❌ Reject if authentication fails

2. **Student Linkage** (FR2.3)
   - Confirm student belongs to parent
   - ❌ Reject if linkage fails

3. **Parse Request** (FR1.2)
   - Extract student, dates, leave type
   - ❌ Error if parsing fails

4. **Date Validity** (FR3.2)
   - Check against term dates
   - ❌ Reject if invalid or ➡️ Special Leave if closed weekend

5. **Balance Check** (FR3.4, FR3.5)
   - Verify sufficient leave balance
   - ✅ Auto-approve Day Leave (unlimited)
   - ❌ Reject if insufficient balance

6. **Restriction Check** (FR3.7)
   - Check if student is restricted
   - ❌ Reject if restricted

7. **Final Approval** (FR5)
   - Register leave
   - Deduct balance
   - ✅ Notify parent

For **Housemaster Requests** (FR9):

- Query student leave balance
- Query leave history
- Cancel approved leave (with refund)
- Set leave restrictions

## WhatsApp Integration

The WhatsApp bridge already exists in this project. To integrate:

```go
// In whatsapp-bridge/main.go - handleMessage()

// After storing message, check if it's a leave request
if isLeaveRequest(content) {
    // Call Python leave processor via HTTP or direct exec
    result := processLeaveRequest(content, sender, "whatsapp")

    // Send response back via WhatsApp
    sendWhatsAppMessage(client, chatJID, result.Message, "")
}
```

Or use the Go → Python bridge via subprocess or HTTP API.

## Email Integration

Use the `EmailLeaveHandler` class:

```python
from email_bridge.email_handler import EmailBridge, EmailLeaveHandler

# Configure email bridge
bridge = EmailBridge(
    imap_server="imap.gmail.com",
    smtp_server="smtp.gmail.com",
    email_address="leave@michaelhouse.org",
    password="app-specific-password"
)

# Create handler
handler = EmailLeaveHandler(bridge)

# Run in loop or as scheduled job
while True:
    handler.process_incoming_emails()
    time.sleep(60)  # Check every minute
```

## Production Deployment Checklist

### Replace Placeholder Tools

- [ ] Implement actual database connections (PostgreSQL/MySQL)
- [ ] Connect to student information system
- [ ] Integrate parent contact database
- [ ] Set up real email service (Gmail API, SendGrid, etc.)
- [ ] Configure term dates and closed weekends

### Add Guard App Support

- [ ] Build Flutter mobile app (FR8)
- [ ] Implement `Tool_Leave_Lookup` with real data
- [ ] Add departure logging
- [ ] Optional: Driver ID capture (NFR4.1)

### Security & Testing

- [ ] Encrypt sensitive data at rest
- [ ] Use TLS for all communications
- [ ] Add logging and audit trails
- [ ] Write unit tests for each tool
- [ ] Write integration tests for workflows
- [ ] Load test with realistic traffic

### Monitoring

- [ ] Set up error alerting
- [ ] Track approval/rejection rates
- [ ] Monitor response times (NFR4.2: < 30 seconds)
- [ ] Dashboard for admin visibility

## Configuration

### Term Dates (FR7)

Update via `Tool_Term_Config_Write`:

```python
tools.tool_term_config_write('term_dates', {
    'term1': {'start': '2025-01-15', 'end': '2025-03-28'},
    'term2': {'start': '2025-04-22', 'end': '2025-06-27'},
    'term3': {'start': '2025-07-22', 'end': '2025-09-26'},
    'term4': {'start': '2025-10-07', 'end': '2025-12-05'}
})
```

### Closed Weekends

Configure blocked weekends for E/D blocks.

## Testing

Run the demo to see all scenarios:

```bash
python3 demo.py
```

Scenarios covered:
1. ✅ Approved overnight leave
2. ✅ Approved Friday supper leave
3. ⚠️ Special leave (closed weekend)
4. ❌ Rejected (insufficient balance)
5. ℹ️ Housemaster balance query
6. 🔴 Housemaster cancellation
7. ✅ Day leave (unlimited)

## API Response Format

All processing functions return:

```python
{
    'status': 'approved' | 'rejected' | 'special_pending' | 'error',
    'message': 'Human-readable response to send to parent/HM',
    'reason': 'machine-readable rejection reason (if rejected)',
    'leave_request': LeaveRequest object (if applicable)
}
```

## Extending the System

### Add New Leave Type

1. Add to `LeaveType` enum in `models/leave_models.py`
2. Update parser indicators in `leave_parser.py`
3. Add balance check logic in `leave_processor.py`
4. Update tool implementations

### Add New Channel (e.g., SMS)

1. Create `sms-bridge/sms_handler.py`
2. Call `LeaveProcessor.process_parent_request()` with `channel='sms'`
3. Send response via SMS gateway

### Custom Business Rules

Modify `_process_leave_eligibility()` in `leave_processor.py` to add:
- Grade-specific rules
- House-specific rules
- Sport/activity exemptions
- Academic performance criteria

## Support & Documentation

- **Requirements**: See `requirements/michaelhouse-leave-requirements.md`
- **Tool Specs**: See FR section in requirements document
- **Agent Instructions**: See `agents/global-context.md`

## License

Proprietary - Michaelhouse

## Contact

For questions about this system, contact the development team.

---

**Status**: ✅ Core functionality complete with placeholder tools
**Next**: Replace placeholders with actual database/email integration
