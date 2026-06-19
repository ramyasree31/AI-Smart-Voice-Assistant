from urllib.parse import quote_plus
from services.youtube_services import search_youtube_video
import yt_dlp
import logging

logger = logging.getLogger(__name__)


class YouTubeMusicService:
    def search_track(self, query: str) -> dict:
        if not query:
            return None

        query = query.strip()
        
        # Use yt-dlp to search and extract audio information
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Search for official audio or lyric videos which are more embeddable
                search_query = f"ytsearch5:{query} official audio"
                info = ydl.extract_info(search_query, download=False)
                
                if info and 'entries' in info and len(info['entries']) > 0:
                    entry = info['entries'][0]  # Get first result
                    video_id = entry.get('id')
                    title = entry.get('title', query)
                    
                    if video_id:
                        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                        proxy_url = f"/stream_audio?video_id={video_id}"
                        return {
                            "source": "youtube_music",
                            "title": title,
                            "artist": "",
                            "query": query,
                            "url": youtube_url,
                            "playable_url": proxy_url,
                            "spotify_uri": None,
                            "source_id": video_id,
                            "metadata": {
                                "video_title": title,
                                "video_id": video_id,
                                "audio_url": proxy_url,
                                "is_audio_stream": True,
                            },
                        }
        except Exception as e:
            logger.error(f"Error searching YouTube music with yt-dlp: {e}")
        
        # Fallback to YouTube API search
        video_id = search_youtube_video(query)
        
        if video_id:
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            return {
                "source": "youtube_music",
                "title": query,
                "artist": "",
                "query": query,
                "url": youtube_url,
                "playable_url": youtube_url,
                "spotify_uri": None,
                "source_id": video_id,
                "metadata": {},
            }
        else:
            # Fallback to search URL if no video found
            youtube_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
            return {
                "source": "youtube_music",
                "title": query,
                "artist": "",
                "query": query,
                "url": youtube_url,
                "playable_url": youtube_url,
                "spotify_uri": None,
                "source_id": None,
                "metadata": {},
            }
