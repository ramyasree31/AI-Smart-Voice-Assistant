import os

import services.weather_service as weather_service


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_weather_service_uses_weatherapi_icon_url(monkeypatch):
    payload = {
        "location": {"name": "Tirupati"},
        "current": {
            "temp_c": 30,
            "feelslike_c": 31,
            "humidity": 45,
            "wind_kph": 12,
            "is_day": 1,
            "condition": {
                "text": "Sunny",
                "code": 1000,
                "icon": "//cdn.weatherapi.com/weather/64x64/day/113.png",
            },
        },
    }

    monkeypatch.setenv(weather_service.WEATHER_API_KEY_ENV, "fake-key")
    monkeypatch.setattr(weather_service.requests, "get", lambda *args, **kwargs: DummyResponse(payload))

    data = weather_service.get_weather_by_city("Tirupati")

    assert data["icon"] == "https://cdn.weatherapi.com/weather/64x64/day/113.png"
