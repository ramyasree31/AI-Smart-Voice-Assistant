import re
import requests

YOUTUBE_API_KEY = "AIzaSyDz7jr7Chu-8LOFKt4erttL1ABgdn9WVLk"
YOUTUBE_EMBED_URL = "https://www.youtube.com/embed/{}"
import os

#YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def _normalize_query(query):
    if not query:
        return ""

    query = query.lower()
    query = re.sub(r"\b(from|on)\s+youtube\b", "", query)
    query = re.sub(r"\b(playing|play|listen to|listen|please|song|music|youtube)\b", "", query)
    query = re.sub(r"[^\w\s]", " ", query)
    return " ".join(query.split()).strip()


def _pick_embeddable_video(video_ids):
    if not video_ids:
        return None

    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "status,contentDetails",
        "id": ",".join(video_ids),
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None

    data = response.json()
    candidates = []
    for item in data.get("items", []):
        status = item.get("status", {})
        content = item.get("contentDetails", {})
        if status.get("embeddable") is not True or status.get("privacyStatus") != "public":
            continue

        region_restriction = content.get("regionRestriction", {})
        blocked = bool(region_restriction.get("blocked"))
        licensed = content.get("licensedContent", True)

        candidates.append({
            "id": item.get("id"),
            "licensed": licensed,
            "blocked": blocked,
            "region_restriction": region_restriction,
        })
        print(
            "VIDEO:",
            item.get("id"),
            "EMBED:",
            status.get("embeddable"),
            "PRIVACY:",
            status.get("privacyStatus")
        )

    if not candidates:
        return None
    

    candidates.sort(
        key=lambda item: (
            item["blocked"],
            item["licensed"],
        )
    )

    print("Selected:", candidates[0]["id"])
    return candidates[0]["id"]


def search_youtube_video(query):
    #query = _normalize_query(query)

    # Better for music playback
    query = f"{query} official audio"
    if not query:
        return None

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 10,
        "videoEmbeddable": "true",
        "videoSyndicated": "true",
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None

    data = response.json()
    items = data.get("items", [])
    if not items:
        return None

    video_ids = [item.get("id", {}).get("videoId") for item in items if item.get("id", {}).get("videoId")]
    return _pick_embeddable_video(video_ids)
