import logging
import os
import requests
import yt_dlp
from fastapi import (
    FastAPI, Request, WebSocket, WebSocketDisconnect,
    Form, Body, HTTPException
)
from fastapi.responses import (
    HTMLResponse, RedirectResponse, StreamingResponse, Response
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
from services.weather_service import get_weather, CityNotFoundError, WeatherServiceError



logger = logging.getLogger("smart_voice_assistant")

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
    device_lat: float | None = None
    device_lon: float | None = None



# -----------------------------
# HOME ROUTE → SERVE INDEX.HTML
# -----------------------------
@app.get("/", response_class=HTMLResponse)
@app.get("/home", response_class=HTMLResponse)
def home(request:Request):

    return templates.TemplateResponse(
    request=request,
    name="home.html",
    context={
        "title": "Home"
    }
)


@app.get("/listen")
def listen_endpoint():
    text = listen()
    return {"command": text}


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