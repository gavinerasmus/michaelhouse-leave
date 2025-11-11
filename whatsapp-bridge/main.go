package main

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	mathrand "math/rand"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"reflect"
	"strconv"
	"strings"
	"syscall"
	"time"

	_ "github.com/mutecomm/go-sqlcipher/v4"
	"github.com/mdp/qrterminal"

	"bytes"

	"github.com/joho/godotenv"
	"go.mau.fi/whatsmeow"
	waProto "go.mau.fi/whatsmeow/binary/proto"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	"google.golang.org/protobuf/proto"
)

// Message represents a chat message for our client
type Message struct {
	Time      time.Time
	Sender    string
	Content   string
	IsFromMe  bool
	MediaType string
	Filename  string
}

// AgentConfig represents the configuration for a chat-specific AI agent
type AgentConfig struct {
	Enabled          bool    `json:"enabled"`
	ResponseRate     float64 `json:"response_rate"`     // Probability of responding (0.0 to 1.0)
	MinTimeBetween   int     `json:"min_time_between"`  // Minimum seconds between responses
	MaxResponseDelay int     `json:"max_response_delay"` // Maximum delay before responding
	APIEndpoint      string  `json:"api_endpoint"`      // AI API endpoint
	APIKey           string  `json:"api_key"`           // API key (if needed)
	ModelName        string  `json:"model_name"`        // AI model to use
}

// AgentContext represents the context and memory for an AI agent
type AgentContext struct {
	Instructions string                 `json:"instructions"` // Agent personality and instructions
	Examples     string                 `json:"examples"`     // Example responses
	Memory       map[string]interface{} `json:"memory"`       // Persistent memory
	LastResponse time.Time              `json:"last_response"` // Last response time
}

// Anthropic API structures
type AnthropicMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type AnthropicRequest struct {
	Model     string             `json:"model"`
	MaxTokens int                `json:"max_tokens"`
	Messages  []AnthropicMessage `json:"messages"`
	System    string             `json:"system,omitempty"`
}

type AnthropicContentBlock struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type AnthropicResponse struct {
	ID      string                  `json:"id"`
	Type    string                  `json:"type"`
	Role    string                  `json:"role"`
	Content []AnthropicContentBlock `json:"content"`
	Model   string                  `json:"model"`
	Error   *AnthropicError         `json:"error,omitempty"`
}

type AnthropicError struct {
	Type    string `json:"type"`
	Message string `json:"message"`
}

// AgentManager manages the global AI agent
type AgentManager struct {
	config       *AgentConfig
	context      *AgentContext
	client       *whatsmeow.Client
	messageStore *MessageStore
	logger       waLog.Logger
}

// Key management functions
func getOrCreateEncryptionKey(envVar, keyFile string) (string, error) {
	// First try environment variable
	if key := os.Getenv(envVar); key != "" {
		return key, nil
	}
	
	// Try to read from key file
	if data, err := os.ReadFile(keyFile); err == nil {
		return strings.TrimSpace(string(data)), nil
	}
	
	// Generate new key and save it
	key, err := generateSecureKey()
	if err != nil {
		return "", fmt.Errorf("failed to generate encryption key: %v", err)
	}
	
	// Create directory if it doesn't exist
	if err := os.MkdirAll(filepath.Dir(keyFile), 0700); err != nil {
		return "", fmt.Errorf("failed to create key directory: %v", err)
	}
	
	// Save key to file with restricted permissions
	if err := os.WriteFile(keyFile, []byte(key), 0600); err != nil {
		return "", fmt.Errorf("failed to save encryption key: %v", err)
	}
	
	fmt.Printf("Generated new encryption key and saved to %s\n", keyFile)
	fmt.Printf("IMPORTANT: Backup this key file - without it you cannot decrypt your data!\n")
	
	return key, nil
}

func generateSecureKey() (string, error) {
	key := make([]byte, 32) // 256 bits
	if _, err := rand.Read(key); err != nil {
		return "", err
	}
	return hex.EncodeToString(key), nil
}

func buildEncryptedDSN(dbPath, key string) string {
	// URL encode the key for safety
	encodedKey := url.QueryEscape(key)
	
	// Check if key is hex-encoded (64 characters for 32 bytes)
	if len(key) == 64 {
		// Use hex format for better performance
		return fmt.Sprintf("%s?_pragma_key=x'%s'&_pragma_cipher_page_size=4096&_foreign_keys=on", dbPath, key)
	} else {
		// Use passphrase format
		return fmt.Sprintf("%s?_pragma_key=%s&_pragma_cipher_page_size=4096&_foreign_keys=on", dbPath, encodedKey)
	}
}

// Database handler for storing message history
type MessageStore struct {
	db *sql.DB
}

// Initialize message store
func NewMessageStore() (*MessageStore, error) {
	// Create directory for database if it doesn't exist
	if err := os.MkdirAll("store", 0755); err != nil {
		return nil, fmt.Errorf("failed to create store directory: %v", err)
	}

	// Get or create encryption key for messages database
	key, err := getOrCreateEncryptionKey("WHATSAPP_MESSAGES_KEY", "store/.messages_key")
	if err != nil {
		return nil, fmt.Errorf("failed to get encryption key: %v", err)
	}

	// Build encrypted DSN
	dsn := buildEncryptedDSN("file:store/messages.db", key)
	
	// Open encrypted SQLite database for messages
	db, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to open message database: %v", err)
	}

	// Create tables if they don't exist
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS chats (
			jid TEXT PRIMARY KEY,
			name TEXT,
			last_message_time TIMESTAMP
		);
		
		CREATE TABLE IF NOT EXISTS messages (
			id TEXT,
			chat_jid TEXT,
			sender TEXT,
			content TEXT,
			timestamp TIMESTAMP,
			is_from_me BOOLEAN,
			media_type TEXT,
			filename TEXT,
			url TEXT,
			media_key BLOB,
			file_sha256 BLOB,
			file_enc_sha256 BLOB,
			file_length INTEGER,
			PRIMARY KEY (id, chat_jid),
			FOREIGN KEY (chat_jid) REFERENCES chats(jid)
		);
		
		CREATE TABLE IF NOT EXISTS reactions (
			id TEXT PRIMARY KEY,
			message_id TEXT,
			chat_jid TEXT,
			reactor TEXT,
			emoji TEXT,
			timestamp TIMESTAMP,
			is_from_me BOOLEAN,
			FOREIGN KEY (chat_jid) REFERENCES chats(jid)
		);
	`)
	if err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to create tables: %v", err)
	}

	// Migration: Drop and recreate reactions table if it has foreign key constraints
	_, err = db.Exec("DROP TABLE IF EXISTS reactions")
	if err != nil {
		fmt.Printf("Warning: Failed to drop reactions table during migration: %v\n", err)
	}
	
	// Recreate reactions table without message foreign key constraint
	_, err = db.Exec(`
		CREATE TABLE reactions (
			id TEXT PRIMARY KEY,
			message_id TEXT,
			chat_jid TEXT,
			reactor TEXT,
			emoji TEXT,
			timestamp TIMESTAMP,
			is_from_me BOOLEAN,
			FOREIGN KEY (chat_jid) REFERENCES chats(jid)
		)
	`)
	if err != nil {
		fmt.Printf("Warning: Failed to recreate reactions table: %v\n", err)
	}

	return &MessageStore{db: db}, nil
}

// Close the database connection
func (store *MessageStore) Close() error {
	return store.db.Close()
}

// Store a chat in the database
func (store *MessageStore) StoreChat(jid, name string, lastMessageTime time.Time) error {
	_, err := store.db.Exec(
		"INSERT OR REPLACE INTO chats (jid, name, last_message_time) VALUES (?, ?, ?)",
		jid, name, lastMessageTime,
	)
	return err
}

// Store a message in the database
func (store *MessageStore) StoreMessage(id, chatJID, sender, content string, timestamp time.Time, isFromMe bool,
	mediaType, filename, url string, mediaKey, fileSHA256, fileEncSHA256 []byte, fileLength uint64) error {
	// Only store if there's actual content or media
	if content == "" && mediaType == "" {
		return nil
	}

	_, err := store.db.Exec(
		`INSERT OR REPLACE INTO messages 
		(id, chat_jid, sender, content, timestamp, is_from_me, media_type, filename, url, media_key, file_sha256, file_enc_sha256, file_length) 
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		id, chatJID, sender, content, timestamp, isFromMe, mediaType, filename, url, mediaKey, fileSHA256, fileEncSHA256, fileLength,
	)
	return err
}

// Get messages from a chat
func (store *MessageStore) GetMessages(chatJID string, limit int) ([]Message, error) {
	rows, err := store.db.Query(
		"SELECT sender, content, timestamp, is_from_me, media_type, filename FROM messages WHERE chat_jid = ? ORDER BY timestamp DESC LIMIT ?",
		chatJID, limit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var messages []Message
	for rows.Next() {
		var msg Message
		var timestamp time.Time
		err := rows.Scan(&msg.Sender, &msg.Content, &timestamp, &msg.IsFromMe, &msg.MediaType, &msg.Filename)
		if err != nil {
			return nil, err
		}
		msg.Time = timestamp
		messages = append(messages, msg)
	}

	return messages, nil
}

// Get all chats
func (store *MessageStore) GetChats() (map[string]time.Time, error) {
	rows, err := store.db.Query("SELECT jid, last_message_time FROM chats ORDER BY last_message_time DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	chats := make(map[string]time.Time)
	for rows.Next() {
		var jid string
		var lastMessageTime time.Time
		err := rows.Scan(&jid, &lastMessageTime)
		if err != nil {
			return nil, err
		}
		chats[jid] = lastMessageTime
	}

	return chats, nil
}

// Store a reaction in the database
func (store *MessageStore) StoreReaction(id, messageID, chatJID, reactor, emoji string, timestamp time.Time, isFromMe bool) error {
	_, err := store.db.Exec(
		"INSERT OR REPLACE INTO reactions (id, message_id, chat_jid, reactor, emoji, timestamp, is_from_me) VALUES (?, ?, ?, ?, ?, ?, ?)",
		id, messageID, chatJID, reactor, emoji, timestamp, isFromMe,
	)
	return err
}

// Get reactions for a specific message
func (store *MessageStore) GetReactionsForMessage(messageID, chatJID string) ([]map[string]interface{}, error) {
	rows, err := store.db.Query(
		"SELECT id, reactor, emoji, timestamp, is_from_me FROM reactions WHERE message_id = ? AND chat_jid = ? ORDER BY timestamp ASC",
		messageID, chatJID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var reactions []map[string]interface{}
	for rows.Next() {
		var id, reactor, emoji string
		var timestamp time.Time
		var isFromMe bool
		err := rows.Scan(&id, &reactor, &emoji, &timestamp, &isFromMe)
		if err != nil {
			return nil, err
		}
		reactions = append(reactions, map[string]interface{}{
			"id":         id,
			"reactor":    reactor,
			"emoji":      emoji,
			"timestamp":  timestamp,
			"is_from_me": isFromMe,
		})
	}

	return reactions, nil
}

// Get all reactions in a chat
func (store *MessageStore) GetReactionsInChat(chatJID string, limit int) ([]map[string]interface{}, error) {
	rows, err := store.db.Query(
		"SELECT id, message_id, reactor, emoji, timestamp, is_from_me FROM reactions WHERE chat_jid = ? ORDER BY timestamp DESC LIMIT ?",
		chatJID, limit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var reactions []map[string]interface{}
	for rows.Next() {
		var id, messageID, reactor, emoji string
		var timestamp time.Time
		var isFromMe bool
		err := rows.Scan(&id, &messageID, &reactor, &emoji, &timestamp, &isFromMe)
		if err != nil {
			return nil, err
		}
		reactions = append(reactions, map[string]interface{}{
			"id":         id,
			"message_id": messageID,
			"reactor":    reactor,
			"emoji":      emoji,
			"timestamp":  timestamp,
			"is_from_me": isFromMe,
		})
	}

	return reactions, nil
}

// Extract text content from a message
func extractTextContent(msg *waProto.Message) string {
	if msg == nil {
		return ""
	}

	// Try to get text content
	if text := msg.GetConversation(); text != "" {
		return text
	} else if extendedText := msg.GetExtendedTextMessage(); extendedText != nil {
		return extendedText.GetText()
	}

	// For now, we're ignoring non-text messages
	return ""
}

// Extract reaction info from a message
func extractReactionInfo(msg *waProto.Message) (targetMessageID string, emoji string) {
	if msg == nil {
		return "", ""
	}

	// Check for reaction message
	if reaction := msg.GetReactionMessage(); reaction != nil {
		targetID := reaction.GetKey().GetID()
		emoji := reaction.GetText()
		return targetID, emoji
	}

	return "", ""
}

// NewAgentManager creates a new agent manager
func NewAgentManager(client *whatsmeow.Client, messageStore *MessageStore, logger waLog.Logger) *AgentManager {
	am := &AgentManager{
		client:       client,
		messageStore: messageStore,
		logger:       logger,
	}

	// Load global config
	config, context, err := am.loadGlobalConfig()
	if err != nil {
		logger.Warnf("Failed to load global agent config: %v", err)
	} else if config != nil {
		am.config = config
		am.context = context
		logger.Infof("Global agent loaded - Enabled: %v", config.Enabled)
	}

	return am
}

// LoadAgentConfig returns the global agent configuration
func (am *AgentManager) LoadAgentConfig() (*AgentConfig, *AgentContext, error) {
	if am.config == nil || am.context == nil {
		// Try to reload
		config, context, err := am.loadGlobalConfig()
		if err != nil {
			return nil, nil, err
		}
		am.config = config
		am.context = context
	}
	return am.config, am.context, nil
}

// loadGlobalConfig loads the global agent configuration
func (am *AgentManager) loadGlobalConfig() (*AgentConfig, *AgentContext, error) {
	configPath := filepath.Join("..", "agents", "global-config.json")
	contextPath := filepath.Join("..", "agents", "global-context.md")
	examplesPath := filepath.Join("..", "agents", "global-examples.md")

	fmt.Printf("[DEBUG] Looking for global config at: %s\n", configPath)

	// Load config
	var config AgentConfig
	if configData, err := os.ReadFile(configPath); err == nil {
		fmt.Printf("[DEBUG] Global config file found, size: %d bytes\n", len(configData))
		if err := json.Unmarshal(configData, &config); err != nil {
			fmt.Printf("[DEBUG] Failed to parse global config: %v\n", err)
			return nil, nil, fmt.Errorf("failed to parse global config: %v", err)
		}
		fmt.Printf("[DEBUG] Global config parsed - Enabled: %v, APIKey configured: %v\n", config.Enabled, config.APIKey != "")
		// Expand environment variables in API key
		originalAPIKey := config.APIKey
		config.APIKey = os.ExpandEnv(config.APIKey)
		fmt.Printf("[DEBUG] Global APIKey expanded from env: %v\n", originalAPIKey != config.APIKey)
	} else {
		fmt.Printf("[DEBUG] Global config file not found: %v\n", err)
		// No global config found
		return nil, nil, nil
	}

	// Load context
	var context AgentContext
	if contextData, err := os.ReadFile(contextPath); err == nil {
		context.Instructions = string(contextData)
		fmt.Printf("[DEBUG] Global context loaded, length: %d chars\n", len(context.Instructions))
	} else {
		fmt.Printf("[DEBUG] Global context not found: %v\n", err)
	}

	// Load examples if they exist
	if examplesData, err := os.ReadFile(examplesPath); err == nil {
		context.Examples = string(examplesData)
		fmt.Printf("[DEBUG] Global examples loaded, length: %d chars\n", len(context.Examples))
	}

	// Initialize memory if not exists
	if context.Memory == nil {
		context.Memory = make(map[string]interface{})
	}

	return &config, &context, nil
}

// ShouldRespond determines if the global agent should respond to a message
func (am *AgentManager) ShouldRespond(chatJID, messageContent string, isFromMe bool) bool {
	fmt.Printf("[DEBUG] ShouldRespond called for chat %s, isFromMe: %v\n", chatJID, isFromMe)

	// Don't respond to our own messages
	if isFromMe {
		fmt.Printf("[DEBUG] Skipping own message\n")
		return false
	}

	config, context, err := am.LoadAgentConfig()
	if err != nil {
		fmt.Printf("[DEBUG] Failed to load global agent config: %v\n", err)
		am.logger.Warnf("Failed to load global agent config: %v", err)
		return false
	}

	// No agent configured
	if config == nil {
		fmt.Printf("[DEBUG] No global agent configured\n")
		return false
	}

	fmt.Printf("[DEBUG] Global agent config loaded - Enabled: %v, ResponseRate: %f, MinTimeBetween: %d\n",
		config.Enabled, config.ResponseRate, config.MinTimeBetween)

	// Agent disabled
	if !config.Enabled {
		fmt.Printf("[DEBUG] Global agent disabled\n")
		return false
	}

	// Check minimum time between responses
	timeSinceLastResponse := time.Since(context.LastResponse)
	minTime := time.Duration(config.MinTimeBetween) * time.Second
	if timeSinceLastResponse < minTime {
		fmt.Printf("[DEBUG] Too soon to respond for chat %s - Time since last: %v, Min time: %v\n", 
			chatJID, timeSinceLastResponse, minTime)
		return false
	}
	
	// Check response rate probability
	randomValue := mathrand.Float64()
	if randomValue > config.ResponseRate {
		fmt.Printf("[DEBUG] Random check failed for chat %s - Random: %f, ResponseRate: %f\n", 
			chatJID, randomValue, config.ResponseRate)
		return false
	}
	
	fmt.Printf("[DEBUG] All checks passed for chat %s - Agent should respond\n", chatJID)
	return true
}

// GenerateResponse generates an AI response for a message
func (am *AgentManager) GenerateResponse(chatJID, messageContent, senderName string) (string, error) {
	fmt.Printf("[DEBUG] GenerateResponse called for chat %s, message: '%s', sender: %s\n", chatJID, messageContent, senderName)

	config, context, err := am.LoadAgentConfig()
	if err != nil {
		fmt.Printf("[DEBUG] Failed to load global agent config in GenerateResponse: %v\n", err)
		return "", err
	}

	if config == nil {
		fmt.Printf("[DEBUG] No global agent config found in GenerateResponse\n")
		return "", fmt.Errorf("no global agent configured")
	}

	fmt.Printf("[DEBUG] Config loaded in GenerateResponse - API configured: %v, APIEndpoint: %s\n",
		config.APIKey != "", config.APIEndpoint)

	// Get recent message history for context (last 15 messages)
	recentMessages, err := am.messageStore.GetMessages(chatJID, 15)
	if err != nil {
		fmt.Printf("[DEBUG] Failed to get recent messages for %s: %v\n", chatJID, err)
		am.logger.Warnf("Failed to get recent messages: %v", err)
	} else {
		fmt.Printf("[DEBUG] Retrieved %d recent messages for chat %s\n", len(recentMessages), chatJID)
	}

	// Build conversation history context (excluding the current message)
	var conversationContext string
	if len(recentMessages) > 0 {
		conversationContext = "\n\n## Recent Conversation History (for context only - already responded to)\n\n"
		for i := len(recentMessages) - 1; i >= 0; i-- {
			msg := recentMessages[i]
			if msg.Content == "" {
				continue
			}

			sender := "User"
			if msg.IsFromMe {
				sender = "You (previous response)"
			} else if msg.Sender != "" {
				sender = "User"
			}

			conversationContext += fmt.Sprintf("%s: %s\n", sender, msg.Content)
		}
		conversationContext += "\n## Current Message (respond to this)\n\n"
	}

	// Build enhanced system prompt with conversation context
	enhancedSystemPrompt := context.Instructions
	if conversationContext != "" {
		enhancedSystemPrompt = context.Instructions + conversationContext
	}

	// Build messages array with only the current message
	messages := []AnthropicMessage{
		{
			Role:    "user",
			Content: messageContent,
		},
	}

	fmt.Printf("[DEBUG] Built message with %d chars of conversation context\n", len(conversationContext))

	// Call Anthropic API
	response, err := am.callAnthropicAPI(config, enhancedSystemPrompt, messages)
	if err != nil {
		fmt.Printf("[DEBUG] API call failed for %s: %v\n", chatJID, err)
		am.logger.Errorf("Failed to call Anthropic API: %v", err)
		return "", err
	}

	fmt.Printf("[DEBUG] Generated response for %s: '%s'\n", chatJID, response)

	// Update last response time
	context.LastResponse = time.Now()
	fmt.Printf("[DEBUG] Updated last response time for %s\n", chatJID)

	return response, nil
}

// callAnthropicAPI makes a request to the Anthropic Claude API
func (am *AgentManager) callAnthropicAPI(config *AgentConfig, systemPrompt string, messages []AnthropicMessage) (string, error) {
	// Validate configuration
	if config.APIKey == "" {
		return "", fmt.Errorf("API key is not configured")
	}
	if config.APIEndpoint == "" {
		return "", fmt.Errorf("API endpoint is not configured")
	}

	// Prepare the API request
	reqBody := AnthropicRequest{
		Model:     config.ModelName,
		MaxTokens: 1024,
		Messages:  messages,
		System:    systemPrompt,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %v", err)
	}

	fmt.Printf("[DEBUG] Calling Anthropic API at %s with model %s\n", config.APIEndpoint, config.ModelName)
	fmt.Printf("[DEBUG] System prompt length: %d chars\n", len(systemPrompt))
	fmt.Printf("[DEBUG] Messages count: %d\n", len(messages))

	// Create HTTP request
	req, err := http.NewRequest("POST", config.APIEndpoint, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %v", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-api-key", config.APIKey)
	req.Header.Set("anthropic-version", "2023-06-01")

	// Make the request
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to make API request: %v", err)
	}
	defer resp.Body.Close()

	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read response body: %v", err)
	}

	fmt.Printf("[DEBUG] API response status: %d\n", resp.StatusCode)

	// Check for non-200 status
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
	}

	// Parse response
	var apiResp AnthropicResponse
	if err := json.Unmarshal(body, &apiResp); err != nil {
		return "", fmt.Errorf("failed to unmarshal response: %v", err)
	}

	// Check for API errors
	if apiResp.Error != nil {
		return "", fmt.Errorf("API error: %s - %s", apiResp.Error.Type, apiResp.Error.Message)
	}

	// Extract text from response
	if len(apiResp.Content) == 0 {
		return "", fmt.Errorf("no content in API response")
	}

	responseText := apiResp.Content[0].Text
	fmt.Printf("[DEBUG] API returned response: '%s'\n", responseText)

	return responseText, nil
}

// SendAgentResponse sends an AI-generated response to a chat
func (am *AgentManager) SendAgentResponse(chatJID, response string) error {
	// Add a small delay to make it seem more natural
	config, _, _ := am.LoadAgentConfig()
	if config != nil && config.MaxResponseDelay > 0 {
		delay := mathrand.Intn(config.MaxResponseDelay) + 1
		time.Sleep(time.Duration(delay) * time.Second)
	}
	
	// Send the message
	success, message := sendWhatsAppMessage(am.client, chatJID, response, "")
	if !success {
		return fmt.Errorf("failed to send agent response: %s", message)
	}
	
	am.logger.Infof("Agent sent response to %s: %s", chatJID, response)
	return nil
}

// SendMessageResponse represents the response for the send message API
type SendMessageResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

// SendMessageRequest represents the request body for the send message API
type SendMessageRequest struct {
	Recipient string `json:"recipient"`
	Message   string `json:"message"`
	MediaPath string `json:"media_path,omitempty"`
}

// SendReactionRequest represents the request body for the send reaction API
type SendReactionRequest struct {
	Recipient   string `json:"recipient"`
	MessageID   string `json:"message_id"`
	Emoji       string `json:"emoji"`
}

// SendReactionResponse represents the response for the send reaction API
type SendReactionResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

// Function to send a WhatsApp message
func sendWhatsAppMessage(client *whatsmeow.Client, recipient string, message string, mediaPath string) (bool, string) {
	if !client.IsConnected() {
		return false, "Not connected to WhatsApp"
	}

	// Create JID for recipient
	var recipientJID types.JID
	var err error

	// Check if recipient is a JID
	isJID := strings.Contains(recipient, "@")

	if isJID {
		// Parse the JID string
		recipientJID, err = types.ParseJID(recipient)
		if err != nil {
			return false, fmt.Sprintf("Error parsing JID: %v", err)
		}
	} else {
		// Create JID from phone number
		recipientJID = types.JID{
			User:   recipient,
			Server: "s.whatsapp.net", // For personal chats
		}
	}

	msg := &waProto.Message{}

	// Check if we have media to send
	if mediaPath != "" {
		// Read media file
		mediaData, err := os.ReadFile(mediaPath)
		if err != nil {
			return false, fmt.Sprintf("Error reading media file: %v", err)
		}

		// Determine media type and mime type based on file extension
		fileExt := strings.ToLower(mediaPath[strings.LastIndex(mediaPath, ".")+1:])
		var mediaType whatsmeow.MediaType
		var mimeType string

		// Handle different media types
		switch fileExt {
		// Image types
		case "jpg", "jpeg":
			mediaType = whatsmeow.MediaImage
			mimeType = "image/jpeg"
		case "png":
			mediaType = whatsmeow.MediaImage
			mimeType = "image/png"
		case "gif":
			mediaType = whatsmeow.MediaImage
			mimeType = "image/gif"
		case "webp":
			mediaType = whatsmeow.MediaImage
			mimeType = "image/webp"

		// Audio types
		case "ogg":
			mediaType = whatsmeow.MediaAudio
			mimeType = "audio/ogg; codecs=opus"

		// Video types
		case "mp4":
			mediaType = whatsmeow.MediaVideo
			mimeType = "video/mp4"
		case "avi":
			mediaType = whatsmeow.MediaVideo
			mimeType = "video/avi"
		case "mov":
			mediaType = whatsmeow.MediaVideo
			mimeType = "video/quicktime"

		// Document types (for any other file type)
		default:
			mediaType = whatsmeow.MediaDocument
			mimeType = "application/octet-stream"
		}

		// Upload media to WhatsApp servers
		resp, err := client.Upload(context.Background(), mediaData, mediaType)
		if err != nil {
			return false, fmt.Sprintf("Error uploading media: %v", err)
		}

		fmt.Println("Media uploaded", resp)

		// Create the appropriate message type based on media type
		switch mediaType {
		case whatsmeow.MediaImage:
			msg.ImageMessage = &waProto.ImageMessage{
				Caption:       proto.String(message),
				Mimetype:      proto.String(mimeType),
				URL:           &resp.URL,
				DirectPath:    &resp.DirectPath,
				MediaKey:      resp.MediaKey,
				FileEncSHA256: resp.FileEncSHA256,
				FileSHA256:    resp.FileSHA256,
				FileLength:    &resp.FileLength,
			}
		case whatsmeow.MediaAudio:
			// Handle ogg audio files
			var seconds uint32 = 30 // Default fallback
			var waveform []byte = nil

			// Try to analyze the ogg file
			if strings.Contains(mimeType, "ogg") {
				analyzedSeconds, analyzedWaveform, err := analyzeOggOpus(mediaData)
				if err == nil {
					seconds = analyzedSeconds
					waveform = analyzedWaveform
				} else {
					return false, fmt.Sprintf("Failed to analyze Ogg Opus file: %v", err)
				}
			} else {
				fmt.Printf("Not an Ogg Opus file: %s\n", mimeType)
			}

			msg.AudioMessage = &waProto.AudioMessage{
				Mimetype:      proto.String(mimeType),
				URL:           &resp.URL,
				DirectPath:    &resp.DirectPath,
				MediaKey:      resp.MediaKey,
				FileEncSHA256: resp.FileEncSHA256,
				FileSHA256:    resp.FileSHA256,
				FileLength:    &resp.FileLength,
				Seconds:       proto.Uint32(seconds),
				PTT:           proto.Bool(true),
				Waveform:      waveform,
			}
		case whatsmeow.MediaVideo:
			msg.VideoMessage = &waProto.VideoMessage{
				Caption:       proto.String(message),
				Mimetype:      proto.String(mimeType),
				URL:           &resp.URL,
				DirectPath:    &resp.DirectPath,
				MediaKey:      resp.MediaKey,
				FileEncSHA256: resp.FileEncSHA256,
				FileSHA256:    resp.FileSHA256,
				FileLength:    &resp.FileLength,
			}
		case whatsmeow.MediaDocument:
			msg.DocumentMessage = &waProto.DocumentMessage{
				Title:         proto.String(mediaPath[strings.LastIndex(mediaPath, "/")+1:]),
				Caption:       proto.String(message),
				Mimetype:      proto.String(mimeType),
				URL:           &resp.URL,
				DirectPath:    &resp.DirectPath,
				MediaKey:      resp.MediaKey,
				FileEncSHA256: resp.FileEncSHA256,
				FileSHA256:    resp.FileSHA256,
				FileLength:    &resp.FileLength,
			}
		}
	} else {
		msg.Conversation = proto.String(message)
	}

	// Send message
	_, err = client.SendMessage(context.Background(), recipientJID, msg)

	if err != nil {
		return false, fmt.Sprintf("Error sending message: %v", err)
	}

	return true, fmt.Sprintf("Message sent to %s", recipient)
}

// Function to send a WhatsApp reaction
func sendWhatsAppReaction(client *whatsmeow.Client, recipient string, messageID string, emoji string) (bool, string) {
	if !client.IsConnected() {
		return false, "Not connected to WhatsApp"
	}

	// Create JID for recipient
	var recipientJID types.JID
	var err error

	// Check if recipient is a JID
	isJID := strings.Contains(recipient, "@")

	if isJID {
		// Parse the JID string
		recipientJID, err = types.ParseJID(recipient)
		if err != nil {
			return false, fmt.Sprintf("Error parsing JID: %v", err)
		}
	} else {
		// Create JID from phone number
		recipientJID = types.JID{
			User:   recipient,
			Server: "s.whatsapp.net", // For personal chats
		}
	}

	// Create reaction message
	reactionMsg := &waProto.Message{
		ReactionMessage: &waProto.ReactionMessage{
			Key: &waProto.MessageKey{
				RemoteJID: proto.String(recipientJID.String()),
				ID:        proto.String(messageID),
				FromMe:    proto.Bool(false), // The message we're reacting to is not from us
			},
			Text: proto.String(emoji),
		},
	}

	// Send reaction
	_, err = client.SendMessage(context.Background(), recipientJID, reactionMsg)

	if err != nil {
		return false, fmt.Sprintf("Error sending reaction: %v", err)
	}

	return true, fmt.Sprintf("Reaction %s sent to message %s for %s", emoji, messageID, recipient)
}

// Extract media info from a message
func extractMediaInfo(msg *waProto.Message) (mediaType string, filename string, url string, mediaKey []byte, fileSHA256 []byte, fileEncSHA256 []byte, fileLength uint64) {
	if msg == nil {
		return "", "", "", nil, nil, nil, 0
	}

	// Check for image message
	if img := msg.GetImageMessage(); img != nil {
		return "image", "image_" + time.Now().Format("20060102_150405") + ".jpg",
			img.GetURL(), img.GetMediaKey(), img.GetFileSHA256(), img.GetFileEncSHA256(), img.GetFileLength()
	}

	// Check for video message
	if vid := msg.GetVideoMessage(); vid != nil {
		return "video", "video_" + time.Now().Format("20060102_150405") + ".mp4",
			vid.GetURL(), vid.GetMediaKey(), vid.GetFileSHA256(), vid.GetFileEncSHA256(), vid.GetFileLength()
	}

	// Check for audio message
	if aud := msg.GetAudioMessage(); aud != nil {
		return "audio", "audio_" + time.Now().Format("20060102_150405") + ".ogg",
			aud.GetURL(), aud.GetMediaKey(), aud.GetFileSHA256(), aud.GetFileEncSHA256(), aud.GetFileLength()
	}

	// Check for document message
	if doc := msg.GetDocumentMessage(); doc != nil {
		filename := doc.GetFileName()
		if filename == "" {
			filename = "document_" + time.Now().Format("20060102_150405")
		}
		return "document", filename,
			doc.GetURL(), doc.GetMediaKey(), doc.GetFileSHA256(), doc.GetFileEncSHA256(), doc.GetFileLength()
	}

	return "", "", "", nil, nil, nil, 0
}

// Handle regular incoming messages with media support
func handleMessage(client *whatsmeow.Client, messageStore *MessageStore, msg *events.Message, agentManager *AgentManager, logger waLog.Logger) {
	// Save message to database
	chatJID := msg.Info.Chat.String()
	sender := msg.Info.Sender.User

	// Get appropriate chat name (pass nil for conversation since we don't have one for regular messages)
	name := GetChatName(client, messageStore, msg.Info.Chat, chatJID, nil, sender, logger)

	// Update chat in database with the message timestamp (keeps last message time updated)
	err := messageStore.StoreChat(chatJID, name, msg.Info.Timestamp)
	if err != nil {
		logger.Warnf("Failed to store chat: %v", err)
	}

	// Check if this is a reaction message
	targetMessageID, emoji := extractReactionInfo(msg.Message)
	if targetMessageID != "" && emoji != "" {
		// This is a reaction message
		reactionID := msg.Info.ID
		err = messageStore.StoreReaction(
			reactionID,
			targetMessageID,
			chatJID,
			sender,
			emoji,
			msg.Info.Timestamp,
			msg.Info.IsFromMe,
		)

		if err != nil {
			logger.Warnf("Failed to store reaction: %v", err)
		} else {
			// Log reaction reception
			timestamp := msg.Info.Timestamp.Format("2006-01-02 15:04:05")
			direction := "←"
			if msg.Info.IsFromMe {
				direction = "→"
			}
			fmt.Printf("[%s] %s %s reacted %s to message %s\n", timestamp, direction, sender, emoji, targetMessageID)
		}
		return
	}

	// Extract text content
	content := extractTextContent(msg.Message)

	// Extract media info
	mediaType, filename, url, mediaKey, fileSHA256, fileEncSHA256, fileLength := extractMediaInfo(msg.Message)

	// Skip if there's no content and no media
	if content == "" && mediaType == "" {
		return
	}

	// Store message in database
	err = messageStore.StoreMessage(
		msg.Info.ID,
		chatJID,
		sender,
		content,
		msg.Info.Timestamp,
		msg.Info.IsFromMe,
		mediaType,
		filename,
		url,
		mediaKey,
		fileSHA256,
		fileEncSHA256,
		fileLength,
	)

	if err != nil {
		logger.Warnf("Failed to store message: %v", err)
	} else {
		// Log message reception
		timestamp := msg.Info.Timestamp.Format("2006-01-02 15:04:05")
		direction := "←"
		if msg.Info.IsFromMe {
			direction = "→"
		}

		// Log based on message type
		if mediaType != "" {
			fmt.Printf("[%s] %s %s: [%s: %s] %s\n", timestamp, direction, sender, mediaType, filename, content)
		} else if content != "" {
			fmt.Printf("[%s] %s %s: %s\n", timestamp, direction, sender, content)
		}
		
		// Check if agent should respond to this message (only for text messages for now)
		fmt.Printf("[DEBUG] Checking agent response for chat %s, content: '%s', agentManager: %v\n", chatJID, content, agentManager != nil)
		if agentManager != nil && content != "" {
			fmt.Printf("[DEBUG] Calling ShouldRespond for chat %s\n", chatJID)
			if agentManager.ShouldRespond(chatJID, content, msg.Info.IsFromMe) {
				fmt.Printf("[DEBUG] Agent should respond to chat %s, generating response...\n", chatJID)
				go func() {
					// Generate and send response in a goroutine to avoid blocking
					response, err := agentManager.GenerateResponse(chatJID, content, sender)
					if err != nil {
						fmt.Printf("[DEBUG] Failed to generate agent response for %s: %v\n", chatJID, err)
						logger.Warnf("Failed to generate agent response: %v", err)
						return
					}
					
					fmt.Printf("[DEBUG] Sending agent response to %s: %s\n", chatJID, response)
					if err := agentManager.SendAgentResponse(chatJID, response); err != nil {
						fmt.Printf("[DEBUG] Failed to send agent response to %s: %v\n", chatJID, err)
						logger.Warnf("Failed to send agent response: %v", err)
					} else {
						fmt.Printf("[DEBUG] Successfully sent agent response to %s\n", chatJID)
					}
				}()
			} else {
				fmt.Printf("[DEBUG] Agent should NOT respond to chat %s\n", chatJID)
			}
		} else {
			if agentManager == nil {
				fmt.Printf("[DEBUG] No agentManager available\n")
			}
			if content == "" {
				fmt.Printf("[DEBUG] Empty content, skipping agent check\n")
			}
		}
	}
}

// DownloadMediaRequest represents the request body for the download media API
type DownloadMediaRequest struct {
	MessageID string `json:"message_id"`
	ChatJID   string `json:"chat_jid"`
}

// DownloadMediaResponse represents the response for the download media API
type DownloadMediaResponse struct {
	Success  bool   `json:"success"`
	Message  string `json:"message"`
	Filename string `json:"filename,omitempty"`
	Path     string `json:"path,omitempty"`
}

// Store additional media info in the database
func (store *MessageStore) StoreMediaInfo(id, chatJID, url string, mediaKey, fileSHA256, fileEncSHA256 []byte, fileLength uint64) error {
	_, err := store.db.Exec(
		"UPDATE messages SET url = ?, media_key = ?, file_sha256 = ?, file_enc_sha256 = ?, file_length = ? WHERE id = ? AND chat_jid = ?",
		url, mediaKey, fileSHA256, fileEncSHA256, fileLength, id, chatJID,
	)
	return err
}

// Get media info from the database
func (store *MessageStore) GetMediaInfo(id, chatJID string) (string, string, string, []byte, []byte, []byte, uint64, error) {
	var mediaType, filename, url string
	var mediaKey, fileSHA256, fileEncSHA256 []byte
	var fileLength uint64

	err := store.db.QueryRow(
		"SELECT media_type, filename, url, media_key, file_sha256, file_enc_sha256, file_length FROM messages WHERE id = ? AND chat_jid = ?",
		id, chatJID,
	).Scan(&mediaType, &filename, &url, &mediaKey, &fileSHA256, &fileEncSHA256, &fileLength)

	return mediaType, filename, url, mediaKey, fileSHA256, fileEncSHA256, fileLength, err
}

// MediaDownloader implements the whatsmeow.DownloadableMessage interface
type MediaDownloader struct {
	URL           string
	DirectPath    string
	MediaKey      []byte
	FileLength    uint64
	FileSHA256    []byte
	FileEncSHA256 []byte
	MediaType     whatsmeow.MediaType
}

// GetDirectPath implements the DownloadableMessage interface
func (d *MediaDownloader) GetDirectPath() string {
	return d.DirectPath
}

// GetURL implements the DownloadableMessage interface
func (d *MediaDownloader) GetURL() string {
	return d.URL
}

// GetMediaKey implements the DownloadableMessage interface
func (d *MediaDownloader) GetMediaKey() []byte {
	return d.MediaKey
}

// GetFileLength implements the DownloadableMessage interface
func (d *MediaDownloader) GetFileLength() uint64 {
	return d.FileLength
}

// GetFileSHA256 implements the DownloadableMessage interface
func (d *MediaDownloader) GetFileSHA256() []byte {
	return d.FileSHA256
}

// GetFileEncSHA256 implements the DownloadableMessage interface
func (d *MediaDownloader) GetFileEncSHA256() []byte {
	return d.FileEncSHA256
}

// GetMediaType implements the DownloadableMessage interface
func (d *MediaDownloader) GetMediaType() whatsmeow.MediaType {
	return d.MediaType
}

// Function to download media from a message
func downloadMedia(client *whatsmeow.Client, messageStore *MessageStore, messageID, chatJID string) (bool, string, string, string, error) {
	// Query the database for the message
	var mediaType, filename, url string
	var mediaKey, fileSHA256, fileEncSHA256 []byte
	var fileLength uint64
	var err error

	// First, check if we already have this file
	chatDir := fmt.Sprintf("store/%s", strings.ReplaceAll(chatJID, ":", "_"))
	localPath := ""

	// Get media info from the database
	mediaType, filename, url, mediaKey, fileSHA256, fileEncSHA256, fileLength, err = messageStore.GetMediaInfo(messageID, chatJID)

	if err != nil {
		// Try to get basic info if extended info isn't available
		err = messageStore.db.QueryRow(
			"SELECT media_type, filename FROM messages WHERE id = ? AND chat_jid = ?",
			messageID, chatJID,
		).Scan(&mediaType, &filename)

		if err != nil {
			return false, "", "", "", fmt.Errorf("failed to find message: %v", err)
		}
	}

	// Check if this is a media message
	if mediaType == "" {
		return false, "", "", "", fmt.Errorf("not a media message")
	}

	// Create directory for the chat if it doesn't exist
	if err := os.MkdirAll(chatDir, 0755); err != nil {
		return false, "", "", "", fmt.Errorf("failed to create chat directory: %v", err)
	}

	// Generate a local path for the file
	localPath = fmt.Sprintf("%s/%s", chatDir, filename)

	// Get absolute path
	absPath, err := filepath.Abs(localPath)
	if err != nil {
		return false, "", "", "", fmt.Errorf("failed to get absolute path: %v", err)
	}

	// Check if file already exists
	if _, err := os.Stat(localPath); err == nil {
		// File exists, return it
		return true, mediaType, filename, absPath, nil
	}

	// If we don't have all the media info we need, we can't download
	if url == "" || len(mediaKey) == 0 || len(fileSHA256) == 0 || len(fileEncSHA256) == 0 || fileLength == 0 {
		return false, "", "", "", fmt.Errorf("incomplete media information for download")
	}

	fmt.Printf("Attempting to download media for message %s in chat %s...\n", messageID, chatJID)

	// Extract direct path from URL
	directPath := extractDirectPathFromURL(url)

	// Create a downloader that implements DownloadableMessage
	var waMediaType whatsmeow.MediaType
	switch mediaType {
	case "image":
		waMediaType = whatsmeow.MediaImage
	case "video":
		waMediaType = whatsmeow.MediaVideo
	case "audio":
		waMediaType = whatsmeow.MediaAudio
	case "document":
		waMediaType = whatsmeow.MediaDocument
	default:
		return false, "", "", "", fmt.Errorf("unsupported media type: %s", mediaType)
	}

	downloader := &MediaDownloader{
		URL:           url,
		DirectPath:    directPath,
		MediaKey:      mediaKey,
		FileLength:    fileLength,
		FileSHA256:    fileSHA256,
		FileEncSHA256: fileEncSHA256,
		MediaType:     waMediaType,
	}

	// Download the media using whatsmeow client
	mediaData, err := client.Download(context.Background(), downloader)
	if err != nil {
		return false, "", "", "", fmt.Errorf("failed to download media: %v", err)
	}

	// Save the downloaded media to file
	if err := os.WriteFile(localPath, mediaData, 0644); err != nil {
		return false, "", "", "", fmt.Errorf("failed to save media file: %v", err)
	}

	fmt.Printf("Successfully downloaded %s media to %s (%d bytes)\n", mediaType, absPath, len(mediaData))
	return true, mediaType, filename, absPath, nil
}

// Extract direct path from a WhatsApp media URL
func extractDirectPathFromURL(url string) string {
	// The direct path is typically in the URL, we need to extract it
	// Example URL: https://mmg.whatsapp.net/v/t62.7118-24/13812002_698058036224062_3424455886509161511_n.enc?ccb=11-4&oh=...

	// Find the path part after the domain
	parts := strings.SplitN(url, ".net/", 2)
	if len(parts) < 2 {
		return url // Return original URL if parsing fails
	}

	pathPart := parts[1]

	// Remove query parameters
	pathPart = strings.SplitN(pathPart, "?", 2)[0]

	// Create proper direct path format
	return "/" + pathPart
}

// Start a REST API server to expose the WhatsApp client functionality
func startRESTServer(client *whatsmeow.Client, messageStore *MessageStore, port int) {
	// Handler for sending messages
	http.HandleFunc("/api/send", func(w http.ResponseWriter, r *http.Request) {
		// Only allow POST requests
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Parse the request body
		var req SendMessageRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid request format", http.StatusBadRequest)
			return
		}

		// Validate request
		if req.Recipient == "" {
			http.Error(w, "Recipient is required", http.StatusBadRequest)
			return
		}

		if req.Message == "" && req.MediaPath == "" {
			http.Error(w, "Message or media path is required", http.StatusBadRequest)
			return
		}

		fmt.Println("Received request to send message", req.Message, req.MediaPath)

		// Send the message
		success, message := sendWhatsAppMessage(client, req.Recipient, req.Message, req.MediaPath)
		fmt.Println("Message sent", success, message)
		// Set response headers
		w.Header().Set("Content-Type", "application/json")

		// Set appropriate status code
		if !success {
			w.WriteHeader(http.StatusInternalServerError)
		}

		// Send response
		json.NewEncoder(w).Encode(SendMessageResponse{
			Success: success,
			Message: message,
		})
	})

	// Handler for downloading media
	http.HandleFunc("/api/download", func(w http.ResponseWriter, r *http.Request) {
		// Only allow POST requests
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Parse the request body
		var req DownloadMediaRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid request format", http.StatusBadRequest)
			return
		}

		// Validate request
		if req.MessageID == "" || req.ChatJID == "" {
			http.Error(w, "Message ID and Chat JID are required", http.StatusBadRequest)
			return
		}

		// Download the media
		success, mediaType, filename, path, err := downloadMedia(client, messageStore, req.MessageID, req.ChatJID)

		// Set response headers
		w.Header().Set("Content-Type", "application/json")

		// Handle download result
		if !success || err != nil {
			errMsg := "Unknown error"
			if err != nil {
				errMsg = err.Error()
			}

			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(DownloadMediaResponse{
				Success: false,
				Message: fmt.Sprintf("Failed to download media: %s", errMsg),
			})
			return
		}

		// Send successful response
		json.NewEncoder(w).Encode(DownloadMediaResponse{
			Success:  true,
			Message:  fmt.Sprintf("Successfully downloaded %s media", mediaType),
			Filename: filename,
			Path:     path,
		})
	})

	// Handler for listing messages
	http.HandleFunc("/api/messages", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Get query parameters
		chatJID := r.URL.Query().Get("chat_jid")
		limit := 20
		if l := r.URL.Query().Get("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
				limit = parsed
			}
		}

		// Get messages
		messages, err := messageStore.GetMessages(chatJID, limit)
		if err != nil {
			http.Error(w, fmt.Sprintf("Failed to get messages: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(messages)
	})

	// Handler for listing chats
	http.HandleFunc("/api/chats", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Get chats
		chats, err := messageStore.GetChats()
		if err != nil {
			http.Error(w, fmt.Sprintf("Failed to get chats: %v", err), http.StatusInternalServerError)
			return
		}

		// Convert to a more useful format
		type ChatInfo struct {
			JID              string    `json:"jid"`
			Name             string    `json:"name"`
			LastMessageTime  time.Time `json:"last_message_time"`
			IsGroup          bool      `json:"is_group"`
		}

		var chatList []ChatInfo
		for jid, lastTime := range chats {
			// Get chat name from database
			var name string
			err := messageStore.db.QueryRow("SELECT name FROM chats WHERE jid = ?", jid).Scan(&name)
			if err != nil {
				name = jid // Fallback to JID
			}

			chatList = append(chatList, ChatInfo{
				JID:              jid,
				Name:             name,
				LastMessageTime:  lastTime,
				IsGroup:          strings.HasSuffix(jid, "@g.us"),
			})
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(chatList)
	})

	// Handler for sending reactions
	http.HandleFunc("/api/react", func(w http.ResponseWriter, r *http.Request) {
		// Only allow POST requests
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Parse the request body
		var req SendReactionRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid request format", http.StatusBadRequest)
			return
		}

		// Validate request
		if req.Recipient == "" {
			http.Error(w, "Recipient is required", http.StatusBadRequest)
			return
		}

		if req.MessageID == "" {
			http.Error(w, "Message ID is required", http.StatusBadRequest)
			return
		}

		if req.Emoji == "" {
			http.Error(w, "Emoji is required", http.StatusBadRequest)
			return
		}

		fmt.Printf("Received request to send reaction %s to message %s for %s\n", req.Emoji, req.MessageID, req.Recipient)

		// Send the reaction
		success, message := sendWhatsAppReaction(client, req.Recipient, req.MessageID, req.Emoji)
		fmt.Printf("Reaction sent: %t, message: %s\n", success, message)

		// Set response headers
		w.Header().Set("Content-Type", "application/json")

		// Set appropriate status code
		if !success {
			w.WriteHeader(http.StatusInternalServerError)
		}

		// Send response
		json.NewEncoder(w).Encode(SendReactionResponse{
			Success: success,
			Message: message,
		})
	})

	// Handler for getting reactions for a message
	http.HandleFunc("/api/reactions", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Get query parameters
		messageID := r.URL.Query().Get("message_id")
		chatJID := r.URL.Query().Get("chat_jid")

		if messageID == "" || chatJID == "" {
			http.Error(w, "message_id and chat_jid are required", http.StatusBadRequest)
			return
		}

		// Get reactions
		reactions, err := messageStore.GetReactionsForMessage(messageID, chatJID)
		if err != nil {
			http.Error(w, fmt.Sprintf("Failed to get reactions: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(reactions)
	})

	// Handler for getting all reactions in a chat
	http.HandleFunc("/api/chat-reactions", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Get query parameters
		chatJID := r.URL.Query().Get("chat_jid")
		limit := 50
		if l := r.URL.Query().Get("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
				limit = parsed
			}
		}

		if chatJID == "" {
			http.Error(w, "chat_jid is required", http.StatusBadRequest)
			return
		}

		// Get reactions
		reactions, err := messageStore.GetReactionsInChat(chatJID, limit)
		if err != nil {
			http.Error(w, fmt.Sprintf("Failed to get reactions: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(reactions)
	})

	// Start the server
	serverAddr := fmt.Sprintf(":%d", port)
	fmt.Printf("Starting REST API server on %s...\n", serverAddr)

	// Run server in a goroutine so it doesn't block
	go func() {
		if err := http.ListenAndServe(serverAddr, nil); err != nil {
			fmt.Printf("REST API server error: %v\n", err)
		}
	}()
}

func main() {
	// Load environment variables from .env file
	if err := godotenv.Load("../.env"); err != nil {
		fmt.Printf("Warning: Could not load .env file: %v\n", err)
	}

	// Set up logger
	logger := waLog.Stdout("Client", "INFO", true)
	logger.Infof("Starting WhatsApp client...")

	// Create database connection for storing session data
	dbLog := waLog.Stdout("Database", "INFO", true)

	// Create directory for database if it doesn't exist
	if err := os.MkdirAll("store", 0755); err != nil {
		logger.Errorf("Failed to create store directory: %v", err)
		return
	}

	// Get or create encryption key for WhatsApp session database
	sessionKey, err := getOrCreateEncryptionKey("WHATSAPP_SESSION_KEY", "store/.session_key")
	if err != nil {
		logger.Errorf("Failed to get session encryption key: %v", err)
		return
	}

	// Build encrypted DSN for session database
	sessionDSN := buildEncryptedDSN("file:store/whatsapp.db", sessionKey)
	
	container, err := sqlstore.New(context.Background(), "sqlite3", sessionDSN, dbLog)
	if err != nil {
		logger.Errorf("Failed to connect to database: %v", err)
		return
	}

	// Get device store - This contains session information
	deviceStore, err := container.GetFirstDevice(context.Background())
	if err != nil {
		if err == sql.ErrNoRows {
			// No device exists, create one
			deviceStore = container.NewDevice()
			logger.Infof("Created new device")
		} else {
			logger.Errorf("Failed to get device: %v", err)
			return
		}
	}

	// Create client instance
	client := whatsmeow.NewClient(deviceStore, logger)
	if client == nil {
		logger.Errorf("Failed to create WhatsApp client")
		return
	}

	// Initialize message store
	messageStore, err := NewMessageStore()
	if err != nil {
		logger.Errorf("Failed to initialize message store: %v", err)
		return
	}
	defer messageStore.Close()

	// Initialize AI agent manager
	agentManager := NewAgentManager(client, messageStore, logger)

	// Setup event handling for messages and history sync
	client.AddEventHandler(func(evt interface{}) {
		switch v := evt.(type) {
		case *events.Message:
			// Process regular messages
			handleMessage(client, messageStore, v, agentManager, logger)

		case *events.HistorySync:
			// Process history sync events
			handleHistorySync(client, messageStore, v, logger)

		case *events.Connected:
			logger.Infof("Connected to WhatsApp")

		case *events.LoggedOut:
			logger.Warnf("Device logged out, please scan QR code to log in again")
		}
	})

	// Create channel to track connection success
	connected := make(chan bool, 1)

	// Connect to WhatsApp
	if client.Store.ID == nil {
		// No ID stored, this is a new client, need to pair with phone
		qrChan, _ := client.GetQRChannel(context.Background())
		err = client.Connect()
		if err != nil {
			logger.Errorf("Failed to connect: %v", err)
			return
		}

		// Print QR code for pairing with phone
		for evt := range qrChan {
			if evt.Event == "code" {
				fmt.Println("\nScan this QR code with your WhatsApp app:")
				qrterminal.GenerateHalfBlock(evt.Code, qrterminal.L, os.Stdout)
			} else if evt.Event == "success" {
				connected <- true
				break
			}
		}

		// Wait for connection
		select {
		case <-connected:
			fmt.Println("\nSuccessfully connected and authenticated!")
		case <-time.After(3 * time.Minute):
			logger.Errorf("Timeout waiting for QR code scan")
			return
		}
	} else {
		// Already logged in, just connect
		err = client.Connect()
		if err != nil {
			logger.Errorf("Failed to connect: %v", err)
			return
		}
		connected <- true
	}

	// Wait a moment for connection to stabilize
	time.Sleep(2 * time.Second)

	if !client.IsConnected() {
		logger.Errorf("Failed to establish stable connection")
		return
	}

	fmt.Println("\n✓ Connected to WhatsApp! Type 'help' for commands.")

	// Start REST API server
	startRESTServer(client, messageStore, 8080)

	// Create a channel to keep the main goroutine alive
	exitChan := make(chan os.Signal, 1)
	signal.Notify(exitChan, syscall.SIGINT, syscall.SIGTERM)

	fmt.Println("REST server is running. Press Ctrl+C to disconnect and exit.")

	// Wait for termination signal
	<-exitChan

	fmt.Println("Disconnecting...")
	// Disconnect client
	client.Disconnect()
}

// GetChatName determines the appropriate name for a chat based on JID and other info
func GetChatName(client *whatsmeow.Client, messageStore *MessageStore, jid types.JID, chatJID string, conversation interface{}, sender string, logger waLog.Logger) string {
	// First, check if chat already exists in database with a name
	var existingName string
	err := messageStore.db.QueryRow("SELECT name FROM chats WHERE jid = ?", chatJID).Scan(&existingName)
	if err == nil && existingName != "" {
		// Chat exists with a name, use that
		logger.Infof("Using existing chat name for %s: %s", chatJID, existingName)
		return existingName
	}

	// Need to determine chat name
	var name string

	if jid.Server == "g.us" {
		// This is a group chat
		logger.Infof("Getting name for group: %s", chatJID)

		// Use conversation data if provided (from history sync)
		if conversation != nil {
			// Extract name from conversation if available
			// This uses type assertions to handle different possible types
			var displayName, convName *string
			// Try to extract the fields we care about regardless of the exact type
			v := reflect.ValueOf(conversation)
			if v.Kind() == reflect.Ptr && !v.IsNil() {
				v = v.Elem()

				// Try to find DisplayName field
				if displayNameField := v.FieldByName("DisplayName"); displayNameField.IsValid() && displayNameField.Kind() == reflect.Ptr && !displayNameField.IsNil() {
					dn := displayNameField.Elem().String()
					displayName = &dn
				}

				// Try to find Name field
				if nameField := v.FieldByName("Name"); nameField.IsValid() && nameField.Kind() == reflect.Ptr && !nameField.IsNil() {
					n := nameField.Elem().String()
					convName = &n
				}
			}

			// Use the name we found
			if displayName != nil && *displayName != "" {
				name = *displayName
			} else if convName != nil && *convName != "" {
				name = *convName
			}
		}

		// If we didn't get a name, try group info
		if name == "" {
			groupInfo, err := client.GetGroupInfo(jid)
			if err == nil && groupInfo.Name != "" {
				name = groupInfo.Name
			} else {
				// Fallback name for groups
				name = fmt.Sprintf("Group %s", jid.User)
			}
		}

		logger.Infof("Using group name: %s", name)
	} else {
		// This is an individual contact
		logger.Infof("Getting name for contact: %s", chatJID)

		// Just use contact info (full name)
		contact, err := client.Store.Contacts.GetContact(context.Background(), jid)
		if err == nil && contact.FullName != "" {
			name = contact.FullName
		} else if sender != "" {
			// Fallback to sender
			name = sender
		} else {
			// Last fallback to JID
			name = jid.User
		}

		logger.Infof("Using contact name: %s", name)
	}

	return name
}

// Handle history sync events
func handleHistorySync(client *whatsmeow.Client, messageStore *MessageStore, historySync *events.HistorySync, logger waLog.Logger) {
	fmt.Printf("Received history sync event with %d conversations\n", len(historySync.Data.Conversations))

	syncedCount := 0
	for _, conversation := range historySync.Data.Conversations {
		// Parse JID from the conversation
		if conversation.ID == nil {
			continue
		}

		chatJID := *conversation.ID

		// Try to parse the JID
		jid, err := types.ParseJID(chatJID)
		if err != nil {
			logger.Warnf("Failed to parse JID %s: %v", chatJID, err)
			continue
		}

		// Get appropriate chat name by passing the history sync conversation directly
		name := GetChatName(client, messageStore, jid, chatJID, conversation, "", logger)

		// Process messages
		messages := conversation.Messages
		if len(messages) > 0 {
			// Update chat with latest message timestamp
			latestMsg := messages[0]
			if latestMsg == nil || latestMsg.Message == nil {
				continue
			}

			// Get timestamp from message info
			timestamp := time.Time{}
			if ts := latestMsg.Message.GetMessageTimestamp(); ts != 0 {
				timestamp = time.Unix(int64(ts), 0)
			} else {
				continue
			}

			messageStore.StoreChat(chatJID, name, timestamp)

			// Store messages
			for _, msg := range messages {
				if msg == nil || msg.Message == nil {
					continue
				}

				// Extract text content
				var content string
				if msg.Message.Message != nil {
					if conv := msg.Message.Message.GetConversation(); conv != "" {
						content = conv
					} else if ext := msg.Message.Message.GetExtendedTextMessage(); ext != nil {
						content = ext.GetText()
					}
				}

				// Extract media info
				var mediaType, filename, url string
				var mediaKey, fileSHA256, fileEncSHA256 []byte
				var fileLength uint64

				if msg.Message.Message != nil {
					mediaType, filename, url, mediaKey, fileSHA256, fileEncSHA256, fileLength = extractMediaInfo(msg.Message.Message)
				}

				// Log the message content for debugging
				logger.Infof("Message content: %v, Media Type: %v", content, mediaType)

				// Skip messages with no content and no media
				if content == "" && mediaType == "" {
					continue
				}

				// Determine sender
				var sender string
				isFromMe := false
				if msg.Message.Key != nil {
					if msg.Message.Key.FromMe != nil {
						isFromMe = *msg.Message.Key.FromMe
					}
					if !isFromMe && msg.Message.Key.Participant != nil && *msg.Message.Key.Participant != "" {
						sender = *msg.Message.Key.Participant
					} else if isFromMe {
						sender = client.Store.ID.User
					} else {
						sender = jid.User
					}
				} else {
					sender = jid.User
				}

				// Store message
				msgID := ""
				if msg.Message.Key != nil && msg.Message.Key.ID != nil {
					msgID = *msg.Message.Key.ID
				}

				// Get message timestamp
				timestamp := time.Time{}
				if ts := msg.Message.GetMessageTimestamp(); ts != 0 {
					timestamp = time.Unix(int64(ts), 0)
				} else {
					continue
				}

				err = messageStore.StoreMessage(
					msgID,
					chatJID,
					sender,
					content,
					timestamp,
					isFromMe,
					mediaType,
					filename,
					url,
					mediaKey,
					fileSHA256,
					fileEncSHA256,
					fileLength,
				)
				if err != nil {
					logger.Warnf("Failed to store history message: %v", err)
				} else {
					syncedCount++
					// Log successful message storage
					if mediaType != "" {
						logger.Infof("Stored message: [%s] %s -> %s: [%s: %s] %s",
							timestamp.Format("2006-01-02 15:04:05"), sender, chatJID, mediaType, filename, content)
					} else {
						logger.Infof("Stored message: [%s] %s -> %s: %s",
							timestamp.Format("2006-01-02 15:04:05"), sender, chatJID, content)
					}
				}
			}
		}
	}

	fmt.Printf("History sync complete. Stored %d messages.\n", syncedCount)
}

// Request history sync from the server
func requestHistorySync(client *whatsmeow.Client) {
	if client == nil {
		fmt.Println("Client is not initialized. Cannot request history sync.")
		return
	}

	if !client.IsConnected() {
		fmt.Println("Client is not connected. Please ensure you are connected to WhatsApp first.")
		return
	}

	if client.Store.ID == nil {
		fmt.Println("Client is not logged in. Please scan the QR code first.")
		return
	}

	// Build and send a history sync request
	historyMsg := client.BuildHistorySyncRequest(nil, 100)
	if historyMsg == nil {
		fmt.Println("Failed to build history sync request.")
		return
	}

	_, err := client.SendMessage(context.Background(), types.JID{
		Server: "s.whatsapp.net",
		User:   "status",
	}, historyMsg)

	if err != nil {
		fmt.Printf("Failed to request history sync: %v\n", err)
	} else {
		fmt.Println("History sync requested. Waiting for server response...")
	}
}

// analyzeOggOpus tries to extract duration and generate a simple waveform from an Ogg Opus file
func analyzeOggOpus(data []byte) (duration uint32, waveform []byte, err error) {
	// Try to detect if this is a valid Ogg file by checking for the "OggS" signature
	// at the beginning of the file
	if len(data) < 4 || string(data[0:4]) != "OggS" {
		return 0, nil, fmt.Errorf("not a valid Ogg file (missing OggS signature)")
	}

	// Parse Ogg pages to find the last page with a valid granule position
	var lastGranule uint64
	var sampleRate uint32 = 48000 // Default Opus sample rate
	var preSkip uint16 = 0
	var foundOpusHead bool

	// Scan through the file looking for Ogg pages
	for i := 0; i < len(data); {
		// Check if we have enough data to read Ogg page header
		if i+27 >= len(data) {
			break
		}

		// Verify Ogg page signature
		if string(data[i:i+4]) != "OggS" {
			// Skip until next potential page
			i++
			continue
		}

		// Extract header fields
		granulePos := binary.LittleEndian.Uint64(data[i+6 : i+14])
		pageSeqNum := binary.LittleEndian.Uint32(data[i+18 : i+22])
		numSegments := int(data[i+26])

		// Extract segment table
		if i+27+numSegments >= len(data) {
			break
		}
		segmentTable := data[i+27 : i+27+numSegments]

		// Calculate page size
		pageSize := 27 + numSegments
		for _, segLen := range segmentTable {
			pageSize += int(segLen)
		}

		// Check if we're looking at an OpusHead packet (should be in first few pages)
		if !foundOpusHead && pageSeqNum <= 1 {
			// Look for "OpusHead" marker in this page
			pageData := data[i : i+pageSize]
			headPos := bytes.Index(pageData, []byte("OpusHead"))
			if headPos >= 0 && headPos+12 < len(pageData) {
				// Found OpusHead, extract sample rate and pre-skip
				// OpusHead format: Magic(8) + Version(1) + Channels(1) + PreSkip(2) + SampleRate(4) + ...
				headPos += 8 // Skip "OpusHead" marker
				// PreSkip is 2 bytes at offset 10
				if headPos+12 <= len(pageData) {
					preSkip = binary.LittleEndian.Uint16(pageData[headPos+10 : headPos+12])
					sampleRate = binary.LittleEndian.Uint32(pageData[headPos+12 : headPos+16])
					foundOpusHead = true
					fmt.Printf("Found OpusHead: sampleRate=%d, preSkip=%d\n", sampleRate, preSkip)
				}
			}
		}

		// Keep track of last valid granule position
		if granulePos != 0 {
			lastGranule = granulePos
		}

		// Move to next page
		i += pageSize
	}

	if !foundOpusHead {
		fmt.Println("Warning: OpusHead not found, using default values")
	}

	// Calculate duration based on granule position
	if lastGranule > 0 {
		// Formula for duration: (lastGranule - preSkip) / sampleRate
		durationSeconds := float64(lastGranule-uint64(preSkip)) / float64(sampleRate)
		duration = uint32(math.Ceil(durationSeconds))
		fmt.Printf("Calculated Opus duration from granule: %f seconds (lastGranule=%d)\n",
			durationSeconds, lastGranule)
	} else {
		// Fallback to rough estimation if granule position not found
		fmt.Println("Warning: No valid granule position found, using estimation")
		durationEstimate := float64(len(data)) / 2000.0 // Very rough approximation
		duration = uint32(durationEstimate)
	}

	// Make sure we have a reasonable duration (at least 1 second, at most 300 seconds)
	if duration < 1 {
		duration = 1
	} else if duration > 300 {
		duration = 300
	}

	// Generate waveform
	waveform = placeholderWaveform(duration)

	fmt.Printf("Ogg Opus analysis: size=%d bytes, calculated duration=%d sec, waveform=%d bytes\n",
		len(data), duration, len(waveform))

	return duration, waveform, nil
}

// min returns the smaller of x or y
func min(x, y int) int {
	if x < y {
		return x
	}
	return y
}

// placeholderWaveform generates a synthetic waveform for WhatsApp voice messages
// that appears natural with some variability based on the duration
func placeholderWaveform(duration uint32) []byte {
	// WhatsApp expects a 64-byte waveform for voice messages
	const waveformLength = 64
	waveform := make([]byte, waveformLength)

	// Seed the random number generator for consistent results with the same duration
	mathrand.Seed(int64(duration))

	// Create a more natural looking waveform with some patterns and variability
	// rather than completely random values

	// Base amplitude and frequency - longer messages get faster frequency
	baseAmplitude := 35.0
	frequencyFactor := float64(min(int(duration), 120)) / 30.0

	for i := range waveform {
		// Position in the waveform (normalized 0-1)
		pos := float64(i) / float64(waveformLength)

		// Create a wave pattern with some randomness
		// Use multiple sine waves of different frequencies for more natural look
		val := baseAmplitude * math.Sin(pos*math.Pi*frequencyFactor*8)
		val += (baseAmplitude / 2) * math.Sin(pos*math.Pi*frequencyFactor*16)

		// Add some randomness to make it look more natural
		val += (mathrand.Float64() - 0.5) * 15

		// Add some fade-in and fade-out effects
		fadeInOut := math.Sin(pos * math.Pi)
		val = val * (0.7 + 0.3*fadeInOut)

		// Center around 50 (typical voice baseline)
		val = val + 50

		// Ensure values stay within WhatsApp's expected range (0-100)
		if val < 0 {
			val = 0
		} else if val > 100 {
			val = 100
		}

		waveform[i] = byte(val)
	}

	return waveform
}
