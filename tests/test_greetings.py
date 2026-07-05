from datetime import datetime

import assistant.core_process as core_process


class FixedDateTime:
    @classmethod
    def now(cls):
        return datetime(2024, 1, 1, 8, 30)


def test_greeting_only_uses_time_based_message(monkeypatch):
    monkeypatch.setattr(core_process, "datetime", FixedDateTime)

    result = core_process.process_command("Hello!!")

    assert result["response"] == "Good Morning! How can I help you today?"


def test_greeting_with_request_prefixes_time_based_greeting(monkeypatch):
    monkeypatch.setattr(core_process, "datetime", FixedDateTime)
    monkeypatch.setattr(core_process, "detect_intent", lambda command: ("weather", {"city": "Tirupati"}))
    monkeypatch.setattr(
        core_process,
        "get_weather_by_city",
        lambda city: {
            "city": "Tirupati",
            "condition": "Sunny",
            "temperature": 30,
            "feels_like": 32,
            "humidity": 50,
        },
    )

    result = core_process.process_command("Good morning!!! what's the weather?")

    assert result["response"].startswith("Good Morning!")
    assert "Tirupati" in result["response"]


def test_wake_word_without_request_uses_time_based_greeting(monkeypatch):
    monkeypatch.setattr(core_process, "datetime", FixedDateTime)

    result = core_process.process_command("hey assistant")

    assert result["response"] == "Good Morning! How can I help you today?"


def test_wake_word_with_listening_acknowledgment_uses_greeting(monkeypatch):
    monkeypatch.setattr(core_process, "datetime", FixedDateTime)

    result = core_process.process_command("hey assistant yes I'm listening")

    assert result["response"] == "Good Morning! How can I help you today?"
