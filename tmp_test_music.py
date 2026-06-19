from assistant.music_manager import MusicManager

mm = MusicManager()
print('import OK')
print(mm.youtube_service.search_track('test song'))
print(mm.handle_command('play_music', 'test song'))
