import asyncio
import logging
from datetime import datetime, timezone, timedelta
from googleapiclient.errors import HttpError

from config import GCP_TOPIC_NAME
import database as db
from gmail_api import GmailAPI

logger = logging.getLogger(__name__)

class WatchManager:
    def __init__(self, bot, gmail_api):
        self.bot = bot
        self.gmail_api = gmail_api
        self._task = None
        self.topic_name = f"projects/exemplary-torch-470317-i1/topics/{GCP_TOPIC_NAME}"

    async def start_watch(self):
        """Start or renew the Gmail watch."""
        try:
            response = await self.gmail_api.start_watch(self.topic_name)
            if response:
                expiration = int(response['expiration'])
                history_id = int(response['historyId'])
                db.set_watch_record(expiration, history_id)
                logger.info(f"Watch started, expires at {expiration} (timestamp)")
                return True
        except HttpError as e:
            logger.error(f"Failed to start watch: {e}")
        return False

    async def stop_watch(self):
        """Stop the watch (cleanup)."""
        await self.gmail_api.stop_watch()
        logger.info("Watch stopped")

    async def check_and_renew(self):
        """Check if watch is expiring soon and renew."""
        record = db.get_watch_record()
        if not record:
            # No watch, start one
            logger.info("No watch record found, starting...")
            await self.start_watch()
            return

        expiration, history_id, created_at = record
        # expiration is a Unix timestamp in milliseconds
        now = datetime.now(timezone.utc)
        exp_time = datetime.fromtimestamp(expiration / 1000, tz=timezone.utc)
        # Renew if within 1 day of expiry
        if exp_time - now < timedelta(days=1):
            logger.info(f"Watch expiring soon at {exp_time}, renewing...")
            await self.start_watch()
        else:
            logger.debug(f"Watch valid until {exp_time}")

    async def run_periodic_check(self):
        """Background task that checks every 6 hours."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self.check_and_renew()
            except Exception as e:
                logger.error(f"Error in watch renewal: {e}")
            await asyncio.sleep(6 * 3600)  # 6 hours

    def start_background_task(self):
        """Start the periodic check task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run_periodic_check())