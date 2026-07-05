import unittest
from fastapi.testclient import TestClient
from db import SessionLocal
from models import Reminder, User
import main
from auth import create_access_token


class ReminderApiTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.db.query(Reminder).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.db.close()

    def test_list_reminders_returns_task_fields(self):
        user = User(username="reminder_user", email="reminder@example.com", password_hash="x")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        reminder = Reminder(
            user_id=user.id,
            title="Study session",
            description="Finish the AI project",
            date="2026-06-30",
            start_time="10:00",
            end_time="12:00",
            priority="High",
            category="Study",
            status="pending",
            due_at=None,
        )
        self.db.add(reminder)
        self.db.commit()

        token = create_access_token({"user_id": user.id})
        response = self.client.get("/reminders", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["title"], "Study session")
        self.assertEqual(payload[0]["priority"], "High")
        self.assertEqual(payload[0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
