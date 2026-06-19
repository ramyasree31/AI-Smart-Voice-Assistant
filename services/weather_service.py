import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()

WEATHERAPI_URL = "http://api.weatherapi.com/v1/current.json"
WEATHER_API_KEY_ENV = "WEATHER_API_KEY"


logger = logging.getLogger("services.weather_service")


class WeatherServiceError(Exception):
    """Base error for weather service failures."""


class CityNotFoundError(WeatherServiceError):
    """Raised when the requested location cannot be found."""


def _fetch_weather(query: str) -> dict:
    """Fetch weather using WeatherAPI.
    
    Args:
        query: City name or "lat,lon" for coordinates
    """
    api_key = os.getenv(WEATHER_API_KEY_ENV)
    print("ENV VALUE:", os.getenv(WEATHER_API_KEY_ENV))
    logger.info(f"Preparing WeatherAPI request with query={query}")
    
    if not api_key:
        logger.error(f"Missing WeatherAPI key (env var: {WEATHER_API_KEY_ENV})")
        raise WeatherServiceError(
            f"WeatherAPI key is not set. Please export {WEATHER_API_KEY_ENV}."
        )

    params = {
        "key": api_key,
        "q": query,
        "aqi": "no",
    }

    try:
        response = requests.get(WEATHERAPI_URL, params=params, timeout=10)
        logger.info(f"WeatherAPI request sent, status={response.status_code}")
    except requests.Timeout as exc:
        logger.error("WeatherAPI request timed out", exc_info=exc)
        raise WeatherServiceError("Weather service timed out. Please try again.") from exc
    except requests.RequestException as exc:
        logger.error("WeatherAPI request failed", exc_info=exc)
        raise WeatherServiceError("Unable to reach the weather service. Please check your network.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        logger.error("Failed to decode WeatherAPI response", exc_info=exc)
        raise WeatherServiceError("Invalid response from the weather service.") from exc

    # WeatherAPI returns HTTP 200 with 'error' field for problems
    if response.status_code != 200 or payload.get("error"):
        err = payload.get("error", {})
        message = err.get("message", "Weather service is unavailable.")
        logger.error(f"WeatherAPI error: {message}", extra={"status": response.status_code})
        
        if "No API key" in message or "Invalid API key" in message:
            raise WeatherServiceError(f"Weather service error: {message}")
        if "No matching location found" in message:
            raise CityNotFoundError(f"Location not found: {query}. Please provide a valid city or coordinates.")
        
        raise WeatherServiceError(f"Weather service error: {message}")

    location = payload.get("location", {})
    current = payload.get("current", {})
    
    if not location or not current:
        logger.error("WeatherAPI returned incomplete data")
        raise WeatherServiceError("Weather service returned incomplete data.")

    description = current.get("condition", {}).get("text", "Unknown")
    temperature = current.get("temp_c")
    feels_like = current.get("feelslike_c")
    humidity = current.get("humidity")
    wind_speed = current.get("wind_kph")
    is_day = current.get("is_day", 1) == 1
    
    # Get icon - WeatherAPI provides icon code/URL, use a generic mapping
    condition_code = current.get("condition", {}).get("code", 1000)
    icon = f"{condition_code:02d}d"

    weather_data = {
        "city": location.get("name", "Unknown").title(),
        "temperature": round(temperature) if temperature is not None else None,
        "feels_like": round(feels_like) if feels_like is not None else None,
        "condition": description,
        "humidity": humidity,
        "wind_speed": round(wind_speed) if wind_speed is not None else None,
        "icon": icon,
        "is_day": is_day,
    }
    logger.info("Weather data formatted", extra={"weather_data": weather_data})
    return weather_data


def get_weather(lat: float, lon: float) -> dict:
    """Fetch current weather data for the requested coordinates."""
    if lat is None or lon is None:
        raise WeatherServiceError("Latitude and longitude are required.")
    query = f"{lat},{lon}"
    logger.info(f"get_weather called with coordinates: {query}")
    return _fetch_weather(query)


def get_weather_by_city(city: str) -> dict:
    """Fetch current weather data for a city name."""
    if not city:
        raise WeatherServiceError("City name is required.")
    logger.info(f"get_weather_by_city called with city: {city}")
    return _fetch_weather(city)
