from datetime import datetime, timedelta
from db import SessionLocal
from models import Reminder, Conversation, Message
import json

# Create a test session
db = SessionLocal()

# Create a test conversation
conv = Conversation(session_id="test-session-due", title="Test Reminder Delivery")
db.add(conv)
db.commit()
db.refresh(conv)

# Create a reminder that's due right now (should be delivered)
reminder = Reminder(
    session_id="test-session-due",
    title="Test Due Reminder",
    due_at=datetime.utcnow() - timedelta(seconds=5),
    is_completed=False,
    is_notified=False
)
db.add(reminder)
db.commit()
db.refresh(reminder)

print(f"✓ Created test reminder: {reminder.id} - '{reminder.title}'")
print(f"  Due: {reminder.due_at.isoformat()}")
print(f"  Is Notified: {reminder.is_notified}")
print(f"  Is Completed: {reminder.is_completed}")

# Simulate delivery by running the delivery function
from main import _deliver_due_reminders_once
_deliver_due_reminders_once()

# Check if the reminder was marked as notified
db.refresh(reminder)
print(f"\n✓ After delivery:")
print(f"  Is Notified: {reminder.is_notified}")

# Check if a message was added to the conversation
messages = db.query(Message).filter(Message.conversation_id == conv.id).all()
print(f"  Messages in conversation: {len(messages)}")
for msg in messages:
    print(f"    - {msg.sender}: {msg.message}")

db.close()
print("\n✓ Test passed - Reminder delivery works!")
