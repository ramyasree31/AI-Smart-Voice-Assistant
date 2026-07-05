import unittest
from datetime import datetime
from db import SessionLocal
from models import Conversation, Message, User
import main


class ConversationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.db.query(Message).delete()
        self.db.query(Conversation).delete()
        self.db.query(User).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_creates_one_conversation_per_day_for_user(self):
        now = datetime(2026, 6, 30, 10, 0, 0)
        conv1 = main._get_or_create_conversation_for_context(self.db, user_id=1, session_id=None, now=now)
        conv2 = main._get_or_create_conversation_for_context(self.db, user_id=1, session_id=None, now=now)
        self.assertEqual(conv1.id, conv2.id)
        self.assertEqual(self.db.query(Conversation).count(), 1)

        next_day = datetime(2026, 7, 1, 8, 0, 0)
        conv3 = main._get_or_create_conversation_for_context(self.db, user_id=1, session_id=None, now=next_day)
        self.assertNotEqual(conv1.id, conv3.id)
        self.assertEqual(self.db.query(Conversation).count(), 2)

    def test_search_rename_and_delete_conversations(self):
        user = User(username="history_user", email="history@example.com", password_hash="x")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        weather_conv = Conversation(user_id=user.id, title="Weather Questions")
        self.db.add(weather_conv)
        self.db.flush()
        self.db.add(Message(conversation_id=weather_conv.id, role="user", content="What is today's weather?"))

        project_conv = Conversation(user_id=user.id, title="Project Discussion")
        self.db.add(project_conv)
        self.db.flush()
        self.db.add(Message(conversation_id=project_conv.id, role="user", content="Let's build a route planner."))
        self.db.commit()

        results = main.list_conversations(db=self.db, current_user=user, q="weather", limit=10, offset=0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Weather Questions")

        renamed = main.patch_conversation(conv_id=weather_conv.id, payload={"title": "Weather Planning"}, db=self.db, current_user=user)
        self.assertEqual(renamed["title"], "Weather Planning")

        deleted = main.delete_conversation(conv_id=project_conv.id, db=self.db, current_user=user)
        self.assertTrue(deleted["ok"])
        self.assertEqual(self.db.query(Conversation).count(), 1)


if __name__ == '__main__':
    unittest.main()
