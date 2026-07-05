import unittest
from fastapi.testclient import TestClient
from db import SessionLocal
from models import TodoItem, User
import main
from auth import create_access_token


class TodoChatPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.db.query(TodoItem).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.db.close()

    def test_chat_todo_command_with_session_id_persists(self):
        session_id = "test-session"
        response = self.client.post(
            "/chat",
            json={
                "command": "add todo finish homework by tomorrow at 5pm",
                "session_id": session_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("todo_id", payload)

        todo = self.db.query(TodoItem).filter(TodoItem.session_id == session_id).one()
        self.assertEqual(todo.title, "finish homework")
        self.assertIsNotNone(todo.due_at)

    def test_chat_todo_command_with_user_token_persists_user_id(self):
        user = User(username="todo_user", email="todo_user@example.com", password_hash="x")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        token = create_access_token({"user_id": user.id})
        response = self.client.post(
            "/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "command": "add todo get groceries at 11pm",
                "session_id": "unused-session",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("todo_id", payload)

        todo = self.db.query(TodoItem).filter(TodoItem.user_id == user.id).one()
        self.assertEqual(todo.title, "get groceries")
        self.assertIsNotNone(todo.due_at)


if __name__ == "__main__":
    unittest.main()
