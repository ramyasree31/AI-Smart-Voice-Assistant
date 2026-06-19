import requests

def get_ai_response(messages):
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "qwen2.5:3b",
                "messages": messages[-10:],  # extra safety
                "stream": False
            },
            timeout=60
        )

        print(f"Sending {len(messages)} messages to Ollama")
        data = response.json()
        return data["message"]["content"]

    except Exception as e:
        print("Error:", e)
        return None