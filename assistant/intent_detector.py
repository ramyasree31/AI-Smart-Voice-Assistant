import re


def _clean_music_query(command: str) -> str:
    if not command:
        return ""

    query = re.sub(r"\b(from|on)\s+youtube\b", "", command)
    query = re.sub(r"\b(playing|play|listen to|listen|please|song|music|youtube|track|a song|add to queue|add)\b", "", query)
    query = re.sub(r"[^\w\s]", " ", query)
    return " ".join(query.split()).strip()


def _extract_city_from_weather_command(command: str) -> str:
    if not command:
        return None

    patterns = [
        r"weather in ([a-zA-Z\s]+)",
        r"temperature in ([a-zA-Z\s]+)",
        r"forecast for ([a-zA-Z\s]+)",
        r"forecast in ([a-zA-Z\s]+)",
        r"how hot is it in ([a-zA-Z\s]+)",
        r"how cold is it in ([a-zA-Z\s]+)",
        r"how hot is it ([a-zA-Z\s]+)",
        r"how cold is it ([a-zA-Z\s]+)",
        r"in ([a-zA-Z\s]+) weather",
        r"in ([a-zA-Z\s]+) temperature",
        r"([a-zA-Z\s]+) weather",
        r"([a-zA-Z\s]+) temperature",
    ]

    city = None
    for pattern in patterns:
        match = re.search(pattern, command)
        if match:
            city = match.group(1)
            break

    if not city:
        return None

    city = re.sub(r"\b(what's|whats|how|is|the|it|today|current|like|today's|today is|please|in)\b", "", city)
    city = re.sub(r"[^a-zA-Z\s]", "", city)
    city = " ".join(city.split()).strip()
    return city.title() if city else None


def detect_intent(command):
    """Detect user intent: greeting, music, news, weather, task creation, or info."""
    command = command.lower().strip()

    if command in ["hello", "hi", "hey", "wake up"]:
        return "greeting", None

    if "news" in command or "headline" in command:
        return "news", None

    task_create_patterns = [
        r"\badd to do list\b",
        r"\badd todo\b",
        r"\badd todo list\b",r"\badd task\b",
        r"\bcreate task\b",
        r"\bremember to\b",
        r"\bremind me to\b",
        r"\bput .* on my to[- ]?do list\b",
        r"\badd this to my tasks\b",
        r"\badd this to my task(s)?\b",
    ]
    reminder_time_pattern = r"\b(at|by|before|after|on|tomorrow|today|in)\b.*\b(\d{1,2})(?::\d{2})?\s*(am|pm)?\b"

    if any(re.search(pattern, command) for pattern in task_create_patterns):
        if re.search(r"\bremind me to\b", command) and re.search(reminder_time_pattern, command):
            return "reminder", command
        return "task_create", command

    reminder_keywords = [
        "remind me",
        "reminder",
        "alarm",
        "wake me",
        "set alarm",
        "set reminder",
        "remind",
    ]
    if any(keyword in command for keyword in reminder_keywords) and not any(word in command for word in ["music", "play", "song"]):
        return "reminder", command

    weather_keywords = [
        "weather",
        "temperature",
        "forecast",
        "hot",
        "cold",
        "rain",
        "snow",
        "sunny",
        "cloudy",
    ]

    if any(keyword in command for keyword in weather_keywords):
        city = _extract_city_from_weather_command(command)
        return "weather", {"city": city}

    music_keywords = [
        "play",
        "song",
        "music",
        "album",
        "artist",
        "playlist",
        "queue",
        "next track",
        "add this song to queue",
    ]

    if any(keyword in command for keyword in music_keywords):
        if re.search(r"\b(next|skip)\b", command):
            return "music", {"action": "next_track"}
        if re.search(r"\b(previous|back)\b", command):
            return "music", {"action": "previous_track"}
        if re.search(r"\b(pause|stop)\b", command) and not re.search(r"\b(play|listen|next|previous|resume|continue|back)\b", command):
            return "music", {"action": "pause_music"}
        if re.search(r"\b(resume|continue)\b", command):
            return "music", {"action": "resume_music"}
        if re.search(r"\b(add .* to queue|queue .* up|add this song to queue)\b", command):
            query = _clean_music_query(command)
            return "music", {"action": "add_to_queue", "query": query or None}

        query = _clean_music_query(command)
        return "music", {"action": "play_music", "query": query or None}

    return "info", command
