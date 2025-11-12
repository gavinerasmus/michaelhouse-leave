"""
Pytest configuration and fixtures
Shared test utilities
"""

import pytest
import os
import sys
from pathlib import Path

# Add parent directory to path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope='session')
def test_data_dir():
    """Get test data directory"""
    return Path(__file__).parent / 'test_data'


@pytest.fixture
def sample_parent_request():
    """Sample parent leave request"""
    return {
        'message': 'Can James have overnight leave this Saturday 8th February?',
        'sender': '27603174174',
        'channel': 'whatsapp'
    }


@pytest.fixture
def sample_housemaster_request():
    """Sample housemaster request"""
    return {
        'message': 'What is the balance for student 12345?',
        'sender': 'hm.finningley@michaelhouse.org',
        'channel': 'email'
    }


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment for each test"""
    # Save original environment
    original_env = os.environ.copy()

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
