"""
Unit tests for Flask API endpoints
Tests API request/response handling
"""

import pytest
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import app as dev_app


class TestLeaveAPI:
    """Test suite for Flask API"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        dev_app.config['TESTING'] = True
        with dev_app.test_client() as client:
            yield client

    # ==================== Health Check Tests ====================

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get('/health')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'service' in data

    # ==================== Parent Request Tests ====================

    def test_process_parent_request_success(self, client):
        """Test successful parent request"""
        payload = {
            'message': 'Can James have overnight leave this Saturday?',
            'sender': '27603174174',
            'channel': 'whatsapp'
        }

        response = client.post(
            '/api/process_parent_request',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'status' in data
        assert 'message' in data

    def test_process_parent_request_missing_fields(self, client):
        """Test request with missing fields"""
        payload = {
            'message': 'Can James have leave?'
            # Missing 'sender' and 'channel'
        }

        response = client.post(
            '/api/process_parent_request',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'missing' in data['message'].lower()

    def test_process_parent_request_invalid_channel(self, client):
        """Test request with invalid channel"""
        payload = {
            'message': 'Can James have leave?',
            'sender': '27603174174',
            'channel': 'sms'  # Invalid
        }

        response = client.post(
            '/api/process_parent_request',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'invalid channel' in data['message'].lower()

    def test_process_parent_request_no_json(self, client):
        """Test request without JSON data"""
        response = client.post('/api/process_parent_request')

        assert response.status_code == 400

    def test_process_parent_request_email_channel(self, client):
        """Test parent request via email channel"""
        payload = {
            'message': 'Request leave for Michael Doe on 14th February',
            'sender': 'jane.doe@example.com',
            'channel': 'email'
        }

        response = client.post(
            '/api/process_parent_request',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'status' in data

    # ==================== Housemaster Request Tests ====================

    def test_process_housemaster_request_success(self, client):
        """Test successful housemaster request"""
        payload = {
            'message': 'What is the balance for student 12345?',
            'sender': 'hm.finningley@michaelhouse.org',
            'channel': 'email'
        }

        response = client.post(
            '/api/process_housemaster_request',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'status' in data
        assert 'message' in data

    def test_process_housemaster_request_missing_fields(self, client):
        """Test housemaster request with missing fields"""
        payload = {
            'message': 'What is the balance?'
            # Missing sender and channel
        }

        response = client.post(
            '/api/process_housemaster_request',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_process_housemaster_request_whatsapp(self, client):
        """Test housemaster request via WhatsApp"""
        payload = {
            'message': 'Balance for 12345',
            'sender': '27831112222',  # HM phone
            'channel': 'whatsapp'
        }

        response = client.post(
            '/api/process_housemaster_request',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

    # ==================== Error Handling Tests ====================

    def test_404_error(self, client):
        """Test 404 handling"""
        response = client.get('/api/nonexistent')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['status'] == 'error'

    def test_method_not_allowed(self, client):
        """Test method not allowed"""
        response = client.get('/api/process_parent_request')

        assert response.status_code == 405

    # ==================== Response Format Tests ====================

    def test_response_has_required_fields(self, client):
        """Test that responses have required fields"""
        payload = {
            'message': 'Can James have leave?',
            'sender': '27603174174',
            'channel': 'whatsapp'
        }

        response = client.post(
            '/api/process_parent_request',
            data=json.dumps(payload),
            content_type='application/json'
        )

        data = json.loads(response.data)
        assert 'status' in data
        assert 'message' in data

    def test_response_is_json(self, client):
        """Test that responses are JSON"""
        response = client.get('/health')

        assert response.content_type == 'application/json'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
