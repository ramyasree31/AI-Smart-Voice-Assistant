import sqlite3

conn = sqlite3.connect('assistant.db')
cur = conn.cursor()

# Check if session_id column exists
cur.execute("PRAGMA table_info(conversations)")
cols = [r[1] for r in cur.fetchall()]
if 'session_id' not in cols:
    print('Adding session_id column to conversations')
    cur.execute("ALTER TABLE conversations ADD COLUMN session_id TEXT")
    conn.commit()
else:
    print('session_id column already exists')

# Ensure user_id is nullable. SQLite can't alter column nullability directly,
# so rebuild the table if necessary.
cur.execute("PRAGMA table_info(conversations)")
info = cur.fetchall()
user_col = None
for col in info:
    if col[1] == 'user_id':
        user_col = col
        break

# col format: (cid, name, type, notnull, dflt_value, pk)
if user_col and user_col[3] == 1:
    print('Making conversations.user_id nullable by rebuilding table')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS conversations_new (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            session_id TEXT,
            title TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )
    ''')
    cur.execute('''
        INSERT INTO conversations_new (id, user_id, session_id, title, created_at, updated_at)
        SELECT id, user_id, session_id, title, created_at, updated_at FROM conversations
    ''')
    cur.execute('DROP TABLE conversations')
    cur.execute('ALTER TABLE conversations_new RENAME TO conversations')
    conn.commit()
    print('Rebuilt conversations table with nullable user_id')
else:
    print('conversations.user_id already nullable or not present')

# Add reminder and todo tables if needed
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reminders'")
if not cur.fetchone():
    print('Creating reminders table')
    cur.execute('''
        CREATE TABLE reminders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            session_id TEXT,
            title TEXT NOT NULL,
            due_at DATETIME NOT NULL,
            is_completed BOOLEAN DEFAULT 0,
                is_notified BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
else:
    print('reminders table already exists')

# Add is_notified to reminders if missing
cur.execute("PRAGMA table_info(reminders)")
reminder_cols = [r[1] for r in cur.fetchall()]
if 'is_notified' not in reminder_cols:
    print('Adding is_notified column to reminders')
    cur.execute("ALTER TABLE reminders ADD COLUMN is_notified BOOLEAN DEFAULT 0")
    conn.commit()
else:
    print('is_notified column already exists')

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='todo_items'")
if not cur.fetchone():
    print('Creating todo_items table')
    cur.execute('''
        CREATE TABLE todo_items (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            session_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            is_completed BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            due_at DATETIME
        )
    ''')
    conn.commit()
else:
    print('todo_items table already exists')

conn.close()
