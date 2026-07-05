from assistant import core_process


def test_process_command_uses_city_lookup_for_weather(monkeypatch):
    def fake_get_weather_by_city(city):
        assert city == "Tirupati"
        return {
            "city": "Tirupati",
            "condition": "Sunny",
            "temperature": 30,
            "feels_like": 32,
            "humidity": 50,
        }

    monkeypatch.setattr(core_process, "get_weather_by_city", fake_get_weather_by_city)
    monkeypatch.setattr(
        core_process,
        "get_weather",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("city weather should use get_weather_by_city")),
    )

    result = core_process.process_command("what is the weather in Tirupati")

    assert "Tirupati" in result["response"]
    assert "sunny" in result["response"]


def test_process_command_uses_device_coordinates_for_weather(monkeypatch):
    def fake_get_weather(lat, lon):
        assert lat == 16.9279
        assert lon == 81.7934
        return {
            "city": "Dowlaishwaram",
            "condition": "Cloudy",
            "temperature": 28,
            "feels_like": 30,
            "humidity": 62,
        }

    monkeypatch.setattr(core_process, "get_weather", fake_get_weather)
    monkeypatch.setattr(core_process, "get_weather_by_city", lambda city: (_ for _ in ()).throw(AssertionError("coordinates should bypass city lookup")))

    result = core_process.process_command("what is the weather like", device_lat=16.9279, device_lon=81.7934)

    assert "Dowlaishwaram" in result["response"]
    assert "cloudy" in result["response"]
