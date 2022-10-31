CONFIG = {
    "file_path": {
        "anime_relation": "data/anime-relations.txt",
        "fansub_relation": "data/fansub-relations.json",
        "filename_relation": "data/filename-relations.json",
    },
    "github_commit": {
        "anime_relation": "https://api.github.com/repos/erengy/anime-relations/commits?path=anime-relations.txt&per_page=1",
        "fansub_relation": "https://api.github.com/repos/MeGaNeKoS/Anime-Fansub-Relation/commits?path=data/fansub-relations.json&per_page=1",
        "filename_relation": "https://api.github.com/repos/MeGaNeKoS/Anime-Fansub-Relation/commits?path=data/filename-relations.json&per_page=1",
    },
    "file_link": {
        "anime_relation": "https://raw.githubusercontent.com/erengy/anime-relations/master/anime-relations.txt",
        "fansub_relation": "https://raw.githubusercontent.com/MeGaNeKoS/Anime-Fansub-Relation/main/data/fansub-relations.json",
        "filename_relation": "https://raw.githubusercontent.com/MeGaNeKoS/Anime-Fansub-Relation/main/data/fansub-relations.json",
    },
    "source_api": "anilist",  # mal, kitsu, anilist
    "title": "romaji",
    "folder_blacklist": ["extra", "extras", "ova", "attachment", "ncop", "nced", "nc", "anime", "specials", "ova",
                         "oad", "bonus cd", "menu", "pv", "scans", "bdmv"],
    "fansub_relation": 'data/anime-fansub-relation.json',
    "filename_relation": 'data/custom-filename-relations.json',
    "extra_type": ['ending', 'ed', 'nced', 'opening', 'op', 'ncop', 'pv', 'preview'],
    "valid_ext": ['3g2', '3gp', 'aaf', 'asf', 'avchd', 'avi', 'drc', 'flv', 'm2v', 'm4p', 'm4v', 'mkv', 'mng',
                  'mov', 'mp2', 'mp4', 'mpe', 'mpeg', 'mpg', 'mpv', 'mxf', 'nsv', 'ogg', 'ogv', 'qt', 'rm',
                  'rmvb', 'roq', 'svi', 'vob', 'webm', 'wmv', 'yuv'],
    "mem_cache_size": 1000
}
