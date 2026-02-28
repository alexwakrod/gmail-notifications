import pyodbc
import logging
import json
from config import DATABASE

logger = logging.getLogger(__name__)

def get_connection():
    try:
        conn = pyodbc.connect(
            driver=DATABASE['driver'],
            server=DATABASE['server'],
            database=DATABASE['database'],
            uid=DATABASE['uid'],
            pwd=DATABASE['pwd'],
            autocommit=False
        )
        return conn
    except pyodbc.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise

def init_db():
    """Create all Gmail bot tables."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # ----- Handshake events (existing) -----
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='handshake_events' AND xtype='U')
            CREATE TABLE handshake_events (
                id INT IDENTITY(1,1) PRIMARY KEY,
                event_type NVARCHAR(50) NOT NULL,
                license_code NVARCHAR(50) NOT NULL,
                details NVARCHAR(MAX),
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        conn.commit()

        # ----- Gmail watch records -----
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='gmail_watch' AND xtype='U')
            CREATE TABLE gmail_watch (
                id INT IDENTITY(1,1) PRIMARY KEY,
                expiration BIGINT NOT NULL,
                history_id BIGINT NOT NULL,
                created_at DATETIME DEFAULT GETDATE(),
                renewed_at DATETIME
            )
        """)
        conn.commit()

        # ----- Gmail event logs (notifications) -----
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='gmail_events' AND xtype='U')
            CREATE TABLE gmail_events (
                id INT IDENTITY(1,1) PRIMARY KEY,
                message_id NVARCHAR(100) NOT NULL,
                thread_id NVARCHAR(100) NOT NULL,
                from_email NVARCHAR(255),
                subject NVARCHAR(500),
                snippet NVARCHAR(2000),
                body_preview NVARCHAR(2000),
                has_code BIT DEFAULT 0,
                notified BIT DEFAULT 0,
                deleted BIT DEFAULT 0,
                received_at DATETIME DEFAULT GETDATE(),
                notified_at DATETIME
            )
        """)
        conn.commit()

        logger.info("✅ Gmail Bot database tables initialised.")
    except pyodbc.Error as e:
        logger.error(f"Error creating tables: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

# ---------- Handshake events (existing) ----------
def log_event(event_type: str, license_code: str, details: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO handshake_events (event_type, license_code, details) VALUES (?, ?, ?)",
            (event_type, license_code, details)
        )
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to log event: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# ---------- Gmail watch ----------
def set_watch_record(expiration: int, history_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM gmail_watch")  # only one record
        cursor.execute(
            "INSERT INTO gmail_watch (expiration, history_id) VALUES (?, ?)",
            (expiration, history_id)
        )
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to set watch record: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_watch_record():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT TOP 1 expiration, history_id, created_at FROM gmail_watch ORDER BY id DESC")
        row = cursor.fetchone()
        if row:
            return (row.expiration, row.history_id, row.created_at)
        return None
    except pyodbc.Error as e:
        logger.error(f"Failed to get watch record: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def update_watch_renewal():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE gmail_watch SET renewed_at = GETDATE()")
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to update watch renewal: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# ---------- Gmail events ----------
def log_gmail_event(message_id: str, thread_id: str, from_email: str, subject: str, snippet: str, body_preview: str, has_code: bool):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO gmail_events (message_id, thread_id, from_email, subject, snippet, body_preview, has_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (message_id, thread_id, from_email, subject, snippet, body_preview, has_code))
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to log gmail event: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def mark_notified(message_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE gmail_events SET notified = 1, notified_at = GETDATE() WHERE message_id = ?", (message_id,))
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to mark notified: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def mark_deleted(message_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE gmail_events SET deleted = 1 WHERE message_id = ?", (message_id,))
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to mark deleted: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()