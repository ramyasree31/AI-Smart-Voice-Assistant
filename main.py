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
from assistant.task_manager import handle_reminder_command, handle_todo_command, PENDING_TODO_CONTEXTS, _pending_context_key, _get_pending_todo_context
from services.weather_service import get_weather, CityNotFoundError, WeatherServiceError

# DB + Auth
from db import engine, Base, get_db, SessionLocal, migrate_database
from models import User, Conversation, Message, TodoItem, Reminder
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
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


@app.get("/voice", response_class=HTMLResponse)
def voice_page(request: Request):
    return templates.TemplateResponse(request, "voice.html")


@app.get("/chat-page", response_class=HTMLResponse)
def chat_page(request: Request):
    return templates.TemplateResponse(request, "chat.html")


@app.get("/todo", response_class=HTMLResponse)
def todo_page(request: Request):
    return templates.TemplateResponse(request, "todo.html")


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html")


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.get("/listen")
def listen_endpoint():
    text = listen()
    return {"command": text}


# Create DB tables and synchronize legacy SQLite message schema if needed
migrate_database()
Base.metadata.create_all(bind=engine)


def _normalize_conversation_title(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.strip().split())
    return cleaned[:64] or None


def _serialize_message(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
    }


def _serialize_conversation(conversation: Conversation, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    messages = sorted(conversation.messages, key=lambda m: m.timestamp or now)
    last_message = _serialize_message(messages[-1]) if messages else None
    title = conversation.title or "Untitled"
    if not conversation.title and messages:
        first_user = next((m for m in messages if m.role == "user"), None)
        if first_user:
            title = _normalize_conversation_title(first_user.content) or f"{conversation.created_at.strftime('%b %d')} Chat"
        else:
            title = f"{conversation.created_at.strftime('%b %d')} Chat"

    preview = None
    if last_message:
        preview = last_message["content"]
        if len(preview) > 120:
            preview = preview[:117] + "..."

    updated_at = conversation.updated_at or conversation.created_at or now
    return {
        "id": conversation.id,
        "title": title,
        "last_message": last_message,
        "preview": preview,
        "message_count": len(messages),
        "updated_at": updated_at.isoformat() if updated_at else None,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "is_today": updated_at.date() == now.date(),
    }


def _get_or_create_conversation_for_context(db: Session, user_id: int | None, session_id: str | None, now: datetime | None = None):
    now = now or datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if user_id:
        existing = (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .filter(Conversation.created_at >= day_start)
            .filter(Conversation.created_at <= day_end)
            .order_by(Conversation.created_at.desc())
            .first()
        )
        if existing:
            return existing
        conv = Conversation(user_id=user_id, title=f"{now.strftime('%b %d')} Chat")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    if session_id:
        existing = (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.created_at.desc())
            .first()
        )
        if existing:
            return existing
        conv = Conversation(session_id=session_id, title=f"{now.strftime('%b %d')} Chat")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    return None


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
    now = datetime.now()
    conv = _get_or_create_conversation_for_context(db, user_id=current_user.id, session_id=None, now=now)
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at.isoformat()}


@app.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if q:
        search = f"%{q.lower()}%"
        query = (
            query.outerjoin(Conversation.messages)
            .filter(or_(func.lower(Conversation.title).like(search), func.lower(Message.content).like(search)))
            .distinct()
        )

    convs = (
        query.order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_serialize_conversation(c, now=datetime.now()) for c in convs]


@app.get("/conversations/search")
def search_conversations(
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_conversations(db=db, current_user=current_user, q=q, limit=limit, offset=offset)


@app.get("/conversations/{conv_id}")
def get_conversation(conv_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = [
        {"id": m.id, "role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()}
        for m in sorted(conv.messages, key=lambda x: x.timestamp)
    ]
    return {
        "id": conv.id,
        "title": conv.title or f"{conv.created_at.strftime('%b %d')} Chat",
        "messages": msgs,
        "message_count": len(msgs),
        "is_today": (conv.updated_at or conv.created_at or datetime.now()).date() == datetime.now().date(),
    }


@app.patch("/conversations/{conv_id}")
def patch_conversation(conv_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    conv.title = title
    conv.updated_at = datetime.now()
    db.commit()
    db.refresh(conv)
    return _serialize_conversation(conv, now=datetime.now())


@app.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"ok": True}


@app.post("/conversation/{conv_id}/messages")
def post_message(conv_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    role = payload.get("role") or "user"
    content = payload.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    m = Message(conversation_id=conv.id, role=role, content=content)
    db.add(m)
    conv.updated_at = m.timestamp
    db.commit()
    db.refresh(m)
    return {"id": m.id, "role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()}


@app.post("/chat")
def chat(payload: VoiceRequest, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    conv = None

    if current_user:
        now = datetime.now()
        if payload.conversation_id:
            conv = db.query(Conversation).filter(Conversation.id == payload.conversation_id, Conversation.user_id == current_user.id).first()
            if conv and conv.created_at.date() != now.date():
                conv = None
        if not conv:
            conv = _get_or_create_conversation_for_context(db, user_id=current_user.id, session_id=payload.session_id, now=now)

        if not conv.title or conv.title.startswith("Chat"):
            conv.title = _normalize_conversation_title(payload.command) or f"{now.strftime('%b %d')} Chat"

        user_msg = Message(conversation_id=conv.id, role="user", content=payload.command)
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        last_msgs = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.timestamp.desc()).limit(10).all()
        history = []
        for m in reversed(last_msgs):
            history.append({"role": m.role, "content": m.content})

    context_key, pending_context = _get_pending_todo_context(current_user.id if current_user else None, payload.session_id, db)
    if pending_context:
        response = handle_todo_command(payload.command, db, current_user.id if current_user else None, payload.session_id)
    else:
        # Check intents for reminders/todos and handle them directly
        intent, target = detect_intent(payload.command)
        if intent == 'reminder':
            response = handle_reminder_command(payload.command, db, current_user.id if current_user else None, payload.session_id)
        elif intent in ('todo', 'task_create'):
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
        assistant_msg = Message(conversation_id=conv.id, role="assistant", content=assistant_text)
        db.add(assistant_msg)
        conv.updated_at = assistant_msg.timestamp
        if not conv.title:
            conv.title = _normalize_conversation_title(payload.command) or f"{datetime.now().strftime('%b %d')} Chat"
        db.commit()
        assistant_response["conversation_id"] = conv.id

    return assistant_response


# -----------------------------
# Reminder endpoints
# -----------------------------
@app.get("/reminders")
def list_reminders(
    session_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    query = db.query(Reminder)
    if current_user:
        query = query.filter(Reminder.user_id == current_user.id)
    elif session_id:
        query = query.filter(Reminder.session_id == session_id)
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")

    reminders = query.order_by(Reminder.date.asc(), Reminder.start_time.asc(), Reminder.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "date": r.date,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "priority": r.priority or "Medium",
            "category": r.category or "Personal",
            "status": r.status or ("completed" if r.is_completed else "pending"),
            "is_completed": bool(r.is_completed),
            "is_notified": bool(r.is_notified),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "due_at": r.due_at.isoformat() if r.due_at else None,
        }
        for r in reminders
    ]


@app.post("/reminders")
def create_reminder(payload: dict, session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    title = payload.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    reminder = Reminder(
        title=title,
        description=payload.get("description"),
        date=payload.get("date"),
        start_time=payload.get("start_time"),
        end_time=payload.get("end_time"),
        priority=payload.get("priority") or "Medium",
        category=payload.get("category") or "Personal",
        status=payload.get("status") or "pending",
    )
    if current_user:
        reminder.user_id = current_user.id
    elif session_id:
        reminder.session_id = session_id
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")

    if payload.get("due_at"):
        try:
            reminder.due_at = datetime.fromisoformat(payload.get("due_at"))
        except Exception:
            raise HTTPException(status_code=400, detail="due_at must be ISO datetime")

    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return {"id": reminder.id, "title": reminder.title, "status": reminder.status or ("completed" if reminder.is_completed else "pending")}


@app.put("/reminders/{reminder_id}")
def update_reminder(reminder_id: int, payload: dict, session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    query = db.query(Reminder).filter(Reminder.id == reminder_id)
    if current_user:
        query = query.filter(Reminder.user_id == current_user.id)
    elif session_id:
        query = query.filter(Reminder.session_id == session_id)
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")

    reminder = query.first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    for field in ["title", "description", "date", "start_time", "end_time", "priority", "category", "status"]:
        if field in payload:
            setattr(reminder, field, payload.get(field))
    if 'due_at' in payload:
        due = payload.get('due_at')
        reminder.due_at = datetime.fromisoformat(due) if due else None
    reminder.updated_at = datetime.now()
    db.commit()
    db.refresh(reminder)
    return {"ok": True}


@app.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    query = db.query(Reminder).filter(Reminder.id == reminder_id)
    if current_user:
        query = query.filter(Reminder.user_id == current_user.id)
    elif session_id:
        query = query.filter(Reminder.session_id == session_id)
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")

    reminder = query.first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return {"ok": True}


@app.patch("/reminders/{reminder_id}/complete")
def complete_reminder(reminder_id: int, session_id: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    query = db.query(Reminder).filter(Reminder.id == reminder_id)
    if current_user:
        query = query.filter(Reminder.user_id == current_user.id)
    elif session_id:
        query = query.filter(Reminder.session_id == session_id)
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")

    reminder = query.first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder.is_completed = True
    reminder.status = "completed"
    reminder.updated_at = datetime.now()
    db.commit()
    return {"ok": True}


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
            "date": t.date,
            "start_time": t.start_time,
            "end_time": t.end_time,
            "reminder": t.reminder,
            "recurrence": t.recurrence,
            "repeat_days": t.repeat_days,
            "subtasks": t.subtasks,
            "priority": t.priority,
            "category": t.category,
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
    date = payload.get("date")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    reminder = payload.get("reminder")
    subtasks = payload.get("subtasks")
    priority = payload.get("priority") or "Medium"
    category = payload.get("category") or "Personal"
    due_at = None
    if payload.get("due_at"):
        try:
            due_at = datetime.fromisoformat(payload.get("due_at"))
        except Exception:
            raise HTTPException(status_code=400, detail="due_at must be ISO datetime")
    if current_user:
        todo = TodoItem(
            user_id=current_user.id,
            title=title,
            description=description,
            date=date,
            start_time=start_time,
            end_time=end_time,
            reminder=reminder,
            recurrence=payload.get('recurrence') or 'one_time',
            repeat_days=payload.get('repeat_days'),
            subtasks=subtasks,
            priority=priority,
            category=category,
            due_at=due_at,
        )
    elif session_id:
        todo = TodoItem(
            session_id=session_id,
            title=title,
            description=description,
            date=date,
            start_time=start_time,
            end_time=end_time,
            reminder=reminder,
            recurrence=payload.get('recurrence') or 'one_time',
            repeat_days=payload.get('repeat_days'),
            subtasks=subtasks,
            priority=priority,
            category=category,
            due_at=due_at,
        )
    else:
        raise HTTPException(status_code=401, detail="Authentication or session_id required")
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return {
        "id": todo.id,
        "title": todo.title,
        "description": todo.description,
        "date": todo.date,
        "start_time": todo.start_time,
        "end_time": todo.end_time,
        "reminder": todo.reminder,
        "recurrence": todo.recurrence,
        "repeat_days": todo.repeat_days,
        "subtasks": todo.subtasks,
        "priority": todo.priority,
        "category": todo.category,
        "is_completed": bool(todo.is_completed),
    }


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
    if 'date' in payload:
        todo.date = payload.get('date')
    if 'start_time' in payload:
        todo.start_time = payload.get('start_time')
    if 'end_time' in payload:
        todo.end_time = payload.get('end_time')
    if 'reminder' in payload:
        todo.reminder = payload.get('reminder')
    if 'subtasks' in payload:
        todo.subtasks = payload.get('subtasks')
    if 'recurrence' in payload:
        todo.recurrence = payload.get('recurrence') or 'one_time'
    if 'repeat_days' in payload:
        todo.repeat_days = payload.get('repeat_days')
    if 'priority' in payload:
        todo.priority = payload.get('priority') or 'Medium'
    if 'category' in payload:
        due = payload.get('due_at')
        if due:
            try:
                todo.due_at = datetime.fromisoformat(due)
            except Exception:
                raise HTTPException(status_code=400, detail='due_at must be ISO datetime')
        else:
            todo.due_at = None
    if 'is_completed' in payload:
        todo.is_completed = bool(payload.get('is_completed'))
    todo.updated_at = datetime.now()
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
                m = Message(conversation_id=conv.id, role="assistant", content=msg)
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
            m = Message(conversation_id=conv.id, role="assistant", content=msg)
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
def voice_endpoint(request: Request, payload: VoiceRequest, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    origin = f"{request.url.scheme}://{request.url.netloc}"
    logger.info(f"Voice command received from {origin}: {payload.command}")

    context_key, pending_context = _get_pending_todo_context(current_user.id if current_user else None, payload.session_id, db)
    if pending_context:
        response = handle_todo_command(payload.command, db, current_user.id if current_user else None, payload.session_id)
    else:
        intent, target = detect_intent(payload.command)
        if intent == 'reminder':
            response = handle_reminder_command(payload.command, db, current_user.id if current_user else None, payload.session_id)
        elif intent in ('todo', 'task_create'):
            response = handle_todo_command(payload.command, db, current_user.id if current_user else None, payload.session_id)
        else:
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