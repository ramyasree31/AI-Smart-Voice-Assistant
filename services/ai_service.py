import requests


def get_ai_response(messages):
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "qwen2.5:3b",
                "messages": messages,
                "stream": False
            }
        )

        data = response.json()

        return data["message"]["content"]

    except Exception as e:
        #print("AI Service Error:", e)
        print("Error:", e)
        #return "Sorry, I am having trouble connecting to the AI model."