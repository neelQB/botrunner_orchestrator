# Database Migrations with Alembic

This document provides comprehensive information about database migrations using Alembic for the BotRunner project.

## Overview

BotRunner uses **Alembic** for database schema migrations, providing version-controlled, reproducible database changes. The migration system supports both **SQLite** (development) and **PostgreSQL/Neon** (production) databases.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Migration Commands](#migration-commands)
- [Schema Structure](#schema-structure)
- [Creating Migrations](#creating-migrations)
- [Environment Configuration](#environment-configuration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

```powershell
# Activate conda environment
conda activate botenv

# Alembic is already installed via Poetry
# If not: pip install alembic
```

### Initialize Fresh Database

```powershell
# For new installations (creates tables)
python scripts/migrate.py init

# Verify migration status
python scripts/migrate.py current
```

### Apply Migrations to Existing Database

```powershell
# Check current status
python scripts/migrate.py info

# Apply all pending migrations
python scripts/migrate.py upgrade head

# Verify
python scripts/migrate.py current
```

---

## Architecture

### Directory Structure

```
botrunner/
├── alembic/                    # Alembic migration directory
│   ├── versions/               # Migration scripts
│   │   └── 02c02c4d5da4_create_session_state_table.py
│   ├── env.py                  # Alembic environment config
│   ├── script.py.mako         # Migration template
│   └── README                  # Alembic info
├── alembic.ini                 # Alembic configuration
├── app/
│   └── database/
│       ├── models.py           # SQLAlchemy models for migrations
│       └── session_manager.py  # Session management (existing)
└── scripts/
    └── migrate.py              # Migration management CLI
```

### Database Support

| Database       | Environment | Connection                  |
| -------------- | ----------- | --------------------------- |
| **SQLite**     | Development | `data/chat_history.db`      |
| **PostgreSQL** | Production  | `DATABASE_URL` env variable |
| **Neon**       | Cloud       | `DATABASE_URL` env variable |

---

## Migration Commands

### Using the Migration CLI

The `scripts/migrate.py` CLI provides convenient database management:

#### Check Status

```powershell
# Show database configuration and current revision
python scripts/migrate.py info

# Show current revision only
python scripts/migrate.py current

# Show migration history
python scripts/migrate.py history

# Show detailed history
python scripts/migrate.py history --verbose
```

#### Apply Migrations

```powershell
# Initialize fresh database (new installations)
python scripts/migrate.py init

# Upgrade to latest version
python scripts/migrate.py upgrade head

# Upgrade one version
python scripts/migrate.py upgrade +1

# Upgrade to specific revision
python scripts/migrate.py upgrade 02c02c4d5da4
```

#### Rollback Migrations

```powershell
# Downgrade one version
python scripts/migrate.py downgrade -1

# Downgrade to beginning (WARNING: data loss!)
python scripts/migrate.py downgrade base

# Downgrade to specific revision
python scripts/migrate.py downgrade abc123
```

#### Create New Migrations

```powershell
# Create empty migration
python scripts/migrate.py revision "add new column"

# Auto-generate migration from model changes
python scripts/migrate.py revision "add indexes" --autogenerate
```

#### Advanced Commands

```powershell
# Stamp database (mark as migrated without running migrations)
# Useful when migrating from non-Alembic setup
python scripts/migrate.py stamp head

# Stamp with specific revision
python scripts/migrate.py stamp 02c02c4d5da4
```

### Using Alembic Directly

```powershell
# Core Alembic commands also work directly
alembic current
alembic upgrade head
alembic downgrade -1
alembic history
alembic revision -m "message"
```

---

## Schema Structure

### Current Schema (v1)

#### `session_state` Table

Stores serialized user session data as JSON.

| Column       | Type         | Constraints                          | Description              |
| ------------ | ------------ | ------------------------------------ | ------------------------ |
| `user_id`    | VARCHAR(255) | PRIMARY KEY, NOT NULL                | Unique user identifier   |
| `state_json` | TEXT         | NOT NULL                             | Serialized BotState JSON |
| `created_at` | TIMESTAMP    | NOT NULL, DEFAULT NOW                | Session creation time    |
| `updated_at` | TIMESTAMP    | NOT NULL, DEFAULT NOW, ON UPDATE NOW | Last update time         |

**Indexes:**

- `pk_session_state_user_id` - Primary key on `user_id`
- `idx_session_state_updated_at` - Index on `updated_at` for efficient queries

**Purpose:**

- Store complete user session state
- Track conversation history
- Maintain user context across requests
- Support session recovery

---

## Creating Migrations

### Manual Migration

1. **Create migration file:**

   ```powershell
   python scripts/migrate.py revision "add user preferences table"
   ```

2. **Edit the generated file** in `alembic/versions/`:

   ```python
   def upgrade() -> None:
       op.create_table(
           'user_preferences',
           sa.Column('id', sa.Integer(), primary_key=True),
           sa.Column('user_id', sa.String(255), nullable=False),
           sa.Column('preferences_json', sa.Text(), nullable=False),
       )

   def downgrade() -> None:
       op.drop_table('user_preferences')
   ```

3. **Apply migration:**
   ```powershell
   python scripts/migrate.py upgrade head
   ```

### Auto-Generate Migration

1. **Update SQLAlchemy models** in `app/database/models.py`:

   ```python
   class UserPreferences(Base):
       __tablename__ = 'user_preferences'

       id = Column(Integer, primary_key=True)
       user_id = Column(String(255), nullable=False)
       preferences_json = Column(Text, nullable=False)
   ```

2. **Generate migration:**

   ```powershell
   python scripts/migrate.py revision "add user preferences" --autogenerate
   ```

3. **Review and apply:**
   ```powershell
   # Always review auto-generated migrations!
   python scripts/migrate.py upgrade head
   ```

---

## Environment Configuration

### SQLite (Default)

No configuration needed. Uses `data/chat_history.db`.

```powershell
# Automatically uses SQLite
python scripts/migrate.py upgrade head
```

### PostgreSQL/Neon

Set environment variables:

```powershell
# Windows PowerShell
$env:DATABASE="neon"
$env:DATABASE_URL="postgresql://user:password@host:5432/database"
python scripts/migrate.py upgrade head
```

```bash
# Linux/Mac
export DATABASE=neon
export DATABASE_URL=postgresql://user:password@host:5432/database
python scripts/migrate.py upgrade head
```

### `.env` File

```ini
# .env file
DATABASE=neon
DATABASE_URL=postgresql://user:password@host:5432/database
```

---

## Best Practices

### 1. Always Review Migrations

```powershell
# After creating migration, review before applying
cat alembic/versions/[revision]_*.py

# Test on development database first
python scripts/migrate.py upgrade head
```

### 2. Create Descriptive Messages

```powershell
# Good
python scripts/migrate.py revision "add user_preferences table with indexes"

# Bad
python scripts/migrate.py revision "update"
```

### 3. Test Rollbacks

```powershell
# Test that downgrade works
python scripts/migrate.py upgrade head
python scripts/migrate.py downgrade -1
python scripts/migrate.py upgrade head
```

### 4. Backup Before Major Changes

```powershell
# SQLite backup
Copy-Item data/chat_history.db data/chat_history.db.backup

# PostgreSQL backup
pg_dump $DATABASE_URL > backup.sql
```

### 5. Version Control

```bash
# Always commit migration files
git add alembic/versions/*.py
git commit -m "Add migration: add user preferences table"
```

### 6. Production Deployment

```powershell
# 1. Backup production database
# 2. Test migrations on staging
# 3. Apply to production
DATABASE=neon DATABASE_URL=$PROD_URL python scripts/migrate.py upgrade head
```

---

## Troubleshooting

### Issue: "table already exists"

**Cause:** Database has tables but no Alembic version tracking.

**Solution:**

```powershell
# Mark current state without running migrations
alembic stamp head
```

### Issue: Migration fails midway

**Cause:** Error in migration script or database constraint violation.

**Solution:**

```powershell
# 1. Check current state
python scripts/migrate.py current

# 2. Fix the issue (manual SQL or fix migration)
# 3. Try again or rollback
python scripts/migrate.py downgrade -1
```

### Issue: "Can't locate revision"

**Cause:** Migration file missing or revision ID mismatch.

**Solution:**

```powershell
# Check migration history
python scripts/migrate.py history

# Verify all migration files exist
ls alembic/versions/
```

### Issue: Different database on different machines

**Cause:** Environment variable not set correctly.

**Solution:**

```powershell
# Check configuration
python scripts/migrate.py info

# Set environment variables
$env:DATABASE="sqlite"  # or "neon"
```

### Issue: "No such table: alembic_version"

**Cause:** Database not initialized with Alembic.

**Solution:**

```powershell
# Initialize Alembic version tracking
python scripts/migrate.py init
```

---

## Migration Workflow

### Development Workflow

```powershell
# 1. Start development
conda activate botenv

# 2. Make code changes to models
# Edit app/database/models.py

# 3. Create migration
python scripts/migrate.py revision "description" --autogenerate

# 4. Review generated migration
code alembic/versions/[new_file].py

# 5. Apply migration
python scripts/migrate.py upgrade head

# 6. Test application
python main.py

# 7. Commit changes
git add alembic/versions/*.py app/database/models.py
git commit -m "Add: new database feature"
```

### Production Deployment Workflow

```powershell
# 1. Backup production database
pg_dump $PROD_DATABASE_URL > backup_$(date +%Y%m%d).sql

# 2. Test on staging
DATABASE=neon DATABASE_URL=$STAGING_URL python scripts/migrate.py upgrade head

# 3. Verify staging works
# Run tests...

# 4. Apply to production
DATABASE=neon DATABASE_URL=$PROD_URL python scripts/migrate.py upgrade head

# 5. Verify production
DATABASE=neon DATABASE_URL=$PROD_URL python scripts/migrate.py current
```

---

## Integration with Session Manager

The existing `session_manager.py` continues to work seamlessly:

```python
from emailbot.database.session_manager import get_or_create_session, save_state

# Existing code works without changes
state = get_or_create_session(user_id="user123")
save_state(user_id="user123", state=state)
```

Alembic manages schema changes while `session_manager.py` handles data operations.

---

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [BotRunner Architecture](docs/ARCHITECTURE.md)
- [Database Session Management](app/database/session_manager.py)

---

## Summary

✅ **Alembic Setup Complete**

- Migration environment configured
- Initial migration created
- CLI tool for easy management
- Support for SQLite and PostgreSQL
- Version-controlled schema changes

**Quick Commands:**

```powershell
python scripts/migrate.py info      # Check configuration
python scripts/migrate.py current   # See current version
python scripts/migrate.py upgrade head  # Apply migrations
```

For questions or issues, refer to the troubleshooting section above.
