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
from assistant.ai_service import get_ai_response
from assistant.speech_to_text import listen
from assistant.core_process import process_command




app = FastAPI()

templates = Jinja2Templates(directory="templates")

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
    file_path = os.path.join("templates", "index.html")

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()



@app.get("/listen")
def listen_endpoint():
    text = listen()
    return {"command": text}


@app.get("/home", response_class=HTMLResponse)
def home(request:Request):

    return templates.TemplateResponse(
    request=request,
    name="home.html",
    context={
        "title": "Home"
    }
)



# -----------------------------
# API ENDPOINT
# -----------------------------
@app.post("/voice")
def voice_endpoint(request: VoiceRequest):
    return process_command(request.command)