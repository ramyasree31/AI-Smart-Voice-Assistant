import os
import json
import sys
from assistant.weather_service import get_weather

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/weather_test.py CITY')
        sys.exit(2)
    city = sys.argv[1]
    try:
        print(json.dumps(get_weather(city), indent=2))
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)
