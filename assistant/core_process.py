import re
import time
from datetime import datetime
from assistant.ai_service import get_ai_response
from assistant.intent_detector import detect_intent
from assistant.music_manager import MusicManager
from services.weather_service import CityNotFoundError, WeatherServiceError, get_weather, get_weather_by_city

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
GREETING_TOKENS = (
    "hi",
    "hello",
    "hey",
    "hii",
    "heyy",
    "yo",
    "morning",
    "afternoon",
    "evening",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
)
GREETING_PATTERNS = [
    r"^\s*(hi|hello|hey|hii|heyy|yo|greetings|morning|afternoon|evening|good morning|good afternoon|good evening)\s*[*!?.]*\s*$",
    r"^\s*(hi|hello|hey|hii|heyy|yo|greetings|morning|afternoon|evening|good morning|good afternoon|good evening)\b",
]

ACTIVE_TIMEOUT = 20  # seconds

assistant_awake = False
last_active_time = 0


def get_time_based_greeting(now: datetime | None = None) -> str:
    current_time = now or datetime.now()
    hour = current_time.hour
    if hour < 12:
        return "Good Morning"
    if hour < 15:
        return "Good Afternoon"
    return "Good Evening"


def build_greeting_response(now: datetime | None = None) -> str:
    greeting = get_time_based_greeting(now)
    if greeting == "Good Morning":
        return f"{greeting}! How can I help you today?"
    if greeting == "Good Afternoon":
        return f"{greeting}! What can I do for you?"
    return f"{greeting}! How may I assist you?"


def is_greeting_message(text: str | None) -> bool:
    if not text:
        return False
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return False
    return any(
        re.match(pattern, normalized)
        for pattern in GREETING_PATTERNS
    )


def extract_greeting_prefix(text: str | None) -> str | None:
    if not text:
        return None
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return None
    if normalized in GREETING_TOKENS or normalized in {"good morning", "good afternoon", "good evening"}:
        return normalized
    for token in GREETING_TOKENS:
        if normalized.startswith(token):
            return token
    return None


def strip_greeting_prefix(text: str | None) -> str:
    if not text:
        return ""
    greeting_prefix = extract_greeting_prefix(text)
    if not greeting_prefix:
        return text.strip()
    pattern = rf"^(?:{re.escape(greeting_prefix)})\b[\s,!.?;:]*"
    return re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).strip()


def is_listening_acknowledgment(text: str | None) -> bool:
    if not text:
        return True
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return True
    return normalized in {
        "yes",
        "ok",
        "okay",
        "sure",
        "i am listening",
        "i m listening",
        "yes i am listening",
        "yes i m listening",
    }


# -----------------------------
# CORE LOGIC
# -----------------------------
def process_command(command: str, origin: str = None, device_lat: float | None = None, device_lon: float | None = None):
    global conversation

    original_command = command or ""
    command = (original_command or "").strip()
    lower_command = command.lower().strip()

    # -------------------------
    # 1. EXIT COMMAND
    # -------------------------
    if "stop" in lower_command or "exit" in lower_command:
        return {"response": "Goodbye!"}

    # -------------------------
    # 2. WAKE WORD CHECK
    # -------------------------
    is_wake = any(wake in lower_command for wake in WAKE_WORDS)

    # If wake word exists, remove it from command
    if is_wake:
        for wake in WAKE_WORDS:
            command = command.replace(wake, "").strip()

        if command == "" or is_listening_acknowledgment(command):
            return {"response": build_greeting_response()}

    # If no wake word and command is long system voice input, you can optionally ignore:
    # (optional safety)
    if not is_wake and len(command.split()) > 6:
        # treat as normal AI query anyway OR ignore based on your design
        pass

    # -------------------------
    # 3. GREETING HANDLING
    # -------------------------
    if is_greeting_message(command):
        greeting_response = build_greeting_response()
        if not command.strip():
            return {"response": greeting_response}

        cleaned_command = strip_greeting_prefix(command)
        if not cleaned_command:
            return {"response": greeting_response}

        return {"response": f"{greeting_response} " + process_command(cleaned_command, origin, device_lat, device_lon)["response"]}

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
            if device_lat is not None and device_lon is not None:
                weather = get_weather(device_lat, device_lon)
                location_name = weather.get("city") or "your location"
            else:
                weather = get_weather_by_city(city)
                location_name = weather.get("city") or city

            description = weather.get("condition") or weather.get("weather_description") or "unknown"
            temperature = weather.get("temperature")
            feels_like = weather.get("feels_like")
            humidity = weather.get("humidity")

            response_text = (
                f"The weather in {location_name} is {description.lower()}. "
                f"The temperature is {temperature} degrees Celsius, "
                f"feels like {feels_like} degrees, "
                f"and humidity is {humidity} percent."
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