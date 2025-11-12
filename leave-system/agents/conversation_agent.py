"""
Conversational AI Agent for Leave System
Handles natural language interactions with parents and housemasters
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import anthropic
import logging

from processors.leave_processor import LeaveProcessor
from agents.agent_logger import AgentLogger

logger = logging.getLogger(__name__)


class ConversationAgent:
    """
    AI agent that handles conversational interactions
    Translates natural language to structured leave system requests
    """

    def __init__(self, agent_context_path: str = None):
        """
        Initialize the conversation agent

        Args:
            agent_context_path: Path to agent context markdown file
        """
        # Load Anthropic API key
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not set - agent will use fallback responses")
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)

        # Load agent context/personality
        self.context = self._load_agent_context(agent_context_path)

        # Initialize processors
        self.leave_processor = LeaveProcessor()

        # Initialize logger
        self.agent_logger = AgentLogger()

    def _load_agent_context(self, context_path: Optional[str]) -> str:
        """Load agent personality/context from file"""
        # If no path provided, use default location in agents folder
        if context_path is None:
            context_path = os.path.join(os.path.dirname(__file__), 'context.md')

        if os.path.exists(context_path):
            with open(context_path, 'r') as f:
                return f.read()

        # Default context if file not found
        return """You are a helpful assistant for the Michaelhouse Leave Management System.

You help parents request leave for their sons and help housemasters manage leave policies.

When processing leave requests:
1. Extract student name/ID, dates, and leave type
2. Be polite and professional
3. If information is missing, ask for it specifically
4. Confirm details before processing

When you don't have information, ask for it explicitly. For example:
- "I need the student ID to process this request. Could you provide it?"
- "What are the specific dates for this leave request?"

Always be helpful and guide users through the process."""

    def process_message(
        self,
        message: str,
        sender: str,
        channel: str,
        chat_id: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Process a conversational message and return a response

        Args:
            message: The user's message text
            sender: Sender identifier (phone/email)
            channel: Communication channel (whatsapp/email)
            chat_id: Unique chat identifier for logging
            conversation_history: Previous messages in this conversation

        Returns:
            Dict with 'response' and 'metadata' about the interaction
        """
        # Log received message
        self.agent_logger.log_received_message(
            chat_id=chat_id,
            sender=sender,
            message=message,
            channel=channel
        )

        # Analyze the message to determine intent
        analysis = self._analyze_message(message, sender, channel)

        # Log analysis
        self.agent_logger.log_analysis(
            chat_id=chat_id,
            analysis=analysis
        )

        # If it's a clear leave request with all information, process it directly
        if analysis['intent'] == 'leave_request' and analysis['has_all_info']:
            result = self.leave_processor.process_parent_request(
                message_text=message,
                sender_identifier=sender,
                channel=channel
            )

            # Log the decision
            self.agent_logger.log_decision(
                chat_id=chat_id,
                decision={
                    'action': 'direct_processing',
                    'reason': 'Complete leave request detected',
                    'result': result['status']
                }
            )

            response_text = result['message']
        else:
            # Use AI agent to handle the conversation
            response_text = self._generate_conversational_response(
                message=message,
                sender=sender,
                channel=channel,
                analysis=analysis,
                conversation_history=conversation_history
            )

        # Log response
        self.agent_logger.log_response(
            chat_id=chat_id,
            response=response_text,
            logic={
                'intent': analysis['intent'],
                'response_type': 'direct' if analysis['has_all_info'] else 'conversational',
                'response_length': len(response_text)
            }
        )

        return {
            'response': response_text,
            'metadata': {
                'intent': analysis['intent'],
                'complete': analysis['has_all_info'],
                'timestamp': datetime.now().isoformat()
            }
        }

    def _analyze_message(
        self,
        message: str,
        sender: str,
        channel: str
    ) -> Dict[str, Any]:
        """
        Analyze message to determine intent and completeness

        Returns:
            Dict with intent, extracted info, missing fields, etc.
        """
        analysis = {
            'intent': 'unknown',
            'has_all_info': False,
            'extracted_info': {},
            'missing_fields': []
        }

        message_lower = message.lower()

        # Detect leave request intent
        leave_keywords = ['leave', 'exeat', 'weekend', 'overnight', 'supper']
        if any(keyword in message_lower for keyword in leave_keywords):
            analysis['intent'] = 'leave_request'

            # Check for student identifier
            if not any(indicator in message_lower for indicator in ['son', 'daughter', 'child', 'student']):
                analysis['missing_fields'].append('student_identifier')

            # Check for dates
            date_indicators = ['tomorrow', 'saturday', 'weekend', 'friday',
                             'monday', 'tuesday', 'wednesday', 'thursday',
                             'next week', 'this weekend']
            has_date = any(indicator in message_lower for indicator in date_indicators)

            # Also check for numeric dates
            import re
            date_patterns = [r'\d{1,2}[/-]\d{1,2}', r'\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)']
            has_date = has_date or any(re.search(pattern, message_lower) for pattern in date_patterns)

            if not has_date:
                analysis['missing_fields'].append('dates')

            # Check for leave type clarity
            leave_type_clear = any(keyword in message_lower for keyword in
                                  ['overnight', 'friday supper', 'day leave', 'day exeat'])
            if not leave_type_clear:
                analysis['missing_fields'].append('leave_type')

            # Determine if we have enough info
            analysis['has_all_info'] = len(analysis['missing_fields']) == 0

        # Detect balance query
        elif any(keyword in message_lower for keyword in ['balance', 'how many', 'remaining']):
            analysis['intent'] = 'balance_query'

        # Detect general query
        elif any(keyword in message_lower for keyword in ['?', 'how', 'what', 'when', 'can']):
            analysis['intent'] = 'question'

        return analysis

    def _generate_conversational_response(
        self,
        message: str,
        sender: str,
        channel: str,
        analysis: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate a conversational response using Claude AI

        Args:
            message: User's message
            sender: Sender identifier
            channel: Communication channel
            analysis: Message analysis results
            conversation_history: Previous conversation

        Returns:
            Generated response text
        """
        if not self.client:
            # Fallback response when API key not configured
            return self._generate_fallback_response(analysis)

        try:
            # Build conversation context
            messages = []

            # Add conversation history if available
            if conversation_history:
                for msg in conversation_history[-10:]:  # Last 10 messages
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })

            # Add current message
            messages.append({
                "role": "user",
                "content": message
            })

            # Build system prompt with analysis context
            system_prompt = self.context + f"""

Current Analysis:
- Intent: {analysis['intent']}
- Has complete info: {analysis['has_all_info']}
- Missing fields: {', '.join(analysis['missing_fields']) if analysis['missing_fields'] else 'none'}

If this is a leave request and information is missing, specifically ask for the missing fields.
If you need a student ID, say so explicitly.
If dates are unclear, ask for clarification.

Be concise and helpful."""

            # Call Anthropic API
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                system=system_prompt,
                messages=messages
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return self._generate_fallback_response(analysis)

    def _generate_fallback_response(self, analysis: Dict[str, Any]) -> str:
        """Generate a simple response when AI is not available"""
        if analysis['intent'] == 'leave_request':
            if 'student_identifier' in analysis['missing_fields']:
                return "I need the student's name or ID number to process this leave request. Could you please provide it?"
            elif 'dates' in analysis['missing_fields']:
                return "I need the specific dates for this leave. When should the leave start and end?"
            elif 'leave_type' in analysis['missing_fields']:
                return "What type of leave is this? (overnight, Friday supper, or day leave)"
            else:
                return "Thank you for your leave request. Let me process that for you."
        else:
            return "I can help you with leave requests. Please provide the student name, dates, and type of leave you need."

    def log_leave_request_analysis(
        self,
        chat_id: str,
        message: str,
        extracted_info: Dict[str, Any],
        missing_fields: List[str],
        next_action: str
    ):
        """
        Log detailed leave request analysis (like the Go version but in Python)

        Args:
            chat_id: Chat identifier
            message: Original message
            extracted_info: Information extracted from message
            missing_fields: Required fields that are missing
            next_action: What the agent should do next
        """
        self.agent_logger.log_leave_request_analysis(
            chat_id=chat_id,
            message=message,
            extracted_info=extracted_info,
            missing_fields=missing_fields,
            next_action=next_action
        )
