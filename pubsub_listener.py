import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from google.cloud import pubsub_v1
from google.api_core.exceptions import NotFound
import discord

from config import (
    GCP_PROJECT_ID, GCP_SUBSCRIPTION_NAME,
    ADMIN_USER_ID, EMOJIS, COLORS, FOOTER_TEXT
)
import database as db
from gmail_api import GmailAPI
from gmail_views import GmailMessageView

logger = logging.getLogger(__name__)

# Discord embed limits
DESCRIPTION_MAX = 4000
FIELD_VALUE_MAX = 1024

class PubSubListener:
    def __init__(self, bot, gmail_api):
        self.bot = bot
        self.gmail_api = gmail_api
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(GCP_PROJECT_ID, GCP_SUBSCRIPTION_NAME)
        self.streaming_pull_future = None
        self.running = False
        self.admin_user = None

    async def get_admin_user(self):
        """Fetch the admin user (cached)."""
        if self.admin_user is None:
            self.admin_user = await self.bot.fetch_user(ADMIN_USER_ID)
        return self.admin_user

    def callback(self, message):
        """Synchronous callback from Pub/Sub – schedules async processing on bot's loop."""
        asyncio.run_coroutine_threadsafe(
            self.process_notification(message),
            self.bot.loop
        )
        message.ack()

    async def process_notification(self, pubsub_message):
        """Process a single notification from Gmail using history."""
        try:
            data = json.loads(pubsub_message.data.decode('utf-8'))
            history_id = data.get('historyId')
            email = data.get('emailAddress')
            logger.info(f"Received notification for {email}, historyId: {history_id}")

            # Get the last stored history ID
            record = db.get_watch_record()
            if not record:
                logger.warning("No watch record found, skipping history fetch.")
                return
            last_history_id = record[1]

            # Ignore notifications that are older than our last processed history ID
            if history_id <= last_history_id:
                logger.debug(f"Ignoring old notification: history_id {history_id} <= {last_history_id}")
                return

            # Fetch history since last_history_id + 1
            loop = asyncio.get_event_loop()
            service = self.gmail_api.service
            try:
                history_response = await loop.run_in_executor(
                    None,
                    lambda: service.users().history().list(
                        userId='me',
                        startHistoryId=last_history_id + 1,
                        historyTypes=['messageAdded']
                    ).execute()
                )
            except Exception as e:
                logger.error(f"Failed to fetch history: {e}")
                return

            histories = history_response.get('history', [])
            for hist in histories:
                messages_added = hist.get('messagesAdded', [])
                for msg_added in messages_added:
                    msg = msg_added.get('message')
                    if msg:
                        msg_id = msg['id']
                        await self.process_message(msg_id)

            # Update stored history ID to the latest one
            db.update_history_id(history_id)

        except Exception as e:
            logger.error(f"Error processing notification: {e}", exc_info=True)

    async def process_message(self, message_id):
        """Fetch full message and send to admin."""
        msg = await self.gmail_api.get_message_metadata(message_id)
        if not msg:
            return

        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        from_email = headers.get('From', 'Unknown')
        subject = headers.get('Subject', '(no subject)')
        snippet = msg.get('snippet', '')

        full_msg = await self.gmail_api.get_message(message_id)
        body_text = self.gmail_api.extract_body_text(full_msg) if full_msg else ''

        # Truncate for display
        if len(snippet) > 500:
            snippet = snippet[:497] + '...'
        if len(body_text) > 1000:
            body_preview = body_text[:997] + '...'
        else:
            body_preview = body_text

        # Detect codes
        code_match = re.search(r'\b\d{6,8}\b', body_text) or re.search(r'\b[A-Z0-9]{8,}\b', body_text)
        has_code = bool(code_match)

        db.log_gmail_event(
            message_id=message_id,
            thread_id=msg['threadId'],
            from_email=from_email,
            subject=subject,
            snippet=snippet,
            body_preview=body_preview,
            has_code=has_code
        )

        admin = await self.get_admin_user()
        if not admin:
            logger.error("Admin user not found")
            return

        embed = discord.Embed(
            title=f"{EMOJIS['mail']} New Email",
            description=f"**From:** {from_email}\n**Subject:** {subject}\n\n{snippet}",
            color=COLORS['gmail'],
            timestamp=datetime.now(timezone.utc)
        )
        if len(body_preview) > 0:
            if len(body_preview) <= DESCRIPTION_MAX - len(embed.description):
                embed.description += f"\n\n{body_preview}"
            else:
                embed.add_field(name="Message Preview", value=body_preview[:FIELD_VALUE_MAX], inline=False)

        if has_code:
            embed.add_field(name="Code Detected", value="This message may contain a verification code.", inline=False)

        view = GmailMessageView(message_id, msg['threadId'], body_text)
        await admin.send(embed=embed, view=view)

        db.mark_notified(message_id)

    async def start(self):
        """Start the Pub/Sub listener."""
        if self.running:
            return
        self.running = True
        try:
            self.streaming_pull_future = self.subscriber.subscribe(
                self.subscription_path,
                callback=self.callback
            )
            logger.info(f"Listening for messages on {self.subscription_path}")
            # Blocking call – run in a separate thread
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._run_streaming_pull)
        except NotFound:
            logger.error(f"Subscription {self.subscription_path} not found")
        except Exception as e:
            logger.error(f"Pub/Sub listener error: {e}")
        finally:
            self.running = False

    def _run_streaming_pull(self):
        """Run the streaming pull future (blocks). This runs in a thread."""
        try:
            self.streaming_pull_future.result()
        except Exception as e:
            logger.error(f"Streaming pull future error: {e}")

    async def stop(self):
        """Stop the listener."""
        if self.streaming_pull_future:
            self.streaming_pull_future.cancel()
        self.running = False