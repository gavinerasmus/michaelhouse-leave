# WhatsApp AI Agents System

This system allows you to add AI-powered agents to WhatsApp chats that can automatically respond to messages with customizable personalities and behaviors.

## 🚀 Quick Start

### 1. Set up an Agent for a Chat

1. **Start the bridge once**: This will automatically create `agents/chat-mappings.json` with all your active chats
2. **Check the mapping file**: View `agents/chat-mappings.json` to see chat names and their folder names
3. **Create agent directory**: For "Notties AI" group, create:
   ```
   agents/chat-configs/Notties_AI/
   ```
4. **Copy template files**:
   ```bash
   cp agents/templates/group-assistant/* agents/chat-configs/Notties_AI/
   ```

### 2. Configure Your Agent

Edit `agents/chat-configs/Notties_AI/config.json`:

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

### 3. Customize Agent Personality

Edit `agents/chat-configs/Notties_AI/context.md` to define your agent's personality, knowledge, and behavior.

### 4. Start the Bridge

```bash
cd whatsapp-bridge
./whatsapp-bridge
```

The agent will now monitor messages and respond according to your configuration!

## 📁 Directory Structure

```
agents/
├── chat-mappings.json      # JID to folder name mappings (auto-generated)
├── chat-configs/           # Per-chat configurations
│   ├── Notties_AI/         # Example: "Notties AI" group  
│   │   ├── config.json     # Agent settings
│   │   ├── context.md      # Agent personality & instructions
│   │   ├── examples.md     # Example responses (optional)
│   │   └── memory.json     # Persistent memory (auto-created)
│   └── My_Friend_John/     # Example: individual chat
├── templates/              # Template configurations
│   ├── group-assistant/    # For group chats
│   └── personal-assistant/ # For individual chats
└── shared/                 # Shared resources
    ├── common-instructions.md
    └── response-formats.md
```

## ⚙️ Configuration Options

### config.json Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `enabled` | Whether the agent is active | `true` |
| `response_rate` | Probability of responding (0.0-1.0) | `0.3` |
| `min_time_between` | Minimum seconds between responses | `60` |
| `max_response_delay` | Maximum delay before responding | `15` |
| `api_endpoint` | AI API endpoint URL | - |
| `api_key` | API authentication key | - |
| `model_name` | AI model to use | - |

### Response Rate Guidelines
- **0.1-0.2**: Very selective (only important questions)
- **0.3-0.4**: Balanced (recommended for groups)
- **0.5-0.7**: Active participant
- **0.8-1.0**: Very responsive (best for personal chats)

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

## 📝 Writing Agent Context

The `context.md` file defines your agent's personality. Include:

### Essential Sections
- **Personality**: How the agent should behave
- **Role**: What the agent is designed to do
- **Communication Style**: Tone, emoji usage, response length
- **Topics**: What to engage with and avoid
- **Guidelines**: Specific rules for this chat

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
```

## 🎯 Pre-configured Examples

### "Notties AI" Group
- **Focus**: AI/tech discussions
- **Style**: Knowledgeable, enthusiastic about AI
- **Response rate**: 40% (balanced engagement)
- **Specialties**: ML/AI questions, tech news, coding help
- **JID**: `120363420411363539@g.us`

Located at: `agents/chat-configs/Notties_AI/`

## 🔧 Troubleshooting

### Agent Not Responding
1. Check `config.json` has `"enabled": true`
2. Verify the chat JID directory name format
3. Ensure `response_rate` > 0
4. Check bridge logs for error messages

### Finding Chat Names and JIDs
- Check `agents/chat-mappings.json` after running the bridge once
- Use API endpoint: `GET http://localhost:8080/api/chats`
- Format: Groups end in `@g.us`, individuals in `@s.whatsapp.net`

### Directory Naming
Chat names are automatically converted to safe directory names:
- Replace special characters with underscores
- Limit length to 50 characters
- Ensure uniqueness by adding numbers if needed
- Example: "Notties AI" → `Notties_AI`

## 🔒 Security Notes

- Keep API keys secure and never commit them to git
- Each agent only sees messages from its configured chat
- No cross-chat information sharing
- Agents respect user privacy

## 🔮 Future Enhancements

- [ ] Full AI API integration (OpenAI, Claude, etc.)
- [ ] Advanced memory and learning capabilities
- [ ] Multi-language support
- [ ] Voice message responses
- [ ] Image analysis and response
- [ ] Scheduled messages and reminders
- [ ] Web dashboard for management

## 📞 Support

For help with configuration or issues:
1. Check this README
2. Review the template configurations
3. Examine bridge logs for error messages
4. Test with simple configurations first

---

Enjoy your AI-powered WhatsApp experience! 🤖✨