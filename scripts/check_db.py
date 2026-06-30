import sqlite3

conn = sqlite3.connect('assistant.db')
cur = conn.cursor()

print('Conversations:')
for row in cur.execute('SELECT id, user_id, session_id, title, created_at, updated_at FROM conversations'):
    print(row)

print('\nMessages:')
for row in cur.execute('SELECT id, conversation_id, sender, message, timestamp FROM messages ORDER BY timestamp DESC LIMIT 20'):
    print(row)

conn.close()
