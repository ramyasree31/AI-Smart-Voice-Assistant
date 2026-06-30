import time
from assistant.ai_service import get_ai_response
from assistant.intent_detector import detect_intent
from assistant.music_manager import MusicManager
from services.weather_service import CityNotFoundError, WeatherServiceError, get_weather

MAX_MESSAGES = 10
DEFAULT_CITY = "Tirupati"

music_manager = MusicManager()

conversation = [
    {
        "role": "system",
        "content": "You are a helpful voice assistant."
    }
]

# -----------------------------
# WAKE WORDS & GREETINGS
# -----------------------------
WAKE_WORDS = ["hey assistant", "ok assistant", "hello assistant", "hi assistant"]
GREETINGS = ["hi", "hello", "hey"]



ACTIVE_TIMEOUT = 20  # seconds

assistant_awake = False
last_active_time = 0
# -----------------------------
# CORE LOGIC
# -----------------------------
def process_command(command: str, origin: str = None, device_lat: float | None = None, device_lon: float | None = None):
    global conversation

    command = command.lower().strip()

    # -------------------------
    # 1. EXIT COMMAND
    # -------------------------
    if "stop" in command or "exit" in command:
        return {"response": "Goodbye!"}

    # -------------------------
    # 2. WAKE WORD CHECK
    # -------------------------
    is_wake = any(wake in command for wake in WAKE_WORDS)

    # If wake word exists, remove it from command
    if is_wake:
        for wake in WAKE_WORDS:
            command = command.replace(wake, "").strip()

        if command == "":
            return {"response": "Yes, I'm listening."}

    # If no wake word and command is long system voice input, you can optionally ignore:
    # (optional safety)
    if not is_wake and len(command.split()) > 6:
        # treat as normal AI query anyway OR ignore based on your design
        pass

    # -------------------------
    # 3. GREETING HANDLING
    # -------------------------
    if command in GREETINGS:
        return {"response": "Hello! How can I help you?"}

    # -------------------------
    # 4. INTENT DETECTION
    # -------------------------
    intent, target = detect_intent(command)

    # -------------------------
    # 5. WEATHER INTENT
    # -------------------------
    if intent == "weather":
        city = None
        if isinstance(target, dict):
            city = target.get("city")
        if not city:
            city = DEFAULT_CITY

        try:
            weather = get_weather(city)
            response_text = (
                f"The weather in {weather['city']} is {weather['weather_description'].lower()}. "
                f"The temperature is {weather['temperature']} degrees Celsius, "
                f"feels like {weather['feels_like']} degrees, "
                f"and humidity is {weather['humidity']} percent."
            )
        except CityNotFoundError:
            response_text = (
                f"I couldn't find weather information for {city}. "
                "Please try another city name."
            )
        except WeatherServiceError as exc:
            response_text = str(exc)

        return {"response": response_text}

    # -------------------------
    # 6. MUSIC INTENT
    # -------------------------
    if intent == "music":
        action = None
        query = None
        if isinstance(target, dict):
            action = target.get("action")
            query = target.get("query")
        else:
            action = "play_music"
            query = target

        response = music_manager.handle_command(action, query)
        return response

    # -------------------------
    # 7. NORMAL AI CHAT
    # -------------------------
    conversation.append({"role": "user", "content": command})

    # trim memory
    conversation = [conversation[0]] + conversation[-MAX_MESSAGES:]

    ai_response = get_ai_response(conversation)

    if ai_response is None:
        return {
            "response": "AI backend is not available. Please start the model server."
        }

    conversation.append({"role": "assistant", "content": ai_response})

    return {"response": ai_response}