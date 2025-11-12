package main

import (
	"regexp"
	"strings"
	"time"
)

// LeaveRequestInfo holds extracted information from a leave request
type LeaveRequestInfo struct {
	StudentName string
	StudentID   string
	StartDate   time.Time
	EndDate     time.Time
	Reason      string
	ContactInfo string
}

// AnalyzeLeaveRequest demonstrates how to use the agent logger for detailed leave request analysis
// This is an EXAMPLE function showing the logging pattern - you would integrate this into your actual agent logic
func (am *AgentManager) AnalyzeLeaveRequest(chatJID, chatName, messageContent, senderName string) (*LeaveRequestInfo, error) {
	// Initialize extracted info map
	extractedInfo := make(map[string]interface{})
	missingFields := []string{}
	info := &LeaveRequestInfo{}

	// Convert to lowercase for easier matching
	contentLower := strings.ToLower(messageContent)

	// 1. Try to extract Student Name
	studentNamePatterns := []string{
		`(?i)(?:my (?:son|daughter|child)|student)\s+(?:is\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)`,
		`(?i)(?:for|regarding)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)`,
		`(?i)name[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)`,
	}

	for _, pattern := range studentNamePatterns {
		re := regexp.MustCompile(pattern)
		if matches := re.FindStringSubmatch(messageContent); len(matches) > 1 {
			info.StudentName = strings.TrimSpace(matches[1])
			extractedInfo["student_name"] = info.StudentName
			break
		}
	}

	if info.StudentName == "" {
		missingFields = append(missingFields, "student_name")
	}

	// 2. Try to extract Student ID
	studentIDPatterns := []string{
		`(?i)(?:student\s+)?(?:id|number)[:\s#]*([A-Z0-9]{4,10})`,
		`(?i)(?:student|pupil)[:\s]+([A-Z0-9]{4,10})`,
		`\b([A-Z]{2,3}\d{4,6})\b`, // Pattern like MHS12345
	}

	for _, pattern := range studentIDPatterns {
		re := regexp.MustCompile(pattern)
		if matches := re.FindStringSubmatch(messageContent); len(matches) > 1 {
			info.StudentID = strings.TrimSpace(matches[1])
			extractedInfo["student_id"] = info.StudentID
			break
		}
	}

	if info.StudentID == "" {
		missingFields = append(missingFields, "student_id")
	}

	// 3. Try to extract dates
	datePatterns := []string{
		`(?i)(?:on|for)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+\d{4})?)`,
		`(?i)(?:on|for)\s+(\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?)`,
		`(?i)tomorrow`,
		`(?i)today`,
		`(?i)next\s+(?:monday|tuesday|wednesday|thursday|friday)`,
	}

	foundDate := false
	for _, pattern := range datePatterns {
		re := regexp.MustCompile(pattern)
		if matches := re.FindStringSubmatch(contentLower); len(matches) > 1 {
			extractedInfo["date_string"] = matches[1]
			foundDate = true
			break
		} else if strings.Contains(contentLower, pattern) {
			extractedInfo["date_string"] = pattern
			foundDate = true
			break
		}
	}

	if !foundDate {
		missingFields = append(missingFields, "date")
	}

	// 4. Try to extract reason
	reasonKeywords := []string{"sick", "ill", "doctor", "appointment", "funeral", "family", "emergency", "medical"}
	foundReason := false

	for _, keyword := range reasonKeywords {
		if strings.Contains(contentLower, keyword) {
			info.Reason = keyword
			extractedInfo["reason_type"] = keyword
			foundReason = true
			break
		}
	}

	// Try to extract full reason sentence
	reasonPatterns := []string{
		`(?i)(?:because|reason|due to)[:\s]+([^.?!]+)`,
		`(?i)(?:is|has|have)[:\s]+([^.?!]+)`,
	}

	for _, pattern := range reasonPatterns {
		re := regexp.MustCompile(pattern)
		if matches := re.FindStringSubmatch(messageContent); len(matches) > 1 {
			fullReason := strings.TrimSpace(matches[1])
			if len(fullReason) > 10 { // Only if it's substantial
				info.Reason = fullReason
				extractedInfo["reason_detail"] = fullReason
				foundReason = true
				break
			}
		}
	}

	if !foundReason {
		missingFields = append(missingFields, "reason")
	}

	// 5. Extract contact info (usually the sender)
	info.ContactInfo = senderName
	extractedInfo["contact"] = senderName

	// Determine next action based on what's missing
	var nextAction string
	if len(missingFields) == 0 {
		nextAction = "All required information present. Validate data and process leave request."
	} else if len(missingFields) >= 3 {
		nextAction = "Too much information missing. Politely request that the parent provide: student ID, dates, and reason for leave."
	} else {
		nextAction = "Request missing information: " + strings.Join(missingFields, ", ")
	}

	// Log the detailed analysis using the specialized leave request logger
	if am.agentLogger != nil {
		am.agentLogger.LogLeaveRequest(
			chatJID,
			chatName,
			messageContent,
			extractedInfo,
			missingFields,
			nextAction,
		)
	}

	return info, nil
}

// Example of how to use this in your agent's response generation:
/*
func (am *AgentManager) GenerateLeaveResponse(chatJID, messageContent, senderName string) (string, error) {
	// Get chat name
	chatName := "" // Get from database or context

	// Analyze the leave request
	leaveInfo, err := am.AnalyzeLeaveRequest(chatJID, chatName, messageContent, senderName)
	if err != nil {
		return "", err
	}

	// Build response based on what's missing
	var response string

	if leaveInfo.StudentID == "" && leaveInfo.StudentName == "" {
		response = "Hi! I'd be happy to help with the leave request. Could you please provide:\n\n" +
			"1. Student's full name\n" +
			"2. Student ID number\n" +
			"3. Date(s) of absence\n" +
			"4. Reason for leave\n\n" +
			"Thank you!"
	} else if leaveInfo.StudentID == "" {
		response = fmt.Sprintf("Thanks for the information about %s. Could you please provide the student ID number? " +
			"You can find this on the school portal or student card.", leaveInfo.StudentName)
	} else {
		// Process the complete request
		response = fmt.Sprintf("Thank you! I have received the leave request for %s (ID: %s). " +
			"The request has been logged and will be reviewed by the appropriate staff member. " +
			"You will receive confirmation shortly.", leaveInfo.StudentName, leaveInfo.StudentID)
	}

	return response, nil
}
*/

// Example log output for: "My son John Smith needs leave tomorrow because he has a doctor's appointment"
/*
{
  "timestamp": "2025-01-12T10:30:45Z",
  "chat_jid": "27123456789@s.whatsapp.net",
  "chat_name": "Parent Contact",
  "stage": "leave_request_analysis",
  "message_content": "My son John Smith needs leave tomorrow because he has a doctor's appointment",
  "logic": {
    "intent": "leave_request",
    "message_content": "My son John Smith needs leave tomorrow because he has a doctor's appointment",
    "extracted_info": {
      "student_name": "John Smith",
      "date_string": "tomorrow",
      "reason_type": "doctor",
      "reason_detail": "he has a doctor's appointment",
      "contact": "27123456789"
    },
    "missing_fields": ["student_id"],
    "next_action": "Request missing information: student_id",
    "analysis_detail": "Found information:\n  - student_name: John Smith\n  - date_string: tomorrow\n  - reason_type: doctor\n  - reason_detail: he has a doctor's appointment\n  - contact: 27123456789\n\nMissing required information:\n  - student_id\n\nNext action: Request missing information: student_id\n"
  }
}
*/

// Example log output for: "Please approve leave"
/*
{
  "timestamp": "2025-01-12T10:35:20Z",
  "chat_jid": "27123456789@s.whatsapp.net",
  "chat_name": "Parent Contact",
  "stage": "leave_request_analysis",
  "message_content": "Please approve leave",
  "logic": {
    "intent": "leave_request",
    "message_content": "Please approve leave",
    "extracted_info": {
      "contact": "27123456789"
    },
    "missing_fields": ["student_name", "student_id", "date", "reason"],
    "next_action": "Too much information missing. Politely request that the parent provide: student ID, dates, and reason for leave.",
    "analysis_detail": "Found information:\n  - contact: 27123456789\n\nMissing required information:\n  - student_name\n  - student_id\n  - date\n  - reason\n\nNext action: Too much information missing. Politely request that the parent provide: student ID, dates, and reason for leave.\n"
  }
}
*/
