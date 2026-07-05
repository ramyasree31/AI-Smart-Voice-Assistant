import requests
import json

BASE = 'http://127.0.0.1:8000'
SID = 'test-session-123'

payload = {
    'title': 'Automated test task',
    'description': 'Created by automated test',
    'date': '2026-07-03',
    'start_time': '10:00',
    'end_time': '11:00',
    'reminder': '15 minutes before',
    'subtasks': 'Step1\nStep2',
    'priority': 'Medium',
    'category': 'Test'
}

print('Posting todo...')
resp = requests.post(f"{BASE}/todos?session_id={SID}", json=payload)
print('POST status', resp.status_code, resp.text)

print('Fetching todos...')
resp2 = requests.get(f"{BASE}/todos?session_id={SID}")
print('GET status', resp2.status_code)
try:
    print(json.dumps(resp2.json(), indent=2))
except Exception as e:
    print('Error parsing JSON:', e)
