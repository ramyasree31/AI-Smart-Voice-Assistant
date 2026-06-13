from assistant.ai_service import get_ai_response
from assistant.intent_detector import detect_intent

YOUTUBE_EMBED_URL = "https://www.youtube.com/embed/5qap5aO4i9A?autoplay=1"
YOUTUBE_API_KEY="AIzaSyDz7jr7Chu-8LOFKt4erttL1ABgdn9WVLk"
MAX_MESSAGES = 10  # keep last 10 messages only   

conversation = [
    {
        "role": "system",
        "content": "You are a helpful voice assistant."
    }
]
#------------------------------
# CORE LOGIC
# -----------------------------
def process_command(command: str):
    global conversation

    command = command.lower().strip()

    if "stop" in command or "exit" in command:
        return {"response": "Goodbye!"}

    intent, target = detect_intent(command)

    if intent == "music":
        song_text = target or "music"
        response_text = f"Playing {song_text} from YouTube. Enjoy!"

        conversation.append({
            "role": "user",
            "content": command
        })
        conversation.append({
            "role": "assistant",
            "content": response_text
        })

        return {
            "response": response_text,
            "play_music": True,
            "youtube_embed_url": YOUTUBE_EMBED_URL,
            "song": song_text
        }

    conversation.append({
        "role": "user",
        "content": command
    })

    # 🔥 trim memory (IMPORTANT FIX)
    conversation = [conversation[0]] + conversation[-MAX_MESSAGES:]

    ai_response = get_ai_response(conversation)

    if ai_response is None:
        return {
            "response": "The AI backend on localhost:11434 is not available. Start the model server or ask me to play music."
        }

    conversation.append({
        "role": "assistant",
        "content": ai_response
    })

    return {"response": ai_response}