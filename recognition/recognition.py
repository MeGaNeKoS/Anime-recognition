import functools
import os
import re
from datetime import date
from difflib import SequenceMatcher

import anitopy
import devlog
import requests
from Anisearch import Anilist
from num2words import num2words

from . import helper
# get all variable from config.py
from .config import CONFIG

instance = Anilist()

last_check = None
last_day_check = None
redirect = None

search_anime_query = """
                query ($query: String, $page: Int, $perPage: Int) {
                    Page (page: $page, perPage: $perPage) {
                        pageInfo {
                            total
                            currentPage
                            lastPage
                            hasNextPage
                        }
                        media (search: $query, type: ANIME) {
                            id
                            title {
                                romaji
                                english
                            }
                            synonyms
                            countryOfOrigin
                            format
                            status
                            episodes
                            duration
                            startDate {
                                year
                            }
                            endDate {
                                year
                            }
                            season
                            seasonYear
                            isAdult
                            genres
                            averageScore
                            meanScore
                            hashtag
                            bannerImage                            
                            description
                            }
                    }
                }
            """
get_anime_query = """
                query ($id: Int) {
                    Media(id: $id, type: ANIME) {
                        title {
                            romaji
                            english
                        }
                        bannerImage
                        format
                        status
                        episodes
                        duration
                        startDate {
                            year
                        }
                        endDate {
                            year
                        }
                        season
                        seasonYear
                        isAdult
                        genres
                        countryOfOrigin
                        description
                        averageScore
                        meanScore
                        synonyms
                    }
                }
            """


def load_update():
    global last_check, redirect
    # get the GitHub commit link
    commit = requests.get(CONFIG["commit_link"])
    relation_file_path = CONFIG["relation_file_path"]
    # if we successfully get the commit, check if the file is updated
    if commit.status_code == 200:
        latest = commit.json()[0]['commit']['author']['date'].split("T")[0]
        # if the file is updated, download the file
        if latest is not last_check:
            last_check = latest
            new_anime_relation = requests.get(CONFIG["file_link"]).content
            os.makedirs("/".join(relation_file_path.split("/")[:-1]), exist_ok=True)
            with open(relation_file_path, 'wb') as outfile:
                outfile.write(new_anime_relation)
    # load the localized anime relation file
    redirect = helper.parse_anime_relations(relation_file_path, CONFIG["source_api"])


@functools.lru_cache(maxsize=10)
def search_anime_info_anilist(title, *args, **kwarg):
    variables = {"query": title, "page": 1, "perPage": 10}
    return instance.search.custom_query(variables, search_anime_query, *args, **kwarg)


@functools.lru_cache(maxsize=10)
def get_anime_info_anilist(anime_id):
    variables = {"id": anime_id}
    result = instance.search.custom_query(variables, get_anime_query)
    return result["data"]["Media"]


@devlog.log_on_error(trace_stack=True)
def anime_check(anime: dict, is_folder: bool = False):
    # remove non-alphanumeric characters
    # search = re.sub(r"([^\w+])+", ' ', anime['anime_title'])
    search = anime['anime_title']
    is_part = re.match(r'^(part \d)', anime.get("episode_title", ""), flags=re.IGNORECASE)
    if is_part:
        search += f' {is_part.group(1)}'

    # remove double spaces
    search = re.sub(r'\s+', ' ', search).strip()

    # convert to lower character, since it doesnt affect the search
    search = search.lower()
    # get all data
    db_result = helper.anime_season_relation(anime)
    if db_result:
        result = get_anime_info_anilist(db_result)
        result["id"] = db_result
        results = []
    else:
        compared_search = re.sub(r"([^\w+])+", '', search)
        compared_search = re.sub(r'\s+', '', compared_search).strip()
        data = search_anime_info_anilist(search)
        results = data['data']['Page']['media']
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
                if not (int(anime.get("anime_year", False)) - 1 <=
                        (result_year or -2) <=
                        int(anime.get("anime_year", 9999)) + 1):
                    continue

            for title in result["title"].values():                # some anime doesn't have english title
                if title is None:
                    # https://anilist.co/anime/8440/Black-Lagoon-Omake/
                    # https://anilist.co/anime/139630/Boku-no-Hero-Academia-6/
                    # https://anilist.co/anime/20767/Date-A-Live-II-Kurumi-Star-Festival/
                    continue

                # remove anything inside bracket, e.g. Hunter x Hunter (2011)
                title = re.sub(r"[(\[{].*?[)\]}]|[-:]", ' ', title)

                # remove non-alphanumeric characters
                # review later for nisekoi:, okusama ga saitokaichou!+!
                compared_title = re.sub(r"([^\w+])+", '', title)

                # remove any spaces in search
                compared_title = re.sub(r'\s+', '', compared_title).strip()  # To love Ru

                ratio = SequenceMatcher(None, compared_search, compared_title.lower()).ratio()
                if ratio > candidate[1]:
                    candidate = (index, ratio)
                    # we found the anime
                    if ratio == 1.0:
                        break
            else:
                for synonym in result["synonyms"]:
                    # remove anything inside bracket, e.g. Hunter x Hunter (2011)
                    synonym = re.sub(r"[(\[{].*?[)\]}]|[-:]", ' ', synonym)

                    # remove non-alphanumeric characters
                    compared_synonym = re.sub(r"([^\w+])+", '', synonym)

                    # remove any spaces in search
                    compared_synonym = re.sub(r'\s+', '', compared_synonym).strip()  # To love Ru

                    ratio = SequenceMatcher(None, compared_search, compared_synonym.lower()).ratio()
                    if ratio > synonyms[1]:
                        synonyms = (index, ratio)
                continue
            break
        # if the result is not found, then try checking the synonyms
        if candidate[1] < 0.95:
            # if the result still below 0.95 after checking synonyms, then return
            if synonyms[1] < 0.95:
                anime["anime_type"] = "torrent"
                return anime
            else:
                candidate = synonyms

        # we have a candidate for the first season of the anime
        result = results[candidate[0]]

        # if the anime season greater than 1, then we need to check the second season
        if int(anime.get("anime_season", 1)) > 1:
            first_season = result["title"]["romaji"].lower()
            season = int(anime.get("anime_season", 1))
            for result in results:
                if anime.get("anime_year", False):
                    # we have the anime year candidate
                    if str(result.get("seasonYear")) != anime.get("anime_year", False):
                        continue
                # attempt to retrieve from the description
                # if the description is none, then skip it
                if result["description"] is not None:
                    if f"{num2words(season, to='ordinal')} season" in result["description"].lower():
                        # https://anilist.co/anime/114233/Gundam-Build-Divers-ReRISE-2nd-Season/
                        # https://anilist.co/anime/20723/Yowamushi-Pedal-GRANDE-ROAD
                        break
                    elif f"after the {num2words(season - 1, to='ordinal')} season" in result["description"].lower():
                        # https://anilist.co/anime/14693/Yurumates-3D-Plus
                        break
                    elif f"after season {num2words(season - 1, to='cardinal')}" in result["description"].lower():
                        # https://anilist.co/anime/558/Major-S2
                        break
                    elif f"of the {num2words(season - 1, to='ordinal')} season" in result["description"].lower():
                        # https://anilist.co/anime/21856/Boku-no-Hero-Academia-2/
                        break

                # attempt to retrieve from the title
                for title in list(result["title"].values()):
                    # remove non-alphanumeric characters
                    if title is None:
                        continue
                    title = re.sub(r"([^\w+])+", ' ', title)
                    title = re.sub(r'\s+', ' ', title).rstrip()
                    if search.lower() == str(title).lower():
                        continue
                    # the title ends with season number
                    elif title.lower().endswith(str(season)):
                        # https://anilist.co/anime/14397/Chihayafuru-2/
                        # https://anilist.co/anime/21004/Kaitou-Joker-2/
                        # https://anilist.co/anime/21856/Boku-no-Hero-Academia-2/
                        # https://anilist.co/anime/100280/Star-Mu-3/
                        # https://anilist.co/anime/12365/Bakuman-3/
                        break
                    # if the title ends with the season number
                    elif f"season {season}" in title.lower():
                        # https://anilist.co/anime/122808/Princess-Connect-ReDive-Season-2/
                        break
                    elif f"{num2words(season, to='ordinal')} season" in title.lower():
                        # https://anilist.co/anime/100133/One-Room-Second-Season/
                        # https://anilist.co/anime/21085/Diamond-no-Ace-Second-Season/
                        # https://anilist.co/anime/2014/Taiho-Shichauzo-SECOND-SEASON/
                        # https://anilist.co/anime/17074/Monogatari-Series-Second-Season/
                        break
                    # if the title has `ordinal number season` in it
                    elif f"{num2words(season, to='ordinal_num')} season" in title.lower():
                        # https://anilist.co/anime/10997/Fujilog-2nd-Season/
                        # https://anilist.co/anime/101633/BanG-Dream-2nd-Season/
                        # https://anilist.co/anime/9656/Kimi-ni-Todoke-2nd-Season/
                        # https://anilist.co/anime/20985/PriPara-2nd-Season/
                        # https://anilist.co/anime/97665/Rewrite-2nd-Season/
                        # https://anilist.co/anime/21559/PriPara-3rd-Season/
                        # https://anilist.co/anime/101634/BanG-Dream-3rd-Season/
                        break
                    # if the title has `episode title` in it.
                    elif anime.get("episode_title", None) and anime.get("episode_title",
                                                                        None).lower() in title.lower():
                        break
                else:
                    continue
                break

    # looking is the anime are continuing episode or not
    (show_id, ep) = (result['id'], int(anime.get('episode_number', 0)))
    (anime['anilist'], anime['episode_number']) = helper.redirect_show((show_id, ep), redirect)

    # if the anime are continuing episode, then we need to get the correct season info
    if result['id'] != anime['anilist']:
        for result in results:
            if result['id'] == anime['anilist']:
                break
        else:
            result = get_anime_info_anilist(anime['anilist'])

    # assign the correct anime info based on the config
    anime['anime_title'] = result['title'][CONFIG["title"]]
    anime["anime_year"] = result['seasonYear']
    if anime["anime_year"] is None:
        if result["startDate"]["year"] is not None:
            anime["anime_year"] = result["startDate"]["year"]
        else:
            anime["anime_year"] = result['startDate']['year']
    anime["anime_year"] = str(anime["anime_year"]) if anime["anime_year"] else None  # convert to string if not None
    # threat tv short as the same as tv (tv short mostly anime less than 12 minutes)
    anime["anime_type"] = 'TV' if result['format'] == 'TV_SHORT' else result['format']
    return anime


@devlog.log_on_error(trace_stack=True)
def track(anime_filepath, is_folder=False):
    # check update the anime relation file.
    # only executed once per day
    global instance, redirect, last_day_check
    if date.today().day != last_day_check or redirect is None:
        load_update()
        last_day_check = date.today().day

    # we expected to get the anime filepath
    folder_path, anime_filename = os.path.split(anime_filepath)  # type: str, str

    # the last element is the anime filename
    anime = parsing(anime_filename, is_folder)

    if anime.get("anime_type", "").lower() in CONFIG["ignored_type"]:
        # remove the anime_type from the title
        anime["anime_title"] = re.sub(r'\b' + anime.get("anime_type", "").lower() + r'\b', '', anime["anime_title"],
                                      flags=re.IGNORECASE)
        # remove the episode number
        anime.pop("episode_number", None)
        # this is an extras. So, put it inside extras folder related to the anime
        anime["anime_extras"] = True
        is_folder = True
    # ignore if the anime are recap episode, usually with float number
    try:
        if not float(anime.get("episode_number", 0)).is_integer():
            return anime
    except TypeError:
        # no folder detection yet
        # if not folder_path:
        return anime
        # else:
        #     anime = parsing(folder_path, is_folder=True)
        # # multiple episodes detected, probably from concat episode, or batch eps
        # # we will ignore the episode
        # CONFIG["logger"].info(f"{anime_filename} has multiple episodes or batch release")
        # anime["episode_number"] = -1

    # check if we detect multiple anime season
    if isinstance(anime.get('anime_season'), list):
        # if the anime season only consist of two element,
        # we could try to guess the season.
        # Usually the first are season and the second are part of the season (e.g. s2 part 1, s2 part 2)
        if len(anime.get('anime_season', [])) == 2:
            number = int(anime['anime_season'][0])
            if number == 0:
                anime['anime_type'] = "torrent"
            else:
                anime["anime_title"] += f" {num2words(number, to='ordinal_num')} season"
                anime['anime_season'] = anime['anime_season'][1]
        else:
            CONFIG["logger"].info(f"Confused about this anime \n{anime}")
            return anime

    elif int(anime.get('anime_season', -1)) == 0:
        anime['anime_type'] = "torrent"
        CONFIG["logger"].info(f"Anime with 0 season found \n{anime}")

    if anime["anime_title"] in anime.get("episode_title", '') or \
            anime.get("episode_title", '').lower() == "end":  # usually last eps from Erai-raws release
        try:
            del anime["episode_title"]
        except KeyError:
            pass

    if (anime.get('file_extension', '') in CONFIG["valid_ext"] or
            is_folder):
        # this anime is not in ignored type and not episode with comma (recap eps)

        # attempt to parse from the title
        if anime.get("anime_title", None):
            anime = anime_check(anime, is_folder)
        else:
            CONFIG["logger"].info(f"Confused about this anime \n{anime}")
            return anime
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
    return anime


def parsing(filename, is_folder):
    # make sure the version number has space before it
    filename = re.sub(r'(\d+)v(\d+)', r'\1 v\2 ', filename)
    filename = re.sub(r'\boads?\b', 'ova', filename, flags=re.IGNORECASE)
    filename = re.sub(r'\boavs?\b', 'ova', filename, flags=re.IGNORECASE)
    filename = re.sub(r'\b&\b', 'and', filename, flags=re.IGNORECASE)
    # filename = re.sub(r'\bthe animation\b', '', filename, flags=re.IGNORECASE)
    # filename = re.sub(r'\bthe\b', '', filename, flags=re.IGNORECASE)
    # filename = re.sub(r'\bepisode\b', '', filename, flags=re.IGNORECASE)
    filename = re.sub(r'\bspecials?\b', 'special', filename, flags=re.IGNORECASE)

    anime = anitopy.parse(filename)
    # remove everything in bracket from the title
    anime_name = re.sub(r"[(\[{].*?[)\]}]|[-:]", ' ', anime['anime_title'])
    # replace any non-alphanumeric character with space and convert to lower case
    anime_name = re.sub(r'[^A-Za-z\d]+', ' ', anime_name).lower()
    # by default, all anime will treat as unknown type
    anime["anime_title"] = anime_name.strip()
    anime['anime_type'] = anime.get("anime_type", "torrent")
    anime["anilist"] = 0
    anime["isFolder"] = is_folder
    return anime


load_update()
