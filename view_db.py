from db import SessionLocal
from models import User, TodoItem, Reminder, Conversation, Message

def iso(v):
    return v.isoformat() if v is not None else None

if __name__ == '__main__':
    db = SessionLocal()
    try:
        print('--- Users ---')
        for u in db.query(User).all():
            print(u.id, u.username, u.email, iso(u.created_at))
        print('\n--- Todo Items ---')
        for t in db.query(TodoItem).order_by(TodoItem.created_at.desc()).limit(100):
            print(t.id, t.title, 'completed' if t.is_completed else 'pending', iso(t.due_at), 'user_id=', t.user_id, 'session_id=', t.session_id)
        print('\n--- Reminders ---')
        for r in db.query(Reminder).order_by(Reminder.due_at.desc()).limit(100):
            print(r.id, r.title, iso(r.due_at), 'notified=' + str(bool(r.is_notified)), 'completed=' + str(bool(r.is_completed)), 'user_id=', r.user_id, 'session_id=', r.session_id)
        print('\n--- Conversations ---')
        for c in db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(50):
            print(c.id, 'user_id=' + str(c.user_id), 'session_id=' + str(c.session_id), 'title=' + str(c.title), 'updated=' + str(iso(c.updated_at)))
        print('\n--- Messages (last 100) ---')
        for m in db.query(Message).order_by(Message.timestamp.desc()).limit(100):
            print(m.id, 'conv=', m.conversation_id, m.role, iso(m.timestamp), m.content)
    finally:
        db.close()
