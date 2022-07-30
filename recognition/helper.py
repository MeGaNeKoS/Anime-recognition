import json
import logging
import re

logger = logging.getLogger(__name__)  # inherits package logger configuration
SUPPORTED_APIS = ['mal', 'kitsu', 'anilist']


def anime_season_relation(anime):
    with open('./data/Anime-Fansub-Relation/anime-fansub-relation.json', "r+", encoding="utf-8") as input_json:
        anime_fansub_relation = json.load(input_json)

    anime_relation = anime_fansub_relation.get(anime['anime_title'], None)
    anime_id = None
    anime_season = anime.get("anime_season", None)

    # we found in database
    if anime_relation:
        # if we have the anime season in the anime relation
        # the anime season should be a string of a number without leading zero and can't be negative
        logger.info("Found in the anime in database")
        if anime_season:
            anime_relation = anime_relation.get(str(int(anime_season)), {})

        # optional
        if anime.get("anime_type", "torrent") != "torrent":
            logger.info("Found in the anime using the anime type")
            anime_relation = anime_relation.get(anime.get("anime_type", "").lower(), anime_relation)

        if anime.get("anime_year", 0):
            logger.info("Found in the anime using the anime type")
            anime_relation = anime_relation.get(anime.get("anime_year", "").lower(), anime_relation)

        # this can be change on code above, if we have the anime season in the anime relation
        # if we don't have the anime season in the anime relation, then we want to ask the user to enter the anime id
        if anime_relation:
            # if the anime fansub in the anime relation
            anime_id = anime_relation.get(anime.get('release_group', "").lower(), None)
            # else we return the default value
            if anime_id is None:
                anime_id = anime_relation.get("anilist", None)
                logger.info(f"Anime id are {anime_id}")
            else:
                logger.info(f"Anime with fansub from {anime.get('release_group')} are {anime_id}")
        else:
            logger.info(f"No Season {int(anime_season)} in database")
    return anime_id


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
        id_pattern = "(\d+|[\?~])\|(\d+|[\?~])\|(\d+|[\?~])"
        ep_pattern = "(\d+)-?(\d+|\?)?"
        full = r'- {0}:{1} -> {0}:{1}(!)?'.format(id_pattern, ep_pattern)
        _re = re.compile(full)
        version = r'- version: (\d.+)'
        _re_version = re.compile(version)

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
