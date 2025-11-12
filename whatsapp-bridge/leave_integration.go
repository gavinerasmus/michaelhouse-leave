package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// LeaveRequest represents a request to the leave system API
type LeaveRequest struct {
	Message string `json:"message"`
	Sender  string `json:"sender"`
	Channel string `json:"channel"`
}

// LeaveResponse represents the response from the leave system API
type LeaveResponse struct {
	Status  string `json:"status"`  // 'approved', 'rejected', 'special_pending', 'error'
	Message string `json:"message"` // Response to send back to user
	Reason  string `json:"reason,omitempty"`
}

// LeaveSystemClient handles communication with the leave system API
type LeaveSystemClient struct {
	BaseURL    string
	HTTPClient *http.Client
}

// NewLeaveSystemClient creates a new leave system API client
func NewLeaveSystemClient() *LeaveSystemClient {
	baseURL := os.Getenv("LEAVE_API_URL")
	if baseURL == "" {
		baseURL = "http://localhost:8090" // Default
	}

	return &LeaveSystemClient{
		BaseURL: baseURL,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// IsLeaveRequest checks if the message content indicates a leave request
func IsLeaveRequest(content string) bool {
	if content == "" {
		return false
	}

	contentLower := strings.ToLower(content)

	// Check for leave-related keywords
	leaveKeywords := []string{
		"leave", "exeat", "overnight", "weekend",
		"friday supper", "day leave", "special leave",
		"permission", "can he go", "can she go",
		"can my son", "can my daughter",
	}

	for _, keyword := range leaveKeywords {
		if strings.Contains(contentLower, keyword) {
			return true
		}
	}

	return false
}

// ProcessParentRequest sends a parent leave request to the API
func (c *LeaveSystemClient) ProcessParentRequest(messageText, sender string) (*LeaveResponse, error) {
	request := LeaveRequest{
		Message: messageText,
		Sender:  sender,
		Channel: "whatsapp",
	}

	return c.callAPI("/api/process_parent_request", request)
}

// ProcessHousemasterRequest sends a housemaster request to the API
func (c *LeaveSystemClient) ProcessHousemasterRequest(messageText, sender string) (*LeaveResponse, error) {
	request := LeaveRequest{
		Message: messageText,
		Sender:  sender,
		Channel: "whatsapp",
	}

	return c.callAPI("/api/process_housemaster_request", request)
}

// callAPI makes the actual HTTP request to the leave system API
func (c *LeaveSystemClient) callAPI(endpoint string, request LeaveRequest) (*LeaveResponse, error) {
	// Marshal request to JSON
	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %v", err)
	}

	// Create HTTP request
	url := c.BaseURL + endpoint
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")

	// Send request
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %v", err)
	}
	defer resp.Body.Close()

	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %v", err)
	}

	// Check HTTP status
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
	}

	// Parse response
	var leaveResponse LeaveResponse
	if err := json.Unmarshal(body, &leaveResponse); err != nil {
		return nil, fmt.Errorf("failed to parse response: %v", err)
	}

	return &leaveResponse, nil
}

// HealthCheck checks if the leave system API is reachable
func (c *LeaveSystemClient) HealthCheck() error {
	url := c.BaseURL + "/health"
	resp, err := c.HTTPClient.Get(url)
	if err != nil {
		return fmt.Errorf("health check failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("health check returned status %d", resp.StatusCode)
	}

	return nil
}
