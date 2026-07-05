import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if os.getenv("TESTING") == "1":
        DATABASE_URL = "sqlite:///./test_assistant.db"
    else:
        DATABASE_URL = "sqlite:///./assistant.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _sqlite_path_from_url(url: str) -> str | None:
    if not url.startswith("sqlite:///"):
        return None
    path = url[len("sqlite:///"):]
    if not path:
        return None
    return os.path.abspath(path)


def migrate_database() -> None:
    db_path = _sqlite_path_from_url(str(engine.url))
    if not db_path or not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    if cur.fetchone():
        cols = [row[1] for row in cur.execute("PRAGMA table_info(messages)")]
        if "role" in cols and "content" in cols and "sender" not in cols and "message" not in cols:
            pass
        else:
            cur.execute("""
                CREATE TABLE messages_new (
                    id INTEGER PRIMARY KEY,
                    conversation_id INTEGER NOT NULL,
                    role VARCHAR(32) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME
                )
            """)

            role_expr = "role" if "role" in cols else ("sender" if "sender" in cols else "'assistant'")
            content_expr = "content" if "content" in cols else ("message" if "message" in cols else "''")

            cur.execute(f"""
                INSERT INTO messages_new (id, conversation_id, role, content, timestamp)
                SELECT id, conversation_id, {role_expr}, {content_expr}, timestamp
                FROM messages
            """)
            cur.execute("DROP TABLE messages")
            cur.execute("ALTER TABLE messages_new RENAME TO messages")

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reminders'")
    if cur.fetchone():
        reminder_cols = [row[1] for row in cur.execute("PRAGMA table_info(reminders)")]
        reminder_notnull = {row[1]: row[3] for row in cur.execute("PRAGMA table_info(reminders)")}
        needs_reminder_rebuild = any(
            col not in reminder_cols
            for col in ["description", "date", "start_time", "end_time", "priority", "category", "status", "updated_at"]
        ) or reminder_notnull.get("due_at") == 1
        if needs_reminder_rebuild:
            cur.execute("""
                CREATE TABLE reminders_new (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    session_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    priority TEXT DEFAULT 'Medium',
                    category TEXT DEFAULT 'Personal',
                    status TEXT DEFAULT 'pending',
                    due_at DATETIME,
                    is_notified BOOLEAN DEFAULT 0,
                    is_completed BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                INSERT INTO reminders_new (
                    id, user_id, session_id, title, description, date, start_time, end_time,
                    priority, category, status, due_at, is_notified, is_completed, created_at, updated_at
                )
                SELECT
                    id, user_id, session_id, title,
                    description,
                    date,
                    start_time,
                    end_time,
                    COALESCE(priority, 'Medium'),
                    COALESCE(category, 'Personal'),
                    CASE WHEN COALESCE(status, '') = '' THEN CASE WHEN is_completed = 1 THEN 'completed' ELSE 'pending' END ELSE status END,
                    due_at,
                    is_notified,
                    is_completed,
                    created_at,
                    COALESCE(updated_at, created_at)
                FROM reminders
            """)
            cur.execute("DROP TABLE reminders")
            cur.execute("ALTER TABLE reminders_new RENAME TO reminders")

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='todo_items'")
    if cur.fetchone():
        todo_cols = [row[1] for row in cur.execute("PRAGMA table_info(todo_items)")]
        todo_columns = [
            ("date", "ALTER TABLE todo_items ADD COLUMN date TEXT"),
            ("start_time", "ALTER TABLE todo_items ADD COLUMN start_time TEXT"),
            ("end_time", "ALTER TABLE todo_items ADD COLUMN end_time TEXT"),
            ("reminder", "ALTER TABLE todo_items ADD COLUMN reminder TEXT"),
            ("recurrence", "ALTER TABLE todo_items ADD COLUMN recurrence TEXT DEFAULT 'one_time'"),
            ("repeat_days", "ALTER TABLE todo_items ADD COLUMN repeat_days TEXT"),
            ("subtasks", "ALTER TABLE todo_items ADD COLUMN subtasks TEXT"),
            ("priority", "ALTER TABLE todo_items ADD COLUMN priority TEXT DEFAULT 'Medium'"),
            ("category", "ALTER TABLE todo_items ADD COLUMN category TEXT DEFAULT 'Personal'"),
            ("updated_at", "ALTER TABLE todo_items ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"),
        ]
        for col_name, alter_sql in todo_columns:
            if col_name not in todo_cols:
                cur.execute(alter_sql)

    conn.commit()
    conn.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
