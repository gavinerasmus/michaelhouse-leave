# Clean Architecture - Leave Management System

## 🎯 Architecture Principle

**Communication channels are dumb pipes. ALL business logic lives in the Leave System.**

## 📊 Architecture Diagram

```
┌─────────────────┐         ┌─────────────────┐
│  WhatsApp User  │         │   Email User    │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │ Messages                  │ Emails
         ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│ WhatsApp Bridge │         │  Email Bridge   │
│   (Go - Simple) │         │ (Python-Simple) │
│                 │         │                 │
│ • Receive msgs  │         │ • Receive email │
│ • Forward to    │         │ • Forward to    │
│   Leave System  │         │   Leave System  │
│ • Send response │         │ • Send response │
│                 │         │                 │
│ NO LOGIC!       │         │ NO LOGIC!       │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │ HTTP POST                 │ HTTP POST
         │ /api/conversation         │ /api/conversation
         │                           │
         └───────────┬───────────────┘
                     ▼
         ┌───────────────────────┐
         │   Leave System API    │
         │   (Python - Flask)    │
         │                       │
         │   Port: 8090          │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌────────────────┐     ┌─────────────────┐
│ AI Agent       │     │ Leave Processor │
│ Module         │     │                 │
│                │     │                 │
│ • Claude API   │     │ • Auth logic    │
│ • Conversation │     │ • Balance check │
│ • NLP parsing  │     │ • Date valid    │
│ • Agent logger │     │ • Approval/     │
│ • Decision     │     │   Rejection     │
│   tracking     │     │ • DB updates    │
└────────────────┘     └─────────────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌───────────────────────┐
         │   Leave System DB     │
         │   (PostgreSQL)        │
         │                       │
         │ • Students            │
         │ • Parents             │
         │ • Leave requests      │
         │ • Balances            │
         │ • Restrictions        │
         └───────────────────────┘
```

## 📂 Directory Structure

```
leave-management-system/
├── whatsapp-bridge/          # Pure communication channel (Go)
│   ├── bridge_simple.go      # NEW: Simplified bridge (just forwards)
│   ├── main.go               # OLD: Complex bridge (has logic) - DEPRECATED
│   └── store/                # WhatsApp session storage only
│
├── email-bridge/             # Pure communication channel (Python)
│   └── email_service.py      # Forwards emails to Leave System
│
└── leave-system/             # ALL BUSINESS LOGIC LIVES HERE
    ├── api.py                # Flask API with endpoints
    │                         #   - /api/conversation (conversational AI)
    │                         #   - /api/process_parent_request (direct)
    │                         #   - /api/process_housemaster_request
    │
    ├── agents/               # ✨ NEW: AI Agent module
    │   ├── conversation_agent.py  # Claude AI integration
    │   └── agent_logger.py        # Decision logging
    │
    ├── processors/           # Business logic processors
    │   ├── leave_processor.py    # Leave approval workflow
    │   └── leave_parser.py       # Message parsing
    │
    ├── models/               # Data models
    │   └── leave_models.py
    │
    ├── tools/                # Integration tools
    │   └── placeholder_tools.py
    │
    └── logs/                 # ✨ NEW: Agent decision logs
        └── agent-logs/       # Structured JSONL logs
```

## 🔄 Data Flow

### Incoming Message Flow

```
1. User sends: "Can my son have leave this weekend?"
   ↓
2. WhatsApp Bridge receives message
   ↓
3. Bridge forwards to: POST http://localhost:8090/api/conversation
   {
     "message": "Can my son have leave this weekend?",
     "sender": "27123456789",
     "channel": "whatsapp",
     "chat_id": "27123456789@s.whatsapp.net"
   }
   ↓
4. Leave System API → Conversation Agent
   ↓
5. Agent analyzes message:
   - Intent: leave_request
   - Missing: student ID, dates
   ↓
6. Agent logs analysis to logs/agent-logs/
   ↓
7. Agent generates response:
   "I'd be happy to help with the leave request. Could you provide:
    1. Student's name or ID number
    2. Specific dates for the leave"
   ↓
8. Leave System returns:
   {
     "response": "I'd be happy to help...",
     "metadata": {"intent": "leave_request", "complete": false}
   }
   ↓
9. Bridge sends response back via WhatsApp
   ↓
10. User receives message
```

### Complete Request Flow

```
1. User: "John Smith (12345) needs overnight leave Sat 15th Jan"
   ↓
2. Bridge → Leave System API
   ↓
3. Agent analyzes: Complete request detected
   ↓
4. Agent calls Leave Processor directly
   ↓
5. Leave Processor:
   - Authenticates parent
   - Validates student linkage
   - Checks dates
   - Checks balance
   - Checks restrictions
   - Approves/Rejects
   ↓
6. Agent logs full decision chain
   ↓
7. Response: "I'm pleased to confirm the exeat has been approved..."
   ↓
8. Bridge → WhatsApp → User
```

## 🎨 Clean Architecture Benefits

### ✅ Single Responsibility

- **WhatsApp Bridge**: Only handles WhatsApp protocol
- **Email Bridge**: Only handles email protocol
- **Leave System**: Only handles leave management logic

### ✅ Easy to Add New Channels

Want to add SMS? Just create `sms-bridge/` that forwards to the same API:

```go
// sms-bridge/main.go
func handleSMS(smsText, sender string) {
    response := forwardToLeaveSystem(smsText, sender, "sms")
    sendSMS(sender, response.Response)
}
```

### ✅ Centralized Logic

ALL leave rules, ALL agent logic, ALL logging in ONE place:
- Change AI behavior? Edit `leave-system/agents/`
- Change approval rules? Edit `leave-system/processors/`
- Change logging? Edit `leave-system/agents/agent_logger.py`

### ✅ Testable

Test business logic independently of communication channels:

```python
# Test leave system without needing WhatsApp running
from leave_system.agents import ConversationAgent

agent = ConversationAgent()
result = agent.process_message(
    message="John needs leave tomorrow",
    sender="test@example.com",
    channel="test",
    chat_id="test-123"
)

assert "student ID" in result['response'].lower()
```

## 🚀 Running the System

### 1. Start Leave System (Required)

```bash
cd leave-system
python3 api.py
# Listens on http://localhost:8090
```

### 2. Start WhatsApp Bridge (Optional - for WhatsApp channel)

```bash
cd whatsapp-bridge
# Use the simplified bridge
go run bridge_simple.go
```

### 3. Start Email Bridge (Optional - for Email channel)

```bash
cd leave-system/email-bridge
python3 email_service.py
```

## 📋 API Contract

### POST /api/conversation

**Request:**
```json
{
  "message": "User's natural language message",
  "sender": "phone_number or email",
  "channel": "whatsapp|email|sms",
  "chat_id": "unique_identifier",
  "conversation_history": [  // optional
    {"role": "user", "content": "previous message"},
    {"role": "assistant", "content": "previous response"}
  ]
}
```

**Response:**
```json
{
  "response": "Generated response text to send back",
  "metadata": {
    "intent": "leave_request|question|balance_query|unknown",
    "complete": true,  // Has all info needed?
    "timestamp": "2025-01-12T10:30:45"
  }
}
```

## 🔧 Configuration

### Leave System
- `ANTHROPIC_API_KEY` - Claude AI API key
- Agent context: `leave-system/agents/context.md`
- Agent config: `leave-system/agents/config.json`
- Logs: `leave-system/logs/agent-logs/`

### WhatsApp Bridge
- `LeaveSystemAPIBase` - Leave System API URL (default: http://localhost:8090)
- Session storage: `whatsapp-bridge/store/`

### Email Bridge
- Leave System API URL configured in `email_bridge/config.py`

## 📊 Agent Logging

ALL agent decision logs are stored in `leave-system/logs/agent-logs/`:

```
leave-system/logs/agent-logs/
├── 27123456789_at_s.whatsapp.net_2025-01-12.jsonl
├── parent_at_example.com_2025-01-12.jsonl
└── README.md
```

Each log entry:
```json
{
  "timestamp": "2025-01-12T10:30:45",
  "chat_id": "27123456789@s.whatsapp.net",
  "stage": "leave_request_analysis",
  "logic": {
    "extracted_info": {"student_name": "John"},
    "missing_fields": ["student_id", "dates"],
    "next_action": "Request student ID and dates"
  }
}
```

## ✅ Migration Path

**Old Architecture (Messy):**
- WhatsApp bridge contains: Agent logic, Anthropic API, decision logic
- Email bridge contains: Agent logic, Anthropic API, decision logic
- Each channel has duplicate logic → maintenance nightmare

**New Architecture (Clean):**
1. ✅ Create agent module in leave-system
2. ✅ Create /api/conversation endpoint
3. ✅ Create simplified bridges (just forwarders)
4. ✅ Move logging to leave-system
5. ⏭️ Test end-to-end
6. ⏭️ Deprecate old bridge files

## 🎯 What Each Component Should NOT Do

### WhatsApp Bridge Should NOT:
- ❌ Call Anthropic API
- ❌ Make leave approval decisions
- ❌ Check student balances
- ❌ Parse date/student information
- ❌ Store business logic

### Email Bridge Should NOT:
- ❌ Call Anthropic API
- ❌ Make leave approval decisions
- ❌ Check student balances
- ❌ Parse date/student information
- ❌ Store business logic

### Leave System Should NOT:
- ❌ Know about WhatsApp protocol details
- ❌ Know about email protocol details
- ❌ Care which channel the message came from (except for routing responses)

## 📚 Further Reading

- `leave-system/agents/conversation_agent.py` - AI agent implementation
- `leave-system/agents/agent_logger.py` - Logging implementation
- `whatsapp-bridge/bridge_simple.go` - Clean channel implementation
- `leave-system/processors/leave_processor.py` - Business logic

---

**Status:** ✅ Refactored with clean separation
**Migration:** In progress
**Next:** Test end-to-end flow
