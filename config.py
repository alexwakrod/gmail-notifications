import os
from dotenv import load_dotenv

load_dotenv()

# ---------- Discord ----------
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')

# ---------- Master Bot Configuration ----------
MASTER_BOT_ID = "MASTERBOTID"        # Discord User ID of the Master Bot
LICENSE_CODE = "BOT-####-####-###-###"     # Your unique license code
MASTER_SECRET = "ꝥ"                         # Must match Master Bot's secret

# ---------- Channels ----------
VERIFY_GUILD_ID = 1470718373959569650
VERIFY_CHANNEL_ID = 1471510775045685475
PATCH_CHANNEL_ID = 1471523020660015261

# ---------- Timeout ----------
VERIFY_TIMEOUT = 15

# ---------- Public channel (optional) ----------
PUBLIC_GUILD_ID = None
PUBLIC_CHANNEL_ID = None

# ---------- Database (SQL Server Authentication) ----------
DATABASE = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'localhost',
    'database': 'DISCORDBOT',
    'uid': 'SQL_ID',
    'pwd': 'SQL_PW'
}

# ---------- Gmail API Configuration ----------
GMAIL_SCOPES = ['https://mail.google.com/']
GMAIL_CREDENTIALS_FILE = 'credentials.json'
GMAIL_TOKEN_FILE = 'token.json'

# ---------- Google Cloud Pub/Sub ----------
GCP_PROJECT_ID = 'exemplary-torch-470317-i1'
GCP_TOPIC_NAME = 'gmail-notifications'
GCP_SUBSCRIPTION_NAME = 'gmail-sub'

# ---------- Admin User (for DMs) ----------
ADMIN_USER_ID = 1399234194281861201  # Your Discord user ID

# ---------- Embed Branding ----------
EMOJIS = {
    'success': '✅',
    'error': '❌',
    'info': 'ℹ️',
    'warning': '⚠️',
    'verified': '🔐',
    'patch': '📦',
    'mail': '📧',
    'reply': '↩️',
    'delete': '🗑️',
    'copy': '📋'
}
COLORS = {
    'success': 0x2ecc71,
    'error': 0xe74c3c,
    'info': 0x5865f2,
    'warning': 0xf39c12,
    'gmail': 0xDB4437
}
FOOTER_TEXT = "Gmail Bot – By AW (Alex Wakrod)"

# ---------- File Paths ----------
PATCH_FOLDER = "patches"
