from fastapi import (
    FastAPI, Request, WebSocket, WebSocketDisconnect,
    Form, Body
)
from fastapi.responses import (
    HTMLResponse, RedirectResponse
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os
from collections import defaultdict
from services.ai_service import get_ai_response

app = FastAPI()

templates = Jinja2Templates(directory="frontend")

# -----------------------------
# CORS (for frontend)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# MEMORY STORE
# -----------------------------
conversation = [
    {
        "role": "system",
        "content": "You are a helpful voice assistant."
    }
]


#sessions = defaultdict(list)
#sessions[session_id].append(...)

# -----------------------------
# REQUEST MODEL
# -----------------------------
class VoiceRequest(BaseModel):
    command: str


# -----------------------------
# HOME ROUTE → SERVE INDEX.HTML
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    file_path = os.path.join("frontend", "index.html")

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()




@app.get("/home", response_class=HTMLResponse)
def home(request:Request):

    return templates.TemplateResponse(
    request=request,
    name="home.html",
    context={
        "title": "Home"
    }
)
    
    
    
#------------------------------
# CORE LOGIC
# -----------------------------
def process_command(command: str):
    global conversation

    command = command.lower().strip()

    if "stop" in command or "exit" in command:
        return {"response": "Goodbye!"}

    conversation.append({
        "role": "user",
        "content": command
    })

    ai_response = get_ai_response(conversation)

    conversation.append({
        "role": "assistant",
        "content": ai_response
    })

    return {"response": ai_response}


# -----------------------------
# API ENDPOINT
# -----------------------------
@app.post("/voice")
def voice_endpoint(request: VoiceRequest):
    return process_command(request.command)