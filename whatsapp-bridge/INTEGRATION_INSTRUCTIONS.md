# WhatsApp Bridge - Leave System Integration

## Overview

This document explains how to integrate the Leave System API with the WhatsApp Bridge.

## Files

- **`leave_integration.go`** - New file with leave system API client
- **`main.go`** - Needs modifications (see below)

## Integration Steps

### Step 1: Add Environment Variable

Add to your `.env` file or set in environment:

```bash
LEAVE_API_URL=http://localhost:8090
```

### Step 2: Modify main.go

Add the leave system client initialization and message handling.

#### A. Add Global Variable (around line 100)

```go
// Leave system API client (global)
var leaveSystemClient *LeaveSystemClient
```

#### B. Initialize Client in main() (around line 2200)

Find the `main()` function and add after the WhatsApp client connects:

```go
// Initialize leave system client
leaveSystemClient = NewLeaveSystemClient()

// Check if leave API is available
if err := leaveSystemClient.HealthCheck(); err != nil {
	log.Warnf("Leave system API not available: %v", err)
	log.Warnf("Leave requests will fall back to agent responses")
} else {
	log.Infof("Leave system API connected at %s", leaveSystemClient.BaseURL)
}
```

#### C. Modify handleMessage() (around line 1137)

Replace the agent check section (lines 1137-1166) with:

```go
		// === LEAVE SYSTEM INTEGRATION ===
		// Check if this is a leave request BEFORE agent processing
		if !msg.Info.IsFromMe && content != "" && leaveSystemClient != nil {
			if IsLeaveRequest(content) {
				fmt.Printf("[LEAVE] Detected leave request from %s: %s\n", sender, content)

				go func() {
					// Determine if this is a housemaster or parent request
					// You can enhance this logic to check against a housemaster database
					isHousemaster := strings.Contains(strings.ToLower(sender), "hm.") ||
									 strings.Contains(strings.ToLower(content), "balance") ||
									 strings.Contains(strings.ToLower(content), "cancel") ||
									 strings.Contains(strings.ToLower(content), "restrict")

					var response *LeaveResponse
					var err error

					if isHousemaster {
						fmt.Printf("[LEAVE] Processing as housemaster request\n")
						response, err = leaveSystemClient.ProcessHousemasterRequest(content, sender)
					} else {
						fmt.Printf("[LEAVE] Processing as parent request\n")
						response, err = leaveSystemClient.ProcessParentRequest(content, sender)
					}

					if err != nil {
						fmt.Printf("[LEAVE] Error processing leave request: %v\n", err)
						logger.Warnf("Failed to process leave request: %v", err)

						// Send error message to user
						errorMsg := "Sorry, I'm having trouble processing your leave request. Please contact the Housemaster directly."
						success, errMsg := sendWhatsAppMessage(client, chatJID, errorMsg, "")
						if !success {
							fmt.Printf("[LEAVE] Failed to send error message: %s\n", errMsg)
						}
						return
					}

					// Send response back to WhatsApp
					fmt.Printf("[LEAVE] Status: %s\n", response.Status)
					fmt.Printf("[LEAVE] Response: %s\n", response.Message)

					success, errMsg := sendWhatsAppMessage(client, chatJID, response.Message, "")
					if !success {
						fmt.Printf("[LEAVE] Failed to send response: %s\n", errMsg)
						logger.Warnf("Failed to send leave response: %s", errMsg)
					} else {
						fmt.Printf("[LEAVE] Response sent successfully\n")
					}
				}()

				// Skip agent processing for leave requests
				return
			}
		}

		// === AGENT PROCESSING (for non-leave messages) ===
		// Check if agent should respond to this message (only for text messages for now)
		fmt.Printf("[DEBUG] Checking agent response for chat %s, content: '%s', agentManager: %v\n", chatJID, content, agentManager != nil)
		if agentManager != nil && content != "" {
			// ... rest of existing agent code ...
		}
```

### Step 3: Build and Test

```bash
# Build the bridge
export CGO_ENABLED=1
go build -o whatsapp-bridge main.go leave_integration.go

# Or run directly
CGO_ENABLED=1 go run main.go leave_integration.go
```

### Step 4: Start Services

Open 2 terminals:

**Terminal 1 - Leave API:**
```bash
cd ../leave-system
python3 api.py
```

**Terminal 2 - WhatsApp Bridge:**
```bash
cd whatsapp-bridge
export CGO_ENABLED=1
export LEAVE_API_URL=http://localhost:8090
go run main.go leave_integration.go
```

## Testing

### Test 1: Parent Leave Request

Send a WhatsApp message:
```
Hi, can James have overnight leave this Saturday?
```

Expected response:
```
Thank you for submitting your request.

I'm pleased to confirm that the exeat request for James Smith for Overnight leave has been approved.

Dates: Saturday 08 February 2025 at 14:00 to Sunday 09 February 2025 at 18:50

Remaining overnight leave balance: 2
```

### Test 2: Housemaster Query

Send from housemaster phone:
```
What is the balance for student 12345?
```

Expected response:
```
Leave Balance for Student 12345:
Overnight Leave: 3 remaining
Friday Supper Leave: 3 remaining
```

### Test 3: Non-Leave Message

Send a normal message:
```
Hello, how are you?
```

This should be handled by the agent system (if enabled) instead of the leave system.

## Monitoring

Watch the terminal output for:
- `[LEAVE]` prefix - Leave system processing
- `[DEBUG]` prefix - Agent system processing
- HTTP status and response details

## Troubleshooting

### Leave API Not Responding

```bash
# Check if API is running
curl http://localhost:8090/health

# Test API directly
curl -X POST http://localhost:8090/api/process_parent_request \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can James have leave this Saturday?",
    "sender": "27603174174",
    "channel": "whatsapp"
  }'
```

### Messages Not Detected as Leave Requests

Check the `IsLeaveRequest()` function in `leave_integration.go` and add more keywords if needed:

```go
leaveKeywords := []string{
	"leave", "exeat", "overnight", "weekend",
	"your-custom-keyword",
}
```

### Database Connection Issues

Make sure the leave system database is set up:

```bash
cd ../leave-system/database
./setup_database.sh --reset
```

## Production Deployment

### Environment Variables

Set in production:
```bash
export LEAVE_API_URL=https://leave-api.michaelhouse.org
export DB_HOST=your-production-db-host
export DB_NAME=michaelhouse_leave
export DB_USER=leave_user
export DB_PASSWORD=secure-password
```

### Systemd Service

Create `/etc/systemd/system/whatsapp-bridge.service`:

```ini
[Unit]
Description=WhatsApp Bridge with Leave System
After=network.target postgresql.service

[Service]
Type=simple
User=michaelhouse
WorkingDirectory=/opt/michaelhouse/whatsapp-bridge
Environment="CGO_ENABLED=1"
Environment="LEAVE_API_URL=http://localhost:8090"
ExecStart=/opt/michaelhouse/whatsapp-bridge/whatsapp-bridge
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable whatsapp-bridge
sudo systemctl start whatsapp-bridge
sudo systemctl status whatsapp-bridge
```

## Next Steps

1. ✅ Integration code created
2. ⏳ Test with real WhatsApp messages
3. ⏳ Add housemaster phone number detection (database lookup)
4. ⏳ Add error handling and retry logic
5. ⏳ Monitor and tune performance
6. ⏳ Deploy to production

## Support

- Leave System API: `../leave-system/api.py`
- Integration Client: `leave_integration.go`
- Main Bridge: `main.go`
- Documentation: `../leave-system/README.md`

---

**Status**: Ready for testing!
