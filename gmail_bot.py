import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio

from config import (
    EMOJIS, COLORS, FOOTER_TEXT,
    ADMIN_USER_ID, GMAIL_CREDENTIALS_FILE
)
import database as db
from auth import GmailAuth
from gmail_api import GmailAPI
from watch_manager import WatchManager
from pubsub_listener import PubSubListener

logger = logging.getLogger(__name__)

def admin_only():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id != ADMIN_USER_ID:
            embed = discord.Embed(
                title=f"{EMOJIS['error']} Permission Denied",
                description="This command is only for the bot owner.",
                color=COLORS['error']
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

class GmailBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth = GmailAuth()
        self.gmail_api = None
        self.watch_manager = None
        self.listener = None
        self.bot.gmail_api = None  # placeholder for views to access

    async def cog_load(self):
        """Initialize Gmail connection and start services."""
        logger.info("Initializing Gmail bot...")
        try:
            creds = await self.auth.get_credentials()
            self.gmail_api = GmailAPI(creds)
            self.bot.gmail_api = self.gmail_api  # make available to views
            self.watch_manager = WatchManager(self.bot, self.gmail_api)
            self.listener = PubSubListener(self.bot, self.gmail_api)

            # Start watch renewal background task
            self.watch_manager.start_background_task()

            # Start Pub/Sub listener in background
            asyncio.create_task(self.listener.start())

            logger.info("Gmail bot initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize Gmail bot: {e}", exc_info=True)

    async def cog_unload(self):
        """Cleanup on unload."""
        if self.listener:
            await self.listener.stop()
        if self.watch_manager:
            await self.watch_manager.stop_watch()

    @app_commands.command(name="setup", description="Start Gmail notifications (admin only)")
    @admin_only()
    async def setup(self, interaction: discord.Interaction):
        """Start the watch and confirm."""
        await interaction.response.defer(ephemeral=True)
        if not self.watch_manager:
            await interaction.followup.send("Gmail not initialized.", ephemeral=True)
            return

        success = await self.watch_manager.start_watch()
        if success:
            # Also ensure listener is running
            if not self.listener.running:
                asyncio.create_task(self.listener.start())
            embed = discord.Embed(
                title=f"{EMOJIS['success']} Gmail Notifications Started",
                description="You will now receive notifications for new emails via DM.",
                color=COLORS['success']
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title=f"{EMOJIS['error']} Failed to Start",
                description="Could not start Gmail watch. Check logs.",
                color=COLORS['error']
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # Optional command to test sending a notification manually
    @app_commands.command(name="testmail", description="Test: process a specific message ID (admin only)")
    @admin_only()
    async def testmail(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)
        if not self.listener:
            await interaction.followup.send("Listener not ready.", ephemeral=True)
            return
        await self.listener.process_message(message_id)
        await interaction.followup.send(f"Processed message {message_id}.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(GmailBotCog(bot))