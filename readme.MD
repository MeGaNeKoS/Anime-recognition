This module is made for detecting the anime from the file name.
This only work with file name that have similar formal with erai-raws, judas, anime time, etc.
Generally are,
`[fansub] title [episode] [any extra info]`
The separator can be `[ _.&+,|]`
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