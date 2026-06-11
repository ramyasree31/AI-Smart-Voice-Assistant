from assistant.speech_to_text import listen
from assistant.text_to_speech import speak
from services.ai_service import get_ai_response

speak("Smart Voice Assistant is now active")

# -----------------------------
# MEMORY STORE (conversation)
# -----------------------------
conversation = [
    {
        "role": "system",
        "content": "You are a helpful voice assistant."
    }
]

while True:

    command = listen()

    if not command:
        continue

    command = command.lower().strip()
    print("You said:", command)

    # Stop condition
    if "stop" in command or "exit" in command:
        speak("Goodbye!")
        break

    try:
        # -----------------------------
        # ADD USER MESSAGE TO MEMORY
        # -----------------------------
        conversation.append({
            "role": "user",
            "content": command
        })

        # -----------------------------
        # GET AI RESPONSE (with memory)
        # -----------------------------
        ai_response = get_ai_response(conversation)

        print("Assistant:", ai_response)

        # -----------------------------
        # ADD ASSISTANT RESPONSE TO MEMORY
        # -----------------------------
        conversation.append({
            "role": "assistant",
            "content": ai_response
        })
        
        speak(ai_response)

    except Exception as e:
        print("Error:", e)
        speak("Sorry, I am unable to connect to the AI model.")