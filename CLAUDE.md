# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TZshnik is a Telegram bot that generates technical specifications (ТЗ) for products using AI vision analysis. Users upload photos, and the bot (via Google Gemini) creates detailed product documentation.

**Tech Stack:** aiogram 3.x, SQLAlchemy 2.0 async, Google Gemini API, YooKassa payments, ReportLab PDF export

**Repository:** https://github.com/Prot1vn1kk/TZshnik

---

## Running the Bot

```bash
# Production (with auto-update)
python app.py

# Development (direct)
python -m TelegramBot_v2.bot

# Or from TelegramBot_v2 directory
python bot/main.py
```

---

## Development Commands

```bash
# Lint and format (Ruff)
ruff check .
ruff format .

# Run tests
pytest

# Create database backup
python -c "from utils.backup import backup_database; backup_database()"
```

---

## Architecture

### Entry Points

- **`app.py`** — Production entry point with GitHub auto-update mechanism. Handles cloud hosting (read-only FS) scenarios by downloading updates via GitHub API instead of git.

- **`bot/main.py`** — Bot initialization: logging setup, middleware registration, router startup, graceful shutdown.

### Core Modules

| Module | Purpose |
|--------|---------|
| `bot/handlers/` | All telegram command/callback handlers |
| `core/generator.py` | AI generation orchestrator (vision → text → validation) |
| `core/ai_providers/` | AI provider implementations (Gemini) with failover chain |
| `database/models.py` | SQLAlchemy models (User, Generation, Payment, etc.) |
| `database/admin_crud.py` | Admin CRUD with pagination (uses `selectinload` to avoid N+1) |
| `config/packages.py` | **Source of truth for pricing** — `CreditPackage` dataclass |
| `utils/validators.py` | Input validation with fallback in admin_panel.py for compatibility |

### Auto-Update Mechanism (`app.py`)

The bot can self-update via GitHub API before starting:
1. Checks latest commit SHA from GitHub
2. Compares with saved version in `.version` file
3. If different, downloads updated Python files via two fallback methods:
   - Method 1: GitHub API individual file download
   - Method 2: ZIP archive download
4. Works on read-only filesystems (logs update availability instead of applying)

**To skip updates:** Create `TelegramBot_v2/.skip_update` file

---

## Important Patterns

### 1. Single Source of Truth for Pricing

`config/packages.py` contains `PACKAGES` dict with `CreditPackage` dataclass. **Never duplicate pricing in other files.** Import from config:

```python
from config.packages import PACKAGES
```

### 2. N+1 Query Prevention

When fetching paginated users, preload relations:

```python
from database.admin_crud import get_users_paginated
users, total = await get_users_paginated(session, page=1, load_relations=True)
```

### 3. Fallback Imports for Compatibility

Some modules have fallback imports to work on cloud hosting where new files may not be immediately available:

```python
try:
    from utils.validators import validate_xxx
except ImportError:
    def validate_xxx(...): ...  # fallback
```

### 4. AI Provider Chain

AI generation uses provider chaining for failover. If primary provider fails, secondary attempts with different model/config.

---

## Database Models Key Relationships

- **User** ← has many → **Generation**, **Payment**
- **Generation** ← has many → **GenerationPhoto**
- **Generation** → **Feedback** (quality rating)
- **User** → referrals (uses `referral_code` and `referred_by` fields)

---

## Admin Panel

Full admin interface accessible via `/admin`. Key sections:
- Dashboard with real-time stats
- User management (search, credits, block/unblock)
- Generation history review
- Payment history
- Analytics (revenue, generation stats)
- Bot settings configuration

**Note:** Admin operations are logged to `admin_actions` table for audit.

---

## Configuration

Environment variables (`.env` or host-provided):
```env
TELEGRAM_BOT_TOKEN=...
ADMIN_IDS_STR=603378487,xxx,xxx
GEMINI_API_KEY=...
YOOASSA_PROVIDER_TOKEN=...  # For payments
DEBUG=true  # Enables colored logs
```

Constants in `config/constants.py`:
- `MAX_PHOTOS_PER_GENERATION` = 5
- `ITEMS_PER_PAGE` = 10
- `MAX_CREDIT_OPERATION_AMOUNT` = 10000

---

## Common Issues

### ImportError on Cloud Hosting

If bot fails with `No module named 'xxx'`:
1. The file may not exist yet (auto-update pending)
2. Check if fallback import exists in the importing file
3. Manual file replacement may be needed if GitHub API is blocked (403 error)

### GitHub API 403 Error

Indicates rate limit or IP blocking. Bot will still run but won't auto-update. Solution:
- Wait for rate limit reset
- Add GitHub token for authentication
- Manually update files via git

### Read-Only Filesystem

Cloud hosting may have read-only FS. Auto-update detects this and logs availability instead of failing.

---

## File Locations

- Bot entry: `TelegramBot_v2/bot/main.py`
- Database: `TelegramBot_v2/data/database.sqlite`
- Exports: `TelegramBot_v2/exports/`
- Temp files: `TelegramBot_v2/data/temp_files/` (cleaned periodically)
- Auto-update wrapper: `app.py` (root level)
- Version tracking: `.version` file (root level)
