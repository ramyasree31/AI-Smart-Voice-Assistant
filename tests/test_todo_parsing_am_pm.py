import unittest

from assistant.task_manager import handle_todo_command
from db import SessionLocal
from models import TodoItem, User


class TodoParsingAmPmTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.db.query(TodoItem).delete()
        self.db.query(User).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_todo_command_handles_pm_spaced_format(self):
        response = handle_todo_command(
            "hey assistant homework p m",
            self.db,
            None,
            "test-session",
        )

        self.assertEqual(response["response"].startswith("homework"), True)
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "test-session").one()
        self.assertEqual(todo.title, "homework")

    def test_todo_command_strips_wake_phrase(self):
        response = handle_todo_command(
            "hey assistant stop ad task to do homework before 12:00 p.m.",
            self.db,
            None,
            "test-session",
        )

        self.assertEqual(response["response"].startswith("homework"), True)
        self.assertIn("Task end", response["response"])
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "test-session").one()
        self.assertEqual(todo.title, "homework")
        self.assertEqual(todo.due_at.hour, 12)
        self.assertEqual(todo.due_at.minute, 0)

    def test_pending_todo_reminder_follow_up_accepts_a_m_format(self):
        handle_todo_command(
            "add task learn python",
            self.db,
            None,
            "reminder-follow-up-session",
        )

        response = handle_todo_command(
            "5:30 a.m.",
            self.db,
            None,
            "reminder-follow-up-session",
        )

        self.assertEqual(response["field"], "category")
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "reminder-follow-up-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.reminder, "05:30")


if __name__ == "__main__":
    unittest.main()
