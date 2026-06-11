def detect_intent(command):
    """Detect user intent: greeting, music, news, weather, or info."""
    command = command.lower().strip()
    
    if command in ["hello", "hi", "hey", "wake up"]:
        return "greeting", None
    if "play" in command or "music" in command or "song" in command:
        song = command.replace("play", "").replace("music", "").replace("song", "").strip()
        return "music", song or None
    if "news" in command or "headline" in command:
        return "news", None
    if "weather" in command:
        return "weather", None
    return "info", command
