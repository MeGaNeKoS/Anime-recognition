import logging


CONFIG = {
    "relation_file_path": "./data/anime-relations/anime-relations.txt",
    "source_api": "anilist",  # mal, kitsu, anilist
    "link": "https://api.github.com/repos/erengy/anime-relations/commits?path=anime-relations.txt&per_page=1",
    "file_link": 'https://raw.githubusercontent.com/erengy/anime-relations/master/anime-relations.txt',
    "title": "romaji",
    "folder_blacklist": ["extra", "extras", "ova", "attachment", "ncop", "nced", "nc", "anime", "specials", "ova",
                         "oad", "bonus cd", "menu", "pv", "scans", "bdmv"],
    "ignored_type": ['ending', 'opening', 'ed', 'nced', 'op', 'ncop', 'menu', '0Season', ' none'],
    "valid_ext": ['3g2', '3gp', 'aaf', 'asf', 'avchd', 'avi', 'drc', 'flv', 'm2v', 'm4p', 'm4v', 'mkv', 'mng',
                  'mov', 'mp2', 'mp4', 'mpe', 'mpeg', 'mpg', 'mpv', 'mxf', 'nsv', 'ogg', 'ogv', 'qt', 'rm', 'rmvb',
                  'roq', 'svi', 'vob', 'webm', 'wmv', 'yuv'],
}

logger = logging.getLogger(__package__)  # set package logger configuration
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
file_handler = logging.FileHandler('app.log', encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

CONFIG["logger"] = logger
CONFIG["log_handler"] = [file_handler]

for handler in CONFIG["log_handler"]:
    logger.addHandler(handler)


# def set_config(**kwargs):
#     edit_log_handler = False
#     edit_logger = False
#     for key, value in kwargs.items():
#         CONFIG[key] = value
#         if key == "log_handler":
#             edit_log_handler = True
#         if key == "logger":
#             edit_logger = True
#
#     if edit_log_handler and not edit_logger:
#         logger = logging.getLogger(__name__)
#         logger.setLevel(logging.DEBUG)
#         for handler in CONFIG["log_handler"]:
#             logger.addHandler(handler)
#         CONFIG["logger"] = logger
#
#     if edit_logger:
#         for handler in CONFIG["log_handler"]:
#             CONFIG["logger"].addHandler(handler)

