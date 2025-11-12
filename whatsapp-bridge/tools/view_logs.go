package main

import (
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// Simple CLI tool to view agent logs
// Usage:
//   go run view_logs.go agent_logger.go <chat_jid> [date]
//   go run view_logs.go agent_logger.go all [date]
//
// Examples:
//   go run view_logs.go agent_logger.go 27123456789@s.whatsapp.net
//   go run view_logs.go agent_logger.go 27123456789@s.whatsapp.net 2025-01-12
//   go run view_logs.go agent_logger.go all
//   go run view_logs.go agent_logger.go all 2025-01-12

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: go run tools/view_logs.go agent_logger.go <chat_jid|all> [date]")
		fmt.Println("\nExamples:")
		fmt.Println("  go run tools/view_logs.go agent_logger.go 27123456789@s.whatsapp.net")
		fmt.Println("  go run tools/view_logs.go agent_logger.go 27123456789@s.whatsapp.net 2025-01-12")
		fmt.Println("  go run tools/view_logs.go agent_logger.go all")
		fmt.Println("  go run tools/view_logs.go agent_logger.go all 2025-01-12")
		os.Exit(1)
	}

	// Initialize logger
	logger, err := NewAgentLogger("store")
	if err != nil {
		fmt.Printf("Error initializing logger: %v\n", err)
		os.Exit(1)
	}

	chatJID := os.Args[1]
	date := time.Now().Format("2006-01-02")
	if len(os.Args) > 2 {
		date = os.Args[2]
	}

	if chatJID == "all" {
		// List all log files
		err := viewAllLogs(logger, date)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			os.Exit(1)
		}
	} else {
		// View specific chat logs
		report, err := logger.GenerateHumanReadableLog(chatJID, date)
		if err != nil {
			fmt.Printf("Error generating report: %v\n", err)
			os.Exit(1)
		}
		fmt.Println(report)
	}
}

func viewAllLogs(logger *AgentLogger, date string) error {
	// List all log files for the specified date
	pattern := filepath.Join(logger.logDir, fmt.Sprintf("*_%s.jsonl", date))
	files, err := filepath.Glob(pattern)
	if err != nil {
		return err
	}

	if len(files) == 0 {
		fmt.Printf("No logs found for date: %s\n", date)
		return nil
	}

	fmt.Printf("=== All Agent Logs for %s ===\n\n", date)
	fmt.Printf("Found %d chat logs:\n\n", len(files))

	for i, file := range files {
		// Extract chat JID from filename
		base := filepath.Base(file)
		// Remove date suffix and .jsonl extension
		chatJID := base[:len(base)-len(fmt.Sprintf("_%s.jsonl", date))]

		fmt.Printf("[%d] %s\n", i+1, chatJID)

		// Get entry count
		entries, err := logger.GetChatLogs(chatJID, date)
		if err != nil {
			fmt.Printf("    Error reading: %v\n", err)
			continue
		}

		// Count entries by stage
		stageCount := make(map[string]int)
		for _, entry := range entries {
			stageCount[entry.Stage]++
		}

		fmt.Printf("    Total entries: %d\n", len(entries))
		for stage, count := range stageCount {
			fmt.Printf("      - %s: %d\n", stage, count)
		}
		fmt.Println()
	}

	fmt.Println("\nTo view detailed logs for a specific chat, run:")
	fmt.Println("  go run tools/view_logs.go agent_logger.go <chat_jid> " + date)

	return nil
}
