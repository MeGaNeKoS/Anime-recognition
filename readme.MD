This module is made for detecting the anime from the file name.
This only work with file name that have similar formal with erai-raws, judas, anime time, etc.
Generally are,
`[fansub] title [episode] [any extra info]`
The default separator are `[ _.&+,|]`
For the extra info, it could be anything, including the file checksum, the file size, the file type, etc.
But in this module, it's only focussing on the title and the episode.

```python
import recognition

anime = recognition.track('[ASW] 86 - Eighty Six - 21 [1080p HEVC][9D595499].mkv')
print(anime)
# {'anilist': 131586,
# 'anime_title': '86: Eighty Six Part 2',
# 'anime_type': 'TV',
# 'anime_year': 2021,
# 'episode_number': 10,
# 'file_checksum': '9D595499',
# 'file_extension': 'mkv',
# 'file_name': '[ASW] 86 - Eighty Six - 21 [1080p HEVC][9D595499].mkv',
## 'release_group': 'ASW',
# 'video_resolution': '1080p',
# 'video_term': 'HEVC'}
```

# Module dev status
Currently, this module more or less finished. But there are still some things that need to be improved.
- Add folder detection if filename failed, usefull for anime from EMBER
- Remake anime-relation. Currently, it's using from [erengy/anime-relations](https://github.com/erengy/anime-relations). But it limited to only 1 rule per anime.
    Some fansub have different episode number for some anime. For example, digimon adventure tri:
    This could be fix by extend the anime-relation to support multiple rule based on the fansub. [Still on idea]
- Add support for another site [mal and kitsu].
- Rewrite the anitopy package, This one could be really hard since I need to think about the regex and the logic.

# Note
The module will not raise any exception. If there's any error, it should be logged and return as undetected.