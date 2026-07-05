import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import Reminder, TodoItem


def _parse_datetime(command: str) -> datetime | None:
    now = datetime.now()
    command = command.lower()
    command = re.sub(r"\b([ap])\s*\.?\s*m\.?\b", lambda m: f"{m.group(1)}m", command)
    command = re.sub(r"\bo['’]?clock\b", "oclock", command)
    match = re.search(r"\b(today|tomorrow)\b", command)
    if match:
        day_name = match.group(1)
        delta = 0 if day_name == "today" else 1
        return datetime(year=now.year, month=now.month, day=now.day, hour=0, minute=0) + timedelta(days=delta)
    match = re.search(r"before\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:oclock)?", command)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = (match.group(3) or "").lower()
        if period == "pm" and hour < 12:
            hour += 12
        if period == "am" and hour == 12:
            hour = 0
        result = datetime(year=now.year, month=now.month, day=now.day, hour=hour, minute=minute)
        if result <= now:
            result = result + timedelta(days=1)
        return result

    match = re.search(r"by\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:oclock)?", command)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = (match.group(3) or "").lower()
        if period == "pm" and hour < 12:
            hour += 12
        if period == "am" and hour == 12:
            hour = 0
        result = datetime(year=now.year, month=now.month, day=now.day, hour=hour, minute=minute)
        if result <= now:
            result = result + timedelta(days=1)
        return result

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

    month_names = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    month_patterns = [
        r"(?:on|for|by|due|date)\s+(\d{1,2})\s*(?:st|nd|rd|th)?\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)",
        r"(?:on|for|by|due|date)\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})\s*(?:st|nd|rd|th)?",
        r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})\s*(?:st|nd|rd|th)?\b",
        r"\b(\d{1,2})\s*(?:st|nd|rd|th)\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    ]
    for pattern in month_patterns:
        match = re.search(pattern, command)
        if match:
            if pattern.startswith(r"(?:on|for|by|due|date)\s+(\d{1,2})"):
                day = int(match.group(1))
                month_name = match.group(2)
            elif pattern.startswith(r"\b(\d{1,2})"):
                day = int(match.group(1))
                month_name = match.group(2)
            else:
                day = int(match.group(2))
                month_name = match.group(1)
            month_name = month_name.lower()
            month = month_names.get(month_name[:3] if month_name[:3] in month_names else month_name)
            if month:
                parsed_date = datetime(year=now.year, month=month, day=day, hour=0, minute=0)
                if parsed_date.date() < now.date():
                    parsed_date = parsed_date.replace(year=now.year + 1)
                return parsed_date

    return None


def _strip_wake_words(command: str) -> str:
    command = re.sub(r"\b(hey|ok|okay|hello|hi)\s+assistant\b", "", command, flags=re.IGNORECASE)
    return re.sub(r"\b(assistant)\b", "", command, flags=re.IGNORECASE).strip()


def _cleanup_title(command: str, remove_patterns: list[str]) -> str:
    title = _strip_wake_words(command.lower())
    for pattern in remove_patterns:
        title = re.sub(pattern, "", title)
    title = re.sub(r"\b([ap])\s*\.?\s*m\.?\b", " ", title)
    title = re.sub(r"\b(before|by|at|for|to|do|on|and|a|an|the|my|your|stop|ad)\b", " ", title)
    title = re.sub(r"\b(o'|o|’)clock\b", " ", title)
    title = re.sub(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", " ", title)
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\b(task|todo|to do|to-do|item|items)\b", " ", title)
    title = " ".join(title.split()).strip()
    return title or "Todo Item"


def _owner_filter(query, model, user_id, session_id):
    if user_id:
        return query.filter(model.user_id == user_id)
    return query.filter(model.session_id == session_id)


def _parse_reminder_time(command: str) -> str | None:
    normalized = command.lower()
    normalized = re.sub(r"\b([ap])\s*\.??\s*m\.??\b", lambda m: f"{m.group(1)}m", normalized)
    match = re.search(r"\b(?:reminder|remind)(?:\s+me)?(?:\s+time)?\s*(?:at|for)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", normalized, re.IGNORECASE)
    if not match:
        match = re.search(r"\b(?:at|by|before|for)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", normalized, re.IGNORECASE)
    if not match:
        match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", normalized, re.IGNORECASE)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    period = (match.group(3) or "").lower()
    if period == "pm" and hour < 12:
        hour += 12
    if period == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _infer_category(command: str) -> str | None:
    lowered = command.lower()
    if re.search(r"\bwork\b", lowered):
        return "Work"
    if re.search(r"\btest\b", lowered):
        return "Test"
    if re.search(r"\bpersonal\b", lowered):
        return "Personal"
    return None


def _merge_repeat_days(existing_days: str | None, new_days: str | None) -> str | None:
    combined = []
    seen = set()
    for day_value in [value for value in (existing_days or "").split(",") if value] + [value for value in (new_days or "").split(",") if value]:
        if day_value not in seen:
            seen.add(day_value)
            combined.append(day_value)
    return ",".join(combined) or None


def _parse_recurrence(command: str) -> tuple[str, str | None]:
    lowered = command.lower()
    if "one-time" in lowered or "one time" in lowered or lowered in {"none", "no repeat", "no recurrence"}:
        return "one_time", None
    if "every day" in lowered or "daily" in lowered:
        return "daily", None
    if "every weekday" in lowered or "weekdays" in lowered or "mon-fri" in lowered or "mon fri" in lowered:
        return "weekdays", "Mon,Tue,Wed,Thu,Fri"
    if "one day" in lowered and "friday" in lowered:
        return "weekdays", "Mon,Tue,Wed,Thu,Fri"
    if "custom" in lowered:
        return "custom", None

    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    short_day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    weekday_map = {
        "monday": "Mon",
        "tuesday": "Tue",
        "wednesday": "Wed",
        "thursday": "Thu",
        "friday": "Fri",
        "saturday": "Sat",
        "sunday": "Sun",
        "mon": "Mon",
        "tue": "Tue",
        "wed": "Wed",
        "thu": "Thu",
        "fri": "Fri",
        "sat": "Sat",
        "sun": "Sun",
    }
    matches = re.findall(r"\b(" + "|".join(day_names + short_day_names) + r")\b", lowered)
    if matches:
        repeat_days = ",".join(weekday_map[m] for m in matches)
        return "custom", repeat_days

    return "one_time", None


def _parse_subtasks(command: str) -> str | None:
    match = re.search(r"\bsubtasks?\b(.*)", command, re.IGNORECASE)
    if not match:
        return None

    raw = match.group(1)
    segments = re.split(r",|;|\band\b", raw, flags=re.IGNORECASE)
    items = []
    for segment in segments:
        cleaned = re.sub(r"^(?:with|for|and|add|new)\s*", "", segment, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\b(?:subtasks?|task|todo|item|items)\b", "", cleaned, flags=re.IGNORECASE).strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return "\n".join(items) if items else None


PENDING_TODO_CONTEXTS: dict[str, dict] = {}
TODO_FIELD_ORDER = ["reminder", "category", "repeat", "due_date", "subtasks"]


def _pending_context_key(user_id: int | None, session_id: str | None) -> str:
    return f"{user_id or 'anon'}:{session_id or 'anon'}"


def _get_pending_todo_context(user_id: int | None, session_id: str | None, db: Session) -> tuple[str | None, dict | None]:
    primary_key = _pending_context_key(user_id, session_id)
    pending_context = PENDING_TODO_CONTEXTS.get(primary_key)
    if pending_context:
        return primary_key, pending_context

    if session_id:
        fallback_key = _pending_context_key(user_id, None)
        pending_context = PENDING_TODO_CONTEXTS.get(fallback_key)
        if pending_context:
            return fallback_key, pending_context

    latest_todo = (
        db.query(TodoItem)
        .filter(TodoItem.user_id == user_id if user_id is not None else True)
        .order_by(TodoItem.created_at.desc())
        .first()
    )
    if latest_todo:
        for key, context in PENDING_TODO_CONTEXTS.items():
            if context.get("todo_id") == latest_todo.id:
                return key, context
    return None, None


def _get_next_missing_todo_field(todo: TodoItem, skip_repeat_days: bool = False) -> tuple[str | None, str | None, list[str] | None]:
    if not todo.reminder:
        return "reminder", "What reminder time would you like for this task?", None
    if not todo.category:
        return "category", "What category should this task be in?", ["Personal", "Work", "Test"]
    if not todo.recurrence or todo.recurrence == "one_time":
        return "repeat", "How should this task repeat?", ["One-time", "Daily", "Mon-Fri", "Custom"]
    if todo.recurrence == "custom":
        if not todo.repeat_days:
            return "repeat_days", "Which days should this task repeat on?", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if not todo.date and not todo.due_at:
            if skip_repeat_days:
                return "due_date", "What due date should I set for this task?", None
            if "," in todo.repeat_days:
                return "due_date", "What due date should I set for this task?", None
            return "repeat_days", "Which other days should this task repeat on? Say done when you're finished.", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if not todo.subtasks:
            return "subtasks", "Would you like to add any subtasks to this task?", None
        return None, None, None
    if not todo.date and not todo.due_at:
        return "due_date", "What due date should I set for this task?", None
    if not todo.subtasks:
        return "subtasks", "Would you like to add any subtasks to this task?", None
    return None, None, None


def _apply_follow_up_to_todo(todo: TodoItem, command: str) -> bool:
    updated = False
    reminder_time = _parse_reminder_time(command)
    if reminder_time:
        todo.reminder = reminder_time
        updated = True

    category = _infer_category(command)
    if category:
        todo.category = category
        updated = True

    recurrence, repeat_days = _parse_recurrence(command)
    if recurrence == "custom":
        todo.recurrence = "custom"
        todo.repeat_days = _merge_repeat_days(todo.repeat_days, repeat_days)
        updated = True
    elif recurrence and recurrence != "one_time":
        todo.recurrence = recurrence
        todo.repeat_days = repeat_days
        updated = True
    elif "specific days" in command.lower() or "specific day" in command.lower():
        todo.recurrence = "custom"
        todo.repeat_days = None
        updated = True
    elif "repeat" in command.lower() or "daily" in command.lower() or "weekday" in command.lower() or "weekly" in command.lower():
        todo.recurrence = recurrence or "one_time"
        todo.repeat_days = repeat_days
        updated = True

    due_at = _parse_datetime(command)
    if due_at:
        todo.due_at = due_at
        todo.date = due_at.date().strftime('%Y-%m-%d')
        updated = True

    subtasks = _parse_subtasks(command)
    if subtasks:
        todo.subtasks = subtasks
        updated = True

    return updated


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

    creation_command = re.search(r"\b(add|create|new|remember to|put .* on my to[- ]?do list|add this to my tasks?)\b", normalized)
    if not creation_command and re.search(r"\b(complete|done|finish|mark .* done|cancel|delete|remove)\b", normalized) and re.search(r"\b(todo|task|item)\b", normalized):
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

    context_key, pending_context = _get_pending_todo_context(user_id, session_id, db)
    if pending_context:
        todo = db.query(TodoItem).filter(TodoItem.id == pending_context["todo_id"]).first()
        if todo is None:
            PENDING_TODO_CONTEXTS.pop(context_key, None)
        else:
            if re.search(r"\b(done|finish|save|skip|next|no thanks|cancel)\b", normalized):
                field_name, prompt, choices = _get_next_missing_todo_field(todo, skip_repeat_days=True)
                if field_name is None:
                    PENDING_TODO_CONTEXTS.pop(context_key, None)
                    return {"response": f"I've finished setting up '{todo.title}'.", "todo_id": todo.id}
                PENDING_TODO_CONTEXTS[context_key] = {"todo_id": todo.id}
                payload = {"response": prompt, "todo_id": todo.id, "field": field_name}
                if choices:
                    payload["choices"] = choices
                return payload

            updated = _apply_follow_up_to_todo(todo, command)
            db.commit()
            db.refresh(todo)
            field_name, prompt, choices = _get_next_missing_todo_field(todo)
            if field_name is None:
                PENDING_TODO_CONTEXTS.pop(context_key, None)
                return {"response": f"I've finished setting up '{todo.title}'.", "todo_id": todo.id}
            if not updated:
                payload = {"response": f"I didn't catch that. {prompt}", "todo_id": todo.id, "field": field_name}
                if choices:
                    payload["choices"] = choices
                return payload
            payload = {"response": prompt, "todo_id": todo.id, "field": field_name}
            if choices:
                payload["choices"] = choices
            return payload

    title = _cleanup_title(command, [
        r"\b(add|create|new|todo item|to-do item|task|to-do|todo|remember to|please|set a reminder for|stop ad)\b",
        r"\b(in \d+\s*(minutes?|hours?)|today at \d{1,2}(?::\d{2})?\s*(am|pm)?|tomorrow at \d{1,2}(?::\d{2})?\s*(am|pm)?|on \d{4}-\d{2}-\d{2}(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(am|pm)?)?|at \d{1,2}(?::\d{2})?\s*(am|pm)?|before \d{1,2}(?::\d{2})?\s*(am|pm)?\s*(o'|o|’)clock|by \d{1,2}(?::\d{2})?\s*(am|pm)?\s*(o'|o|’)clock)\b",
    ])
    if not title:
        title = "Todo Item"

    due_at = _parse_datetime(command)
    reminder_time = _parse_reminder_time(command)
    recurrence, repeat_days = _parse_recurrence(command)
    subtasks = _parse_subtasks(command)
    category = _infer_category(command)

    todo = TodoItem(
        user_id=user_id,
        session_id=session_id,
        title=title,
        due_at=due_at,
        date=due_at.date().strftime('%Y-%m-%d') if due_at else None,
        reminder=reminder_time,
        recurrence=recurrence if recurrence != 'one_time' else None,
        repeat_days=repeat_days if recurrence not in (None, 'one_time') else None,
        subtasks=subtasks,
        category=category,
    )
    if not category:
        todo.category = None
    db.add(todo)
    db.commit()
    db.refresh(todo)

    PENDING_TODO_CONTEXTS[context_key] = {"todo_id": todo.id}
    field_name, prompt, choices = _get_next_missing_todo_field(todo)
    if field_name is None:
        PENDING_TODO_CONTEXTS.pop(context_key, None)
        return {"response": f"{todo.title} added to your todo list.", "todo_id": todo.id}

    if due_at:
        response = (
            f"{todo.title} added to your todo list. "
            f"Task end: {due_at.strftime('%Y-%m-%d %I:%M %p')}. {prompt}"
        )
    else:
        response = (
            f"{todo.title} added to your todo list. {prompt}"
        )
    payload = {"response": response, "todo_id": todo.id, "field": field_name}
    if choices:
        payload["choices"] = choices
    return payload
