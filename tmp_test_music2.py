import sys
from assistant.music_manager import MusicManager

print('start', flush=True)
mm = MusicManager()
print('created', flush=True)
print(mm.youtube_service.search_track('test song'), flush=True)
try:
    result = mm.handle_command('play_music', 'test song')
    print('result', result, flush=True)
except Exception as e:
    print('exception', type(e).__name__, e, flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
print('end', flush=True)
