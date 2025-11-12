#!/usr/bin/env python3
"""
Flask API for Michaelhouse Leave System - PRODUCTION VERSION
Uses real database tools instead of placeholders
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify
from processors.leave_processor import LeaveProcessor
from tools.database_tools import DatabaseTools
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('leave_api')

app = Flask(__name__)

# Initialize with real database tools
try:
    logger.info("Initializing database connection...")
    tools = DatabaseTools()
    processor = LeaveProcessor()
    processor.tools = tools
    logger.info("✓ Database tools initialized successfully")
except Exception as e:
    logger.error(f"✗ Failed to initialize database tools: {e}")
    logger.warning("Falling back to placeholder tools")
    processor = LeaveProcessor()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    # Test database connection
    db_status = "connected"
    try:
        if hasattr(processor.tools, '_get_connection'):
            conn = processor.tools._get_connection()
            if conn and not conn.closed:
                db_status = "connected"
            else:
                db_status = "disconnected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return jsonify({
        'status': 'healthy',
        'service': 'Michaelhouse Leave API',
        'version': '1.0.0',
        'database': db_status,
        'tools': 'production' if hasattr(processor.tools, '_get_connection') else 'placeholder'
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
    port = int(os.getenv('FLASK_PORT', 8090))

    logger.info("=" * 70)
    logger.info("Michaelhouse Leave API - PRODUCTION MODE")
    logger.info("=" * 70)
    logger.info(f"Starting on http://0.0.0.0:{port}")
    logger.info("")
    logger.info("Endpoints:")
    logger.info("  GET  /health - Health check")
    logger.info("  POST /api/process_parent_request - Process parent leave requests")
    logger.info("  POST /api/process_housemaster_request - Process housemaster requests")
    logger.info("")
    logger.info("Database Tools: %s", "PRODUCTION" if hasattr(processor.tools, '_get_connection') else "PLACEHOLDER")
    logger.info("=" * 70)

    # Run in development mode
    # For production, use: gunicorn -w 4 -b 0.0.0.0:8090 api_production:app
    app.run(host='0.0.0.0', port=port, debug=False)
