# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WhatsApp MCP Server - A Model Context Protocol (MCP) server that enables AI assistants (like Claude) to interact with WhatsApp. The project connects to WhatsApp Web's multidevice API, stores messages in encrypted SQLite databases, and provides AI agent capabilities for automated responses.

This is a two-part system:
1. **Go WhatsApp Bridge** (`whatsapp-bridge/`): Handles WhatsApp connectivity, message storage, and AI agent responses
2. **Python MCP Server** (`whatsapp-mcp-server/`): Exposes MCP tools for Claude Desktop integration

## Architecture

### High-Level Data Flow

```
WhatsApp Web API
       ↕
Go Bridge (main.go) ← REST API (port 8080) → Python MCP Server (main.py)
       ↕                                              ↕
Encrypted SQLite DBs                          Claude Desktop
```

### Key Components

**Go Bridge** (`whatsapp-bridge/main.go` - single 2248 line file):
- WhatsApp connection management via whatsmeow library
- Encrypted SQLite database for messages/chats/reactions
- REST API server on port 8080
- Per-chat AI agent system with configurable personalities
- Media download/upload handling
- Message history synchronization

**Python MCP Server** (`whatsapp-mcp-server/`):
- FastMCP server implementation (`main.py`)
- WhatsApp tool wrappers (`whatsapp.py`)
- Audio conversion utilities (`audio.py`)
- Exposes 15+ MCP tools for Claude to interact with WhatsApp

## Common Commands

### Initial Setup

```bash
# Enable CGO for database encryption
export CGO_ENABLED=1

# Set encryption keys (optional - auto-generated if not set)
export WHATSAPP_MESSAGES_KEY="your-secure-messages-passphrase"
export WHATSAPP_SESSION_KEY="your-secure-session-passphrase"

# Install Python dependencies
cd whatsapp-mcp-server
uv sync

# Run Go bridge (first time will show QR code to scan)
cd ../whatsapp-bridge
go run main.go

# Or build and run binary
go build -o whatsapp-bridge main.go
./whatsapp-bridge
```

### Development Workflow

```bash
# Run Go bridge with live reload during development
cd whatsapp-bridge
CGO_ENABLED=1 go run main.go

# Test MCP server locally
cd whatsapp-mcp-server
uv run main.py

# Query encrypted database (requires correct key)
sqlite3 "file:whatsapp-bridge/store/messages.db?_pragma_key=x'YOUR_HEX_KEY'"

# Reset authentication (deletes session, requires QR re-scan)
rm -rf whatsapp-bridge/store/whatsapp.db whatsapp-bridge/store/.session_key
```

### AI Agent Management

```bash
# Configure agent (now in leave-system)
nano leave-system/agents/config.json

# Edit agent personality
nano leave-system/agents/context.md

# Note: Agent logic now lives in leave-system, not in bridges
# See CLEAN_ARCHITECTURE.md for details
```

## Database Structure

### Encrypted SQLite Databases (AES-256 via SQLCipher)

**store/whatsapp.db**: Session and authentication data
- Managed automatically by whatsmeow library
- Encrypted with key from `store/.session_key` or `$WHATSAPP_SESSION_KEY`

**store/messages.db**: Message content and metadata
- `chats` table: JID, name, last_message_time
- `messages` table: Complete message history with media metadata
- `reactions` table: Emoji reactions linked to messages
- Encrypted with key from `store/.messages_key` or `$WHATSAPP_MESSAGES_KEY`

**Encryption keys are critical**: Without them, data cannot be decrypted. Always backup:
```bash
cp whatsapp-bridge/store/.messages_key ~/backup/
cp whatsapp-bridge/store/.session_key ~/backup/
chmod 600 ~/backup/.*.key
```

## AI Agent System

**IMPORTANT:** The AI agent now lives in the **Leave System**, not in communication bridges. This follows clean architecture principles where channels are just pipes and all logic lives centrally.

The agent is configured in `leave-system/agents/` directory and handles requests for all communication channels (WhatsApp, Email, etc.). See `leave-system/agents/README.md` for full details.

### Architecture

```
WhatsApp Bridge → Leave System API → AI Agent → Response
(Just forwards)    (All logic here)
```

### Quick Setup

1. Configure: `leave-system/agents/config.json` (optional)
2. Edit personality: `leave-system/agents/context.md`
3. Set API key: `export ANTHROPIC_API_KEY="your-key"`
4. Start Leave System: `cd leave-system && python3 api.py`
5. Start bridge (optional): Bridge forwards to Leave System

See `CLEAN_ARCHITECTURE.md` for complete architecture documentation.

### Agent Configuration Options

**Note:** Configuration is now in `leave-system/agents/config.json`:

- `enabled`: Whether the global agent responds to messages
- `response_rate`: Probability of responding to any message (0.0-1.0)
- `min_time_between`: Minimum seconds between responses across all chats
- `max_response_delay`: Maximum delay before responding (adds natural timing)
- `api_endpoint`: AI API endpoint (placeholder - not yet integrated)
- `api_key`: API key with env var expansion support (`${VAR_NAME}`)
- `model_name`: Model identifier (placeholder)

**Note**: Current implementation uses placeholder responses in `generateSimpleResponse()`. Full AI API integration is planned. The global agent responds to all chats based on the configured response rate.

## MCP Tools Available

The Python MCP server exposes these tools to Claude:

**Message Operations**:
- `list_messages`: Query messages with filters (time, sender, chat, content)
- `get_message_context`: Get messages before/after a specific message
- `send_message`: Send text or media to contacts/groups
- `send_file`: Send images, videos, documents
- `send_audio_message`: Send voice messages (requires Ogg Opus format)

**Chat Operations**:
- `list_chats`: List available chats with metadata
- `get_chat`: Get specific chat information
- `get_direct_chat_by_contact`: Find direct chat with a contact
- `get_contact_chats`: List all chats involving a contact
- `get_last_interaction`: Get most recent message with contact

**Contact Operations**:
- `search_contacts`: Search by name or phone number

**Media Operations**:
- `download_media`: Download media from messages (saves to `store/{chat_jid}/`)

**Reaction Operations**:
- `send_reaction`: Send emoji reactions
- `get_reactions_for_message`: Get reactions for specific message
- `get_chat_reactions`: Get all reactions in a chat

## REST API (Go Bridge)

The bridge exposes HTTP endpoints on `localhost:8080`:

- `POST /api/send`: Send text/media messages
- `POST /api/react`: Send emoji reactions
- `POST /api/download`: Download media files
- `GET /api/messages?chat_jid=X&limit=N`: Get message history
- `GET /api/chats`: List all chats
- `GET /api/reactions?message_id=X&chat_jid=Y`: Get reactions for message
- `GET /api/chat-reactions?chat_jid=X&limit=N`: Get chat reactions

These are consumed by the Python MCP server's `whatsapp.py` module.

## Important Implementation Details

### Message Processing Flow

1. WhatsApp message arrives → `eventHandler()` processes event
2. Message stored in database via `MessageStore.StoreMessage()`
3. Agent manager checks `ShouldRespond()` (asynchronously in goroutine)
4. If yes → `GenerateResponse()` → `SendAgentResponse()`
5. Response sent via WhatsApp client

### Media Handling

- Only metadata stored initially (URL, keys, hashes from WhatsApp)
- Actual media downloaded on-demand via `downloadMedia()`
- Media files saved to `store/{chat_jid}/` directories
- Voice messages require Ogg Opus format with waveform data

### Chat Name Resolution

Names are resolved in this order:
1. Check database for existing name
2. For groups: Extract from conversation metadata or query WhatsApp
3. For contacts: Use contact store full name
4. Fallback: Use JID user part

### Audio Message Processing

Voice messages need special handling:
- Must be Ogg Opus format
- Duration extracted by reading Ogg page granule positions
- 64-byte waveform generated (WhatsApp requirement)
- Python `audio.py` can convert other formats using FFmpeg

## Security Considerations

### Encryption
- All data at rest encrypted with AES-256 (SQLCipher)
- Encryption keys stored with 0600 permissions
- Lost keys = permanently lost data (no recovery)
- CGO must be enabled for encryption to work

### API Keys
- Agent configs support env var expansion: `"${ANTHROPIC_API_KEY}"`
- Keep `.env` file in gitignore
- Never commit actual API keys

### WhatsApp Session
- Sessions expire after ~20 days, require QR re-scan
- Session data encrypted in `store/whatsapp.db`
- Protect session keys - they grant WhatsApp access

## Troubleshooting

### "Binary was compiled with 'CGO_ENABLED=0'"
- Must set `export CGO_ENABLED=1` before building
- Requires GCC/C compiler installed
- On Windows: Install MSYS2, add to PATH

### "File is encrypted or is not a database"
- Wrong encryption key
- Check key files exist: `ls -la whatsapp-bridge/store/.*.key`
- Verify environment variables if set manually

### QR Code Not Appearing
- Terminal may not support QR rendering
- Session may already be active (check logs)
- Try deleting `store/whatsapp.db` to force re-auth

### Agent Not Responding
- Check `agents/global-config.json` exists at root level
- Verify `"enabled": true`
- Ensure `response_rate` > 0
- Check `min_time_between` hasn't been violated (applies globally across all chats)
- Look for `[DEBUG]` logs in bridge output showing agent decision flow

### Messages Not Syncing
- History sync can take several minutes after initial QR scan
- Check bridge logs for errors
- Verify WhatsApp mobile app has internet connection

## Project Dependencies

### Go Dependencies (`whatsapp-bridge/go.mod`)
- `go.mau.fi/whatsmeow`: WhatsApp Web API client
- `github.com/mutecomm/go-sqlcipher/v4`: SQLite with encryption
- `github.com/mdp/qrterminal`: Terminal QR code display
- `github.com/joho/godotenv`: Environment variable loading
- `google.golang.org/protobuf`: Protocol buffer support

### Python Dependencies (`whatsapp-mcp-server/pyproject.toml`)
- `mcp[cli]>=1.6.0`: Model Context Protocol framework
- `httpx>=0.28.1`: HTTP client
- `requests>=2.32.3`: HTTP requests library
- FFmpeg (optional): Audio format conversion

## Claude Desktop Configuration

The `claude_desktop_config.json` file configures the MCP server connection. Update paths:

```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "/path/to/uv",
      "args": [
        "--directory",
        "/absolute/path/to/whatsapp-mcp-server",
        "run",
        "main.py"
      ]
    }
  }
}
```

Place at:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Cursor: `~/.cursor/mcp.json`

## Testing Strategy

Currently no automated tests. Manual testing workflow:

1. Start Go bridge: `cd whatsapp-bridge && CGO_ENABLED=1 go run main.go`
2. Verify QR scan and connection
3. Send test messages from WhatsApp mobile app
4. Query database: `sqlite3 store/messages.db "SELECT * FROM messages LIMIT 5;"`
5. Test MCP tools through Claude Desktop
6. Verify agent responses if configured

## Development Tips

### Code Organization
- `main.go` is a single large file (~2200 lines) - search by function name
- Use line number references for navigation
- Agent logic isolated in `AgentManager` struct
- REST API handlers grouped together
- Global agent configuration stored at root level in `agents/` directory (accessible to all comms channels)

### Common Gotchas
- Always set `CGO_ENABLED=1` before running/building
- Go bridge must be running for Python MCP server to work
- Media downloads require correct message_id + chat_jid pair
- Voice messages need Ogg Opus format (won't play as voice otherwise)
- Global agent responds to ALL chats based on response_rate and timing settings
- Agent paths in Go code use `../agents/` because bridge runs from `whatsapp-bridge/` subdirectory

### Debugging
- Bridge logs to stdout with timestamps
- Look for `[DEBUG]` prefix for agent decision logs
- Check HTTP response codes from REST API
- Query database directly to verify storage
- Test REST API with curl: `curl http://localhost:8080/api/chats`

## Related Documentation

- `README.md`: Full installation and setup guide
- `agents/GLOBAL_AGENT_README.md`: Comprehensive agent system documentation
- `whatsapp-bridge/CLAUDE.md`: Detailed bridge-specific guidance
- `LICENSE`: MIT license terms
