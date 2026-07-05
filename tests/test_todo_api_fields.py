import unittest
from fastapi.testclient import TestClient
from db import SessionLocal
from models import TodoItem, User
import main
from auth import create_access_token


class TodoApiFieldsTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.db.query(TodoItem).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.db.close()

    def test_todo_api_saves_rich_task_fields(self):
        user = User(username="todo_user", email="todo@example.com", password_hash="x")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        token = create_access_token({"user_id": user.id})
        payload = {
            "title": "Ship release",
            "description": "Prepare deployment checklist",
            "date": "2026-07-02",
            "start_time": "09:00",
            "end_time": "10:30",
            "reminder": "30 minutes before",
            "subtasks": "Draft notes\nConfirm review",
        }

        response = self.client.post("/todos", json=payload, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        created = response.json()
        self.assertEqual(created["date"], "2026-07-02")
        self.assertEqual(created["start_time"], "09:00")
        self.assertEqual(created["end_time"], "10:30")
        self.assertEqual(created["reminder"], "30 minutes before")
        self.assertEqual(created["subtasks"], "Draft notes\nConfirm review")

        list_response = self.client.get("/todos", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(list_response.status_code, 200)
        tasks = list_response.json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["date"], "2026-07-02")
        self.assertEqual(tasks[0]["reminder"], "30 minutes before")


if __name__ == "__main__":
    unittest.main()
