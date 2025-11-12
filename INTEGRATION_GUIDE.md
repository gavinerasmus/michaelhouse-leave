# Integration Guide: Leave System with WhatsApp & Email

This guide explains how to integrate the Michaelhouse Leave System with the existing WhatsApp bridge and new Email bridge.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Communication Channels                   │
├──────────────────────────┬──────────────────────────────────┤
│   WhatsApp Bridge (Go)   │     Email Bridge (Python)        │
│   whatsapp-bridge/       │   leave-system/email-bridge/     │
└───────────┬──────────────┴─────────────┬────────────────────┘
            │                             │
            ├─────────────┬───────────────┤
            │             ▼               │
            │   ┌─────────────────────┐  │
            │   │   Leave Processor   │  │
            │   │  (Single Instance)  │  │
            │   │  leave-system/      │  │
            │   └─────────┬───────────┘  │
            │             │               │
            │             ▼               │
            │   ┌─────────────────────┐  │
            │   │  Placeholder Tools  │  │
            │   │  (Database Layer)   │  │
            │   └─────────────────────┘  │
            │                             │
            └─────────────┬───────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │   Database    │
                  │  (PostgreSQL) │
                  └───────────────┘
```

## Option 1: Go WhatsApp Bridge → Python Processor

### Method A: HTTP API Bridge

Create a simple HTTP API for the leave processor:

```python
# leave-system/api.py
from flask import Flask, request, jsonify
from processors.leave_processor import LeaveProcessor

app = Flask(__name__)
processor = LeaveProcessor()

@app.route('/process_leave_request', methods=['POST'])
def process_leave_request():
    data = request.json
    result = processor.process_parent_request(
        message_text=data['message'],
        sender_identifier=data['sender'],
        channel=data['channel']
    )
    return jsonify(result)

@app.route('/process_hm_request', methods=['POST'])
def process_hm_request():
    data = request.json
    result = processor.process_housemaster_request(
        message_text=data['message'],
        sender_identifier=data['sender'],
        channel=data['channel']
    )
    return jsonify(result)

if __name__ == '__main__':
    app.run(port=8090)
```

Then in Go WhatsApp bridge:

```go
// whatsapp-bridge/main.go

func processLeaveRequest(messageText, sender, channel string) map[string]interface{} {
    apiURL := "http://localhost:8090/process_leave_request"

    requestBody, _ := json.Marshal(map[string]string{
        "message": messageText,
        "sender": sender,
        "channel": channel,
    })

    resp, err := http.Post(apiURL, "application/json", bytes.NewBuffer(requestBody))
    if err != nil {
        return map[string]interface{}{
            "status": "error",
            "message": "Failed to process leave request",
        }
    }
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    return result
}

func handleMessage(/* ... */) {
    // After storing message in database

    // Check if message contains leave request keywords
    contentLower := strings.ToLower(content)
    isLeaveRequest := strings.Contains(contentLower, "leave") ||
                      strings.Contains(contentLower, "exeat") ||
                      strings.Contains(contentLower, "overnight") ||
                      strings.Contains(contentLower, "weekend")

    if isLeaveRequest {
        // Process as leave request
        result := processLeaveRequest(content, sender, "whatsapp")

        // Send response back via WhatsApp
        response := result["message"].(string)
        sendWhatsAppMessage(client, chatJID, response, "")
        return
    }

    // Otherwise, handle as normal message (agent system)
    // ... existing agent logic ...
}
```

### Method B: Direct Python Execution

Call Python directly from Go:

```go
// whatsapp-bridge/main.go

func processLeaveRequestDirect(messageText, sender, channel string) string {
    cmd := exec.Command("python3", "-c", fmt.Sprintf(`
from leave_system import LeaveProcessor
processor = LeaveProcessor()
result = processor.process_parent_request(
    message_text=%q,
    sender_identifier=%q,
    channel=%q
)
print(result['message'])
`, messageText, sender, channel))

    output, err := cmd.Output()
    if err != nil {
        return "Error processing leave request. Please contact the Housemaster."
    }

    return string(output)
}
```

## Option 2: Email Bridge (Pure Python)

The email bridge is already Python, so integration is straightforward:

```python
# leave-system/email-bridge/run_email_bridge.py

from email_handler import EmailBridge, EmailLeaveHandler
import time
import os

def main():
    # Configure email settings
    bridge = EmailBridge(
        imap_server=os.getenv('IMAP_SERVER', 'imap.gmail.com'),
        smtp_server=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
        email_address=os.getenv('LEAVE_EMAIL', ''),
        password=os.getenv('LEAVE_EMAIL_PASSWORD', ''),
    )

    handler = EmailLeaveHandler(bridge)

    print("[EMAIL BRIDGE] Starting email monitoring...")

    while True:
        try:
            handler.process_incoming_emails()
        except Exception as e:
            print(f"[EMAIL BRIDGE] Error: {e}")

        # Check every 60 seconds
        time.sleep(60)

if __name__ == '__main__':
    main()
```

Run as a service:

```bash
# Create systemd service: /etc/systemd/system/leave-email-bridge.service

[Unit]
Description=Michaelhouse Leave Email Bridge
After=network.target

[Service]
Type=simple
User=michaelhouse
WorkingDirectory=/path/to/leave
ExecStart=/usr/bin/python3 leave-system/email-bridge/run_email_bridge.py
Restart=always
Environment="IMAP_SERVER=imap.gmail.com"
Environment="SMTP_SERVER=smtp.gmail.com"
Environment="LEAVE_EMAIL=leave@michaelhouse.org"
Environment="LEAVE_EMAIL_PASSWORD=your-app-specific-password"

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable leave-email-bridge
sudo systemctl start leave-email-bridge
```

## Option 3: Unified Python Service

Create a single Python service that monitors both channels:

```python
# unified-bridge.py

from leave_system import LeaveProcessor
from leave_system.email_bridge.email_handler import EmailBridge, EmailLeaveHandler
import threading
import time

class UnifiedLeaveBridge:
    def __init__(self):
        self.processor = LeaveProcessor()

        # Email bridge
        self.email_bridge = EmailBridge(
            email_address=os.getenv('LEAVE_EMAIL'),
            password=os.getenv('LEAVE_EMAIL_PASSWORD')
        )
        self.email_handler = EmailLeaveHandler(self.email_bridge)

    def run_email_monitor(self):
        """Monitor email inbox"""
        print("[UNIFIED BRIDGE] Starting email monitoring...")
        while True:
            try:
                self.email_handler.process_incoming_emails()
            except Exception as e:
                print(f"[EMAIL] Error: {e}")
            time.sleep(60)

    def run_whatsapp_monitor(self):
        """Monitor WhatsApp messages via database polling"""
        print("[UNIFIED BRIDGE] Starting WhatsApp monitoring...")
        # This would poll the WhatsApp bridge's database for new messages
        # Or listen to a webhook/API from the Go bridge
        pass

    def start(self):
        """Start all monitoring threads"""
        # Email monitoring thread
        email_thread = threading.Thread(target=self.run_email_monitor, daemon=True)
        email_thread.start()

        # WhatsApp monitoring thread (if needed)
        # whatsapp_thread = threading.Thread(target=self.run_whatsapp_monitor, daemon=True)
        # whatsapp_thread.start()

        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[UNIFIED BRIDGE] Shutting down...")

if __name__ == '__main__':
    bridge = UnifiedLeaveBridge()
    bridge.start()
```

## Database Integration

Replace placeholder tools with real database connections:

```python
# leave-system/tools/database_tools.py

import psycopg2
from typing import Optional, Dict, Any

class DatabaseTools(LeaveSystemTools):
    """Production database implementation"""

    def __init__(self, db_config: Dict[str, str]):
        self.conn = psycopg2.connect(**db_config)

    def tool_parent_phone_check(self, phone_number: str) -> Optional[str]:
        """Real database query"""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT parent_id FROM parents WHERE phone = %s AND active = true",
                (phone_number,)
            )
            result = cur.fetchone()
            return result[0] if result else None

    def tool_student_parent_linkage(
        self,
        parent_auth_id: str,
        requested_student_identifier: str
    ) -> Optional[Dict[str, Any]]:
        """Real database query with joins"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT
                    s.admin_number,
                    s.first_name,
                    s.last_name,
                    s.house,
                    s.block,
                    lb.overnight_remaining,
                    lb.friday_supper_remaining
                FROM students s
                JOIN student_parents sp ON s.id = sp.student_id
                JOIN parents p ON sp.parent_id = p.id
                JOIN leave_balances lb ON s.id = lb.student_id
                WHERE p.parent_id = %s
                AND (s.admin_number = %s OR s.first_name ILIKE %s OR s.last_name ILIKE %s)
                AND s.active = true
            """, (parent_auth_id, requested_student_identifier,
                  f"%{requested_student_identifier}%",
                  f"%{requested_student_identifier}%"))

            result = cur.fetchone()
            if not result:
                return None

            return {
                "adminNumber": result[0],
                "firstName": result[1],
                "lastName": result[2],
                "house": result[3],
                "block": result[4],
                "balances": {
                    "overnight": result[5],
                    "fridaySupper": result[6]
                }
            }

    # Implement other tools similarly...
```

Update initialization:

```python
# In your main application
from leave_system.tools.database_tools import DatabaseTools
from leave_system.processors.leave_processor import LeaveProcessor

# Configure database
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'michaelhouse'),
    'user': os.getenv('DB_USER', 'leave_user'),
    'password': os.getenv('DB_PASSWORD', '')
}

# Create processor with real tools
tools = DatabaseTools(db_config)
processor = LeaveProcessor()
processor.tools = tools  # Replace placeholder tools
```

## Testing Integration

### Test WhatsApp Integration

```bash
# Terminal 1: Start Leave API
cd leave-system
python3 api.py

# Terminal 2: Start WhatsApp Bridge
cd whatsapp-bridge
CGO_ENABLED=1 go run main.go

# Terminal 3: Send test message via WhatsApp
# (Use your phone to send: "Can James have overnight leave this Saturday?")
```

### Test Email Integration

```bash
# Start email bridge
cd leave-system/email-bridge
python3 run_email_bridge.py

# Send test email to configured address
# Subject: "Leave Request"
# Body: "Please approve leave for Michael Doe on 14th February"
```

## Deployment Checklist

- [ ] Set up PostgreSQL database with schema
- [ ] Configure email service (Gmail API or SMTP)
- [ ] Update placeholder tools with database implementations
- [ ] Test authentication flows
- [ ] Test all leave types
- [ ] Test Housemaster functions
- [ ] Set up monitoring and logging
- [ ] Configure error alerting
- [ ] Document API endpoints
- [ ] Train staff on system

## Monitoring

Add logging to track:
- Request volume by channel
- Approval/rejection rates
- Response times
- Error rates
- Balance depletion patterns

```python
import logging

logging.basicConfig(
    filename='/var/log/leave-system.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('leave_system')

# In processor
logger.info(f"Leave request: {student_name}, type: {leave_type}, status: {status}")
```

## Support

For integration issues:
1. Check logs: `/var/log/leave-system.log`
2. Verify database connectivity
3. Test email/WhatsApp connectivity
4. Review placeholder tool replacements
5. Contact development team

---

**Status**: System ready for integration
**Next Step**: Replace placeholder tools with database implementations
