from assistant.music_manager import MusicManager

mm = MusicManager()
print('start', flush=True)

orig_play = mm.play
orig_add_to_queue = mm.add_to_queue
orig_search = mm._search_track
orig_spotify = mm.spotify_service.search_track
orig_yt = mm.youtube_service.search_track


def debug_play(query=None):
    print('debug_play start', repr(query), flush=True)
    result = orig_play(query)
    print('debug_play end', result, flush=True)
    return result


def debug_add_to_queue(query, play_now=False):
    print('debug_add_to_queue start', repr(query), play_now, flush=True)
    result = orig_add_to_queue(query, play_now=play_now)
    print('debug_add_to_queue end', result, flush=True)
    return result


def debug_search_track(query):
    print('debug_search_track start', repr(query), flush=True)
    result = orig_search(query)
    print('debug_search_track end', result, flush=True)
    return result


def debug_spotify_search(query):
    print('debug_spotify_search start', repr(query), flush=True)
    result = orig_spotify(query)
    print('debug_spotify_search end', result, flush=True)
    return result


def debug_yt_search(query):
    print('debug_yt_search start', repr(query), flush=True)
    result = orig_yt(query)
    print('debug_yt_search end', result, flush=True)
    return result

mm.play = debug_play
mm.add_to_queue = debug_add_to_queue
mm._search_track = debug_search_track
mm.spotify_service.search_track = debug_spotify_search
mm.youtube_service.search_track = debug_yt_search

print('calling handle_command', flush=True)
res = mm.handle_command('play_music', 'test song')
print('handle_command returned', res, flush=True)
print('end', flush=True)
