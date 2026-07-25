"""
╔══════════════════════════════════════════════════════════════╗
║         ENTERPRISE AI-POWERED DISCORD MANAGEMENT BOT         ║
║                    Commercial SaaS Grade                     ║
╚══════════════════════════════════════════════════════════════╝

Architecture: Single-file enterprise bot with clear sections.
Language: Python 3.12+
Library: discord.py 2.5+
AI: Grok (xAI) primary, OpenAI fallback
Database: SQLite (PostgreSQL-ready)
"""

# ============================================================
# SECTION: Imports & Configuration
# ============================================================

import asyncio
import aiohttp
import aiofiles
import aiosqlite
import datetime
import hashlib
import io
import json
import logging
import math
import os
import random
import re
import sys
import time
import traceback
from collections import defaultdict, deque
from typing import Optional, List, Dict, Any, Union, Tuple
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks
from openai import AsyncOpenAI
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pytz
import psutil
import qrcode

# ── Load environment variables ─────────────────────────────
load_dotenv()

# ── Configuration ──────────────────────────────────────────
DISCORD_TOKEN  = os.getenv("DISCORD_TOKEN", "")
GROK_API_KEY   = os.getenv("GROK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AI_MODEL       = os.getenv("AI_MODEL", "grok-3-fast")
DATABASE_URL   = os.getenv("DATABASE_URL", "")
BOT_PREFIX     = os.getenv("BOT_PREFIX", "!")
OWNER_ID       = int(os.getenv("OWNER_ID", "0") or "0")
LOG_LEVEL      = os.getenv("LOG_LEVEL", "INFO")
WEATHER_API    = os.getenv("WEATHER_API_KEY", "")

# ── Database path ───────────────────────────────────────────
DB_PATH = "bot_database.db"

# ── Directories ─────────────────────────────────────────────
Path("backups").mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)
Path("transcripts").mkdir(exist_ok=True)

# ── Logging ─────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("DiscordBot")

# ── Version ─────────────────────────────────────────────────
BOT_VERSION = "2.0.0"
BOT_START_TIME = time.time()


# ============================================================
# SECTION: Database
# ============================================================

async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_database():
    """Initialize all database tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # ── guild_config ──────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id        INTEGER PRIMARY KEY,
                prefix          TEXT    DEFAULT '!',
                language        TEXT    DEFAULT 'en',
                timezone        TEXT    DEFAULT 'UTC',
                log_channel     INTEGER,
                mod_log_channel INTEGER,
                welcome_channel INTEGER,
                welcome_message TEXT,
                goodbye_message TEXT,
                welcome_enabled INTEGER DEFAULT 0,
                autorole_ids    TEXT    DEFAULT '[]',
                verification    INTEGER DEFAULT 0,
                captcha_enabled INTEGER DEFAULT 0,
                ai_enabled      INTEGER DEFAULT 1,
                ai_channel      INTEGER,
                ai_always_on    INTEGER DEFAULT 0,
                ai_personality  TEXT    DEFAULT 'default',
                ai_language     TEXT    DEFAULT 'en',
                mute_role       INTEGER,
                jail_role       INTEGER,
                jail_channel    INTEGER,
                staff_role      INTEGER,
                mod_role        INTEGER,
                admin_role      INTEGER,
                ticket_category INTEGER,
                ticket_log      INTEGER,
                ticket_support  TEXT    DEFAULT '[]',
                level_channel   INTEGER,
                level_enabled   INTEGER DEFAULT 1,
                economy_enabled INTEGER DEFAULT 1,
                currency_name   TEXT    DEFAULT 'coins',
                currency_emoji  TEXT    DEFAULT '🪙',
                max_warnings    INTEGER DEFAULT 3,
                created_at      INTEGER DEFAULT (strftime('%s','now')),
                updated_at      INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── users ─────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                guild_id        INTEGER NOT NULL,
                username        TEXT,
                joined_at       INTEGER,
                last_seen       INTEGER,
                message_count   INTEGER DEFAULT 0,
                voice_minutes   INTEGER DEFAULT 0,
                reputation      INTEGER DEFAULT 0,
                timezone        TEXT    DEFAULT 'UTC',
                language        TEXT    DEFAULT 'en',
                birthday        TEXT,
                notes           TEXT    DEFAULT '[]',
                flags           TEXT    DEFAULT '[]',
                created_at      INTEGER DEFAULT (strftime('%s','now')),
                UNIQUE(user_id, guild_id)
            )
        """)

        # ── ai_memory ─────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_memory (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER,
                memory_type TEXT    NOT NULL,
                key         TEXT    NOT NULL,
                value       TEXT    NOT NULL,
                importance  INTEGER DEFAULT 1,
                expires_at  INTEGER,
                created_at  INTEGER DEFAULT (strftime('%s','now')),
                updated_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── ai_conversations ──────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                role        TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                tokens      INTEGER DEFAULT 0,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── ai_actions ────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_actions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                action_type TEXT    NOT NULL,
                description TEXT,
                params      TEXT    DEFAULT '{}',
                result      TEXT,
                success     INTEGER DEFAULT 1,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── tickets ───────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id       TEXT    NOT NULL UNIQUE,
                guild_id        INTEGER NOT NULL,
                channel_id      INTEGER,
                user_id         INTEGER NOT NULL,
                claimed_by      INTEGER,
                department      TEXT    DEFAULT 'general',
                subject         TEXT,
                priority        TEXT    DEFAULT 'normal',
                status          TEXT    DEFAULT 'open',
                panel_id        INTEGER,
                transcript_url  TEXT,
                feedback        INTEGER,
                feedback_text   TEXT,
                first_response  INTEGER,
                closed_at       INTEGER,
                sla_deadline    INTEGER,
                tags            TEXT    DEFAULT '[]',
                internal_notes  TEXT    DEFAULT '[]',
                ai_summary      TEXT,
                created_at      INTEGER DEFAULT (strftime('%s','now')),
                updated_at      INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── ticket_messages ───────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id   TEXT    NOT NULL,
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                username    TEXT,
                content     TEXT,
                attachments TEXT    DEFAULT '[]',
                is_staff    INTEGER DEFAULT 0,
                is_internal INTEGER DEFAULT 0,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── ticket_panels ─────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_panels (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id        INTEGER NOT NULL,
                channel_id      INTEGER NOT NULL,
                message_id      INTEGER,
                name            TEXT    NOT NULL,
                description     TEXT,
                departments     TEXT    DEFAULT '[]',
                color           TEXT    DEFAULT '#5865F2',
                thumbnail       TEXT,
                created_at      INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── ticket_stats ──────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_stats (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id        INTEGER NOT NULL,
                user_id         INTEGER NOT NULL,
                tickets_claimed INTEGER DEFAULT 0,
                tickets_closed  INTEGER DEFAULT 0,
                avg_response    INTEGER DEFAULT 0,
                avg_rating      REAL    DEFAULT 0,
                total_ratings   INTEGER DEFAULT 0,
                messages_sent   INTEGER DEFAULT 0,
                updated_at      INTEGER DEFAULT (strftime('%s','now')),
                UNIQUE(guild_id, user_id)
            )
        """)

        # ── moderation_cases ──────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS moderation_cases (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id     TEXT    NOT NULL UNIQUE,
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                mod_id      INTEGER NOT NULL,
                action      TEXT    NOT NULL,
                reason      TEXT,
                duration    INTEGER,
                expires_at  INTEGER,
                active      INTEGER DEFAULT 1,
                evidence    TEXT    DEFAULT '[]',
                appeal_id   INTEGER,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── warnings ──────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                mod_id      INTEGER NOT NULL,
                reason      TEXT,
                severity    INTEGER DEFAULT 1,
                active      INTEGER DEFAULT 1,
                expires_at  INTEGER,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── appeals ───────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                case_id     TEXT    NOT NULL,
                user_id     INTEGER NOT NULL,
                reason      TEXT    NOT NULL,
                status      TEXT    DEFAULT 'pending',
                reviewer_id INTEGER,
                reviewer_note TEXT,
                created_at  INTEGER DEFAULT (strftime('%s','now')),
                updated_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── logs ──────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                event_type  TEXT    NOT NULL,
                user_id     INTEGER,
                target_id   INTEGER,
                channel_id  INTEGER,
                description TEXT,
                extra_data  TEXT    DEFAULT '{}',
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── economy ───────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                guild_id        INTEGER NOT NULL,
                wallet          INTEGER DEFAULT 0,
                bank            INTEGER DEFAULT 0,
                total_earned    INTEGER DEFAULT 0,
                total_spent     INTEGER DEFAULT 0,
                daily_streak    INTEGER DEFAULT 0,
                last_daily      INTEGER,
                last_weekly     INTEGER,
                last_monthly    INTEGER,
                last_work       INTEGER,
                job             TEXT,
                business        TEXT,
                net_worth       INTEGER DEFAULT 0,
                created_at      INTEGER DEFAULT (strftime('%s','now')),
                updated_at      INTEGER DEFAULT (strftime('%s','now')),
                UNIQUE(user_id, guild_id)
            )
        """)

        # ── inventory ─────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                guild_id    INTEGER NOT NULL,
                item_id     TEXT    NOT NULL,
                quantity    INTEGER DEFAULT 1,
                equipped    INTEGER DEFAULT 0,
                expires_at  INTEGER,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── shop ──────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                item_id     TEXT    NOT NULL UNIQUE,
                name        TEXT    NOT NULL,
                description TEXT,
                price       INTEGER NOT NULL,
                type        TEXT    DEFAULT 'item',
                role_id     INTEGER,
                duration    INTEGER,
                stock       INTEGER DEFAULT -1,
                emoji       TEXT    DEFAULT '📦',
                enabled     INTEGER DEFAULT 1,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── levels ────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS levels (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                guild_id        INTEGER NOT NULL,
                xp              INTEGER DEFAULT 0,
                level           INTEGER DEFAULT 0,
                prestige        INTEGER DEFAULT 0,
                text_xp         INTEGER DEFAULT 0,
                voice_xp        INTEGER DEFAULT 0,
                xp_boost        REAL    DEFAULT 1.0,
                boost_expires   INTEGER,
                last_message    INTEGER,
                created_at      INTEGER DEFAULT (strftime('%s','now')),
                updated_at      INTEGER DEFAULT (strftime('%s','now')),
                UNIQUE(user_id, guild_id)
            )
        """)

        # ── role_rewards ──────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS role_rewards (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                level       INTEGER NOT NULL,
                role_id     INTEGER NOT NULL,
                prestige    INTEGER DEFAULT 0,
                remove_prev INTEGER DEFAULT 0,
                UNIQUE(guild_id, level, prestige)
            )
        """)

        # ── automod_rules ─────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS automod_rules (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                rule_type   TEXT    NOT NULL,
                enabled     INTEGER DEFAULT 1,
                action      TEXT    DEFAULT 'warn',
                threshold   INTEGER DEFAULT 5,
                duration    INTEGER DEFAULT 300,
                whitelist   TEXT    DEFAULT '[]',
                extra       TEXT    DEFAULT '{}',
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── anti_raid ─────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS anti_raid (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id            INTEGER NOT NULL UNIQUE,
                enabled             INTEGER DEFAULT 1,
                join_threshold      INTEGER DEFAULT 10,
                join_window         INTEGER DEFAULT 10,
                bot_protection      INTEGER DEFAULT 1,
                webhook_protection  INTEGER DEFAULT 1,
                lockdown_active     INTEGER DEFAULT 0,
                lockdown_reason     TEXT,
                lockdown_at         INTEGER,
                verification_mode   INTEGER DEFAULT 0,
                action              TEXT    DEFAULT 'kick',
                updated_at          INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── reaction_roles ────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                role_id     INTEGER NOT NULL,
                emoji       TEXT    NOT NULL,
                style       TEXT    DEFAULT 'button',
                label       TEXT,
                exclusive   INTEGER DEFAULT 0,
                stackable   INTEGER DEFAULT 1,
                temp_hours  INTEGER DEFAULT 0,
                min_level   INTEGER DEFAULT 0,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── backups ───────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS backups (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                backup_id   TEXT    NOT NULL UNIQUE,
                name        TEXT,
                type        TEXT    DEFAULT 'full',
                data        TEXT    NOT NULL,
                size_bytes  INTEGER DEFAULT 0,
                created_by  INTEGER,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── scheduled_tasks ───────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                task_type   TEXT    NOT NULL,
                channel_id  INTEGER,
                user_id     INTEGER,
                data        TEXT    DEFAULT '{}',
                run_at      INTEGER NOT NULL,
                repeat      INTEGER DEFAULT 0,
                repeat_sec  INTEGER DEFAULT 0,
                active      INTEGER DEFAULT 1,
                last_run    INTEGER,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── reminders ─────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                message     TEXT    NOT NULL,
                remind_at   INTEGER NOT NULL,
                repeat      INTEGER DEFAULT 0,
                repeat_sec  INTEGER DEFAULT 0,
                active      INTEGER DEFAULT 1,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── giveaways ─────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                giveaway_id     TEXT    NOT NULL UNIQUE,
                guild_id        INTEGER NOT NULL,
                channel_id      INTEGER NOT NULL,
                message_id      INTEGER,
                host_id         INTEGER NOT NULL,
                prize           TEXT    NOT NULL,
                description     TEXT,
                winners_count   INTEGER DEFAULT 1,
                entries         TEXT    DEFAULT '[]',
                bonus_roles     TEXT    DEFAULT '{}',
                req_role        INTEGER,
                req_level       INTEGER DEFAULT 0,
                req_messages    INTEGER DEFAULT 0,
                winners         TEXT    DEFAULT '[]',
                status          TEXT    DEFAULT 'active',
                ends_at         INTEGER NOT NULL,
                created_at      INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── polls ─────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id     TEXT    NOT NULL UNIQUE,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                message_id  INTEGER,
                creator_id  INTEGER NOT NULL,
                question    TEXT    NOT NULL,
                options     TEXT    NOT NULL,
                votes       TEXT    DEFAULT '{}',
                anonymous   INTEGER DEFAULT 0,
                multi_vote  INTEGER DEFAULT 0,
                status      TEXT    DEFAULT 'active',
                ends_at     INTEGER,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── suggestions ───────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_id   TEXT    NOT NULL UNIQUE,
                guild_id        INTEGER NOT NULL,
                channel_id      INTEGER NOT NULL,
                message_id      INTEGER,
                user_id         INTEGER NOT NULL,
                content         TEXT    NOT NULL,
                category        TEXT    DEFAULT 'general',
                status          TEXT    DEFAULT 'pending',
                upvotes         INTEGER DEFAULT 0,
                downvotes       INTEGER DEFAULT 0,
                voters          TEXT    DEFAULT '[]',
                reviewer_id     INTEGER,
                reviewer_note   TEXT,
                ai_analysis     TEXT,
                created_at      INTEGER DEFAULT (strftime('%s','now')),
                updated_at      INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── sticky_messages ───────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sticky_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL UNIQUE,
                message_id  INTEGER,
                content     TEXT    NOT NULL,
                embed       TEXT,
                active      INTEGER DEFAULT 1,
                created_at  INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # ── birthdays ─────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS birthdays (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                guild_id    INTEGER NOT NULL,
                birthday    TEXT    NOT NULL,
                timezone    TEXT    DEFAULT 'UTC',
                notified    INTEGER DEFAULT 0,
                UNIQUE(user_id, guild_id)
            )
        """)

        # ── voice_tracking ────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS voice_tracking (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                joined_at   INTEGER NOT NULL,
                left_at     INTEGER,
                duration    INTEGER DEFAULT 0
            )
        """)

        await db.commit()
        log.info("Database initialized successfully.")


# ── Database helpers ─────────────────────────────────────────

async def db_fetch(query: str, *args) -> List[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, args) as cur:
            return await cur.fetchall()


async def db_fetchone(query: str, *args) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, args) as cur:
            return await cur.fetchone()


async def db_execute(query: str, *args) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, args)
        await db.commit()
        return cur.lastrowid


async def get_guild_config(guild_id: int) -> aiosqlite.Row:
    row = await db_fetchone("SELECT * FROM guild_config WHERE guild_id=?", guild_id)
    if not row:
        await db_execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", guild_id
        )
        row = await db_fetchone("SELECT * FROM guild_config WHERE guild_id=?", guild_id)
    return row


async def ensure_user(user_id: int, guild_id: int, username: str = ""):
    await db_execute(
        """INSERT OR IGNORE INTO users (user_id, guild_id, username, last_seen)
           VALUES (?, ?, ?, ?)""",
        user_id, guild_id, username, int(time.time()),
    )


# ── Case ID generator ────────────────────────────────────────
def generate_case_id(guild_id: int) -> str:
    ts = int(time.time() * 1000)
    return f"CASE-{guild_id % 10000:04d}-{ts % 1000000:06d}"


def generate_ticket_id(guild_id: int) -> str:
    ts = int(time.time() * 1000)
    rand = random.randint(100, 999)
    return f"TKT-{rand}-{ts % 100000:05d}"


def generate_id(prefix: str = "ID") -> str:
    ts = int(time.time() * 1000)
    rand = random.randint(1000, 9999)
    return f"{prefix}-{ts % 100000:05d}-{rand}"


# ============================================================
# SECTION: AI System
# ============================================================

class AISystem:
    """Central AI brain for the bot."""

    def __init__(self):
        # Primary: Grok (xAI) via OpenAI-compatible API
        self.grok_client: Optional[AsyncOpenAI] = None
        # Fallback: OpenAI
        self.openai_client: Optional[AsyncOpenAI] = None
        self._init_clients()

        # In-memory rate limiting
        self._cooldowns: Dict[str, float] = {}
        self._usage: Dict[str, int] = defaultdict(int)

        # Personality presets
        self.personalities = {
            "default":    "You are an advanced, helpful Discord server assistant. You are professional, friendly, and concise.",
            "friendly":   "You are a warm, enthusiastic Discord assistant who loves helping the community. Use casual, friendly language.",
            "professional": "You are a formal, professional server assistant. Be concise, accurate, and business-like.",
            "strict":     "You are a strict, no-nonsense server assistant focused on rules enforcement and order.",
            "fun":        "You are a fun, witty Discord assistant with a great sense of humor. Keep things light and entertaining.",
            "teacher":    "You are a patient, educational assistant who explains things clearly with examples.",
        }

    def _init_clients(self):
        if GROK_API_KEY:
            self.grok_client = AsyncOpenAI(
                api_key=GROK_API_KEY,
                base_url="https://api.x.ai/v1",
            )
            log.info("Grok (xAI) AI client initialized.")
        if OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            log.info("OpenAI client initialized (fallback).")
        if not self.grok_client and not self.openai_client:
            log.warning("No AI API keys set. AI features will be limited.")

    async def _call_ai(
        self,
        messages: List[Dict],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Call the AI API with fallback support."""
        model = model or AI_MODEL
        client = self.grok_client or self.openai_client
        if not client:
            return "AI is not configured. Please set GROK_API_KEY or OPENAI_API_KEY."

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"Primary AI error: {e}")
            # Try fallback
            if self.openai_client and client is not self.openai_client:
                try:
                    response = await self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    return response.choices[0].message.content.strip()
                except Exception as e2:
                    log.error(f"Fallback AI error: {e2}")
            return f"AI error: {str(e)}"

    def is_on_cooldown(self, key: str, seconds: int = 5) -> bool:
        now = time.time()
        last = self._cooldowns.get(key, 0)
        if now - last < seconds:
            return True
        self._cooldowns[key] = now
        return False

    async def get_memory(self, guild_id: int, user_id: int = None, limit: int = 20) -> str:
        """Get relevant AI memory for context."""
        if user_id:
            rows = await db_fetch(
                """SELECT memory_type, key, value FROM ai_memory
                   WHERE guild_id=? AND (user_id=? OR user_id IS NULL)
                     AND (expires_at IS NULL OR expires_at > ?)
                   ORDER BY importance DESC, updated_at DESC LIMIT ?""",
                guild_id, user_id, int(time.time()), limit,
            )
        else:
            rows = await db_fetch(
                """SELECT memory_type, key, value FROM ai_memory
                   WHERE guild_id=? AND (expires_at IS NULL OR expires_at > ?)
                   ORDER BY importance DESC, updated_at DESC LIMIT ?""",
                guild_id, int(time.time()), limit,
            )
        if not rows:
            return ""
        mem_parts = [f"[{r['memory_type']}] {r['key']}: {r['value']}" for r in rows]
        return "\n".join(mem_parts)

    async def save_memory(self, guild_id: int, user_id: Optional[int],
                          memory_type: str, key: str, value: str,
                          importance: int = 1, expires_in: int = None):
        """Save a memory entry."""
        expires_at = int(time.time()) + expires_in if expires_in else None
        await db_execute(
            """INSERT INTO ai_memory (guild_id, user_id, memory_type, key, value, importance, expires_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT DO UPDATE SET value=excluded.value, importance=excluded.importance,
               expires_at=excluded.expires_at, updated_at=excluded.updated_at""",
            guild_id, user_id, memory_type, key, value, importance, expires_at, int(time.time()),
        )

    async def get_conversation_history(self, guild_id: int, user_id: int,
                                        channel_id: int, limit: int = 10) -> List[Dict]:
        rows = await db_fetch(
            """SELECT role, content FROM ai_conversations
               WHERE guild_id=? AND user_id=? AND channel_id=?
               ORDER BY created_at DESC LIMIT ?""",
            guild_id, user_id, channel_id, limit,
        )
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    async def save_message(self, guild_id: int, user_id: int, channel_id: int,
                           role: str, content: str):
        await db_execute(
            """INSERT INTO ai_conversations (guild_id, user_id, channel_id, role, content)
               VALUES (?, ?, ?, ?, ?)""",
            guild_id, user_id, channel_id, role, content,
        )
        # Trim old messages (keep last 50)
        await db_execute(
            """DELETE FROM ai_conversations WHERE id NOT IN (
               SELECT id FROM ai_conversations
               WHERE guild_id=? AND user_id=? AND channel_id=?
               ORDER BY created_at DESC LIMIT 50)
               AND guild_id=? AND user_id=? AND channel_id=?""",
            guild_id, user_id, channel_id, guild_id, user_id, channel_id,
        )

    async def chat(self, guild: discord.Guild, user: discord.Member,
                   channel: discord.TextChannel, message: str,
                   personality: str = "default") -> str:
        """Main AI chat function with memory and history."""
        guild_id = guild.id
        user_id  = user.id

        if self.is_on_cooldown(f"chat:{guild_id}:{user_id}", 3):
            return "Please wait a moment before sending another message."

        memory = await self.get_memory(guild_id, user_id)
        history = await self.get_conversation_history(guild_id, user_id, channel.id)

        system_prompt = self.personalities.get(personality, self.personalities["default"])
        system_prompt += f"\n\nServer: {guild.name} | Member count: {guild.member_count}"
        if memory:
            system_prompt += f"\n\nRelevant memory:\n{memory}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-8:])
        messages.append({"role": "user", "content": message})

        response = await self._call_ai(messages, max_tokens=512)

        await self.save_message(guild_id, user_id, channel.id, "user", message)
        await self.save_message(guild_id, user_id, channel.id, "assistant", response)
        return response

    async def moderate_message(self, content: str, guild_id: int) -> Dict:
        """AI moderation check on message content."""
        if not content.strip():
            return {"flagged": False, "reason": "", "action": "none", "confidence": 0}
        if self.is_on_cooldown(f"mod:{guild_id}", 0.5):
            return {"flagged": False, "reason": "", "action": "none", "confidence": 0}

        prompt = f"""Analyze this Discord message for violations. Return JSON only:
{{"flagged": bool, "reason": "brief reason or empty", "action": "none|warn|delete|timeout|ban", "confidence": 0-100, "categories": []}}

Categories to check: toxicity, harassment, hate_speech, spam, scam, phishing, nsfw, self_harm, violence

Message: {content[:500]}"""

        try:
            result = await self._call_ai(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150,
            )
            # Extract JSON
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            log.debug(f"AI moderation parse error: {e}")
        return {"flagged": False, "reason": "", "action": "none", "confidence": 0}

    async def generate_summary(self, messages: List[str], context: str = "") -> str:
        """Generate a summary of messages."""
        if not messages:
            return "No messages to summarize."
        joined = "\n".join(messages[:50])
        prompt = f"Summarize these Discord messages concisely in 2-3 sentences{f' (context: {context})' if context else ''}:\n\n{joined}"
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=200)

    async def generate_announcement(self, topic: str, tone: str = "official",
                                     guild_name: str = "") -> str:
        prompt = f"""Write a Discord server announcement for '{guild_name}' about: {topic}
Tone: {tone}. Format with clear sections. Include an engaging opening. Keep it under 300 words."""
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=400)

    async def generate_embed_content(self, purpose: str, details: str = "") -> Dict:
        prompt = f"""Create Discord embed content as JSON:
{{"title": "...", "description": "...", "color": "#hex", "fields": [{{"name": "...", "value": "..."}}]}}

Purpose: {purpose}
Details: {details}
Return valid JSON only."""
        result = await self._call_ai([{"role": "user", "content": prompt}], temperature=0.5, max_tokens=400)
        try:
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return {"title": purpose, "description": result, "color": "#5865F2", "fields": []}

    async def generate_rules(self, guild_name: str, server_type: str = "community") -> str:
        prompt = f"""Generate comprehensive Discord server rules for '{guild_name}' ({server_type} server).
Include 10-15 numbered rules covering: behavior, content, spam, bots, legal compliance.
Format each rule as: **Rule N: Title** - Description."""
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=800)

    async def analyze_server(self, guild: discord.Guild, stats: Dict) -> str:
        prompt = f"""Analyze this Discord server and provide 5 actionable improvement recommendations:

Server: {guild.name}
Members: {guild.member_count}
Channels: {stats.get('channels', 0)}
Roles: {stats.get('roles', 0)}
Bots: {stats.get('bots', 0)}
Boost level: {guild.premium_tier}
Recent activity: {stats.get('activity', 'unknown')}

Provide specific, actionable recommendations. Be concise."""
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=500)

    async def generate_ticket_summary(self, messages: List[str], subject: str = "") -> str:
        joined = "\n".join(messages[:30])
        prompt = f"Summarize this support ticket{f' about: {subject}' if subject else ''} in 3-4 bullet points covering: issue, steps taken, resolution status:\n\n{joined}"
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=250)

    async def translate(self, text: str, target_lang: str) -> str:
        prompt = f"Translate the following to {target_lang}. Return only the translation:\n\n{text}"
        return await self._call_ai([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=300)

    async def generate_faq(self, topic: str, context: str = "") -> str:
        prompt = f"Generate 5 FAQ entries for '{topic}'{f' ({context})' if context else ''} in Q&A format. Keep answers under 2 sentences each."
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=400)

    async def categorize_suggestion(self, suggestion: str) -> str:
        prompt = f"Categorize this Discord server suggestion into one of: feature, improvement, event, rule, content, other. Return only the category word.\n\nSuggestion: {suggestion}"
        result = await self._call_ai([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=20)
        valid = {"feature", "improvement", "event", "rule", "content", "other"}
        word = result.strip().lower().split()[0] if result.strip() else "other"
        return word if word in valid else "other"

    async def generate_report(self, report_type: str, data: Dict) -> str:
        data_str = json.dumps(data, indent=2)[:1000]
        prompt = f"Generate a professional {report_type} report for a Discord server based on this data:\n{data_str}\nFormat with sections, use bullet points for metrics."
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=600)


# ── Global AI instance ────────────────────────────────────────
ai = AISystem()


# ============================================================
# SECTION: Core Engine
# ============================================================

class RateLimiter:
    """Per-user/guild rate limiting."""
    def __init__(self):
        self._buckets: Dict[str, deque] = defaultdict(deque)

    def is_rate_limited(self, key: str, limit: int, window: float) -> bool:
        now = time.time()
        bucket = self._buckets[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        return False


rate_limiter = RateLimiter()


class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=self._get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            owner_id=OWNER_ID or None,
        )
        self.ai = ai
        self.rate_limiter = rate_limiter
        self.voice_clients_map: Dict[int, discord.VoiceClient] = {}
        self.music_queues: Dict[int, List] = defaultdict(list)
        self.music_current: Dict[int, Dict] = {}
        self.voice_sessions: Dict[str, int] = {}   # f"{guild}:{user}" -> join_timestamp
        self.raid_tracker: Dict[int, deque] = defaultdict(deque)  # guild_id -> join times
        self.sticky_cooldowns: Dict[int, float] = {}
        self.pending_confirmations: Dict[str, Dict] = {}

    async def _get_prefix(self, bot, message: discord.Message) -> List[str]:
        if not message.guild:
            return commands.when_mentioned_or(BOT_PREFIX)(bot, message)
        cfg = await get_guild_config(message.guild.id)
        prefix = cfg["prefix"] if cfg else BOT_PREFIX
        return commands.when_mentioned_or(prefix)(bot, message)

    async def setup_hook(self):
        await init_database()
        # Register all cogs
        for cog in [
            ModerationCog, AutoModCog, AntiRaidCog,
            TicketCog, ReactionRolesCog, WelcomeCog,
            LoggingCog, EconomyCog, LevelingCog, MusicCog,
            GiveawayCog, PollCog, SuggestionCog,
            UtilityCog, AIStaffCog, BackupCog, MessagingCog,
            AIServerBuilderCog, SchedulerCog, ConfigCog,
        ]:
            await self.add_cog(cog(self))
        log.info("All cogs loaded.")

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info(f"Connected to {len(self.guilds)} guild(s).")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | /help",
            )
        )
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            log.info(f"Synced {len(synced)} application commands.")
        except Exception as e:
            log.error(f"Failed to sync commands: {e}")
        # Start background tasks
        self.check_tasks.start()
        self.check_giveaways.start()
        self.check_polls.start()
        self.check_reminders.start()
        self.check_temp_bans.start()
        self.check_sticky.start()
        self.check_birthdays.start()
        log.info(f"Bot v{BOT_VERSION} is ready.")

    async def on_guild_join(self, guild: discord.Guild):
        await get_guild_config(guild.id)
        log.info(f"Joined guild: {guild.name} (ID: {guild.id})")

    async def on_guild_remove(self, guild: discord.Guild):
        log.info(f"Left guild: {guild.name} (ID: {guild.id})")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            await self._check_sticky(message)
            return
        if not message.guild:
            await self.process_commands(message)
            return

        guild_id = message.guild.id
        user_id  = message.author.id
        await ensure_user(user_id, guild_id, str(message.author))

        # Update message count
        await db_execute(
            "UPDATE users SET message_count=message_count+1, last_seen=? WHERE user_id=? AND guild_id=?",
            int(time.time()), user_id, guild_id,
        )

        # Automod check
        await self._run_automod(message)

        # XP for messages
        await self._grant_text_xp(message)

        # AI always-on mode / mentions
        cfg = await get_guild_config(guild_id)
        if cfg:
            always_on = cfg["ai_always_on"] and cfg["ai_channel"] == message.channel.id
            mentioned  = self.user in message.mentions
            if (always_on or mentioned) and cfg["ai_enabled"]:
                content = message.content.replace(f"<@{self.user.id}>", "").strip()
                if content:
                    async with message.channel.typing():
                        reply = await self.ai.chat(
                            message.guild, message.author,
                            message.channel, content,
                            cfg["ai_personality"] or "default",
                        )
                    await message.reply(reply[:2000])
                    return

        await self.process_commands(message)

    async def _check_sticky(self, message: discord.Message):
        if not message.guild:
            return
        row = await db_fetchone(
            "SELECT * FROM sticky_messages WHERE guild_id=? AND channel_id=? AND active=1",
            message.guild.id, message.channel.id,
        )
        if not row:
            return
        now = time.time()
        key = message.channel.id
        if now - self.sticky_cooldowns.get(key, 0) < 3:
            return
        self.sticky_cooldowns[key] = now
        try:
            if row["message_id"]:
                try:
                    old = await message.channel.fetch_message(row["message_id"])
                    await old.delete()
                except Exception:
                    pass
            sent = await message.channel.send(row["content"])
            await db_execute(
                "UPDATE sticky_messages SET message_id=? WHERE channel_id=? AND guild_id=?",
                sent.id, message.channel.id, message.guild.id,
            )
        except Exception as e:
            log.debug(f"Sticky message error: {e}")

    async def _run_automod(self, message: discord.Message):
        """Run all automod checks on a message."""
        guild_id = message.guild.id
        content  = message.content

        # Basic pattern checks (no AI needed)
        if await self._check_spam(message):
            return
        if await self._check_patterns(message):
            return

        # AI moderation (sampled to reduce API calls)
        if content and len(content) > 10 and random.random() < 0.15:
            result = await self.ai.moderate_message(content, guild_id)
            if result.get("flagged") and result.get("confidence", 0) >= 70:
                await self._apply_automod_action(
                    message, result.get("action", "warn"),
                    f"AI detected: {result.get('reason', 'policy violation')}",
                )

    async def _check_spam(self, message: discord.Message) -> bool:
        key = f"{message.guild.id}:{message.author.id}"
        if rate_limiter.is_rate_limited(key, limit=8, window=6.0):
            try:
                await message.delete()
                await message.author.timeout(datetime.timedelta(seconds=30), reason="Spam")
            except Exception:
                pass
            return True
        return False

    # Phishing / scam pattern detection
    PHISHING_PATTERNS = [
        r"discord\.gift[^\s]*", r"nitro.*free", r"free.*nitro",
        r"steam.*free", r"claim.*prize", r"you.*won",
        r"bit\.ly", r"tinyurl\.com", r"discord-gift\.",
    ]

    async def _check_patterns(self, message: discord.Message) -> bool:
        content_lower = message.content.lower()
        for pat in self.PHISHING_PATTERNS:
            if re.search(pat, content_lower):
                try:
                    await message.delete()
                    await message.author.timeout(datetime.timedelta(minutes=5),
                                                  reason="Suspected phishing/scam link")
                except Exception:
                    pass
                await self._log_event(message.guild.id, "automod_phishing",
                                       message.author.id, description=f"Pattern: {pat}")
                return True
        return False

    async def _apply_automod_action(self, message: discord.Message,
                                     action: str, reason: str):
        user = message.author
        guild_id = message.guild.id
        try:
            await message.delete()
        except Exception:
            pass
        try:
            if action == "warn":
                await self._warn_user_internal(guild_id, user.id, self.user.id, reason)
            elif action == "timeout":
                await user.timeout(datetime.timedelta(minutes=10), reason=reason)
            elif action == "kick":
                await user.kick(reason=reason)
            elif action == "ban":
                await user.ban(reason=reason, delete_message_days=1)
        except Exception as e:
            log.debug(f"Automod action error: {e}")
        await self._log_event(guild_id, "automod_action", user.id,
                               description=f"Action={action}: {reason}")

    async def _warn_user_internal(self, guild_id: int, user_id: int,
                                   mod_id: int, reason: str):
        await db_execute(
            "INSERT INTO warnings (guild_id, user_id, mod_id, reason) VALUES (?,?,?,?)",
            guild_id, user_id, mod_id, reason,
        )
        # Check warn threshold
        cfg = await get_guild_config(guild_id)
        count = await db_fetchone(
            "SELECT COUNT(*) as c FROM warnings WHERE guild_id=? AND user_id=? AND active=1",
            guild_id, user_id,
        )
        if cfg and count and count["c"] >= cfg["max_warnings"]:
            guild = self.get_guild(guild_id)
            if guild:
                member = guild.get_member(user_id)
                if member:
                    try:
                        await member.timeout(datetime.timedelta(hours=1),
                                             reason=f"Reached {count['c']} warnings")
                    except Exception:
                        pass

    async def _grant_text_xp(self, message: discord.Message):
        guild_id = message.guild.id
        user_id  = message.author.id
        cfg = await get_guild_config(guild_id)
        if not cfg or not cfg["level_enabled"]:
            return
        row = await db_fetchone(
            "SELECT * FROM levels WHERE user_id=? AND guild_id=?", user_id, guild_id
        )
        now = int(time.time())
        if row and row["last_message"] and now - row["last_message"] < 60:
            return  # XP cooldown
        xp_gain = random.randint(15, 25)
        if not row:
            await db_execute(
                "INSERT OR IGNORE INTO levels (user_id, guild_id, xp, last_message) VALUES (?,?,?,?)",
                user_id, guild_id, xp_gain, now,
            )
            return
        boost = row["xp_boost"] or 1.0
        if row["boost_expires"] and row["boost_expires"] < now:
            boost = 1.0
            await db_execute(
                "UPDATE levels SET xp_boost=1.0 WHERE user_id=? AND guild_id=?",
                user_id, guild_id,
            )
        new_xp = row["xp"] + int(xp_gain * boost)
        new_level = self._calc_level(new_xp)
        leveled_up = new_level > row["level"]
        await db_execute(
            "UPDATE levels SET xp=?, level=?, text_xp=text_xp+?, last_message=?, updated_at=? WHERE user_id=? AND guild_id=?",
            new_xp, new_level, xp_gain, now, now, user_id, guild_id,
        )
        if leveled_up:
            await self._handle_level_up(message, new_level)

    def _calc_level(self, xp: int) -> int:
        """Calculate level from XP using quadratic formula."""
        if xp <= 0:
            return 0
        return int((-1 + math.sqrt(1 + 8 * xp / 100)) / 2)

    def _xp_for_level(self, level: int) -> int:
        return int(level * (level + 1) / 2 * 100)

    async def _handle_level_up(self, message: discord.Message, new_level: int):
        guild_id = message.guild.id
        user_id  = message.author.id
        cfg = await get_guild_config(guild_id)
        # Announce
        level_ch_id = cfg["level_channel"] if cfg else None
        channel = (self.get_channel(level_ch_id) if level_ch_id else message.channel)
        if channel:
            embed = discord.Embed(
                title="⬆️ Level Up!",
                description=f"🎉 {message.author.mention} reached **Level {new_level}**!",
                color=discord.Color.gold(),
            )
            try:
                await channel.send(embed=embed, delete_after=30)
            except Exception:
                pass
        # Role rewards
        rewards = await db_fetch(
            "SELECT * FROM role_rewards WHERE guild_id=? AND level<=? ORDER BY level DESC",
            guild_id, new_level,
        )
        for reward in rewards:
            role = message.guild.get_role(reward["role_id"])
            if role and role not in message.author.roles:
                try:
                    await message.author.add_roles(role, reason=f"Level {reward['level']} reward")
                    if reward["remove_prev"]:
                        prev = await db_fetch(
                            "SELECT role_id FROM role_rewards WHERE guild_id=? AND level<? ORDER BY level DESC LIMIT 1",
                            guild_id, reward["level"],
                        )
                        if prev:
                            pr = message.guild.get_role(prev[0]["role_id"])
                            if pr and pr in message.author.roles:
                                await message.author.remove_roles(pr)
                except Exception:
                    pass

    async def _log_event(self, guild_id: int, event_type: str,
                          user_id: int = None, target_id: int = None,
                          channel_id: int = None, description: str = "",
                          extra: dict = None):
        await db_execute(
            """INSERT INTO logs (guild_id, event_type, user_id, target_id, channel_id, description, extra_data)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            guild_id, event_type, user_id, target_id, channel_id,
            description, json.dumps(extra or {}),
        )
        # Send to log channel
        cfg = await get_guild_config(guild_id)
        if not cfg:
            return
        ch_id = cfg["mod_log_channel"] if "mod" in event_type else cfg["log_channel"]
        if not ch_id:
            return
        channel = self.get_channel(ch_id)
        if not channel:
            return
        color_map = {
            "ban": discord.Color.red(), "kick": discord.Color.orange(),
            "warn": discord.Color.yellow(), "timeout": discord.Color.orange(),
            "unban": discord.Color.green(), "join": discord.Color.green(),
            "leave": discord.Color.greyple(), "delete": discord.Color.greyple(),
        }
        color = next((v for k, v in color_map.items() if k in event_type), discord.Color.blurple())
        embed = discord.Embed(
            title=f"📋 {event_type.replace('_', ' ').title()}",
            description=description or "No description",
            color=color,
            timestamp=datetime.datetime.utcnow(),
        )
        if user_id:
            embed.set_footer(text=f"User ID: {user_id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    # ── Background tasks ─────────────────────────────────────

    @tasks.loop(seconds=30)
    async def check_tasks(self):
        now = int(time.time())
        rows = await db_fetch(
            "SELECT * FROM scheduled_tasks WHERE active=1 AND run_at<=?", now
        )
        for task in rows:
            try:
                await self._run_scheduled_task(task)
            except Exception as e:
                log.error(f"Scheduled task error: {e}")
            if task["repeat"] and task["repeat_sec"]:
                await db_execute(
                    "UPDATE scheduled_tasks SET run_at=?, last_run=? WHERE id=?",
                    now + task["repeat_sec"], now, task["id"],
                )
            else:
                await db_execute(
                    "UPDATE scheduled_tasks SET active=0, last_run=? WHERE id=?",
                    now, task["id"],
                )

    async def _run_scheduled_task(self, task):
        data = json.loads(task["data"] or "{}")
        ch_id = task["channel_id"]
        if not ch_id:
            return
        channel = self.get_channel(ch_id)
        if not channel:
            return
        if task["task_type"] == "announcement":
            embed = discord.Embed(
                title=data.get("title", "Announcement"),
                description=data.get("content", ""),
                color=discord.Color.blurple(),
            )
            await channel.send(embed=embed)
        elif task["task_type"] == "message":
            await channel.send(data.get("content", ""))

    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        now = int(time.time())
        rows = await db_fetch(
            "SELECT * FROM giveaways WHERE status='active' AND ends_at<=?", now
        )
        for g in rows:
            await self._end_giveaway(g)

    async def _end_giveaway(self, g):
        entries = json.loads(g["entries"] or "[]")
        count = g["winners_count"]
        if not entries:
            winners = []
        else:
            winners = random.sample(entries, min(count, len(entries)))
        await db_execute(
            "UPDATE giveaways SET status='ended', winners=? WHERE giveaway_id=?",
            json.dumps(winners), g["giveaway_id"],
        )
        channel = self.get_channel(g["channel_id"])
        if not channel:
            return
        if winners:
            mentions = " ".join(f"<@{w}>" for w in winners)
            embed = discord.Embed(
                title=f"🎉 Giveaway Ended: {g['prize']}",
                description=f"Winners: {mentions}\nCongratulations!",
                color=discord.Color.gold(),
            )
        else:
            embed = discord.Embed(
                title=f"🎉 Giveaway Ended: {g['prize']}",
                description="No valid entries. No winners selected.",
                color=discord.Color.greyple(),
            )
        try:
            if g["message_id"]:
                msg = await channel.fetch_message(g["message_id"])
                await msg.edit(embed=embed, view=None)
            await channel.send(embed=embed)
        except Exception:
            pass

    @tasks.loop(minutes=1)
    async def check_polls(self):
        now = int(time.time())
        rows = await db_fetch(
            "SELECT * FROM polls WHERE status='active' AND ends_at IS NOT NULL AND ends_at<=?", now
        )
        for p in rows:
            await db_execute("UPDATE polls SET status='ended' WHERE poll_id=?", p["poll_id"])
            channel = self.get_channel(p["channel_id"])
            if channel:
                options = json.loads(p["options"])
                votes   = json.loads(p["votes"])
                results = "\n".join(
                    f"**{opt}**: {len(votes.get(str(i), []))} votes"
                    for i, opt in enumerate(options)
                )
                embed = discord.Embed(
                    title=f"📊 Poll Ended: {p['question']}",
                    description=results,
                    color=discord.Color.blurple(),
                )
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now = int(time.time())
        rows = await db_fetch(
            "SELECT * FROM reminders WHERE active=1 AND remind_at<=?", now
        )
        for r in rows:
            channel = self.get_channel(r["channel_id"])
            if channel:
                try:
                    await channel.send(
                        f"⏰ <@{r['user_id']}> Reminder: {r['message']}"
                    )
                except Exception:
                    pass
            if r["repeat"] and r["repeat_sec"]:
                await db_execute(
                    "UPDATE reminders SET remind_at=? WHERE id=?",
                    now + r["repeat_sec"], r["id"],
                )
            else:
                await db_execute("UPDATE reminders SET active=0 WHERE id=?", r["id"])

    @tasks.loop(minutes=5)
    async def check_temp_bans(self):
        now = int(time.time())
        rows = await db_fetch(
            "SELECT * FROM moderation_cases WHERE action='tempban' AND active=1 AND expires_at<=?",
            now,
        )
        for case in rows:
            guild = self.get_guild(case["guild_id"])
            if guild:
                try:
                    await guild.unban(
                        discord.Object(id=case["user_id"]),
                        reason="Temporary ban expired",
                    )
                    await db_execute(
                        "UPDATE moderation_cases SET active=0 WHERE id=?", case["id"]
                    )
                except Exception:
                    pass

    @tasks.loop(seconds=10)
    async def check_sticky(self):
        pass  # Handled in on_message

    @tasks.loop(hours=1)
    async def check_birthdays(self):
        now_utc = datetime.datetime.utcnow()
        today_m  = now_utc.month
        today_d  = now_utc.day
        rows = await db_fetch(
            "SELECT * FROM birthdays WHERE notified=0",
        )
        for b in rows:
            try:
                m, d = map(int, b["birthday"].split("-"))
                if m == today_m and d == today_d:
                    guild = self.get_guild(b["guild_id"])
                    if guild:
                        cfg = await get_guild_config(b["guild_id"])
                        ch = self.get_channel(cfg["welcome_channel"]) if cfg else None
                        if ch:
                            user = guild.get_member(b["user_id"])
                            if user:
                                await ch.send(f"🎂 Happy Birthday {user.mention}! 🥳")
                                await db_execute(
                                    "UPDATE birthdays SET notified=1 WHERE id=?", b["id"]
                                )
            except Exception:
                pass
        # Reset notified at start of new day
        if now_utc.hour == 0:
            await db_execute("UPDATE birthdays SET notified=0")

    @check_tasks.before_loop
    @check_giveaways.before_loop
    @check_polls.before_loop
    @check_reminders.before_loop
    @check_temp_bans.before_loop
    @check_sticky.before_loop
    @check_birthdays.before_loop
    async def before_tasks(self):
        await self.wait_until_ready()

    async def on_error(self, event: str, *args, **kwargs):
        log.error(f"Unhandled error in {event}: {traceback.format_exc()}")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.", delete_after=5)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I'm missing permissions to do that.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`", delete_after=10)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument: {error}", delete_after=10)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Cooldown. Try again in {error.retry_after:.1f}s.", delete_after=5)
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("❌ You don't meet the requirements for this command.", delete_after=5)
        else:
            log.error(f"Command error in {ctx.command}: {error}")
            await ctx.send("❌ An error occurred.", delete_after=5)


# ── Shared helpers ───────────────────────────────────────────

def build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(description=f"❌ {message}", color=discord.Color.red())


def build_success_embed(message: str) -> discord.Embed:
    return discord.Embed(description=f"✅ {message}", color=discord.Color.green())


def build_info_embed(title: str, description: str,
                      color: discord.Color = discord.Color.blurple()) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def parse_duration(s: str) -> Optional[int]:
    """Parse duration strings like '1d', '2h', '30m', '60s' into seconds."""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    match = re.fullmatch(r"(\d+)([smhdw])", s.lower().strip())
    if match:
        return int(match.group(1)) * units[match.group(2)]
    if s.isdigit():
        return int(s)
    return None


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


def perm_check(user: discord.Member, *perms: str) -> bool:
    """Check if user has ALL listed permissions."""
    user_perms = user.guild_permissions
    return all(getattr(user_perms, p, False) for p in perms)


# ============================================================
# SECTION: Moderation
# ============================================================

class ModerationCog(commands.Cog, name="Moderation"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    def _can_mod(self, ctx_or_interaction) -> bool:
        if isinstance(ctx_or_interaction, commands.Context):
            user = ctx_or_interaction.author
        else:
            user = ctx_or_interaction.user
        return perm_check(user, "moderate_members") or perm_check(user, "administrator")

    def _target_safe(self, actor: discord.Member, target: discord.Member) -> bool:
        if actor.guild.owner == target:
            return False
        if target.top_role >= actor.top_role and actor.guild.owner != actor:
            return False
        return True

    # ── /warn ────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for warning", severity="Severity 1-3")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member,
                   reason: str = "No reason provided", severity: int = 1):
        if not self._target_safe(interaction.user, member):
            await interaction.response.send_message(embed=build_error_embed("Cannot warn this user."), ephemeral=True)
            return
        severity = max(1, min(3, severity))
        await db_execute(
            "INSERT INTO warnings (guild_id, user_id, mod_id, reason, severity) VALUES (?,?,?,?,?)",
            interaction.guild_id, member.id, interaction.user.id, reason, severity,
        )
        count_row = await db_fetchone(
            "SELECT COUNT(*) as c FROM warnings WHERE guild_id=? AND user_id=? AND active=1",
            interaction.guild_id, member.id,
        )
        count = count_row["c"] if count_row else 1
        embed = discord.Embed(title="⚠️ Warning Issued", color=discord.Color.yellow())
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Mod", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Severity", value="⭐" * severity, inline=True)
        embed.add_field(name="Total Warnings", value=str(count), inline=True)
        await interaction.response.send_message(embed=embed)
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ You were warned in {interaction.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.yellow(),
            )
            dm_embed.add_field(name="Total Warnings", value=str(count))
            await member.send(embed=dm_embed)
        except Exception:
            pass
        await self.bot._log_event(interaction.guild_id, "mod_warn",
                                   interaction.user.id, member.id,
                                   description=f"Warned {member} | Reason: {reason}")
        # Case log
        case_id = generate_case_id(interaction.guild_id)
        await db_execute(
            "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason) VALUES (?,?,?,?,?,?)",
            case_id, interaction.guild_id, member.id, interaction.user.id, "warn", reason,
        )

    # ── /warnings ────────────────────────────────────────────
    @app_commands.command(name="warnings", description="View a user's warning history")
    @app_commands.default_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        rows = await db_fetch(
            "SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY created_at DESC LIMIT 20",
            interaction.guild_id, member.id,
        )
        embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=discord.Color.yellow())
        if not rows:
            embed.description = "No warnings found."
        else:
            for i, w in enumerate(rows, 1):
                mod = interaction.guild.get_member(w["mod_id"])
                ts = datetime.datetime.fromtimestamp(w["created_at"]).strftime("%Y-%m-%d")
                active = "✅" if w["active"] else "❌"
                embed.add_field(
                    name=f"#{i} — {active} {'⭐' * w['severity']} — {ts}",
                    value=f"**Reason:** {w['reason']}\n**By:** {mod.mention if mod else w['mod_id']}",
                    inline=False,
                )
        await interaction.response.send_message(embed=embed)

    # ── /clearwarnings ────────────────────────────────────────
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a user")
    @app_commands.default_permissions(administrator=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        await db_execute(
            "UPDATE warnings SET active=0 WHERE guild_id=? AND user_id=?",
            interaction.guild_id, member.id,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Cleared all warnings for {member.mention}")
        )

    # ── /kick ─────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member,
                   reason: str = "No reason provided"):
        if not self._target_safe(interaction.user, member):
            await interaction.response.send_message(embed=build_error_embed("Cannot kick this user."), ephemeral=True)
            return
        try:
            await member.send(f"You were kicked from **{interaction.guild.name}**.\n**Reason:** {reason}")
        except Exception:
            pass
        await member.kick(reason=reason)
        case_id = generate_case_id(interaction.guild_id)
        await db_execute(
            "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason) VALUES (?,?,?,?,?,?)",
            case_id, interaction.guild_id, member.id, interaction.user.id, "kick", reason,
        )
        await self.bot._log_event(interaction.guild_id, "mod_kick",
                                   interaction.user.id, member.id,
                                   description=f"Kicked {member} | Reason: {reason}")
        embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.orange())
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Case ID", value=case_id, inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /ban ──────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member,
                  reason: str = "No reason provided", delete_days: int = 1):
        if not self._target_safe(interaction.user, member):
            await interaction.response.send_message(embed=build_error_embed("Cannot ban this user."), ephemeral=True)
            return
        delete_days = max(0, min(7, delete_days))
        try:
            await member.send(f"You were banned from **{interaction.guild.name}**.\n**Reason:** {reason}")
        except Exception:
            pass
        await member.ban(reason=reason, delete_message_days=delete_days)
        case_id = generate_case_id(interaction.guild_id)
        await db_execute(
            "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason) VALUES (?,?,?,?,?,?)",
            case_id, interaction.guild_id, member.id, interaction.user.id, "ban", reason,
        )
        await self.bot._log_event(interaction.guild_id, "mod_ban",
                                   interaction.user.id, member.id,
                                   description=f"Banned {member} | Reason: {reason}")
        embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red())
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Case ID", value=case_id, inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /tempban ──────────────────────────────────────────────
    @app_commands.command(name="tempban", description="Temporarily ban a member")
    @app_commands.default_permissions(ban_members=True)
    async def tempban(self, interaction: discord.Interaction, member: discord.Member,
                      duration: str = "1d", reason: str = "No reason provided"):
        secs = parse_duration(duration)
        if not secs:
            await interaction.response.send_message(embed=build_error_embed("Invalid duration. Use: 1d, 2h, 30m"), ephemeral=True)
            return
        if not self._target_safe(interaction.user, member):
            await interaction.response.send_message(embed=build_error_embed("Cannot ban this user."), ephemeral=True)
            return
        expires = int(time.time()) + secs
        try:
            await member.send(f"You were temporarily banned from **{interaction.guild.name}** for {format_duration(secs)}.\n**Reason:** {reason}")
        except Exception:
            pass
        await member.ban(reason=reason, delete_message_days=0)
        case_id = generate_case_id(interaction.guild_id)
        await db_execute(
            "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason, duration, expires_at) VALUES (?,?,?,?,?,?,?,?)",
            case_id, interaction.guild_id, member.id, interaction.user.id,
            "tempban", reason, secs, expires,
        )
        embed = discord.Embed(title="⏱️ Temporary Ban", color=discord.Color.red())
        embed.add_field(name="User", value=str(member), inline=True)
        embed.add_field(name="Duration", value=format_duration(secs), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Expires", value=f"<t:{expires}:R>", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /softban ──────────────────────────────────────────────
    @app_commands.command(name="softban", description="Softban (ban+unban) to delete messages")
    @app_commands.default_permissions(ban_members=True)
    async def softban(self, interaction: discord.Interaction, member: discord.Member,
                      reason: str = "No reason provided"):
        if not self._target_safe(interaction.user, member):
            await interaction.response.send_message(embed=build_error_embed("Cannot softban this user."), ephemeral=True)
            return
        await interaction.response.defer()
        await member.ban(reason=f"Softban: {reason}", delete_message_days=7)
        await asyncio.sleep(1)
        await interaction.guild.unban(discord.Object(id=member.id), reason="Softban completed")
        embed = discord.Embed(title="🧹 Softban Applied",
                               description=f"{member.mention}'s recent messages were deleted and they were removed.",
                               color=discord.Color.orange())
        embed.add_field(name="Reason", value=reason)
        await interaction.followup.send(embed=embed)

    # ── /unban ────────────────────────────────────────────────
    @app_commands.command(name="unban", description="Unban a user by ID")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str,
                    reason: str = "No reason provided"):
        try:
            uid = int(user_id)
            await interaction.guild.unban(discord.Object(id=uid), reason=reason)
            await db_execute(
                "UPDATE moderation_cases SET active=0 WHERE guild_id=? AND user_id=? AND action IN ('ban','tempban')",
                interaction.guild_id, uid,
            )
            await self.bot._log_event(interaction.guild_id, "mod_unban",
                                       interaction.user.id, uid,
                                       description=f"Unbanned {uid} | Reason: {reason}")
            await interaction.response.send_message(
                embed=build_success_embed(f"Unbanned user `{uid}`. Reason: {reason}")
            )
        except Exception as e:
            await interaction.response.send_message(embed=build_error_embed(f"Failed: {e}"), ephemeral=True)

    # ── /timeout ──────────────────────────────────────────────
    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.default_permissions(moderate_members=True)
    async def timeout_user(self, interaction: discord.Interaction, member: discord.Member,
                            duration: str = "10m", reason: str = "No reason provided"):
        secs = parse_duration(duration)
        if not secs:
            await interaction.response.send_message(embed=build_error_embed("Invalid duration."), ephemeral=True)
            return
        if not self._target_safe(interaction.user, member):
            await interaction.response.send_message(embed=build_error_embed("Cannot timeout this user."), ephemeral=True)
            return
        delta = datetime.timedelta(seconds=min(secs, 2419200))  # Max 28 days
        await member.timeout(delta, reason=reason)
        case_id = generate_case_id(interaction.guild_id)
        await db_execute(
            "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason, duration) VALUES (?,?,?,?,?,?,?)",
            case_id, interaction.guild_id, member.id, interaction.user.id, "timeout", reason, secs,
        )
        embed = discord.Embed(title="⏸️ Member Timed Out", color=discord.Color.orange())
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Duration", value=format_duration(secs), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /untimeout ────────────────────────────────────────────
    @app_commands.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.default_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member,
                         reason: str = "No reason provided"):
        await member.timeout(None, reason=reason)
        await interaction.response.send_message(
            embed=build_success_embed(f"Removed timeout from {member.mention}.")
        )

    # ── /mute (role-based) ────────────────────────────────────
    @app_commands.command(name="mute", description="Mute a member using the mute role")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member,
                   reason: str = "No reason provided"):
        cfg = await get_guild_config(interaction.guild_id)
        mute_role_id = cfg["mute_role"] if cfg else None
        if not mute_role_id:
            await interaction.response.send_message(
                embed=build_error_embed("No mute role configured. Use `/config mute_role`."), ephemeral=True
            )
            return
        role = interaction.guild.get_role(mute_role_id)
        if not role:
            await interaction.response.send_message(embed=build_error_embed("Mute role not found."), ephemeral=True)
            return
        await member.add_roles(role, reason=reason)
        await interaction.response.send_message(
            embed=build_success_embed(f"Muted {member.mention}. Reason: {reason}")
        )

    # ── /unmute ───────────────────────────────────────────────
    @app_commands.command(name="unmute", description="Unmute a member")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        cfg = await get_guild_config(interaction.guild_id)
        mute_role_id = cfg["mute_role"] if cfg else None
        if not mute_role_id:
            await interaction.response.send_message(embed=build_error_embed("No mute role configured."), ephemeral=True)
            return
        role = interaction.guild.get_role(mute_role_id)
        if role and role in member.roles:
            await member.remove_roles(role, reason="Unmuted")
        await interaction.response.send_message(embed=build_success_embed(f"Unmuted {member.mention}."))

    # ── /jail ─────────────────────────────────────────────────
    @app_commands.command(name="jail", description="Jail a member (restrict to jail channel)")
    @app_commands.default_permissions(moderate_members=True)
    async def jail(self, interaction: discord.Interaction, member: discord.Member,
                   reason: str = "No reason provided"):
        cfg = await get_guild_config(interaction.guild_id)
        jail_role_id = cfg["jail_role"] if cfg else None
        if not jail_role_id:
            await interaction.response.send_message(
                embed=build_error_embed("No jail role configured. Use `/config jail_role`."), ephemeral=True
            )
            return
        role = interaction.guild.get_role(jail_role_id)
        if not role:
            await interaction.response.send_message(embed=build_error_embed("Jail role not found."), ephemeral=True)
            return
        await member.add_roles(role, reason=reason)
        embed = discord.Embed(
            title="🔒 Member Jailed",
            description=f"{member.mention} has been jailed.\n**Reason:** {reason}",
            color=discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed)

    # ── /unjail ───────────────────────────────────────────────
    @app_commands.command(name="unjail", description="Release a member from jail")
    @app_commands.default_permissions(moderate_members=True)
    async def unjail(self, interaction: discord.Interaction, member: discord.Member):
        cfg = await get_guild_config(interaction.guild_id)
        jail_role_id = cfg["jail_role"] if cfg else None
        if not jail_role_id:
            await interaction.response.send_message(embed=build_error_embed("No jail role configured."), ephemeral=True)
            return
        role = interaction.guild.get_role(jail_role_id)
        if role and role in member.roles:
            await member.remove_roles(role, reason="Released from jail")
        await interaction.response.send_message(embed=build_success_embed(f"Released {member.mention} from jail."))

    # ── /purge ────────────────────────────────────────────────
    @app_commands.command(name="purge", description="Delete messages in bulk")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int,
                    member: discord.Member = None):
        if amount < 1 or amount > 200:
            await interaction.response.send_message(embed=build_error_embed("Amount must be 1-200."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        def check(m):
            return (not member or m.author == member)
        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(
            embed=build_success_embed(f"Deleted {len(deleted)} messages."), ephemeral=True
        )
        await self.bot._log_event(interaction.guild_id, "mod_purge",
                                   interaction.user.id, channel_id=interaction.channel_id,
                                   description=f"Purged {len(deleted)} messages")

    # ── /lock & /unlock ───────────────────────────────────────
    @app_commands.command(name="lock", description="Lock a channel")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction,
                   channel: discord.TextChannel = None, reason: str = "No reason provided"):
        ch = channel or interaction.channel
        await ch.set_permissions(interaction.guild.default_role,
                                  send_messages=False, reason=reason)
        embed = discord.Embed(title="🔒 Channel Locked",
                               description=f"{ch.mention} has been locked.\n**Reason:** {reason}",
                               color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unlock", description="Unlock a channel")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction,
                     channel: discord.TextChannel = None, reason: str = "Unlocked"):
        ch = channel or interaction.channel
        await ch.set_permissions(interaction.guild.default_role,
                                  send_messages=None, reason=reason)
        embed = discord.Embed(title="🔓 Channel Unlocked",
                               description=f"{ch.mention} has been unlocked.",
                               color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    # ── /slowmode ─────────────────────────────────────────────
    @app_commands.command(name="slowmode", description="Set channel slowmode")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int = 0,
                        channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        seconds = max(0, min(21600, seconds))
        await ch.edit(slowmode_delay=seconds)
        msg = f"Slowmode disabled in {ch.mention}." if seconds == 0 else f"Slowmode set to {seconds}s in {ch.mention}."
        await interaction.response.send_message(embed=build_success_embed(msg))

    # ── /nick ─────────────────────────────────────────────────
    @app_commands.command(name="nick", description="Change or reset a member's nickname")
    @app_commands.default_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, member: discord.Member,
                   nickname: str = None):
        old = member.nick or member.name
        await member.edit(nick=nickname)
        if nickname:
            await interaction.response.send_message(
                embed=build_success_embed(f"Changed {member.mention}'s nickname from `{old}` to `{nickname}`.")
            )
        else:
            await interaction.response.send_message(
                embed=build_success_embed(f"Reset {member.mention}'s nickname.")
            )

    # ── /case ─────────────────────────────────────────────────
    @app_commands.command(name="case", description="View a moderation case")
    @app_commands.default_permissions(moderate_members=True)
    async def case(self, interaction: discord.Interaction, case_id: str):
        row = await db_fetchone(
            "SELECT * FROM moderation_cases WHERE case_id=? AND guild_id=?",
            case_id, interaction.guild_id,
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("Case not found."), ephemeral=True)
            return
        mod = interaction.guild.get_member(row["mod_id"])
        user = interaction.guild.get_member(row["user_id"])
        embed = discord.Embed(title=f"📋 Case {case_id}", color=discord.Color.blurple())
        embed.add_field(name="User", value=str(user or row["user_id"]), inline=True)
        embed.add_field(name="Moderator", value=str(mod or row["mod_id"]), inline=True)
        embed.add_field(name="Action", value=row["action"].title(), inline=True)
        embed.add_field(name="Reason", value=row["reason"] or "None", inline=False)
        if row["duration"]:
            embed.add_field(name="Duration", value=format_duration(row["duration"]), inline=True)
        embed.add_field(name="Active", value="Yes" if row["active"] else "No", inline=True)
        ts = datetime.datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d %H:%M UTC")
        embed.set_footer(text=f"Created: {ts}")
        await interaction.response.send_message(embed=embed)

    # ── /modhistory ────────────────────────────────────────────
    @app_commands.command(name="modhistory", description="View moderation history of a user")
    @app_commands.default_permissions(moderate_members=True)
    async def modhistory(self, interaction: discord.Interaction, member: discord.Member):
        rows = await db_fetch(
            "SELECT * FROM moderation_cases WHERE guild_id=? AND user_id=? ORDER BY created_at DESC LIMIT 10",
            interaction.guild_id, member.id,
        )
        embed = discord.Embed(title=f"📋 Mod History: {member}", color=discord.Color.blurple())
        if not rows:
            embed.description = "No moderation history found."
        else:
            for r in rows:
                mod = interaction.guild.get_member(r["mod_id"])
                ts  = datetime.datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d")
                embed.add_field(
                    name=f"[{r['case_id']}] {r['action'].upper()} — {ts}",
                    value=f"**By:** {str(mod or r['mod_id'])}\n**Reason:** {r['reason'] or 'None'}",
                    inline=False,
                )
        await interaction.response.send_message(embed=embed)

    # ── /appeal ───────────────────────────────────────────────
    @app_commands.command(name="appeal", description="Appeal a moderation action")
    async def appeal(self, interaction: discord.Interaction, case_id: str, reason: str):
        row = await db_fetchone(
            "SELECT * FROM moderation_cases WHERE case_id=? AND user_id=? AND guild_id=?",
            case_id, interaction.user.id, interaction.guild_id,
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("Case not found or doesn't belong to you."), ephemeral=True)
            return
        await db_execute(
            "INSERT INTO appeals (guild_id, case_id, user_id, reason) VALUES (?,?,?,?)",
            interaction.guild_id, case_id, interaction.user.id, reason,
        )
        embed = discord.Embed(title="📝 Appeal Submitted",
                               description=f"Your appeal for case `{case_id}` has been submitted for review.",
                               color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Voice moderation ──────────────────────────────────────
    @app_commands.command(name="vcmove", description="Move a member to a voice channel")
    @app_commands.default_permissions(move_members=True)
    async def vcmove(self, interaction: discord.Interaction, member: discord.Member,
                     channel: discord.VoiceChannel):
        if not member.voice:
            await interaction.response.send_message(embed=build_error_embed("Member is not in a voice channel."), ephemeral=True)
            return
        await member.move_to(channel)
        await interaction.response.send_message(
            embed=build_success_embed(f"Moved {member.mention} to {channel.mention}.")
        )

    @app_commands.command(name="vckick", description="Kick a member from voice channel")
    @app_commands.default_permissions(move_members=True)
    async def vckick(self, interaction: discord.Interaction, member: discord.Member):
        if not member.voice:
            await interaction.response.send_message(embed=build_error_embed("Member is not in a voice channel."), ephemeral=True)
            return
        await member.move_to(None)
        await interaction.response.send_message(
            embed=build_success_embed(f"Kicked {member.mention} from voice channel.")
        )

    # ── Mass moderation ───────────────────────────────────────
    @app_commands.command(name="massban", description="Ban multiple users by ID (space-separated)")
    @app_commands.default_permissions(administrator=True)
    async def massban(self, interaction: discord.Interaction, user_ids: str,
                      reason: str = "Mass ban"):
        await interaction.response.defer()
        ids = user_ids.split()
        banned, failed = [], []
        for uid_str in ids[:50]:
            try:
                uid = int(uid_str)
                await interaction.guild.ban(discord.Object(id=uid), reason=reason, delete_message_days=1)
                banned.append(uid)
            except Exception:
                failed.append(uid_str)
        embed = discord.Embed(title="🔨 Mass Ban Complete", color=discord.Color.red())
        embed.add_field(name="Banned", value=str(len(banned)), inline=True)
        embed.add_field(name="Failed", value=str(len(failed)), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed)


# ============================================================
# SECTION: AI Automod
# ============================================================

class AutoModCog(commands.Cog, name="AutoMod"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="automod", description="Configure AI AutoMod rules")
    @app_commands.default_permissions(administrator=True)
    async def automod_config(self, interaction: discord.Interaction,
                              rule_type: str = "spam", enabled: bool = True,
                              action: str = "warn", threshold: int = 5):
        valid_rules = {"spam", "toxicity", "phishing", "invite", "mention", "caps", "emoji", "zalgo"}
        if rule_type not in valid_rules:
            await interaction.response.send_message(
                embed=build_error_embed(f"Invalid rule type. Choose: {', '.join(valid_rules)}"),
                ephemeral=True,
            )
            return
        await db_execute(
            """INSERT INTO automod_rules (guild_id, rule_type, enabled, action, threshold)
               VALUES (?,?,?,?,?)
               ON CONFLICT DO UPDATE SET enabled=excluded.enabled, action=excluded.action, threshold=excluded.threshold""",
            interaction.guild_id, rule_type, int(enabled), action, threshold,
        )
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            embed=build_success_embed(f"AutoMod rule `{rule_type}` {status}. Action: `{action}`, Threshold: `{threshold}`")
        )

    @app_commands.command(name="automodlist", description="List all AutoMod rules")
    @app_commands.default_permissions(manage_guild=True)
    async def automod_list(self, interaction: discord.Interaction):
        rows = await db_fetch(
            "SELECT * FROM automod_rules WHERE guild_id=?", interaction.guild_id
        )
        embed = discord.Embed(title="🛡️ AutoMod Rules", color=discord.Color.blurple())
        if not rows:
            embed.description = "No AutoMod rules configured."
        else:
            for r in rows:
                status = "✅" if r["enabled"] else "❌"
                embed.add_field(
                    name=f"{status} {r['rule_type'].title()}",
                    value=f"Action: `{r['action']}` | Threshold: `{r['threshold']}`",
                    inline=True,
                )
        await interaction.response.send_message(embed=embed)


# ============================================================
# SECTION: Anti-Raid Security
# ============================================================

class AntiRaidCog(commands.Cog, name="AntiRaid"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = member.guild.id
        cfg = await db_fetchone("SELECT * FROM anti_raid WHERE guild_id=?", guild_id)
        if not cfg or not cfg["enabled"]:
            return

        # Lockdown check
        if cfg["lockdown_active"]:
            if not member.bot:
                try:
                    await member.kick(reason="Server is in lockdown mode")
                except Exception:
                    pass
            return

        # Verification mode
        if cfg["verification_mode"]:
            role = member.guild.get_role(await self._get_unverified_role(guild_id))
            if role:
                try:
                    await member.add_roles(role)
                except Exception:
                    pass

        # Bot raid protection
        if cfg["bot_protection"] and member.bot:
            try:
                await member.kick(reason="Bot raid protection — bots require manual approval")
            except Exception:
                pass
            await self.bot._log_event(guild_id, "antiraid_bot_kicked",
                                       member.id, description="Bot kicked by anti-raid")
            return

        # Join flood detection
        tracker = self.bot.raid_tracker[guild_id]
        now = time.time()
        tracker.append(now)
        while tracker and now - tracker[0] > cfg["join_window"]:
            tracker.popleft()

        if len(tracker) >= cfg["join_threshold"]:
            await self._activate_lockdown(member.guild, f"Raid detected: {len(tracker)} joins in {cfg['join_window']}s")

    async def _get_unverified_role(self, guild_id: int) -> Optional[int]:
        row = await db_fetchone("SELECT admin_role FROM guild_config WHERE guild_id=?", guild_id)
        return None

    async def _activate_lockdown(self, guild: discord.Guild, reason: str):
        guild_id = guild.id
        await db_execute(
            "UPDATE anti_raid SET lockdown_active=1, lockdown_reason=?, lockdown_at=? WHERE guild_id=?",
            reason, int(time.time()), guild_id,
        )
        cfg = await get_guild_config(guild_id)
        if cfg and cfg["log_channel"]:
            ch = self.bot.get_channel(cfg["log_channel"])
            if ch:
                embed = discord.Embed(
                    title="🚨 EMERGENCY LOCKDOWN ACTIVATED",
                    description=f"**Reason:** {reason}\n\nNew joins are being blocked.",
                    color=discord.Color.red(),
                )
                await ch.send(embed=embed)
        log.warning(f"Lockdown activated in {guild.name}: {reason}")

    @app_commands.command(name="lockdown", description="Toggle server lockdown mode")
    @app_commands.default_permissions(administrator=True)
    async def lockdown(self, interaction: discord.Interaction,
                        reason: str = "Manual lockdown", enable: bool = True):
        await db_execute(
            """INSERT INTO anti_raid (guild_id, enabled, lockdown_active, lockdown_reason, lockdown_at)
               VALUES (?,1,?,?,?)
               ON CONFLICT(guild_id) DO UPDATE SET lockdown_active=excluded.lockdown_active,
               lockdown_reason=excluded.lockdown_reason, lockdown_at=excluded.lockdown_at""",
            interaction.guild_id, int(enable), reason, int(time.time()),
        )
        if enable:
            embed = discord.Embed(
                title="🔒 Lockdown Activated",
                description=f"**Reason:** {reason}\n\nNo new members will be allowed in.",
                color=discord.Color.red(),
            )
        else:
            embed = discord.Embed(
                title="🔓 Lockdown Lifted",
                description="Server lockdown has been deactivated.",
                color=discord.Color.green(),
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="antiraid", description="Configure anti-raid settings")
    @app_commands.default_permissions(administrator=True)
    async def antiraid_config(self, interaction: discord.Interaction,
                               enabled: bool = True, join_threshold: int = 10,
                               join_window: int = 10, action: str = "kick",
                               bot_protection: bool = True):
        await db_execute(
            """INSERT INTO anti_raid (guild_id, enabled, join_threshold, join_window, action, bot_protection)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(guild_id) DO UPDATE SET
               enabled=excluded.enabled, join_threshold=excluded.join_threshold,
               join_window=excluded.join_window, action=excluded.action,
               bot_protection=excluded.bot_protection, updated_at=strftime('%s','now')""",
            interaction.guild_id, int(enabled), join_threshold, join_window, action, int(bot_protection),
        )
        embed = discord.Embed(title="🛡️ Anti-Raid Configuration Updated", color=discord.Color.green())
        embed.add_field(name="Status", value="Enabled" if enabled else "Disabled", inline=True)
        embed.add_field(name="Join Threshold", value=f"{join_threshold} joins", inline=True)
        embed.add_field(name="Time Window", value=f"{join_window} seconds", inline=True)
        embed.add_field(name="Action", value=action.title(), inline=True)
        embed.add_field(name="Bot Protection", value="Yes" if bot_protection else "No", inline=True)
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        cfg = await db_fetchone("SELECT * FROM anti_raid WHERE guild_id=? AND enabled=1", channel.guild.id)
        if not cfg:
            return
        audit = [entry async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1)]
        if audit and audit[0].user != self.bot.user:
            await self.bot._log_event(
                channel.guild.id, "antiraid_channel_deleted",
                audit[0].user.id, channel_id=channel.id,
                description=f"Channel #{channel.name} deleted",
            )

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        cfg = await db_fetchone("SELECT * FROM anti_raid WHERE guild_id=? AND webhook_protection=1", channel.guild.id)
        if not cfg:
            return
        webhooks = await channel.webhooks()
        now = time.time()
        for wh in webhooks:
            if wh.created_at and (now - wh.created_at.timestamp()) < 30:
                try:
                    await wh.delete(reason="Anti-raid webhook protection")
                    await self.bot._log_event(
                        channel.guild.id, "antiraid_webhook_removed",
                        description=f"Suspicious webhook '{wh.name}' removed from #{channel.name}",
                    )
                except Exception:
                    pass


# ============================================================
# SECTION: Enterprise Ticket System
# ============================================================

class TicketCog(commands.Cog, name="Tickets"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="ticket-panel", description="Create a ticket panel in a channel")
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_panel(self, interaction: discord.Interaction,
                            channel: discord.TextChannel,
                            title: str = "Support Tickets",
                            description: str = "Click a button below to open a ticket."):
        await interaction.response.defer(ephemeral=True)
        departments = ["General Support", "Billing", "Technical", "Reports", "Other"]
        view = discord.ui.View(timeout=None)
        for dept in departments:
            btn = discord.ui.Button(label=dept, style=discord.ButtonStyle.primary,
                                     custom_id=f"ticket_open:{dept.lower().replace(' ', '_')}")
            view.add_item(btn)
        embed = discord.Embed(title=f"🎫 {title}", description=description,
                               color=discord.Color.blurple())
        embed.set_footer(text="Select a department to open a ticket.")
        msg = await channel.send(embed=embed, view=view)
        panel_id = await db_execute(
            "INSERT INTO ticket_panels (guild_id, channel_id, message_id, name, description) VALUES (?,?,?,?,?)",
            interaction.guild_id, channel.id, msg.id, title, description,
        )
        await interaction.followup.send(embed=build_success_embed(f"Ticket panel created in {channel.mention}."), ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or not interaction.guild:
            return
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("ticket_open:"):
            dept = custom_id.split(":")[1].replace("_", " ").title()
            await self._open_ticket(interaction, dept)
        elif custom_id == "ticket_close":
            await self._close_ticket(interaction)
        elif custom_id == "ticket_claim":
            await self._claim_ticket(interaction)
        elif custom_id.startswith("ticket_priority:"):
            priority = custom_id.split(":")[1]
            await self._set_priority(interaction, priority)

    async def _open_ticket(self, interaction: discord.Interaction, department: str):
        guild_id = interaction.guild_id
        user     = interaction.user

        # Check for existing open ticket
        existing = await db_fetchone(
            "SELECT * FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
            guild_id, user.id,
        )
        if existing:
            ch = self.bot.get_channel(existing["channel_id"])
            msg = f"You already have an open ticket: {ch.mention}." if ch else "You already have an open ticket."
            await interaction.response.send_message(embed=build_error_embed(msg), ephemeral=True)
            return

        await interaction.response.send_modal(TicketOpenModal(self.bot, department))

    async def create_ticket_channel(self, guild: discord.Guild, user: discord.Member,
                                     department: str, subject: str) -> Optional[discord.TextChannel]:
        cfg = await get_guild_config(guild.id)
        ticket_id = generate_ticket_id(guild.id)

        # Find or create category
        category_id = cfg["ticket_category"] if cfg else None
        category = guild.get_channel(category_id) if category_id else None
        if not category:
            category = await guild.create_category("Tickets", reason="Ticket system setup")
            if cfg:
                await db_execute(
                    "UPDATE guild_config SET ticket_category=? WHERE guild_id=?",
                    category.id, guild.id,
                )

        # Support roles
        support_ids = json.loads(cfg["ticket_support"]) if cfg and cfg["ticket_support"] else []
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, attach_files=True, embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for rid in support_ids:
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_messages=True
                )

        channel_name = f"ticket-{ticket_id.lower()}"
        try:
            channel = await category.create_text_channel(
                name=channel_name, overwrites=overwrites, reason=f"Ticket: {subject}"
            )
        except Exception as e:
            log.error(f"Failed to create ticket channel: {e}")
            return None

        sla = int(time.time()) + 86400  # 24h SLA
        await db_execute(
            """INSERT INTO tickets (ticket_id, guild_id, channel_id, user_id, department, subject, sla_deadline)
               VALUES (?,?,?,?,?,?,?)""",
            ticket_id, guild.id, channel.id, user.id, department, subject, sla,
        )

        # Build ticket embed
        embed = discord.Embed(
            title=f"🎫 Ticket {ticket_id}",
            description=f"**Department:** {department}\n**Subject:** {subject}\n\nSupport staff will assist you shortly.",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Priority", value="🟡 Normal", inline=True)
        embed.add_field(name="SLA", value=f"<t:{sla}:R>", inline=True)

        view = discord.ui.View(timeout=None)
        close_btn  = discord.ui.Button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close")
        claim_btn  = discord.ui.Button(label="Claim",        style=discord.ButtonStyle.success, emoji="👋", custom_id="ticket_claim")
        view.add_item(close_btn)
        view.add_item(claim_btn)

        await channel.send(embed=embed, view=view)
        await channel.send(f"{user.mention} Welcome! Please describe your issue.")

        await self.bot._log_event(guild.id, "ticket_opened", user.id,
                                   channel_id=channel.id,
                                   description=f"Ticket {ticket_id} opened | Dept: {department}")
        return channel

    async def _close_ticket(self, interaction: discord.Interaction):
        row = await db_fetchone(
            "SELECT * FROM tickets WHERE channel_id=? AND status='open'",
            interaction.channel_id,
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("This is not an open ticket."), ephemeral=True)
            return
        user = interaction.guild.get_member(row["user_id"])
        await interaction.response.send_modal(TicketCloseModal(self.bot, row, user))

    async def _claim_ticket(self, interaction: discord.Interaction):
        row = await db_fetchone(
            "SELECT * FROM tickets WHERE channel_id=? AND status='open'",
            interaction.channel_id,
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("This is not an open ticket."), ephemeral=True)
            return
        if row["claimed_by"]:
            claimer = interaction.guild.get_member(row["claimed_by"])
            await interaction.response.send_message(
                embed=build_error_embed(f"Ticket already claimed by {claimer.mention if claimer else 'staff'}."),
                ephemeral=True,
            )
            return
        await db_execute(
            "UPDATE tickets SET claimed_by=?, first_response=COALESCE(first_response,?) WHERE ticket_id=?",
            interaction.user.id, int(time.time()), row["ticket_id"],
        )
        embed = discord.Embed(
            title="👋 Ticket Claimed",
            description=f"{interaction.user.mention} is now handling this ticket.",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)
        # Update stats
        await db_execute(
            """INSERT INTO ticket_stats (guild_id, user_id, tickets_claimed) VALUES (?,?,1)
               ON CONFLICT(guild_id,user_id) DO UPDATE SET tickets_claimed=tickets_claimed+1""",
            interaction.guild_id, interaction.user.id,
        )

    async def _set_priority(self, interaction: discord.Interaction, priority: str):
        await db_execute(
            "UPDATE tickets SET priority=? WHERE channel_id=?",
            priority, interaction.channel_id,
        )
        icons = {"low": "🟢", "normal": "🟡", "high": "🟠", "urgent": "🔴"}
        icon = icons.get(priority, "🟡")
        await interaction.response.send_message(
            embed=build_success_embed(f"Priority set to {icon} {priority.title()}.")
        )

    @app_commands.command(name="ticket-close", description="Close the current ticket")
    async def ticket_close_cmd(self, interaction: discord.Interaction):
        await self._close_ticket(interaction)

    @app_commands.command(name="ticket-add", description="Add a user to the current ticket")
    @app_commands.default_permissions(moderate_members=True)
    async def ticket_add(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.channel.set_permissions(member,
            view_channel=True, send_messages=True, read_message_history=True,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Added {member.mention} to the ticket.")
        )

    @app_commands.command(name="ticket-remove", description="Remove a user from the current ticket")
    @app_commands.default_permissions(moderate_members=True)
    async def ticket_remove(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(
            embed=build_success_embed(f"Removed {member.mention} from the ticket.")
        )

    @app_commands.command(name="ticket-rename", description="Rename the current ticket channel")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_rename(self, interaction: discord.Interaction, name: str):
        await interaction.channel.edit(name=name)
        await interaction.response.send_message(embed=build_success_embed(f"Ticket renamed to `{name}`."))

    @app_commands.command(name="ticket-note", description="Add an internal note to the ticket")
    @app_commands.default_permissions(moderate_members=True)
    async def ticket_note(self, interaction: discord.Interaction, note: str):
        row = await db_fetchone(
            "SELECT * FROM tickets WHERE channel_id=?", interaction.channel_id
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("Not a ticket channel."), ephemeral=True)
            return
        notes = json.loads(row["internal_notes"] or "[]")
        notes.append({
            "author": str(interaction.user),
            "note": note,
            "at": int(time.time()),
        })
        await db_execute(
            "UPDATE tickets SET internal_notes=? WHERE channel_id=?",
            json.dumps(notes), interaction.channel_id,
        )
        embed = discord.Embed(
            title="📝 Internal Note Added",
            description=note,
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"Note by {interaction.user} — Staff only")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ticket-summary", description="AI-generated ticket summary")
    @app_commands.default_permissions(moderate_members=True)
    async def ticket_summary(self, interaction: discord.Interaction):
        row = await db_fetchone(
            "SELECT * FROM tickets WHERE channel_id=?", interaction.channel_id
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("Not a ticket channel."), ephemeral=True)
            return
        await interaction.response.defer()
        msgs = await db_fetch(
            "SELECT content FROM ticket_messages WHERE ticket_id=? ORDER BY created_at LIMIT 30",
            row["ticket_id"],
        )
        msg_texts = [m["content"] for m in msgs if m["content"]]
        summary = await self.bot.ai.generate_ticket_summary(msg_texts, row["subject"] or "")
        embed = discord.Embed(title="🤖 AI Ticket Summary",
                               description=summary, color=discord.Color.blurple())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ticket-stats", description="View ticket statistics")
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_stats_cmd(self, interaction: discord.Interaction):
        total  = await db_fetchone("SELECT COUNT(*) as c FROM tickets WHERE guild_id=?", interaction.guild_id)
        open_t = await db_fetchone("SELECT COUNT(*) as c FROM tickets WHERE guild_id=? AND status='open'", interaction.guild_id)
        closed = await db_fetchone("SELECT COUNT(*) as c FROM tickets WHERE guild_id=? AND status='closed'", interaction.guild_id)
        avg_rating = await db_fetchone(
            "SELECT AVG(feedback) as avg FROM tickets WHERE guild_id=? AND feedback IS NOT NULL", interaction.guild_id
        )
        embed = discord.Embed(title="📊 Ticket Statistics", color=discord.Color.blurple())
        embed.add_field(name="Total Tickets", value=str(total["c"] if total else 0), inline=True)
        embed.add_field(name="Open", value=str(open_t["c"] if open_t else 0), inline=True)
        embed.add_field(name="Closed", value=str(closed["c"] if closed else 0), inline=True)
        if avg_rating and avg_rating["avg"]:
            embed.add_field(name="Avg Rating", value=f"⭐ {avg_rating['avg']:.1f}/5", inline=True)
        await interaction.response.send_message(embed=embed)


class TicketOpenModal(discord.ui.Modal, title="Open a Ticket"):
    def __init__(self, bot: DiscordBot, department: str):
        super().__init__()
        self.bot = bot
        self.department = department
        self.subject = discord.ui.TextInput(
            label="Subject",
            placeholder="Brief description of your issue",
            max_length=100,
        )
        self.details = discord.ui.TextInput(
            label="Details",
            placeholder="Describe your issue in detail",
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )
        self.add_item(self.subject)
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ticket_cog: TicketCog = self.bot.cogs.get("Tickets")
        if ticket_cog:
            channel = await ticket_cog.create_ticket_channel(
                interaction.guild, interaction.user,
                self.department, self.subject.value,
            )
            if channel:
                # Save initial details to ticket_messages
                row = await db_fetchone("SELECT ticket_id FROM tickets WHERE channel_id=?", channel.id)
                if row:
                    await db_execute(
                        "INSERT INTO ticket_messages (ticket_id, guild_id, user_id, username, content) VALUES (?,?,?,?,?)",
                        row["ticket_id"], interaction.guild_id, interaction.user.id,
                        str(interaction.user), self.details.value,
                    )
                await interaction.followup.send(
                    embed=build_success_embed(f"Your ticket has been opened: {channel.mention}"),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(embed=build_error_embed("Failed to create ticket channel."), ephemeral=True)


class TicketCloseModal(discord.ui.Modal, title="Close Ticket"):
    def __init__(self, bot: DiscordBot, ticket_row, user: discord.Member):
        super().__init__()
        self.bot = bot
        self.ticket_row = ticket_row
        self.ticket_user = user
        self.reason = discord.ui.TextInput(
            label="Close Reason",
            placeholder="Why is this ticket being closed?",
            max_length=500,
            required=False,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ticket_id = self.ticket_row["ticket_id"]
        await db_execute(
            "UPDATE tickets SET status='closed', closed_at=? WHERE ticket_id=?",
            int(time.time()), ticket_id,
        )
        # Generate transcript
        messages = await db_fetch(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY created_at",
            ticket_id,
        )
        transcript_lines = [
            f"Ticket: {ticket_id}",
            f"Department: {self.ticket_row['department']}",
            f"Subject: {self.ticket_row['subject'] or 'N/A'}",
            f"Opened by: User {self.ticket_row['user_id']}",
            "=" * 50,
        ]
        for m in messages:
            ts = datetime.datetime.fromtimestamp(m["created_at"]).strftime("%Y-%m-%d %H:%M")
            transcript_lines.append(f"[{ts}] {m['username']}: {m['content']}")

        transcript_content = "\n".join(transcript_lines)
        transcript_path = f"transcripts/{ticket_id}.txt"
        async with aiofiles.open(transcript_path, "w", encoding="utf-8") as f:
            await f.write(transcript_content)

        await db_execute(
            "UPDATE tickets SET transcript_url=? WHERE ticket_id=?",
            transcript_path, ticket_id,
        )
        # Update stats for claimer
        if self.ticket_row["claimed_by"]:
            await db_execute(
                """INSERT INTO ticket_stats (guild_id, user_id, tickets_closed) VALUES (?,?,1)
                   ON CONFLICT(guild_id,user_id) DO UPDATE SET tickets_closed=tickets_closed+1""",
                interaction.guild_id, self.ticket_row["claimed_by"],
            )

        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"Closed by {interaction.user.mention}.\n**Reason:** {self.reason.value or 'No reason given'}",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed)

        # Send feedback request to user
        if self.ticket_user:
            try:
                rating_view = TicketRatingView(self.bot, ticket_id)
                dm_embed = discord.Embed(
                    title="📝 Ticket Feedback",
                    description=f"Your ticket `{ticket_id}` has been closed. Please rate your experience:",
                    color=discord.Color.blurple(),
                )
                await self.ticket_user.send(embed=dm_embed, view=rating_view)
            except Exception:
                pass

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket {ticket_id} closed")
        except Exception:
            pass

        await self.bot._log_event(interaction.guild_id, "ticket_closed",
                                   interaction.user.id,
                                   description=f"Ticket {ticket_id} closed by {interaction.user}")


class TicketRatingView(discord.ui.View):
    def __init__(self, bot: DiscordBot, ticket_id: str):
        super().__init__(timeout=86400)
        self.bot = bot
        self.ticket_id = ticket_id
        for i in range(1, 6):
            stars = "⭐" * i
            btn = discord.ui.Button(label=stars, style=discord.ButtonStyle.secondary,
                                     custom_id=f"rate:{ticket_id}:{i}")
            self.add_item(btn)


# ============================================================
# SECTION: Reaction Roles
# ============================================================

class ReactionRolesCog(commands.Cog, name="ReactionRoles"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="reactionrole-add", description="Add a reaction role button to a message")
    @app_commands.default_permissions(manage_roles=True)
    async def rr_add(self, interaction: discord.Interaction,
                      channel: discord.TextChannel, message_id: str,
                      role: discord.Role, label: str, emoji: str = "🎭",
                      exclusive: bool = False, style: str = "button"):
        try:
            msg_id = int(message_id)
            msg = await channel.fetch_message(msg_id)
        except Exception:
            await interaction.response.send_message(embed=build_error_embed("Message not found."), ephemeral=True)
            return

        await db_execute(
            """INSERT INTO reaction_roles (guild_id, message_id, channel_id, role_id, emoji, style, label, exclusive)
               VALUES (?,?,?,?,?,?,?,?)""",
            interaction.guild_id, msg_id, channel.id, role.id, emoji, style, label, int(exclusive),
        )

        view = await self._build_rr_view(interaction.guild_id, msg_id)
        await msg.edit(view=view)
        await interaction.response.send_message(
            embed=build_success_embed(f"Reaction role {emoji} `{label}` → {role.mention} added.")
        )

    @app_commands.command(name="reactionrole-remove", description="Remove a reaction role")
    @app_commands.default_permissions(manage_roles=True)
    async def rr_remove(self, interaction: discord.Interaction, role: discord.Role):
        row = await db_fetchone(
            "SELECT * FROM reaction_roles WHERE guild_id=? AND role_id=?",
            interaction.guild_id, role.id,
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("Reaction role not found."), ephemeral=True)
            return
        await db_execute(
            "DELETE FROM reaction_roles WHERE guild_id=? AND role_id=?",
            interaction.guild_id, role.id,
        )
        await interaction.response.send_message(embed=build_success_embed(f"Removed reaction role for {role.mention}."))

    async def _build_rr_view(self, guild_id: int, message_id: int) -> discord.ui.View:
        rows = await db_fetch(
            "SELECT * FROM reaction_roles WHERE guild_id=? AND message_id=?",
            guild_id, message_id,
        )
        view = discord.ui.View(timeout=None)
        for r in rows[:25]:
            btn = discord.ui.Button(
                label=r["label"] or "Role",
                emoji=r["emoji"],
                style=discord.ButtonStyle.secondary,
                custom_id=f"rr:{message_id}:{r['role_id']}:{r['exclusive']}",
            )
            view.add_item(btn)
        return view

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or not interaction.guild:
            return
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("rr:"):
            return
        parts = custom_id.split(":")
        if len(parts) < 4:
            return
        _, _, role_id_str, exclusive_str = parts[0], parts[1], parts[2], parts[3]
        try:
            role_id   = int(role_id_str)
            exclusive = int(exclusive_str) == 1
        except ValueError:
            return
        member = interaction.user
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(embed=build_error_embed("Role not found."), ephemeral=True)
            return
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Reaction role toggle")
                await interaction.response.send_message(
                    embed=build_success_embed(f"Removed role: **{role.name}**"), ephemeral=True
                )
            else:
                if exclusive:
                    # Remove other roles in same message
                    msg_id = parts[1]
                    other_rows = await db_fetch(
                        "SELECT role_id FROM reaction_roles WHERE guild_id=? AND message_id=?",
                        interaction.guild_id, int(msg_id),
                    )
                    for other in other_rows:
                        other_role = interaction.guild.get_role(other["role_id"])
                        if other_role and other_role in member.roles and other_role != role:
                            await member.remove_roles(other_role, reason="Exclusive reaction role")
                await member.add_roles(role, reason="Reaction role")
                await interaction.response.send_message(
                    embed=build_success_embed(f"Added role: **{role.name}**"), ephemeral=True
                )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=build_error_embed("I don't have permission to manage that role."), ephemeral=True
            )


# ============================================================
# SECTION: Welcome System
# ============================================================

class WelcomeCog(commands.Cog, name="Welcome"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = member.guild.id
        await ensure_user(member.id, guild_id, str(member))
        await db_execute(
            "UPDATE users SET joined_at=? WHERE user_id=? AND guild_id=?",
            int(member.joined_at.timestamp()) if member.joined_at else int(time.time()),
            member.id, guild_id,
        )
        cfg = await get_guild_config(guild_id)
        if not cfg:
            return

        # Auto-roles
        autorole_ids = json.loads(cfg["autorole_ids"] or "[]")
        for rid in autorole_ids:
            role = member.guild.get_role(rid)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except Exception:
                    pass

        # Welcome message
        if cfg["welcome_enabled"] and cfg["welcome_channel"]:
            ch = self.bot.get_channel(cfg["welcome_channel"])
            if ch:
                try:
                    msg_template = cfg["welcome_message"] or "Welcome {user} to **{server}**! 🎉"
                    msg = msg_template.replace("{user}", member.mention) \
                                      .replace("{server}", member.guild.name) \
                                      .replace("{count}", str(member.guild.member_count))

                    # Check if AI welcome is enabled
                    if cfg["ai_enabled"]:
                        ai_msg = await self.bot.ai._call_ai(
                            [{"role": "user", "content": f"Write a short, friendly welcome message (1-2 sentences) for {member.name} who just joined {member.guild.name}. No emojis needed."}],
                            max_tokens=80,
                        )
                        embed = discord.Embed(
                            title=f"👋 Welcome to {member.guild.name}!",
                            description=f"{member.mention}\n\n{ai_msg}",
                            color=discord.Color.green(),
                        )
                    else:
                        embed = discord.Embed(
                            title=f"👋 Welcome!",
                            description=msg,
                            color=discord.Color.green(),
                        )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text=f"Member #{member.guild.member_count}")
                    await ch.send(embed=embed)
                except Exception as e:
                    log.error(f"Welcome message error: {e}")

        await self.bot._log_event(guild_id, "member_join", member.id,
                                   description=f"{member} joined the server")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild_id = member.guild.id
        cfg = await get_guild_config(guild_id)
        if cfg and cfg["welcome_enabled"] and cfg["welcome_channel"]:
            ch = self.bot.get_channel(cfg["welcome_channel"])
            if ch:
                msg_template = cfg["goodbye_message"] or "**{user}** has left the server. Goodbye! 👋"
                msg = msg_template.replace("{user}", str(member)) \
                                  .replace("{server}", member.guild.name)
                embed = discord.Embed(description=msg, color=discord.Color.greyple())
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass
        await self.bot._log_event(guild_id, "member_leave", member.id,
                                   description=f"{member} left the server")

    @app_commands.command(name="welcome-config", description="Configure the welcome system")
    @app_commands.default_permissions(manage_guild=True)
    async def welcome_config(self, interaction: discord.Interaction,
                              channel: discord.TextChannel = None,
                              enabled: bool = True,
                              message: str = None):
        updates = ["welcome_enabled=?", "updated_at=?"]
        values  = [int(enabled), int(time.time())]
        if channel:
            updates.append("welcome_channel=?")
            values.append(channel.id)
        if message:
            updates.append("welcome_message=?")
            values.append(message)
        values.append(interaction.guild_id)
        await db_execute(
            f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id=?",
            *values,
        )
        embed = discord.Embed(title="✅ Welcome System Updated", color=discord.Color.green())
        embed.add_field(name="Status", value="Enabled" if enabled else "Disabled", inline=True)
        if channel:
            embed.add_field(name="Channel", value=channel.mention, inline=True)
        if message:
            embed.add_field(name="Message", value=message[:100], inline=False)
        embed.add_field(
            name="Variables",
            value="`{user}` `{server}` `{count}`",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="autorole-add", description="Add an auto-role for new members")
    @app_commands.default_permissions(manage_roles=True)
    async def autorole_add(self, interaction: discord.Interaction, role: discord.Role):
        cfg = await get_guild_config(interaction.guild_id)
        ids = json.loads(cfg["autorole_ids"] or "[]")
        if role.id in ids:
            await interaction.response.send_message(embed=build_error_embed("Already an auto-role."), ephemeral=True)
            return
        ids.append(role.id)
        await db_execute(
            "UPDATE guild_config SET autorole_ids=? WHERE guild_id=?",
            json.dumps(ids), interaction.guild_id,
        )
        await interaction.response.send_message(embed=build_success_embed(f"Added {role.mention} as an auto-role."))

    @app_commands.command(name="autorole-remove", description="Remove an auto-role")
    @app_commands.default_permissions(manage_roles=True)
    async def autorole_remove(self, interaction: discord.Interaction, role: discord.Role):
        cfg = await get_guild_config(interaction.guild_id)
        ids = json.loads(cfg["autorole_ids"] or "[]")
        if role.id not in ids:
            await interaction.response.send_message(embed=build_error_embed("Not an auto-role."), ephemeral=True)
            return
        ids.remove(role.id)
        await db_execute(
            "UPDATE guild_config SET autorole_ids=? WHERE guild_id=?",
            json.dumps(ids), interaction.guild_id,
        )
        await interaction.response.send_message(embed=build_success_embed(f"Removed {role.mention} from auto-roles."))


# ============================================================
# SECTION: Logging System
# ============================================================

class LoggingCog(commands.Cog, name="Logging"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        await self.bot._log_event(
            message.guild.id, "message_delete",
            message.author.id, channel_id=message.channel.id,
            description=f"Message deleted: {message.content[:200]}",
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return
        await self.bot._log_event(
            before.guild.id, "message_edit",
            before.author.id, channel_id=before.channel.id,
            description=f"Before: {before.content[:100]} | After: {after.content[:100]}",
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                     before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        guild_id = member.guild.id
        now = int(time.time())
        if after.channel and not before.channel:
            # Joined
            key = f"{guild_id}:{member.id}"
            self.bot.voice_sessions[key] = now
            await db_execute(
                "INSERT INTO voice_tracking (user_id, guild_id, channel_id, joined_at) VALUES (?,?,?,?)",
                member.id, guild_id, after.channel.id, now,
            )
            await self.bot._log_event(guild_id, "voice_join", member.id,
                                       channel_id=after.channel.id,
                                       description=f"{member} joined voice: {after.channel.name}")
        elif before.channel and not after.channel:
            # Left
            key = f"{guild_id}:{member.id}"
            joined_at = self.bot.voice_sessions.pop(key, now)
            duration  = now - joined_at
            await db_execute(
                "UPDATE voice_tracking SET left_at=?, duration=? WHERE user_id=? AND guild_id=? AND left_at IS NULL",
                now, duration, member.id, guild_id,
            )
            await db_execute(
                "UPDATE users SET voice_minutes=voice_minutes+? WHERE user_id=? AND guild_id=?",
                duration // 60, member.id, guild_id,
            )
            # Voice XP
            cfg = await get_guild_config(guild_id)
            if cfg and cfg["level_enabled"] and duration >= 60:
                xp_gain = duration // 60 * 3  # 3 XP per voice minute
                lvl = await db_fetchone("SELECT * FROM levels WHERE user_id=? AND guild_id=?", member.id, guild_id)
                if lvl:
                    new_xp = lvl["xp"] + xp_gain
                    await db_execute(
                        "UPDATE levels SET xp=?, level=?, voice_xp=voice_xp+? WHERE user_id=? AND guild_id=?",
                        new_xp, self.bot._calc_level(new_xp), xp_gain, member.id, guild_id,
                    )
            await self.bot._log_event(guild_id, "voice_leave", member.id,
                                       channel_id=before.channel.id,
                                       description=f"{member} left voice after {format_duration(duration)}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not before.guild:
            return
        if before.roles != after.roles:
            added   = [r for r in after.roles if r not in before.roles]
            removed = [r for r in before.roles if r not in after.roles]
            desc = ""
            if added:
                desc += f"Roles added: {', '.join(r.name for r in added)}. "
            if removed:
                desc += f"Roles removed: {', '.join(r.name for r in removed)}."
            await self.bot._log_event(before.guild.id, "member_role_update",
                                       before.id, description=desc)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await self.bot._log_event(channel.guild.id, "channel_create",
                                   description=f"Channel created: #{channel.name}")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            await self.bot._log_event(before.guild.id, "channel_update",
                                       description=f"Channel renamed: #{before.name} → #{after.name}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        await self.bot._log_event(role.guild.id, "role_create",
                                   description=f"Role created: @{role.name}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await self.bot._log_event(role.guild.id, "role_delete",
                                   description=f"Role deleted: @{role.name}")

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        added   = [e for e in after if e not in before]
        removed = [e for e in before if e not in after]
        if added or removed:
            desc = ""
            if added:   desc += f"Emojis added: {', '.join(str(e) for e in added)}. "
            if removed: desc += f"Emojis removed: {', '.join(e.name for e in removed)}."
            await self.bot._log_event(guild.id, "emoji_update", description=desc)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self.bot._log_event(guild.id, "member_ban", user.id,
                                   description=f"{user} was banned")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self.bot._log_event(guild.id, "member_unban", user.id,
                                   description=f"{user} was unbanned")

    @app_commands.command(name="logs-config", description="Configure the logging system")
    @app_commands.default_permissions(administrator=True)
    async def logs_config(self, interaction: discord.Interaction,
                           log_channel: discord.TextChannel = None,
                           mod_log_channel: discord.TextChannel = None):
        updates = ["updated_at=?"]
        values  = [int(time.time())]
        if log_channel:
            updates.append("log_channel=?")
            values.append(log_channel.id)
        if mod_log_channel:
            updates.append("mod_log_channel=?")
            values.append(mod_log_channel.id)
        values.append(interaction.guild_id)
        await db_execute(
            f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id=?", *values
        )
        embed = discord.Embed(title="✅ Logging Configured", color=discord.Color.green())
        if log_channel:
            embed.add_field(name="Log Channel", value=log_channel.mention, inline=True)
        if mod_log_channel:
            embed.add_field(name="Mod Log Channel", value=mod_log_channel.mention, inline=True)
        await interaction.response.send_message(embed=embed)


# ============================================================
# SECTION: Economy System
# ============================================================

JOBS = {
    "developer": {"salary": (500, 900), "cooldown": 3600, "description": "Write code"},
    "teacher":   {"salary": (300, 600), "cooldown": 3600, "description": "Educate students"},
    "chef":      {"salary": (200, 500), "cooldown": 3600, "description": "Cook meals"},
    "doctor":    {"salary": (600, 1000), "cooldown": 3600, "description": "Treat patients"},
    "artist":    {"salary": (150, 400), "cooldown": 3600, "description": "Create art"},
    "streamer":  {"salary": (100, 800), "cooldown": 3600, "description": "Stream games"},
    "trader":    {"salary": (200, 1500), "cooldown": 3600, "description": "Trade stocks (risky)"},
    "miner":     {"salary": (300, 600), "cooldown": 3600, "description": "Mine resources"},
}


class EconomyCog(commands.Cog, name="Economy"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    async def _get_economy(self, user_id: int, guild_id: int) -> aiosqlite.Row:
        row = await db_fetchone(
            "SELECT * FROM economy WHERE user_id=? AND guild_id=?", user_id, guild_id
        )
        if not row:
            await db_execute(
                "INSERT OR IGNORE INTO economy (user_id, guild_id) VALUES (?,?)", user_id, guild_id
            )
            row = await db_fetchone(
                "SELECT * FROM economy WHERE user_id=? AND guild_id=?", user_id, guild_id
            )
        return row

    def _currency(self, cfg, amount: int) -> str:
        if not cfg:
            return f"🪙 {amount:,}"
        return f"{cfg['currency_emoji']} {amount:,} {cfg['currency_name']}"

    @app_commands.command(name="balance", description="Check your or another user's balance")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        eco = await self._get_economy(target.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        total = eco["wallet"] + eco["bank"]
        embed = discord.Embed(title=f"💰 Balance — {target.display_name}", color=discord.Color.gold())
        embed.add_field(name="👛 Wallet", value=self._currency(cfg, eco["wallet"]), inline=True)
        embed.add_field(name="🏦 Bank", value=self._currency(cfg, eco["bank"]), inline=True)
        embed.add_field(name="💎 Total", value=self._currency(cfg, total), inline=True)
        if eco["job"]:
            embed.add_field(name="💼 Job", value=eco["job"].title(), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim your daily reward")
    async def daily(self, interaction: discord.Interaction):
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        now = int(time.time())
        if eco["last_daily"] and now - eco["last_daily"] < 86400:
            remaining = 86400 - (now - eco["last_daily"])
            await interaction.response.send_message(
                embed=build_error_embed(f"Daily already claimed. Next: {format_duration(remaining)}"),
                ephemeral=True,
            )
            return
        # Streak bonus
        streak = eco["daily_streak"]
        if eco["last_daily"] and now - eco["last_daily"] < 172800:
            streak += 1
        else:
            streak = 1
        base    = 200
        bonus   = min(streak * 10, 500)
        reward  = base + bonus
        await db_execute(
            "UPDATE economy SET wallet=wallet+?, daily_streak=?, last_daily=?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
            reward, streak, now, reward, interaction.user.id, interaction.guild_id,
        )
        embed = discord.Embed(title="📅 Daily Reward", color=discord.Color.gold())
        embed.add_field(name="Reward", value=self._currency(cfg, reward), inline=True)
        embed.add_field(name="Streak", value=f"🔥 {streak} days", inline=True)
        if bonus > 0:
            embed.add_field(name="Streak Bonus", value=self._currency(cfg, bonus), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="weekly", description="Claim your weekly reward")
    async def weekly(self, interaction: discord.Interaction):
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        now = int(time.time())
        if eco["last_weekly"] and now - eco["last_weekly"] < 604800:
            remaining = 604800 - (now - eco["last_weekly"])
            await interaction.response.send_message(
                embed=build_error_embed(f"Weekly already claimed. Next: {format_duration(remaining)}"),
                ephemeral=True,
            )
            return
        reward = 1500
        await db_execute(
            "UPDATE economy SET wallet=wallet+?, last_weekly=?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
            reward, now, reward, interaction.user.id, interaction.guild_id,
        )
        embed = discord.Embed(title="📅 Weekly Reward",
                               description=f"You claimed your weekly reward of {self._currency(cfg, reward)}!",
                               color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="monthly", description="Claim your monthly reward")
    async def monthly(self, interaction: discord.Interaction):
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        now = int(time.time())
        if eco["last_monthly"] and now - eco["last_monthly"] < 2592000:
            remaining = 2592000 - (now - eco["last_monthly"])
            await interaction.response.send_message(
                embed=build_error_embed(f"Monthly already claimed. Next: {format_duration(remaining)}"),
                ephemeral=True,
            )
            return
        reward = 10000
        await db_execute(
            "UPDATE economy SET wallet=wallet+?, last_monthly=?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
            reward, now, reward, interaction.user.id, interaction.guild_id,
        )
        embed = discord.Embed(title="📅 Monthly Reward",
                               description=f"You claimed {self._currency(cfg, reward)}! 🎉",
                               color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="work", description="Work your job to earn money")
    async def work(self, interaction: discord.Interaction):
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        now = int(time.time())
        if eco["last_work"] and now - eco["last_work"] < 3600:
            remaining = 3600 - (now - eco["last_work"])
            await interaction.response.send_message(
                embed=build_error_embed(f"You need to rest. Next work: {format_duration(remaining)}"),
                ephemeral=True,
            )
            return
        job = eco["job"] or "freelancer"
        job_data = JOBS.get(job, {"salary": (100, 300), "description": "Do odd jobs"})
        lo, hi = job_data["salary"]
        earned = random.randint(lo, hi)
        await db_execute(
            "UPDATE economy SET wallet=wallet+?, last_work=?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
            earned, now, earned, interaction.user.id, interaction.guild_id,
        )
        work_scenarios = [
            f"You completed a project and earned {self._currency(cfg, earned)}!",
            f"Hard work pays off! You made {self._currency(cfg, earned)}.",
            f"Another day, another dollar! Earned {self._currency(cfg, earned)}.",
        ]
        embed = discord.Embed(title=f"💼 Work — {job.title()}",
                               description=random.choice(work_scenarios),
                               color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="jobs", description="View available jobs")
    async def jobs_list(self, interaction: discord.Interaction):
        embed = discord.Embed(title="💼 Available Jobs", color=discord.Color.blurple())
        for name, data in JOBS.items():
            lo, hi = data["salary"]
            embed.add_field(
                name=f"**{name.title()}**",
                value=f"Salary: {lo:,}–{hi:,} | {data['description']}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="apply", description="Apply for a job")
    @app_commands.describe(job="Job name to apply for")
    async def apply(self, interaction: discord.Interaction, job: str):
        job = job.lower()
        if job not in JOBS:
            await interaction.response.send_message(
                embed=build_error_embed(f"Job not found. Use `/jobs` to see available jobs."), ephemeral=True
            )
            return
        await db_execute(
            "UPDATE economy SET job=? WHERE user_id=? AND guild_id=?",
            job, interaction.user.id, interaction.guild_id,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"You got the job! You are now a **{job.title()}**.")
        )

    @app_commands.command(name="deposit", description="Deposit money into your bank")
    async def deposit(self, interaction: discord.Interaction, amount: str):
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        actual = eco["wallet"] if amount.lower() == "all" else int(amount)
        if actual <= 0 or actual > eco["wallet"]:
            await interaction.response.send_message(embed=build_error_embed("Invalid amount."), ephemeral=True)
            return
        await db_execute(
            "UPDATE economy SET wallet=wallet-?, bank=bank+? WHERE user_id=? AND guild_id=?",
            actual, actual, interaction.user.id, interaction.guild_id,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Deposited {self._currency(cfg, actual)} to your bank.")
        )

    @app_commands.command(name="withdraw", description="Withdraw money from your bank")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        actual = eco["bank"] if amount.lower() == "all" else int(amount)
        if actual <= 0 or actual > eco["bank"]:
            await interaction.response.send_message(embed=build_error_embed("Invalid amount."), ephemeral=True)
            return
        await db_execute(
            "UPDATE economy SET wallet=wallet+?, bank=bank-? WHERE user_id=? AND guild_id=?",
            actual, actual, interaction.user.id, interaction.guild_id,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Withdrew {self._currency(cfg, actual)} from your bank.")
        )

    @app_commands.command(name="pay", description="Pay another user")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message(embed=build_error_embed("Amount must be positive."), ephemeral=True)
            return
        if member == interaction.user:
            await interaction.response.send_message(embed=build_error_embed("Cannot pay yourself."), ephemeral=True)
            return
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        if eco["wallet"] < amount:
            await interaction.response.send_message(embed=build_error_embed("Insufficient funds."), ephemeral=True)
            return
        await db_execute(
            "UPDATE economy SET wallet=wallet-? WHERE user_id=? AND guild_id=?",
            amount, interaction.user.id, interaction.guild_id,
        )
        await self._get_economy(member.id, interaction.guild_id)
        await db_execute(
            "UPDATE economy SET wallet=wallet+? WHERE user_id=? AND guild_id=?",
            amount, member.id, interaction.guild_id,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Paid {self._currency(cfg, amount)} to {member.mention}.")
        )

    @app_commands.command(name="leaderboard", description="View the economy leaderboard")
    async def leaderboard_eco(self, interaction: discord.Interaction):
        rows = await db_fetch(
            "SELECT user_id, wallet+bank as total FROM economy WHERE guild_id=? ORDER BY total DESC LIMIT 10",
            interaction.guild_id,
        )
        cfg = await get_guild_config(interaction.guild_id)
        embed = discord.Embed(title="🏆 Economy Leaderboard", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        description = ""
        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            description += f"{medals[i]} **{name}** — {self._currency(cfg, row['total'])}\n"
        embed.description = description or "No data yet."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop", description="View the server shop")
    async def shop_view(self, interaction: discord.Interaction):
        rows = await db_fetch(
            "SELECT * FROM shop WHERE guild_id=? AND enabled=1 ORDER BY price",
            interaction.guild_id,
        )
        cfg = await get_guild_config(interaction.guild_id)
        embed = discord.Embed(title="🛒 Server Shop", color=discord.Color.blurple())
        if not rows:
            embed.description = "The shop is empty."
        else:
            for item in rows:
                stock = "∞" if item["stock"] == -1 else str(item["stock"])
                embed.add_field(
                    name=f"{item['emoji']} {item['name']} — {self._currency(cfg, item['price'])}",
                    value=f"{item['description'] or 'No description'} | Stock: {stock}",
                    inline=False,
                )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Buy an item from the shop")
    async def buy(self, interaction: discord.Interaction, item_id: str):
        item = await db_fetchone(
            "SELECT * FROM shop WHERE guild_id=? AND item_id=? AND enabled=1",
            interaction.guild_id, item_id,
        )
        if not item:
            await interaction.response.send_message(embed=build_error_embed("Item not found."), ephemeral=True)
            return
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        if eco["wallet"] < item["price"]:
            await interaction.response.send_message(
                embed=build_error_embed(f"Insufficient funds. Need {self._currency(cfg, item['price'])}."),
                ephemeral=True,
            )
            return
        if item["stock"] == 0:
            await interaction.response.send_message(embed=build_error_embed("Out of stock."), ephemeral=True)
            return
        await db_execute(
            "UPDATE economy SET wallet=wallet-?, total_spent=total_spent+? WHERE user_id=? AND guild_id=?",
            item["price"], item["price"], interaction.user.id, interaction.guild_id,
        )
        if item["stock"] > 0:
            await db_execute("UPDATE shop SET stock=stock-1 WHERE item_id=? AND guild_id=?",
                              item["item_id"], interaction.guild_id)
        await db_execute(
            "INSERT INTO inventory (user_id, guild_id, item_id) VALUES (?,?,?)",
            interaction.user.id, interaction.guild_id, item["item_id"],
        )
        # Role item
        if item["type"] == "role" and item["role_id"]:
            role = interaction.guild.get_role(item["role_id"])
            if role:
                expires_at = int(time.time()) + item["duration"] if item["duration"] else None
                await interaction.user.add_roles(role, reason=f"Shop purchase: {item['name']}")
        await interaction.response.send_message(
            embed=build_success_embed(f"Purchased **{item['emoji']} {item['name']}** for {self._currency(cfg, item['price'])}!")
        )

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory_view(self, interaction: discord.Interaction):
        rows = await db_fetch(
            """SELECT i.*, s.name, s.emoji, s.description FROM inventory i
               LEFT JOIN shop s ON i.item_id = s.item_id
               WHERE i.user_id=? AND i.guild_id=?""",
            interaction.user.id, interaction.guild_id,
        )
        embed = discord.Embed(title="🎒 Your Inventory", color=discord.Color.blurple())
        if not rows:
            embed.description = "Your inventory is empty."
        else:
            for item in rows:
                name  = item["name"] or item["item_id"]
                emoji = item["emoji"] or "📦"
                embed.add_field(name=f"{emoji} {name}", value=f"Qty: {item['quantity']}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="gamble", description="Gamble your coins (casino)")
    async def gamble(self, interaction: discord.Interaction, amount: int):
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        if amount <= 0 or amount > eco["wallet"]:
            await interaction.response.send_message(embed=build_error_embed("Invalid amount."), ephemeral=True)
            return
        roll  = random.random()
        if roll < 0.47:   # Win
            multiplier = random.choice([1.5, 2.0, 2.5, 3.0])
            winnings   = int(amount * multiplier)
            profit     = winnings - amount
            await db_execute(
                "UPDATE economy SET wallet=wallet+? WHERE user_id=? AND guild_id=?",
                profit, interaction.user.id, interaction.guild_id,
            )
            embed = discord.Embed(title="🎰 You Won!",
                                   description=f"You bet {self._currency(cfg, amount)} and won {self._currency(cfg, winnings)}! ({multiplier}x)",
                                   color=discord.Color.green())
        else:             # Lose
            await db_execute(
                "UPDATE economy SET wallet=wallet-? WHERE user_id=? AND guild_id=?",
                amount, interaction.user.id, interaction.guild_id,
            )
            embed = discord.Embed(title="🎰 You Lost",
                                   description=f"You lost {self._currency(cfg, amount)}. Better luck next time!",
                                   color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="fish", description="Go fishing for coins")
    async def fish(self, interaction: discord.Interaction):
        eco = await self._get_economy(interaction.user.id, interaction.guild_id)
        cfg = await get_guild_config(interaction.guild_id)
        now = int(time.time())
        await interaction.response.defer()
        await asyncio.sleep(2)
        fish_table = [
            ("🐟 Small Fish",    50,   200,  0.40),
            ("🐠 Tropical Fish", 150,  400,  0.25),
            ("🐡 Pufferfish",    100,  300,  0.20),
            ("🦈 Shark",         500,  1000, 0.10),
            ("🦞 Lobster",       800,  1500, 0.04),
            ("💎 Diamond Fish",  2000, 5000, 0.01),
        ]
        roll = random.random()
        cumulative = 0
        caught = fish_table[0]
        for fish in fish_table:
            cumulative += fish[3]
            if roll < cumulative:
                caught = fish
                break
        reward = random.randint(caught[1], caught[2])
        await db_execute(
            "UPDATE economy SET wallet=wallet+?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
            reward, reward, interaction.user.id, interaction.guild_id,
        )
        embed = discord.Embed(
            title="🎣 Fishing",
            description=f"You caught a {caught[0]}!\nYou earned {self._currency(cfg, reward)}!",
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="mine", description="Mine for resources and coins")
    async def mine(self, interaction: discord.Interaction):
        cfg = await get_guild_config(interaction.guild_id)
        await interaction.response.defer()
        await asyncio.sleep(2)
        mine_table = [
            ("🪨 Stone",    10,  50,   0.40),
            ("⚙️ Iron",     80,  150,  0.25),
            ("💛 Gold",     200, 500,  0.20),
            ("💎 Diamond",  500, 1500, 0.10),
            ("💠 Crystal",  1000,3000, 0.04),
            ("🌟 Stardust", 3000,8000, 0.01),
        ]
        roll = random.random()
        cumulative = 0
        found = mine_table[0]
        for item in mine_table:
            cumulative += item[3]
            if roll < cumulative:
                found = item
                break
        reward = random.randint(found[1], found[2])
        await db_execute(
            "UPDATE economy SET wallet=wallet+?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
            reward, reward, interaction.user.id, interaction.guild_id,
        )
        embed = discord.Embed(
            title="⛏️ Mining",
            description=f"You found {found[0]}!\nYou earned {self._currency(cfg, reward)}!",
            color=discord.Color.dark_grey(),
        )
        await interaction.followup.send(embed=embed)


# ============================================================
# SECTION: Leveling System
# ============================================================

class LevelingCog(commands.Cog, name="Leveling"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="rank", description="View your or another user's rank card")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        await interaction.response.defer()
        row = await db_fetchone(
            "SELECT * FROM levels WHERE user_id=? AND guild_id=?",
            target.id, interaction.guild_id,
        )
        if not row:
            await interaction.followup.send(embed=build_info_embed("No rank yet", "This user hasn't chatted yet."))
            return
        current_level = row["level"]
        xp_needed     = self.bot._xp_for_level(current_level + 1)
        xp_current    = self.bot._xp_for_level(current_level)
        xp_progress   = row["xp"] - xp_current
        xp_for_next   = xp_needed - xp_current
        progress_pct  = min(xp_progress / max(xp_for_next, 1), 1.0)

        # Build rank card image
        img = await self._build_rank_card(target, current_level, row["xp"],
                                           xp_progress, xp_for_next, progress_pct, row["prestige"])
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_image(url="attachment://rank.png")
        await interaction.followup.send(embed=embed, file=discord.File(img, "rank.png"))

    async def _build_rank_card(self, member: discord.Member, level: int,
                                 total_xp: int, xp_progress: int, xp_for_next: int,
                                 progress_pct: float, prestige: int) -> io.BytesIO:
        W, H = 800, 200
        img  = Image.new("RGBA", (W, H), (30, 30, 40, 255))
        draw = ImageDraw.Draw(img)

        # Background gradient
        for y in range(H):
            r = int(30 + (50 - 30) * y / H)
            draw.rectangle([(0, y), (W, y + 1)], fill=(r, r, r + 20, 255))

        # Avatar circle
        try:
            avatar_data = await member.display_avatar.replace(size=128, format="png").read()
            av = Image.open(io.BytesIO(avatar_data)).resize((120, 120)).convert("RGBA")
            mask = Image.new("L", (120, 120), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 119, 119], fill=255)
            img.paste(av, (40, 40), mask)
        except Exception:
            draw.ellipse([40, 40, 159, 159], fill=(100, 100, 150, 255))

        # Name
        try:
            font_large  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            font_small  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except Exception:
            font_large = font_medium = font_small = ImageFont.load_default()

        display_name = member.display_name[:20]
        draw.text((200, 30), display_name, font=font_large, fill=(255, 255, 255, 255))
        if prestige > 0:
            draw.text((200, 65), f"✦ Prestige {prestige}", font=font_medium, fill=(255, 215, 0, 255))
        draw.text((200, 95), f"Level {level} • {total_xp:,} XP total", font=font_medium, fill=(200, 200, 220, 255))

        # Progress bar
        bar_x, bar_y, bar_w, bar_h = 200, 130, 530, 24
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=12,
                                 fill=(60, 60, 80, 255))
        filled = int(bar_w * progress_pct)
        if filled > 0:
            draw.rounded_rectangle([bar_x, bar_y, bar_x + filled, bar_y + bar_h], radius=12,
                                     fill=(88, 101, 242, 255))
        draw.text((200, 160), f"{xp_progress:,} / {xp_for_next:,} XP",
                   font=font_small, fill=(180, 180, 200, 255))

        # Level circle
        lx, ly = 690, 90
        draw.ellipse([lx - 45, ly - 45, lx + 45, ly + 45], fill=(88, 101, 242, 255))
        lvl_text = str(level)
        draw.text((lx, ly), lvl_text, font=font_large, fill=(255, 255, 255, 255), anchor="mm")

        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf

    @app_commands.command(name="top", description="View the XP leaderboard")
    async def top(self, interaction: discord.Interaction):
        rows = await db_fetch(
            "SELECT user_id, level, xp FROM levels WHERE guild_id=? ORDER BY xp DESC LIMIT 10",
            interaction.guild_id,
        )
        embed = discord.Embed(title="⭐ XP Leaderboard", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        desc = ""
        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name   = member.display_name if member else f"User {row['user_id']}"
            desc  += f"{medals[i]} **{name}** — Level {row['level']} ({row['xp']:,} XP)\n"
        embed.description = desc or "No data yet."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setxp", description="Set a user's XP (admin)")
    @app_commands.default_permissions(administrator=True)
    async def setxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        new_level = self.bot._calc_level(xp)
        await db_execute(
            """INSERT INTO levels (user_id, guild_id, xp, level) VALUES (?,?,?,?)
               ON CONFLICT(user_id,guild_id) DO UPDATE SET xp=excluded.xp, level=excluded.level""",
            member.id, interaction.guild_id, xp, new_level,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Set {member.mention}'s XP to {xp:,} (Level {new_level}).")
        )

    @app_commands.command(name="role-reward-add", description="Add a role reward for reaching a level")
    @app_commands.default_permissions(administrator=True)
    async def rr_level_add(self, interaction: discord.Interaction,
                             level: int, role: discord.Role, remove_previous: bool = False):
        await db_execute(
            "INSERT OR REPLACE INTO role_rewards (guild_id, level, role_id, remove_prev) VALUES (?,?,?,?)",
            interaction.guild_id, level, role.id, int(remove_previous),
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Added {role.mention} as reward for reaching Level {level}.")
        )

    @app_commands.command(name="prestige", description="Prestige your level (resets to 0, gains prestige point)")
    async def prestige(self, interaction: discord.Interaction):
        row = await db_fetchone(
            "SELECT * FROM levels WHERE user_id=? AND guild_id=?",
            interaction.user.id, interaction.guild_id,
        )
        if not row or row["level"] < 50:
            await interaction.response.send_message(
                embed=build_error_embed("You need to be Level 50 to prestige."), ephemeral=True
            )
            return
        await db_execute(
            "UPDATE levels SET xp=0, level=0, prestige=prestige+1 WHERE user_id=? AND guild_id=?",
            interaction.user.id, interaction.guild_id,
        )
        embed = discord.Embed(
            title="✦ Prestige Achieved!",
            description=f"You prestiged! You are now **Prestige {row['prestige'] + 1}**. Your level has reset.",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)


# ============================================================
# SECTION: Music System
# ============================================================

class MusicCog(commands.Cog, name="Music"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot
        self.yt_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "default_search": "ytsearch",
            "source_address": "0.0.0.0",
        }

    async def _get_vc(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        if interaction.user.voice:
            vc = interaction.guild.voice_client
            if not vc:
                vc = await interaction.user.voice.channel.connect()
            elif vc.channel != interaction.user.voice.channel:
                await vc.move_to(interaction.user.voice.channel)
            return vc
        return None

    async def _extract_info(self, query: str) -> Optional[Dict]:
        loop = asyncio.get_event_loop()
        try:
            with yt_dlp.YoutubeDL(self.yt_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
                if "entries" in info:
                    info = info["entries"][0]
                return info
        except Exception as e:
            log.error(f"Music extract error: {e}")
            return None

    @app_commands.command(name="play", description="Play a song from YouTube")
    async def play(self, interaction: discord.Interaction, query: str):
        vc = await self._get_vc(interaction)
        if not vc:
            await interaction.response.send_message(
                embed=build_error_embed("Join a voice channel first."), ephemeral=True
            )
            return
        await interaction.response.defer()
        info = await self._extract_info(query)
        if not info:
            await interaction.followup.send(embed=build_error_embed("Could not find that song."))
            return
        guild_id = interaction.guild_id
        track = {
            "title":     info.get("title", "Unknown"),
            "url":       info.get("url") or info.get("webpage_url"),
            "webpage":   info.get("webpage_url", ""),
            "duration":  info.get("duration", 0),
            "thumbnail": info.get("thumbnail", ""),
            "requester": interaction.user.mention,
        }
        self.bot.music_queues[guild_id].append(track)
        if not vc.is_playing():
            await self._play_next(interaction.guild, vc)
            embed = discord.Embed(title="▶️ Now Playing", color=discord.Color.green())
        else:
            pos = len(self.bot.music_queues[guild_id])
            embed = discord.Embed(title=f"📋 Added to Queue (#{pos})", color=discord.Color.blurple())
        embed.add_field(name="Track", value=f"[{track['title']}]({track['webpage']})")
        embed.add_field(name="Requested by", value=track["requester"])
        if track["duration"]:
            embed.add_field(name="Duration", value=format_duration(track["duration"]))
        await interaction.followup.send(embed=embed)

    async def _play_next(self, guild: discord.Guild, vc: discord.VoiceClient):
        queue = self.bot.music_queues[guild.id]
        if not queue:
            return
        track = queue.pop(0)
        self.bot.music_current[guild.id] = track
        try:
            source = discord.FFmpegPCMAudio(
                track["url"],
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn",
            )
            source = discord.PCMVolumeTransformer(source, volume=0.5)
            vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
                self._play_next(guild, vc), self.bot.loop
            ).result() if not e else log.error(f"Music error: {e}"))
        except Exception as e:
            log.error(f"Play error: {e}")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message(embed=build_error_embed("Nothing is playing."), ephemeral=True)
            return
        vc.stop()
        await interaction.response.send_message(embed=build_success_embed("Skipped current track."))

    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            self.bot.music_queues[interaction.guild_id].clear()
            self.bot.music_current.pop(interaction.guild_id, None)
            await vc.disconnect()
        await interaction.response.send_message(embed=build_success_embed("Stopped music and cleared queue."))

    @app_commands.command(name="queue", description="View the music queue")
    async def queue_view(self, interaction: discord.Interaction):
        current = self.bot.music_current.get(interaction.guild_id)
        queue   = self.bot.music_queues[interaction.guild_id]
        embed   = discord.Embed(title="🎵 Music Queue", color=discord.Color.blurple())
        if current:
            embed.add_field(name="▶️ Now Playing",
                             value=f"[{current['title']}]({current['webpage']})",
                             inline=False)
        if queue:
            q_text = "\n".join(f"`{i+1}.` [{t['title']}]({t['webpage']})" for i, t in enumerate(queue[:10]))
            embed.add_field(name=f"📋 Up Next ({len(queue)})", value=q_text, inline=False)
        else:
            embed.add_field(name="Queue", value="Empty", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set the music volume")
    async def volume(self, interaction: discord.Interaction, level: int):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message(embed=build_error_embed("Nothing is playing."), ephemeral=True)
            return
        level = max(0, min(200, level))
        if hasattr(vc.source, "volume"):
            vc.source.volume = level / 100
        await interaction.response.send_message(embed=build_success_embed(f"Volume set to {level}%."))

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message(embed=build_success_embed("Paused."))
        else:
            await interaction.response.send_message(embed=build_error_embed("Nothing is playing."), ephemeral=True)

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message(embed=build_success_embed("Resumed."))
        else:
            await interaction.response.send_message(embed=build_error_embed("Nothing is paused."), ephemeral=True)

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        current = self.bot.music_current.get(interaction.guild_id)
        if not current:
            await interaction.response.send_message(embed=build_error_embed("Nothing is playing."), ephemeral=True)
            return
        embed = discord.Embed(title="🎵 Now Playing",
                               description=f"[{current['title']}]({current['webpage']})",
                               color=discord.Color.green())
        if current.get("duration"):
            embed.add_field(name="Duration", value=format_duration(current["duration"]))
        if current.get("requester"):
            embed.add_field(name="Requested by", value=current["requester"])
        if current.get("thumbnail"):
            embed.set_thumbnail(url=current["thumbnail"])
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shuffle", description="Shuffle the music queue")
    async def shuffle(self, interaction: discord.Interaction):
        queue = self.bot.music_queues[interaction.guild_id]
        if not queue:
            await interaction.response.send_message(embed=build_error_embed("Queue is empty."), ephemeral=True)
            return
        random.shuffle(queue)
        await interaction.response.send_message(embed=build_success_embed("Queue shuffled!"))


# ============================================================
# SECTION: Giveaway System
# ============================================================

class GiveawayCog(commands.Cog, name="Giveaways"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="giveaway-start", description="Start a giveaway")
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway_start(self, interaction: discord.Interaction,
                              prize: str, duration: str = "24h",
                              winners: int = 1, channel: discord.TextChannel = None,
                              req_role: discord.Role = None,
                              description: str = None):
        secs = parse_duration(duration)
        if not secs:
            await interaction.response.send_message(embed=build_error_embed("Invalid duration."), ephemeral=True)
            return
        target_ch = channel or interaction.channel
        ends_at   = int(time.time()) + secs
        g_id      = generate_id("GIVE")
        embed = discord.Embed(
            title=f"🎉 GIVEAWAY",
            description=f"**Prize:** {prize}\n{description or ''}\n\nClick 🎉 to enter!\n{f'**Required role:** {req_role.mention}' if req_role else ''}",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Winners", value=str(winners), inline=True)
        embed.add_field(name="Ends", value=f"<t:{ends_at}:R>", inline=True)
        embed.add_field(name="Hosted by", value=interaction.user.mention, inline=True)
        embed.set_footer(text=f"Giveaway ID: {g_id}")

        view = GiveawayView(self.bot, g_id)
        msg  = await target_ch.send(embed=embed, view=view)

        await db_execute(
            """INSERT INTO giveaways
               (giveaway_id, guild_id, channel_id, message_id, host_id, prize, description,
                winners_count, req_role, ends_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            g_id, interaction.guild_id, target_ch.id, msg.id,
            interaction.user.id, prize, description, winners,
            req_role.id if req_role else None, ends_at,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Giveaway started in {target_ch.mention}!"), ephemeral=True
        )

    @app_commands.command(name="giveaway-reroll", description="Reroll giveaway winners")
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway_reroll(self, interaction: discord.Interaction, giveaway_id: str):
        row = await db_fetchone(
            "SELECT * FROM giveaways WHERE giveaway_id=? AND guild_id=?",
            giveaway_id, interaction.guild_id,
        )
        if not row or row["status"] != "ended":
            await interaction.response.send_message(embed=build_error_embed("Giveaway not found or still active."), ephemeral=True)
            return
        entries = json.loads(row["entries"] or "[]")
        if not entries:
            await interaction.response.send_message(embed=build_error_embed("No entries."), ephemeral=True)
            return
        new_winners = random.sample(entries, min(row["winners_count"], len(entries)))
        mentions = " ".join(f"<@{w}>" for w in new_winners)
        await interaction.response.send_message(
            embed=build_success_embed(f"🎉 Rerolled winners: {mentions}")
        )


class GiveawayView(discord.ui.View):
    def __init__(self, bot: DiscordBot, giveaway_id: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.giveaway_id = giveaway_id
        btn = discord.ui.Button(label="Enter Giveaway", emoji="🎉",
                                 style=discord.ButtonStyle.primary,
                                 custom_id=f"give:{giveaway_id}")
        self.add_item(btn)


# ============================================================
# SECTION: Poll System
# ============================================================

class PollCog(commands.Cog, name="Polls"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a poll")
    async def create_poll(self, interaction: discord.Interaction,
                           question: str, option1: str, option2: str,
                           option3: str = None, option4: str = None,
                           option5: str = None, anonymous: bool = False,
                           duration: str = None):
        options = [o for o in [option1, option2, option3, option4, option5] if o]
        if len(options) < 2:
            await interaction.response.send_message(embed=build_error_embed("Need at least 2 options."), ephemeral=True)
            return
        poll_id = generate_id("POLL")
        ends_at = int(time.time()) + parse_duration(duration) if duration else None

        embed = discord.Embed(title=f"📊 {question}", color=discord.Color.blurple())
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        options_text = "\n".join(f"{number_emojis[i]} {opt}" for i, opt in enumerate(options))
        embed.description = options_text
        if anonymous:
            embed.set_footer(text="🔒 Anonymous poll")
        if ends_at:
            embed.add_field(name="Ends", value=f"<t:{ends_at}:R>")

        view = PollView(self.bot, poll_id, options, anonymous)
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()

        await db_execute(
            """INSERT INTO polls (poll_id, guild_id, channel_id, message_id, creator_id, question, options, anonymous, ends_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            poll_id, interaction.guild_id, interaction.channel_id, msg.id,
            interaction.user.id, question, json.dumps(options), int(anonymous), ends_at,
        )

    @app_commands.command(name="poll-results", description="View poll results")
    async def poll_results(self, interaction: discord.Interaction, poll_id: str):
        row = await db_fetchone(
            "SELECT * FROM polls WHERE poll_id=? AND guild_id=?",
            poll_id, interaction.guild_id,
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("Poll not found."), ephemeral=True)
            return
        options = json.loads(row["options"])
        votes   = json.loads(row["votes"])
        total   = sum(len(v) for v in votes.values())
        embed   = discord.Embed(title=f"📊 Poll Results: {row['question']}", color=discord.Color.blurple())
        for i, opt in enumerate(options):
            count = len(votes.get(str(i), []))
            pct   = (count / total * 100) if total > 0 else 0
            bar   = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            embed.add_field(name=opt, value=f"{bar} {count} votes ({pct:.1f}%)", inline=False)
        embed.set_footer(text=f"Total votes: {total} | Status: {row['status']}")
        await interaction.response.send_message(embed=embed)


class PollView(discord.ui.View):
    def __init__(self, bot: DiscordBot, poll_id: str, options: List[str], anonymous: bool):
        super().__init__(timeout=None)
        self.bot = bot
        self.poll_id = poll_id
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for i, opt in enumerate(options[:5]):
            btn = discord.ui.Button(
                label=opt[:80],
                emoji=number_emojis[i],
                style=discord.ButtonStyle.secondary,
                custom_id=f"poll:{poll_id}:{i}",
            )
            self.add_item(btn)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        pass  # Handled globally in bot


# ============================================================
# SECTION: Suggestion System
# ============================================================

class SuggestionCog(commands.Cog, name="Suggestions"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="suggest", description="Submit a suggestion")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        await interaction.response.defer(ephemeral=True)
        cfg = await get_guild_config(interaction.guild_id)
        s_id     = generate_id("SUGG")
        category = await self.bot.ai.categorize_suggestion(suggestion)

        embed = discord.Embed(
            title=f"💡 Suggestion #{s_id}",
            description=suggestion,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Category", value=category.title(), inline=True)
        embed.add_field(name="Author", value=interaction.user.mention, inline=True)
        embed.add_field(name="Status", value="⏳ Pending", inline=True)

        view = SuggestionView(self.bot, s_id)

        # Find suggestion channel or use current
        target_ch = interaction.channel
        msg = await target_ch.send(embed=embed, view=view)

        await db_execute(
            """INSERT INTO suggestions (suggestion_id, guild_id, channel_id, message_id, user_id, content, category)
               VALUES (?,?,?,?,?,?,?)""",
            s_id, interaction.guild_id, target_ch.id, msg.id,
            interaction.user.id, suggestion, category,
        )
        await interaction.followup.send(embed=build_success_embed("Your suggestion has been submitted!"), ephemeral=True)

    @app_commands.command(name="suggestion-review", description="Approve or reject a suggestion")
    @app_commands.default_permissions(manage_guild=True)
    async def suggestion_review(self, interaction: discord.Interaction,
                                  suggestion_id: str, status: str, note: str = None):
        valid = {"approved", "rejected", "implemented", "considering"}
        if status not in valid:
            await interaction.response.send_message(
                embed=build_error_embed(f"Status must be: {', '.join(valid)}"), ephemeral=True
            )
            return
        row = await db_fetchone(
            "SELECT * FROM suggestions WHERE suggestion_id=? AND guild_id=?",
            suggestion_id, interaction.guild_id,
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("Suggestion not found."), ephemeral=True)
            return
        await db_execute(
            "UPDATE suggestions SET status=?, reviewer_id=?, reviewer_note=?, updated_at=? WHERE suggestion_id=?",
            status, interaction.user.id, note, int(time.time()), suggestion_id,
        )
        colors = {
            "approved":     discord.Color.green(),
            "rejected":     discord.Color.red(),
            "implemented":  discord.Color.gold(),
            "considering":  discord.Color.orange(),
        }
        icons = {
            "approved": "✅", "rejected": "❌", "implemented": "🚀", "considering": "🤔"
        }
        channel = self.bot.get_channel(row["channel_id"])
        if channel and row["message_id"]:
            try:
                msg = await channel.fetch_message(row["message_id"])
                embed = msg.embeds[0] if msg.embeds else discord.Embed()
                for i, field in enumerate(embed.fields):
                    if field.name == "Status":
                        embed.set_field_at(i, name="Status",
                                           value=f"{icons[status]} {status.title()}", inline=True)
                        break
                embed.color = colors[status]
                if note:
                    embed.add_field(name="Review Note", value=note, inline=False)
                await msg.edit(embed=embed)
            except Exception:
                pass
        await interaction.response.send_message(
            embed=build_success_embed(f"Suggestion `{suggestion_id}` marked as **{status}**.")
        )


class SuggestionView(discord.ui.View):
    def __init__(self, bot: DiscordBot, suggestion_id: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.suggestion_id = suggestion_id
        up_btn   = discord.ui.Button(emoji="👍", style=discord.ButtonStyle.success,
                                      custom_id=f"sugg_vote:{suggestion_id}:up")
        down_btn = discord.ui.Button(emoji="👎", style=discord.ButtonStyle.danger,
                                      custom_id=f"sugg_vote:{suggestion_id}:down")
        self.add_item(up_btn)
        self.add_item(down_btn)


# ============================================================
# SECTION: Utility System
# ============================================================

class UtilityCog(commands.Cog, name="Utility"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="serverinfo", description="View server information")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        bots    = sum(1 for m in g.members if m.bot)
        humans  = g.member_count - bots
        created = int(g.created_at.timestamp())
        embed = discord.Embed(title=g.name, color=discord.Color.blurple())
        embed.set_thumbnail(url=g.icon.url if g.icon else None)
        embed.add_field(name="👑 Owner", value=g.owner.mention if g.owner else "Unknown", inline=True)
        embed.add_field(name="📅 Created", value=f"<t:{created}:D>", inline=True)
        embed.add_field(name="👥 Members", value=f"{humans:,} humans | {bots} bots", inline=True)
        embed.add_field(name="📺 Channels", value=f"{len(g.text_channels)} text | {len(g.voice_channels)} voice", inline=True)
        embed.add_field(name="🎭 Roles", value=str(len(g.roles)), inline=True)
        embed.add_field(name="😀 Emojis", value=str(len(g.emojis)), inline=True)
        embed.add_field(name="🚀 Boosts", value=f"{g.premium_subscription_count} (Tier {g.premium_tier})", inline=True)
        embed.add_field(name="🌍 Region", value=str(g.preferred_locale), inline=True)
        embed.set_footer(text=f"Server ID: {g.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="View information about a user")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        m = member or interaction.user
        joined   = int(m.joined_at.timestamp()) if m.joined_at else 0
        created  = int(m.created_at.timestamp())
        roles    = [r.mention for r in m.roles[1:][:10]]
        db_user  = await db_fetchone("SELECT * FROM users WHERE user_id=? AND guild_id=?", m.id, interaction.guild_id)
        embed = discord.Embed(title=str(m), color=m.color)
        embed.set_thumbnail(url=m.display_avatar.url)
        embed.add_field(name="📅 Joined Server", value=f"<t:{joined}:D>" if joined else "Unknown", inline=True)
        embed.add_field(name="🎂 Account Created", value=f"<t:{created}:D>", inline=True)
        embed.add_field(name="🤖 Bot", value="Yes" if m.bot else "No", inline=True)
        if db_user:
            embed.add_field(name="💬 Messages", value=f"{db_user['message_count']:,}", inline=True)
            embed.add_field(name="🎙️ Voice", value=f"{db_user['voice_minutes']:,} min", inline=True)
        if roles:
            embed.add_field(name=f"🎭 Roles ({len(m.roles)-1})", value=" ".join(roles), inline=False)
        embed.set_footer(text=f"User ID: {m.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Get a user's avatar")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        m = member or interaction.user
        embed = discord.Embed(title=f"{m.display_name}'s Avatar", color=discord.Color.blurple())
        embed.set_image(url=m.display_avatar.url)
        for fmt in ["png", "jpg", "webp"]:
            embed.description = (embed.description or "") + f"[{fmt.upper()}]({m.display_avatar.with_format(fmt).url}) | "
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="banner", description="Get a user's banner")
    async def banner(self, interaction: discord.Interaction, member: discord.Member = None):
        m = member or interaction.user
        user = await self.bot.fetch_user(m.id)
        if not user.banner:
            await interaction.response.send_message(embed=build_error_embed("This user has no banner."), ephemeral=True)
            return
        embed = discord.Embed(title=f"{m.display_name}'s Banner", color=discord.Color.blurple())
        embed.set_image(url=user.banner.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
        embed.add_field(name="WebSocket Latency", value=f"{latency}ms", inline=True)
        embed.add_field(name="Status", value="✅ Online", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botstats", description="View bot statistics")
    async def botstats(self, interaction: discord.Interaction):
        uptime  = int(time.time() - BOT_START_TIME)
        cpu     = psutil.cpu_percent()
        mem     = psutil.virtual_memory()
        embed   = discord.Embed(title=f"📊 Bot Statistics v{BOT_VERSION}", color=discord.Color.blurple())
        embed.add_field(name="Uptime",   value=format_duration(uptime), inline=True)
        embed.add_field(name="Servers",  value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Users",    value=f"{sum(g.member_count for g in self.bot.guilds):,}", inline=True)
        embed.add_field(name="Latency",  value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="CPU",      value=f"{cpu:.1f}%", inline=True)
        embed.add_field(name="Memory",   value=f"{mem.percent:.1f}%", inline=True)
        embed.add_field(name="Python",   value=sys.version.split()[0], inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="remind", description="Set a reminder")
    async def remind(self, interaction: discord.Interaction, duration: str, message: str):
        secs = parse_duration(duration)
        if not secs:
            await interaction.response.send_message(embed=build_error_embed("Invalid duration."), ephemeral=True)
            return
        remind_at = int(time.time()) + secs
        await db_execute(
            "INSERT INTO reminders (user_id, guild_id, channel_id, message, remind_at) VALUES (?,?,?,?,?)",
            interaction.user.id, interaction.guild_id, interaction.channel_id, message, remind_at,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Reminder set for <t:{remind_at}:R>: {message[:100]}")
        )

    @app_commands.command(name="qr", description="Generate a QR code")
    async def qr(self, interaction: discord.Interaction, content: str):
        await interaction.response.defer()
        qr_img = qrcode.make(content)
        buf = io.BytesIO()
        qr_img.save(buf, "PNG")
        buf.seek(0)
        await interaction.followup.send(
            embed=build_info_embed("QR Code", f"Content: `{content[:50]}`"),
            file=discord.File(buf, "qr.png"),
        )

    @app_commands.command(name="translate", description="Translate text to another language")
    async def translate_cmd(self, interaction: discord.Interaction,
                             text: str, language: str = "English"):
        await interaction.response.defer()
        result = await self.bot.ai.translate(text, language)
        embed = discord.Embed(title=f"🌐 Translation → {language}", color=discord.Color.blurple())
        embed.add_field(name="Original", value=text[:512], inline=False)
        embed.add_field(name="Translated", value=result[:512], inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="weather", description="Get weather for a location")
    async def weather(self, interaction: discord.Interaction, location: str):
        await interaction.response.defer()
        if not WEATHER_API:
            await interaction.followup.send(embed=build_error_embed("Weather API not configured."))
            return
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={WEATHER_API}&units=metric"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(embed=build_error_embed("Location not found."))
                        return
                    data = await resp.json()
            embed = discord.Embed(title=f"🌤️ Weather in {data['name']}, {data['sys']['country']}",
                                   color=discord.Color.blurple())
            embed.add_field(name="🌡️ Temperature", value=f"{data['main']['temp']:.1f}°C", inline=True)
            embed.add_field(name="💧 Humidity", value=f"{data['main']['humidity']}%", inline=True)
            embed.add_field(name="💨 Wind", value=f"{data['wind']['speed']} m/s", inline=True)
            embed.add_field(name="☁️ Condition", value=data['weather'][0]['description'].title(), inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(embed=build_error_embed(f"Weather error: {e}"))

    @app_commands.command(name="calc", description="Calculate a math expression")
    async def calc(self, interaction: discord.Interaction, expression: str):
        allowed = set("0123456789+-*/().%^ ")
        if not all(c in allowed for c in expression):
            await interaction.response.send_message(embed=build_error_embed("Invalid expression."), ephemeral=True)
            return
        try:
            result = eval(expression.replace("^", "**"))  # noqa: S307
            embed  = discord.Embed(title="🧮 Calculator", color=discord.Color.blurple())
            embed.add_field(name="Expression", value=f"`{expression}`", inline=False)
            embed.add_field(name="Result", value=f"`{result}`", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception:
            await interaction.response.send_message(embed=build_error_embed("Invalid expression."), ephemeral=True)

    @app_commands.command(name="sticky", description="Create a sticky message in a channel")
    @app_commands.default_permissions(manage_messages=True)
    async def sticky(self, interaction: discord.Interaction, message: str,
                      channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        existing = await db_fetchone(
            "SELECT * FROM sticky_messages WHERE channel_id=? AND guild_id=?",
            ch.id, interaction.guild_id,
        )
        if existing:
            await db_execute(
                "UPDATE sticky_messages SET content=?, active=1 WHERE channel_id=? AND guild_id=?",
                message, ch.id, interaction.guild_id,
            )
        else:
            await db_execute(
                "INSERT INTO sticky_messages (guild_id, channel_id, content) VALUES (?,?,?)",
                interaction.guild_id, ch.id, message,
            )
        msg = await ch.send(message)
        await db_execute(
            "UPDATE sticky_messages SET message_id=? WHERE channel_id=? AND guild_id=?",
            msg.id, ch.id, interaction.guild_id,
        )
        await interaction.response.send_message(embed=build_success_embed(f"Sticky message set in {ch.mention}."))

    @app_commands.command(name="unsticky", description="Remove sticky message from a channel")
    @app_commands.default_permissions(manage_messages=True)
    async def unsticky(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        await db_execute(
            "UPDATE sticky_messages SET active=0 WHERE channel_id=? AND guild_id=?",
            ch.id, interaction.guild_id,
        )
        await interaction.response.send_message(embed=build_success_embed(f"Sticky message removed from {ch.mention}."))

    @app_commands.command(name="birthday-set", description="Set your birthday")
    async def birthday_set(self, interaction: discord.Interaction, month: int, day: int):
        if not (1 <= month <= 12 and 1 <= day <= 31):
            await interaction.response.send_message(embed=build_error_embed("Invalid date."), ephemeral=True)
            return
        bday = f"{month:02d}-{day:02d}"
        await db_execute(
            "INSERT OR REPLACE INTO birthdays (user_id, guild_id, birthday) VALUES (?,?,?)",
            interaction.user.id, interaction.guild_id, bday,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Birthday set to {bday}! 🎂"), ephemeral=True
        )

    @app_commands.command(name="timezone-set", description="Set your timezone")
    async def timezone_set(self, interaction: discord.Interaction, timezone: str):
        try:
            pytz.timezone(timezone)
        except Exception:
            await interaction.response.send_message(
                embed=build_error_embed(f"Invalid timezone. Examples: America/New_York, Europe/London, Asia/Tokyo"),
                ephemeral=True,
            )
            return
        await db_execute(
            "UPDATE users SET timezone=? WHERE user_id=? AND guild_id=?",
            timezone, interaction.user.id, interaction.guild_id,
        )
        await interaction.response.send_message(embed=build_success_embed(f"Timezone set to `{timezone}`."), ephemeral=True)

    @app_commands.command(name="time", description="Show current time in different timezones")
    async def time_cmd(self, interaction: discord.Interaction, timezone: str = "UTC"):
        try:
            tz   = pytz.timezone(timezone)
            now  = datetime.datetime.now(tz)
            embed = discord.Embed(title=f"🕐 Time in {timezone}",
                                   description=now.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                   color=discord.Color.blurple())
            await interaction.response.send_message(embed=embed)
        except Exception:
            await interaction.response.send_message(embed=build_error_embed("Invalid timezone."), ephemeral=True)

    @app_commands.command(name="inviteinfo", description="Get information about an invite")
    async def inviteinfo(self, interaction: discord.Interaction, invite_link: str):
        try:
            invite = await self.bot.fetch_invite(invite_link, with_counts=True)
            embed  = discord.Embed(title=f"📨 Invite Info", color=discord.Color.blurple())
            embed.add_field(name="Server", value=invite.guild.name, inline=True)
            embed.add_field(name="Channel", value=invite.channel.name if invite.channel else "N/A", inline=True)
            embed.add_field(name="Inviter", value=str(invite.inviter) if invite.inviter else "Unknown", inline=True)
            embed.add_field(name="Uses", value=str(invite.uses) if invite.uses is not None else "N/A", inline=True)
            embed.add_field(name="Members", value=f"{invite.approximate_member_count:,}", inline=True)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(embed=build_error_embed(f"Invalid invite: {e}"), ephemeral=True)

    @app_commands.command(name="announce", description="Create a server announcement")
    @app_commands.default_permissions(manage_guild=True)
    async def announce(self, interaction: discord.Interaction,
                        title: str, content: str,
                        channel: discord.TextChannel = None,
                        ping_everyone: bool = False):
        ch = channel or interaction.channel
        embed = discord.Embed(
            title=f"📢 {title}",
            description=content,
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(text=f"Announced by {interaction.user}")
        content_str = "@everyone" if ping_everyone else None
        await ch.send(content=content_str, embed=embed)
        await interaction.response.send_message(embed=build_success_embed(f"Announcement posted in {ch.mention}."), ephemeral=True)

    @app_commands.command(name="scheduleannounce", description="Schedule an announcement")
    @app_commands.default_permissions(manage_guild=True)
    async def schedule_announce(self, interaction: discord.Interaction,
                                  title: str, content: str, duration: str,
                                  channel: discord.TextChannel = None):
        secs = parse_duration(duration)
        if not secs:
            await interaction.response.send_message(embed=build_error_embed("Invalid duration."), ephemeral=True)
            return
        ch = channel or interaction.channel
        run_at = int(time.time()) + secs
        await db_execute(
            """INSERT INTO scheduled_tasks (guild_id, task_type, channel_id, data, run_at)
               VALUES (?,?,?,?,?)""",
            interaction.guild_id, "announcement", ch.id,
            json.dumps({"title": title, "content": content}), run_at,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Announcement scheduled for <t:{run_at}:R> in {ch.mention}.")
        )


# ============================================================
# SECTION: AI Staff Assistant
# ============================================================

class AIStaffCog(commands.Cog, name="AIStaff"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="ai-ask", description="Ask the AI assistant a question")
    async def ai_ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        answer = await self.bot.ai.chat(
            interaction.guild, interaction.user, interaction.channel,
            question, "professional",
        )
        embed = discord.Embed(title="🤖 AI Assistant", description=answer, color=discord.Color.blurple())
        embed.set_footer(text=f"Asked by {interaction.user}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ai-announce", description="Generate an AI announcement")
    @app_commands.default_permissions(manage_guild=True)
    async def ai_announce(self, interaction: discord.Interaction, topic: str,
                           tone: str = "official"):
        await interaction.response.defer()
        result = await self.bot.ai.generate_announcement(topic, tone, interaction.guild.name)
        embed = discord.Embed(title="📢 AI-Generated Announcement",
                               description=result, color=discord.Color.blurple())
        view = discord.ui.View()
        post_btn = discord.ui.Button(label="Post Announcement", style=discord.ButtonStyle.success,
                                      custom_id=f"post_announce:{interaction.channel_id}")
        view.add_item(post_btn)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="ai-rules", description="Generate server rules with AI")
    @app_commands.default_permissions(administrator=True)
    async def ai_rules(self, interaction: discord.Interaction, server_type: str = "community"):
        await interaction.response.defer()
        rules = await self.bot.ai.generate_rules(interaction.guild.name, server_type)
        embed = discord.Embed(title="📜 AI-Generated Server Rules",
                               description=rules[:4096], color=discord.Color.blurple())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ai-embed", description="Generate an embed with AI")
    @app_commands.default_permissions(manage_messages=True)
    async def ai_embed(self, interaction: discord.Interaction, purpose: str, details: str = ""):
        await interaction.response.defer()
        content = await self.bot.ai.generate_embed_content(purpose, details)
        try:
            color_hex = content.get("color", "#5865F2").lstrip("#")
            color_int = int(color_hex, 16)
        except Exception:
            color_int = 0x5865F2
        embed = discord.Embed(
            title=content.get("title", ""),
            description=content.get("description", ""),
            color=color_int,
        )
        for field in content.get("fields", [])[:10]:
            embed.add_field(name=field.get("name", ""), value=field.get("value", ""), inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ai-analyze", description="Get an AI analysis of the server")
    @app_commands.default_permissions(administrator=True)
    async def ai_analyze(self, interaction: discord.Interaction):
        await interaction.response.defer()
        g = interaction.guild
        stats = {
            "channels":  len(g.channels),
            "roles":     len(g.roles),
            "bots":      sum(1 for m in g.members if m.bot),
            "activity":  "moderate",
        }
        analysis = await self.bot.ai.analyze_server(g, stats)
        embed = discord.Embed(title=f"🔍 Server Analysis: {g.name}",
                               description=analysis, color=discord.Color.blurple())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ai-faq", description="Generate FAQ entries with AI")
    @app_commands.default_permissions(manage_guild=True)
    async def ai_faq(self, interaction: discord.Interaction, topic: str, context: str = ""):
        await interaction.response.defer()
        faq = await self.bot.ai.generate_faq(topic, context)
        embed = discord.Embed(title=f"❓ AI FAQ: {topic}",
                               description=faq, color=discord.Color.blurple())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ai-report", description="Generate a server report with AI")
    @app_commands.default_permissions(administrator=True)
    async def ai_report(self, interaction: discord.Interaction,
                         report_type: str = "daily"):
        await interaction.response.defer()
        g = interaction.guild
        total_msgs  = await db_fetchone("SELECT SUM(message_count) as t FROM users WHERE guild_id=?", g.id)
        total_warns = await db_fetchone("SELECT COUNT(*) as t FROM warnings WHERE guild_id=? AND active=1", g.id)
        total_tkts  = await db_fetchone("SELECT COUNT(*) as t FROM tickets WHERE guild_id=?", g.id)
        data = {
            "server":   g.name,
            "members":  g.member_count,
            "messages": total_msgs["t"] if total_msgs else 0,
            "warnings": total_warns["t"] if total_warns else 0,
            "tickets":  total_tkts["t"] if total_tkts else 0,
        }
        report = await self.bot.ai.generate_report(f"{report_type} server", data)
        embed  = discord.Embed(title=f"📊 {report_type.title()} Report: {g.name}",
                                description=report[:4096], color=discord.Color.blurple())
        embed.set_footer(text=f"Generated at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ai-personality", description="Set the AI personality")
    @app_commands.default_permissions(manage_guild=True)
    async def ai_personality(self, interaction: discord.Interaction, personality: str):
        valid = list(self.bot.ai.personalities.keys())
        if personality not in valid:
            await interaction.response.send_message(
                embed=build_error_embed(f"Invalid personality. Choose: {', '.join(valid)}"),
                ephemeral=True,
            )
            return
        await db_execute(
            "UPDATE guild_config SET ai_personality=? WHERE guild_id=?",
            personality, interaction.guild_id,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"AI personality set to **{personality}**.")
        )

    @app_commands.command(name="ai-memory-add", description="Add a memory for the AI")
    @app_commands.default_permissions(manage_guild=True)
    async def ai_memory_add(self, interaction: discord.Interaction,
                             key: str, value: str, memory_type: str = "server"):
        await self.bot.ai.save_memory(interaction.guild_id, None, memory_type, key, value, importance=2)
        await interaction.response.send_message(
            embed=build_success_embed(f"Memory saved: `{key}` = `{value}`")
        )

    @app_commands.command(name="ai-translate", description="AI-powered translation")
    async def ai_translate_cmd(self, interaction: discord.Interaction,
                                text: str, language: str):
        await interaction.response.defer()
        result = await self.bot.ai.translate(text, language)
        embed = discord.Embed(title=f"🌐 Translation to {language}", color=discord.Color.blurple())
        embed.add_field(name="Original", value=text[:512], inline=False)
        embed.add_field(name="Translated", value=result[:512], inline=False)
        await interaction.followup.send(embed=embed)


# ============================================================
# SECTION: Backup System
# ============================================================

class BackupCog(commands.Cog, name="Backup"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="backup-create", description="Create a server backup")
    @app_commands.default_permissions(administrator=True)
    async def backup_create(self, interaction: discord.Interaction,
                             name: str = None, backup_type: str = "full"):
        await interaction.response.defer(ephemeral=True)
        g = interaction.guild
        backup_id = generate_id("BCK")
        name = name or f"backup-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M')}"

        data = {
            "guild_id":   g.id,
            "guild_name": g.name,
            "created_at": int(time.time()),
            "type":       backup_type,
            "roles":      [
                {
                    "id":          r.id,
                    "name":        r.name,
                    "color":       r.color.value,
                    "permissions": r.permissions.value,
                    "position":    r.position,
                    "hoist":       r.hoist,
                    "mentionable": r.mentionable,
                }
                for r in g.roles if not r.managed
            ],
            "channels": [
                {
                    "id":       c.id,
                    "name":     c.name,
                    "type":     str(c.type),
                    "category": c.category.name if c.category else None,
                    "position": c.position,
                }
                for c in g.channels
            ],
            "settings": {
                "name":             g.name,
                "description":      g.description,
                "verification_level": str(g.verification_level),
                "default_notifications": str(g.default_notifications),
                "explicit_content_filter": str(g.explicit_content_filter),
            },
        }
        if backup_type in ("full", "config"):
            cfg = await get_guild_config(g.id)
            if cfg:
                data["bot_config"] = dict(cfg)

        data_str  = json.dumps(data)
        data_bytes = len(data_str.encode())

        await db_execute(
            "INSERT INTO backups (guild_id, backup_id, name, type, data, size_bytes, created_by) VALUES (?,?,?,?,?,?,?)",
            g.id, backup_id, name, backup_type, data_str, data_bytes, interaction.user.id,
        )

        # Save to file
        backup_path = f"backups/{backup_id}.json"
        async with aiofiles.open(backup_path, "w", encoding="utf-8") as f:
            await f.write(data_str)

        embed = discord.Embed(title="✅ Backup Created", color=discord.Color.green())
        embed.add_field(name="ID",   value=backup_id, inline=True)
        embed.add_field(name="Name", value=name,      inline=True)
        embed.add_field(name="Type", value=backup_type.title(), inline=True)
        embed.add_field(name="Size", value=f"{data_bytes / 1024:.1f} KB", inline=True)
        embed.add_field(name="Roles",    value=str(len(data["roles"])),    inline=True)
        embed.add_field(name="Channels", value=str(len(data["channels"])), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="backup-list", description="List all server backups")
    @app_commands.default_permissions(administrator=True)
    async def backup_list(self, interaction: discord.Interaction):
        rows = await db_fetch(
            "SELECT backup_id, name, type, size_bytes, created_at FROM backups WHERE guild_id=? ORDER BY created_at DESC LIMIT 10",
            interaction.guild_id,
        )
        embed = discord.Embed(title="💾 Server Backups", color=discord.Color.blurple())
        if not rows:
            embed.description = "No backups found."
        else:
            for r in rows:
                ts = datetime.datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d %H:%M")
                embed.add_field(
                    name=f"`{r['backup_id']}` — {r['name']}",
                    value=f"Type: {r['type']} | Size: {r['size_bytes']/1024:.1f}KB | {ts}",
                    inline=False,
                )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="backup-restore", description="Restore roles from a backup (WARNING: destructive)")
    @app_commands.default_permissions(administrator=True)
    async def backup_restore(self, interaction: discord.Interaction,
                              backup_id: str, restore_type: str = "roles"):
        row = await db_fetchone(
            "SELECT * FROM backups WHERE backup_id=? AND guild_id=?",
            backup_id, interaction.guild_id,
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("Backup not found."), ephemeral=True)
            return
        # Show confirmation
        embed = discord.Embed(
            title="⚠️ CONFIRM RESTORE",
            description=f"This will restore `{restore_type}` from backup `{backup_id}`.\n\n"
                        "**This action may overwrite existing data.**\n\n"
                        "Type `CONFIRM RESTORE` to proceed.",
            color=discord.Color.red(),
        )
        key = f"restore:{interaction.user.id}:{backup_id}"
        self.bot.pending_confirmations[key] = {
            "backup_id": backup_id, "restore_type": restore_type, "expires": time.time() + 60
        }
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="backup-export", description="Export a backup as a file")
    @app_commands.default_permissions(administrator=True)
    async def backup_export(self, interaction: discord.Interaction, backup_id: str):
        row = await db_fetchone(
            "SELECT * FROM backups WHERE backup_id=? AND guild_id=?",
            backup_id, interaction.guild_id,
        )
        if not row:
            await interaction.response.send_message(embed=build_error_embed("Backup not found."), ephemeral=True)
            return
        buf = io.BytesIO(row["data"].encode())
        await interaction.response.send_message(
            file=discord.File(buf, f"{backup_id}.json"),
            ephemeral=True,
        )


# ============================================================
# SECTION: Messaging System
# ============================================================

class MessagingCog(commands.Cog, name="Messaging"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="dm", description="Send a DM to a user")
    @app_commands.default_permissions(manage_guild=True)
    async def dm(self, interaction: discord.Interaction, member: discord.Member, message: str):
        try:
            await member.send(message)
            await interaction.response.send_message(
                embed=build_success_embed(f"DM sent to {member.mention}."), ephemeral=True
            )
            await self.bot._log_event(interaction.guild_id, "dm_sent",
                                       interaction.user.id, member.id,
                                       description=f"DM sent to {member}: {message[:100]}")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=build_error_embed("Cannot DM this user (DMs disabled or blocked)."), ephemeral=True
            )

    @app_commands.command(name="dm-role", description="DM all members with a specific role (requires confirmation)")
    @app_commands.default_permissions(administrator=True)
    async def dm_role(self, interaction: discord.Interaction,
                       role: discord.Role, message: str):
        members = [m for m in role.members if not m.bot]
        embed = discord.Embed(
            title="⚠️ Confirm Mass DM",
            description=f"You are about to DM **{len(members)}** members with the **{role.name}** role.\n\n"
                        f"**Message preview:** {message[:200]}\n\n"
                        "This may take a while. Are you sure?",
            color=discord.Color.orange(),
        )
        view = ConfirmView(self.bot, f"dm_role:{role.id}:{interaction.user.id}",
                           {"message": message, "role_id": role.id, "guild_id": interaction.guild_id})
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="dm-all", description="DM all server members (ADMIN ONLY, requires confirmation)")
    @app_commands.default_permissions(administrator=True)
    async def dm_all(self, interaction: discord.Interaction, message: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(embed=build_error_embed("Requires administrator."), ephemeral=True)
            return
        members = [m for m in interaction.guild.members if not m.bot]
        embed = discord.Embed(
            title="🚨 CONFIRM MASS DM — ALL MEMBERS",
            description=f"You are about to DM **{len(members)}** members.\n\n"
                        f"**Message:** {message[:200]}\n\n"
                        "⚠️ This is a potentially spammy action. Only proceed if necessary.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        # No automatic execution — admin must use a separate confirmed command

    @app_commands.command(name="embed-send", description="Send a custom embed to a channel")
    @app_commands.default_permissions(manage_messages=True)
    async def embed_send(self, interaction: discord.Interaction,
                          channel: discord.TextChannel, title: str,
                          description: str, color: str = "#5865F2"):
        try:
            color_int = int(color.lstrip("#"), 16)
        except Exception:
            color_int = 0x5865F2
        embed = discord.Embed(title=title, description=description, color=color_int)
        embed.set_footer(text=f"Sent by {interaction.user}")
        await channel.send(embed=embed)
        await interaction.response.send_message(
            embed=build_success_embed(f"Embed sent to {channel.mention}."), ephemeral=True
        )


class ConfirmView(discord.ui.View):
    def __init__(self, bot: DiscordBot, action: str, data: Dict):
        super().__init__(timeout=60)
        self.bot = bot
        self.action = action
        self.data = data

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.action.startswith("dm_role:"):
            guild = self.bot.get_guild(self.data["guild_id"])
            role  = guild.get_role(self.data["role_id"])
            if role:
                sent, failed = 0, 0
                for member in role.members:
                    if member.bot:
                        continue
                    try:
                        await member.send(self.data["message"])
                        sent += 1
                        await asyncio.sleep(1)  # Rate limit protection
                    except Exception:
                        failed += 1
                await interaction.followup.send(
                    embed=build_success_embed(f"DM sent to {sent} members. {failed} failed."),
                    ephemeral=True,
                )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_info_embed("Cancelled", "Action cancelled."), ephemeral=True)
        self.stop()


# ============================================================
# SECTION: AI Server Builder
# ============================================================

class AIServerBuilderCog(commands.Cog, name="ServerBuilder"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    TEMPLATES = {
        "gaming":     {"categories": ["📢 Announcements", "💬 General", "🎮 Gaming", "🔊 Voice"], "desc": "Gaming community"},
        "anime":      {"categories": ["📢 Announcements", "💬 General", "🎌 Anime", "🎨 Art", "🔊 Voice"], "desc": "Anime community"},
        "business":   {"categories": ["📢 Announcements", "💼 Business", "📊 Reports", "🤝 Networking", "🔊 Meetings"], "desc": "Business server"},
        "education":  {"categories": ["📢 Announcements", "📚 Courses", "💬 Study Groups", "❓ Help", "🔊 Study Rooms"], "desc": "Education server"},
        "support":    {"categories": ["📢 Announcements", "💬 General", "🎫 Support", "📋 FAQ", "🔊 Help Rooms"], "desc": "Support server"},
        "marketplace":{"categories": ["📢 Announcements", "🛒 Buy", "💰 Sell", "🤝 Trades", "📋 Rules"], "desc": "Marketplace"},
    }

    @app_commands.command(name="server-build", description="AI-powered server builder from a template")
    @app_commands.default_permissions(administrator=True)
    async def server_build(self, interaction: discord.Interaction, template: str):
        template = template.lower()
        if template not in self.TEMPLATES:
            await interaction.response.send_message(
                embed=build_error_embed(f"Invalid template. Choose: {', '.join(self.TEMPLATES.keys())}"),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="⚠️ Confirm Server Build",
            description=f"Building **{self.TEMPLATES[template]['desc']}** template will create:\n"
                        f"• {len(self.TEMPLATES[template]['categories'])} categories\n"
                        "• Multiple channels, roles, and permissions\n\n"
                        "This will NOT delete existing content.",
            color=discord.Color.orange(),
        )
        view = ServerBuildConfirmView(self.bot, template, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="server-templates", description="View available server templates")
    async def server_templates(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🏗️ Server Templates", color=discord.Color.blurple())
        for name, data in self.TEMPLATES.items():
            embed.add_field(
                name=f"**{name.title()}**",
                value=f"{data['desc']}\nCategories: {', '.join(data['categories'][:3])}...",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)


class ServerBuildConfirmView(discord.ui.View):
    def __init__(self, bot: DiscordBot, template: str, guild: discord.Guild):
        super().__init__(timeout=60)
        self.bot = bot
        self.template = template
        self.guild = guild

    @discord.ui.button(label="Build Server", style=discord.ButtonStyle.success)
    async def build_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        tmpl = AIServerBuilderCog.TEMPLATES[self.template]
        created = 0
        for cat_name in tmpl["categories"]:
            try:
                await self.guild.create_category(cat_name)
                created += 1
            except Exception:
                pass
        await interaction.followup.send(
            embed=build_success_embed(f"Created {created} categories for {self.template} template!"),
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_info_embed("Cancelled", "Server build cancelled."), ephemeral=True)
        self.stop()


# ============================================================
# SECTION: Config System
# ============================================================

class ConfigCog(commands.Cog, name="Config"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="config", description="View or update bot configuration")
    @app_commands.default_permissions(administrator=True)
    async def config_view(self, interaction: discord.Interaction):
        cfg = await get_guild_config(interaction.guild_id)
        embed = discord.Embed(title="⚙️ Bot Configuration", color=discord.Color.blurple())
        if cfg:
            log_ch  = self.bot.get_channel(cfg["log_channel"]) if cfg["log_channel"] else None
            mod_ch  = self.bot.get_channel(cfg["mod_log_channel"]) if cfg["mod_log_channel"] else None
            wel_ch  = self.bot.get_channel(cfg["welcome_channel"]) if cfg["welcome_channel"] else None
            tick_cat = interaction.guild.get_channel(cfg["ticket_category"]) if cfg["ticket_category"] else None
            embed.add_field(name="Prefix",         value=cfg["prefix"], inline=True)
            embed.add_field(name="Language",       value=cfg["language"], inline=True)
            embed.add_field(name="Timezone",       value=cfg["timezone"], inline=True)
            embed.add_field(name="Log Channel",    value=log_ch.mention if log_ch else "Not set", inline=True)
            embed.add_field(name="Mod Log",        value=mod_ch.mention if mod_ch else "Not set", inline=True)
            embed.add_field(name="Welcome",        value=wel_ch.mention if wel_ch else "Not set", inline=True)
            embed.add_field(name="AI Enabled",     value="✅" if cfg["ai_enabled"] else "❌", inline=True)
            embed.add_field(name="Leveling",       value="✅" if cfg["level_enabled"] else "❌", inline=True)
            embed.add_field(name="Economy",        value="✅" if cfg["economy_enabled"] else "❌", inline=True)
            embed.add_field(name="Ticket Category",value=tick_cat.name if tick_cat else "Not set", inline=True)
            embed.add_field(name="Max Warnings",   value=str(cfg["max_warnings"]), inline=True)
            embed.add_field(name="Currency",       value=f"{cfg['currency_emoji']} {cfg['currency_name']}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="set-prefix", description="Change the bot prefix")
    @app_commands.default_permissions(administrator=True)
    async def set_prefix(self, interaction: discord.Interaction, prefix: str):
        if len(prefix) > 5:
            await interaction.response.send_message(embed=build_error_embed("Prefix must be 5 characters or less."), ephemeral=True)
            return
        await db_execute(
            "UPDATE guild_config SET prefix=? WHERE guild_id=?", prefix, interaction.guild_id
        )
        await interaction.response.send_message(embed=build_success_embed(f"Prefix changed to `{prefix}`."))

    @app_commands.command(name="set-language", description="Set the server language")
    @app_commands.default_permissions(manage_guild=True)
    async def set_language(self, interaction: discord.Interaction, language: str):
        await db_execute(
            "UPDATE guild_config SET language=? WHERE guild_id=?", language, interaction.guild_id
        )
        await interaction.response.send_message(embed=build_success_embed(f"Language set to `{language}`."))

    @app_commands.command(name="set-currency", description="Customize the economy currency")
    @app_commands.default_permissions(administrator=True)
    async def set_currency(self, interaction: discord.Interaction,
                            name: str = "coins", emoji: str = "🪙"):
        await db_execute(
            "UPDATE guild_config SET currency_name=?, currency_emoji=? WHERE guild_id=?",
            name, emoji, interaction.guild_id,
        )
        await interaction.response.send_message(
            embed=build_success_embed(f"Currency set to {emoji} {name}.")
        )

    @app_commands.command(name="set-ai", description="Toggle AI features on/off")
    @app_commands.default_permissions(administrator=True)
    async def set_ai(self, interaction: discord.Interaction, enabled: bool,
                      always_on: bool = False, channel: discord.TextChannel = None):
        updates = "ai_enabled=?, ai_always_on=?"
        values  = [int(enabled), int(always_on)]
        if channel:
            updates += ", ai_channel=?"
            values.append(channel.id)
        values.append(interaction.guild_id)
        await db_execute(f"UPDATE guild_config SET {updates} WHERE guild_id=?", *values)
        embed = discord.Embed(title="✅ AI Settings Updated", color=discord.Color.green())
        embed.add_field(name="Enabled", value="✅" if enabled else "❌", inline=True)
        embed.add_field(name="Always On", value="✅" if always_on else "❌", inline=True)
        if channel:
            embed.add_field(name="AI Channel", value=channel.mention, inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup-roles", description="Configure moderation roles")
    @app_commands.default_permissions(administrator=True)
    async def setup_roles(self, interaction: discord.Interaction,
                           mute_role: discord.Role = None,
                           jail_role: discord.Role = None,
                           mod_role: discord.Role = None,
                           staff_role: discord.Role = None):
        updates, values = [], []
        if mute_role:
            updates.append("mute_role=?");  values.append(mute_role.id)
        if jail_role:
            updates.append("jail_role=?");  values.append(jail_role.id)
        if mod_role:
            updates.append("mod_role=?");   values.append(mod_role.id)
        if staff_role:
            updates.append("staff_role=?"); values.append(staff_role.id)
        if not updates:
            await interaction.response.send_message(embed=build_error_embed("No roles provided."), ephemeral=True)
            return
        values.append(interaction.guild_id)
        await db_execute(f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id=?", *values)
        await interaction.response.send_message(embed=build_success_embed("Role configuration updated."))

    @app_commands.command(name="help", description="Get help with bot commands")
    async def help_cmd(self, interaction: discord.Interaction, category: str = None):
        categories = {
            "🛡️ Moderation":   ["/warn", "/kick", "/ban", "/tempban", "/timeout", "/mute", "/jail", "/purge", "/lock"],
            "🤖 AI":            ["/ai-ask", "/ai-announce", "/ai-rules", "/ai-embed", "/ai-analyze", "/ai-faq", "/ai-report"],
            "🎫 Tickets":       ["/ticket-panel", "/ticket-close", "/ticket-add", "/ticket-note", "/ticket-summary"],
            "💰 Economy":       ["/balance", "/daily", "/weekly", "/work", "/gamble", "/fish", "/mine", "/shop", "/buy"],
            "⭐ Leveling":      ["/rank", "/top", "/setxp", "/role-reward-add", "/prestige"],
            "🎵 Music":         ["/play", "/skip", "/stop", "/queue", "/volume", "/pause", "/resume"],
            "🎉 Events":        ["/giveaway-start", "/poll", "/suggest"],
            "🔧 Utility":       ["/serverinfo", "/userinfo", "/remind", "/translate", "/weather", "/calc", "/qr"],
            "⚙️ Config":        ["/config", "/set-prefix", "/setup-roles", "/set-ai", "/welcome-config"],
            "🔒 Security":      ["/antiraid", "/lockdown", "/automod"],
            "💾 Backup":        ["/backup-create", "/backup-list", "/backup-restore", "/backup-export"],
        }
        if category:
            found = next((v for k, v in categories.items() if category.lower() in k.lower()), None)
            if found:
                embed = discord.Embed(title=f"Help: {category.title()}", color=discord.Color.blurple())
                embed.description = "\n".join(f"`{cmd}`" for cmd in found)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        embed = discord.Embed(
            title=f"📚 Bot Help — v{BOT_VERSION}",
            description="Advanced AI-Powered Discord Management Bot\n\nSelect a category:",
            color=discord.Color.blurple(),
        )
        for cat, cmds in categories.items():
            embed.add_field(name=cat, value=f"{len(cmds)} commands", inline=True)
        embed.set_footer(text="Use /help <category> for detailed command list")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# SECTION: Scheduler Cog
# ============================================================

class SchedulerCog(commands.Cog, name="Scheduler"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="schedule", description="Schedule a message or task")
    @app_commands.default_permissions(manage_guild=True)
    async def schedule(self, interaction: discord.Interaction,
                        channel: discord.TextChannel, message: str,
                        when: str, repeat: bool = False, repeat_every: str = None):
        secs = parse_duration(when)
        if not secs:
            await interaction.response.send_message(embed=build_error_embed("Invalid duration."), ephemeral=True)
            return
        run_at = int(time.time()) + secs
        repeat_sec = parse_duration(repeat_every) if repeat and repeat_every else 0

        await db_execute(
            """INSERT INTO scheduled_tasks (guild_id, task_type, channel_id, data, run_at, repeat, repeat_sec)
               VALUES (?,?,?,?,?,?,?)""",
            interaction.guild_id, "message", channel.id,
            json.dumps({"content": message}), run_at, int(repeat), repeat_sec or 0,
        )
        msg = f"Message scheduled for <t:{run_at}:R> in {channel.mention}."
        if repeat and repeat_sec:
            msg += f" Repeating every {format_duration(repeat_sec)}."
        await interaction.response.send_message(embed=build_success_embed(msg))


# ============================================================
# SECTION: Global Interaction Handler
# ============================================================

async def _global_interaction_handler(self: DiscordBot, interaction: discord.Interaction):
    if not interaction.data:
        return
    custom_id = interaction.data.get("custom_id", "")
    if not custom_id:
        return

    # ── Poll votes ────────────────────────────────────────────
    if custom_id.startswith("poll:"):
        parts = custom_id.split(":")
        if len(parts) >= 3:
            poll_id = parts[1]
            option_idx = parts[2]
            row = await db_fetchone(
                "SELECT * FROM polls WHERE poll_id=? AND status='active'", poll_id
            )
            if row:
                votes = json.loads(row["votes"] or "{}")
                user_id = str(interaction.user.id)
                if not votes.get(option_idx):
                    votes[option_idx] = []
                if user_id in votes[option_idx]:
                    votes[option_idx].remove(user_id)
                    await interaction.response.send_message("Vote removed.", ephemeral=True)
                else:
                    if not row["multi_vote"]:
                        for k in votes:
                            if user_id in votes[k]:
                                votes[k].remove(user_id)
                    votes[option_idx].append(user_id)
                    options = json.loads(row["options"])
                    opt_name = options[int(option_idx)] if int(option_idx) < len(options) else "option"
                    await interaction.response.send_message(f"Voted for **{opt_name}**!", ephemeral=True)
                await db_execute(
                    "UPDATE polls SET votes=? WHERE poll_id=?",
                    json.dumps(votes), poll_id,
                )

    # ── Suggestion votes ──────────────────────────────────────
    elif custom_id.startswith("sugg_vote:"):
        parts = custom_id.split(":")
        if len(parts) >= 3:
            sugg_id, vote_type = parts[1], parts[2]
            row = await db_fetchone("SELECT * FROM suggestions WHERE suggestion_id=?", sugg_id)
            if row:
                voters = json.loads(row["voters"] or "[]")
                user_id = interaction.user.id
                if user_id in voters:
                    await interaction.response.send_message("Already voted!", ephemeral=True)
                    return
                voters.append(user_id)
                if vote_type == "up":
                    await db_execute(
                        "UPDATE suggestions SET upvotes=upvotes+1, voters=? WHERE suggestion_id=?",
                        json.dumps(voters), sugg_id,
                    )
                    await interaction.response.send_message("👍 Upvoted!", ephemeral=True)
                else:
                    await db_execute(
                        "UPDATE suggestions SET downvotes=downvotes+1, voters=? WHERE suggestion_id=?",
                        json.dumps(voters), sugg_id,
                    )
                    await interaction.response.send_message("👎 Downvoted!", ephemeral=True)

    # ── Giveaway entries ──────────────────────────────────────
    elif custom_id.startswith("give:"):
        giveaway_id = custom_id.split(":")[1]
        row = await db_fetchone(
            "SELECT * FROM giveaways WHERE giveaway_id=? AND status='active'", giveaway_id
        )
        if not row:
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return
        entries = json.loads(row["entries"] or "[]")
        user_id = interaction.user.id
        # Check requirements
        if row["req_role"]:
            role = interaction.guild.get_role(row["req_role"])
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(
                    f"You need the {role.mention} role to enter!", ephemeral=True
                )
                return
        if user_id in entries:
            entries.remove(user_id)
            await db_execute("UPDATE giveaways SET entries=? WHERE giveaway_id=?",
                              json.dumps(entries), giveaway_id)
            await interaction.response.send_message("❌ You left the giveaway.", ephemeral=True)
        else:
            entries.append(user_id)
            await db_execute("UPDATE giveaways SET entries=? WHERE giveaway_id=?",
                              json.dumps(entries), giveaway_id)
            await interaction.response.send_message("🎉 You entered the giveaway!", ephemeral=True)

    # ── Ticket rating ─────────────────────────────────────────
    elif custom_id.startswith("rate:"):
        parts = custom_id.split(":")
        if len(parts) >= 3:
            ticket_id = parts[1]
            rating    = int(parts[2])
            await db_execute(
                "UPDATE tickets SET feedback=? WHERE ticket_id=?", rating, ticket_id
            )
            stars = "⭐" * rating
            await interaction.response.send_message(
                f"Thank you for your rating: {stars}", ephemeral=True
            )


# ============================================================
# SECTION: Main Entry Point
# ============================================================

async def main():
    """Main entry point."""
    if not DISCORD_TOKEN:
        log.critical("DISCORD_TOKEN not set! Please configure it in your .env file.")
        sys.exit(1)

    bot = DiscordBot()

    # Add global interaction handler
    original_on_interaction = bot.on_interaction if hasattr(bot, "on_interaction") else None

    async def combined_interaction(interaction: discord.Interaction):
        await _global_interaction_handler(bot, interaction)
        # Also dispatch to cogs
        for cog in bot.cogs.values():
            if hasattr(cog, "on_interaction"):
                try:
                    await cog.on_interaction(interaction)
                except Exception:
                    pass

    bot.add_listener(combined_interaction, "on_interaction")

    log.info(f"Starting Discord Bot v{BOT_VERSION}...")
    log.info(f"AI Provider: {'Grok (xAI)' if GROK_API_KEY else 'OpenAI' if OPENAI_API_KEY else 'None configured'}")
    log.info(f"Database: {DB_PATH}")

    try:
        async with bot:
            await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        log.critical("Invalid Discord token! Check your DISCORD_TOKEN.")
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
    except Exception as e:
        log.critical(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        import yt_dlp  # noqa: F401 — ensure it's available
    except ImportError:
        log.warning("yt-dlp not installed. Music features unavailable.")

    asyncio.run(main())
