package main

/**
 * Simplified WhatsApp Bridge - Clean Architecture
 *
 * This bridge is a PURE COMMUNICATION CHANNEL with NO business logic.
 * It forwards messages to the Leave System API and sends back responses.
 *
 * ALL business logic (leave processing, AI agent, decision making) lives in the Leave System.
 */

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/mdp/qrterminal/v3"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	waProto "go.mau.fi/whatsmeow/binary/proto"
	"google.golang.org/protobuf/proto"
)

// Configuration
const (
	LeaveSystemAPIBase = "http://localhost:8090"
	ConversationEndpoint = "/api/conversation"
)

// ConversationRequest is the payload sent to the Leave System
type ConversationRequest struct {
	Message             string                   `json:"message"`
	Sender              string                   `json:"sender"`
	Channel             string                   `json:"channel"`
	ChatID              string                   `json:"chat_id"`
	ConversationHistory []map[string]interface{} `json:"conversation_history,omitempty"`
}

// ConversationResponse is the response from the Leave System
type ConversationResponse struct {
	Response string                 `json:"response"`
	Metadata map[string]interface{} `json:"metadata"`
}

func main() {
	// Initialize WhatsApp client
	dbLog := waLog.Stdout("Database", "INFO", true)
	container, err := sqlstore.New("sqlite3", "file:store/whatsapp.db?_foreign_keys=on", dbLog)
	if err != nil {
		panic(err)
	}

	deviceStore, err := container.GetFirstDevice()
	if err != nil {
		panic(err)
	}

	clientLog := waLog.Stdout("Client", "INFO", true)
	client := whatsmeow.NewClient(deviceStore, clientLog)

	// Set up event handler
	client.AddEventHandler(func(evt interface{}) {
		switch v := evt.(type) {
		case *events.Message:
			handleIncomingMessage(client, v, clientLog)
		}
	})

	// Connect to WhatsApp
	if client.Store.ID == nil {
		qrChan, _ := client.GetQRChannel(context.Background())
		err = client.Connect()
		if err != nil {
			panic(err)
		}

		for evt := range qrChan {
			if evt.Event == "code" {
				qrterminal.GenerateHalfBlock(evt.Code, qrterminal.L, os.Stdout)
			} else {
				fmt.Println("Login event:", evt.Event)
			}
		}
	} else {
		err = client.Connect()
		if err != nil {
			panic(err)
		}
	}

	fmt.Println("✅ WhatsApp Bridge connected")
	fmt.Println("📡 Forwarding all messages to Leave System API at", LeaveSystemAPIBase)
	fmt.Println("🔧 This bridge contains NO business logic - it's just a communication channel")

	// Keep running
	select {}
}

func handleIncomingMessage(client *whatsmeow.Client, msg *events.Message, logger waLog.Logger) {
	// Skip our own messages
	if msg.Info.IsFromMe {
		return
	}

	// Extract message content
	content := extractMessageText(msg)
	if content == "" {
		return // Skip empty messages
	}

	chatJID := msg.Info.Chat.String()
	sender := msg.Info.Sender.User

	fmt.Printf("📨 [%s] Message from %s: %s\n",
		msg.Info.Timestamp.Format("15:04:05"),
		sender,
		content)

	// Forward to Leave System API
	response, err := forwardToLeaveSystem(content, sender, chatJID)
	if err != nil {
		logger.Errorf("Failed to forward to Leave System: %v", err)

		// Send error response
		_, sendErr := client.SendMessage(context.Background(), msg.Info.Chat, &waProto.Message{
			Conversation: proto.String("Sorry, I'm having trouble processing your request right now. Please try again later."),
		})
		if sendErr != nil {
			logger.Errorf("Failed to send error message: %v", sendErr)
		}
		return
	}

	fmt.Printf("💬 [%s] Response: %s\n",
		time.Now().Format("15:04:05"),
		response.Response)

	// Send response back via WhatsApp
	_, err = client.SendMessage(context.Background(), msg.Info.Chat, &waProto.Message{
		Conversation: proto.String(response.Response),
	})
	if err != nil {
		logger.Errorf("Failed to send message: %v", err)
	}
}

// forwardToLeaveSystem sends the message to the Leave System API
func forwardToLeaveSystem(message, sender, chatID string) (*ConversationResponse, error) {
	// Build request payload
	payload := ConversationRequest{
		Message: message,
		Sender:  sender,
		Channel: "whatsapp",
		ChatID:  chatID,
		// TODO: Add conversation history tracking if needed
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Send HTTP POST to Leave System
	url := LeaveSystemAPIBase + ConversationEndpoint
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to call Leave System API: %w", err)
	}
	defer resp.Body.Close()

	// Check response status
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Leave System returned status %d: %s", resp.StatusCode, string(body))
	}

	// Parse response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var response ConversationResponse
	if err := json.Unmarshal(body, &response); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &response, nil
}

// extractMessageText extracts text content from a WhatsApp message
func extractMessageText(msg *events.Message) string {
	if msg.Message == nil {
		return ""
	}

	if text := msg.Message.GetConversation(); text != "" {
		return text
	}

	if extText := msg.Message.GetExtendedTextMessage(); extText != nil {
		return extText.GetText()
	}

	return ""
}
