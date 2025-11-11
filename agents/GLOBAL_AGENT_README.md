# Global Agent Configuration

The WhatsApp bridge now supports a **global agent** that can respond to messages in any chat, not just specific chats with dedicated configurations.

## How It Works

The agent system uses a **priority-based fallback** approach:

1. **Chat-Specific Config** (Priority 1): If a chat has its own configuration in `agents/chat-configs/{chat_name}/`, that config is used
2. **Global Config** (Priority 2): If no chat-specific config exists, the global agent configuration is used
3. **No Agent** (Priority 3): If neither exists, no agent responds

This means you can have a global agent that responds to all chats, but override it with specific configurations for individual chats.

## Configuration Files

### Global Agent Files

Located in the `agents/` directory:

- **`global-config.json`**: Global agent settings (API keys, response behavior)
- **`global-context.md`**: Global agent personality and instructions
- **`global-examples.md`** (optional): Example responses for the global agent

### Chat-Specific Files

Located in `agents/chat-configs/{chat_name}/`:

- **`config.json`**: Chat-specific agent settings
- **`context.md`**: Chat-specific agent personality
- **`examples.md`** (optional): Chat-specific examples

## Global Configuration Options

### global-config.json

```json
{
  "enabled": true,                    // Turn global agent on/off
  "response_rate": 0.8,               // Probability of responding (0.0-1.0)
  "min_time_between": 5,              // Minimum seconds between responses
  "max_response_delay": 3,            // Maximum delay before responding
  "api_endpoint": "https://api.anthropic.com/v1/messages",
  "api_key": "${ANTHROPIC_API_KEY}",  // API key (supports env variables)
  "model_name": "claude-3-haiku-20240307",
  "priority": "fallback"              // Priority level (currently just documentation)
}
```

### Key Settings

| Setting | Description | Recommended Value |
|---------|-------------|-------------------|
| `enabled` | Master on/off switch for global agent | `true` to enable, `false` to disable |
| `response_rate` | How often the agent responds (0.0-1.0) | `0.3-0.5` for groups, `0.7-0.9` for personal |
| `min_time_between` | Cooldown period between responses (seconds) | `5-30` for groups, `1-5` for personal |
| `max_response_delay` | Maximum artificial delay before responding | `2-5` seconds for natural feel |

## Use Cases

### 1. Global Agent Only

Set up just the global config to have an agent respond to all chats:

```bash
# Enable global agent
agents/
  ├── global-config.json    (enabled: true)
  └── global-context.md
```

**Result**: Agent responds to all chats based on global settings.

### 2. Mixed Configuration

Have a global agent but override specific chats:

```bash
agents/
  ├── global-config.json       (enabled: true, response_rate: 0.3)
  ├── global-context.md
  └── chat-configs/
      ├── 27603174174/
      │   ├── config.json      (enabled: true, response_rate: 0.9)
      │   └── context.md       (custom personality)
      └── Work_Group/
          ├── config.json      (enabled: false)
          └── context.md
```

**Result**:
- Most chats use global agent (30% response rate)
- Chat `27603174174` uses custom config (90% response rate, custom personality)
- `Work_Group` has agent disabled (no responses)

### 3. Disable Global Agent

Turn off global agent but keep chat-specific agents:

```bash
# In global-config.json
{
  "enabled": false,
  ...
}
```

**Result**: Only chats with specific configurations will have agent responses.

## Turning the Global Agent On/Off

### Method 1: Edit the Config File

```bash
# Edit agents/global-config.json
{
  "enabled": false,    # Change to true to enable, false to disable
  ...
}
```

### Method 2: Remove the Config File

```bash
# Disable by renaming or removing
mv agents/global-config.json agents/global-config.json.disabled

# Re-enable by restoring
mv agents/global-config.json.disabled agents/global-config.json
```

## Current Global Agent Identity

The global agent is configured as **"Crazy Like The Fox"** (or "Fox" for short):

- Friendly and helpful AI assistant
- Responds to all types of chats (groups and personal)
- Adapts communication style based on context
- Technical knowledge about AI and coding
- Warm, conversational tone

You can customize this by editing `agents/global-context.md`.

## Testing the Global Agent

1. **Enable the global agent**:
   ```bash
   # Ensure global-config.json has "enabled": true
   ```

2. **Restart the bridge**:
   ```bash
   cd whatsapp-bridge
   CGO_ENABLED=1 go run main.go
   ```

3. **Send a test message** to any chat that doesn't have a specific config

4. **Check the logs** for debug output:
   ```
   [DEBUG] No chat-specific config found, checking global config
   [DEBUG] Global config file found
   [DEBUG] Using global config for {chat_jid}
   ```

## Priority Override Example

If you want the global agent to respond to most chats but NOT a specific chat:

```bash
# Create a disabled config for that specific chat
mkdir -p agents/chat-configs/Specific_Chat
echo '{"enabled": false}' > agents/chat-configs/Specific_Chat/config.json
```

This will prevent the global agent from responding to `Specific_Chat` even though it's enabled globally.

## Best Practices

1. **Start Conservative**: Begin with a low `response_rate` (0.2-0.3) for the global agent
2. **Monitor Groups**: Watch group chats to ensure the agent isn't too chatty
3. **Use Chat-Specific Overrides**: Create specific configs for important chats
4. **Test Thoroughly**: Send test messages to verify behavior before full deployment
5. **Adjust Based on Feedback**: Fine-tune response rates based on actual usage

## Troubleshooting

### Global agent not responding

1. Check `global-config.json` has `"enabled": true`
2. Verify API key is configured correctly
3. Check debug logs for errors
4. Ensure `response_rate` > 0

### Global agent responding too much

1. Lower `response_rate` in `global-config.json`
2. Increase `min_time_between` cooldown period
3. Create disabled configs for specific chats

### Want to disable for specific chat

Create a chat-specific config with `"enabled": false`:

```bash
mkdir -p agents/chat-configs/{chat_name}
echo '{"enabled": false}' > agents/chat-configs/{chat_name}/config.json
```

## Architecture Notes

The configuration loading follows this flow:

1. Agent receives message
2. `LoadAgentConfig(chatJID)` is called
3. Tries `loadChatSpecificConfig()` first
4. If not found, tries `loadGlobalConfig()`
5. If found, caches the config for that chat
6. Agent uses the loaded config to decide whether to respond

This means the first message to each chat will load the appropriate config (chat-specific or global), and subsequent messages will use the cached config until the bridge restarts.
