from medusa.genre import song_similarity

print(song_similarity("house", 124, "house", 126))   # ~1.0
print(song_similarity("house", 124, "disco", 120))   # medium
print(song_similarity("house", 124, "dnb", 170))     # very low
