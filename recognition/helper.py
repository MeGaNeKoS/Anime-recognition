import re
import logging

logger = logging.getLogger(__package__)
SUPPORTED_APIS = ['mal', 'kitsu', 'anilist']


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
