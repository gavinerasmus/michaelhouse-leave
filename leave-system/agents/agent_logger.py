"""
Agent Logger for Leave System
Tracks AI agent decision-making process and conversations
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AgentLogger:
    """
    Logs agent interactions and decision-making process
    Stores logs in JSONL format organized by chat and date
    """

    def __init__(self, log_dir: str = "logs/agent-logs"):
        """
        Initialize agent logger

        Args:
            log_dir: Directory to store agent logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_received_message(
        self,
        chat_id: str,
        sender: str,
        message: str,
        channel: str
    ):
        """Log when a message is received"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "stage": "received",
            "sender": sender,
            "channel": channel,
            "message": message,
            "logic": {
                "message_length": len(message),
                "has_content": bool(message.strip())
            }
        }
        self._write_log_entry(chat_id, entry)

    def log_analysis(
        self,
        chat_id: str,
        analysis: Dict[str, Any]
    ):
        """Log message analysis results"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "stage": "analysis",
            "logic": analysis
        }
        self._write_log_entry(chat_id, entry)

    def log_decision(
        self,
        chat_id: str,
        decision: Dict[str, Any]
    ):
        """Log agent decision"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "stage": "decision",
            "logic": decision
        }
        self._write_log_entry(chat_id, entry)

    def log_response(
        self,
        chat_id: str,
        response: str,
        logic: Dict[str, Any]
    ):
        """Log generated response"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "stage": "response",
            "response": response,
            "logic": logic
        }
        self._write_log_entry(chat_id, entry)

    def log_error(
        self,
        chat_id: str,
        stage: str,
        error: str
    ):
        """Log an error"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "stage": stage,
            "error": error
        }
        self._write_log_entry(chat_id, entry)

    def log_leave_request_analysis(
        self,
        chat_id: str,
        message: str,
        extracted_info: Dict[str, Any],
        missing_fields: List[str],
        next_action: str
    ):
        """
        Log detailed leave request analysis

        Args:
            chat_id: Chat identifier
            message: Original message text
            extracted_info: Information extracted from the message
            missing_fields: Required fields that are missing
            next_action: What the agent should do next
        """
        # Build detailed analysis text
        analysis_detail = ""

        if extracted_info:
            analysis_detail += "Found information:\n"
            for key, value in extracted_info.items():
                analysis_detail += f"  - {key}: {value}\n"

        if missing_fields:
            analysis_detail += "\nMissing required information:\n"
            for field in missing_fields:
                analysis_detail += f"  - {field}\n"

        analysis_detail += f"\nNext action: {next_action}\n"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "stage": "leave_request_analysis",
            "message": message,
            "logic": {
                "intent": "leave_request",
                "message_content": message,
                "extracted_info": extracted_info,
                "missing_fields": missing_fields,
                "next_action": next_action,
                "analysis_detail": analysis_detail
            }
        }
        self._write_log_entry(chat_id, entry)

    def _write_log_entry(self, chat_id: str, entry: Dict[str, Any]):
        """Write a log entry to the appropriate file"""
        try:
            # Create daily log file for each chat
            date = datetime.now().strftime("%Y-%m-%d")
            # Sanitize chat_id for filename
            safe_chat_id = chat_id.replace('/', '_').replace('@', '_at_')
            log_file = self.log_dir / f"{safe_chat_id}_{date}.jsonl"

            # Append to log file
            with open(log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')

        except Exception as e:
            logger.error(f"Failed to write log entry: {e}")

    def get_chat_logs(
        self,
        chat_id: str,
        date: str = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve logs for a specific chat

        Args:
            chat_id: Chat identifier
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            List of log entries
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        safe_chat_id = chat_id.replace('/', '_').replace('@', '_at_')
        log_file = self.log_dir / f"{safe_chat_id}_{date}.jsonl"

        if not log_file.exists():
            return []

        entries = []
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read log file: {e}")

        return entries

    def generate_human_readable_log(
        self,
        chat_id: str,
        date: str = None
    ) -> str:
        """
        Generate a human-readable summary of logs

        Args:
            chat_id: Chat identifier
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Human-readable log text
        """
        entries = self.get_chat_logs(chat_id, date)

        if not entries:
            return f"No logs found for {chat_id} on {date or 'today'}\n"

        output = f"=== Agent Logs for {chat_id} ({date or 'today'}) ===\n\n"

        for i, entry in enumerate(entries, 1):
            timestamp = entry.get('timestamp', 'unknown')
            stage = entry.get('stage', 'unknown')

            output += f"[{i}] {timestamp} - Stage: {stage}\n"

            if entry.get('sender'):
                output += f"    Sender: {entry['sender']}\n"

            if entry.get('message'):
                output += f"    Message: {entry['message']}\n"

            if entry.get('logic'):
                output += "    Logic/Analysis:\n"
                logic = entry['logic']
                for key, value in logic.items():
                    if key == 'analysis_detail':
                        output += f"      {value}\n"
                    else:
                        output += f"      {key}: {value}\n"

            if entry.get('response'):
                output += f"    Response: {entry['response']}\n"

            if entry.get('error'):
                output += f"    Error: {entry['error']}\n"

            output += "\n"

        return output
