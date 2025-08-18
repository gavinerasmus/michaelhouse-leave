# WhatsApp MCP Server

This is a Model Context Protocol (MCP) server for WhatsApp.

With this you can search and read your personal Whatsapp messages (including images, videos, documents, and audio messages), search your contacts and send messages to either individuals or groups. You can also send media files including images, videos, documents, and audio messages.

It connects to your **personal WhatsApp account** directly via the Whatsapp web multidevice API (using the [whatsmeow](https://github.com/tulir/whatsmeow) library). All your messages are stored locally in a SQLite database and only sent to an LLM (such as Claude) when the agent accesses them through tools (which you control).

Here's an example of what you can do when it's connected to Claude.

![WhatsApp MCP](./example-use.png)

> To get updates on this and other projects I work on [enter your email here](https://docs.google.com/forms/d/1rTF9wMBTN0vPfzWuQa2BjfGKdKIpTbyeKxhPMcEzgyI/preview)

> *Caution:* as with many MCP servers, the WhatsApp MCP is subject to [the lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/). This means that project injection could lead to private data exfiltration.

## Installation

### Prerequisites

- Go (with CGO enabled for database encryption)
- Python 3.6+
- Anthropic Claude Desktop app (or Cursor)
- UV (Python package manager), install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- FFmpeg (_optional_) - Only needed for audio messages. If you want to send audio files as playable WhatsApp voice messages, they must be in `.ogg` Opus format. With FFmpeg installed, the MCP server will automatically convert non-Opus audio files. Without FFmpeg, you can still send raw audio files using the `send_file` tool.
- GCC compiler (required for SQLite encryption)

### Steps

1. **Clone this repository**

   ```bash
   git clone https://github.com/lharries/whatsapp-mcp.git
   cd whatsapp-mcp
   ```

2. **Set up database encryption (IMPORTANT for security)**

   Your WhatsApp messages and session data are now encrypted at rest using AES-256 encryption. You have two options for encryption keys:

   **Option A: Environment Variables (Recommended)**
   ```bash
   export CGO_ENABLED=1
   export WHATSAPP_MESSAGES_KEY="your-secure-messages-passphrase"
   export WHATSAPP_SESSION_KEY="your-secure-session-passphrase"
   ```

   **Option B: Auto-generated Keys (Automatic)**
   If you don't set environment variables, the application will automatically generate secure 256-bit encryption keys and save them to:
   - `whatsapp-bridge/store/.messages_key`
   - `whatsapp-bridge/store/.session_key`

   **⚠️ CRITICAL: Backup your encryption keys! Without them, you cannot decrypt your data.**

3. **Run the WhatsApp bridge**

   Navigate to the whatsapp-bridge directory and run the Go application:

   ```bash
   cd whatsapp-bridge
   CGO_ENABLED=1 go run main.go
   ```

   **If you have existing unencrypted databases**, run the migration first:
   ```bash
   CGO_ENABLED=1 go run main.go migrate.go migrate
   ```

   The first time you run it, you will be prompted to scan a QR code. Scan the QR code with your WhatsApp mobile app to authenticate.

   After approximately 20 days, you will might need to re-authenticate.

4. **Connect to the MCP server**

   Copy the below json with the appropriate {{PATH}} values:

   ```json
   {
     "mcpServers": {
       "whatsapp": {
         "command": "{{PATH_TO_UV}}", // Run `which uv` and place the output here
         "args": [
           "--directory",
           "{{PATH_TO_SRC}}/whatsapp-mcp/whatsapp-mcp-server", // cd into the repo, run `pwd` and enter the output here + "/whatsapp-mcp-server"
           "run",
           "main.py"
         ]
       }
     }
   }
   ```

   For **Claude**, save this as `claude_desktop_config.json` in your Claude Desktop configuration directory at:

   ```
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

   For **Cursor**, save this as `mcp.json` in your Cursor configuration directory at:

   ```
   ~/.cursor/mcp.json
   ```

5. **Restart Claude Desktop / Cursor**

   Open Claude Desktop and you should now see WhatsApp as an available integration.

   Or restart Cursor.

### Windows Compatibility

If you're running this project on Windows, database encryption requires **CGO to be enabled** and a C compiler installed. By default, **CGO is disabled on Windows**.

#### Steps to get it working:

1. **Install a C compiler**  
   We recommend using [MSYS2](https://www.msys2.org/) to install a C compiler for Windows. After installing MSYS2, make sure to add the `ucrt64\bin` folder to your `PATH`.  
   → A step-by-step guide is available [here](https://code.visualstudio.com/docs/cpp/config-mingw).

2. **Enable CGO and set encryption keys**

   ```bash
   cd whatsapp-bridge
   go env -w CGO_ENABLED=1
   set WHATSAPP_MESSAGES_KEY=your-secure-messages-passphrase
   set WHATSAPP_SESSION_KEY=your-secure-session-passphrase
   go run main.go
   ```

   For migration of existing databases:
   ```bash
   go run main.go migrate.go migrate
   ```

Without this setup, you'll likely run into errors like:

> `Binary was compiled with 'CGO_ENABLED=0', SQLCipher requires CGO to work.`

## Architecture Overview

This application consists of two main components:

1. **Go WhatsApp Bridge** (`whatsapp-bridge/`): A Go application that connects to WhatsApp's web API, handles authentication via QR code, and stores message history in SQLite. It serves as the bridge between WhatsApp and the MCP server.

2. **Python MCP Server** (`whatsapp-mcp-server/`): A Python server implementing the Model Context Protocol (MCP), which provides standardized tools for Claude to interact with WhatsApp data and send/receive messages.

### Data Storage & Security

- All message history is stored in **encrypted SQLite databases** within the `whatsapp-bridge/store/` directory
- **AES-256 encryption** protects your data at rest using SQLCipher
- The database maintains tables for chats and messages
- Messages are indexed for efficient searching and retrieval
- **Two encrypted databases**:
  - `messages.db` - Your WhatsApp message content and media metadata
  - `whatsapp.db` - Session and authentication data
- **Encryption keys** are stored in:
  - `store/.messages_key` - Key for messages database
  - `store/.session_key` - Key for session database
- **Performance impact**: 5-15% overhead for encryption (minimal impact on normal usage)

## Usage

Once connected, you can interact with your WhatsApp contacts through Claude, leveraging Claude's AI capabilities in your WhatsApp conversations.

### MCP Tools

Claude can access the following tools to interact with WhatsApp:

- **search_contacts**: Search for contacts by name or phone number
- **list_messages**: Retrieve messages with optional filters and context
- **list_chats**: List available chats with metadata
- **get_chat**: Get information about a specific chat
- **get_direct_chat_by_contact**: Find a direct chat with a specific contact
- **get_contact_chats**: List all chats involving a specific contact
- **get_last_interaction**: Get the most recent message with a contact
- **get_message_context**: Retrieve context around a specific message
- **send_message**: Send a WhatsApp message to a specified phone number or group JID
- **send_file**: Send a file (image, video, raw audio, document) to a specified recipient
- **send_audio_message**: Send an audio file as a WhatsApp voice message (requires the file to be an .ogg opus file or ffmpeg must be installed)
- **download_media**: Download media from a WhatsApp message and get the local file path

### Media Handling Features

The MCP server supports both sending and receiving various media types:

#### Media Sending

You can send various media types to your WhatsApp contacts:

- **Images, Videos, Documents**: Use the `send_file` tool to share any supported media type.
- **Voice Messages**: Use the `send_audio_message` tool to send audio files as playable WhatsApp voice messages.
  - For optimal compatibility, audio files should be in `.ogg` Opus format.
  - With FFmpeg installed, the system will automatically convert other audio formats (MP3, WAV, etc.) to the required format.
  - Without FFmpeg, you can still send raw audio files using the `send_file` tool, but they won't appear as playable voice messages.

#### Media Downloading

By default, just the metadata of the media is stored in the local database. The message will indicate that media was sent. To access this media you need to use the download_media tool which takes the `message_id` and `chat_jid` (which are shown when printing messages containing the meda), this downloads the media and then returns the file path which can be then opened or passed to another tool.

## Technical Details

1. Claude sends requests to the Python MCP server
2. The MCP server queries the Go bridge for WhatsApp data or directly to the SQLite database
3. The Go accesses the WhatsApp API and keeps the SQLite database up to date
4. Data flows back through the chain to Claude
5. When sending messages, the request flows from Claude through the MCP server to the Go bridge and to WhatsApp

## Troubleshooting

- If you encounter permission issues when running uv, you may need to add it to your PATH or use the full path to the executable.
- Make sure both the Go application and the Python server are running for the integration to work properly.

### Authentication Issues

- **QR Code Not Displaying**: If the QR code doesn't appear, try restarting the authentication script. If issues persist, check if your terminal supports displaying QR codes.
- **WhatsApp Already Logged In**: If your session is already active, the Go bridge will automatically reconnect without showing a QR code.
- **Device Limit Reached**: WhatsApp limits the number of linked devices. If you reach this limit, you'll need to remove an existing device from WhatsApp on your phone (Settings > Linked Devices).
- **No Messages Loading**: After initial authentication, it can take several minutes for your message history to load, especially if you have many chats.
- **WhatsApp Out of Sync**: If your WhatsApp messages get out of sync with the bridge, delete both database files (`whatsapp-bridge/store/messages.db` and `whatsapp-bridge/store/whatsapp.db`) and restart the bridge to re-authenticate.

### Database Encryption Issues

- **"Failed to open database" error**: Ensure CGO is enabled (`export CGO_ENABLED=1`) and you have a C compiler installed
- **"File is encrypted or is not a database" error**: This means you're trying to open an encrypted database without the correct key. Check your encryption key environment variables or key files
- **Migration issues**: If migration fails, check that the original database exists and is not already encrypted
- **Lost encryption keys**: Without your encryption keys, your data cannot be recovered. Always backup your key files (`store/.messages_key` and `store/.session_key`)
- **Key file permissions**: Ensure key files have restricted permissions (`chmod 600 store/.messages_key store/.session_key`)

### Encryption Key Management

To backup your encryption keys:
```bash
# Create a secure backup directory
mkdir -p ~/whatsapp-mcp-backup
chmod 700 ~/whatsapp-mcp-backup

# Copy key files
cp whatsapp-bridge/store/.messages_key ~/whatsapp-mcp-backup/
cp whatsapp-bridge/store/.session_key ~/whatsapp-mcp-backup/
chmod 600 ~/whatsapp-mcp-backup/*
```

To restore from backup:
```bash
# Copy keys back to store directory
cp ~/whatsapp-mcp-backup/.messages_key whatsapp-bridge/store/
cp ~/whatsapp-mcp-backup/.session_key whatsapp-bridge/store/
chmod 600 whatsapp-bridge/store/.messages_key whatsapp-bridge/store/.session_key
```

For additional Claude Desktop integration troubleshooting, see the [MCP documentation](https://modelcontextprotocol.io/quickstart/server#claude-for-desktop-integration-issues). The documentation includes helpful tips for checking logs and resolving common issues.
