# view_todos.py
import sqlite3
conn = sqlite3.connect('assistant.db')
for row in conn.execute("SELECT id,title,is_completed,due_at FROM todo_items ORDER BY created_at DESC LIMIT 50"):
    print(row)
conn.close()