"""
Simplified Google Sheets Backend using Personal Google Account

This version uses OAuth 2.0 with your personal Google account instead of
a service account. Much simpler setup for local testing!

Setup:
1. Enable Google Sheets API in your Google account (2 minutes)
2. Download OAuth credentials
3. Run initial authentication (opens browser once)
4. Done! Token is saved for future use
"""

import os
import pickle
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import uuid

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Warning: Google Sheets dependencies not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    raise

from tools.google_sheets_tools import GoogleSheetsTools as BaseGoogleSheetsTools


class GoogleSheetsSimple(BaseGoogleSheetsTools):
    """
    Simplified Google Sheets backend using personal Google account OAuth.

    No service account needed - just your regular Google account!
    """

    # OAuth scopes needed
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    def __init__(self, credentials_path: Optional[str] = None, sheet_id: Optional[str] = None):
        """
        Initialize with personal Google account OAuth.

        Args:
            credentials_path: Path to OAuth client credentials JSON (from Google Console)
            sheet_id: Google Sheets document ID
        """
        # Get configuration
        self.credentials_path = credentials_path or os.getenv('GOOGLE_OAUTH_CREDENTIALS_PATH')
        self.sheet_id = sheet_id or os.getenv('GOOGLE_SHEET_ID')

        if not self.credentials_path:
            raise ValueError("GOOGLE_OAUTH_CREDENTIALS_PATH not set in environment")
        if not self.sheet_id:
            raise ValueError("GOOGLE_SHEET_ID not set in environment")

        # Token storage path (next to credentials)
        token_dir = os.path.dirname(self.credentials_path)
        self.token_path = os.path.join(token_dir, 'token.pickle')

        # Initialize API service
        self.service = self._initialize_service()
        self.cache = {}

    def _initialize_service(self):
        """Initialize Google Sheets API with OAuth."""
        creds = None

        # Check if we have a saved token
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Refresh the token
                print("Refreshing Google authentication token...")
                creds.refresh(Request())
            else:
                # First time authentication - will open browser
                print("\n" + "="*60)
                print("GOOGLE AUTHENTICATION REQUIRED")
                print("="*60)
                print("\nA browser window will open for you to sign in with Google.")
                print("Please authorize access to Google Sheets.")
                print("This only needs to be done once.\n")

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path,
                    self.SCOPES
                )
                creds = flow.run_local_server(port=0)

                print("\n✅ Authentication successful!")
                print(f"Token saved to: {self.token_path}\n")

            # Save the credentials for next time
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)

        # Build the service
        try:
            service = build('sheets', 'v4', credentials=creds)
            return service
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Sheets API: {e}")


# Convenience function for simple initialization
def create_sheets_backend():
    """
    Create a Google Sheets backend with automatic OAuth.

    This will:
    1. Check for saved authentication token
    2. If not found, open browser for one-time authentication
    3. Save token for future use
    4. Return initialized backend

    Usage:
        tools = create_sheets_backend()
        processor.tools = tools
    """
    return GoogleSheetsSimple()
