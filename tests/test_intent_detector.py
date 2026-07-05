import unittest

from assistant.intent_detector import detect_intent


class IntentDetectorTests(unittest.TestCase):
    def test_task_creation_intent_for_add_todo(self):
        intent, target = detect_intent("add todo buy milk")
        self.assertEqual(intent, "task_create")
        self.assertEqual(target, "add todo buy milk")

    def test_task_creation_intent_for_remember_to(self):
        intent, target = detect_intent("remember to buy milk")
        self.assertEqual(intent, "task_create")
        self.assertEqual(target, "remember to buy milk")

    def test_task_creation_intent_for_put_on_todo_list(self):
        intent, target = detect_intent("put buy milk on my todo list")
        self.assertEqual(intent, "task_create")
        self.assertEqual(target, "put buy milk on my todo list")

    def test_task_creation_does_not_match_music(self):
        intent, target = detect_intent("add this to my tasks")
        self.assertEqual(intent, "task_create")
        self.assertEqual(target, "add this to my tasks")

    def test_music_intent_still_matches_play(self):
        intent, target = detect_intent("play baahubali song")
        self.assertEqual(intent, "music")
        self.assertEqual(target["action"], "play_music")

    def test_music_intent_with_add_to_queue(self):
        intent, target = detect_intent("add this song to queue")
        self.assertEqual(intent, "music")
        self.assertEqual(target["action"], "add_to_queue")

    def test_remind_me_to_with_time_becomes_reminder(self):
        intent, target = detect_intent("remind me to buy milk at 5pm")
        self.assertEqual(intent, "reminder")
        self.assertEqual(target, "remind me to buy milk at 5pm")


if __name__ == "__main__":
    unittest.main()
