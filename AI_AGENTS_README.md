# WhatsApp Global AI Agent System

This system allows you to add a global AI-powered agent that can automatically respond to messages across all WhatsApp chats with a customizable personality and behavior.

## 🚀 Quick Start

### 1. Configure the Global Agent

Edit `agents/global-config.json`:

```json
{
  "enabled": true,
  "response_rate": 0.3,
  "min_time_between": 60,
  "max_response_delay": 15,
  "api_endpoint": "https://api.anthropic.com/v1/messages",
  "api_key": "your-api-key-here",
  "model_name": "claude-3-haiku-20240307"
}
```

### 2. Customize Agent Personality

Edit `agents/global-context.md` to define your agent's personality, knowledge, and behavior.

### 3. (Optional) Add Examples

Edit `agents/global-examples.md` to provide example responses.

### 4. Start the Bridge

```bash
cd whatsapp-bridge
./whatsapp-bridge
```

The global agent will now monitor all messages and respond according to your configuration!

## 📁 Directory Structure

```
agents/
├── global-config.json      # Global agent configuration
├── global-context.md       # Global agent personality & instructions
├── global-examples.md      # Example responses (optional)
├── templates/              # Template configurations (for reference)
│   ├── group-assistant/    # Example for group chat agents
│   └── personal-assistant/ # Example for personal chat agents
└── shared/                 # Shared resources
    ├── common-instructions.md
    └── response-formats.md
```

## ⚙️ Configuration Options

### global-config.json Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `enabled` | Whether the global agent is active | `true` |
| `response_rate` | Probability of responding to any message (0.0-1.0) | `0.3` |
| `min_time_between` | Minimum seconds between responses (global) | `60` |
| `max_response_delay` | Maximum delay before responding | `15` |
| `api_endpoint` | AI API endpoint URL | - |
| `api_key` | API authentication key | - |
| `model_name` | AI model to use | - |

### Response Rate Guidelines
- **0.1-0.2**: Very selective (responds rarely across all chats)
- **0.3-0.4**: Balanced (recommended for general use)
- **0.5-0.7**: Active participant (responds frequently)
- **0.8-1.0**: Very responsive (responds to most messages)

**Note**: Response rate and timing apply globally across ALL chats, not per-chat.

## 🤖 Supported AI Providers

### Anthropic Claude
```json
{
  "api_endpoint": "https://api.anthropic.com/v1/messages",
  "model_name": "claude-3-haiku-20240307"
}
```

### OpenAI
```json
{
  "api_endpoint": "https://api.openai.com/v1/chat/completions", 
  "model_name": "gpt-3.5-turbo"
}
```

*Note: Currently using placeholder responses. Full AI integration coming soon!*

## 📝 Writing Global Agent Context

The `global-context.md` file defines your agent's personality. Include:

### Essential Sections
- **Personality**: How the agent should behave across all conversations
- **Role**: What the agent is designed to do
- **Communication Style**: Tone, emoji usage, response length
- **Topics**: What to engage with and avoid
- **Guidelines**: Global rules for all chats

### Example Context Structure
```markdown
# My Agent Name

You are a [role] for [chat description].

## Personality
- Be [trait 1]
- Show [trait 2]  
- Avoid [behavior]

## Your Role
- Help with [task 1]
- Provide [service 2]
- Engage in [activity 3]

## Communication Style
- [Response length preference]
- [Emoji usage guidelines]
- [Formality level]

## Important
- You respond to ALL chats, not specific ones
- Adapt your responses to context while maintaining consistent personality
```

## 🔧 Troubleshooting

### Agent Not Responding
1. Check `agents/global-config.json` has `"enabled": true`
2. Ensure `response_rate` > 0
3. Verify `min_time_between` hasn't been violated (applies globally)
4. Check bridge logs for `[DEBUG]` messages showing decision flow
5. Remember: Global agent responds to ALL chats based on probability

### Testing the Agent
- Start the bridge and send messages from WhatsApp
- Check bridge console logs for `[DEBUG]` output
- Agent decisions are logged showing:
  - Whether agent is enabled
  - Response rate probability check
  - Time since last response
  - Final decision to respond or not

## 🔒 Security Notes

- Keep API keys secure and never commit them to git
- Use environment variable expansion: `"${ANTHROPIC_API_KEY}"` in config
- Global agent sees messages from all chats
- Agent decisions are logged locally for debugging
- Respects user privacy - only processes messages when bridge is running

## 🔮 Future Enhancements

- [ ] Full AI API integration (OpenAI, Claude, etc.) - Currently uses placeholder responses
- [ ] Per-chat personality adaptation while maintaining global config
- [ ] Advanced memory and learning capabilities
- [ ] Multi-language support
- [ ] Voice message responses
- [ ] Image analysis and response
- [ ] Scheduled messages and reminders
- [ ] Web dashboard for agent management

## 📞 Support

For help with configuration or issues:
1. Check this README
2. Review the template configurations
3. Examine bridge logs for error messages
4. Test with simple configurations first

---

Enjoy your AI-powered WhatsApp experience! 🤖✨