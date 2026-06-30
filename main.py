import logging
import os
import requests
import yt_dlp
from fastapi import (
    FastAPI, Request, WebSocket, WebSocketDisconnect,
    Form, Body, HTTPException, Depends
)
from fastapi.responses import (
    HTMLResponse, RedirectResponse, StreamingResponse, Response, JSONResponse
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from collections import defaultdict
from assistant.ai_service import get_ai_response
from assistant.speech_to_text import listen
from assistant.core_process import process_command
from assistant.intent_detector import detect_intent
from assistant.task_manager import handle_reminder_command, handle_todo_command
from services.weather_service import get_weather, CityNotFoundError, WeatherServiceError

# DB + Auth
from db import engine, Base, get_db, SessionLocal
from models import User, Conversation, Message, TodoItem, Reminder
from datetime import datetime
from sqlalchemy.orm import Session
from auth import hash_password, verify_password, create_access_token, get_current_user, get_optional_current_user



logger = logging.getLogger("smart_voice_assistant")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    device_lat: float | None = None
    device_lon: float | None = None
    conversation_id: int | None = None
    session_id: str | None = None



# -----------------------------
# HOME ROUTE → SERVE INDEX.HTML
# -----------------------------
@app.get("/", response_class=HTMLResponse)
@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.get("/listen")
def listen_endpoint():
    text = listen()
    return {"command": text}


# Create DB tables
Base.metadata.create_all(bind=engine)


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


@app.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter((User.email == payload.email) | (User.username == payload.username)).first():
        raise HTTPException(status_code=400, detail="User with that email or username already exists")
    pwd_hash = hash_password(payload.password)
    user = User(username=payload.username, email=payload.email, password_hash=pwd_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"user_id": user.id})
    return {"access_token": token, "user": {"id": user.id, "username": user.username, "email": user.email}}


@app.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.email == payload.identifier) | (User.username == payload.identifier)
    ).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"user_id": user.id})
    return {"access_token": token, "user": {"id": user.id, "username": user.username, "email": user.email}}


@app.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    # Stateless JWT: client should remove token. Endpoint returns success for convenience.
    return {"ok": True}


@app.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "email": current_user.email}


@app.post("/conversations")
def create_conversation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = Conversation(user_id=current_user.id, title=None)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at.isoformat()}


@app.get("/conversations")
def list_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    convs = db.query(Conversation).filter(Conversation.user_id == current_user.id).order_by(Conversation.updated_at.desc()).all()
    results = []
    for c in convs:
        last = None
        if c.messages:
            m = sorted(c.messages, key=lambda x: x.timestamp)[-1]
            last = {"sender": m.sender, "message": m.message, "timestamp": m.timestamp.isoformat()}
        updated = c.updated_at or c.created_at
        results.append({"id": c.id, "title": c.title or "Untitled", "last_message": last, "updated_at": updated.isoformat() if updated else None})
    return results


@app.get("/conversation/{conv_id}")
def get_conversation(conv_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = [
        {"id": m.id, "sender": m.sender, "message": m.message, "timestamp": m.timestamp.isoformat()}
        for m in sorted(conv.messages, key=lambda x: x.timestamp)
    ]
    return {"id": conv.id, "title": conv.title, "messages": msgs}


@app.post("/conversation/{conv_id}/messages")
def post_message(conv_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    sender = payload.get("sender")
    message = payload.get("message")
    if not sender or not message:
        raise HTTPException(status_code=400, detail="sender and message required")
    m = Message(conversation_id=conv.id, sender=sender, message=message)
    db.add(m)
    conv.updated_at = m.timestamp
    db.commit()
    db.refresh(m)
    return {"id": m.id, "sender": m.sender, "message": m.message, "timestamp": m.timestamp.isoformat()}


@app.post("/chat")
def chat(payload: VoiceRequest, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    conv = None
    
    # Only save to DB if user is authenticated
    if current_user:
        if payload.conversation_id:
            conv = db.query(Conversation).filter(Conversation.id == payload.conversation_id, Conversation.user_id == current_user.id).first()
        if not conv:
            conv = Conversation(user_id=current_user.id, title=None)
            db.add(conv)
            db.commit()
            db.refresh(conv)

        # Save user message
        user_msg = Message(conversation_id=conv.id, sender="user", message=payload.command)
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # Retrieve last messages for context (last 10)
        last_msgs = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.timestamp.desc()).limit(10).all()
        history = []
        for m in reversed(last_msgs):
            role = "assistant" if m.sender == "assistant" else "user"
            history.append({"role": role, "content": m.message})

    # Check intents for reminders/todos and handle them directly
    intent, target = detect_intent(payload.command)
    if intent == 'reminder':
        response = handle_reminder_command(payload.command, db, current_user.id if current_user else None, payload.session_id)
    elif intent == 'todo':
        response = handle_todo_command(payload.command, db, current_user.id if current_user else None, payload.session_id)
    else:
        # Call existing process_command with device coords
        response = process_command(payload.command, None, payload.device_lat, payload.device_lon)
    
    # Ensure response is a dict
    if isinstance(response, dict):
        assistant_response = response
    else:
        assistant_response = {"response": str(response)}

    # Only save assistant message if user is authenticated
    if current_user and conv:
        assistant_text = assistant_response.get("response", str(response))
        assistant_msg = Message(conversation_id=conv.id, sender="assistant", message=assistant_text)
        db.add(assistant_msg)
        conv.updated_at = assistant_msg.timestamp
        # generate title from first user message if empty
        if not conv.title:
            conv.title = (payload.command[:64]) if payload.command else "Conversation"
        db.commit()
        assistant_response["conversation_id"] = conv.id

    return assistant_response


# -----------------------------
# Todo endpoints
# -----------------------------
@app.get("/todos")
def list_todos(session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    query = db.query(TodoItem)
    if current_user:
        query = query.filter(TodoItem.user_id == current_user.id)
    elif session_id:
        query = query.filter(TodoItem.session_id == session_id)
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")
    items = query.order_by(TodoItem.created_at.desc()).all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "is_completed": bool(t.is_completed),
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in items
    ]


@app.post("/todos")
def create_todo(payload: dict, session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    title = payload.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    description = payload.get("description")
    due_at = None
    if payload.get("due_at"):
        try:
            due_at = datetime.fromisoformat(payload.get("due_at"))
        except Exception:
            raise HTTPException(status_code=400, detail="due_at must be ISO datetime")
    if current_user:
        todo = TodoItem(user_id=current_user.id, title=title, description=description, due_at=due_at)
    elif session_id:
        todo = TodoItem(session_id=session_id, title=title, description=description, due_at=due_at)
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return {"id": todo.id, "title": todo.title, "is_completed": bool(todo.is_completed)}


@app.post("/todos/{todo_id}/complete")
def complete_todo(todo_id: int, session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    query = db.query(TodoItem).filter(TodoItem.id == todo_id)
    if current_user:
        query = query.filter(TodoItem.user_id == current_user.id)
    elif session_id:
        query = query.filter(TodoItem.session_id == session_id)
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")
    todo = query.first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    todo.is_completed = True
    db.commit()
    return {"ok": True}


@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    query = db.query(TodoItem).filter(TodoItem.id == todo_id)
    if current_user:
        query = query.filter(TodoItem.user_id == current_user.id)
    elif session_id:
        query = query.filter(TodoItem.session_id == session_id)
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")
    todo = query.first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    db.delete(todo)
    db.commit()
    return {"ok": True}


@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, payload: dict, session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    query = db.query(TodoItem).filter(TodoItem.id == todo_id)
    if current_user:
        query = query.filter(TodoItem.user_id == current_user.id)
    elif session_id:
        query = query.filter(TodoItem.session_id == session_id)
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")
    todo = query.first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    title = payload.get('title')
    if title is not None:
        todo.title = title
    if 'description' in payload:
        todo.description = payload.get('description')
    if 'due_at' in payload:
        due = payload.get('due_at')
        if due:
            try:
                todo.due_at = datetime.fromisoformat(due)
            except Exception:
                raise HTTPException(status_code=400, detail='due_at must be ISO datetime')
        else:
            todo.due_at = None
    db.commit()
    return {"ok": True}


# -----------------------------
# Reminders: deliver due reminders
# -----------------------------
def _deliver_due_reminders_once():
    db = SessionLocal()
    try:
        now = datetime.now()
        reminders = db.query(Reminder).filter(Reminder.due_at <= now, Reminder.is_notified == False, Reminder.is_completed == False).all()
        results = []
        for r in reminders:
            if "alarm" in r.title.lower() or "wake" in r.title.lower():
                msg = f"⏰ Alarm now: {r.title}. It's time to act."
            else:
                msg = f"🔔 Reminder now: {r.title}. Don't forget."
            conv = None
            if r.session_id:
                conv = db.query(Conversation).filter(Conversation.session_id == r.session_id).first()
                if not conv:
                    conv = Conversation(session_id=r.session_id, title="Reminders")
                    db.add(conv)
                    db.commit()
                    db.refresh(conv)
            elif r.user_id:
                conv = db.query(Conversation).filter(Conversation.user_id == r.user_id).order_by(Conversation.updated_at.desc()).first()
                if not conv:
                    conv = Conversation(user_id=r.user_id, title="Reminders")
                    db.add(conv)
                    db.commit()
                    db.refresh(conv)
            if conv:
                m = Message(conversation_id=conv.id, sender="assistant", message=msg)
                db.add(m)
            r.is_notified = True
            db.commit()
            results.append({"id": r.id, "message": msg})
        return results
    finally:
        db.close()


@app.get('/reminders/due')
def reminders_due(session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    now = datetime.now()
    query = db.query(Reminder).filter(Reminder.due_at <= now, Reminder.is_notified == False, Reminder.is_completed == False)
    if current_user:
        query = query.filter(Reminder.user_id == current_user.id)
    elif session_id:
        query = query.filter(Reminder.session_id == session_id)
    else:
        return {"due_reminders": []}
    reminders = query.all()
    out = []
    for r in reminders:
        if "alarm" in r.title.lower() or "wake" in r.title.lower():
            msg = f"⏰ Alarm now: {r.title}. It's time to act."
        else:
            msg = f"🔔 Reminder now: {r.title}. Don't forget."
        out.append({"id": r.id, "message": msg})
        conv = None
        if r.session_id:
            conv = db.query(Conversation).filter(Conversation.session_id == r.session_id).first()
            if not conv:
                conv = Conversation(session_id=r.session_id, title="Reminders")
                db.add(conv)
                db.commit()
                db.refresh(conv)
        elif r.user_id:
            conv = db.query(Conversation).filter(Conversation.user_id == r.user_id).order_by(Conversation.updated_at.desc()).first()
            if not conv:
                conv = Conversation(user_id=r.user_id, title="Reminders")
                db.add(conv)
                db.commit()
                db.refresh(conv)
        if conv:
            m = Message(conversation_id=conv.id, sender="assistant", message=msg)
            db.add(m)
        r.is_notified = True
    db.commit()
    return {"due_reminders": out}


@app.api_route("/stream_audio", methods=["GET", "HEAD", "OPTIONS"])
def stream_audio(request: Request, video_id: str):
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id is required")

    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
        }
        cookiefile = os.getenv("YTDLP_COOKIES_FILE") or os.getenv("YTDLP_COOKIEFILE")
        if cookiefile:
            ydl_opts["cookiefile"] = cookiefile

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            audio_url = info.get("url")
            if not audio_url:
                raise HTTPException(status_code=404, detail="Audio stream not available")
            media_type = info.get("ext", "webm")
    except HTTPException:
        raise
    except Exception as e:
        err_text = str(e)
        if "Sign in to confirm you’re not a bot" in err_text or "cookies" in err_text.lower():
            raise HTTPException(
                status_code=502,
                detail=(
                    "Unable to resolve audio stream because YouTube requires authentication. "
                    "Set YTDLP_COOKIES_FILE to a cookies file or use the normal YouTube player instead."
                )
            )
        raise HTTPException(status_code=500, detail=f"Unable to resolve audio stream: {e}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header

    is_head_request = request.method == "HEAD"
    try:
        if is_head_request:
            upstream = requests.head(audio_url, headers=headers, allow_redirects=True, timeout=30)
        else:
            upstream = requests.get(audio_url, stream=True, headers=headers, timeout=30)

        if upstream.status_code not in (200, 206):
            raise HTTPException(status_code=502, detail=f"Failed to fetch audio stream: {upstream.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Audio stream fetch failed: {str(e)}")

    content_type = upstream.headers.get("Content-Type", f"audio/{media_type}")
    content_length = upstream.headers.get("Content-Length")
    response_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Range",
        "Accept-Ranges": upstream.headers.get("Accept-Ranges", "bytes"),
        "Cache-Control": "public, max-age=3600",
    }
    if content_length:
        response_headers["Content-Length"] = content_length
    if upstream.status_code == 206 and upstream.headers.get("Content-Range"):
        response_headers["Content-Range"] = upstream.headers.get("Content-Range")

    if is_head_request:
        upstream.close()
        return Response(status_code=upstream.status_code, media_type=content_type, headers=response_headers)

    return StreamingResponse(
        upstream.iter_content(chunk_size=8192),
        status_code=upstream.status_code,
        media_type=content_type,
        headers=response_headers,
    )





# -----------------------------
# API ENDPOINT
# -----------------------------
@app.post("/voice")
def voice_endpoint(request: Request, payload: VoiceRequest):
    origin = f"{request.url.scheme}://{request.url.netloc}"
    logger.info(f"Voice command received from {origin}: {payload.command}")
    response = process_command(payload.command, origin, payload.device_lat, payload.device_lon)
    logger.info(f"Voice response: {response}")
    return response


# Weather endpoint
@app.get("/weather")
def weather_endpoint(lat: float | None = None, lon: float | None = None):
    logger.info(f"Weather endpoint called with lat={lat}, lon={lon}")
    if lat is None or lon is None:
        logger.error("Weather endpoint missing lat or lon")
        raise HTTPException(status_code=400, detail="lat and lon query parameters are required")
    try:
        data = get_weather(lat, lon)
        logger.info(f"Weather endpoint success: city={data.get('city')}, temp={data.get('temperature')}°C")
        return data
    except CityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except WeatherServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))