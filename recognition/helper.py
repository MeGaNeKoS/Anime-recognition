import os
import json
import logging
import re

from .config import CONFIG

logger = logging.getLogger(__name__)
SUPPORTED_APIS = ['mal', 'kitsu', 'anilist']

_cache = {
    "filename_relation_mTime": 0.,
    "filename_relation": {},
    "fansub_relation_mTime": 0.,
    "fansub_relation": {},
}


def anime_season_relation(anime):
    anime_id = None
    anime_season = anime.get("anime_season", None)

    try:
        modified_time = os.stat(CONFIG['file_path']['filename_relation']).st_mtime
        if modified_time != _cache['filename_relation_mTime']:
            with open(CONFIG['file_path']['filename_relation'], "r+", encoding="utf-8") as input_json:
                filename_relation = _cache['filename_relation'] = json.load(input_json)
                _cache['filename_relation_mTime'] = modified_time
        else:
            filename_relation = _cache['filename_relation']

        anime_id = filename_relation.get(anime.get('file_name', ""), None)
        if anime_id:
            anime["custom_filename"] = True  # just a mark to know that we use custom filename, no real use yet.

        if anime_id is None:
            modified_time = os.stat(CONFIG['file_path']['fansub_relation']).st_mtime
            if modified_time != _cache['fansub_relation_mTime']:
                with open(CONFIG['file_path']['fansub_relation'], "r+", encoding="utf-8") as input_json:
                    anime_fansub_relation = json.load(input_json)
                    _cache['fansub_relation_mTime'] = modified_time
            else:
                anime_fansub_relation = _cache['fansub_relation']

            anime_relation = anime_fansub_relation.get(anime['anime_title'], None)
            # we found in database
            if anime_relation:
                # the anime season should be a string of a number without leading zero and can't be negative
                # check for the anime type
                if isinstance(anime.get("anime_type", None), list):
                    for anime_type in anime.get("anime_type", []):
                        if anime_type.lower() != "torrent":
                            anime_relation = anime_relation.get(anime_type.lower(), {})
                elif anime.get("anime_type", "torrent").lower() != "torrent":
                    anime_relation = anime_relation.get(anime.get("anime_type", "").lower(), {})

                if anime_season is not None:
                    anime_relation = anime_relation.get(str(int(anime_season)), {})

                if anime.get("anime_year", 0):
                    anime_relation = anime_relation.get(str(anime.get("anime_year", 0)), anime_relation)

                if anime.get("episode_title"):
                    anime_relation = anime_relation.get(anime.get("episode_title", "").lower(), anime_relation)

                # this can be change on code above, if we have the anime season in the anime relation
                if anime_relation:
                    # if the anime fansub in the anime relation
                    anime_id = anime_relation.get(anime.get('release_group', "").lower(), None)
                    # else we return the default value
                    if anime_id is None:
                        anime_id = anime_relation.get("anilist", None)
                        logger.debug(f"Anime id are {anime_id}")
                    else:
                        logger.debug(f"Anime id  from fansub {anime.get('release_group')} are {anime_id}")
                else:
                    logger.debug(f"No Season {anime_season} in database")

    except (FileNotFoundError, ValueError, TypeError):
        pass
    return anime, anime_id


def parse_anime_relations(filename, api='anilist'):
    """
    Support for Taiga-style anime relations file.
    Thanks to erengy and all the contributors.
    Database under the public domain.

    https://github.com/erengy/anime-relations
    """
    (src_grp, dst_grp) = (SUPPORTED_APIS.index(api) + 1, SUPPORTED_APIS.index(api) + 6)

    with open(filename) as f:

        relations = {'meta': {}}
        id_pattern = r"(\d+|[\?~])\|(\d+|[\?~])\|(\d+|[\?~])"
        ep_pattern = r"(\d+)-?(\d+|\?)?"
        full = r'- {0}:{1} -> {0}:{1}(!)?'.format(id_pattern, ep_pattern)
        _re = re.compile(full)

        mode = 0

        for line in f:
            line = line.strip()

            if not line:
                continue
            if line[0] == '#':
                continue
            if mode == 0 and line == "::rules":
                mode = 1
            elif mode == 1 and line[0] == '-':
                m = _re.match(line)
                if m:
                    # Source
                    src_id = m.group(src_grp)

                    # Handle unknown IDs
                    if src_id == '?':
                        continue
                    else:
                        src_id = int(src_id)
                    # Handle infinite ranges
                    if m.group(5) == '?':
                        src_eps = (int(m.group(4)), -1)
                    else:
                        src_eps = (int(m.group(4)), int(
                            m.group(5) or m.group(4)))

                    # Destination
                    dst_id = m.group(dst_grp)

                    # Handle ID repeaters
                    if dst_id == '~':
                        dst_id = src_id
                    else:
                        dst_id = int(dst_id)

                    # Handle infinite ranges
                    if m.group(10) == '?':
                        dst_eps = (int(m.group(9)), -1)
                    else:
                        dst_eps = (int(m.group(9)), int(
                            m.group(10) or m.group(9)))

                    if src_id not in relations:
                        relations[src_id] = []
                    relations[src_id].append((src_eps, dst_id, dst_eps))
                    # Handle the destination ID is redirected to itself
                    if m.group(11) == '!':
                        if dst_id not in relations:
                            relations[dst_id] = []
                        relations[dst_id].append((dst_eps, dst_id, dst_eps))
                else:
                    logger.info("Not recognized. " + line)

        return relations


def redirect_show(show_tuple, redirections):
    if not redirections:
        return show_tuple

    (show_id, ep) = show_tuple
    try:
        for redirection in redirections[show_id]:
            (src_eps, dst_id, dst_eps) = redirection

            if (src_eps[1] == -1 and ep >= src_eps[0]) or (ep in range(src_eps[0], src_eps[1] + 1)):
                new_show_id = dst_id
                new_ep = ep + (dst_eps[0] - src_eps[0])
                return new_show_id, new_ep
    except KeyError:
        logger.debug(f"Show id {show_id} is not found on the redirections table!")
    return show_tuple


def get_number(number_string: str):
    digit = ""
    try:
        number = float(number_string)
        if number.is_integer():
            digit = str(int(number))
        else:
            digit = str(number)
    except ValueError:
        for x in number_string:
            if x.isdigit():
                digit += f"{x}"
            else:
                break
    return digit
