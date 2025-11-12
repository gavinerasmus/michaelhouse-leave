# Quick Start - Clean Architecture

## 🎯 30-Second Overview

**NEW:** WhatsApp bridge just forwards messages. ALL logic in Leave System ✅

## 🚀 Start the System

### Step 1: Start Leave System API (Required)

```bash
cd leave-system

# Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Start the API
python3 api.py
```

**Expected output:**
```
Starting Michaelhouse Leave API on http://localhost:8090
Endpoints:
  GET  /health - Health check
  POST /api/conversation - Conversational AI agent (recommended) ✨
  POST /api/process_parent_request - Process parent leave requests (direct)
  POST /api/process_housemaster_request - Process housemaster requests
```

**✅ Leave System running - This contains ALL your business logic**

### Step 2: Test API Directly (No WhatsApp needed)

```bash
# In another terminal
curl -X POST http://localhost:8090/api/conversation \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can my son John have leave this weekend?",
    "sender": "parent@example.com",
    "channel": "test",
    "chat_id": "test-123"
  }'
```

**Expected response:**
```json
{
  "response": "I'd be happy to help with the leave request. Could you provide the student ID number so I can process this?",
  "metadata": {
    "intent": "leave_request",
    "complete": false,
    "timestamp": "2025-01-12T11:00:00"
  }
}
```

**✅ API working - Agent is responding**

### Step 3: Check Logs Were Created

```bash
ls -la leave-system/logs/agent-logs/
```

**Expected:**
```
test-123_2025-01-12.jsonl  ← Your conversation log
```

**View the log:**
```bash
cat leave-system/logs/agent-logs/test-123_2025-01-12.jsonl | jq '.'
```

**✅ Logging working - Decisions are tracked**

### Step 4: Start WhatsApp Bridge (Optional)

```bash
cd whatsapp-bridge

# Use the NEW simplified bridge
go run bridge_simple.go
```

**Expected output:**
```
✅ WhatsApp Bridge connected
📡 Forwarding all messages to Leave System API at http://localhost:8090
🔧 This bridge contains NO business logic - it's just a communication channel
```

**✅ Channel ready - Now send WhatsApp messages**

## 📱 Send a Test Message

Send via WhatsApp:
```
Can my son John (ID: 12345) have overnight leave Saturday 15th Jan?
```

**What happens:**
1. WhatsApp → Bridge receives message
2. Bridge → Forwards to Leave System API
3. Leave System → Agent analyzes and processes
4. Agent → Logs decision to `logs/agent-logs/`
5. Leave System → Returns response
6. Bridge → Sends response via WhatsApp
7. You → See response on your phone

## 🔍 View What The Agent is Thinking

```bash
cd leave-system

# View logs for a specific chat
python3 -c "
from agents.agent_logger import AgentLogger
import sys

logger = AgentLogger()

# Replace with your actual chat ID
chat_id = '27123456789@s.whatsapp.net'
date = '2025-01-12'

logs = logger.get_chat_logs(chat_id, date)
print(f'Found {len(logs)} log entries\n')

for entry in logs:
    print(f\"Stage: {entry['stage']}\")
    if 'logic' in entry:
        print(f\"Logic: {entry['logic']}\")
    print()
"
```

**Example output:**
```
Found 4 log entries

Stage: received
Logic: {'message_length': 45, 'has_content': True}

Stage: analysis
Logic: {'intent': 'leave_request', 'missing_fields': ['student_id', 'dates']}

Stage: decision
Logic: {'action': 'request_info', 'reason': 'incomplete_request'}

Stage: response
Logic: {'response_length': 87, 'response_type': 'conversational'}
```

## 🎯 Architecture At a Glance

```
WhatsApp Message
       ↓
[WhatsApp Bridge]  ← Just forwards, NO logic
       ↓
  HTTP POST to
  localhost:8090
       ↓
[Leave System API]  ← ALL logic lives here
       ↓
  ┌─────────┬─────────┐
  │         │         │
[Agent]  [Processor] [Logger]
  │         │         │
Claude AI Leave    Decision
          Rules     Tracking
```

## ✅ Verify Clean Separation

### Bridge Should Only Have:
```go
// bridge_simple.go - ONLY 3 things:
1. Receive WhatsApp message
2. HTTP POST to Leave System
3. Send response back

// NO:
- No Anthropic API ❌
- No business logic ❌
- No decision making ❌
```

### Leave System Should Have:
```python
# leave-system/ - ALL the logic:
✓ AI agent (Anthropic)
✓ Leave processing
✓ Student validation
✓ Balance checking
✓ Decision logging
✓ Everything else
```

## 📚 Next Steps

1. **Read:** `CLEAN_ARCHITECTURE.md` - Full architecture documentation
2. **Read:** `REFACTORING_SUMMARY.md` - What changed and why
3. **Test:** Send various messages and check logs
4. **Customize:** Edit `leave-system/agents/context.md` for agent personality

## 🔧 Configuration

### Leave System
```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional - Agent personality
vim leave-system/agents/context.md
```

### WhatsApp Bridge
```go
// bridge_simple.go
const (
    LeaveSystemAPIBase = "http://localhost:8090"  // Change if needed
    ConversationEndpoint = "/api/conversation"
)
```

## ❓ Troubleshooting

### "Connection refused" error in bridge
**Problem:** Leave System not running
**Solution:** Start Leave System first (Step 1)

### "ANTHROPIC_API_KEY not set" warning
**Problem:** No API key configured
**Solution:** `export ANTHROPIC_API_KEY="your-key"`
**Fallback:** System will use simple responses without AI

### No logs appearing
**Problem:** Logs directory doesn't exist or wrong permissions
**Solution:** Check `leave-system/logs/agent-logs/` exists

### Bridge not forwarding messages
**Problem:** Using old bridge instead of new one
**Solution:** Use `go run bridge_simple.go` not `go run main.go`

## 🎓 Understanding The Flow

### Example: Incomplete Request

```
User: "Can my son have leave?"

Bridge:
  - Receive message
  - POST to Leave System
  - Wait for response

Leave System:
  ┌─ Agent receives message
  ├─ Analyzes: Intent=leave_request, Missing=[student_id, dates]
  ├─ Logs analysis
  ├─ Generates: "Could you provide student ID and dates?"
  └─ Returns response

Bridge:
  - Receive response
  - Send via WhatsApp

User sees: "Could you provide student ID and dates?"

Logs show:
  {
    "stage": "analysis",
    "logic": {
      "intent": "leave_request",
      "missing_fields": ["student_id", "dates"]
    }
  }
```

### Example: Complete Request

```
User: "John Smith (12345) overnight leave Sat 15 Jan"

Bridge:
  - Receive message
  - POST to Leave System

Leave System:
  ┌─ Agent receives message
  ├─ Analyzes: Complete request detected
  ├─ Calls Leave Processor directly
  │
  └─ Processor:
      ├─ Authenticates parent ✓
      ├─ Validates student linkage ✓
      ├─ Checks dates ✓
      ├─ Checks balance ✓
      ├─ Approves ✓
      └─ Returns: "Exeat approved..."

Bridge:
  - Receive response
  - Send via WhatsApp

User sees: "I'm pleased to confirm the exeat has been approved..."
```

## 🎉 Success Indicators

✅ Leave System API running on port 8090
✅ API responds to curl test with JSON
✅ Logs created in `leave-system/logs/agent-logs/`
✅ WhatsApp bridge forwards messages
✅ Responses appear in WhatsApp
✅ NO business logic in bridge code

---

**You're running with clean architecture! 🎊**

Channels are dumb pipes. Logic is centralized. Easy to maintain. 🚀
