import base64
import re
from email.utils import parsedate_to_datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
import asyncio

logger = logging.getLogger(__name__)

class GmailAPI:
    def __init__(self, credentials):
        self.service = build('gmail', 'v1', credentials=credentials, cache_discovery=False)

    async def get_user_profile(self):
        """Get user's email address."""
        loop = asyncio.get_event_loop()
        try:
            profile = await loop.run_in_executor(None, self.service.users().getProfile(userId='me').execute)
            return profile
        except HttpError as e:
            logger.error(f"Failed to get profile: {e}")
            return None

    async def start_watch(self, topic_name: str):
        """Start watching for changes."""
        body = {
            'labelIds': ['INBOX'],
            'topicName': topic_name
        }
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(None, self.service.users().watch(userId='me', body=body).execute)
            return response
        except HttpError as e:
            logger.error(f"Failed to start watch: {e}")
            return None

    async def stop_watch(self):
        """Stop watching (cleanup)."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self.service.users().stop(userId='me').execute)
        except HttpError as e:
            logger.error(f"Failed to stop watch: {e}")

    async def get_message(self, message_id: str):
        """Fetch full message by ID."""
        loop = asyncio.get_event_loop()
        try:
            msg = await loop.run_in_executor(None, self.service.users().messages().get(userId='me', id=message_id, format='full').execute)
            return msg
        except HttpError as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None

    async def get_message_metadata(self, message_id: str):
        """Fetch only metadata to extract from, subject, snippet."""
        loop = asyncio.get_event_loop()
        try:
            msg = await loop.run_in_executor(None, self.service.users().messages().get(userId='me', id=message_id, format='metadata').execute)
            return msg
        except HttpError as e:
            logger.error(f"Failed to get message metadata {message_id}: {e}")
            return None

    async def delete_message(self, message_id: str):
        """Delete a message permanently."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self.service.users().messages().delete(userId='me', id=message_id).execute)
            return True
        except HttpError as e:
            logger.error(f"Failed to delete message {message_id}: {e}")
            return False

    async def send_reply(self, thread_id: str, message_id: str, reply_text: str):
        """Send a reply in the same thread."""
        # First get the original message to extract headers
        original = await self.get_message(message_id)
        if not original:
            return False
        # Extract headers
        headers = {h['name']: h['value'] for h in original['payload']['headers']}
        to = headers.get('From')
        subject = headers.get('Subject', '')
        if not subject.startswith('Re:'):
            subject = f"Re: {subject}"

        # Create reply message
        from email.message import EmailMessage
        import base64

        mime_message = EmailMessage()
        mime_message.set_content(reply_text)
        mime_message['To'] = to
        mime_message['Subject'] = subject
        mime_message['In-Reply-To'] = message_id
        mime_message['References'] = message_id

        encoded_message = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()

        body = {
            'raw': encoded_message,
            'threadId': thread_id
        }
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self.service.users().messages().send(userId='me', body=body).execute)
            return True
        except HttpError as e:
            logger.error(f"Failed to send reply: {e}")
            return False

    def extract_body_text(self, msg):
        """Extract plain text body from message payload."""
        parts = []
        if 'payload' in msg:
            self._extract_parts(msg['payload'], parts)
        return '\n'.join(parts)

    def _extract_parts(self, payload, parts):
        if payload.get('mimeType') == 'text/plain' and 'data' in payload.get('body', {}):
            data = payload['body']['data']
            text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            parts.append(text)
        elif 'parts' in payload:
            for part in payload['parts']:
                self._extract_parts(part, parts)