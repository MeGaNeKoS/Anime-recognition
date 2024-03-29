import functools
import logging
import os
import re
from datetime import date
from difflib import SequenceMatcher

import aniparse
import devlog
import requests
from Anisearch import Anilist
from num2words import num2words

from . import helper
# get all variable from config.py
from .config import CONFIG

logger = logging.getLogger(__name__)
instance = Anilist()

last_check = {}
last_day_check = None
redirect = None

open_brackets = (
    "(",  # U+0028 LEFT PARENTHESIS
    "[",  # U+005B LEFT SQUARE BRACKET
    "{",  # U+007B LEFT CURLY BRACKET
    "\u300C",  # Corner bracket
    "\u300E",  # White corner bracket
    "\u3010",  # Black lenticular bracket
    "\uFF08",  # Fullwidth parenthesis
)

close_brackets = (
    ")",  # U+0029 Right parenthesis
    "]",  # U+005D Right square bracket
    "}",  # U+007D Right curly bracket
    "\u300D",  # Corner bracket
    "\u300F",  # White corner bracket
    "\u3011",  # Black lenticular bracket
    "\uFF09",  # Fullwidth right parenthesis
)

escaped_bracket = "".join(re.escape(char) for char in open_brackets + close_brackets)

search_anime_query = """
query (
  $page: Int = 1
  $perPage: Int = 10
  $search: String
) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      total
      perPage
      currentPage
      lastPage
      hasNextPage
    }
    media(
      search: $search
      type: ANIME
    ) {
      id
      title {
        userPreferred
        romaji
        english
        native
      }
      startDate {
        year
        month
        day
      }
      endDate {
        year
        month
        day
      }
      bannerImage
      season
      seasonYear
      description
      type
      format
      status(version: 2)
      episodes
      duration
      chapters
      volumes
      genres
      isAdult
      averageScore
      popularity
    }
  }
}
"""


def load_update() -> None:
    global last_check, redirect
    # get the GitHub commit link
    for commit_type, commit_link in CONFIG["github_commit"].items():
        try:
            commit = requests.get(commit_link)
            relative_file_path = CONFIG["file_path"][commit_type]
            if commit.status_code == 200:
                latest = commit_link.json()[0]['commit']['author']['date']
                # if the file is updated, download the file
                if latest != last_check.get(commit_type, None):
                    last_check[commit_type] = latest
                    new_data = requests.get(CONFIG["file_link"][commit_type]).content
                    os.makedirs("/".join(relative_file_path.split("/")[:-1]), exist_ok=True)
                    with open(relative_file_path, 'wb+') as outfile:
                        outfile.write(new_data)
        except Exception:
            pass

    try:
        relation_file_path = CONFIG["file_path"]["anime_relation"]
        # if we successfully get the commit, check if the file is updated
        # load the localized anime relation file
        redirect = helper.parse_anime_relations(relation_file_path, CONFIG["source_api"])
    except FileNotFoundError:
        redirect = {}


@functools.lru_cache(maxsize=CONFIG["mem_cache_size"])
def search_anime_info_anilist(title, *args, **kwarg):
    try:
        variable = {
            "page": 1,
            "perPage": 1000,
            "search": title
        }

        res = instance.search.custom_query(variable, search_anime_query, *args, **kwarg)
        if res is None:
            return []
        if res.get("errors", None):
            logger.error(res['errors'])
            return []
        return res["data"]["Page"]["media"]
    except Exception as e:
        logger.error(f"Error while searching anime info {title}: {e}")
    return []


@functools.lru_cache(maxsize=CONFIG["mem_cache_size"])
def get_anime_info_anilist(anime_id):
    if not anime_id:
        return None
    try:
        result = instance.get.anime(anime_id, is_adult=None)
        if result.get("errors", None):
            logger.error(result['errors'])
            return []
        return result["data"]["Media"]
    except Exception as e:
        logger.error(f"Error while getting anime info {anime_id}: {e}")
    return None


@devlog.log_on_error(trace_stack=True)
def anime_check(anime: dict, offline: bool = False):
    search = anime['anime_title']

    is_part = re.match(r'^(part \d)', anime.get("episode_title", ""), flags=re.IGNORECASE)
    if is_part:
        search += f' {is_part.group(1)}'

    # remove double spaces
    search = re.sub(r'\s+', ' ', search).strip(" _-.&+,|")

    # convert to lower character, since it doesn't affect the search
    search = search.lower()
    # get all data
    anime, db_result = helper.anime_season_relation(anime)
    if offline:
        result = {
            "id": db_result or 0
        }
        results = []
    elif db_result:
        result = get_anime_info_anilist(db_result) or {}
        result["id"] = db_result
        results = []
    else:
        # we cant properly track if it OP/ED.
        if isinstance(anime.get("anime_type", None), list):
            for anime_type in anime.get("anime_type", []):
                if anime_type.startswith(("opening", "ending")):
                    anime["verified"] = True
                    return anime
        elif anime.get("anime_type", "").startswith(("opening", "ending")):
            anime["verified"] = True
            return anime

        results = search_anime_info_anilist(search)
        if len(results) == 0:
            if search.endswith("sp"):
                search = search[:-2] + "special"
                results = search_anime_info_anilist(search)
                if len(results) == 0:
                    search += "s"
                    results = search_anime_info_anilist(search)
        compared_search = re.sub(r"([^\w+])+", '', search)
        compared_search = re.sub(r'\s+', '', compared_search).strip(" _-.&+,|")
        if len(results) == 1:
            # if the result is only one, then we can assume it is the correct anime
            candidate = (0, 1.0)  # index, score
            synonyms = (0, 1.0)  # index, score
        else:
            candidate = (0, 0)  # index, score
            synonyms = (0, 0)  # index, score

            for index, result in enumerate(results):
                if anime.get("anime_year", False):
                    result_year = result["seasonYear"]
                    if result_year is None:
                        if result["startDate"]["year"] is not None:
                            result_year = result["startDate"]["year"]
                        else:
                            result_year = result["endDate"]["year"]

                    # we detect the year in anime title, then we focused one year behind and one year ahead
                    if not (int(anime.get("anime_year", 0)) - 1 <=
                            (result_year or -2) <=
                            int(anime.get("anime_year", 9999)) + 1):
                        continue

                for title in result["title"].values():
                    # some anime doesn't have english title
                    if title is None:
                        # https://anilist.co/anime/8440/Black-Lagoon-Omake/
                        # https://anilist.co/anime/139630/Boku-no-Hero-Academia-6/
                        # https://anilist.co/anime/20767/Date-A-Live-II-Kurumi-Star-Festival/
                        continue

                    # remove anything inside bracket, e.g. Hunter x Hunter (2011)
                    title = re.sub(r"[(\[{].*?[)\]}]|[-:]", ' ', title)

                    # remove any spaces in search
                    compared_title = re.sub(r"([^\w+])+", '', title)
                    compared_title = re.sub(r'\s+', '', compared_title).strip(" _-.&+,|").lower()

                    ratio = SequenceMatcher(None, compared_search, compared_title).ratio()
                    if ratio > candidate[1]:
                        candidate = (index, ratio)
                        # we found the anime
                        if ratio == 1.0:
                            break
                else:
                    for synonym in result.get("synonyms", []):
                        # remove anything inside bracket, e.g. Hunter x Hunter (2011)
                        synonym = re.sub(r"[(\[{].*?[)\]}]|[-:]", ' ', synonym)

                        # remove any spaces in search
                        compared_synonym = re.sub(r"([^\w+])+", '', synonym)
                        compared_synonym = re.sub(r'\s+', '', compared_synonym).strip(" _-.&+,|").lower()

                        ratio = SequenceMatcher(None, compared_search, compared_synonym).ratio()
                        if ratio > synonyms[1]:
                            synonyms = (index, ratio)
                    continue
                break
        # if the result is not found, then try checking the synonyms
        if candidate[1] < 0.95:
            # if the result still below 0.95 after checking synonyms, then return
            if synonyms[1] < 0.95:
                if not (anime.get("anime_season") and results):
                    anime["anime_type"] = "torrent"
                    return anime
                candidate = candidate if candidate[1] > synonyms[1] else synonyms
            else:
                candidate = synonyms

        # we have a candidate for the first season of the anime
        result = results[candidate[0]]

        # if the anime season greater than 1, then we need to check the second season
        if (int(anime.get("anime_season", 1)) != 1 and
                len(results) > 1):
            season = int(anime.get("anime_season", 1))
            for result in results:
                if anime.get("anime_year", False):
                    # we have the anime year candidate
                    if result.get("seasonYear") != anime.get("anime_year", False):
                        continue
                # attempt to retrieve from the description
                # if the description is none, then skip it
                if result["description"] is not None:
                    if f"{num2words(season, to='ordinal')} season" in result["description"].lower():
                        # https://anilist.co/anime/114233/Gundam-Build-Divers-ReRISE-2nd-Season/
                        # https://anilist.co/anime/20723/Yowamushi-Pedal-GRANDE-ROAD
                        break
                    elif f"after the {num2words(max(season - 1, 0), to='ordinal')} season" in result[
                        "description"].lower():
                        # https://anilist.co/anime/14693/Yurumates-3D-Plus
                        break
                    elif f"after season {num2words(max(season - 1, 0), to='cardinal')}" in result[
                        "description"].lower():
                        # https://anilist.co/anime/558/Major-S2
                        break
                    elif f"of the {num2words(max(season - 1, 0), to='ordinal')} season" in result[
                        "description"].lower():
                        # https://anilist.co/anime/21856/Boku-no-Hero-Academia-2/
                        break

                # attempt to retrieve from the title
                for title in list(result["title"].values()):
                    if title is None:
                        continue

                    # remove double spaces
                    title = re.sub(r'\s+', ' ', title).rstrip(" _-.&+,|")
                    if search == title:
                        # this is the first season, so skip it
                        continue

                    parsed_title, _ = parsing(f"{title} - 05.mkv", False)
                    if parsed_title.get("anime_season", False) == season:
                        # it the part of the season
                        if parsed_title.get("episode_title") and is_part:
                            if parsed_title.get("episode_title").lower() == is_part.group(1).lower():
                                break
                            else:
                                continue
                        # we found it
                        break

                    # if the title ends with the season number but not the part, then skip it
                    if title.endswith(str(season)) and not title.endswith(f"part {season}"):
                        break
                else:
                    continue
                break
            else:
                # after checking all the results, we still can't find the correct season
                return anime
    if isinstance(anime.get('episode_number', 0), list):
        anime_ids = []
        for idx, episode in enumerate(anime.get('episode_number', [])):
            anime_ids.append(result["id"])
            (show_id, ep) = (result['id'], int(episode))
            temp = helper.redirect_show((show_id, ep), redirect)
            (anime_ids[idx], anime['episode_number'][idx]) = temp[0], temp[1]
        if len(set(anime_ids)) == 1:
            anime['anilist'] = anime_ids[0]
        else:
            logger.error('Multiple anime ids found for %s', anime)
            return anime
    # looking is the anime are continuing episode or not
    else:
        (show_id, ep) = (result['id'], int(anime.get('episode_number', 0)))
        temp = helper.redirect_show((show_id, ep), redirect)
        (anime['anilist'], anime['episode_number']) = temp[0], temp[1]

    if offline:
        anime["verified"] = True
        return anime

    # if the anime are continuing episode, then we need to get the correct season info
    if result['id'] != anime['anilist'] and not offline:
        for result in results:
            if result['id'] == anime['anilist']:
                break
        else:
            result = get_anime_info_anilist(anime['anilist'])
            if result is None:
                anime["anilist"] = 0
                return anime
    # assign the correct anime info based on the config
    anime['anime_title'] = result.get("title", {}).get(CONFIG["title"], anime['anime_title'])
    anime["anime_year"] = result.get('seasonYear', None)
    if anime["anime_year"] is None:
        if result.get("startDate", {}).get("year") is not None:
            anime["anime_year"] = result.get("startDate", {}).get("year")
        else:
            anime["anime_year"] = result.get("endDate", {}).get("year")
    anime["anime_year"] = anime["anime_year"] if anime["anime_year"] else None
    # threat tv short as the same as tv (tv short mostly anime less than 12 minutes)
    if not offline:
        anime["anime_type_filename"] = anime.get("anime_type", None)
        anime["anime_type"] = 'TV' if result.get("format", "") == 'TV_SHORT' else result.get("format", "torrent")
    anime["verified"] = True
    return anime


def track(anime_filepath, is_folder=False, offline=False):
    # check update the anime relation file.
    # only executed once per day
    global instance, redirect, last_day_check
    if not offline:
        if date.today().day != last_day_check or redirect is None:
            load_update()
            last_day_check = date.today().day

    folder_path, anime_filename = os.path.split(anime_filepath)  # type: str, str
    try:
        anime, fails = parsing(anime_filename, is_folder)
        anime["verified"] = False

        if fails:
            logger.error(f"Failed to parse {anime_filename}")
            return return_formatter(anime)

        if isinstance(anime.get("anime_title", False), list):
            logger.error(f"Multiple anime found for {anime_filename}")
            return return_formatter(anime)

        if isinstance(anime.get("episode_number", False), list):
            # probably an episode batch where it concat the same arc
            logger.debug(f"Multiple episode number found for {anime_filename} {anime['episode_number']}")
            number = anime['episode_number']
            for idx, episode_number in enumerate(number):
                # ignore if the anime are recap episode, usually with float number
                try:
                    if not float(episode_number).is_integer():
                        return return_formatter(anime)
                except TypeError as e:
                    # no folder detection yet
                    # if not folder_path:
                    logger.error(f"Failed to parse {anime_filename} episode {episode_number} with error {e}")
                    return return_formatter(anime)
                    # else:
                    #     anime = parsing(folder_path, is_folder=True)
                    # # multiple episodes detected, probably from concat episode, or batch eps
                    # # we will ignore the episode
                    # logger.info(f"{anime_filename} has multiple episodes or batch release")
                    # anime["episode_number"] = -1
        else:
            # ignore if the anime are recap episode, usually with float number
            episode_number = anime.get("episode_number", 0)
            try:
                if not float(episode_number).is_integer():
                    return return_formatter(anime)
            except TypeError as e:
                # no folder detection yet
                # if not folder_path:
                logger.error(f"Failed to parse {anime_filename} episode {episode_number} with error {e}")
                return return_formatter(anime)
                # else:
                #     anime = parsing(folder_path, is_folder=True)
                # # multiple episodes detected, probably from concat episode, or batch eps
                # # we will ignore the episode
                # logger.info(f"{anime_filename} has multiple episodes or batch release")
                # anime["episode_number"] = -1

        # check if we detect multiple anime season
        if isinstance(anime.get('anime_season'), list):
            # if the anime season only consist of two element,
            # we could try to guess the season.
            # Usually the first are season and the second are part of the season (e.g. s2 part 1, s2 part 2)
            if len(anime.get('anime_season', [])) == 2:
                logger.debug(f"Multiple anime season found for {anime_filename}")
                number = int(anime['anime_season'][0])
                if number == 0:
                    anime['anime_type'] = "torrent"
                else:
                    # Aniparse very unlikely to miss detect the part <number> as season.
                    # This is most likely a multiple season stuff, e.g `S03E13 ... (S03E12 part 2)`
                    # anime["anime_title"] += f" part {anime['anime_season'][1]}"
                    anime['anime_season'] = number
            else:
                logger.error(f"Confused about this anime season\n{anime}")
                return return_formatter(anime)

        elif int(anime.get('anime_season', -1)) == 0:
            if not offline:
                anime['anime_type'] = "torrent"
            logger.error(f"Anime with 0 season found \n{anime}")


        if (anime.get('file_extension', '') in CONFIG["valid_ext"] or
                is_folder):
            # this anime is not in ignored type and not episode with comma (recap eps)
            # attempt to parse from the title
            if anime.get("anime_title", None):
                anime = anime_check(anime, offline)
            else:
                logger.error(f"Anime title not found\n{anime}")
                return return_formatter(anime)
            # no folder detection added yet.
            # guess = anime.copy()
            # while anime.get("anime_type", None) == "torrent":
            #     # attempt to parse from the folder name
            #     # look up to 2 level above
            #     for path in paths[:-3:-1]:
            #         guess_title = parsing(path, is_folder)
            #         if guess_title.get("anime_title", "None").lower() in CONFIG["folder_blacklist"]:
            #             continue
            #         guess["anime_title"] = guess_title["anime_title"]
            #         anime = anime_check(guess)
            #         break
            #     break
            # if guess.get("anime_type", None) != "torrent":
            #     return guess
        if anime.get("anime_type", None) != "torrent" and anime.get("anilist", 0) == 0 and not offline:
            logger.error(f"anime type was not torrent but the id 0 \n{anime}")
            anime["anime_type_filename"] = anime["anime_type"]
            anime["anime_type"] = "torrent"
        return return_formatter(anime)
    except Exception as e:
        logger.error(f"Failed to parse {anime_filepath} with error {e}")

        return return_formatter({
            "anime_title": anime_filename,
            "anime_type": "torrent",
            "verified": False,
            "anilist": 0,
            "isFolder": is_folder,
            "isExtras": False
        })


def parsing(filename, is_folder=False) -> tuple[dict, bool]:
    """
    Parsing the filename and return the anime information
    :param filename:
    :param is_folder:
    :returns: {
        anime_title,
        anime_type = str("tv" | "movie" | "ova" | "ona" | "special" | "torrent" | "ending/opening [int]"),
        file_extension,
        anime_id = int(0),
        isFolder = is_folder,
        isExtras = False,
        ...
    }, bool(is_fails)

    """
    original_filename = filename

    # clean up the plural anime types in the filename
    filename = re.sub(r'\b(?:oads?|oavs?|ovas?)(?:[^A-Z0-9a-z' + escaped_bracket + r']{0,4}(\d+))?\b',
                      r'ova\1', filename, flags=re.IGNORECASE)

    filename = re.sub(r'\bspecials?\b', 'special', filename, flags=re.IGNORECASE)

    # remove double spaces
    filename = re.sub(r'\s+', ' ', filename)

    # parse the filename
    try:
        anime = aniparse.parse(filename)
    except Exception as e:
        logger.error(f"Error parsing {filename}\n{e}")
        anime = {
            "anime_title": "",
            "anime_type": "torrent",
            "anilist": 0,
            "isFolder": is_folder,
            "isExtras": False,
        }
        return anime, True
    anime["file_name"] = original_filename

    # check if it parsed correctly
    if (anime.get("anime_title", "") == ""):
        return anime, True

    # remove everything in bracket from the title, (Reconsider again)
    anime_name = re.sub(r"[(\[{].*?[)\]}]", ' ', anime['anime_title'])
    if anime_name != anime['anime_title']:
        logger.debug(f"Removed {anime['anime_title']} from {anime_name}")
    # remove floating dashes
    anime_name = re.sub(r'[^A-Z0-9a-z][-:][^A-Z0-9a-z]', ' ', anime_name)
    anime_name = re.sub(r'\s+', ' ', anime_name).lower()

    # Filling the anime information with cleaned up title and default values if not exist
    anime["anime_title"] = anime_name.strip(" _-.&+,|")
    anime['anime_type'] = anime.get("anime_type", "torrent")
    anime["anilist"] = 0
    anime["isFolder"] = is_folder
    anime["isExtras"] = False

    if is_folder:
        # what do we need to remove?
        anime.pop("episode_number", None)
        anime.pop("anime_season", None)

    # Check if the anime is extra_type
    if not is_folder and isinstance(anime.get("anime_type", None), str):
        anime, anime_type = normalize_anime_format_type(anime, anime.get("anime_type", ""), filename)
        anime["anime_type"] = anime_type

    if not is_folder and isinstance(anime.get("anime_type", None), list):
        # make a set of the anime_type, case-insensitive
        anime_types = list(set([x.lower() for x in anime.get("anime_type", [])]))

        format_type = [ft for ft in anime_types if ft.lower() in ['tv', 'gekijouban', 'special', 'sp',
                                                                  'ova', 'movie', 'special', 'ona']]
        extra_type = [et for et in anime_types if et.lower() in CONFIG["extra_type"]]
        unknown_type = [ut for ut in anime_types if ut.lower() not in format_type + extra_type]
        if unknown_type:
            logger.warning(f"Unknown anime type {unknown_type} in {original_filename}")
        if len(format_type) != 1 or len(extra_type) > 1 or unknown_type:
            logger.warning(f"multiple format type or extra type\n{anime}")
            anime["anime_type"] = "torrent"
        else:
            anime_types = format_type + extra_type
            for idx, anime_type in enumerate(anime_types.copy()):
                anime, anime_typed = normalize_anime_format_type(anime, anime_type, filename)
                anime_types[idx] = anime_typed

            if len(anime_types) == 1:
                anime["anime_type"] = anime_types[0]
            else:
                anime["anime_type"] = anime_types

    return anime, False


def normalize_anime_format_type(anime, anime_type, filename):
    anime_type = anime_type.lower()
    if anime_type in CONFIG["extra_type"]:
        anime["isExtras"] = True
    # normalize the anime type for special
    if anime_type in ["special", "sp", "s"]:
        anime_type = "special"
    # normalize the anime type for movie
    elif anime_type in ['gekijouban', 'movie']:
        anime_type = "movie"
    # normalize the anime type for ending
    elif anime_type in ['ed', 'ending', 'nced', 'clean ending']:
        anime_type = "ending"
    # normalize the anime type for opening
    elif anime_type in ['op', 'opening', 'ncop', 'clean opening']:
        anime_type = "opening"

    # threat movies episode as season number,
    if anime_type == "movie":
        if anime.get("episode_number"):
            anime["anime_season"] = anime.pop("episode_number")

    return anime, anime_type


def return_formatter(anime: dict):
    if anime.get("verified", False) is False:
        anime["anime_type"] = "torrent"
    anime.pop("verified", None)
    return dict(sorted(anime.items()))
