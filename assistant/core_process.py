import logging
import time
from assistant.ai_service import get_ai_response
from assistant.intent_detector import detect_intent
from assistant.music_manager import MusicManager
from services.weather_service import CityNotFoundError, WeatherServiceError, get_weather_by_city, get_weather

logger = logging.getLogger("assistant.core_process")

MAX_MESSAGES = 10
DEFAULT_CITY = "Tirupati"

music_manager = MusicManager()

conversation = [
    {
        "role": "system",
        "content": "You are a helpful voice assistant."
    }
]


# -------------------------
# WEATHER DECISION LOGIC
# -------------------------
def _should_carry_umbrella(weather: dict) -> tuple[bool, str]:
    """
    Determine if umbrella is needed based on weather data.
    
    Returns:
        tuple: (should_carry: bool, reason: str)
    """
    if not weather:
        return False, ""
    
    condition = weather.get("condition", "").lower()
    humidity = weather.get("humidity", 0)
    
    # Precipitation-related conditions
    precipitation_keywords = ["rain", "drizzle", "thunderstorm", "shower", "hail", "sleet"]
    has_precipitation = any(keyword in condition for keyword in precipitation_keywords)
    
    if has_precipitation:
        return True, f"There's {condition} and you should carry an umbrella."
    
    # High humidity + cloudy/mist → possible rain risk
    cloudy_keywords = ["cloudy", "overcast", "mist", "fog"]
    is_cloudy = any(keyword in condition for keyword in cloudy_keywords)
    
    if is_cloudy and humidity and humidity > 75:
        return True, f"It's {condition} with high humidity ({humidity}%), so there's a chance of drizzle. Better carry an umbrella."
    
    # Clear weather → no umbrella needed
    clear_keywords = ["clear", "sunny", "bright"]
    is_clear = any(keyword in condition for keyword in clear_keywords)
    
    if is_clear:
        return False, f"No umbrella needed. It's {condition} and dry."
    
    # Default: safe weather
    return False, f"No umbrella needed right now. It's {condition}."

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
def process_command(command: str, origin: str = None, device_lat: float = None, device_lon: float = None):
    global conversation

    command = command.lower().strip()
    logger.info(f"Processing command: {command}, device_location: lat={device_lat}, lon={device_lon}")

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
        is_umbrella_query = False
        
        if isinstance(target, dict):
            city = target.get("city")
            is_umbrella_query = target.get("is_umbrella_query", False)
        
        logger.info(f"Weather intent detected, city={city}, is_umbrella_query={is_umbrella_query}, has_device_location={device_lat is not None and device_lon is not None}")

        # Try to get weather - MANDATORY fetch before answering
        weather = None
        location_used = None
        
        try:
            # Priority 1: If city is specified, use it
            if city:
                weather = get_weather_by_city(city)
                location_used = city
                logger.info(f"Weather fetched for city: {city}")
            # Priority 2: If device location available, use coordinates
            elif device_lat is not None and device_lon is not None:
                weather = get_weather(device_lat, device_lon)
                location_used = "device_location"
                logger.info(f"Weather fetched for device location: {device_lat}, {device_lon}")
            # Priority 3: No city and no device location
            else:
                response_text = "I couldn't access your location. Please tell me your city or allow location access."
                logger.info("Weather intent: no city and no device location")
                return {"response": response_text}
        
        except CityNotFoundError as exc:
            logger.warning(f"City not found: {exc}")
            response_text = f"I couldn't find weather information for {city}. Please try another city name."
            return {"response": response_text}
        except WeatherServiceError as exc:
            logger.error(f"Weather service error: {exc}")
            response_text = "I'm unable to fetch live weather right now. Please try again later."
            return {"response": response_text}
        
        # Format voice-friendly response
        if weather:
            condition = weather.get("condition", "Unknown").lower()
            temp = weather.get("temperature", "--")
            feels_like = weather.get("feels_like", "--")
            humidity = weather.get("humidity", "--")
            wind_speed = weather.get("wind_speed", "--")
            city_name = weather.get("city", "your location")
            is_day = weather.get("is_day", True)
            
            # Handle umbrella-specific queries
            if is_umbrella_query:
                should_carry, umbrella_reason = _should_carry_umbrella(weather)
                response_text = umbrella_reason
                logger.info(f"Umbrella query result: should_carry={should_carry}, reason={umbrella_reason}")
            else:
                # Standard weather report
                response_text = (
                    f"Right now it's {temp}°C and {condition} in {city_name}. "
                    f"It feels like {feels_like}°C with {wind_speed} km/h wind. "
                    f"Humidity is {humidity}%."
                )
                logger.info(f"Weather response: {response_text}")
            
            return {
                "intent": "weather",
                "location_used": location_used,
                "temperature": temp,
                "condition": condition,
                "feels_like": feels_like,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "is_day": is_day,
                "is_umbrella_query": is_umbrella_query,
                "response": response_text,
            }

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