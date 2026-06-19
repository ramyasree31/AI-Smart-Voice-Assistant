import threading
from typing import Optional

from services.spotify_service import SpotifyService
from services.youtube_music_service import YouTubeMusicService


class MusicManager:
    def __init__(self):
        self.queue = []
        self.current_index = -1
        self.playback_status = "stopped"
        self.spotify_service = SpotifyService()
        self.youtube_service = YouTubeMusicService()
        self._lock = threading.RLock()

    def _current_track(self) -> Optional[dict]:
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

    def _build_response(self, action: str, message: str, track: Optional[dict] = None) -> dict:
        payload = {
            "response": message,
            "action": action,
            "playback_status": self.playback_status,
            "queue_length": len(self.queue),
        }

        if track:
            payload.update(
                {
                    "source": track.get("source"),
                    "query": track.get("query"),
                    "url": track.get("playable_url"),
                    "track_title": track.get("title"),
                    "track_artist": track.get("artist"),
                    "spotify_uri": track.get("spotify_uri"),
                    "queue_position": self.current_index + 1,
                    "metadata": track.get("metadata", {}),
                }
            )

        return payload

    def _search_track(self, query: str) -> Optional[dict]:
        spotify_track = self.spotify_service.search_track(query)
        if spotify_track:
            return spotify_track

        return self.youtube_service.search_track(query)

    def play(self, query: Optional[str] = None) -> dict:
        with self._lock:
            if query:
                return self.add_to_queue(query, play_now=True)

            current = self._current_track()
            if current and self.playback_status == "paused":
                self.playback_status = "playing"
                return self._build_response(
                    "resume_music", f"Resuming {current.get('title')}.", current
                )

            if current:
                self.playback_status = "playing"
                return self._build_response(
                    "play_music", f"Playing {current.get('title')}.", current
                )

            return {
                "response": "What would you like to play?",
                "action": "request_music_query",
                "playback_status": self.playback_status,
                "queue_length": len(self.queue),
            }

    def pause(self) -> dict:
        with self._lock:
            current = self._current_track()
            if not current or self.playback_status != "playing":
                message = "There is no active track to pause."
                if current and self.playback_status == "paused":
                    message = f"{current.get('title')} is already paused."
                return self._build_response("pause_music", message, current)

            self.playback_status = "paused"
            return self._build_response(
                "pause_music", f"Paused {current.get('title')}.", current
            )

    def resume(self) -> dict:
        with self._lock:
            current = self._current_track()
            if not current:
                return self._build_response("resume_music", "There is no track to resume.", None)

            self.playback_status = "playing"
            return self._build_response(
                "resume_music", f"Resuming {current.get('title')}.", current
            )

    def next_track(self) -> dict:
        with self._lock:
            if self.current_index + 1 >= len(self.queue):
                return self._build_response(
                    "next_track",
                    "You are already at the end of the queue.",
                    self._current_track(),
                )

            self.current_index += 1
            self.playback_status = "playing"
            current = self._current_track()
            return self._build_response(
                "next_track",
                f"Skipping to the next track: {current.get('title')}.",
                current,
            )

    def previous_track(self) -> dict:
        with self._lock:
            if self.current_index <= 0:
                return self._build_response(
                    "previous_track",
                    "There is no previous track in the queue.",
                    self._current_track(),
                )

            self.current_index -= 1
            self.playback_status = "playing"
            current = self._current_track()
            return self._build_response(
                "previous_track",
                f"Playing the previous track: {current.get('title')}.",
                current,
            )

    def add_to_queue(self, query: str, play_now: bool = False) -> dict:
        with self._lock:
            if not query:
                return {
                    "response": "Please tell me the name of the track or artist to add.",
                    "action": "request_music_query",
                    "playback_status": self.playback_status,
                    "queue_length": len(self.queue),
                }

            track = self._search_track(query)
            if not track:
                return {
                    "response": f"I couldn't find {query} on Spotify or YouTube Music.",
                    "action": "no_track_found",
                    "playback_status": self.playback_status,
                    "queue_length": len(self.queue),
                }

            self.queue.append(track)
            self.current_index = len(self.queue) - 1 if play_now or self.current_index == -1 else self.current_index
            if play_now or self.current_index == len(self.queue) - 1:
                self.playback_status = "playing"
                return self._build_response(
                    "play_music",
                    f"Playing {track.get('title')} from {track.get('source')}.",
                    track,
                )

            return self._build_response(
                "add_to_queue",
                f"Added {track.get('title')} to the queue.",
                track,
            )

    def handle_command(self, action: str, query: Optional[str] = None) -> dict:
        if action == "play_music":
            return self.play(query)
        if action == "pause_music":
            return self.pause()
        if action == "resume_music":
            return self.resume()
        if action == "next_track":
            return self.next_track()
        if action == "previous_track":
            return self.previous_track()
        if action == "add_to_queue":
            return self.add_to_queue(query, play_now=False)
        if action == "stop_music":
            return self.pause()

        return {
            "response": "I did not recognize that music command.",
            "action": "unknown_music_command",
            "playback_status": self.playback_status,
            "queue_length": len(self.queue),
        }
