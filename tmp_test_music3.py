from assistant.music_manager import MusicManager

mm = MusicManager()
print('start')

orig_search = mm._search_track

def debug_search(query):
    print('debug_search start')
    result = orig_search(query)
    print('debug_search end', result)
    return result

mm._search_track = debug_search
print('calling handle_command')
print(mm.handle_command('play_music', 'test song'))
print('done')
