# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **WhatsApp Bridge** component of the WhatsApp MCP (Model Context Protocol) system. It's a Go application that connects directly to WhatsApp's Web Multidevice API using the [whatsmeow](https://github.com/tulir/whatsmeow) library. The bridge serves as the backend that manages WhatsApp connections, message storage, and AI agent responses.

## Architecture

### Two-Part System

1. **whatsapp-bridge/** (this directory): Go application that handles WhatsApp connectivity
2. **whatsapp-mcp-server/** (sibling directory): Python MCP server that exposes tools to Claude Desktop

### Key Components in main.go

The entire bridge is implemented in a single `main.go` file (2248 lines) with these major sections:

- **Encryption Management** (lines 87-140): Handles AES-256 encryption keys for SQLite databases
- **MessageStore** (lines 143-388): SQLite database operations for messages, chats, and reactions
- **AgentManager** (lines 423-759): Manages per-chat AI agents with configurable personalities
- **Message Handling** (lines 787-1171): Processes incoming/outgoing WhatsApp messages
- **Media Operations** (lines 1174-1376): Download and upload media files
- **REST API Server** (lines 1378-1668): HTTP endpoints for the MCP server to interact with
- **History Sync** (lines 1907-2083): Syncs historical WhatsApp messages
- **Audio Processing** (lines 2085-2247): Analyzes Ogg Opus files for voice messages

## Database Structure

### Two Encrypted SQLite Databases

Both databases use SQLCipher for AES-256 encryption:

1. **store/whatsapp.db**: Session and authentication data (managed by whatsmeow)
2. **store/messages.db**: Message content with these tables:
   - `chats`: JID, name, last_message_time
   - `messages`: Complete message history with media metadata
   - `reactions`: Emoji reactions to messages

### Encryption Keys

Keys are stored in:
- `store/.session_key`: For whatsapp.db
- `store/.messages_key`: For messages.db

Keys are either:
- Loaded from environment variables (`WHATSAPP_SESSION_KEY`, `WHATSAPP_MESSAGES_KEY`)
- Auto-generated on first run and saved to key files

## AI Agent System

### Agent Directory Structure

**Note**: The agents directory is located at the repository root level (`../agents/` relative to this bridge), allowing the global agent to work across multiple communication channels.

```
../agents/                       # Root-level agents directory
├── global-config.json           # Global agent configuration
├── global-context.md            # Global agent personality/instructions
├── global-examples.md           # Optional response examples
├── templates/                   # Template configurations (for reference)
│   ├── group-assistant/
│   └── personal-assistant/
└── shared/                      # Shared resources
```

### Global Agent System

- Single global agent responds to all chats across all communication channels
- No per-chat configuration - one personality for all conversations
- Agents configured at root level to support multi-channel communication (WhatsApp, email, etc.)

### Agent Configuration (global-config.json)

```json
{
  "enabled": true,              // Whether global agent responds
  "response_rate": 0.3,         // Probability of responding to any message (0.0-1.0)
  "min_time_between": 60,       // Min seconds between responses (global across all chats)
  "max_response_delay": 15,     // Max delay before responding
  "api_endpoint": "...",        // AI API endpoint (currently unused)
  "api_key": "${ENV_VAR}",      // API key (supports env var expansion)
  "model_name": "..."           // Model name (currently unused)
}
```

**Note**: AI integration is currently placeholder-only. The `generateSimpleResponse()` function returns pre-defined responses instead of calling an AI API.

### Agent Decision Flow

1. Message arrives → `handleMessage()`
2. Check `AgentManager.ShouldRespond()`:
   - Skip if message is from us
   - Skip if global agent disabled or not configured
   - Check minimum time since last response (global timer)
   - Roll dice against `response_rate`
3. If yes → `GenerateResponse()` → `SendAgentResponse()`

## REST API Endpoints

The bridge exposes these HTTP endpoints on port 8080 for the MCP server:

- `POST /api/send`: Send text/media messages
- `POST /api/react`: Send emoji reactions
- `POST /api/download`: Download media files
- `GET /api/messages?chat_jid=X&limit=N`: Get message history
- `GET /api/chats`: List all chats
- `GET /api/reactions?message_id=X&chat_jid=Y`: Get reactions for a message
- `GET /api/chat-reactions?chat_jid=X&limit=N`: Get all reactions in a chat

## Common Development Commands

### Build and Run

```bash
# Enable CGO for SQLCipher encryption support
export CGO_ENABLED=1

# Run the bridge (will prompt for QR code on first run)
go run main.go

# Build binary
go build -o whatsapp-bridge main.go
```

### Database Operations

```bash
# View encrypted database (requires correct key)
sqlite3 "file:store/messages.db?_pragma_key=x'YOUR_HEX_KEY'"

# Reset everything (will require QR code re-scan)
rm -rf store/*.db store/.*.key
```

### Agent Management

```bash
# Configure global agent (from repository root)
nano agents/global-config.json
nano agents/global-context.md

# Or from whatsapp-bridge directory
nano ../agents/global-config.json
nano ../agents/global-context.md
```

## Important Implementation Details

### Message Processing

- Messages are stored immediately in the database (`StoreMessage()`)
- Agent decisions happen asynchronously in goroutines to avoid blocking
- Both regular messages and history sync events are processed similarly
- Reactions are stored separately and linked by `message_id` + `chat_jid`

### Media Handling

- Only metadata is stored in the database initially (URL, keys, hashes)
- Actual media files are downloaded on-demand via `downloadMedia()`
- Downloaded files are saved to `store/{chat_jid}/` directories
- The `MediaDownloader` struct implements whatsmeow's `DownloadableMessage` interface

### Chat Name Resolution

The `GetChatName()` function (line 1824) determines chat display names:
1. Check database for existing name
2. For groups: Extract from conversation metadata or query `GetGroupInfo()`
3. For contacts: Use contact full name from store
4. Fallback to JID user part

### Audio Messages

Voice messages require Ogg Opus format:
- `analyzeOggOpus()` (line 2086) extracts duration from Ogg pages
- Reads granule positions to calculate accurate duration
- Generates synthetic waveform data (required by WhatsApp)
- `placeholderWaveform()` creates natural-looking 64-byte waveforms

## Security Considerations

### Encryption
- All data at rest is encrypted with AES-256 via SQLCipher
- Keys must be backed up - lost keys = lost data
- Key files have 0600 permissions (owner read/write only)

### Agent API Keys
- Support environment variable expansion: `"${ANTHROPIC_API_KEY}"`
- Never commit actual keys to git
- Keep `.env` file in parent directory (gitignored)

## Troubleshooting

### CGO/Compilation Issues
- Must have `CGO_ENABLED=1` for SQLCipher
- Requires GCC/C compiler installed
- On Windows: Install MSYS2 and add to PATH

### Authentication
- QR code appears once on first run
- Session persists in encrypted `store/whatsapp.db`
- Sessions expire after ~20 days, requiring re-scan
- Delete `store/whatsapp.db` to force new authentication

### Database Corruption
- "File is encrypted or not a database": Wrong encryption key
- Check key files exist and have correct permissions
- Verify `CGO_ENABLED=1` was set during compilation

### Agent Not Responding
- Check `../agents/global-config.json` exists (note: agents at root level)
- Verify `"enabled": true`
- Look for debug logs: `[DEBUG]` lines show decision flow
- Ensure `response_rate` > 0 and `min_time_between` has elapsed (applies globally across all chats)
- Global agent responds to ALL chats, not specific ones

## Dependencies

Key Go packages:
- `go.mau.fi/whatsmeow`: WhatsApp Web Multidevice API client
- `github.com/mutecomm/go-sqlcipher/v4`: SQLite with encryption
- `github.com/mdp/qrterminal`: Terminal QR code display
- `github.com/joho/godotenv`: Environment variable loading
- `google.golang.org/protobuf`: Protocol buffer support

## Testing

Currently no automated tests. Manual testing involves:
1. Running the bridge and scanning QR code
2. Sending test messages to configured chats
3. Verifying message storage in database
4. Testing agent responses (if configured)
5. Using MCP server tools through Claude Desktop

## Development Workflow

1. Make changes to `main.go`
2. Restart the bridge: `CGO_ENABLED=1 go run main.go`
3. Test via WhatsApp mobile app or MCP tools
4. Check logs for errors and debug output
5. Query database to verify data storage

## Related Files

- `../whatsapp-mcp-server/main.py`: Python MCP server implementation
- `../whatsapp-mcp-server/whatsapp.py`: WhatsApp tool implementations for MCP
- `../whatsapp-mcp-server/audio.py`: Audio file conversion utilities
- `../README.md`: Full project documentation
- `../AI_AGENTS_README.md`: Agent system documentation
- `../agents/`: Root-level agent configurations (shared across communication channels)
