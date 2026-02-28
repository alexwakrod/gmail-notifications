import os
import json
import asyncio
import aiofiles
import functools
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import GMAIL_SCOPES, GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE

class GmailAuth:
    def __init__(self):
        self.creds = None

    async def load_token(self):
        """Load token from file if exists."""
        if os.path.exists(GMAIL_TOKEN_FILE):
            async with aiofiles.open(GMAIL_TOKEN_FILE, 'r') as f:
                token_data = json.loads(await f.read())
                self.creds = Credentials.from_authorized_user_info(token_data, GMAIL_SCOPES)

    async def save_token(self):
        """Save token to file."""
        if self.creds:
            async with aiofiles.open(GMAIL_TOKEN_FILE, 'w') as f:
                await f.write(self.creds.to_json())

    async def refresh_if_expired(self):
        """Refresh token if expired."""
        if self.creds and self.creds.expired and self.creds.refresh_token:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.creds.refresh, Request())
            await self.save_token()
            return True
        return False

    async def get_credentials(self):
        """Return valid credentials, performing OAuth flow if needed."""
        await self.load_token()
        if self.creds and self.creds.valid:
            return self.creds
        if await self.refresh_if_expired():
            return self.creds

        # No valid credentials, start OAuth flow (blocking, must be run in executor)
        loop = asyncio.get_event_loop()
        flow = InstalledAppFlow.from_client_secrets_file(
            GMAIL_CREDENTIALS_FILE, GMAIL_SCOPES)
        # Use functools.partial to pass port argument
        run_server = functools.partial(flow.run_local_server, port=0)
        creds = await loop.run_in_executor(None, run_server)
        self.creds = creds
        await self.save_token()
        return self.creds