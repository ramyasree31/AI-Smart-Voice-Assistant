import importlib
import os
import sys


def test_test_environment_uses_isolated_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("TESTING", "1")
    sys.modules.pop("db", None)

    db = importlib.import_module("db")

    assert db.DATABASE_URL.endswith("test_assistant.db")
    assert db.DATABASE_URL != "sqlite:///./assistant.db"
