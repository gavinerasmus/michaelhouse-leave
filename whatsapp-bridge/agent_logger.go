package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// AgentLogEntry represents a single log entry in the agent's decision-making process
type AgentLogEntry struct {
	Timestamp      time.Time              `json:"timestamp"`
	ChatJID        string                 `json:"chat_jid"`
	ChatName       string                 `json:"chat_name,omitempty"`
	Stage          string                 `json:"stage"`           // "received", "analysis", "decision", "response"
	MessageID      string                 `json:"message_id,omitempty"`
	Sender         string                 `json:"sender,omitempty"`
	MessageContent string                 `json:"message_content,omitempty"`
	Logic          map[string]interface{} `json:"logic,omitempty"` // Agent's reasoning and analysis
	Response       string                 `json:"response,omitempty"`
	Error          string                 `json:"error,omitempty"`
}

// AgentLogger handles structured logging of agent interactions and decision-making
type AgentLogger struct {
	logDir string
	mu     sync.Mutex
}

// NewAgentLogger creates a new agent logger
func NewAgentLogger(baseDir string) (*AgentLogger, error) {
	logDir := filepath.Join(baseDir, "agent-logs")

	// Create logs directory if it doesn't exist
	if err := os.MkdirAll(logDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create agent logs directory: %w", err)
	}

	return &AgentLogger{
		logDir: logDir,
	}, nil
}

// LogReceivedMessage logs when a message is received
func (al *AgentLogger) LogReceivedMessage(chatJID, chatName, messageID, sender, content string) error {
	entry := AgentLogEntry{
		Timestamp:      time.Now(),
		ChatJID:        chatJID,
		ChatName:       chatName,
		Stage:          "received",
		MessageID:      messageID,
		Sender:         sender,
		MessageContent: content,
		Logic: map[string]interface{}{
			"message_length": len(content),
			"has_content":    content != "",
		},
	}

	return al.writeLogEntry(chatJID, entry)
}

// LogAnalysis logs the agent's analysis of the message
func (al *AgentLogger) LogAnalysis(chatJID, chatName string, analysis map[string]interface{}) error {
	entry := AgentLogEntry{
		Timestamp: time.Now(),
		ChatJID:   chatJID,
		ChatName:  chatName,
		Stage:     "analysis",
		Logic:     analysis,
	}

	return al.writeLogEntry(chatJID, entry)
}

// LogDecision logs the agent's decision (should respond, why/why not)
func (al *AgentLogger) LogDecision(chatJID, chatName string, decision map[string]interface{}) error {
	entry := AgentLogEntry{
		Timestamp: time.Now(),
		ChatJID:   chatJID,
		ChatName:  chatName,
		Stage:     "decision",
		Logic:     decision,
	}

	return al.writeLogEntry(chatJID, entry)
}

// LogResponse logs the generated response
func (al *AgentLogger) LogResponse(chatJID, chatName, messageID, response string, logic map[string]interface{}) error {
	entry := AgentLogEntry{
		Timestamp:  time.Now(),
		ChatJID:    chatJID,
		ChatName:   chatName,
		Stage:      "response",
		MessageID:  messageID,
		Response:   response,
		Logic:      logic,
	}

	return al.writeLogEntry(chatJID, entry)
}

// LogError logs an error that occurred during agent processing
func (al *AgentLogger) LogError(chatJID, chatName, stage, errorMsg string) error {
	entry := AgentLogEntry{
		Timestamp: time.Now(),
		ChatJID:   chatJID,
		ChatName:  chatName,
		Stage:     stage,
		Error:     errorMsg,
	}

	return al.writeLogEntry(chatJID, entry)
}

// LogLeaveRequest logs specifically for leave request processing with detailed logic
func (al *AgentLogger) LogLeaveRequest(chatJID, chatName, messageContent string, extractedInfo map[string]interface{}, missingFields []string, nextAction string) error {
	logic := map[string]interface{}{
		"intent":          "leave_request",
		"message_content": messageContent,
		"extracted_info":  extractedInfo,
		"missing_fields":  missingFields,
		"next_action":     nextAction,
		"analysis_detail": "",
	}

	// Build detailed analysis text
	var analysisDetail string
	if len(extractedInfo) > 0 {
		analysisDetail += "Found information:\n"
		for key, value := range extractedInfo {
			analysisDetail += fmt.Sprintf("  - %s: %v\n", key, value)
		}
	}

	if len(missingFields) > 0 {
		analysisDetail += "\nMissing required information:\n"
		for _, field := range missingFields {
			analysisDetail += fmt.Sprintf("  - %s\n", field)
		}
	}

	analysisDetail += fmt.Sprintf("\nNext action: %s\n", nextAction)
	logic["analysis_detail"] = analysisDetail

	entry := AgentLogEntry{
		Timestamp:      time.Now(),
		ChatJID:        chatJID,
		ChatName:       chatName,
		Stage:          "leave_request_analysis",
		MessageContent: messageContent,
		Logic:          logic,
	}

	return al.writeLogEntry(chatJID, entry)
}

// writeLogEntry writes a log entry to the appropriate file
func (al *AgentLogger) writeLogEntry(chatJID string, entry AgentLogEntry) error {
	al.mu.Lock()
	defer al.mu.Unlock()

	// Create a daily log file for each chat
	date := time.Now().Format("2006-01-02")
	// Sanitize JID for filename (replace @ and other special chars)
	sanitizedJID := filepath.Base(chatJID)
	logFile := filepath.Join(al.logDir, fmt.Sprintf("%s_%s.jsonl", sanitizedJID, date))

	// Open file in append mode
	f, err := os.OpenFile(logFile, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("failed to open log file: %w", err)
	}
	defer f.Close()

	// Write JSON line
	jsonData, err := json.Marshal(entry)
	if err != nil {
		return fmt.Errorf("failed to marshal log entry: %w", err)
	}

	if _, err := f.Write(append(jsonData, '\n')); err != nil {
		return fmt.Errorf("failed to write log entry: %w", err)
	}

	return nil
}

// GetChatLogs retrieves all log entries for a specific chat and date
func (al *AgentLogger) GetChatLogs(chatJID, date string) ([]AgentLogEntry, error) {
	sanitizedJID := filepath.Base(chatJID)
	logFile := filepath.Join(al.logDir, fmt.Sprintf("%s_%s.jsonl", sanitizedJID, date))

	data, err := os.ReadFile(logFile)
	if err != nil {
		if os.IsNotExist(err) {
			return []AgentLogEntry{}, nil // No logs for this date
		}
		return nil, fmt.Errorf("failed to read log file: %w", err)
	}

	// Parse JSONL (JSON Lines format)
	var entries []AgentLogEntry
	lines := make([]byte, 0, len(data))
	for _, b := range data {
		if b == '\n' {
			if len(lines) > 0 {
				var entry AgentLogEntry
				if err := json.Unmarshal(lines, &entry); err == nil {
					entries = append(entries, entry)
				}
				lines = lines[:0]
			}
		} else {
			lines = append(lines, b)
		}
	}

	// Handle last line if no trailing newline
	if len(lines) > 0 {
		var entry AgentLogEntry
		if err := json.Unmarshal(lines, &entry); err == nil {
			entries = append(entries, entry)
		}
	}

	return entries, nil
}

// GenerateHumanReadableLog creates a human-readable version of the logs
func (al *AgentLogger) GenerateHumanReadableLog(chatJID, date string) (string, error) {
	entries, err := al.GetChatLogs(chatJID, date)
	if err != nil {
		return "", err
	}

	if len(entries) == 0 {
		return fmt.Sprintf("No agent logs found for %s on %s\n", chatJID, date), nil
	}

	var output string
	output += fmt.Sprintf("=== Agent Logs for %s (%s) ===\n\n", chatJID, date)

	for i, entry := range entries {
		output += fmt.Sprintf("[%d] %s - Stage: %s\n", i+1, entry.Timestamp.Format("15:04:05"), entry.Stage)

		if entry.Sender != "" {
			output += fmt.Sprintf("    Sender: %s\n", entry.Sender)
		}

		if entry.MessageContent != "" {
			output += fmt.Sprintf("    Message: %s\n", entry.MessageContent)
		}

		if len(entry.Logic) > 0 {
			output += "    Logic/Analysis:\n"
			for key, value := range entry.Logic {
				if key == "analysis_detail" {
					output += fmt.Sprintf("      %v\n", value)
				} else {
					output += fmt.Sprintf("      %s: %v\n", key, value)
				}
			}
		}

		if entry.Response != "" {
			output += fmt.Sprintf("    Response: %s\n", entry.Response)
		}

		if entry.Error != "" {
			output += fmt.Sprintf("    Error: %s\n", entry.Error)
		}

		output += "\n"
	}

	return output, nil
}
