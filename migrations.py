# ============================================================
# Feedback Analyser — migrations.py
# Database schema versioning and migration scripts
# Run: python migrations.py
# ============================================================

import os
import datetime
import sqlite3
from sqlalchemy import create_engine, text, inspect

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./feedback_analyser.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# ── Migration Registry ────────────────────────────────────────
# Each migration has a version number, description, and SQL to run.
# Migrations are applied in order and tracked in a migrations table.

MIGRATIONS = [
    {
        "version":     1,
        "description": "Initial schema — reviews, jobs, issues, reports tables",
        "up": """
            CREATE TABLE IF NOT EXISTS reviews (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id       TEXT    UNIQUE NOT NULL,
                source          TEXT    NOT NULL,
                date            DATE    NOT NULL,
                rating          INTEGER NOT NULL DEFAULT 3,
                text            TEXT    NOT NULL,
                thumbs_up       INTEGER DEFAULT 0,
                sentiment_label TEXT,
                sentiment_score REAL,
                keywords        TEXT,
                is_flagged      INTEGER DEFAULT 0,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                app_id          TEXT
            );

            CREATE TABLE IF NOT EXISTS analysis_jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT    UNIQUE NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'running',
                message     TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS issues (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_keyword       TEXT    NOT NULL,
                priority            TEXT    NOT NULL,
                frequency           INTEGER DEFAULT 0,
                recent_count        INTEGER DEFAULT 0,
                avg_sentiment_score REAL    DEFAULT 0.0,
                sample_quote        TEXT,
                detected_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
                app_id              TEXT
            );

            CREATE TABLE IF NOT EXISTS reports (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id     TEXT    UNIQUE NOT NULL,
                start_date    DATE    NOT NULL,
                end_date      DATE    NOT NULL,
                total_reviews INTEGER DEFAULT 0,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "down": """
            DROP TABLE IF EXISTS reviews;
            DROP TABLE IF EXISTS analysis_jobs;
            DROP TABLE IF EXISTS issues;
            DROP TABLE IF EXISTS reports;
        """,
    },
    {
        "version":     2,
        "description": "Add category and language columns to reviews",
        "up": """
            ALTER TABLE reviews ADD COLUMN category TEXT DEFAULT 'uncategorized';
            ALTER TABLE reviews ADD COLUMN language TEXT DEFAULT 'English';
            ALTER TABLE reviews ADD COLUMN is_urgent INTEGER DEFAULT 0;
        """,
        "down": """
            -- SQLite does not support DROP COLUMN in older versions.
            -- To revert: recreate table without these columns.
            SELECT 1;
        """,
    },
    {
        "version":     3,
        "description": "Add segments table for customer segmentation",
        "up": """
            CREATE TABLE IF NOT EXISTS customer_segments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id   TEXT REFERENCES reviews(review_id),
                segment     TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "down": """
            DROP TABLE IF EXISTS customer_segments;
        """,
    },
    {
        "version":     4,
        "description": "Add competitor_reviews table for benchmarking",
        "up": """
            CREATE TABLE IF NOT EXISTS competitor_reviews (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id       TEXT    UNIQUE NOT NULL,
                competitor_name TEXT    NOT NULL,
                app_id          TEXT    NOT NULL,
                date            DATE    NOT NULL,
                rating          INTEGER NOT NULL DEFAULT 3,
                text            TEXT    NOT NULL,
                sentiment_label TEXT,
                sentiment_score REAL,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "down": """
            DROP TABLE IF EXISTS competitor_reviews;
        """,
    },
    {
        "version":     5,
        "description": "Add roi_calculations table",
        "up": """
            CREATE TABLE IF NOT EXISTS roi_calculations (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_keyword        TEXT    NOT NULL,
                monthly_active_users INTEGER NOT NULL,
                avg_revenue_per_user REAL    NOT NULL,
                fix_cost             REAL    NOT NULL,
                users_affected       INTEGER,
                users_converted      INTEGER,
                revenue_gain         REAL,
                net_roi              REAL,
                calculated_at        DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "down": """
            DROP TABLE IF EXISTS roi_calculations;
        """,
    },
]


# ── Migration Runner ──────────────────────────────────────────

def get_connection():
    return engine.connect()


def ensure_migrations_table(conn):
    """Create the schema_migrations tracking table if it doesn't exist."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     INTEGER PRIMARY KEY,
            description TEXT,
            applied_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.commit()


def get_applied_versions(conn) -> list:
    """Return list of already-applied migration version numbers."""
    result = conn.execute(text("SELECT version FROM schema_migrations ORDER BY version"))
    return [row[0] for row in result.fetchall()]


def apply_migration(conn, migration: dict):
    """Apply a single migration's UP sql."""
    statements = [s.strip() for s in migration["up"].split(";") if s.strip()]
    for stmt in statements:
        try:
            conn.execute(text(stmt))
        except Exception as e:
            print(f"  Warning on statement: {e}")
    conn.execute(
        text("INSERT INTO schema_migrations (version, description) VALUES (:v, :d)"),
        {"v": migration["version"], "d": migration["description"]},
    )
    conn.commit()


def rollback_migration(conn, migration: dict):
    """Roll back a single migration's DOWN sql."""
    statements = [s.strip() for s in migration["down"].split(";") if s.strip()]
    for stmt in statements:
        try:
            conn.execute(text(stmt))
        except Exception as e:
            print(f"  Warning on rollback: {e}")
    conn.execute(
        text("DELETE FROM schema_migrations WHERE version = :v"),
        {"v": migration["version"]},
    )
    conn.commit()


def run_migrations(target_version: int = None):
    """
    Apply all pending migrations up to target_version.
    If target_version is None, apply all.
    """
    print("=" * 50)
    print("  Feedback Analyser — Database Migrations")
    print("=" * 50)

    with get_connection() as conn:
        ensure_migrations_table(conn)
        applied = get_applied_versions(conn)
        print(f"  Applied versions: {applied if applied else 'none'}")
        print()

        pending = [
            m for m in MIGRATIONS
            if m["version"] not in applied
            and (target_version is None or m["version"] <= target_version)
        ]

        if not pending:
            print("  All migrations already applied. Database is up to date.")
            return

        for migration in pending:
            print(f"  Applying v{migration['version']}: {migration['description']}…")
            try:
                apply_migration(conn, migration)
                print(f"  ✅ v{migration['version']} applied successfully")
            except Exception as e:
                print(f"  ❌ v{migration['version']} FAILED: {e}")
                break

    print()
    print("  Migration complete.")
    print("=" * 50)


def rollback(steps: int = 1):
    """Roll back the last N migrations."""
    print(f"Rolling back {steps} migration(s)…")

    with get_connection() as conn:
        ensure_migrations_table(conn)
        applied = get_applied_versions(conn)

        to_rollback = sorted(
            [m for m in MIGRATIONS if m["version"] in applied],
            key=lambda x: x["version"],
            reverse=True,
        )[:steps]

        for migration in to_rollback:
            print(f"  Rolling back v{migration['version']}: {migration['description']}…")
            try:
                rollback_migration(conn, migration)
                print(f"  ✅ v{migration['version']} rolled back")
            except Exception as e:
                print(f"  ❌ Rollback of v{migration['version']} FAILED: {e}")


def status():
    """Print current migration status."""
    print("Migration Status:")
    with get_connection() as conn:
        ensure_migrations_table(conn)
        applied = get_applied_versions(conn)

    for m in MIGRATIONS:
        status_icon = "✅" if m["version"] in applied else "⏳"
        print(f"  {status_icon} v{m['version']}: {m['description']}")


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "migrate"

    if cmd == "migrate":
        run_migrations()
    elif cmd == "rollback":
        steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        rollback(steps)
    elif cmd == "status":
        status()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python migrations.py [migrate|rollback|status]")