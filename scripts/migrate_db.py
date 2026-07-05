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
            description TEXT,
            date TEXT,
            start_time TEXT,
            end_time TEXT,
            priority TEXT DEFAULT 'Medium',
            category TEXT DEFAULT 'Personal',
            status TEXT DEFAULT 'pending',
            due_at DATETIME,
            is_completed BOOLEAN DEFAULT 0,
            is_notified BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
else:
    print('reminders table already exists')

# Add reminder columns if missing or rebuild if the legacy schema still uses NOT NULL due_at
cur.execute("PRAGMA table_info(reminders)")
reminder_info = cur.fetchall()
reminder_cols = [r[1] for r in reminder_info]
reminder_notnull = {r[1]: r[3] for r in reminder_info}
needs_reminder_rebuild = any(
    col not in reminder_cols
    for col in ['description', 'date', 'start_time', 'end_time', 'priority', 'category', 'status', 'updated_at']
) or reminder_notnull.get('due_at') == 1
if needs_reminder_rebuild:
    print('Rebuilding reminders table with the modern schema')
    cur.execute('''
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
            is_completed BOOLEAN DEFAULT 0,
            is_notified BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        INSERT INTO reminders_new (
            id, user_id, session_id, title, description, date, start_time, end_time,
            priority, category, status, due_at, is_completed, is_notified, created_at, updated_at
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
            is_completed,
            is_notified,
            created_at,
            COALESCE(updated_at, created_at)
        FROM reminders
    ''')
    cur.execute('DROP TABLE reminders')
    cur.execute('ALTER TABLE reminders_new RENAME TO reminders')
    conn.commit()
else:
    for col, ddl in [
        ('description', "ALTER TABLE reminders ADD COLUMN description TEXT"),
        ('date', "ALTER TABLE reminders ADD COLUMN date TEXT"),
        ('start_time', "ALTER TABLE reminders ADD COLUMN start_time TEXT"),
        ('end_time', "ALTER TABLE reminders ADD COLUMN end_time TEXT"),
        ('priority', "ALTER TABLE reminders ADD COLUMN priority TEXT DEFAULT 'Medium'"),
        ('category', "ALTER TABLE reminders ADD COLUMN category TEXT DEFAULT 'Personal'"),
        ('status', "ALTER TABLE reminders ADD COLUMN status TEXT DEFAULT 'pending'"),
        ('updated_at', "ALTER TABLE reminders ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"),
    ]:
        if col not in reminder_cols:
            print(f'Adding {col} column to reminders')
            cur.execute(ddl)
            conn.commit()

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
