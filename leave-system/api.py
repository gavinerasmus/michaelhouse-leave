#!/usr/bin/env python3
"""
Flask API for Michaelhouse Leave System
Provides HTTP endpoints for WhatsApp bridge integration
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify
from processors.leave_processor import LeaveProcessor
from agents.conversation_agent import ConversationAgent
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('leave_api')

app = Flask(__name__)
processor = LeaveProcessor()

# Initialize conversation agent
# Agent will auto-load context from agents/context.md
import os
conversation_agent = ConversationAgent()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Michaelhouse Leave API',
        'version': '1.0.0'
    })


@app.route('/api/process_parent_request', methods=['POST'])
def process_parent_request():
    """
    Process parent leave request

    Expected JSON:
    {
        "message": "Can James have overnight leave this Saturday?",
        "sender": "27603174174" or "parent@example.com",
        "channel": "whatsapp" or "email"
    }

    Returns:
    {
        "status": "approved|rejected|special_pending|error",
        "message": "Response to send back to parent",
        "reason": "Optional machine-readable reason"
    }
    """
    try:
        data = request.json

        # Validate input
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No JSON data provided'
            }), 400

        required_fields = ['message', 'sender', 'channel']
        missing_fields = [f for f in required_fields if f not in data]

        if missing_fields:
            return jsonify({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400

        message_text = data['message']
        sender_identifier = data['sender']
        channel = data['channel']

        # Validate channel
        if channel not in ['whatsapp', 'email']:
            return jsonify({
                'status': 'error',
                'message': f'Invalid channel: {channel}. Must be "whatsapp" or "email"'
            }), 400

        logger.info(f"Processing parent request from {sender_identifier} via {channel}")

        # Process the request
        result = processor.process_parent_request(
            message_text=message_text,
            sender_identifier=sender_identifier,
            channel=channel
        )

        logger.info(f"Request processed: status={result['status']}")

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error processing parent request: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred processing your request. Please contact the Housemaster.'
        }), 500


@app.route('/api/process_housemaster_request', methods=['POST'])
def process_housemaster_request():
    """
    Process housemaster request (query, cancellation, restriction)

    Expected JSON:
    {
        "message": "What is the balance for student 12345?",
        "sender": "hm.finningley@michaelhouse.org" or housemaster phone,
        "channel": "whatsapp" or "email"
    }

    Returns:
    {
        "status": "success|error",
        "message": "Response to send back to housemaster"
    }
    """
    try:
        data = request.json

        # Validate input
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No JSON data provided'
            }), 400

        required_fields = ['message', 'sender', 'channel']
        missing_fields = [f for f in required_fields if f not in data]

        if missing_fields:
            return jsonify({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400

        message_text = data['message']
        sender_identifier = data['sender']
        channel = data['channel']

        # Validate channel
        if channel not in ['whatsapp', 'email']:
            return jsonify({
                'status': 'error',
                'message': f'Invalid channel: {channel}. Must be "whatsapp" or "email"'
            }), 400

        logger.info(f"Processing housemaster request from {sender_identifier} via {channel}")

        # Process the request
        result = processor.process_housemaster_request(
            message_text=message_text,
            sender_identifier=sender_identifier,
            channel=channel
        )

        logger.info(f"Housemaster request processed: status={result['status']}")

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error processing housemaster request: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred processing your request.'
        }), 500


@app.route('/api/conversation', methods=['POST'])
def conversation():
    """
    Process conversational message through AI agent

    Expected JSON:
    {
        "message": "Can my son have leave this weekend?",
        "sender": "27603174174" or "parent@example.com",
        "channel": "whatsapp" or "email",
        "chat_id": "unique_chat_identifier",
        "conversation_history": [  // optional
            {"role": "user", "content": "previous message"},
            {"role": "assistant", "content": "previous response"}
        ]
    }

    Returns:
    {
        "response": "Generated response text",
        "metadata": {
            "intent": "leave_request|question|balance_query",
            "complete": true|false,
            "timestamp": "2025-01-12T10:30:45"
        }
    }
    """
    try:
        data = request.json

        # Validate input
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No JSON data provided'
            }), 400

        required_fields = ['message', 'sender', 'channel', 'chat_id']
        missing_fields = [f for f in required_fields if f not in data]

        if missing_fields:
            return jsonify({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400

        message = data['message']
        sender = data['sender']
        channel = data['channel']
        chat_id = data['chat_id']
        conversation_history = data.get('conversation_history', [])

        # Validate channel
        if channel not in ['whatsapp', 'email']:
            return jsonify({
                'status': 'error',
                'message': f'Invalid channel: {channel}. Must be "whatsapp" or "email"'
            }), 400

        logger.info(f"Processing conversational message from {sender} via {channel}")

        # Process through conversation agent
        result = conversation_agent.process_message(
            message=message,
            sender=sender,
            channel=channel,
            chat_id=chat_id,
            conversation_history=conversation_history
        )

        logger.info(f"Conversation processed: intent={result['metadata']['intent']}")

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error processing conversation: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred processing your message. Please try again.'
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500


if __name__ == '__main__':
    logger.info("Starting Michaelhouse Leave API on http://localhost:8090")
    logger.info("Endpoints:")
    logger.info("  GET  /health - Health check")
    logger.info("  POST /api/conversation - Conversational AI agent (recommended)")
    logger.info("  POST /api/process_parent_request - Process parent leave requests (direct)")
    logger.info("  POST /api/process_housemaster_request - Process housemaster requests")

    # Run in development mode
    # For production, use: gunicorn -w 4 -b 0.0.0.0:8090 api:app
    app.run(host='0.0.0.0', port=8090, debug=True)
