import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import Reminder, TodoItem


def _parse_datetime(command: str) -> datetime | None:
    now = datetime.now()
    command = command.lower()

    match = re.search(r"in\s+(\d+)\s*minutes?", command)
    if match:
        return now + timedelta(minutes=int(match.group(1)))

    match = re.search(r"in\s+(\d+)\s*hours?", command)
    if match:
        return now + timedelta(hours=int(match.group(1)))

    match = re.search(r"(today|tomorrow)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", command)
    if match:
        day, hour, minute, period = match.groups()
        hour = int(hour)
        minute = int(minute or 0)
        if period:
            period = period.lower()
            if period == "pm" and hour < 12:
                hour += 12
            if period == "am" and hour == 12:
                hour = 0
        date = now.date()
        if day == "tomorrow":
            date = date + timedelta(days=1)
        result = datetime(year=date.year, month=date.month, day=date.day, hour=hour, minute=minute)
        # If user didn't specify am/pm and the time is already past, assume next occurrence
        if not period and result <= now:
            result = result + timedelta(days=1)
        return result

    match = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", command)
    if match:
        hour, minute, period = match.groups()
        hour = int(hour)
        minute = int(minute or 0)
        if period:
            period = period.lower()
            if period == "pm" and hour < 12:
                hour += 12
            if period == "am" and hour == 12:
                hour = 0
        date = now.date()
        result = datetime(year=date.year, month=date.month, day=date.day, hour=hour, minute=minute)
        # If no am/pm was provided and the parsed time is in the past, schedule for next day
        if not period and result <= now:
            result = result + timedelta(days=1)
        return result

    # Handle phrases like "for 7" or "for 7pm"
    match = re.search(r"for\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", command)
    if match:
        hour, minute, period = match.groups()
        hour = int(hour)
        minute = int(minute or 0)
        if period:
            period = period.lower()
            if period == "pm" and hour < 12:
                hour += 12
            if period == "am" and hour == 12:
                hour = 0
        date = now.date()
        result = datetime(year=date.year, month=date.month, day=date.day, hour=hour, minute=minute)
        if not period and result <= now:
            result = result + timedelta(days=1)
        return result

    match = re.search(r"on\s+(\d{4}-\d{2}-\d{2})(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", command)
    if match:
        date_str, hour, minute, period = match.groups()
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None
        hour = int(hour or 0)
        minute = int(minute or 0)
        if period:
            period = period.lower()
            if period == "pm" and hour < 12:
                hour += 12
            if period == "am" and hour == 12:
                hour = 0
        return datetime(year=date.year, month=date.month, day=date.day, hour=hour, minute=minute)

    return None


def _cleanup_title(command: str, remove_patterns: list[str]) -> str:
    title = command.lower()
    for pattern in remove_patterns:
        title = re.sub(pattern, "", title)
    title = re.sub(r"[^\w\s]", " ", title)
    title = " ".join(title.split()).strip()
    return title


def _owner_filter(query, model, user_id, session_id):
    if user_id:
        return query.filter(model.user_id == user_id)
    return query.filter(model.session_id == session_id)


def handle_reminder_command(command: str, db: Session, user_id: int | None, session_id: str | None):
    normalized = command.lower().strip()

    if re.search(r"\b(list|show|what are|my)\b.*\b(reminders|alarms)\b", normalized):
        query = _owner_filter(db.query(Reminder), Reminder, user_id, session_id)
        reminders = query.order_by(Reminder.due_at).all()
        if not reminders:
            return {"response": "You have no reminders."}
        lines = [
            f"{r.id}. {r.title} - due {r.due_at.strftime('%Y-%m-%d %H:%M')} - {'done' if r.is_completed else 'pending'}"
            for r in reminders
        ]
        return {"response": "Your reminders:\n" + '\n'.join(lines)}

    if re.search(r"\b(complete|done|finish|mark .* done|cancel|delete|remove)\b", normalized) and re.search(r"\b(reminder|alarm)\b", normalized):
        title = _cleanup_title(normalized, [r"\b(complete|done|finish|marked|mark|cancel|delete|remove)\b", r"\b(reminder|alarm)s?\b", r"\b(to|the|my|a|an)\b"]) 
        if title:
            query = _owner_filter(db.query(Reminder), Reminder, user_id, session_id)
            reminder = query.filter(Reminder.title.contains(title)).order_by(Reminder.due_at.desc()).first()
        else:
            query = _owner_filter(db.query(Reminder), Reminder, user_id, session_id)
            reminder = query.filter(Reminder.is_completed == False).order_by(Reminder.due_at.desc()).first()
        if not reminder:
            return {"response": "I couldn't find that reminder to complete."}
        reminder.is_completed = True
        db.commit()
        return {"response": f"Marked reminder '{reminder.title}' as completed."}

    due_at = _parse_datetime(command)
    title = _cleanup_title(command, [
        r"\b(remind me to|remind me|set (an )?alarm (to|for|at)|set (a )?reminder (to|for)|reminder to|alarm for|alarm at|please)\b",
        r"\b(in \d+\s*(minutes?|hours?)|today at \d{1,2}(?::\d{2})?\s*(am|pm)?|tomorrow at \d{1,2}(?::\d{2})?\s*(am|pm)?|on \d{4}-\d{2}-\d{2}(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(am|pm)?)?|at \d{1,2}(?::\d{2})?\s*(am|pm)?)\b",
    ])
    is_alarm = "alarm" in normalized

    if not title:
        title = "Reminder"
    if due_at is None:
        due_at = datetime.now() + timedelta(minutes=5)

    reminder = Reminder(user_id=user_id, session_id=session_id, title=title, due_at=due_at)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    if is_alarm:
        response_text = f"Okay, your alarm to '{reminder.title}' is set for {reminder.due_at.strftime('%Y-%m-%d %I:%M %p')}"
    else:
        response_text = f"Okay, your reminder to '{reminder.title}' is set for {reminder.due_at.strftime('%Y-%m-%d %I:%M %p')}"
    return {"response": response_text, "reminder_id": reminder.id}


def handle_todo_command(command: str, db: Session, user_id: int | None, session_id: str | None):
    normalized = command.lower().strip()

    if re.search(r"\b(list|show|what are|my|view)\b.*\b(todo|tasks|to-do|items)\b", normalized):
        query = _owner_filter(db.query(TodoItem), TodoItem, user_id, session_id)
        todos = query.order_by(TodoItem.created_at).all()
        if not todos:
            return {"response": "You have no todo items."}
        lines = [
            f"{t.id}. {t.title} - {'done' if t.is_completed else 'pending'}" + (f" - due {t.due_at.strftime('%Y-%m-%d %H:%M')}" if t.due_at else "")
            for t in todos
        ]
        return {"response": "Your todo items:\n" + '\n'.join(lines)}

    if re.search(r"\b(complete|done|finish|mark .* done|cancel|delete|remove)\b", normalized) and re.search(r"\b(todo|task|item)\b", normalized):
        title = _cleanup_title(normalized, [r"\b(complete|done|finish|marked|mark|cancel|delete|remove)\b", r"\b(todo|task|item)s?\b", r"\b(to|the|my|a|an)\b"]) 
        if title:
            query = _owner_filter(db.query(TodoItem), TodoItem, user_id, session_id)
            todo = query.filter(TodoItem.title.contains(title)).order_by(TodoItem.created_at.desc()).first()
        else:
            query = _owner_filter(db.query(TodoItem), TodoItem, user_id, session_id)
            todo = query.filter(TodoItem.is_completed == False).order_by(TodoItem.created_at.desc()).first()
        if not todo:
            return {"response": "I couldn't find that todo item to complete."}
        todo.is_completed = True
        db.commit()
        return {"response": f"Marked todo '{todo.title}' as completed."}

    title = _cleanup_title(command, [
        r"\b(add|create|new|todo item|to-do item|task|to-do|todo|remember to|please|set a reminder for)\b",
        r"\b(in \d+\s*(minutes?|hours?)|today at \d{1,2}(?::\d{2})?\s*(am|pm)?|tomorrow at \d{1,2}(?::\d{2})?\s*(am|pm)?|on \d{4}-\d{2}-\d{2}(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(am|pm)?)?|at \d{1,2}(?::\d{2})?\s*(am|pm)?)\b",
    ])
    if not title:
        title = "Todo Item"

    due_at = _parse_datetime(command)
    todo = TodoItem(user_id=user_id, session_id=session_id, title=title, due_at=due_at)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    response = f"Todo item added: '{todo.title}'."
    if due_at:
        response += f" Due {due_at.strftime('%Y-%m-%d %H:%M')}"
    return {"response": response, "todo_id": todo.id}
