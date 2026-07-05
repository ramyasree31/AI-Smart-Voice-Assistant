import unittest
from datetime import datetime, timedelta

from assistant.task_manager import _parse_datetime, handle_todo_command
from db import SessionLocal
from main import VoiceRequest, chat
from models import TodoItem, User


class TodoParsingTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.db.query(TodoItem).delete()
        self.db.query(User).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_todo_command_extracts_title_and_deadline(self):
        response = handle_todo_command(
            "stop ad task to do homework before 12 o'clock",
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

    def test_add_todo_with_finish_phrase_does_not_complete_existing_item(self):
        response = handle_todo_command(
            "add todo finish homework by tomorrow at 5pm",
            self.db,
            None,
            "test-session",
        )

        self.assertIn("todo_id", response)
        self.assertEqual(response["response"].startswith("finish homework"), True)
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "test-session").one()
        self.assertEqual(todo.title, "finish homework")
        self.assertIsNotNone(todo.due_at)

    def test_voice_todo_command_extracts_category_reminder_recurrence_and_subtasks(self):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        response = handle_todo_command(
            "add work task prepare report tomorrow at 3pm reminder at 2pm every weekday with subtasks draft outline and review draft",
            self.db,
            None,
            "test-session",
        )

        self.assertIn("todo_id", response)
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "test-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.category, "Work")
        self.assertEqual(todo.date, tomorrow)
        self.assertEqual(todo.reminder, "14:00")
        self.assertEqual(todo.recurrence, "weekdays")
        self.assertEqual(todo.repeat_days, "Mon,Tue,Wed,Thu,Fri")
        self.assertEqual(todo.subtasks, "draft outline\nreview draft")

    def test_todo_command_asks_for_next_missing_field_in_chat_flow(self):
        first_response = handle_todo_command(
            "add task buy groceries",
            self.db,
            None,
            "test-session",
        )
        self.assertIn("reminder", first_response["response"].lower())

        second_response = handle_todo_command(
            "reminder at 5pm",
            self.db,
            None,
            "test-session",
        )
        self.assertIn("category", second_response["response"].lower())

        third_response = handle_todo_command(
            "work",
            self.db,
            None,
            "test-session",
        )
        self.assertIn("repeat", third_response["response"].lower())

        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "test-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.category, "Work")
        self.assertEqual(todo.reminder, "17:00")

    def test_chat_route_uses_pending_todo_context_for_follow_up(self):
        handle_todo_command(
            "add task finish frontend",
            self.db,
            None,
            "chat-session",
        )

        response = chat(
            VoiceRequest(command="12:00 pm", session_id="chat-session"),
            db=self.db,
            current_user=None,
        )

        self.assertIn("category", response["response"].lower())
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "chat-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.reminder, "12:00")

    def test_todo_follow_up_prompts_include_choice_options(self):
        first_response = handle_todo_command(
            "add task buy groceries",
            self.db,
            None,
            "choice-session",
        )
        self.assertNotIn("choices", first_response)

        second_response = handle_todo_command(
            "8:00 am",
            self.db,
            None,
            "choice-session",
        )
        self.assertEqual(second_response["field"], "category")
        self.assertEqual(second_response["choices"], ["Personal", "Work", "Test"])

        third_response = handle_todo_command(
            "work",
            self.db,
            None,
            "choice-session",
        )
        self.assertEqual(third_response["field"], "repeat")
        self.assertEqual(third_response["choices"], ["One-time", "Daily", "Mon-Fri", "Custom"])

    def test_chat_repeat_follow_up_accepts_task_detail_repeat_values(self):
        handle_todo_command(
            "add task learn python",
            self.db,
            None,
            "repeat-values-session",
        )
        handle_todo_command(
            "12:00 pm",
            self.db,
            None,
            "repeat-values-session",
        )
        handle_todo_command(
            "work",
            self.db,
            None,
            "repeat-values-session",
        )

        response = handle_todo_command(
            "Custom",
            self.db,
            None,
            "repeat-values-session",
        )

        self.assertEqual(response["field"], "repeat_days")
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "repeat-values-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.recurrence, "custom")
        self.assertIsNone(todo.repeat_days)

    def test_voice_repeat_phrase_one_day_to_friday_maps_to_weekdays(self):
        handle_todo_command(
            "add task learn python",
            self.db,
            None,
            "voice-repeat-session",
        )
        handle_todo_command(
            "5:30 am",
            self.db,
            None,
            "voice-repeat-session",
        )
        handle_todo_command(
            "work",
            self.db,
            None,
            "voice-repeat-session",
        )

        response = handle_todo_command(
            "one day to friday",
            self.db,
            None,
            "voice-repeat-session",
        )

        self.assertEqual(response["field"], "due_date")
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "voice-repeat-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.recurrence, "weekdays")
        self.assertEqual(todo.repeat_days, "Mon,Tue,Wed,Thu,Fri")

    def test_voice_day_list_and_date_phrase_are_accepted(self):
        handle_todo_command(
            "add task learn python",
            self.db,
            None,
            "voice-date-session",
        )
        handle_todo_command(
            "5:30 am",
            self.db,
            None,
            "voice-date-session",
        )
        handle_todo_command(
            "work",
            self.db,
            None,
            "voice-date-session",
        )
        handle_todo_command(
            "custom",
            self.db,
            None,
            "voice-date-session",
        )

        response = handle_todo_command(
            "sunday friday",
            self.db,
            None,
            "voice-date-session",
        )

        self.assertEqual(response["field"], "due_date")
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "voice-date-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.recurrence, "custom")
        self.assertEqual(todo.repeat_days, "Sun,Fri")

        due_date_response = handle_todo_command(
            "12th July",
            self.db,
            None,
            "voice-date-session",
        )

        self.assertEqual(due_date_response["field"], "subtasks")
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "voice-date-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.date, f"{datetime.now().year}-07-12")

    def test_specific_days_repeat_choice_asks_for_days(self):
        handle_todo_command(
            "add task learn python",
            self.db,
            None,
            "specific-days-session",
        )
        handle_todo_command(
            "12:00 pm",
            self.db,
            None,
            "specific-days-session",
        )
        handle_todo_command(
            "work",
            self.db,
            None,
            "specific-days-session",
        )

        response = handle_todo_command(
            "specific days",
            self.db,
            None,
            "specific-days-session",
        )

        self.assertEqual(response["field"], "repeat_days")
        self.assertIn("which days", response["response"].lower())
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "specific-days-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.recurrence, "custom")
        self.assertIsNone(todo.repeat_days)

    def test_short_weekday_button_value_sets_repeat_days(self):
        handle_todo_command(
            "add task learn python",
            self.db,
            None,
            "weekday-button-session",
        )
        handle_todo_command(
            "12:00 pm",
            self.db,
            None,
            "weekday-button-session",
        )
        handle_todo_command(
            "work",
            self.db,
            None,
            "weekday-button-session",
        )

        response = handle_todo_command(
            "Mon",
            self.db,
            None,
            "weekday-button-session",
        )

        self.assertEqual(response["field"], "repeat_days")
        self.assertIn("repeat on", response["response"].lower())
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "weekday-button-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.recurrence, "custom")
        self.assertEqual(todo.repeat_days, "Mon")

    def test_parse_datetime_supports_spaced_dates(self):
        parsed = _parse_datetime("12 th july")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.month, 7)
        self.assertEqual(parsed.day, 12)

    def test_parse_datetime_moves_past_month_day_dates_to_next_year(self):
        now = datetime.now()
        parsed = _parse_datetime("due date 12 january")
        self.assertIsNotNone(parsed)
        expected = datetime(now.year, 1, 12)
        if expected < now.replace(hour=0, minute=0, second=0, microsecond=0):
            expected = expected.replace(year=now.year + 1)
        self.assertEqual(parsed.date(), expected.date())

    def test_specific_days_follow_up_keeps_collecting_days(self):
        handle_todo_command(
            "add task learn python",
            self.db,
            None,
            "repeat-days-session",
        )
        handle_todo_command(
            "12:00 pm",
            self.db,
            None,
            "repeat-days-session",
        )
        handle_todo_command(
            "work",
            self.db,
            None,
            "repeat-days-session",
        )

        handle_todo_command(
            "specific days",
            self.db,
            None,
            "repeat-days-session",
        )

        response = handle_todo_command(
            "Mon",
            self.db,
            None,
            "repeat-days-session",
        )

        self.assertEqual(response["field"], "repeat_days")
        self.assertIn("repeat on", response["response"].lower())
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "repeat-days-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.recurrence, "custom")
        self.assertEqual(todo.repeat_days, "Mon")

    def test_specific_days_follow_up_accepts_multiple_days_in_one_reply(self):
        handle_todo_command(
            "add task learn python",
            self.db,
            None,
            "multi-day-session",
        )
        handle_todo_command(
            "12:00 pm",
            self.db,
            None,
            "multi-day-session",
        )
        handle_todo_command(
            "work",
            self.db,
            None,
            "multi-day-session",
        )
        handle_todo_command(
            "specific days",
            self.db,
            None,
            "multi-day-session",
        )

        response = handle_todo_command(
            "Mon Wed Fri",
            self.db,
            None,
            "multi-day-session",
        )

        self.assertEqual(response["field"], "due_date")
        todo = self.db.query(TodoItem).filter(TodoItem.session_id == "multi-day-session").order_by(TodoItem.created_at.desc()).first()
        self.assertEqual(todo.recurrence, "custom")
        self.assertEqual(todo.repeat_days, "Mon,Wed,Fri")


if __name__ == "__main__":
    unittest.main()
