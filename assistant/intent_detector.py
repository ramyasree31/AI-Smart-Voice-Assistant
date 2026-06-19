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
    """Detect user intent: greeting, music, news, weather, or info."""
    command = command.lower().strip()

    if command in ["hello", "hi", "hey", "wake up"]:
        return "greeting", None

    if "news" in command or "headline" in command:
        return "news", None

    # Weather-related intents (including umbrella, rain, outdoor questions)
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
        "outside",
        "raining",
        "storm",
        "wind",
        "umbrella",
        "jacket",
        "go out",
        "outside",
    ]

    if any(keyword in command for keyword in weather_keywords):
        city = _extract_city_from_weather_command(command)
        
        # Detect umbrella-specific queries
        umbrella_keywords = ["umbrella", "need umbrella", "should i", "do i need", "rain coat", "jacket"]
        is_umbrella_query = any(keyword in command for keyword in umbrella_keywords)
        
        return "weather", {"city": city, "is_umbrella_query": is_umbrella_query}

    if any(keyword in command for keyword in ["play", "listen", "song", "music", "pause", "resume", "next", "previous", "skip", "stop", "continue", "back", "add"]):
        if re.search(r"\b(next|skip)\b", command):
            return "music", {"action": "next_track"}
        if re.search(r"\b(previous|back)\b", command):
            return "music", {"action": "previous_track"}
        if re.search(r"\b(pause|stop)\b", command) and not re.search(r"\b(play|listen|next|previous|resume|continue|back)\b", command):
            return "music", {"action": "pause_music"}
        if re.search(r"\b(resume|continue)\b", command):
            return "music", {"action": "resume_music"}
        if re.search(r"\b(add .* to queue|queue .* up|add)\b", command):
            query = _clean_music_query(command)
            return "music", {"action": "add_to_queue", "query": query or None}

        query = _clean_music_query(command)
        return "music", {"action": "play_music", "query": query or None}

    return "info", command
