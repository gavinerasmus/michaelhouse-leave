# Leave System AI Agent

This is the conversational AI agent for the Michaelhouse Leave Management System. The agent handles natural language interactions with parents and housemasters across all communication channels (WhatsApp, Email, etc.).

## 🎯 Architecture

The agent lives in the **Leave System** (not in communication channels). Communication bridges (WhatsApp, Email) forward messages to the Leave System API, and the agent processes them here.

```
WhatsApp/Email → Leave System API → AI Agent → Response
```

## 🚀 Quick Start

### 1. Configure the Agent

Edit `leave-system/agents/config.json`:

```json
{
  "enabled": true,
  "response_rate": 0.3,
  "min_time_between": 60,
  "max_response_delay": 15,
  "api_endpoint": "https://api.anthropic.com/v1/messages",
  "api_key": "${ANTHROPIC_API_KEY}",
  "model_name": "claude-3-5-sonnet-20241022"
}
```

### 2. Customize Agent Personality

Edit `leave-system/agents/context.md` to define your agent's personality, knowledge, and behavior.

### 3. Set API Key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 4. Start the Leave System

```bash
cd leave-system
python3 api.py
```

The agent will now handle all conversational requests through the `/api/conversation` endpoint!

## 📁 Directory Structure

```
leave-system/agents/
├── config.json             # Agent configuration (optional)
├── context.md              # Agent personality & instructions
├── conversation_agent.py   # Main agent implementation
├── agent_logger.py         # Decision logging
├── __init__.py             # Module exports
└── README.md               # This file
```

## ⚙️ How It Works

### Message Flow

1. **User sends message** (via WhatsApp, Email, etc.)
2. **Channel bridge forwards** to `POST /api/conversation`
3. **API calls** `ConversationAgent.process_message()`
4. **Agent analyzes** message for intent and completeness
5. **Agent logs** analysis, decision, and response
6. **Agent either**:
   - Processes complete leave request directly, OR
   - Generates conversational response for missing info
7. **Response sent back** through API to channel
8. **User receives** response

### Agent Intelligence

The agent uses Claude AI to:
- **Understand natural language** requests
- **Extract information** (student ID, dates, leave type)
- **Identify missing fields** explicitly
- **Generate helpful responses** when info is incomplete
- **Process complete requests** automatically

### Decision Logging

Every decision is logged to `leave-system/logs/agent-logs/`:

```json
{
  "timestamp": "2025-01-12T10:30:45",
  "chat_id": "27123456789@s.whatsapp.net",
  "stage": "leave_request_analysis",
  "logic": {
    "extracted_info": {"student_name": "John"},
    "missing_fields": ["student_id", "dates"],
    "next_action": "Request student ID and dates from parent"
  }
}
```

## 🔧 Configuration

### Environment Variables

```bash
# Required for AI functionality
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional - defaults to these values
export LEAVE_SYSTEM_PORT=8090
```

### config.json (Optional)

The agent works without a config file, but you can customize:

- `enabled`: Whether agent is active
- `response_rate`: Probability of responding (0.0-1.0)
- `min_time_between`: Minimum seconds between responses
- `model_name`: Claude model to use

### context.md (Important!)

This defines the agent's personality and behavior. Include:

```markdown
# Your Agent Name

You are a helpful assistant for leave management.

## Personality
- Be polite and professional
- Be concise but friendly
- Show empathy

## Your Role
- Help parents request leave
- Answer questions about leave policies
- Guide users when information is missing

## Important Rules
- Always ask for student ID if missing
- Confirm dates explicitly
- Explain reasons for rejections clearly
```

## 📊 API Integration

The agent is exposed through the Leave System API:

### POST /api/conversation

**Request:**
```json
{
  "message": "Can my son have leave this weekend?",
  "sender": "27123456789",
  "channel": "whatsapp",
  "chat_id": "27123456789@s.whatsapp.net",
  "conversation_history": []
}
```

**Response:**
```json
{
  "response": "I'd be happy to help. Could you provide the student ID number?",
  "metadata": {
    "intent": "leave_request",
    "complete": false,
    "timestamp": "2025-01-12T10:30:45"
  }
}
```

## 🧪 Testing

### Test Agent Directly

```python
from agents import ConversationAgent

agent = ConversationAgent()

result = agent.process_message(
    message="Can John have leave tomorrow?",
    sender="test@example.com",
    channel="test",
    chat_id="test-123"
)

print(result['response'])
print(result['metadata'])
```

### Test via API

```bash
curl -X POST http://localhost:8090/api/conversation \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can my son have leave this weekend?",
    "sender": "test@example.com",
    "channel": "test",
    "chat_id": "test-123"
  }'
```

### View Logs

```bash
# View logs for a specific chat
cat leave-system/logs/agent-logs/test-123_2025-01-12.jsonl | jq '.'
```

## 🔍 Troubleshooting

### Agent Not Responding

1. Check API is running: `curl http://localhost:8090/health`
2. Check API key: `echo $ANTHROPIC_API_KEY`
3. Check logs: `leave-system/logs/agent-logs/`

### "ANTHROPIC_API_KEY not set" Warning

**Problem:** No API key configured
**Solution:** `export ANTHROPIC_API_KEY="your-key"`
**Fallback:** Agent will use simple rule-based responses

### Agent Gives Unexpected Responses

1. Check `context.md` - Agent personality defined here
2. Check logs to see agent's reasoning
3. Adjust context.md and restart

### Logs Not Being Created

1. Check directory exists: `mkdir -p leave-system/logs/agent-logs`
2. Check permissions
3. Check AgentLogger initialization in conversation_agent.py

## 📚 Files Reference

| File | Purpose |
|------|---------|
| `conversation_agent.py` | Main agent logic, Anthropic integration |
| `agent_logger.py` | Decision logging system |
| `config.json` | Optional agent configuration |
| `context.md` | Agent personality & instructions |
| `__init__.py` | Module exports |

## 🎯 Example Scenarios

### Scenario 1: Missing Student ID

**User:** "Can my son have leave this weekend?"

**Agent Logic:**
- Intent: leave_request
- Found: request for weekend leave
- Missing: student_id, specific_dates
- Action: Ask for student ID and exact dates

**Response:** "I'd be happy to help with the leave request. Could you please provide:
1. The student's ID number
2. The specific dates (e.g., Saturday 15th to Sunday 16th January)"

**Logged:**
```json
{
  "stage": "leave_request_analysis",
  "logic": {
    "missing_fields": ["student_id", "dates"],
    "next_action": "Request student ID and dates"
  }
}
```

### Scenario 2: Complete Request

**User:** "John Smith (ID: 12345) needs overnight leave Saturday 15th Jan"

**Agent Logic:**
- Intent: leave_request
- Found: student_id=12345, date=15 Jan, type=overnight
- Missing: nothing
- Action: Process directly through LeaveProcessor

**Response:** "I'm pleased to confirm that the exeat request for John Smith has been approved..."

## 🔄 Updates and Maintenance

### Changing Agent Personality

Edit `context.md` and restart the API. Changes take effect immediately.

### Updating AI Model

Edit code to use different Claude model:
```python
response = self.client.messages.create(
    model="claude-3-opus-20240229",  # Change model here
    ...
)
```

### Adding New Intents

Edit `_analyze_message()` in `conversation_agent.py` to detect new patterns.

---

**The agent is the brain of your leave system. It lives here, in the Leave System, not in communication channels.**
