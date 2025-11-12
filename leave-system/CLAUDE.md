# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Michaelhouse Leave System** - AI-powered student leave (exeat) request system for boarding schools that processes parent requests via WhatsApp and Email. Features automated approval workflows, balance tracking (3 overnight + 3 supper leaves per term), and special approval routing.

## Quick Start Commands

### Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run development server
python3 api.py
# API runs on http://localhost:8090

# Run demo (placeholder data)
python3 demo.py
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_leave_processor.py

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test function
pytest tests/test_leave_processor.py::test_approve_overnight_leave -v
```

### Production Deployment

```bash
# Using gunicorn (recommended)
gunicorn -w 4 -b 0.0.0.0:8090 api:app

# Or direct Flask (development only)
python3 api.py
```

## Architecture

### High-Level Request Flow

```
Parent (WhatsApp/Email)
    → API Endpoint (/api/conversation or /api/process_parent_request)
    → ConversationAgent (Claude AI for NLP)
    → LeaveProcessor (business logic)
    → Tools (GoogleSheets/PostgreSQL/Placeholder)
    → Response back to parent
```

### Core Components

**API Layer** (`api.py`):
- Flask REST API with 3 main endpoints
- Endpoint selection: `/api/conversation` (AI agent) vs `/api/process_parent_request` (direct)
- Backend configuration: Google Sheets (OAuth or Service Account) or PostgreSQL
- Environment-driven tool initialization

**Agent System** (`agents/`):
- `conversation_agent.py`: Claude AI integration for natural language processing
- `agent_logger.py`: Structured logging (received, analysis, decision, response)
- `context.md`: Agent personality/instructions
- Handles incomplete requests, asks clarifying questions, extracts intent

**Leave Processing** (`processors/`):
- `leave_processor.py`: Sequential decision protocol (FR1-FR9 requirements)
  - Authentication → Student linkage → Date validity → Balance check → Restrictions → Approval/Rejection
- `leave_parser.py`: NLP parser for extracting student, dates, leave type from text

**Data Models** (`models/`):
- `leave_models.py`: Core data structures
  - LeaveType enum (OVERNIGHT, FRIDAY_SUPPER, DAY_LEAVE, SPECIAL)
  - LeaveRequest, StudentInfo, ParentInfo, HousemasterInfo

**Tool Implementations** (`tools/`):
- `placeholder_tools.py`: Demo mode with hardcoded data
- `database_tools.py`: PostgreSQL backend (production)
- `google_sheets_simple.py`: Personal Google account OAuth (simplified setup)
- `google_sheets_tools.py`: Service account integration (enterprise)

**Email Bridge** (`email-bridge/`):
- `email_handler.py`: IMAP/SMTP integration
- Polls inbox, processes leave emails, sends responses
- Email-to-LeaveProcessor integration

### Backend Selection Logic

System auto-selects backend based on environment variables:

1. `USE_GOOGLE_SHEETS=true` + `USE_SIMPLE_OAUTH=true` → Personal Google account (OAuth)
2. `USE_GOOGLE_SHEETS=true` + `USE_SIMPLE_OAUTH=false` → Service account
3. `USE_GOOGLE_SHEETS=false` → PostgreSQL database
4. Fallback → Placeholder tools (demo mode)

See `api.py:30-60` for initialization logic.

## Key Business Logic

### Leave Types & Auto-Approval Rules

- **Overnight**: Saturday post-sport to Sunday 18:50 (3/term, auto-approved with balance)
- **Friday Supper**: Friday 17:00-21:00 (3/term, auto-approved with balance)
- **Day Leave**: Saturday/Sunday return before 17:00 (unlimited, always auto-approved)
- **Special**: Any other time OR closed weekends (requires Housemaster approval)

### Sequential Decision Flow

Processor executes in strict order (see `leave_processor.py:144-234`):

1. **Authentication** (FR2): Verify parent via phone/email
2. **Student Linkage** (FR2.3): Confirm student belongs to parent
3. **Parse Request** (FR1.2): Extract student, dates, type
4. **Date Validity** (FR3.2): Check against term dates
5. **Closed Weekend Check** (FR3.3): E/D block restrictions → triggers special leave
6. **Day Leave Fast-Track** (FR3.6): Auto-approve immediately (unlimited)
7. **Restriction Check** (FR3.7): Check if student blocked from leave
8. **Balance Check** (FR3.4-3.5): Verify sufficient leave count
9. **Final Decision**: Approve, Reject, or Route to Special

### Closed Weekends

E Block and D Block students cannot take overnight/supper leave on:
- First weekend of term
- Weekend immediately after half term

These automatically route to **Special Leave** for Housemaster approval (see `leave_processor.py:314-368`).

## API Endpoints

### POST /api/conversation (Recommended)

Conversational AI agent - handles incomplete requests, asks clarifying questions.

```json
{
  "message": "Can my son have leave this weekend?",
  "sender": "27603174174",
  "channel": "whatsapp",
  "chat_id": "unique_chat_id",
  "conversation_history": []  // optional
}
```

Returns:
```json
{
  "response": "Generated response",
  "metadata": {
    "intent": "leave_request",
    "complete": false,
    "timestamp": "2025-01-12T10:30:45"
  }
}
```

### POST /api/process_parent_request (Direct)

Direct processing - requires complete request in single message.

```json
{
  "message": "Can James have overnight leave this Saturday?",
  "sender": "27603174174",
  "channel": "whatsapp"
}
```

Returns:
```json
{
  "status": "approved|rejected|special_pending|error",
  "message": "Response text to send back",
  "reason": "machine_readable_reason"  // if rejected
}
```

### POST /api/process_housemaster_request

Housemaster queries, cancellations, restrictions (FR9).

```json
{
  "message": "What is the balance for student 12345?",
  "sender": "hm.finningley@michaelhouse.org",
  "channel": "email"
}
```

## Tool System

All data access goes through tool interfaces. Current implementations:

### Placeholder Tools (Demo)
- Hardcoded student/parent data
- In-memory leave balances
- No persistence
- Use for testing/demos

### Google Sheets (Testing/Small Scale)
- Spreadsheet as database
- Two auth modes: Personal OAuth (simple) or Service Account (enterprise)
- Good for testing without database setup
- See `GOOGLE_SHEETS_SIMPLE_SETUP.md` and `GOOGLE_SHEETS_SETUP.md`

### PostgreSQL (Production)
- Full database backend
- Schema in `database_tools.py`
- Requires database setup (connection via .env)

### Tool Interface Methods

All tools implement these methods (see `placeholder_tools.py` for signatures):

- `tool_parent_phone_check(phone)` → parent_auth_id
- `tool_parent_email_check(email)` → parent_auth_id
- `tool_student_parent_linkage(parent_id, student_identifier)` → student_record
- `tool_leave_balance_check(admin_number, leave_type)` → int
- `tool_date_validity_check(block, start_date, end_date)` → {isValid, reason}
- `tool_restriction_check(admin_number, start_date, end_date)` → bool
- `tool_leave_update(...)` → bool
- `tool_leave_query_hm(hm_id, admin_number, query_type)` → dict
- `tool_hm_auth_house_check(identifier)` → {hmID, assignedHouse}
- `tool_restriction_update(...)` → bool
- `tool_term_config_read(config_key)` → dict
- `tool_term_config_write(config_key, config_data)` → bool

## Conversational Agent

### Claude AI Integration

Agent uses Anthropic Claude (`conversation_agent.py:284`):
- Model: `claude-3-5-sonnet-20241022`
- System prompt: Loaded from `agents/context.md`
- Conversation history: Last 10 messages for context
- Fallback: Simple rule-based responses if API key missing

### Message Analysis

Agent analyzes messages to determine (`conversation_agent.py:163-224`):
- **Intent**: leave_request, balance_query, question, unknown
- **Completeness**: has_all_info (bool)
- **Missing Fields**: student_identifier, dates, leave_type
- **Decision**: Direct processing vs conversational response

### Agent Logging

Structured logs saved to `logs/agent-logs/` (see `agent_logger.py`):
- **Received Message**: Timestamp, sender, channel, content
- **Analysis**: Intent, extracted info, missing fields
- **Decision**: Action taken, reasoning
- **Response**: Generated response, logic used

## Testing

Test files use pytest fixtures (see `tests/conftest.py`):

- `test_leave_parser.py`: Natural language parsing tests
- `test_leave_processor.py`: Business logic and decision flow tests
- `test_api.py`: API endpoint integration tests

Run specific scenarios:
```bash
# Test overnight approval
pytest tests/test_leave_processor.py::test_approve_overnight_leave -v

# Test closed weekend routing
pytest tests/test_leave_processor.py::test_route_closed_weekend_to_special -v

# Test balance rejection
pytest tests/test_leave_processor.py::test_reject_insufficient_balance -v
```

## Configuration Files

- `.env`: Environment configuration (copy from `.env.example`)
- `agents/context.md`: Agent personality/instructions
- `requirements.txt`: Python dependencies
- `GOOGLE_SHEETS_SIMPLE_SETUP.md`: OAuth setup guide (personal account)
- `GOOGLE_SHEETS_SETUP.md`: Service account setup guide

## Production Deployment Checklist

1. **Replace Placeholder Tools**:
   - Implement `database_tools.py` with real database
   - Or configure Google Sheets with service account

2. **Configure Environment**:
   - Set `ANTHROPIC_API_KEY` for AI agent
   - Set database credentials (PostgreSQL) or Google Sheets credentials
   - Configure email bridge (IMAP/SMTP) if using email channel

3. **Set Up Term Configuration**:
   - Configure term dates via `tool_term_config_write`
   - Define closed weekends for E/D blocks

4. **Security**:
   - Use HTTPS/TLS for API
   - Secure environment variables
   - Set up proper authentication for API endpoints

5. **Monitoring**:
   - Enable structured logging
   - Monitor `logs/agent-logs/` for agent decisions
   - Track approval/rejection rates
   - Alert on errors

## Extending the System

### Add New Leave Type

1. Add to `LeaveType` enum in `models/leave_models.py`
2. Update parser indicators in `leave_parser.py`
3. Add balance check logic in `leave_processor.py:207-228`
4. Update all tool implementations

### Add New Communication Channel

1. Create bridge handler (e.g., `sms-bridge/sms_handler.py`)
2. Call `processor.process_parent_request(channel='sms')`
3. Send response via channel

### Custom Business Rules

Modify `_process_leave_eligibility()` in `leave_processor.py:144` to add:
- Grade-specific rules
- House-specific restrictions
- Sport/activity exemptions
- Academic performance criteria

## Common Issues

### "ANTHROPIC_API_KEY not set"
- Agent falls back to simple rule-based responses
- Set key in `.env` for full AI capabilities

### "No backend configured"
- System defaults to placeholder tools
- Set `USE_GOOGLE_SHEETS=true` or configure PostgreSQL

### Google Sheets Authentication
- Simple OAuth: Opens browser once, saves token to `token.pickle`
- Service Account: Requires `GOOGLE_SHEETS_CREDENTIALS_PATH` and sheet sharing
- See setup guides for detailed instructions

### Tests Failing
- Ensure placeholder tools are used for tests (default in conftest.py)
- Check test fixtures in `tests/conftest.py`

## Important Code Locations

- Main business logic: `processors/leave_processor.py:144-234` (eligibility checks)
- AI agent integration: `agents/conversation_agent.py:226-295` (Claude API)
- Backend initialization: `api.py:30-64` (tool selection)
- Tool interface: `tools/placeholder_tools.py` (method signatures)
- Date parsing: `processors/leave_parser.py:50-150` (NLP extraction)
