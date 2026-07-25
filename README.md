# Enterprise AI-Powered Discord Bot

> Commercial-grade Discord SaaS management platform powered by Grok (xAI) AI.

---

## Features

### 🤖 AI Core System
- AI Chat, Reasoning, Planning, Suggestions
- AI Memory System (server + user context)
- AI Personalities (Default, Friendly, Professional, Strict, Fun, Teacher)
- AI Moderation, Automod, Ticket Summaries
- AI Announcement/Rules/Embed/FAQ Generator
- AI Server Analysis & Health Reports
- AI Translation (any language)
- Always-on AI channel mode + mention support

### 🛡️ Moderation
- Warn, Kick, Ban, Tempban, Softban, Unban
- Timeout, Mute, Jail system
- Purge, Slowmode, Lock, Unlock
- Nickname moderation, Voice moderation
- Mass moderation, Moderator notes
- Appeal system, Evidence storage
- Case tracking with full history

### 🤖 AI AutoMod
- Toxicity, Harassment, Hate speech detection
- Spam, Flood, Scam, Phishing detection
- Fake Nitro, Token leak, Malicious link detection
- NSFW, Mention spam, Invite spam, Emoji spam
- Zalgo text, Repeated messages detection
- Configurable actions per rule

### 🔒 Anti-Raid Security
- Join flood detection with configurable threshold
- Bot raid protection (auto-kick unauthorized bots)
- Webhook creation protection
- Channel/Role deletion monitoring
- Emergency lockdown mode
- Verification mode

### 🎫 Enterprise Ticket System
- Unlimited panels, departments, categories
- Buttons, Modals, Priority levels
- Claim, Unclaim, Transfer tickets
- Archive, Reopen, Close with feedback
- HTML/TXT transcripts, DM transcripts
- AI summaries, Internal notes
- SLA tracking, Staff statistics
- Auto-close, Feedback ratings

### 🎭 Reaction Roles
- Button-based reaction roles
- Exclusive roles (remove others on select)
- Stackable roles

### 👋 Welcome System
- Custom welcome/goodbye messages
- Auto-roles on join
- AI-generated personalized welcomes
- Variable support: `{user}` `{server}` `{count}`

### 📋 Logging System
- Message delete/edit logs
- Voice join/leave logs
- Role change logs
- Channel/permission change logs
- Member join/leave logs
- Moderation action logs
- AI action logs, Error logs

### 💰 Economy System
- Wallet & Bank
- Daily, Weekly, Monthly rewards with streak bonuses
- 8 Jobs with hourly work cooldown
- Shop system with role items
- Inventory management
- Trading via `/pay`
- Casino gambling
- Fishing & Mining minigames
- Economy leaderboard

### ⭐ Leveling System
- Text XP (60s cooldown between gains)
- Voice XP (per minute)
- Level-up announcements
- Role rewards with optional replace-previous
- Prestige system (resets at Level 50)
- Beautiful rank card images
- XP Leaderboard

### 🎵 Music System
- YouTube playback via yt-dlp
- Queue management
- Volume control
- Skip, Stop, Pause, Resume
- Shuffle queue
- Now Playing display

### 🎉 Giveaway System
- Create giveaways with duration
- Multiple winners support
- Role requirements
- One-click entry via button
- Auto-end with winner selection
- Reroll command

### 📊 Poll System
- Up to 5 options per poll
- Anonymous voting option
- Timed polls (auto-end)
- Results display with percentages

### 💡 Suggestion System
- AI-powered auto-categorization
- Upvote/Downvote system
- Staff review workflow (approve/reject/implement/considering)

### 🔧 Utility
- Server info, User info
- Avatar, Banner viewer
- Calculator, QR code generator
- Weather (requires API key)
- Translation (AI-powered)
- Reminders with repeat support
- Birthday system with announcements
- Timezone support
- Sticky messages
- Invite info
- Scheduled announcements

### 🏗️ AI Server Builder
- Server templates (Gaming, Anime, Business, Education, Support, Marketplace)
- Auto-creates categories, channels, roles

### 💾 Backup System
- Full server backup (roles, channels, settings, bot config)
- Export to JSON file
- Restore confirmation workflow
- Auto-saved to `backups/` directory

### 📩 Messaging System
- DM individual users
- DM by role (with confirmation)
- Custom embed creation
- Scheduled announcements

---

## Setup

### Requirements
- Python 3.12+
- FFmpeg (for music features)

### Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/discord-bot.git
cd discord-bot

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your keys
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Your Discord bot token |
| `GROK_API_KEY` | Recommended | xAI Grok API key (primary AI) |
| `OPENAI_API_KEY` | Optional | OpenAI API key (fallback AI) |
| `DATABASE_URL` | Optional | PostgreSQL URL (leave empty for SQLite) |
| `BOT_PREFIX` | Optional | Command prefix (default: `!`) |
| `OWNER_ID` | Optional | Your Discord user ID |
| `WEATHER_API_KEY` | Optional | OpenWeatherMap API key |

### Running

```bash
python main.py
```

---

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a New Application
3. Go to **Bot** → Reset Token → Copy token → set as `DISCORD_TOKEN`
4. Enable all **Privileged Gateway Intents** (Presence, Server Members, Message Content)
5. Go to **OAuth2 → URL Generator**
6. Select scopes: `bot`, `applications.commands`
7. Select permissions: **Administrator** (or granular permissions)
8. Copy and open the generated URL to invite the bot

---

## Getting AI API Keys

### Grok (xAI) — Primary AI
1. Go to [console.x.ai](https://console.x.ai)
2. Create an account and generate an API key
3. Set as `GROK_API_KEY`

### OpenAI — Fallback
1. Go to [platform.openai.com](https://platform.openai.com)
2. Create API key
3. Set as `OPENAI_API_KEY`

---

## Deployment on Render.com

1. Push code to GitHub
2. Go to [render.com](https://render.com) → New → Web Service (or Worker)
3. Connect your GitHub repo
4. Render auto-detects `render.yaml`
5. Add environment variables in Render dashboard
6. Deploy!

> **Note:** Use a **Background Worker** (not Web Service) on Render for Discord bots.

---

## Database

The bot uses **SQLite** by default (`bot_database.db`).

For PostgreSQL (production), set `DATABASE_URL` to your PostgreSQL connection string. The schema is PostgreSQL-compatible — just update the driver from `aiosqlite` to `asyncpg` in the database section.

### Tables
`guild_config`, `users`, `ai_memory`, `ai_conversations`, `ai_actions`, `tickets`, `ticket_messages`, `ticket_panels`, `ticket_stats`, `moderation_cases`, `warnings`, `appeals`, `logs`, `economy`, `inventory`, `shop`, `levels`, `role_rewards`, `automod_rules`, `anti_raid`, `reaction_roles`, `backups`, `scheduled_tasks`, `reminders`, `giveaways`, `polls`, `suggestions`, `sticky_messages`, `birthdays`, `voice_tracking`

---

## Quick Start Commands

After inviting the bot:
```
/config                  — View current configuration
/setup-roles             — Configure mod/mute/jail roles
/logs-config             — Set up log channels
/welcome-config          — Configure welcome messages
/ticket-panel            — Create a support ticket panel
/antiraid                — Configure anti-raid protection
/ai-ask                  — Ask the AI anything
/help                    — View all commands
```

---

## Architecture

```
main.py
├── SECTION: Imports & Configuration
├── SECTION: Database (init + helpers)
├── SECTION: AI System (AISystem class)
├── SECTION: Core Engine (DiscordBot class + background tasks)
├── SECTION: Moderation (ModerationCog)
├── SECTION: AI Automod (AutoModCog)
├── SECTION: Anti-Raid Security (AntiRaidCog)
├── SECTION: Enterprise Ticket System (TicketCog)
├── SECTION: Reaction Roles (ReactionRolesCog)
├── SECTION: Welcome System (WelcomeCog)
├── SECTION: Logging System (LoggingCog)
├── SECTION: Economy System (EconomyCog)
├── SECTION: Leveling System (LevelingCog)
├── SECTION: Music System (MusicCog)
├── SECTION: Giveaway System (GiveawayCog)
├── SECTION: Poll System (PollCog)
├── SECTION: Suggestion System (SuggestionCog)
├── SECTION: Utility System (UtilityCog)
├── SECTION: AI Staff Assistant (AIStaffCog)
├── SECTION: Backup System (BackupCog)
├── SECTION: Messaging System (MessagingCog)
├── SECTION: AI Server Builder (AIServerBuilderCog)
├── SECTION: Config System (ConfigCog)
├── SECTION: Scheduler (SchedulerCog)
└── SECTION: Main Entry Point
```

---

## License

MIT License — Commercial use permitted.
