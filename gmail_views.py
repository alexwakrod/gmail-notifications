import discord
import asyncio
import re
from config import EMOJIS, COLORS, FOOTER_TEXT
import database as db

class GmailMessageView(discord.ui.View):
    def __init__(self, message_id, thread_id, full_body):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.thread_id = thread_id
        self.full_body = full_body

        # Reply button
        reply_btn = discord.ui.Button(
            label="Reply",
            style=discord.ButtonStyle.primary,
            emoji=EMOJIS['reply'],
            custom_id="gmail_reply"
        )
        reply_btn.callback = self.reply_callback
        self.add_item(reply_btn)

        # Delete button
        delete_btn = discord.ui.Button(
            label="Delete",
            style=discord.ButtonStyle.danger,
            emoji=EMOJIS['delete'],
            custom_id="gmail_delete"
        )
        delete_btn.callback = self.delete_callback
        self.add_item(delete_btn)

        # Copy button (only if code detected)
        code_match = re.search(r'\b\d{6,8}\b', full_body) or re.search(r'\b[A-Z0-9]{8,}\b', full_body)
        if code_match:
            self.code = code_match.group()
            copy_btn = discord.ui.Button(
                label="Copy Code",
                style=discord.ButtonStyle.secondary,
                emoji=EMOJIS['copy'],
                custom_id="gmail_copy"
            )
            copy_btn.callback = self.copy_callback
            self.add_item(copy_btn)

        # Read All link button
        gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"
        self.add_item(discord.ui.Button(
            label="Read All",
            style=discord.ButtonStyle.link,
            url=gmail_url,
            emoji="🔗"
        ))

    async def reply_callback(self, interaction: discord.Interaction):
        modal = ReplyModal(self.message_id, self.thread_id)
        await interaction.response.send_modal(modal)

    async def delete_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        bot = interaction.client
        gmail_api = getattr(bot, 'gmail_api', None)
        if not gmail_api:
            await interaction.followup.send("Gmail API not available.", ephemeral=True)
            return

        success = await gmail_api.delete_message(self.message_id)
        if success:
            db.mark_deleted(self.message_id)
            await interaction.followup.send("✅ Email deleted.", ephemeral=True)
            embed = interaction.message.embeds[0]
            embed.title = f"[DELETED] {embed.title}"
            embed.color = COLORS['error']
            await interaction.message.edit(embed=embed, view=None)
        else:
            await interaction.followup.send("❌ Failed to delete email.", ephemeral=True)

    async def copy_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"📋 Code: `{self.code}`", ephemeral=True)

class ReplyModal(discord.ui.Modal, title="Reply to Email"):
    reply_text = discord.ui.TextInput(
        label="Your Reply",
        style=discord.TextStyle.paragraph,
        placeholder="Type your reply here...",
        max_length=2000,
        required=True
    )

    def __init__(self, message_id, thread_id):
        super().__init__()
        self.message_id = message_id
        self.thread_id = thread_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        bot = interaction.client
        gmail_api = getattr(bot, 'gmail_api', None)
        if not gmail_api:
            await interaction.followup.send("Gmail API not available.", ephemeral=True)
            return

        success = await gmail_api.send_reply(self.thread_id, self.message_id, self.reply_text.value)
        if success:
            await interaction.followup.send("✅ Reply sent.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to send reply.", ephemeral=True)