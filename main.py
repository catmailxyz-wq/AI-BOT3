"""
╔══════════════════════════════════════════════════════════════╗
║         ENTERPRISE AI-POWERED DISCORD MANAGEMENT BOT         ║
║                    Commercial SaaS Grade                     ║
║               98 Slash Commands · Full Prefix Support        ║
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

load_dotenv()

DISCORD_TOKEN  = os.getenv("DISCORD_TOKEN", "")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AI_MODEL       = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
DATABASE_URL   = os.getenv("DATABASE_URL", "")
BOT_PREFIX     = os.getenv("BOT_PREFIX", "!")
OWNER_ID       = int(os.getenv("OWNER_ID", "0") or "0")
LOG_LEVEL      = os.getenv("LOG_LEVEL", "INFO")
WEATHER_API    = os.getenv("WEATHER_API_KEY", "")

DB_PATH = "bot_database.db"

Path("backups").mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)
Path("transcripts").mkdir(exist_ok=True)

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

BOT_VERSION    = "3.0.0"
BOT_START_TIME = time.time()


# ============================================================
# SECTION: Database
# ============================================================

async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_database():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

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
        await db_execute("INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", guild_id)
        row = await db_fetchone("SELECT * FROM guild_config WHERE guild_id=?", guild_id)
    return row


async def ensure_user(user_id: int, guild_id: int, username: str = ""):
    await db_execute(
        "INSERT OR IGNORE INTO users (user_id, guild_id, username, last_seen) VALUES (?, ?, ?, ?)",
        user_id, guild_id, username, int(time.time()),
    )


def generate_case_id(guild_id: int) -> str:
    ts = int(time.time() * 1000)
    return f"CASE-{guild_id % 10000:04d}-{ts % 1000000:06d}"


def generate_ticket_id(guild_id: int) -> str:
    ts   = int(time.time() * 1000)
    rand = random.randint(100, 999)
    return f"TKT-{rand}-{ts % 100000:05d}"


def generate_id(prefix: str = "ID") -> str:
    ts   = int(time.time() * 1000)
    rand = random.randint(1000, 9999)
    return f"{prefix}-{ts % 100000:05d}-{rand}"


# ============================================================
# SECTION: Shared Helpers
# ============================================================

def build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(description=f"❌ {message}", color=discord.Color.red())


def build_success_embed(message: str) -> discord.Embed:
    return discord.Embed(description=f"✅ {message}", color=discord.Color.green())


def build_info_embed(title: str, description: str,
                     color: discord.Color = discord.Color.blurple()) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def parse_duration(s: str) -> Optional[int]:
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
    up = user.guild_permissions
    return all(getattr(up, p, False) for p in perms)


# ============================================================
# SECTION: AI System
# ============================================================

class AISystem:
    def __init__(self):
        self.groq_client: Optional[AsyncOpenAI] = None
        self.openai_client: Optional[AsyncOpenAI] = None
        self._init_clients()
        self._cooldowns: Dict[str, float] = {}
        self._usage: Dict[str, int] = defaultdict(int)
        self.personalities = {
            "default":      "You are an advanced, helpful Discord server assistant. You are professional, friendly, and concise.",
            "friendly":     "You are a warm, enthusiastic Discord assistant who loves helping the community. Use casual, friendly language.",
            "professional": "You are a formal, professional server assistant. Be concise, accurate, and business-like.",
            "strict":       "You are a strict, no-nonsense server assistant focused on rules enforcement and order.",
            "fun":          "You are a fun, witty Discord assistant with a great sense of humor. Keep things light and entertaining.",
            "teacher":      "You are a patient, educational assistant who explains things clearly with examples.",
        }

    def _init_clients(self):
        if GROQ_API_KEY:
            self.groq_client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
            log.info("Groq (xAI) AI client initialized.")
        if OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            log.info("OpenAI client initialized (fallback).")
        if not self.groq_client and not self.openai_client:
            log.warning("No AI API keys set. AI features will be limited.")

    async def _call_ai(self, messages: List[Dict], model: str = None,
                       temperature: float = 0.7, max_tokens: int = 1024) -> str:
        model  = model or AI_MODEL
        client = self.groq_client or self.openai_client
        if not client:
            return ""
        try:
            response = await client.chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"Primary AI error: {e}")
            if self.openai_client and client is not self.openai_client:
                try:
                    response = await self.openai_client.chat.completions.create(
                        model="gpt-4o-mini", messages=messages,
                        temperature=temperature, max_tokens=max_tokens,
                    )
                    return response.choices[0].message.content.strip()
                except Exception as e2:
                    log.error(f"Fallback AI error: {e2}")
            return f"AI error: {str(e)}"

    def is_on_cooldown(self, key: str, seconds: int = 5) -> bool:
        now  = time.time()
        last = self._cooldowns.get(key, 0)
        if now - last < seconds:
            return True
        self._cooldowns[key] = now
        return False

    async def get_memory(self, guild_id: int, user_id: int = None, limit: int = 20) -> str:
        if user_id:
            rows = await db_fetch(
                "SELECT memory_type, key, value FROM ai_memory WHERE guild_id=? AND (user_id=? OR user_id IS NULL) AND (expires_at IS NULL OR expires_at > ?) ORDER BY importance DESC, updated_at DESC LIMIT ?",
                guild_id, user_id, int(time.time()), limit,
            )
        else:
            rows = await db_fetch(
                "SELECT memory_type, key, value FROM ai_memory WHERE guild_id=? AND (expires_at IS NULL OR expires_at > ?) ORDER BY importance DESC, updated_at DESC LIMIT ?",
                guild_id, int(time.time()), limit,
            )
        if not rows:
            return ""
        return "\n".join(f"[{r['memory_type']}] {r['key']}: {r['value']}" for r in rows)

    async def save_memory(self, guild_id: int, user_id: Optional[int],
                          memory_type: str, key: str, value: str,
                          importance: int = 1, expires_in: int = None):
        expires_at = int(time.time()) + expires_in if expires_in else None
        await db_execute(
            "INSERT INTO ai_memory (guild_id, user_id, memory_type, key, value, importance, expires_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO UPDATE SET value=excluded.value, importance=excluded.importance, expires_at=excluded.expires_at, updated_at=excluded.updated_at",
            guild_id, user_id, memory_type, key, value, importance, expires_at, int(time.time()),
        )

    async def get_conversation_history(self, guild_id: int, user_id: int,
                                       channel_id: int, limit: int = 10) -> List[Dict]:
        rows = await db_fetch(
            "SELECT role, content FROM ai_conversations WHERE guild_id=? AND user_id=? AND channel_id=? ORDER BY created_at DESC LIMIT ?",
            guild_id, user_id, channel_id, limit,
        )
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    async def save_message(self, guild_id: int, user_id: int, channel_id: int,
                           role: str, content: str):
        await db_execute(
            "INSERT INTO ai_conversations (guild_id, user_id, channel_id, role, content) VALUES (?, ?, ?, ?, ?)",
            guild_id, user_id, channel_id, role, content,
        )
        await db_execute(
            "DELETE FROM ai_conversations WHERE id NOT IN (SELECT id FROM ai_conversations WHERE guild_id=? AND user_id=? AND channel_id=? ORDER BY created_at DESC LIMIT 50) AND guild_id=? AND user_id=? AND channel_id=?",
            guild_id, user_id, channel_id, guild_id, user_id, channel_id,
        )

    async def chat(self, guild: discord.Guild, user: discord.Member,
                   channel: discord.TextChannel, message: str, personality: str = "default") -> str:
        guild_id = guild.id
        user_id  = user.id
        if self.is_on_cooldown(f"chat:{guild_id}:{user_id}", 3):
            return "Please wait a moment before sending another message."
        memory  = await self.get_memory(guild_id, user_id)
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
        if not content.strip():
            return {"flagged": False, "reason": "", "action": "none", "confidence": 0}
        if self.is_on_cooldown(f"mod:{guild_id}", 0.5):
            return {"flagged": False, "reason": "", "action": "none", "confidence": 0}
        prompt = f'Analyze this Discord message for violations. Return JSON only:\n{{"flagged": bool, "reason": "brief reason or empty", "action": "none|warn|delete|timeout|ban", "confidence": 0-100, "categories": []}}\n\nCategories: toxicity, harassment, hate_speech, spam, scam, phishing, nsfw, self_harm, violence\n\nMessage: {content[:500]}'
        try:
            result = await self._call_ai([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=150)
            match  = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            log.debug(f"AI moderation parse error: {e}")
        return {"flagged": False, "reason": "", "action": "none", "confidence": 0}

    async def generate_summary(self, messages: List[str], context: str = "") -> str:
        if not messages:
            return "No messages to summarize."
        joined = "\n".join(messages[:50])
        prompt = f"Summarize these Discord messages concisely in 2-3 sentences{f' (context: {context})' if context else ''}:\n\n{joined}"
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=200)

    async def generate_announcement(self, topic: str, tone: str = "official", guild_name: str = "") -> str:
        prompt = f"Write a Discord server announcement for '{guild_name}' about: {topic}\nTone: {tone}. Format with clear sections. Include an engaging opening. Keep it under 300 words."
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=400)

    async def generate_embed_content(self, purpose: str, details: str = "") -> Dict:
        prompt = f'Create Discord embed content as JSON:\n{{"title": "...", "description": "...", "color": "#hex", "fields": [{{"name": "...", "value": "..."}}]}}\n\nPurpose: {purpose}\nDetails: {details}\nReturn valid JSON only.'
        result = await self._call_ai([{"role": "user", "content": prompt}], temperature=0.5, max_tokens=400)
        try:
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return {"title": purpose, "description": result, "color": "#5865F2", "fields": []}

    async def generate_rules(self, guild_name: str, server_type: str = "community") -> str:
        prompt = f"Generate comprehensive Discord server rules for '{guild_name}' ({server_type} server). Include 10-15 numbered rules covering: behavior, content, spam, bots, legal compliance. Format each rule as: **Rule N: Title** - Description."
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=800)

    async def analyze_server(self, guild: discord.Guild, stats: Dict) -> str:
        prompt = f"Analyze this Discord server and provide 5 actionable improvement recommendations:\n\nServer: {guild.name}\nMembers: {guild.member_count}\nChannels: {stats.get('channels', 0)}\nRoles: {stats.get('roles', 0)}\nBots: {stats.get('bots', 0)}\nBoost level: {guild.premium_tier}\n\nProvide specific, actionable recommendations. Be concise."
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
        valid  = {"feature", "improvement", "event", "rule", "content", "other"}
        word   = result.strip().lower().split()[0] if result.strip() else "other"
        return word if word in valid else "other"

    async def generate_report(self, report_type: str, data: Dict) -> str:
        data_str = json.dumps(data, indent=2)[:1000]
        prompt   = f"Generate a professional {report_type} report for a Discord server based on this data:\n{data_str}\nFormat with sections, use bullet points for metrics."
        return await self._call_ai([{"role": "user", "content": prompt}], max_tokens=600)


ai = AISystem()


# ============================================================
# SECTION: Core Engine
# ============================================================

class RateLimiter:
    def __init__(self):
        self._buckets: Dict[str, deque] = defaultdict(deque)

    def is_rate_limited(self, key: str, limit: int, window: float) -> bool:
        now    = time.time()
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
        self.ai              = ai
        self.rate_limiter    = rate_limiter
        self.voice_clients_map: Dict[int, discord.VoiceClient] = {}
        self.music_queues:     Dict[int, List] = defaultdict(list)
        self.music_current:   Dict[int, Dict] = {}
        self.voice_sessions:  Dict[str, int] = {}
        self.raid_tracker:    Dict[int, deque] = defaultdict(deque)
        self.sticky_cooldowns: Dict[int, float] = {}
        self.pending_confirmations: Dict[str, Dict] = {}

    async def _get_prefix(self, bot, message: discord.Message) -> List[str]:
        if not message.guild:
            return commands.when_mentioned_or(BOT_PREFIX)(bot, message)
        cfg    = await get_guild_config(message.guild.id)
        prefix = cfg["prefix"] if cfg else BOT_PREFIX
        return commands.when_mentioned_or(prefix)(bot, message)

    async def setup_hook(self):
        await init_database()
        for cog in [
            ModerationCog, TicketCog, ReactionRolesCog, WelcomeCog,
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
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.guilds)} servers | /help")
        )
        try:
            synced = await self.tree.sync()
            log.info(f"Synced {len(synced)} application commands.")
        except Exception as e:
            log.error(f"Failed to sync commands: {e}")
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
        await db_execute(
            "UPDATE users SET message_count=message_count+1, last_seen=? WHERE user_id=? AND guild_id=?",
            int(time.time()), user_id, guild_id,
        )
        await self._run_automod(message)
        await self._grant_text_xp(message)
        cfg = await get_guild_config(guild_id)
        if cfg:
            always_on = cfg["ai_always_on"] and cfg["ai_channel"] == message.channel.id
            mentioned  = self.user in message.mentions
            if (always_on or mentioned) and cfg["ai_enabled"]:
                content = message.content.replace(f"<@{self.user.id}>", "").strip()
                if content:
                    async with message.channel.typing():
                        reply = await self.ai.chat(
                            message.guild, message.author, message.channel, content,
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
        if await self._check_spam(message):
            return
        if await self._check_patterns(message):
            return
        content = message.content
        if content and len(content) > 10 and random.random() < 0.15:
            result = await self.ai.moderate_message(content, message.guild.id)
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
                    await message.author.timeout(datetime.timedelta(minutes=5), reason="Suspected phishing/scam link")
                except Exception:
                    pass
                await self._log_event(message.guild.id, "automod_phishing", message.author.id, description=f"Pattern: {pat}")
                return True
        return False

    async def _apply_automod_action(self, message: discord.Message, action: str, reason: str):
        user = message.author
        try:
            await message.delete()
        except Exception:
            pass
        try:
            if action == "warn":
                await self._warn_user_internal(message.guild.id, user.id, self.user.id, reason)
            elif action == "timeout":
                await user.timeout(datetime.timedelta(minutes=10), reason=reason)
            elif action == "kick":
                await user.kick(reason=reason)
            elif action == "ban":
                await user.ban(reason=reason, delete_message_days=1)
        except Exception as e:
            log.debug(f"Automod action error: {e}")
        await self._log_event(message.guild.id, "automod_action", user.id, description=f"Action={action}: {reason}")

    async def _warn_user_internal(self, guild_id: int, user_id: int, mod_id: int, reason: str):
        await db_execute(
            "INSERT INTO warnings (guild_id, user_id, mod_id, reason) VALUES (?,?,?,?)",
            guild_id, user_id, mod_id, reason,
        )
        cfg   = await get_guild_config(guild_id)
        count = await db_fetchone(
            "SELECT COUNT(*) as c FROM warnings WHERE guild_id=? AND user_id=? AND active=1",
            guild_id, user_id,
        )
        if cfg and count and count["c"] >= cfg["max_warnings"]:
            guild  = self.get_guild(guild_id)
            if guild:
                member = guild.get_member(user_id)
                if member:
                    try:
                        await member.timeout(datetime.timedelta(hours=1), reason=f"Reached {count['c']} warnings")
                    except Exception:
                        pass

    async def _grant_text_xp(self, message: discord.Message):
        guild_id = message.guild.id
        user_id  = message.author.id
        cfg = await get_guild_config(guild_id)
        if not cfg or not cfg["level_enabled"]:
            return
        row = await db_fetchone("SELECT * FROM levels WHERE user_id=? AND guild_id=?", user_id, guild_id)
        now = int(time.time())
        if row and row["last_message"] and now - row["last_message"] < 60:
            return
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
            await db_execute("UPDATE levels SET xp_boost=1.0 WHERE user_id=? AND guild_id=?", user_id, guild_id)
        new_xp    = row["xp"] + int(xp_gain * boost)
        new_level = self._calc_level(new_xp)
        leveled_up = new_level > row["level"]
        await db_execute(
            "UPDATE levels SET xp=?, level=?, text_xp=text_xp+?, last_message=?, updated_at=? WHERE user_id=? AND guild_id=?",
            new_xp, new_level, xp_gain, now, now, user_id, guild_id,
        )
        if leveled_up:
            await self._handle_level_up(message, new_level)

    def _calc_level(self, xp: int) -> int:
        if xp <= 0:
            return 0
        return int((-1 + math.sqrt(1 + 8 * xp / 100)) / 2)

    def _xp_for_level(self, level: int) -> int:
        return int(level * (level + 1) / 2 * 100)

    async def _handle_level_up(self, message: discord.Message, new_level: int):
        guild_id = message.guild.id
        user_id  = message.author.id
        cfg = await get_guild_config(guild_id)
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
        rewards = await db_fetch(
            "SELECT * FROM role_rewards WHERE guild_id=? AND level<=? ORDER BY level DESC", guild_id, new_level
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

    async def _log_event(self, guild_id: int, event_type: str, user_id: int = None,
                         target_id: int = None, channel_id: int = None,
                         description: str = "", extra: dict = None):
        await db_execute(
            "INSERT INTO logs (guild_id, event_type, user_id, target_id, channel_id, description, extra_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            guild_id, event_type, user_id, target_id, channel_id, description, json.dumps(extra or {}),
        )
        cfg = await get_guild_config(guild_id)
        if not cfg:
            return
        ch_id   = cfg["mod_log_channel"] if "mod" in event_type else cfg["log_channel"]
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
            color=color, timestamp=datetime.datetime.utcnow(),
        )
        if user_id:
            embed.set_footer(text=f"User ID: {user_id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    # ── Background tasks ──────────────────────────────────────

    @tasks.loop(seconds=30)
    async def check_tasks(self):
        now  = int(time.time())
        rows = await db_fetch("SELECT * FROM scheduled_tasks WHERE active=1 AND run_at<=?", now)
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
                await db_execute("UPDATE scheduled_tasks SET active=0, last_run=? WHERE id=?", now, task["id"])

    async def _run_scheduled_task(self, task):
        data    = json.loads(task["data"] or "{}")
        ch_id   = task["channel_id"]
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
        now  = int(time.time())
        rows = await db_fetch("SELECT * FROM giveaways WHERE status='active' AND ends_at<=?", now)
        for g in rows:
            await self._end_giveaway(g)

    async def _end_giveaway(self, g):
        entries = json.loads(g["entries"] or "[]")
        if not entries:
            winners_str = "No winners (no entries)"
        else:
            count   = min(g["winners_count"], len(entries))
            winners = random.sample(entries, count)
            winners_str = " ".join(f"<@{w}>" for w in winners)
            await db_execute("UPDATE giveaways SET winners=?, status='ended' WHERE giveaway_id=?",
                             json.dumps(winners), g["giveaway_id"])
        channel = self.get_channel(g["channel_id"])
        if channel:
            try:
                embed = discord.Embed(
                    title=f"🎉 Giveaway Ended: {g['prize']}",
                    description=f"**Winners:** {winners_str}",
                    color=discord.Color.gold(),
                )
                await channel.send(embed=embed)
            except Exception:
                pass
        await db_execute("UPDATE giveaways SET status='ended' WHERE giveaway_id=?", g["giveaway_id"])

    @tasks.loop(minutes=1)
    async def check_polls(self):
        now  = int(time.time())
        rows = await db_fetch("SELECT * FROM polls WHERE status='active' AND ends_at IS NOT NULL AND ends_at<=?", now)
        for p in rows:
            await db_execute("UPDATE polls SET status='ended' WHERE poll_id=?", p["poll_id"])
            channel = self.get_channel(p["channel_id"])
            if channel:
                try:
                    options = json.loads(p["options"])
                    votes   = json.loads(p["votes"])
                    total   = sum(len(v) for v in votes.values())
                    embed   = discord.Embed(title=f"📊 Poll Ended: {p['question']}", color=discord.Color.blurple())
                    for i, opt in enumerate(options):
                        count = len(votes.get(str(i), []))
                        pct   = (count / total * 100) if total > 0 else 0
                        embed.add_field(name=opt, value=f"{count} votes ({pct:.1f}%)", inline=False)
                    await channel.send(embed=embed)
                except Exception:
                    pass

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now  = int(time.time())
        rows = await db_fetch("SELECT * FROM reminders WHERE active=1 AND remind_at<=?", now)
        for r in rows:
            channel = self.get_channel(r["channel_id"])
            if channel:
                try:
                    user = channel.guild.get_member(r["user_id"])
                    mention = user.mention if user else f"<@{r['user_id']}>"
                    embed   = discord.Embed(
                        title="⏰ Reminder!",
                        description=f"{mention}: {r['message']}",
                        color=discord.Color.blurple(),
                    )
                    await channel.send(embed=embed)
                except Exception:
                    pass
            if r["repeat"] and r["repeat_sec"]:
                await db_execute("UPDATE reminders SET remind_at=? WHERE id=?", now + r["repeat_sec"], r["id"])
            else:
                await db_execute("UPDATE reminders SET active=0 WHERE id=?", r["id"])

    @tasks.loop(minutes=5)
    async def check_temp_bans(self):
        now  = int(time.time())
        rows = await db_fetch(
            "SELECT * FROM moderation_cases WHERE action='tempban' AND active=1 AND expires_at IS NOT NULL AND expires_at<=?",
            now,
        )
        for r in rows:
            guild = self.get_guild(r["guild_id"])
            if guild:
                try:
                    await guild.unban(discord.Object(id=r["user_id"]), reason="Temp ban expired")
                    await db_execute("UPDATE moderation_cases SET active=0 WHERE case_id=?", r["case_id"])
                except Exception:
                    pass

    @tasks.loop(seconds=5)
    async def check_sticky(self):
        pass  # Sticky is handled in on_message

    @tasks.loop(hours=1)
    async def check_birthdays(self):
        now_utc = datetime.datetime.utcnow()
        today_m = now_utc.month
        today_d = now_utc.day
        rows    = await db_fetch("SELECT * FROM birthdays WHERE notified=0")
        for b in rows:
            try:
                m, d = map(int, b["birthday"].split("-"))
                if m == today_m and d == today_d:
                    guild = self.get_guild(b["guild_id"])
                    if guild:
                        cfg = await get_guild_config(b["guild_id"])
                        ch  = self.get_channel(cfg["welcome_channel"]) if cfg else None
                        if ch:
                            user = guild.get_member(b["user_id"])
                            if user:
                                await ch.send(f"🎂 Happy Birthday {user.mention}! 🥳")
                                await db_execute("UPDATE birthdays SET notified=1 WHERE id=?", b["id"])
            except Exception:
                pass
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


# ============================================================
# SECTION: Moderation Cog  (21 slash commands)
# ============================================================

class ModerationCog(commands.Cog, name="Moderation"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    def _target_safe(self, actor: discord.Member, target: discord.Member) -> bool:
        if actor.guild.owner == target:
            return False
        if target.top_role >= actor.top_role and actor.guild.owner != actor:
            return False
        return True

    # ── /warn ────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason", severity="Severity 1-3")
    @app_commands.default_permissions(moderate_members=True)
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member,
                         reason: str = "No reason provided", severity: int = 1):
        embed = await self._warn_impl(interaction.guild, member, interaction.user, reason, severity)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="warn", help="Warn a member. Usage: warn <member> [reason]")
    @commands.has_permissions(moderate_members=True)
    async def warn_prefix(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        embed = await self._warn_impl(ctx.guild, member, ctx.author, reason, 1)
        await ctx.send(embed=embed)

    async def _warn_impl(self, guild, member, mod, reason, severity):
        severity = max(1, min(3, severity))
        if not self._target_safe(mod, member):
            return build_error_embed("Cannot warn this user.")
        await db_execute(
            "INSERT INTO warnings (guild_id, user_id, mod_id, reason, severity) VALUES (?,?,?,?,?)",
            guild.id, member.id, mod.id, reason, severity,
        )
        count_row = await db_fetchone(
            "SELECT COUNT(*) as c FROM warnings WHERE guild_id=? AND user_id=? AND active=1",
            guild.id, member.id,
        )
        count = count_row["c"] if count_row else 1
        case_id = generate_case_id(guild.id)
        await db_execute(
            "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason) VALUES (?,?,?,?,?,?)",
            case_id, guild.id, member.id, mod.id, "warn", reason,
        )
        embed = discord.Embed(title="⚠️ Warning Issued", color=discord.Color.yellow())
        embed.add_field(name="User",     value=member.mention, inline=True)
        embed.add_field(name="Mod",      value=mod.mention,    inline=True)
        embed.add_field(name="Reason",   value=reason,         inline=False)
        embed.add_field(name="Severity", value="⭐" * severity, inline=True)
        embed.add_field(name="Total",    value=str(count),     inline=True)
        try:
            dm_embed = discord.Embed(title=f"⚠️ You were warned in {guild.name}", description=f"**Reason:** {reason}", color=discord.Color.yellow())
            dm_embed.add_field(name="Total Warnings", value=str(count))
            await member.send(embed=dm_embed)
        except Exception:
            pass
        await self.bot._log_event(guild.id, "mod_warn", mod.id, member.id, description=f"Warned {member} | Reason: {reason}")
        return embed

    # ── /warnings ────────────────────────────────────────────
    @app_commands.command(name="warnings", description="View or clear a user's warnings")
    @app_commands.describe(member="Target member", clear="Clear all warnings instead of viewing")
    @app_commands.default_permissions(moderate_members=True)
    async def warnings_slash(self, interaction: discord.Interaction, member: discord.Member,
                              clear: bool = False):
        embed = await self._warnings_impl(interaction.guild, member, interaction.user, clear)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="warnings", help="View a user's warnings. Add 'clear' to clear them.")
    @commands.has_permissions(moderate_members=True)
    async def warnings_prefix(self, ctx, member: discord.Member, action: str = "view"):
        clear = action.lower() == "clear"
        embed = await self._warnings_impl(ctx.guild, member, ctx.author, clear)
        await ctx.send(embed=embed)

    async def _warnings_impl(self, guild, member, mod, clear: bool):
        if clear:
            if not perm_check(mod, "administrator"):
                return build_error_embed("Clearing warnings requires Administrator.")
            await db_execute("UPDATE warnings SET active=0 WHERE guild_id=? AND user_id=?", guild.id, member.id)
            return build_success_embed(f"Cleared all warnings for {member.mention}.")
        rows = await db_fetch(
            "SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY created_at DESC LIMIT 20",
            guild.id, member.id,
        )
        embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=discord.Color.yellow())
        if not rows:
            embed.description = "No warnings found."
        else:
            for i, w in enumerate(rows, 1):
                mod_obj = guild.get_member(w["mod_id"])
                ts      = datetime.datetime.fromtimestamp(w["created_at"]).strftime("%Y-%m-%d")
                active  = "✅" if w["active"] else "❌"
                embed.add_field(
                    name=f"#{i} — {active} {'⭐' * w['severity']} — {ts}",
                    value=f"**Reason:** {w['reason']}\n**By:** {mod_obj.mention if mod_obj else w['mod_id']}",
                    inline=False,
                )
        return embed

    # ── /kick ─────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.default_permissions(kick_members=True)
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member,
                         reason: str = "No reason provided"):
        await interaction.response.defer()
        embed = await self._kick_impl(interaction.guild, member, interaction.user, reason)
        await interaction.followup.send(embed=embed)

    @commands.command(name="kick", help="Kick a member. Usage: kick <member> [reason]")
    @commands.has_permissions(kick_members=True)
    async def kick_prefix(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        embed = await self._kick_impl(ctx.guild, member, ctx.author, reason)
        await ctx.send(embed=embed)

    async def _kick_impl(self, guild, member, mod, reason):
        if not self._target_safe(mod, member):
            return build_error_embed("Cannot kick this user.")
        try:
            await member.send(f"You were kicked from **{guild.name}**.\n**Reason:** {reason}")
        except Exception:
            pass
        await member.kick(reason=reason)
        case_id = generate_case_id(guild.id)
        await db_execute(
            "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason) VALUES (?,?,?,?,?,?)",
            case_id, guild.id, member.id, mod.id, "kick", reason,
        )
        await self.bot._log_event(guild.id, "mod_kick", mod.id, member.id, description=f"Kicked {member} | {reason}")
        embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.orange())
        embed.add_field(name="User",    value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="Reason",  value=reason, inline=False)
        embed.add_field(name="Case ID", value=case_id, inline=True)
        return embed

    # ── /ban  (includes softban via soft=True) ────────────────
    @app_commands.command(name="ban", description="Ban a member. Use soft=True for softban (cleans messages, no permanent ban)")
    @app_commands.default_permissions(ban_members=True)
    async def ban_slash(self, interaction: discord.Interaction, member: discord.Member,
                        reason: str = "No reason provided", delete_days: int = 1, soft: bool = False):
        await interaction.response.defer()
        embed = await self._ban_impl(interaction.guild, member, interaction.user, reason, delete_days, soft)
        await interaction.followup.send(embed=embed)

    @commands.command(name="ban", help="Ban a member. Usage: ban <member> [reason]")
    @commands.has_permissions(ban_members=True)
    async def ban_prefix(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        embed = await self._ban_impl(ctx.guild, member, ctx.author, reason, 1, False)
        await ctx.send(embed=embed)

    @commands.command(name="softban", help="Softban a member (ban+unban to delete messages). Usage: softban <member> [reason]")
    @commands.has_permissions(ban_members=True)
    async def softban_prefix(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        embed = await self._ban_impl(ctx.guild, member, ctx.author, reason, 7, True)
        await ctx.send(embed=embed)

    async def _ban_impl(self, guild, member, mod, reason, delete_days, soft):
        if not self._target_safe(mod, member):
            return build_error_embed("Cannot ban this user.")
        delete_days = max(0, min(7, delete_days))
        try:
            action_str = "softbanned" if soft else "banned"
            await member.send(f"You were {action_str} from **{guild.name}**.\n**Reason:** {reason}")
        except Exception:
            pass
        if soft:
            await member.ban(reason=f"Softban: {reason}", delete_message_days=7)
            await asyncio.sleep(1)
            await guild.unban(discord.Object(id=member.id), reason="Softban completed")
            embed = discord.Embed(title="🧹 Softban Applied",
                                  description=f"{member.mention}'s recent messages were deleted and they were removed.",
                                  color=discord.Color.orange())
            embed.add_field(name="Reason", value=reason)
            return embed
        else:
            await member.ban(reason=reason, delete_message_days=delete_days)
            case_id = generate_case_id(guild.id)
            await db_execute(
                "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason) VALUES (?,?,?,?,?,?)",
                case_id, guild.id, member.id, mod.id, "ban", reason,
            )
            await self.bot._log_event(guild.id, "mod_ban", mod.id, member.id, description=f"Banned {member} | {reason}")
            embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red())
            embed.add_field(name="User",    value=f"{member} (`{member.id}`)", inline=True)
            embed.add_field(name="Reason",  value=reason, inline=False)
            embed.add_field(name="Case ID", value=case_id, inline=True)
            return embed

    # ── /tempban ──────────────────────────────────────────────
    @app_commands.command(name="tempban", description="Temporarily ban a member")
    @app_commands.default_permissions(ban_members=True)
    async def tempban_slash(self, interaction: discord.Interaction, member: discord.Member,
                            duration: str = "1d", reason: str = "No reason provided"):
        await interaction.response.defer()
        embed = await self._tempban_impl(interaction.guild, member, interaction.user, duration, reason)
        await interaction.followup.send(embed=embed)

    @commands.command(name="tempban", help="Temp-ban a member. Usage: tempban <member> <duration> [reason]")
    @commands.has_permissions(ban_members=True)
    async def tempban_prefix(self, ctx, member: discord.Member, duration: str = "1d", *, reason: str = "No reason provided"):
        embed = await self._tempban_impl(ctx.guild, member, ctx.author, duration, reason)
        await ctx.send(embed=embed)

    async def _tempban_impl(self, guild, member, mod, duration, reason):
        secs = parse_duration(duration)
        if not secs:
            return build_error_embed("Invalid duration. Use: 1d, 2h, 30m")
        if not self._target_safe(mod, member):
            return build_error_embed("Cannot ban this user.")
        expires = int(time.time()) + secs
        try:
            await member.send(f"You were temporarily banned from **{guild.name}** for {format_duration(secs)}.\n**Reason:** {reason}")
        except Exception:
            pass
        await member.ban(reason=reason, delete_message_days=0)
        case_id = generate_case_id(guild.id)
        await db_execute(
            "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason, duration, expires_at) VALUES (?,?,?,?,?,?,?,?)",
            case_id, guild.id, member.id, mod.id, "tempban", reason, secs, expires,
        )
        embed = discord.Embed(title="⏱️ Temporary Ban", color=discord.Color.red())
        embed.add_field(name="User",     value=str(member),          inline=True)
        embed.add_field(name="Duration", value=format_duration(secs), inline=True)
        embed.add_field(name="Reason",   value=reason,               inline=False)
        embed.add_field(name="Expires",  value=f"<t:{expires}:R>",   inline=True)
        return embed

    # ── /unban ────────────────────────────────────────────────
    @app_commands.command(name="unban", description="Unban a user by ID")
    @app_commands.default_permissions(ban_members=True)
    async def unban_slash(self, interaction: discord.Interaction, user_id: str,
                          reason: str = "No reason provided"):
        embed = await self._unban_impl(interaction.guild, user_id, interaction.user, reason)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="unban", help="Unban a user by ID. Usage: unban <user_id> [reason]")
    @commands.has_permissions(ban_members=True)
    async def unban_prefix(self, ctx, user_id: str, *, reason: str = "No reason provided"):
        embed = await self._unban_impl(ctx.guild, user_id, ctx.author, reason)
        await ctx.send(embed=embed)

    async def _unban_impl(self, guild, user_id_str, mod, reason):
        try:
            uid = int(user_id_str)
            await guild.unban(discord.Object(id=uid), reason=reason)
            await db_execute(
                "UPDATE moderation_cases SET active=0 WHERE guild_id=? AND user_id=? AND action IN ('ban','tempban')",
                guild.id, uid,
            )
            await self.bot._log_event(guild.id, "mod_unban", mod.id, uid, description=f"Unbanned {uid}")
            return build_success_embed(f"Unbanned user `{uid}`. Reason: {reason}")
        except Exception as e:
            return build_error_embed(f"Failed: {e}")

    # ── /timeout  (includes untimeout via remove=True) ────────
    @app_commands.command(name="timeout", description="Timeout a member. Use remove=True to remove timeout.")
    @app_commands.default_permissions(moderate_members=True)
    async def timeout_slash(self, interaction: discord.Interaction, member: discord.Member,
                            duration: str = "10m", reason: str = "No reason provided",
                            remove: bool = False):
        embed = await self._timeout_impl(interaction.guild, member, interaction.user, duration, reason, remove)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="timeout", help="Timeout a member. Usage: timeout <member> [duration] [reason]")
    @commands.has_permissions(moderate_members=True)
    async def timeout_prefix(self, ctx, member: discord.Member, duration: str = "10m", *, reason: str = "No reason provided"):
        embed = await self._timeout_impl(ctx.guild, member, ctx.author, duration, reason, False)
        await ctx.send(embed=embed)

    @commands.command(name="untimeout", help="Remove timeout from a member. Usage: untimeout <member>")
    @commands.has_permissions(moderate_members=True)
    async def untimeout_prefix(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        embed = await self._timeout_impl(ctx.guild, member, ctx.author, "0", reason, True)
        await ctx.send(embed=embed)

    async def _timeout_impl(self, guild, member, mod, duration, reason, remove):
        if not self._target_safe(mod, member):
            return build_error_embed("Cannot timeout this user.")
        if remove:
            await member.timeout(None, reason=reason)
            return build_success_embed(f"Removed timeout from {member.mention}.")
        secs = parse_duration(duration)
        if not secs:
            return build_error_embed("Invalid duration.")
        delta = datetime.timedelta(seconds=min(secs, 2419200))
        await member.timeout(delta, reason=reason)
        case_id = generate_case_id(guild.id)
        await db_execute(
            "INSERT INTO moderation_cases (case_id, guild_id, user_id, mod_id, action, reason, duration) VALUES (?,?,?,?,?,?,?)",
            case_id, guild.id, member.id, mod.id, "timeout", reason, secs,
        )
        embed = discord.Embed(title="⏸️ Member Timed Out", color=discord.Color.orange())
        embed.add_field(name="User",     value=member.mention,      inline=True)
        embed.add_field(name="Duration", value=format_duration(secs), inline=True)
        embed.add_field(name="Reason",   value=reason,              inline=False)
        return embed

    # ── /mute  (includes unmute via unmute=True) ──────────────
    @app_commands.command(name="mute", description="Mute a member using the mute role. Use unmute=True to unmute.")
    @app_commands.default_permissions(moderate_members=True)
    async def mute_slash(self, interaction: discord.Interaction, member: discord.Member,
                         reason: str = "No reason provided", unmute: bool = False):
        embed = await self._mute_impl(interaction.guild, member, interaction.user, reason, unmute)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="mute", help="Mute a member. Usage: mute <member> [reason]")
    @commands.has_permissions(moderate_members=True)
    async def mute_prefix(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        embed = await self._mute_impl(ctx.guild, member, ctx.author, reason, False)
        await ctx.send(embed=embed)

    @commands.command(name="unmute", help="Unmute a member. Usage: unmute <member>")
    @commands.has_permissions(moderate_members=True)
    async def unmute_prefix(self, ctx, member: discord.Member):
        embed = await self._mute_impl(ctx.guild, member, ctx.author, "Unmuted", True)
        await ctx.send(embed=embed)

    async def _mute_impl(self, guild, member, mod, reason, do_unmute):
        cfg = await get_guild_config(guild.id)
        mute_role_id = cfg["mute_role"] if cfg else None
        if not mute_role_id:
            return build_error_embed("No mute role configured. Use `/config` or `setup-roles`.")
        role = guild.get_role(mute_role_id)
        if not role:
            return build_error_embed("Mute role not found.")
        if do_unmute:
            if role in member.roles:
                await member.remove_roles(role, reason="Unmuted")
            return build_success_embed(f"Unmuted {member.mention}.")
        await member.add_roles(role, reason=reason)
        return build_success_embed(f"Muted {member.mention}. Reason: {reason}")

    # ── /jail  (includes unjail via release=True) ─────────────
    @app_commands.command(name="jail", description="Jail a member. Use release=True to release them.")
    @app_commands.default_permissions(moderate_members=True)
    async def jail_slash(self, interaction: discord.Interaction, member: discord.Member,
                         reason: str = "No reason provided", release: bool = False):
        embed = await self._jail_impl(interaction.guild, member, interaction.user, reason, release)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="jail", help="Jail a member. Usage: jail <member> [reason]")
    @commands.has_permissions(moderate_members=True)
    async def jail_prefix(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        embed = await self._jail_impl(ctx.guild, member, ctx.author, reason, False)
        await ctx.send(embed=embed)

    @commands.command(name="unjail", help="Release a member from jail. Usage: unjail <member>")
    @commands.has_permissions(moderate_members=True)
    async def unjail_prefix(self, ctx, member: discord.Member):
        embed = await self._jail_impl(ctx.guild, member, ctx.author, "Released", True)
        await ctx.send(embed=embed)

    async def _jail_impl(self, guild, member, mod, reason, do_release):
        cfg = await get_guild_config(guild.id)
        jail_role_id = cfg["jail_role"] if cfg else None
        if not jail_role_id:
            return build_error_embed("No jail role configured. Use `/setup-roles`.")
        role = guild.get_role(jail_role_id)
        if not role:
            return build_error_embed("Jail role not found.")
        if do_release:
            if role in member.roles:
                await member.remove_roles(role, reason="Released from jail")
            return build_success_embed(f"Released {member.mention} from jail.")
        await member.add_roles(role, reason=reason)
        embed = discord.Embed(title="🔒 Member Jailed",
                              description=f"{member.mention} has been jailed.\n**Reason:** {reason}",
                              color=discord.Color.dark_red())
        return embed

    # ── /purge ────────────────────────────────────────────────
    @app_commands.command(name="purge", description="Delete messages in bulk (1-200)")
    @app_commands.default_permissions(manage_messages=True)
    async def purge_slash(self, interaction: discord.Interaction, amount: int,
                          member: discord.Member = None):
        if amount < 1 or amount > 200:
            await interaction.response.send_message(embed=build_error_embed("Amount must be 1-200."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        check   = (lambda m: m.author == member) if member else None
        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(embed=build_success_embed(f"Deleted {len(deleted)} messages."), ephemeral=True)
        await self.bot._log_event(interaction.guild_id, "mod_purge", interaction.user.id,
                                  channel_id=interaction.channel_id, description=f"Purged {len(deleted)} messages")

    @commands.command(name="purge", aliases=["clear"], help="Delete messages. Usage: purge <amount> [@member]")
    @commands.has_permissions(manage_messages=True)
    async def purge_prefix(self, ctx, amount: int, member: discord.Member = None):
        if amount < 1 or amount > 200:
            await ctx.send(embed=build_error_embed("Amount must be 1-200."))
            return
        await ctx.message.delete()
        check   = (lambda m: m.author == member) if member else None
        deleted = await ctx.channel.purge(limit=amount, check=check)
        msg     = await ctx.send(embed=build_success_embed(f"Deleted {len(deleted)} messages."))
        await asyncio.sleep(3)
        try:
            await msg.delete()
        except Exception:
            pass

    # ── /lock  (includes unlock via unlock=True) ──────────────
    @app_commands.command(name="lock", description="Lock a channel. Use unlock=True to unlock.")
    @app_commands.default_permissions(manage_channels=True)
    async def lock_slash(self, interaction: discord.Interaction,
                         channel: discord.TextChannel = None,
                         reason: str = "No reason provided", unlock: bool = False):
        ch    = channel or interaction.channel
        embed = await self._lock_impl(interaction.guild, ch, interaction.user, reason, unlock)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="lock", help="Lock a channel. Usage: lock [#channel] [reason]")
    @commands.has_permissions(manage_channels=True)
    async def lock_prefix(self, ctx, channel: discord.TextChannel = None, *, reason: str = "No reason provided"):
        ch    = channel or ctx.channel
        embed = await self._lock_impl(ctx.guild, ch, ctx.author, reason, False)
        await ctx.send(embed=embed)

    @commands.command(name="unlock", help="Unlock a channel. Usage: unlock [#channel]")
    @commands.has_permissions(manage_channels=True)
    async def unlock_prefix(self, ctx, channel: discord.TextChannel = None, *, reason: str = "Unlocked"):
        ch    = channel or ctx.channel
        embed = await self._lock_impl(ctx.guild, ch, ctx.author, reason, True)
        await ctx.send(embed=embed)

    async def _lock_impl(self, guild, ch, mod, reason, do_unlock):
        if do_unlock:
            await ch.set_permissions(guild.default_role, send_messages=None, reason=reason)
            return discord.Embed(title="🔓 Channel Unlocked", description=f"{ch.mention} has been unlocked.", color=discord.Color.green())
        await ch.set_permissions(guild.default_role, send_messages=False, reason=reason)
        return discord.Embed(title="🔒 Channel Locked", description=f"{ch.mention} has been locked.\n**Reason:** {reason}", color=discord.Color.red())

    # ── /slowmode ─────────────────────────────────────────────
    @app_commands.command(name="slowmode", description="Set channel slowmode (0 to disable)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode_slash(self, interaction: discord.Interaction, seconds: int = 0,
                             channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        seconds = max(0, min(21600, seconds))
        await ch.edit(slowmode_delay=seconds)
        msg = f"Slowmode disabled in {ch.mention}." if seconds == 0 else f"Slowmode set to {seconds}s in {ch.mention}."
        await interaction.response.send_message(embed=build_success_embed(msg))

    @commands.command(name="slowmode", help="Set slowmode. Usage: slowmode <seconds> [#channel]")
    @commands.has_permissions(manage_channels=True)
    async def slowmode_prefix(self, ctx, seconds: int = 0, channel: discord.TextChannel = None):
        ch = channel or ctx.channel
        seconds = max(0, min(21600, seconds))
        await ch.edit(slowmode_delay=seconds)
        msg = f"Slowmode disabled in {ch.mention}." if seconds == 0 else f"Slowmode set to {seconds}s in {ch.mention}."
        await ctx.send(embed=build_success_embed(msg))

    # ── /nick ─────────────────────────────────────────────────
    @app_commands.command(name="nick", description="Change or reset a member's nickname")
    @app_commands.default_permissions(manage_nicknames=True)
    async def nick_slash(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None):
        old = member.nick or member.name
        await member.edit(nick=nickname)
        msg = f"Changed {member.mention}'s nickname from `{old}` to `{nickname}`." if nickname else f"Reset {member.mention}'s nickname."
        await interaction.response.send_message(embed=build_success_embed(msg))

    @commands.command(name="nick", help="Change nickname. Usage: nick <member> [new nickname]")
    @commands.has_permissions(manage_nicknames=True)
    async def nick_prefix(self, ctx, member: discord.Member, *, nickname: str = None):
        old = member.nick or member.name
        await member.edit(nick=nickname)
        msg = f"Changed {member.mention}'s nickname from `{old}` to `{nickname}`." if nickname else f"Reset {member.mention}'s nickname."
        await ctx.send(embed=build_success_embed(msg))

    # ── /case ─────────────────────────────────────────────────
    @app_commands.command(name="case", description="View a moderation case by ID")
    @app_commands.default_permissions(moderate_members=True)
    async def case_slash(self, interaction: discord.Interaction, case_id: str):
        embed = await self._case_impl(interaction.guild, case_id)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="case", help="View a case. Usage: case <CASE-ID>")
    @commands.has_permissions(moderate_members=True)
    async def case_prefix(self, ctx, case_id: str):
        embed = await self._case_impl(ctx.guild, case_id)
        await ctx.send(embed=embed)

    async def _case_impl(self, guild, case_id):
        row = await db_fetchone("SELECT * FROM moderation_cases WHERE case_id=? AND guild_id=?", case_id, guild.id)
        if not row:
            return build_error_embed("Case not found.")
        mod  = guild.get_member(row["mod_id"])
        user = guild.get_member(row["user_id"])
        embed = discord.Embed(title=f"📋 Case {case_id}", color=discord.Color.blurple())
        embed.add_field(name="User",       value=str(user or row["user_id"]),  inline=True)
        embed.add_field(name="Moderator",  value=str(mod or row["mod_id"]),    inline=True)
        embed.add_field(name="Action",     value=row["action"].title(),         inline=True)
        embed.add_field(name="Reason",     value=row["reason"] or "None",       inline=False)
        if row["duration"]:
            embed.add_field(name="Duration", value=format_duration(row["duration"]), inline=True)
        embed.add_field(name="Active", value="Yes" if row["active"] else "No", inline=True)
        ts = datetime.datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d %H:%M UTC")
        embed.set_footer(text=f"Created: {ts}")
        return embed

    # ── /modhistory ────────────────────────────────────────────
    @app_commands.command(name="modhistory", description="View moderation history of a user")
    @app_commands.default_permissions(moderate_members=True)
    async def modhistory_slash(self, interaction: discord.Interaction, member: discord.Member):
        embed = await self._modhistory_impl(interaction.guild, member)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="modhistory", aliases=["history"], help="View mod history. Usage: modhistory <member>")
    @commands.has_permissions(moderate_members=True)
    async def modhistory_prefix(self, ctx, member: discord.Member):
        embed = await self._modhistory_impl(ctx.guild, member)
        await ctx.send(embed=embed)

    async def _modhistory_impl(self, guild, member):
        rows = await db_fetch(
            "SELECT * FROM moderation_cases WHERE guild_id=? AND user_id=? ORDER BY created_at DESC LIMIT 10",
            guild.id, member.id,
        )
        embed = discord.Embed(title=f"📋 Mod History: {member}", color=discord.Color.blurple())
        if not rows:
            embed.description = "No moderation history found."
        else:
            for r in rows:
                mod = guild.get_member(r["mod_id"])
                ts  = datetime.datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d")
                embed.add_field(
                    name=f"[{r['case_id']}] {r['action'].upper()} — {ts}",
                    value=f"**By:** {str(mod or r['mod_id'])}\n**Reason:** {r['reason'] or 'None'}",
                    inline=False,
                )
        return embed

    # ── /appeal ───────────────────────────────────────────────
    @app_commands.command(name="appeal", description="Appeal a moderation action")
    async def appeal_slash(self, interaction: discord.Interaction, case_id: str, reason: str):
        embed = await self._appeal_impl(interaction.guild, interaction.user, case_id, reason)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="appeal", help="Appeal a case. Usage: appeal <CASE-ID> <reason>")
    async def appeal_prefix(self, ctx, case_id: str, *, reason: str):
        embed = await self._appeal_impl(ctx.guild, ctx.author, case_id, reason)
        await ctx.send(embed=embed)

    async def _appeal_impl(self, guild, user, case_id, reason):
        row = await db_fetchone(
            "SELECT * FROM moderation_cases WHERE case_id=? AND user_id=? AND guild_id=?",
            case_id, user.id, guild.id,
        )
        if not row:
            return build_error_embed("Case not found or doesn't belong to you.")
        await db_execute(
            "INSERT INTO appeals (guild_id, case_id, user_id, reason) VALUES (?,?,?,?)",
            guild.id, case_id, user.id, reason,
        )
        return discord.Embed(title="📝 Appeal Submitted",
                             description=f"Your appeal for case `{case_id}` has been submitted for review.",
                             color=discord.Color.blurple())

    # ── /voice  (vcmove + vckick combined) ────────────────────
    @app_commands.command(name="voice", description="Voice moderation: move or kick a member from VC")
    @app_commands.describe(action="move or kick", member="Target member", channel="Target channel (for move)")
    @app_commands.default_permissions(move_members=True)
    async def voice_slash(self, interaction: discord.Interaction, action: str, member: discord.Member,
                          channel: discord.VoiceChannel = None):
        embed = await self._voice_impl(action, member, channel)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="vcmove", help="Move a member to a voice channel. Usage: vcmove <member> <#channel>")
    @commands.has_permissions(move_members=True)
    async def vcmove_prefix(self, ctx, member: discord.Member, channel: discord.VoiceChannel):
        embed = await self._voice_impl("move", member, channel)
        await ctx.send(embed=embed)

    @commands.command(name="vckick", help="Kick a member from voice. Usage: vckick <member>")
    @commands.has_permissions(move_members=True)
    async def vckick_prefix(self, ctx, member: discord.Member):
        embed = await self._voice_impl("kick", member, None)
        await ctx.send(embed=embed)

    async def _voice_impl(self, action, member, channel):
        if not member.voice:
            return build_error_embed("Member is not in a voice channel.")
        action = action.lower()
        if action == "move":
            if not channel:
                return build_error_embed("Please specify a target voice channel.")
            await member.move_to(channel)
            return build_success_embed(f"Moved {member.mention} to {channel.mention}.")
        elif action == "kick":
            await member.move_to(None)
            return build_success_embed(f"Kicked {member.mention} from voice.")
        return build_error_embed("Invalid action. Use: move, kick")

    # ── /massban ──────────────────────────────────────────────
    @app_commands.command(name="massban", description="Ban multiple users by ID (space-separated)")
    @app_commands.default_permissions(administrator=True)
    async def massban_slash(self, interaction: discord.Interaction, user_ids: str,
                            reason: str = "Mass ban"):
        await interaction.response.defer()
        embed = await self._massban_impl(interaction.guild, interaction.user, user_ids, reason)
        await interaction.followup.send(embed=embed)

    @commands.command(name="massban", help="Ban multiple users by ID. Usage: massban <id1> <id2> ... [reason]")
    @commands.has_permissions(administrator=True)
    async def massban_prefix(self, ctx, *args):
        ids    = [a for a in args if a.isdigit()]
        reason = " ".join(a for a in args if not a.isdigit()) or "Mass ban"
        embed  = await self._massban_impl(ctx.guild, ctx.author, " ".join(ids), reason)
        await ctx.send(embed=embed)

    async def _massban_impl(self, guild, mod, user_ids_str, reason):
        ids     = [int(x) for x in user_ids_str.split() if x.isdigit()]
        banned  = 0
        failed  = 0
        for uid in ids[:20]:
            try:
                await guild.ban(discord.Object(id=uid), reason=reason)
                banned += 1
            except Exception:
                failed += 1
        embed = discord.Embed(title="🔨 Mass Ban Complete", color=discord.Color.red())
        embed.add_field(name="Banned", value=str(banned), inline=True)
        embed.add_field(name="Failed", value=str(failed), inline=True)
        embed.add_field(name="Reason", value=reason,      inline=False)
        return embed

    # ── /automod  (configure + list combined) ─────────────────
    @app_commands.command(name="automod", description="Configure or list AutoMod rules")
    @app_commands.describe(rule_type="spam/links/mentions/words/etc", action="warn/delete/timeout/kick/ban", list_rules="Show existing rules instead")
    @app_commands.default_permissions(administrator=True)
    async def automod_slash(self, interaction: discord.Interaction,
                            list_rules: bool = False, rule_type: str = None,
                            enabled: bool = True, action: str = "warn", threshold: int = 5):
        embed = await self._automod_impl(interaction.guild, list_rules, rule_type, enabled, action, threshold)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="automod", help="Configure automod. Usage: automod list | automod <type> [action]")
    @commands.has_permissions(administrator=True)
    async def automod_prefix(self, ctx, subcommand: str = "list", rule_type: str = None, action: str = "warn"):
        list_rules = subcommand.lower() == "list"
        embed = await self._automod_impl(ctx.guild, list_rules, rule_type or subcommand if not list_rules else None, True, action, 5)
        await ctx.send(embed=embed)

    async def _automod_impl(self, guild, list_rules, rule_type, enabled, action, threshold):
        if list_rules:
            rows = await db_fetch("SELECT * FROM automod_rules WHERE guild_id=?", guild.id)
            embed = discord.Embed(title="🛡️ AutoMod Rules", color=discord.Color.blurple())
            if not rows:
                embed.description = "No custom AutoMod rules configured. Built-in spam/phishing detection is always active."
            else:
                for r in rows:
                    status = "✅" if r["enabled"] else "❌"
                    embed.add_field(name=f"{status} {r['rule_type']}", value=f"Action: {r['action']} | Threshold: {r['threshold']}", inline=True)
            return embed
        if not rule_type:
            return build_error_embed("Provide a rule type or use `list_rules=True`.")
        await db_execute(
            "INSERT INTO automod_rules (guild_id, rule_type, enabled, action, threshold) VALUES (?,?,?,?,?) ON CONFLICT DO UPDATE SET enabled=excluded.enabled, action=excluded.action, threshold=excluded.threshold",
            guild.id, rule_type, int(enabled), action, threshold,
        )
        return build_success_embed(f"AutoMod rule `{rule_type}` {'enabled' if enabled else 'disabled'} with action `{action}`.")

    # ── /lockdown ─────────────────────────────────────────────
    @app_commands.command(name="lockdown", description="Toggle server lockdown mode")
    @app_commands.default_permissions(administrator=True)
    async def lockdown_slash(self, interaction: discord.Interaction, reason: str = "Emergency lockdown"):
        await interaction.response.defer()
        embed = await self._lockdown_impl(interaction.guild, interaction.user, reason)
        await interaction.followup.send(embed=embed)

    @commands.command(name="lockdown", help="Toggle server lockdown. Usage: lockdown [reason]")
    @commands.has_permissions(administrator=True)
    async def lockdown_prefix(self, ctx, *, reason: str = "Emergency lockdown"):
        embed = await self._lockdown_impl(ctx.guild, ctx.author, reason)
        await ctx.send(embed=embed)

    async def _lockdown_impl(self, guild, mod, reason):
        row = await db_fetchone("SELECT * FROM anti_raid WHERE guild_id=?", guild.id)
        active = row["lockdown_active"] if row else 0
        new_state = 1 if not active else 0
        await db_execute(
            "INSERT INTO anti_raid (guild_id, lockdown_active, lockdown_reason, lockdown_at) VALUES (?,?,?,?) ON CONFLICT(guild_id) DO UPDATE SET lockdown_active=excluded.lockdown_active, lockdown_reason=excluded.lockdown_reason, lockdown_at=excluded.lockdown_at",
            guild.id, new_state, reason if new_state else None, int(time.time()) if new_state else None,
        )
        if new_state:
            try:
                for ch in guild.text_channels:
                    await ch.set_permissions(guild.default_role, send_messages=False)
            except Exception:
                pass
            return discord.Embed(title="🔒 SERVER LOCKDOWN ACTIVE", description=f"**Reason:** {reason}\nAll channels have been locked.", color=discord.Color.red())
        else:
            try:
                for ch in guild.text_channels:
                    await ch.set_permissions(guild.default_role, send_messages=None)
            except Exception:
                pass
            return discord.Embed(title="🔓 Lockdown Lifted", description="Server has been unlocked.", color=discord.Color.green())

    # ── /antiraid ─────────────────────────────────────────────
    @app_commands.command(name="antiraid", description="Configure anti-raid settings")
    @app_commands.default_permissions(administrator=True)
    async def antiraid_slash(self, interaction: discord.Interaction, enabled: bool = True,
                             join_threshold: int = 10, join_window: int = 10,
                             action: str = "kick"):
        embed = await self._antiraid_impl(interaction.guild, enabled, join_threshold, join_window, action)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="antiraid", help="Configure anti-raid. Usage: antiraid <enabled> [threshold] [window] [action]")
    @commands.has_permissions(administrator=True)
    async def antiraid_prefix(self, ctx, enabled: bool = True, join_threshold: int = 10,
                               join_window: int = 10, action: str = "kick"):
        embed = await self._antiraid_impl(ctx.guild, enabled, join_threshold, join_window, action)
        await ctx.send(embed=embed)

    async def _antiraid_impl(self, guild, enabled, threshold, window, action):
        await db_execute(
            "INSERT INTO anti_raid (guild_id, enabled, join_threshold, join_window, action) VALUES (?,?,?,?,?) ON CONFLICT(guild_id) DO UPDATE SET enabled=excluded.enabled, join_threshold=excluded.join_threshold, join_window=excluded.join_window, action=excluded.action",
            guild.id, int(enabled), threshold, window, action,
        )
        embed = discord.Embed(title="🛡️ Anti-Raid Configured", color=discord.Color.blurple())
        embed.add_field(name="Enabled",        value="✅" if enabled else "❌",  inline=True)
        embed.add_field(name="Join Threshold", value=f"{threshold} joins",       inline=True)
        embed.add_field(name="Window",         value=f"{window} seconds",        inline=True)
        embed.add_field(name="Action",         value=action.title(),             inline=True)
        return embed


# ============================================================
# SECTION: Tickets  (6 slash commands)
# ============================================================

class TicketCog(commands.Cog, name="Tickets"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="ticket-panel", description="Create a ticket panel with department buttons")
    @app_commands.default_permissions(administrator=True)
    async def ticket_panel_slash(self, interaction: discord.Interaction,
                                  channel: discord.TextChannel, title: str = "Support Tickets",
                                  description: str = "Select a department to open a ticket.",
                                  departments: str = "General,Technical,Billing,Appeals"):
        await interaction.response.defer(ephemeral=True)
        dept_list = [d.strip() for d in departments.split(",") if d.strip()]
        view = discord.ui.View(timeout=None)
        for dept in dept_list:
            btn = discord.ui.Button(label=dept, style=discord.ButtonStyle.primary,
                                    custom_id=f"ticket_open:{dept.lower().replace(' ', '_')}")
            view.add_item(btn)
        embed = discord.Embed(title=f"🎫 {title}", description=description, color=discord.Color.blurple())
        embed.set_footer(text="Select a department to open a ticket.")
        msg = await channel.send(embed=embed, view=view)
        await db_execute(
            "INSERT INTO ticket_panels (guild_id, channel_id, message_id, name, description) VALUES (?,?,?,?,?)",
            interaction.guild_id, channel.id, msg.id, title, description,
        )
        await interaction.followup.send(embed=build_success_embed(f"Ticket panel created in {channel.mention}."), ephemeral=True)

    @commands.command(name="ticket-panel", help="Create a ticket panel. Usage: ticket-panel <#channel> [title]")
    @commands.has_permissions(administrator=True)
    async def ticket_panel_prefix(self, ctx, channel: discord.TextChannel, *, title: str = "Support Tickets"):
        view = discord.ui.View(timeout=None)
        for dept in ["General", "Technical", "Billing"]:
            btn = discord.ui.Button(label=dept, style=discord.ButtonStyle.primary,
                                    custom_id=f"ticket_open:{dept.lower()}")
            view.add_item(btn)
        embed = discord.Embed(title=f"🎫 {title}", description="Select a department to open a ticket.", color=discord.Color.blurple())
        msg = await channel.send(embed=embed, view=view)
        await db_execute(
            "INSERT INTO ticket_panels (guild_id, channel_id, message_id, name, description) VALUES (?,?,?,?,?)",
            ctx.guild.id, channel.id, msg.id, title, "Select a department to open a ticket.",
        )
        await ctx.send(embed=build_success_embed(f"Ticket panel created in {channel.mention}."))

    @app_commands.command(name="ticket-close", description="Close the current ticket")
    async def ticket_close_slash(self, interaction: discord.Interaction):
        await self._close_ticket(interaction)

    @commands.command(name="ticket-close", aliases=["tclose"], help="Close the current ticket channel.")
    async def ticket_close_prefix(self, ctx):
        row = await db_fetchone("SELECT * FROM tickets WHERE channel_id=? AND status='open'", ctx.channel.id)
        if not row:
            await ctx.send(embed=build_error_embed("This is not an open ticket."))
            return
        await db_execute("UPDATE tickets SET status='closed', closed_at=? WHERE ticket_id=?",
                         int(time.time()), row["ticket_id"])
        await ctx.send(embed=build_success_embed("Ticket closed."))
        await asyncio.sleep(5)
        try:
            await ctx.channel.delete(reason=f"Ticket {row['ticket_id']} closed")
        except Exception:
            pass

    # ── /ticket-manage  (add + remove + rename combined) ──────
    @app_commands.command(name="ticket-manage", description="Manage ticket: add/remove user or rename channel")
    @app_commands.describe(action="add, remove, or rename", member="Member to add/remove", name="New channel name")
    @app_commands.default_permissions(moderate_members=True)
    async def ticket_manage_slash(self, interaction: discord.Interaction, action: str,
                                   member: discord.Member = None, name: str = None):
        embed = await self._ticket_manage_impl(interaction.channel, interaction.user, action, member, name)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="ticket-add", help="Add a user to the ticket. Usage: ticket-add <member>")
    @commands.has_permissions(moderate_members=True)
    async def ticket_add_prefix(self, ctx, member: discord.Member):
        embed = await self._ticket_manage_impl(ctx.channel, ctx.author, "add", member, None)
        await ctx.send(embed=embed)

    @commands.command(name="ticket-remove", help="Remove a user from the ticket. Usage: ticket-remove <member>")
    @commands.has_permissions(moderate_members=True)
    async def ticket_remove_prefix(self, ctx, member: discord.Member):
        embed = await self._ticket_manage_impl(ctx.channel, ctx.author, "remove", member, None)
        await ctx.send(embed=embed)

    @commands.command(name="ticket-rename", help="Rename the ticket channel. Usage: ticket-rename <name>")
    @commands.has_permissions(manage_channels=True)
    async def ticket_rename_prefix(self, ctx, *, name: str):
        embed = await self._ticket_manage_impl(ctx.channel, ctx.author, "rename", None, name)
        await ctx.send(embed=embed)

    async def _ticket_manage_impl(self, channel, mod, action, member, name):
        action = action.lower()
        if action == "add":
            if not member:
                return build_error_embed("Please specify a member to add.")
            await channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
            return build_success_embed(f"Added {member.mention} to the ticket.")
        elif action == "remove":
            if not member:
                return build_error_embed("Please specify a member to remove.")
            await channel.set_permissions(member, overwrite=None)
            return build_success_embed(f"Removed {member.mention} from the ticket.")
        elif action == "rename":
            if not name:
                return build_error_embed("Please specify a new name.")
            await channel.edit(name=name)
            return build_success_embed(f"Ticket renamed to `{name}`.")
        return build_error_embed("Invalid action. Use: add, remove, rename")

    @app_commands.command(name="ticket-note", description="Add an internal staff note to the ticket")
    @app_commands.default_permissions(moderate_members=True)
    async def ticket_note_slash(self, interaction: discord.Interaction, note: str):
        embed = await self._ticket_note_impl(interaction.channel, interaction.user, note)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="ticket-note", aliases=["tnote"], help="Add a staff note. Usage: ticket-note <note>")
    @commands.has_permissions(moderate_members=True)
    async def ticket_note_prefix(self, ctx, *, note: str):
        embed = await self._ticket_note_impl(ctx.channel, ctx.author, note)
        await ctx.send(embed=embed)

    async def _ticket_note_impl(self, channel, mod, note):
        row = await db_fetchone("SELECT * FROM tickets WHERE channel_id=?", channel.id)
        if not row:
            return build_error_embed("Not a ticket channel.")
        notes = json.loads(row["internal_notes"] or "[]")
        notes.append({"author": str(mod), "note": note, "at": int(time.time())})
        await db_execute("UPDATE tickets SET internal_notes=? WHERE channel_id=?",
                         json.dumps(notes), channel.id)
        embed = discord.Embed(title="📝 Internal Note Added", description=note, color=discord.Color.gold())
        embed.set_footer(text=f"Note by {mod} — Staff only")
        return embed

    @app_commands.command(name="ticket-summary", description="Generate an AI summary of this ticket")
    @app_commands.default_permissions(moderate_members=True)
    async def ticket_summary_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = await self._ticket_summary_impl(interaction.channel)
        await interaction.followup.send(embed=embed)

    @commands.command(name="ticket-summary", aliases=["tsummary"], help="AI ticket summary.")
    @commands.has_permissions(moderate_members=True)
    async def ticket_summary_prefix(self, ctx):
        embed = await self._ticket_summary_impl(ctx.channel)
        await ctx.send(embed=embed)

    async def _ticket_summary_impl(self, channel):
        row = await db_fetchone("SELECT * FROM tickets WHERE channel_id=?", channel.id)
        if not row:
            return build_error_embed("Not a ticket channel.")
        msgs     = await db_fetch("SELECT content FROM ticket_messages WHERE ticket_id=? ORDER BY created_at LIMIT 30", row["ticket_id"])
        msg_texts = [m["content"] for m in msgs if m["content"]]
        summary   = await self.bot.ai.generate_ticket_summary(msg_texts, row["subject"] or "")
        return discord.Embed(title="🤖 AI Ticket Summary", description=summary, color=discord.Color.blurple())

    @app_commands.command(name="ticket-stats", description="View server ticket statistics")
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_stats_slash(self, interaction: discord.Interaction):
        embed = await self._ticket_stats_impl(interaction.guild_id)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="ticket-stats", aliases=["tstats"], help="View ticket statistics.")
    @commands.has_permissions(manage_guild=True)
    async def ticket_stats_prefix(self, ctx):
        embed = await self._ticket_stats_impl(ctx.guild.id)
        await ctx.send(embed=embed)

    async def _ticket_stats_impl(self, guild_id):
        total      = await db_fetchone("SELECT COUNT(*) as c FROM tickets WHERE guild_id=?", guild_id)
        open_t     = await db_fetchone("SELECT COUNT(*) as c FROM tickets WHERE guild_id=? AND status='open'", guild_id)
        closed     = await db_fetchone("SELECT COUNT(*) as c FROM tickets WHERE guild_id=? AND status='closed'", guild_id)
        avg_rating = await db_fetchone("SELECT AVG(feedback) as avg FROM tickets WHERE guild_id=? AND feedback IS NOT NULL", guild_id)
        embed = discord.Embed(title="📊 Ticket Statistics", color=discord.Color.blurple())
        embed.add_field(name="Total Tickets", value=str(total["c"] if total else 0), inline=True)
        embed.add_field(name="Open",          value=str(open_t["c"] if open_t else 0), inline=True)
        embed.add_field(name="Closed",        value=str(closed["c"] if closed else 0), inline=True)
        if avg_rating and avg_rating["avg"]:
            embed.add_field(name="Avg Rating", value=f"⭐ {avg_rating['avg']:.1f}/5", inline=True)
        return embed

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

    async def _open_ticket(self, interaction: discord.Interaction, department: str):
        existing = await db_fetchone(
            "SELECT * FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
            interaction.guild_id, interaction.user.id,
        )
        if existing:
            ch  = self.bot.get_channel(existing["channel_id"])
            msg = f"You already have an open ticket: {ch.mention}." if ch else "You already have an open ticket."
            await interaction.response.send_message(embed=build_error_embed(msg), ephemeral=True)
            return
        await interaction.response.send_modal(TicketOpenModal(self.bot, department))

    async def create_ticket_channel(self, guild, user, department, subject):
        cfg        = await get_guild_config(guild.id)
        ticket_id  = generate_ticket_id(guild.id)
        category_id = cfg["ticket_category"] if cfg else None
        category    = guild.get_channel(category_id) if category_id else None
        if not category:
            category = await guild.create_category("Tickets", reason="Ticket system setup")
            if cfg:
                await db_execute("UPDATE guild_config SET ticket_category=? WHERE guild_id=?", category.id, guild.id)
        support_ids = json.loads(cfg["ticket_support"]) if cfg and cfg["ticket_support"] else []
        overwrites  = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for rid in support_ids:
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)
        try:
            channel = await category.create_text_channel(
                name=f"ticket-{ticket_id.lower()}", overwrites=overwrites, reason=f"Ticket: {subject}"
            )
        except Exception as e:
            log.error(f"Failed to create ticket channel: {e}")
            return None
        sla = int(time.time()) + 86400
        await db_execute(
            "INSERT INTO tickets (ticket_id, guild_id, channel_id, user_id, department, subject, sla_deadline) VALUES (?,?,?,?,?,?,?)",
            ticket_id, guild.id, channel.id, user.id, department, subject, sla,
        )
        embed = discord.Embed(title=f"🎫 Ticket {ticket_id}",
                              description=f"**Department:** {department}\n**Subject:** {subject}\n\nSupport staff will assist you shortly.",
                              color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
        embed.add_field(name="User",     value=user.mention,    inline=True)
        embed.add_field(name="Priority", value="🟡 Normal",     inline=True)
        embed.add_field(name="SLA",      value=f"<t:{sla}:R>",  inline=True)
        view      = discord.ui.View(timeout=None)
        close_btn = discord.ui.Button(label="Close Ticket", style=discord.ButtonStyle.danger,   emoji="🔒", custom_id="ticket_close")
        claim_btn = discord.ui.Button(label="Claim",        style=discord.ButtonStyle.success,  emoji="👋", custom_id="ticket_claim")
        view.add_item(close_btn)
        view.add_item(claim_btn)
        await channel.send(embed=embed, view=view)
        await channel.send(f"{user.mention} Welcome! Please describe your issue.")
        await self.bot._log_event(guild.id, "ticket_opened", user.id, channel_id=channel.id,
                                  description=f"Ticket {ticket_id} opened | Dept: {department}")
        return channel

    async def _close_ticket(self, interaction: discord.Interaction):
        row = await db_fetchone("SELECT * FROM tickets WHERE channel_id=? AND status='open'", interaction.channel_id)
        if not row:
            await interaction.response.send_message(embed=build_error_embed("This is not an open ticket."), ephemeral=True)
            return
        user = interaction.guild.get_member(row["user_id"])
        await interaction.response.send_modal(TicketCloseModal(self.bot, row, user))

    async def _claim_ticket(self, interaction: discord.Interaction):
        row = await db_fetchone("SELECT * FROM tickets WHERE channel_id=? AND status='open'", interaction.channel_id)
        if not row:
            await interaction.response.send_message(embed=build_error_embed("This is not an open ticket."), ephemeral=True)
            return
        if row["claimed_by"]:
            claimer = interaction.guild.get_member(row["claimed_by"])
            await interaction.response.send_message(
                embed=build_error_embed(f"Already claimed by {claimer.mention if claimer else 'staff'}."), ephemeral=True
            )
            return
        await db_execute(
            "UPDATE tickets SET claimed_by=?, first_response=COALESCE(first_response,?) WHERE ticket_id=?",
            interaction.user.id, int(time.time()), row["ticket_id"],
        )
        await db_execute(
            "INSERT INTO ticket_stats (guild_id, user_id, tickets_claimed) VALUES (?,?,1) ON CONFLICT(guild_id,user_id) DO UPDATE SET tickets_claimed=tickets_claimed+1",
            interaction.guild_id, interaction.user.id,
        )
        await interaction.response.send_message(
            embed=discord.Embed(title="👋 Ticket Claimed",
                                description=f"{interaction.user.mention} is now handling this ticket.",
                                color=discord.Color.green())
        )


class TicketOpenModal(discord.ui.Modal, title="Open a Ticket"):
    def __init__(self, bot, department):
        super().__init__()
        self.bot        = bot
        self.department = department
        self.subject    = discord.ui.TextInput(label="Subject", placeholder="Brief description of your issue", max_length=100)
        self.details    = discord.ui.TextInput(label="Details",  placeholder="Describe your issue in detail",  style=discord.TextStyle.paragraph, max_length=1000)
        self.add_item(self.subject)
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog: TicketCog = self.bot.cogs.get("Tickets")
        if cog:
            channel = await cog.create_ticket_channel(interaction.guild, interaction.user, self.department, self.subject.value)
            if channel:
                row = await db_fetchone("SELECT ticket_id FROM tickets WHERE channel_id=?", channel.id)
                if row:
                    await db_execute(
                        "INSERT INTO ticket_messages (ticket_id, guild_id, user_id, username, content) VALUES (?,?,?,?,?)",
                        row["ticket_id"], interaction.guild_id, interaction.user.id, str(interaction.user), self.details.value,
                    )
                await interaction.followup.send(embed=build_success_embed(f"Your ticket has been opened: {channel.mention}"), ephemeral=True)
            else:
                await interaction.followup.send(embed=build_error_embed("Failed to create ticket channel."), ephemeral=True)


class TicketCloseModal(discord.ui.Modal, title="Close Ticket"):
    def __init__(self, bot, ticket_row, user):
        super().__init__()
        self.bot         = bot
        self.ticket_row  = ticket_row
        self.ticket_user = user
        self.reason      = discord.ui.TextInput(label="Close Reason", placeholder="Why is this ticket being closed?", max_length=500, required=False)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ticket_id = self.ticket_row["ticket_id"]
        await db_execute("UPDATE tickets SET status='closed', closed_at=? WHERE ticket_id=?", int(time.time()), ticket_id)
        messages = await db_fetch("SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY created_at", ticket_id)
        transcript_lines = [f"Ticket: {ticket_id}", f"Department: {self.ticket_row['department']}", f"Subject: {self.ticket_row['subject'] or 'N/A'}", "=" * 50]
        for m in messages:
            ts = datetime.datetime.fromtimestamp(m["created_at"]).strftime("%Y-%m-%d %H:%M")
            transcript_lines.append(f"[{ts}] {m['username']}: {m['content']}")
        transcript_path = f"transcripts/{ticket_id}.txt"
        async with aiofiles.open(transcript_path, "w", encoding="utf-8") as f:
            await f.write("\n".join(transcript_lines))
        await db_execute("UPDATE tickets SET transcript_url=? WHERE ticket_id=?", transcript_path, ticket_id)
        if self.ticket_row["claimed_by"]:
            await db_execute(
                "INSERT INTO ticket_stats (guild_id, user_id, tickets_closed) VALUES (?,?,1) ON CONFLICT(guild_id,user_id) DO UPDATE SET tickets_closed=tickets_closed+1",
                interaction.guild_id, self.ticket_row["claimed_by"],
            )
        embed = discord.Embed(title="🔒 Ticket Closed",
                              description=f"Closed by {interaction.user.mention}.\n**Reason:** {self.reason.value or 'No reason given'}",
                              color=discord.Color.red())
        await interaction.followup.send(embed=embed)
        if self.ticket_user:
            try:
                view = TicketRatingView(self.bot, ticket_id)
                dm_embed = discord.Embed(title="📝 Ticket Feedback",
                                         description=f"Your ticket `{ticket_id}` has been closed. Please rate your experience:",
                                         color=discord.Color.blurple())
                await self.ticket_user.send(embed=dm_embed, view=view)
            except Exception:
                pass
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket {ticket_id} closed")
        except Exception:
            pass
        await self.bot._log_event(interaction.guild_id, "ticket_closed", interaction.user.id,
                                  description=f"Ticket {ticket_id} closed by {interaction.user}")


class TicketRatingView(discord.ui.View):
    def __init__(self, bot, ticket_id):
        super().__init__(timeout=86400)
        self.bot       = bot
        self.ticket_id = ticket_id
        for i in range(1, 6):
            btn = discord.ui.Button(label="⭐" * i, style=discord.ButtonStyle.secondary,
                                    custom_id=f"rate:{ticket_id}:{i}")
            self.add_item(btn)


# ============================================================
# SECTION: Reaction Roles  (1 slash command)
# ============================================================

class ReactionRolesCog(commands.Cog, name="ReactionRoles"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="reactionrole", description="Add or remove a reaction role button")
    @app_commands.describe(action="add or remove", channel="Channel with the message", message_id="Message ID")
    @app_commands.default_permissions(manage_roles=True)
    async def rr_slash(self, interaction: discord.Interaction, action: str,
                       role: discord.Role, channel: discord.TextChannel = None,
                       message_id: str = None, label: str = None, emoji: str = "🎭",
                       exclusive: bool = False):
        embed = await self._rr_impl(interaction.guild, action, role, channel, message_id, label, emoji, exclusive)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="rradd", help="Add reaction role. Usage: rradd <#channel> <msg_id> <@role> <label>")
    @commands.has_permissions(manage_roles=True)
    async def rr_add_prefix(self, ctx, channel: discord.TextChannel, message_id: str, role: discord.Role, *, label: str = "Role"):
        embed = await self._rr_impl(ctx.guild, "add", role, channel, message_id, label, "🎭", False)
        await ctx.send(embed=embed)

    @commands.command(name="rrremove", help="Remove reaction role. Usage: rrremove <@role>")
    @commands.has_permissions(manage_roles=True)
    async def rr_remove_prefix(self, ctx, role: discord.Role):
        embed = await self._rr_impl(ctx.guild, "remove", role, None, None, None, None, False)
        await ctx.send(embed=embed)

    async def _rr_impl(self, guild, action, role, channel, message_id_str, label, emoji, exclusive):
        action = action.lower()
        if action == "remove":
            row = await db_fetchone("SELECT * FROM reaction_roles WHERE guild_id=? AND role_id=?", guild.id, role.id)
            if not row:
                return build_error_embed("Reaction role not found.")
            await db_execute("DELETE FROM reaction_roles WHERE guild_id=? AND role_id=?", guild.id, role.id)
            return build_success_embed(f"Removed reaction role for {role.mention}.")
        if action == "add":
            if not channel or not message_id_str:
                return build_error_embed("Please provide a channel and message ID.")
            try:
                msg_id = int(message_id_str)
                msg    = await channel.fetch_message(msg_id)
            except Exception:
                return build_error_embed("Message not found.")
            await db_execute(
                "INSERT INTO reaction_roles (guild_id, message_id, channel_id, role_id, emoji, label, exclusive) VALUES (?,?,?,?,?,?,?)",
                guild.id, msg_id, channel.id, role.id, emoji or "🎭", label or "Role", int(exclusive),
            )
            rows = await db_fetch("SELECT * FROM reaction_roles WHERE guild_id=? AND message_id=?", guild.id, msg_id)
            view = discord.ui.View(timeout=None)
            for r in rows[:25]:
                btn = discord.ui.Button(label=r["label"] or "Role", emoji=r["emoji"],
                                        style=discord.ButtonStyle.secondary,
                                        custom_id=f"rr:{msg_id}:{r['role_id']}:{r['exclusive']}")
                view.add_item(btn)
            await msg.edit(view=view)
            return build_success_embed(f"Reaction role {emoji} `{label}` → {role.mention} added.")
        return build_error_embed("Invalid action. Use: add, remove")

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
        try:
            role_id   = int(parts[2])
            exclusive = int(parts[3]) == 1
        except ValueError:
            return
        member = interaction.user
        role   = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(embed=build_error_embed("Role not found."), ephemeral=True)
            return
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Reaction role toggle")
                await interaction.response.send_message(embed=build_success_embed(f"Removed role: **{role.name}**"), ephemeral=True)
            else:
                if exclusive:
                    msg_id     = int(parts[1])
                    other_rows = await db_fetch("SELECT role_id FROM reaction_roles WHERE guild_id=? AND message_id=?", interaction.guild_id, msg_id)
                    for other in other_rows:
                        other_role = interaction.guild.get_role(other["role_id"])
                        if other_role and other_role in member.roles and other_role != role:
                            await member.remove_roles(other_role, reason="Exclusive reaction role")
                await member.add_roles(role, reason="Reaction role")
                await interaction.response.send_message(embed=build_success_embed(f"Added role: **{role.name}**"), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(embed=build_error_embed("I don't have permission to manage that role."), ephemeral=True)


# ============================================================
# SECTION: Welcome System  (3 slash commands)
# ============================================================

class WelcomeCog(commands.Cog, name="Welcome"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = member.guild.id
        await ensure_user(member.id, guild_id, str(member))
        await db_execute("UPDATE users SET joined_at=? WHERE user_id=? AND guild_id=?",
                         int(member.joined_at.timestamp()) if member.joined_at else int(time.time()),
                         member.id, guild_id)
        cfg = await get_guild_config(guild_id)
        if not cfg:
            return
        autorole_ids = json.loads(cfg["autorole_ids"] or "[]")
        for rid in autorole_ids:
            role = member.guild.get_role(rid)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except Exception:
                    pass
        if cfg["welcome_enabled"] and cfg["welcome_channel"]:
            ch = self.bot.get_channel(cfg["welcome_channel"])
            if ch:
                try:
                    msg_template = cfg["welcome_message"] or "Welcome {user} to **{server}**! 🎉"
                    msg = msg_template.replace("{user}", member.mention).replace("{server}", member.guild.name).replace("{count}", str(member.guild.member_count))
                    if cfg["ai_enabled"]:
                        ai_msg = await self.bot.ai._call_ai(
                            [{"role": "user", "content": f"Write a short, friendly welcome message (1-2 sentences) for {member.name} who just joined {member.guild.name}. No emojis needed."}],
                            max_tokens=80,
                        )
                        embed = discord.Embed(title=f"👋 Welcome to {member.guild.name}!",
                                             description=f"{member.mention}\n\n{ai_msg}", color=discord.Color.green())
                    else:
                        embed = discord.Embed(title="👋 Welcome!", description=msg, color=discord.Color.green())
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text=f"Member #{member.guild.member_count}")
                    await ch.send(embed=embed)
                except Exception as e:
                    log.error(f"Welcome message error: {e}")
        await self.bot._log_event(guild_id, "member_join", member.id, description=f"{member} joined the server")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild_id = member.guild.id
        cfg = await get_guild_config(guild_id)
        if cfg and cfg["welcome_enabled"] and cfg["welcome_channel"]:
            ch = self.bot.get_channel(cfg["welcome_channel"])
            if ch:
                msg_template = cfg["goodbye_message"] or "**{user}** has left the server. Goodbye! 👋"
                msg = msg_template.replace("{user}", str(member)).replace("{server}", member.guild.name)
                try:
                    await ch.send(msg)
                except Exception:
                    pass
        await self.bot._log_event(guild_id, "member_leave", member.id, description=f"{member} left the server")

    @app_commands.command(name="welcome-config", description="Configure the welcome/goodbye system")
    @app_commands.default_permissions(manage_guild=True)
    async def welcome_config_slash(self, interaction: discord.Interaction,
                                    channel: discord.TextChannel = None,
                                    message: str = None, enabled: bool = True,
                                    goodbye: str = None):
        embed = await self._welcome_config_impl(interaction.guild, channel, message, enabled, goodbye)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="welcome-config", help="Set up welcome messages. Usage: welcome-config #channel")
    @commands.has_permissions(manage_guild=True)
    async def welcome_config_prefix(self, ctx, channel: discord.TextChannel = None, *, message: str = None):
        embed = await self._welcome_config_impl(ctx.guild, channel, message, True, None)
        await ctx.send(embed=embed)

    async def _welcome_config_impl(self, guild, channel, message, enabled, goodbye):
        updates, values = ["welcome_enabled=?", "updated_at=?"], [int(enabled), int(time.time())]
        if channel:
            updates.append("welcome_channel=?"); values.append(channel.id)
        if message:
            updates.append("welcome_message=?"); values.append(message)
        if goodbye:
            updates.append("goodbye_message=?"); values.append(goodbye)
        values.append(guild.id)
        await db_execute(f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id=?", *values)
        embed = discord.Embed(title="✅ Welcome System Configured", color=discord.Color.green())
        if channel:
            embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Enabled", value="✅" if enabled else "❌", inline=True)
        return embed

    @app_commands.command(name="autorole", description="Add or remove an auto-role for new members")
    @app_commands.describe(action="add or remove")
    @app_commands.default_permissions(manage_roles=True)
    async def autorole_slash(self, interaction: discord.Interaction, action: str, role: discord.Role):
        embed = await self._autorole_impl(interaction.guild, action, role)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="autorole", help="Manage auto-roles. Usage: autorole add/remove <@role>")
    @commands.has_permissions(manage_roles=True)
    async def autorole_prefix(self, ctx, action: str, role: discord.Role):
        embed = await self._autorole_impl(ctx.guild, action, role)
        await ctx.send(embed=embed)

    async def _autorole_impl(self, guild, action, role):
        cfg = await get_guild_config(guild.id)
        ids = json.loads(cfg["autorole_ids"] or "[]") if cfg else []
        action = action.lower()
        if action == "add":
            if role.id in ids:
                return build_error_embed("Already an auto-role.")
            ids.append(role.id)
            await db_execute("UPDATE guild_config SET autorole_ids=? WHERE guild_id=?", json.dumps(ids), guild.id)
            return build_success_embed(f"Added {role.mention} as auto-role.")
        elif action == "remove":
            if role.id not in ids:
                return build_error_embed("Not an auto-role.")
            ids.remove(role.id)
            await db_execute("UPDATE guild_config SET autorole_ids=? WHERE guild_id=?", json.dumps(ids), guild.id)
            return build_success_embed(f"Removed {role.mention} from auto-roles.")
        return build_error_embed("Invalid action. Use: add, remove")

    @app_commands.command(name="logs-config", description="Configure log and mod-log channels")
    @app_commands.default_permissions(administrator=True)
    async def logs_config_slash(self, interaction: discord.Interaction,
                                 log_channel: discord.TextChannel = None,
                                 mod_log_channel: discord.TextChannel = None):
        embed = await self._logs_config_impl(interaction.guild, log_channel, mod_log_channel)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="logs-config", help="Set log channels. Usage: logs-config #log [#modlog]")
    @commands.has_permissions(administrator=True)
    async def logs_config_prefix(self, ctx, log_channel: discord.TextChannel = None,
                                  mod_log_channel: discord.TextChannel = None):
        embed = await self._logs_config_impl(ctx.guild, log_channel, mod_log_channel)
        await ctx.send(embed=embed)

    async def _logs_config_impl(self, guild, log_channel, mod_log_channel):
        updates, values = ["updated_at=?"], [int(time.time())]
        if log_channel:
            updates.append("log_channel=?"); values.append(log_channel.id)
        if mod_log_channel:
            updates.append("mod_log_channel=?"); values.append(mod_log_channel.id)
        values.append(guild.id)
        await db_execute(f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id=?", *values)
        embed = discord.Embed(title="✅ Logging Configured", color=discord.Color.green())
        if log_channel:
            embed.add_field(name="Log Channel",     value=log_channel.mention,     inline=True)
        if mod_log_channel:
            embed.add_field(name="Mod Log Channel", value=mod_log_channel.mention, inline=True)
        return embed


# ============================================================
# SECTION: Logging Cog (event listeners only)
# ============================================================

class LoggingCog(commands.Cog, name="Logging"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        await self.bot._log_event(message.guild.id, "message_delete", message.author.id,
                                  channel_id=message.channel.id, description=f"Message deleted: {message.content[:200]}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        await self.bot._log_event(before.guild.id, "message_edit", before.author.id,
                                  channel_id=before.channel.id,
                                  description=f"Before: {before.content[:100]} | After: {after.content[:100]}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if before.channel == after.channel:
            return
        guild_id = member.guild.id
        now      = int(time.time())
        if after.channel and not before.channel:
            key = f"{guild_id}:{member.id}"
            self.bot.voice_sessions[key] = now
            await db_execute("INSERT INTO voice_tracking (user_id, guild_id, channel_id, joined_at) VALUES (?,?,?,?)",
                             member.id, guild_id, after.channel.id, now)
            await self.bot._log_event(guild_id, "voice_join", member.id, channel_id=after.channel.id,
                                      description=f"{member} joined voice: {after.channel.name}")
        elif before.channel and not after.channel:
            key       = f"{guild_id}:{member.id}"
            joined_at = self.bot.voice_sessions.pop(key, now)
            duration  = now - joined_at
            await db_execute("UPDATE voice_tracking SET left_at=?, duration=? WHERE user_id=? AND guild_id=? AND left_at IS NULL",
                             now, duration, member.id, guild_id)
            await db_execute("UPDATE users SET voice_minutes=voice_minutes+? WHERE user_id=? AND guild_id=?",
                             duration // 60, member.id, guild_id)
            cfg = await get_guild_config(guild_id)
            if cfg and cfg["level_enabled"] and duration >= 60:
                xp_gain = duration // 60 * 3
                lvl = await db_fetchone("SELECT * FROM levels WHERE user_id=? AND guild_id=?", member.id, guild_id)
                if lvl:
                    new_xp = lvl["xp"] + xp_gain
                    await db_execute("UPDATE levels SET xp=?, level=?, voice_xp=voice_xp+? WHERE user_id=? AND guild_id=?",
                                     new_xp, self.bot._calc_level(new_xp), xp_gain, member.id, guild_id)
            await self.bot._log_event(guild_id, "voice_leave", member.id, channel_id=before.channel.id,
                                      description=f"{member} left voice after {format_duration(duration)}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if not before.guild or before.roles == after.roles:
            return
        added   = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        desc = ""
        if added:   desc += f"Roles added: {', '.join(r.name for r in added)}. "
        if removed: desc += f"Roles removed: {', '.join(r.name for r in removed)}."
        await self.bot._log_event(before.guild.id, "member_role_update", before.id, description=desc)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.bot._log_event(channel.guild.id, "channel_create", description=f"Channel created: #{channel.name}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self.bot._log_event(role.guild.id, "role_create", description=f"Role created: @{role.name}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.bot._log_event(role.guild.id, "role_delete", description=f"Role deleted: @{role.name}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self.bot._log_event(guild.id, "member_ban", user.id, description=f"{user} was banned")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self.bot._log_event(guild.id, "member_unban", user.id, description=f"{user} was unbanned")


# ============================================================
# SECTION: Economy  (17 slash commands)
# ============================================================

JOBS = {
    "developer": {"salary": (500, 900),  "cooldown": 3600, "description": "Write code"},
    "teacher":   {"salary": (300, 600),  "cooldown": 3600, "description": "Educate students"},
    "chef":      {"salary": (200, 500),  "cooldown": 3600, "description": "Cook meals"},
    "doctor":    {"salary": (600, 1000), "cooldown": 3600, "description": "Treat patients"},
    "artist":    {"salary": (150, 400),  "cooldown": 3600, "description": "Create art"},
    "streamer":  {"salary": (100, 800),  "cooldown": 3600, "description": "Stream games"},
    "trader":    {"salary": (200, 1500), "cooldown": 3600, "description": "Trade stocks (risky)"},
    "miner":     {"salary": (300, 600),  "cooldown": 3600, "description": "Mine resources"},
}


class EconomyCog(commands.Cog, name="Economy"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    async def _get_eco(self, user_id, guild_id):
        row = await db_fetchone("SELECT * FROM economy WHERE user_id=? AND guild_id=?", user_id, guild_id)
        if not row:
            await db_execute("INSERT OR IGNORE INTO economy (user_id, guild_id) VALUES (?,?)", user_id, guild_id)
            row = await db_fetchone("SELECT * FROM economy WHERE user_id=? AND guild_id=?", user_id, guild_id)
        return row

    def _cur(self, cfg, amount):
        if not cfg:
            return f"🪙 {amount:,}"
        return f"{cfg['currency_emoji']} {amount:,} {cfg['currency_name']}"

    @app_commands.command(name="balance", description="Check your or another user's balance")
    async def balance_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        embed = await self._balance_impl(interaction.guild_id, member or interaction.user)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="balance", aliases=["bal", "money"], help="Check your balance.")
    async def balance_prefix(self, ctx, member: discord.Member = None):
        embed = await self._balance_impl(ctx.guild.id, member or ctx.author)
        await ctx.send(embed=embed)

    async def _balance_impl(self, guild_id, target):
        eco = await self._get_eco(target.id, guild_id)
        cfg = await get_guild_config(guild_id)
        embed = discord.Embed(title=f"💰 Balance — {target.display_name}", color=discord.Color.gold())
        embed.add_field(name="👛 Wallet", value=self._cur(cfg, eco["wallet"]), inline=True)
        embed.add_field(name="🏦 Bank",   value=self._cur(cfg, eco["bank"]),   inline=True)
        embed.add_field(name="💎 Total",  value=self._cur(cfg, eco["wallet"] + eco["bank"]), inline=True)
        if eco["job"]:
            embed.add_field(name="💼 Job", value=eco["job"].title(), inline=True)
        return embed

    @app_commands.command(name="daily", description="Claim your daily reward")
    async def daily_slash(self, interaction: discord.Interaction):
        embed = await self._daily_impl(interaction.guild_id, interaction.user)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="daily", help="Claim your daily reward.")
    async def daily_prefix(self, ctx):
        embed = await self._daily_impl(ctx.guild.id, ctx.author)
        await ctx.send(embed=embed)

    async def _daily_impl(self, guild_id, user):
        eco = await self._get_eco(user.id, guild_id)
        cfg = await get_guild_config(guild_id)
        now = int(time.time())
        if eco["last_daily"] and now - eco["last_daily"] < 86400:
            remaining = 86400 - (now - eco["last_daily"])
            return build_error_embed(f"Daily already claimed. Next: {format_duration(remaining)}")
        streak = eco["daily_streak"]
        if eco["last_daily"] and now - eco["last_daily"] < 172800:
            streak += 1
        else:
            streak = 1
        base   = 200
        bonus  = min(streak * 10, 500)
        reward = base + bonus
        await db_execute("UPDATE economy SET wallet=wallet+?, daily_streak=?, last_daily=?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
                         reward, streak, now, reward, user.id, guild_id)
        embed = discord.Embed(title="📅 Daily Reward", color=discord.Color.gold())
        embed.add_field(name="Reward", value=self._cur(cfg, reward), inline=True)
        embed.add_field(name="Streak", value=f"🔥 {streak} days",   inline=True)
        if bonus > 0:
            embed.add_field(name="Streak Bonus", value=self._cur(cfg, bonus), inline=True)
        return embed

    @app_commands.command(name="weekly", description="Claim your weekly reward")
    async def weekly_slash(self, interaction: discord.Interaction):
        embed = await self._weekly_impl(interaction.guild_id, interaction.user)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="weekly", help="Claim your weekly reward.")
    async def weekly_prefix(self, ctx):
        embed = await self._weekly_impl(ctx.guild.id, ctx.author)
        await ctx.send(embed=embed)

    async def _weekly_impl(self, guild_id, user):
        eco = await self._get_eco(user.id, guild_id)
        cfg = await get_guild_config(guild_id)
        now = int(time.time())
        if eco["last_weekly"] and now - eco["last_weekly"] < 604800:
            remaining = 604800 - (now - eco["last_weekly"])
            return build_error_embed(f"Weekly already claimed. Next: {format_duration(remaining)}")
        reward = 1500
        await db_execute("UPDATE economy SET wallet=wallet+?, last_weekly=?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
                         reward, now, reward, user.id, guild_id)
        return discord.Embed(title="📅 Weekly Reward", description=f"You claimed {self._cur(cfg, reward)}!", color=discord.Color.gold())

    @app_commands.command(name="monthly", description="Claim your monthly reward")
    async def monthly_slash(self, interaction: discord.Interaction):
        embed = await self._monthly_impl(interaction.guild_id, interaction.user)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="monthly", help="Claim your monthly reward.")
    async def monthly_prefix(self, ctx):
        embed = await self._monthly_impl(ctx.guild.id, ctx.author)
        await ctx.send(embed=embed)

    async def _monthly_impl(self, guild_id, user):
        eco = await self._get_eco(user.id, guild_id)
        cfg = await get_guild_config(guild_id)
        now = int(time.time())
        if eco["last_monthly"] and now - eco["last_monthly"] < 2592000:
            remaining = 2592000 - (now - eco["last_monthly"])
            return build_error_embed(f"Monthly already claimed. Next: {format_duration(remaining)}")
        reward = 10000
        await db_execute("UPDATE economy SET wallet=wallet+?, last_monthly=?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
                         reward, now, reward, user.id, guild_id)
        return discord.Embed(title="📅 Monthly Reward", description=f"You claimed {self._cur(cfg, reward)}! 🎉", color=discord.Color.gold())

    @app_commands.command(name="work", description="Work your job to earn money")
    async def work_slash(self, interaction: discord.Interaction):
        embed = await self._work_impl(interaction.guild_id, interaction.user)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="work", help="Work to earn money.")
    async def work_prefix(self, ctx):
        embed = await self._work_impl(ctx.guild.id, ctx.author)
        await ctx.send(embed=embed)

    async def _work_impl(self, guild_id, user):
        eco = await self._get_eco(user.id, guild_id)
        cfg = await get_guild_config(guild_id)
        now = int(time.time())
        if eco["last_work"] and now - eco["last_work"] < 3600:
            remaining = 3600 - (now - eco["last_work"])
            return build_error_embed(f"You need to rest. Next work: {format_duration(remaining)}")
        job      = eco["job"] or "freelancer"
        job_data = JOBS.get(job, {"salary": (100, 300), "description": "Do odd jobs"})
        lo, hi   = job_data["salary"]
        earned   = random.randint(lo, hi)
        await db_execute("UPDATE economy SET wallet=wallet+?, last_work=?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
                         earned, now, earned, user.id, guild_id)
        scenarios = [
            f"You completed a project and earned {self._cur(cfg, earned)}!",
            f"Hard work pays off! You made {self._cur(cfg, earned)}.",
            f"Another day, another dollar! Earned {self._cur(cfg, earned)}.",
        ]
        return discord.Embed(title=f"💼 Work — {job.title()}", description=random.choice(scenarios), color=discord.Color.green())

    @app_commands.command(name="jobs", description="View available jobs")
    async def jobs_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(title="💼 Available Jobs", color=discord.Color.blurple())
        for name, data in JOBS.items():
            lo, hi = data["salary"]
            embed.add_field(name=f"**{name.title()}**", value=f"Salary: {lo:,}–{hi:,} | {data['description']}", inline=False)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="jobs", help="View available jobs.")
    async def jobs_prefix(self, ctx):
        embed = discord.Embed(title="💼 Available Jobs", color=discord.Color.blurple())
        for name, data in JOBS.items():
            lo, hi = data["salary"]
            embed.add_field(name=f"**{name.title()}**", value=f"Salary: {lo:,}–{hi:,} | {data['description']}", inline=False)
        await ctx.send(embed=embed)

    @app_commands.command(name="apply", description="Apply for a job")
    async def apply_slash(self, interaction: discord.Interaction, job: str):
        embed = await self._apply_impl(interaction.guild_id, interaction.user, job)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="apply", help="Apply for a job. Usage: apply <job>")
    async def apply_prefix(self, ctx, job: str):
        embed = await self._apply_impl(ctx.guild.id, ctx.author, job)
        await ctx.send(embed=embed)

    async def _apply_impl(self, guild_id, user, job):
        job = job.lower()
        if job not in JOBS:
            return build_error_embed(f"Job not found. Use `jobs` to see available jobs.")
        await db_execute("UPDATE economy SET job=? WHERE user_id=? AND guild_id=?", job, user.id, guild_id)
        return build_success_embed(f"You got the job! You are now a **{job.title()}**.")

    @app_commands.command(name="deposit", description="Deposit money into your bank")
    async def deposit_slash(self, interaction: discord.Interaction, amount: str):
        embed = await self._deposit_impl(interaction.guild_id, interaction.user, amount, True)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="deposit", aliases=["dep"], help="Deposit to bank. Usage: deposit <amount|all>")
    async def deposit_prefix(self, ctx, amount: str):
        embed = await self._deposit_impl(ctx.guild.id, ctx.author, amount, True)
        await ctx.send(embed=embed)

    @app_commands.command(name="withdraw", description="Withdraw money from your bank")
    async def withdraw_slash(self, interaction: discord.Interaction, amount: str):
        embed = await self._deposit_impl(interaction.guild_id, interaction.user, amount, False)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="withdraw", aliases=["with"], help="Withdraw from bank. Usage: withdraw <amount|all>")
    async def withdraw_prefix(self, ctx, amount: str):
        embed = await self._deposit_impl(ctx.guild.id, ctx.author, amount, False)
        await ctx.send(embed=embed)

    async def _deposit_impl(self, guild_id, user, amount_str, is_deposit):
        eco = await self._get_eco(user.id, guild_id)
        cfg = await get_guild_config(guild_id)
        try:
            actual = (eco["wallet"] if is_deposit else eco["bank"]) if amount_str.lower() == "all" else int(amount_str)
        except ValueError:
            return build_error_embed("Invalid amount.")
        source = eco["wallet"] if is_deposit else eco["bank"]
        if actual <= 0 or actual > source:
            return build_error_embed("Invalid amount.")
        if is_deposit:
            await db_execute("UPDATE economy SET wallet=wallet-?, bank=bank+? WHERE user_id=? AND guild_id=?", actual, actual, user.id, guild_id)
            return build_success_embed(f"Deposited {self._cur(cfg, actual)} to your bank.")
        else:
            await db_execute("UPDATE economy SET wallet=wallet+?, bank=bank-? WHERE user_id=? AND guild_id=?", actual, actual, user.id, guild_id)
            return build_success_embed(f"Withdrew {self._cur(cfg, actual)} from your bank.")

    @app_commands.command(name="pay", description="Pay another user")
    async def pay_slash(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        embed = await self._pay_impl(interaction.guild_id, interaction.user, member, amount)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="pay", help="Pay a user. Usage: pay <member> <amount>")
    async def pay_prefix(self, ctx, member: discord.Member, amount: int):
        embed = await self._pay_impl(ctx.guild.id, ctx.author, member, amount)
        await ctx.send(embed=embed)

    async def _pay_impl(self, guild_id, payer, recipient, amount):
        if amount <= 0:
            return build_error_embed("Amount must be positive.")
        if recipient == payer:
            return build_error_embed("Cannot pay yourself.")
        eco = await self._get_eco(payer.id, guild_id)
        cfg = await get_guild_config(guild_id)
        if eco["wallet"] < amount:
            return build_error_embed("Insufficient funds.")
        await db_execute("UPDATE economy SET wallet=wallet-? WHERE user_id=? AND guild_id=?", amount, payer.id, guild_id)
        await self._get_eco(recipient.id, guild_id)
        await db_execute("UPDATE economy SET wallet=wallet+? WHERE user_id=? AND guild_id=?", amount, recipient.id, guild_id)
        return build_success_embed(f"Paid {self._cur(cfg, amount)} to {recipient.mention}.")

    @app_commands.command(name="leaderboard", description="View the economy leaderboard")
    async def leaderboard_slash(self, interaction: discord.Interaction):
        embed = await self._leaderboard_impl(interaction.guild)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb", "top-eco"], help="Economy leaderboard.")
    async def leaderboard_prefix(self, ctx):
        embed = await self._leaderboard_impl(ctx.guild)
        await ctx.send(embed=embed)

    async def _leaderboard_impl(self, guild):
        rows   = await db_fetch("SELECT user_id, wallet+bank as total FROM economy WHERE guild_id=? ORDER BY total DESC LIMIT 10", guild.id)
        cfg    = await get_guild_config(guild.id)
        embed  = discord.Embed(title="🏆 Economy Leaderboard", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        desc   = ""
        for i, row in enumerate(rows):
            member = guild.get_member(row["user_id"])
            name   = member.display_name if member else f"User {row['user_id']}"
            desc  += f"{medals[i]} **{name}** — {self._cur(cfg, row['total'])}\n"
        embed.description = desc or "No data yet."
        return embed

    @app_commands.command(name="shop", description="View the server shop")
    async def shop_slash(self, interaction: discord.Interaction):
        embed = await self._shop_impl(interaction.guild_id)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="shop", help="View the server shop.")
    async def shop_prefix(self, ctx):
        embed = await self._shop_impl(ctx.guild.id)
        await ctx.send(embed=embed)

    async def _shop_impl(self, guild_id):
        rows = await db_fetch("SELECT * FROM shop WHERE guild_id=? AND enabled=1 ORDER BY price", guild_id)
        cfg  = await get_guild_config(guild_id)
        embed = discord.Embed(title="🛒 Server Shop", color=discord.Color.blurple())
        if not rows:
            embed.description = "The shop is empty."
        else:
            for item in rows:
                stock = "∞" if item["stock"] == -1 else str(item["stock"])
                embed.add_field(
                    name=f"{item['emoji']} {item['name']} — {self._cur(cfg, item['price'])}",
                    value=f"{item['description'] or 'No description'} | Stock: {stock}",
                    inline=False,
                )
        return embed

    @app_commands.command(name="buy", description="Buy an item from the shop")
    async def buy_slash(self, interaction: discord.Interaction, item_id: str):
        embed = await self._buy_impl(interaction.guild, interaction.user, item_id)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="buy", help="Buy an item. Usage: buy <item_id>")
    async def buy_prefix(self, ctx, item_id: str):
        embed = await self._buy_impl(ctx.guild, ctx.author, item_id)
        await ctx.send(embed=embed)

    async def _buy_impl(self, guild, user, item_id):
        item = await db_fetchone("SELECT * FROM shop WHERE guild_id=? AND item_id=? AND enabled=1", guild.id, item_id)
        if not item:
            return build_error_embed("Item not found.")
        eco = await self._get_eco(user.id, guild.id)
        cfg = await get_guild_config(guild.id)
        if eco["wallet"] < item["price"]:
            return build_error_embed(f"Insufficient funds. Need {self._cur(cfg, item['price'])}.")
        if item["stock"] == 0:
            return build_error_embed("Out of stock.")
        await db_execute("UPDATE economy SET wallet=wallet-?, total_spent=total_spent+? WHERE user_id=? AND guild_id=?",
                         item["price"], item["price"], user.id, guild.id)
        if item["stock"] > 0:
            await db_execute("UPDATE shop SET stock=stock-1 WHERE item_id=? AND guild_id=?", item["item_id"], guild.id)
        await db_execute("INSERT INTO inventory (user_id, guild_id, item_id) VALUES (?,?,?)", user.id, guild.id, item["item_id"])
        if item["type"] == "role" and item["role_id"]:
            role = guild.get_role(item["role_id"])
            if role:
                await user.add_roles(role, reason=f"Shop purchase: {item['name']}")
        return build_success_embed(f"Purchased **{item['emoji']} {item['name']}** for {self._cur(cfg, item['price'])}!")

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory_slash(self, interaction: discord.Interaction):
        embed = await self._inventory_impl(interaction.guild_id, interaction.user)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="inventory", aliases=["inv"], help="View your inventory.")
    async def inventory_prefix(self, ctx):
        embed = await self._inventory_impl(ctx.guild.id, ctx.author)
        await ctx.send(embed=embed)

    async def _inventory_impl(self, guild_id, user):
        rows = await db_fetch(
            "SELECT i.*, s.name, s.emoji, s.description FROM inventory i LEFT JOIN shop s ON i.item_id = s.item_id WHERE i.user_id=? AND i.guild_id=?",
            user.id, guild_id,
        )
        embed = discord.Embed(title="🎒 Your Inventory", color=discord.Color.blurple())
        if not rows:
            embed.description = "Your inventory is empty."
        else:
            for item in rows:
                name  = item["name"]  or item["item_id"]
                emoji = item["emoji"] or "📦"
                embed.add_field(name=f"{emoji} {name}", value=f"Qty: {item['quantity']}", inline=True)
        return embed

    @app_commands.command(name="gamble", description="Gamble your coins at the casino")
    async def gamble_slash(self, interaction: discord.Interaction, amount: int):
        embed = await self._gamble_impl(interaction.guild_id, interaction.user, amount)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="gamble", aliases=["casino", "bet"], help="Gamble coins. Usage: gamble <amount>")
    async def gamble_prefix(self, ctx, amount: int):
        embed = await self._gamble_impl(ctx.guild.id, ctx.author, amount)
        await ctx.send(embed=embed)

    async def _gamble_impl(self, guild_id, user, amount):
        eco = await self._get_eco(user.id, guild_id)
        cfg = await get_guild_config(guild_id)
        if amount <= 0 or amount > eco["wallet"]:
            return build_error_embed("Invalid amount.")
        roll = random.random()
        if roll < 0.47:
            multiplier = random.choice([1.5, 2.0, 2.5, 3.0])
            winnings   = int(amount * multiplier)
            profit     = winnings - amount
            await db_execute("UPDATE economy SET wallet=wallet+? WHERE user_id=? AND guild_id=?", profit, user.id, guild_id)
            return discord.Embed(title="🎰 You Won!",
                                 description=f"You bet {self._cur(cfg, amount)} and won {self._cur(cfg, winnings)}! ({multiplier}x)",
                                 color=discord.Color.green())
        else:
            await db_execute("UPDATE economy SET wallet=wallet-? WHERE user_id=? AND guild_id=?", amount, user.id, guild_id)
            return discord.Embed(title="🎰 You Lost",
                                 description=f"You lost {self._cur(cfg, amount)}. Better luck next time!",
                                 color=discord.Color.red())

    @app_commands.command(name="fish", description="Go fishing for coins")
    async def fish_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await asyncio.sleep(2)
        embed = await self._fish_impl(interaction.guild_id, interaction.user)
        await interaction.followup.send(embed=embed)

    @commands.command(name="fish", help="Go fishing for coins.")
    async def fish_prefix(self, ctx):
        msg = await ctx.send("🎣 Casting your line...")
        await asyncio.sleep(2)
        embed = await self._fish_impl(ctx.guild.id, ctx.author)
        await msg.edit(content=None, embed=embed)

    async def _fish_impl(self, guild_id, user):
        cfg = await get_guild_config(guild_id)
        fish_table = [
            ("🐟 Small Fish",    50,   200,  0.40),
            ("🐠 Tropical Fish", 150,  400,  0.25),
            ("🐡 Pufferfish",    100,  300,  0.20),
            ("🦈 Shark",         500,  1000, 0.10),
            ("🦞 Lobster",       800,  1500, 0.04),
            ("💎 Diamond Fish",  2000, 5000, 0.01),
        ]
        roll       = random.random()
        cumulative = 0
        caught     = fish_table[0]
        for fish in fish_table:
            cumulative += fish[3]
            if roll < cumulative:
                caught = fish
                break
        reward = random.randint(caught[1], caught[2])
        await db_execute("UPDATE economy SET wallet=wallet+?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
                         reward, reward, user.id, guild_id)
        return discord.Embed(title="🎣 Fishing",
                             description=f"You caught a {caught[0]}!\nYou earned {self._cur(cfg, reward)}!",
                             color=discord.Color.blue())

    @app_commands.command(name="mine", description="Mine for resources and coins")
    async def mine_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await asyncio.sleep(2)
        embed = await self._mine_impl(interaction.guild_id, interaction.user)
        await interaction.followup.send(embed=embed)

    @commands.command(name="mine", help="Mine for coins.")
    async def mine_prefix(self, ctx):
        msg = await ctx.send("⛏️ Mining...")
        await asyncio.sleep(2)
        embed = await self._mine_impl(ctx.guild.id, ctx.author)
        await msg.edit(content=None, embed=embed)

    async def _mine_impl(self, guild_id, user):
        cfg = await get_guild_config(guild_id)
        mine_table = [
            ("🪨 Stone",    10,  50,   0.40),
            ("⚙️ Iron",     80,  150,  0.25),
            ("💛 Gold",     200, 500,  0.20),
            ("💎 Diamond",  500, 1500, 0.10),
            ("💠 Crystal",  1000, 3000, 0.04),
            ("🌟 Stardust", 3000, 8000, 0.01),
        ]
        roll       = random.random()
        cumulative = 0
        found      = mine_table[0]
        for item in mine_table:
            cumulative += item[3]
            if roll < cumulative:
                found = item
                break
        reward = random.randint(found[1], found[2])
        await db_execute("UPDATE economy SET wallet=wallet+?, total_earned=total_earned+? WHERE user_id=? AND guild_id=?",
                         reward, reward, user.id, guild_id)
        return discord.Embed(title="⛏️ Mining",
                             description=f"You found {found[0]}!\nYou earned {self._cur(cfg, reward)}!",
                             color=discord.Color.dark_grey())


# ============================================================
# SECTION: Leveling  (5 slash commands)
# ============================================================

class LevelingCog(commands.Cog, name="Leveling"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="rank", description="View your or another user's rank card")
    async def rank_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        await interaction.response.defer()
        embed, file = await self._rank_impl(interaction.guild, target)
        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    @commands.command(name="rank", help="View your rank card.")
    async def rank_prefix(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        embed, file = await self._rank_impl(ctx.guild, target)
        if file:
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

    async def _rank_impl(self, guild, target):
        row = await db_fetchone("SELECT * FROM levels WHERE user_id=? AND guild_id=?", target.id, guild.id)
        if not row:
            return build_info_embed("No rank yet", "This user hasn't chatted yet."), None
        current_level = row["level"]
        xp_needed     = self.bot._xp_for_level(current_level + 1)
        xp_current    = self.bot._xp_for_level(current_level)
        xp_progress   = row["xp"] - xp_current
        xp_for_next   = xp_needed - xp_current
        progress_pct  = min(xp_progress / max(xp_for_next, 1), 1.0)
        img   = await self._build_rank_card(target, current_level, row["xp"], xp_progress, xp_for_next, progress_pct, row["prestige"])
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_image(url="attachment://rank.png")
        return embed, discord.File(img, "rank.png")

    async def _build_rank_card(self, member, level, total_xp, xp_progress, xp_for_next, progress_pct, prestige):
        W, H = 800, 200
        img  = Image.new("RGBA", (W, H), (30, 30, 40, 255))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            r = int(30 + (50 - 30) * y / H)
            draw.rectangle([(0, y), (W, y + 1)], fill=(r, r, r + 20, 255))
        try:
            avatar_data = await member.display_avatar.replace(size=128, format="png").read()
            av   = Image.open(io.BytesIO(avatar_data)).resize((120, 120)).convert("RGBA")
            mask = Image.new("L", (120, 120), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 119, 119], fill=255)
            img.paste(av, (40, 40), mask)
        except Exception:
            draw.ellipse([40, 40, 159, 159], fill=(100, 100, 150, 255))
        try:
            font_large  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            font_small  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except Exception:
            font_large = font_medium = font_small = ImageFont.load_default()
        draw.text((200, 30), member.display_name[:20], font=font_large, fill=(255, 255, 255, 255))
        if prestige > 0:
            draw.text((200, 65), f"✦ Prestige {prestige}", font=font_medium, fill=(255, 215, 0, 255))
        draw.text((200, 95), f"Level {level} • {total_xp:,} XP total", font=font_medium, fill=(200, 200, 220, 255))
        bar_x, bar_y, bar_w, bar_h = 200, 130, 530, 24
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=12, fill=(60, 60, 80, 255))
        filled = int(bar_w * progress_pct)
        if filled > 0:
            draw.rounded_rectangle([bar_x, bar_y, bar_x + filled, bar_y + bar_h], radius=12, fill=(88, 101, 242, 255))
        draw.text((200, 160), f"{xp_progress:,} / {xp_for_next:,} XP", font=font_small, fill=(180, 180, 200, 255))
        lx, ly = 690, 90
        draw.ellipse([lx - 45, ly - 45, lx + 45, ly + 45], fill=(88, 101, 242, 255))
        draw.text((lx, ly), str(level), font=font_large, fill=(255, 255, 255, 255), anchor="mm")
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf

    @app_commands.command(name="top", description="View the XP leaderboard")
    async def top_slash(self, interaction: discord.Interaction):
        embed = await self._top_impl(interaction.guild)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="top", aliases=["xplb"], help="XP leaderboard.")
    async def top_prefix(self, ctx):
        embed = await self._top_impl(ctx.guild)
        await ctx.send(embed=embed)

    async def _top_impl(self, guild):
        rows   = await db_fetch("SELECT user_id, level, xp FROM levels WHERE guild_id=? ORDER BY xp DESC LIMIT 10", guild.id)
        embed  = discord.Embed(title="⭐ XP Leaderboard", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        desc   = ""
        for i, row in enumerate(rows):
            member = guild.get_member(row["user_id"])
            name   = member.display_name if member else f"User {row['user_id']}"
            desc  += f"{medals[i]} **{name}** — Level {row['level']} ({row['xp']:,} XP)\n"
        embed.description = desc or "No data yet."
        return embed

    @app_commands.command(name="setxp", description="Set a user's XP (admin only)")
    @app_commands.default_permissions(administrator=True)
    async def setxp_slash(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        new_level = self.bot._calc_level(xp)
        await db_execute(
            "INSERT INTO levels (user_id, guild_id, xp, level) VALUES (?,?,?,?) ON CONFLICT(user_id,guild_id) DO UPDATE SET xp=excluded.xp, level=excluded.level",
            member.id, interaction.guild_id, xp, new_level,
        )
        await interaction.response.send_message(embed=build_success_embed(f"Set {member.mention}'s XP to {xp:,} (Level {new_level})."))

    @commands.command(name="setxp", help="Set a user's XP. Usage: setxp <member> <xp>")
    @commands.has_permissions(administrator=True)
    async def setxp_prefix(self, ctx, member: discord.Member, xp: int):
        new_level = self.bot._calc_level(xp)
        await db_execute(
            "INSERT INTO levels (user_id, guild_id, xp, level) VALUES (?,?,?,?) ON CONFLICT(user_id,guild_id) DO UPDATE SET xp=excluded.xp, level=excluded.level",
            member.id, ctx.guild.id, xp, new_level,
        )
        await ctx.send(embed=build_success_embed(f"Set {member.mention}'s XP to {xp:,} (Level {new_level})."))

    @app_commands.command(name="role-reward-add", description="Add a role reward for reaching a level")
    @app_commands.default_permissions(administrator=True)
    async def rr_level_slash(self, interaction: discord.Interaction, level: int, role: discord.Role,
                              remove_previous: bool = False):
        await db_execute("INSERT OR REPLACE INTO role_rewards (guild_id, level, role_id, remove_prev) VALUES (?,?,?,?)",
                         interaction.guild_id, level, role.id, int(remove_previous))
        await interaction.response.send_message(embed=build_success_embed(f"Added {role.mention} as reward for Level {level}."))

    @commands.command(name="role-reward-add", aliases=["rraward"], help="Add a level role reward. Usage: role-reward-add <level> <@role>")
    @commands.has_permissions(administrator=True)
    async def rr_level_prefix(self, ctx, level: int, role: discord.Role, remove_previous: bool = False):
        await db_execute("INSERT OR REPLACE INTO role_rewards (guild_id, level, role_id, remove_prev) VALUES (?,?,?,?)",
                         ctx.guild.id, level, role.id, int(remove_previous))
        await ctx.send(embed=build_success_embed(f"Added {role.mention} as reward for Level {level}."))

    @app_commands.command(name="prestige", description="Prestige your level (requires Level 50, resets to 0)")
    async def prestige_slash(self, interaction: discord.Interaction):
        embed = await self._prestige_impl(interaction.guild_id, interaction.user)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="prestige", help="Prestige your level (requires Level 50).")
    async def prestige_prefix(self, ctx):
        embed = await self._prestige_impl(ctx.guild.id, ctx.author)
        await ctx.send(embed=embed)

    async def _prestige_impl(self, guild_id, user):
        row = await db_fetchone("SELECT * FROM levels WHERE user_id=? AND guild_id=?", user.id, guild_id)
        if not row or row["level"] < 50:
            return build_error_embed("You need to be Level 50 to prestige.")
        await db_execute("UPDATE levels SET xp=0, level=0, prestige=prestige+1 WHERE user_id=? AND guild_id=?", user.id, guild_id)
        return discord.Embed(title="✦ Prestige Achieved!",
                             description=f"You prestiged! You are now **Prestige {row['prestige'] + 1}**. Your level has reset.",
                             color=discord.Color.gold())


# ============================================================
# SECTION: Music  (8 slash commands)
# ============================================================

class MusicCog(commands.Cog, name="Music"):
    def __init__(self, bot: DiscordBot):
        self.bot    = bot
        self.yt_opts = {
            "format": "bestaudio/best", "quiet": True, "no_warnings": True,
            "default_search": "ytsearch", "source_address": "0.0.0.0",
        }

    async def _get_vc(self, guild, user):
        if user.voice:
            vc = guild.voice_client
            if not vc:
                vc = await user.voice.channel.connect()
            elif vc.channel != user.voice.channel:
                await vc.move_to(user.voice.channel)
            return vc
        return None

    async def _extract_info(self, query):
        loop = asyncio.get_event_loop()
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(self.yt_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
                if "entries" in info:
                    info = info["entries"][0]
                return info
        except Exception as e:
            log.error(f"Music extract error: {e}")
            return None

    async def _play_next(self, guild, vc):
        queue = self.bot.music_queues[guild.id]
        if not queue:
            return
        track = queue.pop(0)
        self.bot.music_current[guild.id] = track
        try:
            source = discord.FFmpegPCMAudio(track["url"],
                                            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                                            options="-vn")
            source = discord.PCMVolumeTransformer(source, volume=0.5)
            vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
                self._play_next(guild, vc), self.bot.loop
            ).result() if not e else log.error(f"Music error: {e}"))
        except Exception as e:
            log.error(f"Play error: {e}")

    @app_commands.command(name="play", description="Play a song from YouTube")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        vc = await self._get_vc(interaction.guild, interaction.user)
        if not vc:
            await interaction.response.send_message(embed=build_error_embed("Join a voice channel first."), ephemeral=True)
            return
        await interaction.response.defer()
        info = await self._extract_info(query)
        if not info:
            await interaction.followup.send(embed=build_error_embed("Could not find that song."))
            return
        embed = await self._queue_track(interaction.guild_id, vc, info, interaction.user.mention)
        await interaction.followup.send(embed=embed)

    @commands.command(name="play", aliases=["p"], help="Play a song. Usage: play <query>")
    async def play_prefix(self, ctx, *, query: str):
        vc = await self._get_vc(ctx.guild, ctx.author)
        if not vc:
            await ctx.send(embed=build_error_embed("Join a voice channel first."))
            return
        msg  = await ctx.send("🔍 Searching...")
        info = await self._extract_info(query)
        if not info:
            await msg.edit(content=None, embed=build_error_embed("Could not find that song."))
            return
        embed = await self._queue_track(ctx.guild.id, vc, info, ctx.author.mention)
        await msg.edit(content=None, embed=embed)

    async def _queue_track(self, guild_id, vc, info, requester):
        track = {
            "title":     info.get("title", "Unknown"),
            "url":       info.get("url") or info.get("webpage_url"),
            "webpage":   info.get("webpage_url", ""),
            "duration":  info.get("duration", 0),
            "thumbnail": info.get("thumbnail", ""),
            "requester": requester,
        }
        self.bot.music_queues[guild_id].append(track)
        if not vc.is_playing():
            await self._play_next(vc.guild, vc)
            embed = discord.Embed(title="▶️ Now Playing", color=discord.Color.green())
        else:
            pos   = len(self.bot.music_queues[guild_id])
            embed = discord.Embed(title=f"📋 Added to Queue (#{pos})", color=discord.Color.blurple())
        embed.add_field(name="Track",        value=f"[{track['title']}]({track['webpage']})")
        embed.add_field(name="Requested by", value=track["requester"])
        if track["duration"]:
            embed.add_field(name="Duration", value=format_duration(track["duration"]))
        return embed

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message(embed=build_error_embed("Nothing is playing."), ephemeral=True)
            return
        vc.stop()
        await interaction.response.send_message(embed=build_success_embed("Skipped current track."))

    @commands.command(name="skip", aliases=["s"], help="Skip the current song.")
    async def skip_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if not vc or not vc.is_playing():
            await ctx.send(embed=build_error_embed("Nothing is playing."))
            return
        vc.stop()
        await ctx.send(embed=build_success_embed("Skipped current track."))

    @app_commands.command(name="stop", description="Stop music and clear the queue")
    async def stop_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            self.bot.music_queues[interaction.guild_id].clear()
            self.bot.music_current.pop(interaction.guild_id, None)
            await vc.disconnect()
        await interaction.response.send_message(embed=build_success_embed("Stopped music and cleared queue."))

    @commands.command(name="stop", help="Stop music and disconnect.")
    async def stop_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            self.bot.music_queues[ctx.guild.id].clear()
            self.bot.music_current.pop(ctx.guild.id, None)
            await vc.disconnect()
        await ctx.send(embed=build_success_embed("Stopped music and cleared queue."))

    @app_commands.command(name="queue", description="View the music queue and now playing")
    async def queue_slash(self, interaction: discord.Interaction):
        embed = self._queue_embed(interaction.guild_id)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="queue", aliases=["q", "nowplaying", "np"], help="View the music queue.")
    async def queue_prefix(self, ctx):
        embed = self._queue_embed(ctx.guild.id)
        await ctx.send(embed=embed)

    def _queue_embed(self, guild_id):
        current = self.bot.music_current.get(guild_id)
        queue   = self.bot.music_queues[guild_id]
        embed   = discord.Embed(title="🎵 Music Queue", color=discord.Color.blurple())
        if current:
            embed.add_field(name="▶️ Now Playing", value=f"[{current['title']}]({current['webpage']})", inline=False)
        if queue:
            q_text = "\n".join(f"`{i+1}.` [{t['title']}]({t['webpage']})" for i, t in enumerate(queue[:10]))
            embed.add_field(name=f"📋 Up Next ({len(queue)})", value=q_text, inline=False)
        else:
            embed.add_field(name="Queue", value="Empty", inline=False)
        return embed

    @app_commands.command(name="volume", description="Set the music volume (0-200)")
    async def volume_slash(self, interaction: discord.Interaction, level: int):
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message(embed=build_error_embed("Not playing."), ephemeral=True)
            return
        level = max(0, min(200, level))
        if hasattr(vc.source, "volume"):
            vc.source.volume = level / 100
        await interaction.response.send_message(embed=build_success_embed(f"Volume set to {level}%."))

    @commands.command(name="volume", aliases=["vol"], help="Set volume 0-200. Usage: volume <level>")
    async def volume_prefix(self, ctx, level: int):
        vc = ctx.guild.voice_client
        if not vc:
            await ctx.send(embed=build_error_embed("Not playing."))
            return
        level = max(0, min(200, level))
        if hasattr(vc.source, "volume"):
            vc.source.volume = level / 100
        await ctx.send(embed=build_success_embed(f"Volume set to {level}%."))

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message(embed=build_success_embed("Paused."))
        else:
            await interaction.response.send_message(embed=build_error_embed("Nothing is playing."), ephemeral=True)

    @commands.command(name="pause", help="Pause music.")
    async def pause_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send(embed=build_success_embed("Paused."))
        else:
            await ctx.send(embed=build_error_embed("Nothing is playing."))

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message(embed=build_success_embed("Resumed."))
        else:
            await interaction.response.send_message(embed=build_error_embed("Nothing is paused."), ephemeral=True)

    @commands.command(name="resume", help="Resume music.")
    async def resume_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send(embed=build_success_embed("Resumed."))
        else:
            await ctx.send(embed=build_error_embed("Nothing is paused."))

    @app_commands.command(name="shuffle", description="Shuffle the music queue")
    async def shuffle_slash(self, interaction: discord.Interaction):
        queue = self.bot.music_queues[interaction.guild_id]
        if not queue:
            await interaction.response.send_message(embed=build_error_embed("Queue is empty."), ephemeral=True)
            return
        random.shuffle(queue)
        await interaction.response.send_message(embed=build_success_embed("Queue shuffled!"))

    @commands.command(name="shuffle", help="Shuffle the music queue.")
    async def shuffle_prefix(self, ctx):
        queue = self.bot.music_queues[ctx.guild.id]
        if not queue:
            await ctx.send(embed=build_error_embed("Queue is empty."))
            return
        random.shuffle(queue)
        await ctx.send(embed=build_success_embed("Queue shuffled!"))


# ============================================================
# SECTION: Giveaways  (1 slash command)
# ============================================================

class GiveawayCog(commands.Cog, name="Giveaways"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="giveaway", description="Start a giveaway (action=start) or reroll winners (action=reroll)")
    @app_commands.describe(action="start or reroll", prize="Prize for the giveaway", duration="Duration e.g. 24h",
                           winners="Number of winners", giveaway_id="ID for reroll action")
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway_slash(self, interaction: discord.Interaction, action: str,
                              prize: str = None, duration: str = "24h",
                              winners: int = 1, channel: discord.TextChannel = None,
                              req_role: discord.Role = None, description: str = None,
                              giveaway_id: str = None):
        action = action.lower()
        if action == "start":
            embed = await self._giveaway_start(interaction.guild, interaction.user, prize, duration, winners, channel or interaction.channel, req_role, description)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif action == "reroll":
            embed = await self._giveaway_reroll(interaction.guild_id, giveaway_id)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=build_error_embed("Invalid action. Use: start, reroll"), ephemeral=True)

    @commands.command(name="giveaway", aliases=["gstart"], help="Start a giveaway. Usage: giveaway <duration> <winners> <prize>")
    @commands.has_permissions(manage_guild=True)
    async def giveaway_prefix(self, ctx, duration: str = "24h", winners: int = 1, *, prize: str = "Prize"):
        embed = await self._giveaway_start(ctx.guild, ctx.author, prize, duration, winners, ctx.channel, None, None)
        await ctx.send(embed=embed)

    @commands.command(name="greroll", help="Reroll a giveaway. Usage: greroll <giveaway_id>")
    @commands.has_permissions(manage_guild=True)
    async def greroll_prefix(self, ctx, giveaway_id: str):
        embed = await self._giveaway_reroll(ctx.guild.id, giveaway_id)
        await ctx.send(embed=embed)

    async def _giveaway_start(self, guild, host, prize, duration, winners, target_ch, req_role, description):
        if not prize:
            return build_error_embed("Please provide a prize.")
        secs = parse_duration(duration)
        if not secs:
            return build_error_embed("Invalid duration.")
        ends_at = int(time.time()) + secs
        g_id    = generate_id("GIVE")
        embed   = discord.Embed(title="🎉 GIVEAWAY",
                                description=f"**Prize:** {prize}\n{description or ''}\n\nClick 🎉 to enter!\n{f'**Required role:** {req_role.mention}' if req_role else ''}",
                                color=discord.Color.gold())
        embed.add_field(name="Winners",   value=str(winners),        inline=True)
        embed.add_field(name="Ends",      value=f"<t:{ends_at}:R>",  inline=True)
        embed.add_field(name="Hosted by", value=host.mention,        inline=True)
        embed.set_footer(text=f"Giveaway ID: {g_id}")
        view    = GiveawayView(self.bot, g_id)
        msg     = await target_ch.send(embed=embed, view=view)
        await db_execute(
            "INSERT INTO giveaways (giveaway_id, guild_id, channel_id, message_id, host_id, prize, description, winners_count, req_role, ends_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            g_id, guild.id, target_ch.id, msg.id, host.id, prize, description, winners,
            req_role.id if req_role else None, ends_at,
        )
        return build_success_embed(f"Giveaway started in {target_ch.mention}! ID: `{g_id}`")

    async def _giveaway_reroll(self, guild_id, giveaway_id):
        if not giveaway_id:
            return build_error_embed("Please provide a giveaway ID.")
        row = await db_fetchone("SELECT * FROM giveaways WHERE giveaway_id=? AND guild_id=?", giveaway_id, guild_id)
        if not row or row["status"] != "ended":
            return build_error_embed("Giveaway not found or still active.")
        entries = json.loads(row["entries"] or "[]")
        if not entries:
            return build_error_embed("No entries.")
        new_winners = random.sample(entries, min(row["winners_count"], len(entries)))
        mentions    = " ".join(f"<@{w}>" for w in new_winners)
        return build_success_embed(f"🎉 Rerolled winners: {mentions}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or not interaction.guild:
            return
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("give:"):
            return
        giveaway_id = custom_id.split(":")[1]
        row = await db_fetchone("SELECT * FROM giveaways WHERE giveaway_id=? AND status='active'", giveaway_id)
        if not row:
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return
        entries = json.loads(row["entries"] or "[]")
        user_id = interaction.user.id
        if row["req_role"]:
            role = interaction.guild.get_role(row["req_role"])
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(f"You need the {role.mention} role to enter!", ephemeral=True)
                return
        if user_id in entries:
            entries.remove(user_id)
            await db_execute("UPDATE giveaways SET entries=? WHERE giveaway_id=?", json.dumps(entries), giveaway_id)
            await interaction.response.send_message("❌ You left the giveaway.", ephemeral=True)
        else:
            entries.append(user_id)
            await db_execute("UPDATE giveaways SET entries=? WHERE giveaway_id=?", json.dumps(entries), giveaway_id)
            await interaction.response.send_message("🎉 You entered the giveaway!", ephemeral=True)


class GiveawayView(discord.ui.View):
    def __init__(self, bot, giveaway_id):
        super().__init__(timeout=None)
        self.bot         = bot
        self.giveaway_id = giveaway_id
        btn = discord.ui.Button(label="Enter Giveaway", emoji="🎉",
                                style=discord.ButtonStyle.primary,
                                custom_id=f"give:{giveaway_id}")
        self.add_item(btn)


# ============================================================
# SECTION: Polls  (1 slash command)
# ============================================================

class PollCog(commands.Cog, name="Polls"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a poll or view results (provide poll_id to see results)")
    async def poll_slash(self, interaction: discord.Interaction,
                         question: str = None, option1: str = None, option2: str = None,
                         option3: str = None, option4: str = None, option5: str = None,
                         anonymous: bool = False, duration: str = None,
                         poll_id: str = None):
        if poll_id:
            embed = await self._poll_results_impl(interaction.guild_id, poll_id)
            await interaction.response.send_message(embed=embed)
            return
        if not question or not option1 or not option2:
            await interaction.response.send_message(embed=build_error_embed("Provide a question and at least 2 options."), ephemeral=True)
            return
        options = [o for o in [option1, option2, option3, option4, option5] if o]
        await self._create_poll(interaction, question, options, anonymous, duration)

    @commands.command(name="poll", help="Create a poll. Usage: poll <question> | opt1 | opt2 | opt3")
    async def poll_prefix(self, ctx, *, args: str):
        parts    = [p.strip() for p in args.split("|")]
        question = parts[0]
        options  = parts[1:] if len(parts) > 1 else []
        if len(options) < 2:
            await ctx.send(embed=build_error_embed("Provide at least 2 options separated by `|`. Example: `poll Question | Option 1 | Option 2`"))
            return
        poll_id = generate_id("POLL")
        ends_at = None
        embed   = discord.Embed(title=f"📊 {question}", color=discord.Color.blurple())
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        embed.description = "\n".join(f"{number_emojis[i]} {opt}" for i, opt in enumerate(options[:5]))
        view = PollView(self.bot, poll_id, options[:5], False)
        msg  = await ctx.send(embed=embed, view=view)
        await db_execute(
            "INSERT INTO polls (poll_id, guild_id, channel_id, message_id, creator_id, question, options, anonymous, ends_at) VALUES (?,?,?,?,?,?,?,?,?)",
            poll_id, ctx.guild.id, ctx.channel.id, msg.id, ctx.author.id, question, json.dumps(options[:5]), 0, ends_at,
        )

    @commands.command(name="poll-results", aliases=["pollresults"], help="View poll results. Usage: poll-results <poll_id>")
    async def poll_results_prefix(self, ctx, poll_id: str):
        embed = await self._poll_results_impl(ctx.guild.id, poll_id)
        await ctx.send(embed=embed)

    async def _create_poll(self, interaction, question, options, anonymous, duration):
        poll_id = generate_id("POLL")
        ends_at = int(time.time()) + parse_duration(duration) if duration else None
        embed   = discord.Embed(title=f"📊 {question}", color=discord.Color.blurple())
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        embed.description = "\n".join(f"{number_emojis[i]} {opt}" for i, opt in enumerate(options))
        if anonymous:
            embed.set_footer(text="🔒 Anonymous poll")
        if ends_at:
            embed.add_field(name="Ends", value=f"<t:{ends_at}:R>")
        view = PollView(self.bot, poll_id, options, anonymous)
        await interaction.response.send_message(embed=embed, view=view)
        msg  = await interaction.original_response()
        await db_execute(
            "INSERT INTO polls (poll_id, guild_id, channel_id, message_id, creator_id, question, options, anonymous, ends_at) VALUES (?,?,?,?,?,?,?,?,?)",
            poll_id, interaction.guild_id, interaction.channel_id, msg.id,
            interaction.user.id, question, json.dumps(options), int(anonymous), ends_at,
        )

    async def _poll_results_impl(self, guild_id, poll_id):
        row = await db_fetchone("SELECT * FROM polls WHERE poll_id=? AND guild_id=?", poll_id, guild_id)
        if not row:
            return build_error_embed("Poll not found.")
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
        return embed

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or not interaction.guild:
            return
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("poll:"):
            return
        parts = custom_id.split(":")
        if len(parts) < 3:
            return
        poll_id    = parts[1]
        option_idx = parts[2]
        row = await db_fetchone("SELECT * FROM polls WHERE poll_id=? AND status='active'", poll_id)
        if not row:
            await interaction.response.send_message("This poll has ended.", ephemeral=True)
            return
        votes   = json.loads(row["votes"] or "{}")
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
            options  = json.loads(row["options"])
            opt_name = options[int(option_idx)] if int(option_idx) < len(options) else "option"
            await interaction.response.send_message(f"Voted for **{opt_name}**!", ephemeral=True)
        await db_execute("UPDATE polls SET votes=? WHERE poll_id=?", json.dumps(votes), poll_id)


class PollView(discord.ui.View):
    def __init__(self, bot, poll_id, options, anonymous):
        super().__init__(timeout=None)
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for i, opt in enumerate(options[:5]):
            btn = discord.ui.Button(label=opt[:80], emoji=number_emojis[i],
                                    style=discord.ButtonStyle.secondary,
                                    custom_id=f"poll:{poll_id}:{i}")
            self.add_item(btn)


# ============================================================
# SECTION: Suggestions  (1 slash command)
# ============================================================

class SuggestionCog(commands.Cog, name="Suggestions"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="suggest", description="Submit a suggestion. Mods: use review=True to review one.")
    async def suggest_slash(self, interaction: discord.Interaction, suggestion: str = None,
                             review: bool = False, suggestion_id: str = None,
                             status: str = "approved", note: str = None):
        if review:
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(embed=build_error_embed("Requires Manage Guild permission."), ephemeral=True)
                return
            embed = await self._review_impl(interaction.guild, suggestion_id, status, interaction.user, note)
            await interaction.response.send_message(embed=embed)
        else:
            if not suggestion:
                await interaction.response.send_message(embed=build_error_embed("Please provide a suggestion."), ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            embed = await self._suggest_impl(interaction.guild, interaction.channel, interaction.user, suggestion)
            await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.command(name="suggest", help="Submit a suggestion. Usage: suggest <idea>")
    async def suggest_prefix(self, ctx, *, suggestion: str):
        embed = await self._suggest_impl(ctx.guild, ctx.channel, ctx.author, suggestion)
        await ctx.send(embed=embed)

    @commands.command(name="suggestion-review", aliases=["sreview"], help="Review a suggestion. Usage: suggestion-review <id> <status> [note]")
    @commands.has_permissions(manage_guild=True)
    async def suggestion_review_prefix(self, ctx, suggestion_id: str, status: str, *, note: str = None):
        embed = await self._review_impl(ctx.guild, suggestion_id, status, ctx.author, note)
        await ctx.send(embed=embed)

    async def _suggest_impl(self, guild, channel, user, suggestion):
        s_id     = generate_id("SUGG")
        category = await self.bot.ai.categorize_suggestion(suggestion)
        embed    = discord.Embed(title=f"💡 Suggestion #{s_id}", description=suggestion, color=discord.Color.blurple())
        embed.add_field(name="Category", value=category.title(), inline=True)
        embed.add_field(name="Author",   value=user.mention,     inline=True)
        embed.add_field(name="Status",   value="⏳ Pending",      inline=True)
        view = SuggestionView(self.bot, s_id)
        msg  = await channel.send(embed=embed, view=view)
        await db_execute(
            "INSERT INTO suggestions (suggestion_id, guild_id, channel_id, message_id, user_id, content, category) VALUES (?,?,?,?,?,?,?)",
            s_id, guild.id, channel.id, msg.id, user.id, suggestion, category,
        )
        return build_success_embed("Your suggestion has been submitted!")

    async def _review_impl(self, guild, suggestion_id, status, mod, note):
        valid = {"approved", "rejected", "implemented", "considering"}
        if status not in valid:
            return build_error_embed(f"Status must be: {', '.join(valid)}")
        row = await db_fetchone("SELECT * FROM suggestions WHERE suggestion_id=? AND guild_id=?", suggestion_id, guild.id)
        if not row:
            return build_error_embed("Suggestion not found.")
        await db_execute("UPDATE suggestions SET status=?, reviewer_id=?, reviewer_note=?, updated_at=? WHERE suggestion_id=?",
                         status, mod.id, note, int(time.time()), suggestion_id)
        icons  = {"approved": "✅", "rejected": "❌", "implemented": "🚀", "considering": "🤔"}
        colors = {"approved": discord.Color.green(), "rejected": discord.Color.red(),
                  "implemented": discord.Color.gold(), "considering": discord.Color.orange()}
        channel = self.bot.get_channel(row["channel_id"])
        if channel and row["message_id"]:
            try:
                msg   = await channel.fetch_message(row["message_id"])
                embed = msg.embeds[0] if msg.embeds else discord.Embed()
                for i, field in enumerate(embed.fields):
                    if field.name == "Status":
                        embed.set_field_at(i, name="Status", value=f"{icons[status]} {status.title()}", inline=True)
                        break
                embed.color = colors[status]
                if note:
                    embed.add_field(name="Review Note", value=note, inline=False)
                await msg.edit(embed=embed)
            except Exception:
                pass
        return build_success_embed(f"Suggestion `{suggestion_id}` marked as **{status}**.")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or not interaction.guild:
            return
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("sugg_vote:"):
            return
        parts = custom_id.split(":")
        if len(parts) < 3:
            return
        sugg_id, vote_type = parts[1], parts[2]
        row = await db_fetchone("SELECT * FROM suggestions WHERE suggestion_id=?", sugg_id)
        if not row:
            return
        voters  = json.loads(row["voters"] or "[]")
        user_id = interaction.user.id
        if user_id in voters:
            await interaction.response.send_message("Already voted!", ephemeral=True)
            return
        voters.append(user_id)
        if vote_type == "up":
            await db_execute("UPDATE suggestions SET upvotes=upvotes+1, voters=? WHERE suggestion_id=?", json.dumps(voters), sugg_id)
            await interaction.response.send_message("👍 Upvoted!", ephemeral=True)
        else:
            await db_execute("UPDATE suggestions SET downvotes=downvotes+1, voters=? WHERE suggestion_id=?", json.dumps(voters), sugg_id)
            await interaction.response.send_message("👎 Downvoted!", ephemeral=True)


class SuggestionView(discord.ui.View):
    def __init__(self, bot, suggestion_id):
        super().__init__(timeout=None)
        up_btn   = discord.ui.Button(emoji="👍", style=discord.ButtonStyle.success, custom_id=f"sugg_vote:{suggestion_id}:up")
        down_btn = discord.ui.Button(emoji="👎", style=discord.ButtonStyle.danger,  custom_id=f"sugg_vote:{suggestion_id}:down")
        self.add_item(up_btn)
        self.add_item(down_btn)


# ============================================================
# SECTION: Utility  (16 slash commands)
# ============================================================

class UtilityCog(commands.Cog, name="Utility"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="serverinfo", description="View server information")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        embed = self._serverinfo_impl(interaction.guild)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="serverinfo", aliases=["server", "si"], help="View server info.")
    async def serverinfo_prefix(self, ctx):
        embed = self._serverinfo_impl(ctx.guild)
        await ctx.send(embed=embed)

    def _serverinfo_impl(self, g):
        bots    = sum(1 for m in g.members if m.bot)
        humans  = g.member_count - bots
        created = int(g.created_at.timestamp())
        embed   = discord.Embed(title=g.name, color=discord.Color.blurple())
        embed.set_thumbnail(url=g.icon.url if g.icon else None)
        embed.add_field(name="👑 Owner",    value=g.owner.mention if g.owner else "Unknown", inline=True)
        embed.add_field(name="📅 Created",  value=f"<t:{created}:D>",                        inline=True)
        embed.add_field(name="👥 Members",  value=f"{humans:,} humans | {bots} bots",        inline=True)
        embed.add_field(name="📺 Channels", value=f"{len(g.text_channels)} text | {len(g.voice_channels)} voice", inline=True)
        embed.add_field(name="🎭 Roles",    value=str(len(g.roles)),                          inline=True)
        embed.add_field(name="😀 Emojis",   value=str(len(g.emojis)),                         inline=True)
        embed.add_field(name="🚀 Boosts",   value=f"{g.premium_subscription_count} (Tier {g.premium_tier})", inline=True)
        embed.set_footer(text=f"Server ID: {g.id}")
        return embed

    @app_commands.command(name="userinfo", description="View information about a user")
    async def userinfo_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        embed = await self._userinfo_impl(interaction.guild, member or interaction.user)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="userinfo", aliases=["ui", "whois"], help="View user info.")
    async def userinfo_prefix(self, ctx, member: discord.Member = None):
        embed = await self._userinfo_impl(ctx.guild, member or ctx.author)
        await ctx.send(embed=embed)

    async def _userinfo_impl(self, guild, m):
        joined  = int(m.joined_at.timestamp()) if m.joined_at else 0
        created = int(m.created_at.timestamp())
        roles   = [r.mention for r in m.roles[1:][:10]]
        db_user = await db_fetchone("SELECT * FROM users WHERE user_id=? AND guild_id=?", m.id, guild.id)
        embed   = discord.Embed(title=str(m), color=m.color)
        embed.set_thumbnail(url=m.display_avatar.url)
        embed.add_field(name="📅 Joined Server",  value=f"<t:{joined}:D>" if joined else "Unknown", inline=True)
        embed.add_field(name="🎂 Account Created", value=f"<t:{created}:D>",                        inline=True)
        embed.add_field(name="🤖 Bot",             value="Yes" if m.bot else "No",                   inline=True)
        if db_user:
            embed.add_field(name="💬 Messages", value=f"{db_user['message_count']:,}",   inline=True)
            embed.add_field(name="🎙️ Voice",   value=f"{db_user['voice_minutes']:,} min", inline=True)
        if roles:
            embed.add_field(name=f"🎭 Roles ({len(m.roles)-1})", value=" ".join(roles), inline=False)
        embed.set_footer(text=f"User ID: {m.id}")
        return embed

    @app_commands.command(name="botstats", description="View bot statistics and ping")
    async def botstats_slash(self, interaction: discord.Interaction):
        embed = self._botstats_impl()
        await interaction.response.send_message(embed=embed)

    @commands.command(name="botstats", aliases=["stats", "ping"], help="View bot stats and ping.")
    async def botstats_prefix(self, ctx):
        embed = self._botstats_impl()
        await ctx.send(embed=embed)

    def _botstats_impl(self):
        uptime  = int(time.time() - BOT_START_TIME)
        cpu     = psutil.cpu_percent()
        mem     = psutil.virtual_memory()
        latency = round(self.bot.latency * 1000)
        embed   = discord.Embed(title=f"📊 Bot Statistics v{BOT_VERSION}", color=discord.Color.blurple())
        embed.add_field(name="🏓 Ping",    value=f"{latency}ms",          inline=True)
        embed.add_field(name="⏱️ Uptime",  value=format_duration(uptime), inline=True)
        embed.add_field(name="🌐 Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="💻 CPU",     value=f"{cpu:.1f}%",            inline=True)
        embed.add_field(name="🧠 Memory",  value=f"{mem.percent:.1f}%",    inline=True)
        embed.add_field(name="🐍 Python",  value=sys.version.split()[0],   inline=True)
        return embed

    @app_commands.command(name="media", description="View a user's avatar or banner")
    @app_commands.describe(type="avatar or banner", member="Target member")
    async def media_slash(self, interaction: discord.Interaction, type: str = "avatar",
                          member: discord.Member = None):
        m     = member or interaction.user
        embed = await self._media_impl(m, type)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="avatar", aliases=["av"], help="Get a user's avatar.")
    async def avatar_prefix(self, ctx, member: discord.Member = None):
        m     = member or ctx.author
        embed = await self._media_impl(m, "avatar")
        await ctx.send(embed=embed)

    @commands.command(name="banner", help="Get a user's banner.")
    async def banner_prefix(self, ctx, member: discord.Member = None):
        m     = member or ctx.author
        embed = await self._media_impl(m, "banner")
        await ctx.send(embed=embed)

    async def _media_impl(self, m, media_type):
        media_type = media_type.lower()
        if media_type == "banner":
            try:
                user = await self.bot.fetch_user(m.id)
                if not user.banner:
                    return build_error_embed("This user has no banner.")
                embed = discord.Embed(title=f"{m.display_name}'s Banner", color=discord.Color.blurple())
                embed.set_image(url=user.banner.url)
                return embed
            except Exception as e:
                return build_error_embed(f"Could not fetch banner: {e}")
        embed = discord.Embed(title=f"{m.display_name}'s Avatar", color=discord.Color.blurple())
        embed.set_image(url=m.display_avatar.url)
        desc = ""
        for fmt in ["png", "jpg", "webp"]:
            desc += f"[{fmt.upper()}]({m.display_avatar.with_format(fmt).url}) | "
        embed.description = desc.rstrip(" | ")
        return embed

    @app_commands.command(name="remind", description="Set a reminder")
    async def remind_slash(self, interaction: discord.Interaction, duration: str, message: str):
        embed = await self._remind_impl(interaction.guild_id, interaction.user, interaction.channel_id, duration, message)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="remind", aliases=["reminder"], help="Set a reminder. Usage: remind <duration> <message>")
    async def remind_prefix(self, ctx, duration: str, *, message: str):
        embed = await self._remind_impl(ctx.guild.id, ctx.author, ctx.channel.id, duration, message)
        await ctx.send(embed=embed)

    async def _remind_impl(self, guild_id, user, channel_id, duration, message):
        secs = parse_duration(duration)
        if not secs:
            return build_error_embed("Invalid duration. Use: 1d, 2h, 30m, 60s")
        remind_at = int(time.time()) + secs
        await db_execute(
            "INSERT INTO reminders (user_id, guild_id, channel_id, message, remind_at) VALUES (?,?,?,?,?)",
            user.id, guild_id, channel_id, message, remind_at,
        )
        return build_success_embed(f"Reminder set for <t:{remind_at}:R>: {message[:100]}")

    @app_commands.command(name="qr", description="Generate a QR code for any text or URL")
    async def qr_slash(self, interaction: discord.Interaction, content: str):
        await interaction.response.defer()
        file, embed = self._qr_impl(content)
        await interaction.followup.send(embed=embed, file=file)

    @commands.command(name="qr", help="Generate a QR code. Usage: qr <content>")
    async def qr_prefix(self, ctx, *, content: str):
        file, embed = self._qr_impl(content)
        await ctx.send(embed=embed, file=file)

    def _qr_impl(self, content):
        qr_img = qrcode.make(content)
        buf    = io.BytesIO()
        qr_img.save(buf, "PNG")
        buf.seek(0)
        file  = discord.File(buf, "qr.png")
        embed = build_info_embed("QR Code", f"Content: `{content[:50]}`")
        embed.set_image(url="attachment://qr.png")
        return file, embed

    @app_commands.command(name="translate", description="Translate text to another language (AI-powered)")
    async def translate_slash(self, interaction: discord.Interaction, text: str, language: str = "English"):
        await interaction.response.defer()
        embed = await self._translate_impl(text, language)
        await interaction.followup.send(embed=embed)

    @commands.command(name="translate", aliases=["tr"], help="Translate text. Usage: translate <language> <text>")
    async def translate_prefix(self, ctx, language: str, *, text: str):
        embed = await self._translate_impl(text, language)
        await ctx.send(embed=embed)

    async def _translate_impl(self, text, language):
        result = await self.bot.ai.translate(text, language)
        embed  = discord.Embed(title=f"🌐 Translation → {language}", color=discord.Color.blurple())
        embed.add_field(name="Original",   value=text[:512],   inline=False)
        embed.add_field(name="Translated", value=result[:512], inline=False)
        return embed

    @app_commands.command(name="weather", description="Get weather for a location")
    async def weather_slash(self, interaction: discord.Interaction, location: str):
        await interaction.response.defer()
        embed = await self._weather_impl(location)
        await interaction.followup.send(embed=embed)

    @commands.command(name="weather", help="Get weather. Usage: weather <location>")
    async def weather_prefix(self, ctx, *, location: str):
        embed = await self._weather_impl(location)
        await ctx.send(embed=embed)

    async def _weather_impl(self, location):
        if not WEATHER_API:
            return build_error_embed("Weather API not configured. Set WEATHER_API_KEY.")
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={WEATHER_API}&units=metric"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return build_error_embed("Location not found.")
                    data = await resp.json()
            embed = discord.Embed(title=f"🌤️ Weather in {data['name']}, {data['sys']['country']}", color=discord.Color.blurple())
            embed.add_field(name="🌡️ Temperature", value=f"{data['main']['temp']:.1f}°C",               inline=True)
            embed.add_field(name="💧 Humidity",    value=f"{data['main']['humidity']}%",                 inline=True)
            embed.add_field(name="💨 Wind",        value=f"{data['wind']['speed']} m/s",                 inline=True)
            embed.add_field(name="☁️ Condition",   value=data['weather'][0]['description'].title(),      inline=True)
            return embed
        except Exception as e:
            return build_error_embed(f"Weather error: {e}")

    @app_commands.command(name="calc", description="Calculate a math expression")
    async def calc_slash(self, interaction: discord.Interaction, expression: str):
        embed = self._calc_impl(expression)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="calc", aliases=["calculate"], help="Calculate an expression. Usage: calc <expression>")
    async def calc_prefix(self, ctx, *, expression: str):
        embed = self._calc_impl(expression)
        await ctx.send(embed=embed)

    def _calc_impl(self, expression):
        allowed = set("0123456789+-*/().%^ ")
        if not all(c in allowed for c in expression):
            return build_error_embed("Invalid expression. Only numbers and +-*/().%^ are allowed.")
        try:
            result = eval(expression.replace("^", "**"))  # noqa: S307
            embed  = discord.Embed(title="🧮 Calculator", color=discord.Color.blurple())
            embed.add_field(name="Expression", value=f"`{expression}`", inline=False)
            embed.add_field(name="Result",     value=f"`{result}`",     inline=False)
            return embed
        except Exception:
            return build_error_embed("Invalid expression.")

    @app_commands.command(name="sticky", description="Set or remove a sticky message in a channel")
    @app_commands.default_permissions(manage_messages=True)
    async def sticky_slash(self, interaction: discord.Interaction, message: str = None,
                           channel: discord.TextChannel = None, remove: bool = False):
        ch    = channel or interaction.channel
        embed = await self._sticky_impl(interaction.guild_id, ch, message, remove)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="sticky", help="Set a sticky message. Usage: sticky [#channel] <message>")
    @commands.has_permissions(manage_messages=True)
    async def sticky_prefix(self, ctx, channel_or_msg: str = None, *, rest: str = None):
        ch = ctx.channel
        if channel_or_msg and channel_or_msg.startswith("<#"):
            try:
                ch_id = int(channel_or_msg.strip("<#>"))
                ch    = ctx.guild.get_channel(ch_id)
                message = rest
            except Exception:
                message = f"{channel_or_msg} {rest or ''}".strip()
        else:
            message = f"{channel_or_msg or ''} {rest or ''}".strip()
        embed = await self._sticky_impl(ctx.guild.id, ch, message, False)
        await ctx.send(embed=embed)

    @commands.command(name="unsticky", help="Remove sticky message. Usage: unsticky [#channel]")
    @commands.has_permissions(manage_messages=True)
    async def unsticky_prefix(self, ctx, channel: discord.TextChannel = None):
        ch    = channel or ctx.channel
        embed = await self._sticky_impl(ctx.guild.id, ch, None, True)
        await ctx.send(embed=embed)

    async def _sticky_impl(self, guild_id, ch, message, remove):
        if remove:
            await db_execute("UPDATE sticky_messages SET active=0 WHERE channel_id=? AND guild_id=?", ch.id, guild_id)
            return build_success_embed(f"Sticky message removed from {ch.mention}.")
        if not message:
            return build_error_embed("Please provide a message.")
        existing = await db_fetchone("SELECT * FROM sticky_messages WHERE channel_id=? AND guild_id=?", ch.id, guild_id)
        if existing:
            await db_execute("UPDATE sticky_messages SET content=?, active=1 WHERE channel_id=? AND guild_id=?", message, ch.id, guild_id)
        else:
            await db_execute("INSERT INTO sticky_messages (guild_id, channel_id, content) VALUES (?,?,?)", guild_id, ch.id, message)
        msg = await ch.send(message)
        await db_execute("UPDATE sticky_messages SET message_id=? WHERE channel_id=? AND guild_id=?", msg.id, ch.id, guild_id)
        return build_success_embed(f"Sticky message set in {ch.mention}.")

    @app_commands.command(name="birthday-set", description="Set your birthday (month and day)")
    async def birthday_slash(self, interaction: discord.Interaction, month: int, day: int):
        embed = await self._birthday_impl(interaction.guild_id, interaction.user, month, day)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="birthday-set", aliases=["setbirthday"], help="Set your birthday. Usage: birthday-set <month> <day>")
    async def birthday_prefix(self, ctx, month: int, day: int):
        embed = await self._birthday_impl(ctx.guild.id, ctx.author, month, day)
        await ctx.send(embed=embed)

    async def _birthday_impl(self, guild_id, user, month, day):
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return build_error_embed("Invalid date.")
        bday = f"{month:02d}-{day:02d}"
        await db_execute("INSERT OR REPLACE INTO birthdays (user_id, guild_id, birthday) VALUES (?,?,?)", user.id, guild_id, bday)
        return build_success_embed(f"Birthday set to **{bday}**! 🎂")

    @app_commands.command(name="timezone-set", description="Set your timezone (e.g. America/New_York)")
    async def timezone_slash(self, interaction: discord.Interaction, timezone: str):
        embed = await self._timezone_impl(interaction.guild_id, interaction.user, timezone)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="timezone-set", aliases=["settimezone"], help="Set your timezone. Usage: timezone-set <timezone>")
    async def timezone_prefix(self, ctx, timezone: str):
        embed = await self._timezone_impl(ctx.guild.id, ctx.author, timezone)
        await ctx.send(embed=embed)

    async def _timezone_impl(self, guild_id, user, timezone):
        try:
            pytz.timezone(timezone)
        except Exception:
            return build_error_embed("Invalid timezone. Examples: America/New_York, Europe/London, Asia/Tokyo")
        await db_execute("UPDATE users SET timezone=? WHERE user_id=? AND guild_id=?", timezone, user.id, guild_id)
        return build_success_embed(f"Timezone set to `{timezone}`.")

    @app_commands.command(name="time", description="Show current time in a timezone")
    async def time_slash(self, interaction: discord.Interaction, timezone: str = "UTC"):
        embed = self._time_impl(timezone)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="time", help="Show time in a timezone. Usage: time [timezone]")
    async def time_prefix(self, ctx, timezone: str = "UTC"):
        embed = self._time_impl(timezone)
        await ctx.send(embed=embed)

    def _time_impl(self, timezone):
        try:
            tz  = pytz.timezone(timezone)
            now = datetime.datetime.now(tz)
            return discord.Embed(title=f"🕐 Time in {timezone}", description=now.strftime("%Y-%m-%d %H:%M:%S %Z"), color=discord.Color.blurple())
        except Exception:
            return build_error_embed("Invalid timezone.")

    @app_commands.command(name="inviteinfo", description="Get information about a Discord invite")
    async def inviteinfo_slash(self, interaction: discord.Interaction, invite_link: str):
        embed = await self._inviteinfo_impl(invite_link)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="inviteinfo", help="Get invite info. Usage: inviteinfo <invite_link>")
    async def inviteinfo_prefix(self, ctx, invite_link: str):
        embed = await self._inviteinfo_impl(invite_link)
        await ctx.send(embed=embed)

    async def _inviteinfo_impl(self, invite_link):
        try:
            invite = await self.bot.fetch_invite(invite_link, with_counts=True)
            embed  = discord.Embed(title="📨 Invite Info", color=discord.Color.blurple())
            embed.add_field(name="Server",  value=invite.guild.name,                               inline=True)
            embed.add_field(name="Channel", value=invite.channel.name if invite.channel else "N/A", inline=True)
            embed.add_field(name="Inviter", value=str(invite.inviter) if invite.inviter else "Unknown", inline=True)
            embed.add_field(name="Uses",    value=str(invite.uses) if invite.uses is not None else "N/A", inline=True)
            embed.add_field(name="Members", value=f"{invite.approximate_member_count:,}", inline=True)
            return embed
        except Exception as e:
            return build_error_embed(f"Invalid invite: {e}")

    @app_commands.command(name="announce", description="Create a server announcement")
    @app_commands.default_permissions(manage_guild=True)
    async def announce_slash(self, interaction: discord.Interaction, title: str, content: str,
                              channel: discord.TextChannel = None, ping_everyone: bool = False):
        ch    = channel or interaction.channel
        embed = discord.Embed(title=f"📢 {title}", description=content, color=discord.Color.blurple(),
                              timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Announced by {interaction.user}")
        content_str = "@everyone" if ping_everyone else None
        await ch.send(content=content_str, embed=embed)
        await interaction.response.send_message(embed=build_success_embed(f"Announcement sent to {ch.mention}."), ephemeral=True)

    @commands.command(name="announce", help="Send an announcement. Usage: announce [#channel] <title> | <content>")
    @commands.has_permissions(manage_guild=True)
    async def announce_prefix(self, ctx, channel: Optional[discord.TextChannel] = None, *, args: str = None):
        ch = channel or ctx.channel
        if not args:
            await ctx.send(embed=build_error_embed("Usage: `announce [#channel] <title> | <content>`"))
            return
        parts = args.split("|", 1)
        title   = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else title
        embed = discord.Embed(title=f"📢 {title}", description=content, color=discord.Color.blurple(),
                              timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Announced by {ctx.author}")
        await ch.send(embed=embed)
        await ctx.send(embed=build_success_embed(f"Announcement sent to {ch.mention}."))

    @app_commands.command(name="scheduleannounce", description="Schedule an announcement")
    @app_commands.default_permissions(manage_guild=True)
    async def scheduleannounce_slash(self, interaction: discord.Interaction, title: str, content: str,
                                      duration: str, channel: discord.TextChannel = None):
        ch    = channel or interaction.channel
        embed = await self._scheduleannounce_impl(interaction.guild_id, ch, title, content, duration)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="scheduleannounce", aliases=["sannounce"], help="Schedule announcement. Usage: scheduleannounce <duration> <title> | <content>")
    @commands.has_permissions(manage_guild=True)
    async def scheduleannounce_prefix(self, ctx, duration: str, *, args: str):
        parts   = args.split("|", 1)
        title   = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else title
        embed   = await self._scheduleannounce_impl(ctx.guild.id, ctx.channel, title, content, duration)
        await ctx.send(embed=embed)

    async def _scheduleannounce_impl(self, guild_id, ch, title, content, duration):
        secs = parse_duration(duration)
        if not secs:
            return build_error_embed("Invalid duration.")
        run_at = int(time.time()) + secs
        await db_execute(
            "INSERT INTO scheduled_tasks (guild_id, task_type, channel_id, data, run_at) VALUES (?,?,?,?,?)",
            guild_id, "announcement", ch.id, json.dumps({"title": title, "content": content}), run_at,
        )
        return build_success_embed(f"Announcement scheduled for <t:{run_at}:R> in {ch.mention}.")


# ============================================================
# SECTION: AI Staff  (7 slash commands)
# ============================================================

class AIStaffCog(commands.Cog, name="AIStaff"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="ai-ask", description="Ask the AI assistant a question")
    async def ai_ask_slash(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        answer = await self.bot.ai.chat(interaction.guild, interaction.user, interaction.channel, question, "professional")
        embed  = discord.Embed(title="🤖 AI Assistant", description=answer, color=discord.Color.blurple())
        embed.set_footer(text=f"Asked by {interaction.user}")
        await interaction.followup.send(embed=embed)

    @commands.command(name="ai-ask", aliases=["ask", "ai"], help="Ask the AI a question. Usage: ai-ask <question>")
    async def ai_ask_prefix(self, ctx, *, question: str):
        async with ctx.typing():
            answer = await self.bot.ai.chat(ctx.guild, ctx.author, ctx.channel, question, "professional")
        embed  = discord.Embed(title="🤖 AI Assistant", description=answer, color=discord.Color.blurple())
        embed.set_footer(text=f"Asked by {ctx.author}")
        await ctx.send(embed=embed)

    @app_commands.command(name="ai-announce", description="Generate an AI-powered announcement")
    @app_commands.default_permissions(manage_guild=True)
    async def ai_announce_slash(self, interaction: discord.Interaction, topic: str, tone: str = "official"):
        await interaction.response.defer()
        result = await self.bot.ai.generate_announcement(topic, tone, interaction.guild.name)
        embed  = discord.Embed(title="📢 AI-Generated Announcement", description=result, color=discord.Color.blurple())
        await interaction.followup.send(embed=embed)

    @commands.command(name="ai-announce", help="Generate an AI announcement. Usage: ai-announce <topic>")
    @commands.has_permissions(manage_guild=True)
    async def ai_announce_prefix(self, ctx, *, topic: str):
        async with ctx.typing():
            result = await self.bot.ai.generate_announcement(topic, "official", ctx.guild.name)
        embed = discord.Embed(title="📢 AI-Generated Announcement", description=result, color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @app_commands.command(name="ai-rules", description="Generate server rules with AI")
    @app_commands.default_permissions(administrator=True)
    async def ai_rules_slash(self, interaction: discord.Interaction, server_type: str = "community"):
        await interaction.response.defer()
        rules = await self.bot.ai.generate_rules(interaction.guild.name, server_type)
        embed = discord.Embed(title="📜 AI-Generated Server Rules", description=rules[:4096], color=discord.Color.blurple())
        await interaction.followup.send(embed=embed)

    @commands.command(name="ai-rules", help="Generate server rules. Usage: ai-rules [server_type]")
    @commands.has_permissions(administrator=True)
    async def ai_rules_prefix(self, ctx, server_type: str = "community"):
        async with ctx.typing():
            rules = await self.bot.ai.generate_rules(ctx.guild.name, server_type)
        embed = discord.Embed(title="📜 AI-Generated Server Rules", description=rules[:4096], color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @app_commands.command(name="ai-embed", description="Generate a Discord embed with AI")
    @app_commands.default_permissions(manage_messages=True)
    async def ai_embed_slash(self, interaction: discord.Interaction, purpose: str, details: str = ""):
        await interaction.response.defer()
        content = await self.bot.ai.generate_embed_content(purpose, details)
        try:
            color_int = int(content.get("color", "#5865F2").lstrip("#"), 16)
        except Exception:
            color_int = 0x5865F2
        embed = discord.Embed(title=content.get("title", ""), description=content.get("description", ""), color=color_int)
        for field in content.get("fields", [])[:10]:
            embed.add_field(name=field.get("name", ""), value=field.get("value", ""), inline=False)
        await interaction.followup.send(embed=embed)

    @commands.command(name="ai-embed", help="Generate an AI embed. Usage: ai-embed <purpose>")
    @commands.has_permissions(manage_messages=True)
    async def ai_embed_prefix(self, ctx, *, purpose: str):
        async with ctx.typing():
            content = await self.bot.ai.generate_embed_content(purpose)
        try:
            color_int = int(content.get("color", "#5865F2").lstrip("#"), 16)
        except Exception:
            color_int = 0x5865F2
        embed = discord.Embed(title=content.get("title", ""), description=content.get("description", ""), color=color_int)
        await ctx.send(embed=embed)

    @app_commands.command(name="ai-analyze", description="Get an AI analysis and recommendations for this server")
    @app_commands.default_permissions(administrator=True)
    async def ai_analyze_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        g    = interaction.guild
        stats = {"channels": len(g.channels), "roles": len(g.roles), "bots": sum(1 for m in g.members if m.bot), "activity": "moderate"}
        analysis = await self.bot.ai.analyze_server(g, stats)
        embed = discord.Embed(title=f"🔍 Server Analysis: {g.name}", description=analysis, color=discord.Color.blurple())
        await interaction.followup.send(embed=embed)

    @commands.command(name="ai-analyze", help="Get AI server analysis.")
    @commands.has_permissions(administrator=True)
    async def ai_analyze_prefix(self, ctx):
        async with ctx.typing():
            g    = ctx.guild
            stats = {"channels": len(g.channels), "roles": len(g.roles), "bots": sum(1 for m in g.members if m.bot), "activity": "moderate"}
            analysis = await self.bot.ai.analyze_server(g, stats)
        embed = discord.Embed(title=f"🔍 Server Analysis: {g.name}", description=analysis, color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @app_commands.command(name="ai-generate", description="Generate FAQ entries or a server report with AI")
    @app_commands.describe(type="faq or report", topic="Topic for FAQ or report type for report")
    @app_commands.default_permissions(manage_guild=True)
    async def ai_generate_slash(self, interaction: discord.Interaction, type: str = "faq",
                                 topic: str = "server", context: str = ""):
        await interaction.response.defer()
        embed = await self._ai_generate_impl(interaction.guild, type, topic, context)
        await interaction.followup.send(embed=embed)

    @commands.command(name="ai-faq", help="Generate FAQ entries. Usage: ai-faq <topic>")
    @commands.has_permissions(manage_guild=True)
    async def ai_faq_prefix(self, ctx, *, topic: str = "server"):
        async with ctx.typing():
            embed = await self._ai_generate_impl(ctx.guild, "faq", topic, "")
        await ctx.send(embed=embed)

    @commands.command(name="ai-report", help="Generate a server report. Usage: ai-report [daily|weekly]")
    @commands.has_permissions(administrator=True)
    async def ai_report_prefix(self, ctx, report_type: str = "daily"):
        async with ctx.typing():
            embed = await self._ai_generate_impl(ctx.guild, "report", report_type, "")
        await ctx.send(embed=embed)

    async def _ai_generate_impl(self, guild, gen_type, topic, context):
        gen_type = gen_type.lower()
        if gen_type == "faq":
            result = await self.bot.ai.generate_faq(topic, context)
            return discord.Embed(title=f"❓ AI FAQ: {topic}", description=result, color=discord.Color.blurple())
        elif gen_type == "report":
            total_msgs  = await db_fetchone("SELECT SUM(message_count) as t FROM users WHERE guild_id=?", guild.id)
            total_warns = await db_fetchone("SELECT COUNT(*) as t FROM warnings WHERE guild_id=? AND active=1", guild.id)
            total_tkts  = await db_fetchone("SELECT COUNT(*) as t FROM tickets WHERE guild_id=?", guild.id)
            data   = {"server": guild.name, "members": guild.member_count,
                      "messages": total_msgs["t"] if total_msgs else 0,
                      "warnings": total_warns["t"] if total_warns else 0,
                      "tickets": total_tkts["t"] if total_tkts else 0}
            report = await self.bot.ai.generate_report(f"{topic} server", data)
            embed  = discord.Embed(title=f"📊 {topic.title()} Report: {guild.name}", description=report[:4096], color=discord.Color.blurple())
            embed.set_footer(text=f"Generated at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            return embed
        return build_error_embed("Invalid type. Use: faq, report")

    @app_commands.command(name="ai-config", description="Configure AI settings: personality or add memory")
    @app_commands.describe(action="personality or memory", personality="default/friendly/professional/strict/fun/teacher",
                           key="Memory key", value="Memory value")
    @app_commands.default_permissions(manage_guild=True)
    async def ai_config_slash(self, interaction: discord.Interaction, action: str = "personality",
                               personality: str = None, key: str = None, value: str = None):
        embed = await self._ai_config_impl(interaction.guild_id, action, personality, key, value)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="ai-personality", help="Set AI personality. Usage: ai-personality <name>")
    @commands.has_permissions(manage_guild=True)
    async def ai_personality_prefix(self, ctx, personality: str):
        embed = await self._ai_config_impl(ctx.guild.id, "personality", personality, None, None)
        await ctx.send(embed=embed)

    @commands.command(name="ai-memory", help="Add AI memory. Usage: ai-memory <key> <value>")
    @commands.has_permissions(manage_guild=True)
    async def ai_memory_prefix(self, ctx, key: str, *, value: str):
        embed = await self._ai_config_impl(ctx.guild.id, "memory", None, key, value)
        await ctx.send(embed=embed)

    async def _ai_config_impl(self, guild_id, action, personality, key, value):
        action = action.lower()
        if action == "personality":
            valid = list(self.bot.ai.personalities.keys())
            if not personality or personality not in valid:
                return build_error_embed(f"Invalid personality. Choose: {', '.join(valid)}")
            await db_execute("UPDATE guild_config SET ai_personality=? WHERE guild_id=?", personality, guild_id)
            return build_success_embed(f"AI personality set to **{personality}**.")
        elif action == "memory":
            if not key or not value:
                return build_error_embed("Please provide both key and value.")
            await self.bot.ai.save_memory(guild_id, None, "server", key, value, importance=2)
            return build_success_embed(f"Memory saved: `{key}` = `{value}`")
        return build_error_embed("Invalid action. Use: personality, memory")


# ============================================================
# SECTION: Backup  (1 slash command)
# ============================================================

class BackupCog(commands.Cog, name="Backup"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="backup", description="Manage server backups: create, list, restore, or export")
    @app_commands.describe(action="create, list, restore, or export", backup_id="Backup ID (for restore/export)")
    @app_commands.default_permissions(administrator=True)
    async def backup_slash(self, interaction: discord.Interaction, action: str,
                            name: str = None, backup_id: str = None, restore_type: str = "roles"):
        await interaction.response.defer(ephemeral=True)
        embed, file = await self._backup_impl(interaction.guild, interaction.user, action, name, backup_id, restore_type)
        if file:
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.command(name="backup", help="Manage backups. Usage: backup create|list|restore|export [name] [backup_id]")
    @commands.has_permissions(administrator=True)
    async def backup_prefix(self, ctx, action: str = "list", name_or_id: str = None, *, rest: str = None):
        backup_id = name_or_id if action in ("restore", "export") else None
        name      = name_or_id if action == "create" else None
        embed, file = await self._backup_impl(ctx.guild, ctx.author, action, name, backup_id, "roles")
        if file:
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

    async def _backup_impl(self, guild, mod, action, name, backup_id, restore_type):
        action = action.lower()
        if action == "create":
            data = {
                "roles": [{"id": r.id, "name": r.name, "color": str(r.color), "perms": r.permissions.value, "position": r.position}
                          for r in guild.roles],
                "channels": [{"id": c.id, "name": c.name, "type": str(c.type)} for c in guild.channels[:50]],
                "guild": {"name": guild.name, "description": guild.description, "member_count": guild.member_count},
            }
            data_str  = json.dumps(data)
            bid        = generate_id("BACKUP")
            bname      = name or f"Backup {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            await db_execute(
                "INSERT INTO backups (guild_id, backup_id, name, data, size_bytes, created_by) VALUES (?,?,?,?,?,?)",
                guild.id, bid, bname, data_str, len(data_str), mod.id,
            )
            embed = discord.Embed(title="✅ Backup Created", color=discord.Color.green())
            embed.add_field(name="Backup ID", value=f"`{bid}`",         inline=True)
            embed.add_field(name="Name",      value=bname,              inline=True)
            embed.add_field(name="Size",      value=f"{len(data_str)/1024:.1f}KB", inline=True)
            return embed, None
        elif action == "list":
            rows = await db_fetch("SELECT * FROM backups WHERE guild_id=? ORDER BY created_at DESC LIMIT 10", guild.id)
            embed = discord.Embed(title="💾 Server Backups", color=discord.Color.blurple())
            if not rows:
                embed.description = "No backups found."
            else:
                for r in rows:
                    ts = datetime.datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d %H:%M")
                    embed.add_field(name=f"`{r['backup_id']}` — {r['name']}",
                                    value=f"Size: {r['size_bytes']/1024:.1f}KB | {ts}", inline=False)
            return embed, None
        elif action == "export":
            if not backup_id:
                return build_error_embed("Please provide a backup ID."), None
            row = await db_fetchone("SELECT * FROM backups WHERE backup_id=? AND guild_id=?", backup_id, guild.id)
            if not row:
                return build_error_embed("Backup not found."), None
            buf  = io.BytesIO(row["data"].encode())
            file = discord.File(buf, f"{backup_id}.json")
            return build_success_embed(f"Exporting backup `{backup_id}`."), file
        elif action == "restore":
            if not backup_id:
                return build_error_embed("Please provide a backup ID."), None
            row = await db_fetchone("SELECT * FROM backups WHERE backup_id=? AND guild_id=?", backup_id, guild.id)
            if not row:
                return build_error_embed("Backup not found."), None
            embed = discord.Embed(title="⚠️ Restore Info",
                                  description=f"To restore `{restore_type}` from backup `{backup_id}`, confirm by using the restore command with a separate `CONFIRM` flag. This is a destructive operation.",
                                  color=discord.Color.orange())
            return embed, None
        return build_error_embed("Invalid action. Use: create, list, restore, export"), None


# ============================================================
# SECTION: Messaging  (2 slash commands)
# ============================================================

class MessagingCog(commands.Cog, name="Messaging"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="dm", description="Send a DM to a user, all members with a role, or everyone")
    @app_commands.describe(member="Specific member to DM", role="DM all members with this role",
                           everyone="DM all server members (use with caution)", message="The message to send")
    @app_commands.default_permissions(manage_guild=True)
    async def dm_slash(self, interaction: discord.Interaction, message: str,
                       member: discord.Member = None, role: discord.Role = None,
                       everyone: bool = False):
        await interaction.response.defer(ephemeral=True)
        embed = await self._dm_impl(interaction.guild, interaction.user, message, member, role, everyone)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.command(name="dm", help="Send a DM to a user. Usage: dm <member> <message>")
    @commands.has_permissions(manage_guild=True)
    async def dm_prefix(self, ctx, member: discord.Member, *, message: str):
        embed = await self._dm_impl(ctx.guild, ctx.author, message, member, None, False)
        await ctx.send(embed=embed)

    @commands.command(name="dm-role", help="DM all members with a role. Usage: dm-role <@role> <message>")
    @commands.has_permissions(administrator=True)
    async def dm_role_prefix(self, ctx, role: discord.Role, *, message: str):
        embed = await self._dm_impl(ctx.guild, ctx.author, message, None, role, False)
        await ctx.send(embed=embed)

    async def _dm_impl(self, guild, mod, message, member, role, everyone):
        if member:
            try:
                await member.send(message)
                await self.bot._log_event(guild.id, "dm_sent", mod.id, member.id, description=f"DM sent to {member}: {message[:100]}")
                return build_success_embed(f"DM sent to {member.mention}.")
            except discord.Forbidden:
                return build_error_embed("Cannot DM this user (DMs disabled or blocked).")
        elif role or everyone:
            targets = [m for m in (role.members if role else guild.members) if not m.bot]
            if len(targets) > 200:
                return build_error_embed(f"Too many targets ({len(targets)}). Max 200 for safety.")
            sent, failed = 0, 0
            for target in targets:
                try:
                    await target.send(message)
                    sent += 1
                    await asyncio.sleep(1)
                except Exception:
                    failed += 1
            return build_success_embed(f"DM sent to **{sent}** members. Failed: {failed}.")
        return build_error_embed("Please specify a member, role, or set everyone=True.")

    @app_commands.command(name="embed-send", description="Send a custom embed to a channel")
    @app_commands.default_permissions(manage_messages=True)
    async def embed_send_slash(self, interaction: discord.Interaction, channel: discord.TextChannel,
                                title: str, description: str, color: str = "#5865F2"):
        try:
            color_int = int(color.lstrip("#"), 16)
        except Exception:
            color_int = 0x5865F2
        embed = discord.Embed(title=title, description=description, color=color_int)
        embed.set_footer(text=f"Sent by {interaction.user}")
        await channel.send(embed=embed)
        await interaction.response.send_message(embed=build_success_embed(f"Embed sent to {channel.mention}."), ephemeral=True)

    @commands.command(name="embed-send", aliases=["sendembed"], help="Send a custom embed. Usage: embed-send <#channel> <title> | <description>")
    @commands.has_permissions(manage_messages=True)
    async def embed_send_prefix(self, ctx, channel: discord.TextChannel, *, args: str):
        parts = args.split("|", 1)
        title = parts[0].strip()
        desc  = parts[1].strip() if len(parts) > 1 else title
        embed = discord.Embed(title=title, description=desc, color=discord.Color.blurple())
        embed.set_footer(text=f"Sent by {ctx.author}")
        await channel.send(embed=embed)
        await ctx.send(embed=build_success_embed(f"Embed sent to {channel.mention}."))


# ============================================================
# SECTION: AI Server Builder  (1 slash command)
# ============================================================

TEMPLATES = {
    "gaming":      {"categories": ["📢 Announcements", "💬 General", "🎮 Gaming", "🔊 Voice Channels"], "desc": "Gaming community"},
    "anime":       {"categories": ["📢 Announcements", "💬 General", "🎌 Anime", "🎨 Art", "🔊 Voice"], "desc": "Anime community"},
    "business":    {"categories": ["📢 Announcements", "💼 Business", "📊 Reports", "🤝 Networking"], "desc": "Business server"},
    "education":   {"categories": ["📢 Announcements", "📚 Courses", "💬 Study Groups", "❓ Help"], "desc": "Education server"},
    "support":     {"categories": ["📢 Announcements", "💬 General", "🎫 Support", "📋 FAQ"], "desc": "Support server"},
    "marketplace": {"categories": ["📢 Announcements", "🛒 Buy", "💰 Sell", "🤝 Trades"], "desc": "Marketplace"},
}


class AIServerBuilderCog(commands.Cog, name="ServerBuilder"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="server", description="View server templates (action=templates) or build one (action=build)")
    @app_commands.describe(action="templates or build", template="Template name for build action")
    @app_commands.default_permissions(administrator=True)
    async def server_slash(self, interaction: discord.Interaction, action: str = "templates",
                            template: str = None):
        action = action.lower()
        if action == "templates":
            embed = discord.Embed(title="🏗️ Server Templates", color=discord.Color.blurple())
            for name, data in TEMPLATES.items():
                embed.add_field(name=f"**{name.title()}**",
                                value=f"{data['desc']}\nCategories: {', '.join(data['categories'][:3])}...",
                                inline=False)
            await interaction.response.send_message(embed=embed)
        elif action == "build":
            if not template or template.lower() not in TEMPLATES:
                await interaction.response.send_message(
                    embed=build_error_embed(f"Invalid template. Choose: {', '.join(TEMPLATES.keys())}"), ephemeral=True
                )
                return
            tmpl = TEMPLATES[template.lower()]
            embed = discord.Embed(title="⚠️ Confirm Server Build",
                                  description=f"Building **{tmpl['desc']}** will create {len(tmpl['categories'])} categories.\nThis will NOT delete existing content.",
                                  color=discord.Color.orange())
            view  = ServerBuildConfirmView(self.bot, template.lower(), interaction.guild)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=build_error_embed("Invalid action. Use: templates, build"), ephemeral=True)

    @commands.command(name="server-templates", help="View available server templates.")
    @commands.has_permissions(administrator=True)
    async def server_templates_prefix(self, ctx):
        embed = discord.Embed(title="🏗️ Server Templates", color=discord.Color.blurple())
        for name, data in TEMPLATES.items():
            embed.add_field(name=f"**{name.title()}**", value=f"{data['desc']}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="server-build", help="Build a server template. Usage: server-build <template>")
    @commands.has_permissions(administrator=True)
    async def server_build_prefix(self, ctx, template: str):
        template = template.lower()
        if template not in TEMPLATES:
            await ctx.send(embed=build_error_embed(f"Invalid template. Choose: {', '.join(TEMPLATES.keys())}"))
            return
        tmpl = TEMPLATES[template]
        msg  = await ctx.send(f"🏗️ Building **{tmpl['desc']}** template...")
        created = 0
        for cat_name in tmpl["categories"]:
            try:
                await ctx.guild.create_category(cat_name)
                created += 1
            except Exception:
                pass
        await msg.edit(content=None, embed=build_success_embed(f"Created {created} categories for **{template}** template!"))


class ServerBuildConfirmView(discord.ui.View):
    def __init__(self, bot, template, guild):
        super().__init__(timeout=60)
        self.bot      = bot
        self.template = template
        self.guild    = guild

    @discord.ui.button(label="Build Server", style=discord.ButtonStyle.success)
    async def build_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        tmpl    = TEMPLATES[self.template]
        created = 0
        for cat_name in tmpl["categories"]:
            try:
                await self.guild.create_category(cat_name)
                created += 1
            except Exception:
                pass
        await interaction.followup.send(embed=build_success_embed(f"Created {created} categories for **{self.template}** template!"), ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_info_embed("Cancelled", "Server build cancelled."), ephemeral=True)
        self.stop()


# ============================================================
# SECTION: Config  (5 slash commands)
# ============================================================

class ConfigCog(commands.Cog, name="Config"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="config", description="View the current bot configuration")
    @app_commands.default_permissions(administrator=True)
    async def config_slash(self, interaction: discord.Interaction):
        embed = await self._config_impl(interaction.guild)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="config", help="View bot configuration.")
    @commands.has_permissions(administrator=True)
    async def config_prefix(self, ctx):
        embed = await self._config_impl(ctx.guild)
        await ctx.send(embed=embed)

    async def _config_impl(self, guild):
        cfg = await get_guild_config(guild.id)
        embed = discord.Embed(title="⚙️ Bot Configuration", color=discord.Color.blurple())
        if cfg:
            log_ch   = self.bot.get_channel(cfg["log_channel"])     if cfg["log_channel"]     else None
            mod_ch   = self.bot.get_channel(cfg["mod_log_channel"]) if cfg["mod_log_channel"] else None
            wel_ch   = self.bot.get_channel(cfg["welcome_channel"]) if cfg["welcome_channel"] else None
            tick_cat = guild.get_channel(cfg["ticket_category"])    if cfg["ticket_category"] else None
            embed.add_field(name="Prefix",          value=cfg["prefix"],                                inline=True)
            embed.add_field(name="Language",        value=cfg["language"],                              inline=True)
            embed.add_field(name="Log Channel",     value=log_ch.mention if log_ch else "Not set",      inline=True)
            embed.add_field(name="Mod Log",         value=mod_ch.mention if mod_ch else "Not set",      inline=True)
            embed.add_field(name="Welcome",         value=wel_ch.mention if wel_ch else "Not set",      inline=True)
            embed.add_field(name="AI Enabled",      value="✅" if cfg["ai_enabled"] else "❌",          inline=True)
            embed.add_field(name="Leveling",        value="✅" if cfg["level_enabled"] else "❌",       inline=True)
            embed.add_field(name="Economy",         value="✅" if cfg["economy_enabled"] else "❌",     inline=True)
            embed.add_field(name="Ticket Category", value=tick_cat.name if tick_cat else "Not set",     inline=True)
            embed.add_field(name="Max Warnings",    value=str(cfg["max_warnings"]),                     inline=True)
            embed.add_field(name="Currency",        value=f"{cfg['currency_emoji']} {cfg['currency_name']}", inline=True)
        return embed

    @app_commands.command(name="set-prefix", description="Change the bot's command prefix")
    @app_commands.default_permissions(administrator=True)
    async def set_prefix_slash(self, interaction: discord.Interaction, prefix: str):
        embed = await self._set_prefix_impl(interaction.guild_id, prefix)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="set-prefix", aliases=["prefix"], help="Change prefix. Usage: set-prefix <prefix>")
    @commands.has_permissions(administrator=True)
    async def set_prefix_prefix_cmd(self, ctx, prefix: str):
        embed = await self._set_prefix_impl(ctx.guild.id, prefix)
        await ctx.send(embed=embed)

    async def _set_prefix_impl(self, guild_id, prefix):
        if len(prefix) > 5:
            return build_error_embed("Prefix must be 5 characters or less.")
        await db_execute("UPDATE guild_config SET prefix=? WHERE guild_id=?", prefix, guild_id)
        return build_success_embed(f"Prefix changed to `{prefix}`.")

    @app_commands.command(name="set-server", description="Configure server language and/or currency")
    @app_commands.default_permissions(manage_guild=True)
    async def set_server_slash(self, interaction: discord.Interaction,
                                language: str = None, currency_name: str = None, currency_emoji: str = None):
        embed = await self._set_server_impl(interaction.guild_id, language, currency_name, currency_emoji)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="set-language", help="Set server language. Usage: set-language <language>")
    @commands.has_permissions(manage_guild=True)
    async def set_language_prefix(self, ctx, language: str):
        embed = await self._set_server_impl(ctx.guild.id, language, None, None)
        await ctx.send(embed=embed)

    @commands.command(name="set-currency", help="Set currency. Usage: set-currency <name> [emoji]")
    @commands.has_permissions(administrator=True)
    async def set_currency_prefix(self, ctx, name: str = "coins", emoji: str = "🪙"):
        embed = await self._set_server_impl(ctx.guild.id, None, name, emoji)
        await ctx.send(embed=embed)

    async def _set_server_impl(self, guild_id, language, currency_name, currency_emoji):
        updates, values = [], []
        if language:
            updates.append("language=?"); values.append(language)
        if currency_name:
            updates.append("currency_name=?"); values.append(currency_name)
        if currency_emoji:
            updates.append("currency_emoji=?"); values.append(currency_emoji)
        if not updates:
            return build_error_embed("Provide at least one setting to update.")
        values.append(guild_id)
        await db_execute(f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id=?", *values)
        embed = discord.Embed(title="✅ Server Settings Updated", color=discord.Color.green())
        if language:
            embed.add_field(name="Language", value=language, inline=True)
        if currency_name:
            embed.add_field(name="Currency", value=f"{currency_emoji or '🪙'} {currency_name}", inline=True)
        return embed

    @app_commands.command(name="set-ai", description="Toggle AI features and configure the AI channel")
    @app_commands.default_permissions(administrator=True)
    async def set_ai_slash(self, interaction: discord.Interaction, enabled: bool,
                            always_on: bool = False, channel: discord.TextChannel = None):
        embed = await self._set_ai_impl(interaction.guild_id, enabled, always_on, channel)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="set-ai", help="Toggle AI. Usage: set-ai <true/false>")
    @commands.has_permissions(administrator=True)
    async def set_ai_prefix(self, ctx, enabled: bool, always_on: bool = False, channel: discord.TextChannel = None):
        embed = await self._set_ai_impl(ctx.guild.id, enabled, always_on, channel)
        await ctx.send(embed=embed)

    async def _set_ai_impl(self, guild_id, enabled, always_on, channel):
        updates, values = "ai_enabled=?, ai_always_on=?", [int(enabled), int(always_on)]
        if channel:
            updates += ", ai_channel=?"; values.append(channel.id)
        values.append(guild_id)
        await db_execute(f"UPDATE guild_config SET {updates} WHERE guild_id=?", *values)
        embed = discord.Embed(title="✅ AI Settings Updated", color=discord.Color.green())
        embed.add_field(name="Enabled",    value="✅" if enabled    else "❌", inline=True)
        embed.add_field(name="Always On",  value="✅" if always_on  else "❌", inline=True)
        if channel:
            embed.add_field(name="AI Channel", value=channel.mention, inline=True)
        return embed

    @app_commands.command(name="setup-roles", description="Configure moderation roles (mute, jail, mod, staff)")
    @app_commands.default_permissions(administrator=True)
    async def setup_roles_slash(self, interaction: discord.Interaction,
                                 mute_role: discord.Role = None, jail_role: discord.Role = None,
                                 mod_role: discord.Role = None, staff_role: discord.Role = None):
        embed = await self._setup_roles_impl(interaction.guild_id, mute_role, jail_role, mod_role, staff_role)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="setup-roles", help="Configure mod roles. Usage: setup-roles mute:@role jail:@role")
    @commands.has_permissions(administrator=True)
    async def setup_roles_prefix(self, ctx, *, args: str = ""):
        await ctx.send(embed=build_info_embed("Setup Roles", "Please use `/setup-roles` slash command to configure roles, or mention roles with flags like `mute:@Role jail:@Role`."))

    async def _setup_roles_impl(self, guild_id, mute_role, jail_role, mod_role, staff_role):
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
            return build_error_embed("No roles provided.")
        values.append(guild_id)
        await db_execute(f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id=?", *values)
        return build_success_embed("Role configuration updated.")

    @app_commands.command(name="help", description="Get help with bot commands and categories")
    async def help_slash(self, interaction: discord.Interaction, category: str = None):
        embed = self._help_impl(category)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="help", aliases=["h", "commands"], help="Show all commands or a specific category.")
    async def help_prefix(self, ctx, category: str = None):
        embed = self._help_impl(category)
        await ctx.send(embed=embed)

    def _help_impl(self, category: str = None):
        categories = {
            "🛡️ Moderation": {
                "cmds": ["warn", "warnings [clear]", "kick", "ban [soft=True]", "tempban", "unban", "timeout [remove=True]",
                         "mute [unmute=True]", "jail [release=True]", "purge", "lock [unlock=True]", "slowmode",
                         "nick", "case", "modhistory", "appeal", "voice", "massban", "automod", "lockdown", "antiraid"],
                "desc": "Moderation tools for keeping your server safe",
            },
            "🎫 Tickets": {
                "cmds": ["ticket-panel", "ticket-close", "ticket-manage", "ticket-note", "ticket-summary", "ticket-stats"],
                "desc": "Advanced ticket system with AI summaries",
            },
            "💰 Economy": {
                "cmds": ["balance", "daily", "weekly", "monthly", "work", "jobs", "apply", "deposit", "withdraw",
                         "pay", "leaderboard", "shop", "buy", "inventory", "gamble", "fish", "mine"],
                "desc": "Full-featured economy system",
            },
            "⭐ Leveling": {
                "cmds": ["rank", "top", "setxp", "role-reward-add", "prestige"],
                "desc": "XP and leveling system with rank cards",
            },
            "🎵 Music": {
                "cmds": ["play", "skip", "stop", "queue", "volume", "pause", "resume", "shuffle"],
                "desc": "Music player powered by YouTube",
            },
            "🎉 Events": {
                "cmds": ["giveaway [start/reroll]", "poll", "suggest"],
                "desc": "Giveaways, polls, and suggestions",
            },
            "🔧 Utility": {
                "cmds": ["serverinfo", "userinfo", "botstats", "media", "remind", "qr", "translate", "weather",
                         "calc", "sticky [remove=True]", "birthday-set", "timezone-set", "time", "inviteinfo", "announce", "scheduleannounce"],
                "desc": "General utility commands",
            },
            "🤖 AI Tools": {
                "cmds": ["ai-ask", "ai-announce", "ai-rules", "ai-embed", "ai-analyze", "ai-generate [faq/report]", "ai-config [personality/memory]"],
                "desc": "AI-powered content generation",
            },
            "🔒 Security": {
                "cmds": ["antiraid", "lockdown", "automod [list=True]"],
                "desc": "Anti-raid and AutoMod protection",
            },
            "💾 Backup": {
                "cmds": ["backup [create/list/restore/export]"],
                "desc": "Server backup and restore",
            },
            "📨 Messaging": {
                "cmds": ["dm [member/role/everyone]", "embed-send"],
                "desc": "Bulk DMs and custom embeds",
            },
            "⚙️ Config": {
                "cmds": ["config", "set-prefix", "set-server", "set-ai", "setup-roles", "welcome-config",
                         "autorole", "logs-config", "reactionrole", "server [templates/build]", "schedule"],
                "desc": "Bot configuration and setup",
            },
        }

        if category:
            found_key = next((k for k in categories if category.lower() in k.lower()), None)
            if found_key:
                data  = categories[found_key]
                embed = discord.Embed(title=f"Help: {found_key}", description=data["desc"], color=discord.Color.blurple())
                embed.add_field(name="Commands", value="\n".join(f"`/{c}`" for c in data["cmds"]), inline=False)
                embed.set_footer(text=f"Use !<command> or /<command> • Total: 98 slash commands")
                return embed

        embed = discord.Embed(
            title=f"📚 Enterprise Bot Help — v{BOT_VERSION}",
            description=(
                f"**98 Slash Commands · All available as prefix commands too**\n"
                f"Use `/help <category>` or `!help <category>` for detailed commands.\n\n"
                f"**Prefix:** Configurable (default: `!`) • **Slash:** All commands\n"
                f"**AI Powered:** Groq (xAI) primary, OpenAI fallback"
            ),
            color=discord.Color.blurple(),
        )
        for cat, data in categories.items():
            embed.add_field(name=cat, value=f"{len(data['cmds'])} commands • {data['desc']}", inline=False)
        embed.set_footer(text="Tip: Every slash command also works as a prefix command!")
        return embed


# ============================================================
# SECTION: Scheduler  (1 slash command)
# ============================================================

class SchedulerCog(commands.Cog, name="Scheduler"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(name="schedule", description="Schedule a message to be sent later")
    @app_commands.default_permissions(manage_guild=True)
    async def schedule_slash(self, interaction: discord.Interaction,
                              channel: discord.TextChannel, message: str, when: str,
                              repeat: bool = False, repeat_every: str = None):
        embed = await self._schedule_impl(interaction.guild_id, channel, message, when, repeat, repeat_every)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="schedule", help="Schedule a message. Usage: schedule <#channel> <duration> <message>")
    @commands.has_permissions(manage_guild=True)
    async def schedule_prefix(self, ctx, channel: discord.TextChannel, when: str, *, message: str):
        embed = await self._schedule_impl(ctx.guild.id, channel, message, when, False, None)
        await ctx.send(embed=embed)

    async def _schedule_impl(self, guild_id, channel, message, when, repeat, repeat_every):
        secs = parse_duration(when)
        if not secs:
            return build_error_embed("Invalid duration. Use: 1d, 2h, 30m, 60s")
        run_at     = int(time.time()) + secs
        repeat_sec = parse_duration(repeat_every) if repeat and repeat_every else 0
        await db_execute(
            "INSERT INTO scheduled_tasks (guild_id, task_type, channel_id, data, run_at, repeat, repeat_sec) VALUES (?,?,?,?,?,?,?)",
            guild_id, "message", channel.id, json.dumps({"content": message}), run_at, int(repeat), repeat_sec or 0,
        )
        msg = f"Message scheduled for <t:{run_at}:R> in {channel.mention}."
        if repeat and repeat_sec:
            msg += f" Repeating every {format_duration(repeat_sec)}."
        return build_success_embed(msg)


# ============================================================
# SECTION: Global Interaction Handler
# ============================================================

async def _global_interaction_handler(bot: DiscordBot, interaction: discord.Interaction):
    if not interaction.data:
        return
    custom_id = interaction.data.get("custom_id", "")
    if not custom_id:
        return
    if custom_id.startswith("rate:"):
        parts = custom_id.split(":")
        if len(parts) >= 3:
            ticket_id = parts[1]
            rating    = int(parts[2])
            await db_execute("UPDATE tickets SET feedback=? WHERE ticket_id=?", rating, ticket_id)
            stars = "⭐" * rating
            await interaction.response.send_message(f"Thank you for your rating: {stars}", ephemeral=True)


# ============================================================
# SECTION: Main Entry Point
# ============================================================

async def main():
    if not DISCORD_TOKEN:
        log.critical("DISCORD_TOKEN not set! Please configure it in your .env file.")
        sys.exit(1)

    bot = DiscordBot()

    async def combined_interaction(interaction: discord.Interaction):
        await _global_interaction_handler(bot, interaction)
        for cog in bot.cogs.values():
            if hasattr(cog, "on_interaction"):
                try:
                    await cog.on_interaction(interaction)
                except Exception as e:
                    log.debug(f"Interaction handler error in {cog}: {e}")

    bot.add_listener(combined_interaction, "on_interaction")

    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
