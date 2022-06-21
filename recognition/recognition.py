import functools
import logging
import os
import re
from datetime import date

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


def load_update():
    global last_check, redirect
    # get the GitHub commit link
    commit = requests.get(CONFIG["link"])
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
    return instance.search.anime(title, *args, **kwarg)


@functools.lru_cache(maxsize=10)
def get_anime_info_anilist(anime_id):
    result = instance.get.anime(anime_id)
    return result["data"]["Media"]


def result_parser(anime, season, search, results):
    # attempt to guess the correct anime
    # if the anime description says x season of, after season x, of the x season,
    season_year = 0  # use on guessing by anime publish order
    candidate = None

    for result in results:
        if anime.get("anime_year", False):
            if str(result.get("seasonYear")) != anime.get("anime_year", False):
                continue
        # attempt to retrieve from the description
        # if the description is none, then skip it
        if result["description"] is not None:
            if f"{num2words(season, to='ordinal')} season" in result["description"].lower():
                # https://anilist.co/anime/114233/Gundam-Build-Divers-ReRISE-2nd-Season/
                # https://anilist.co/anime/20723/Yowamushi-Pedal-GRANDE-ROAD
                return False, result
            elif f"after the {num2words(season - 1, to='ordinal')} season" in result["description"].lower():
                # https://anilist.co/anime/14693/Yurumates-3D-Plus
                return False, result
            elif f"after season {num2words(season - 1, to='cardinal')}" in result["description"].lower():
                # https://anilist.co/anime/558/Major-S2
                return False, result
            elif f"of the {num2words(season - 1, to='ordinal')} season" in result["description"].lower():
                # https://anilist.co/anime/21856/Boku-no-Hero-Academia-2/
                return False, result

        # attempt to retrieve from the title
        for title in list(result["title"].values()):
            # remove non-alphanumeric characters
            if title is None:
                continue
            title = re.sub(r"([^\w+])+", ' ', title)
            title = re.sub(r'\s+', ' ', title).rstrip()
            if search.lower() == str(title).lower():
                return False, result
            # the title ends with season number
            elif title.lower().endswith(str(season)):
                # https://anilist.co/anime/14397/Chihayafuru-2/
                # https://anilist.co/anime/21004/Kaitou-Joker-2/
                # https://anilist.co/anime/21856/Boku-no-Hero-Academia-2/
                # https://anilist.co/anime/100280/Star-Mu-3/
                # https://anilist.co/anime/12365/Bakuman-3/
                return False, result
            # if the title ends with the season number
            elif f"season {season}" in title.lower():
                # https://anilist.co/anime/122808/Princess-Connect-ReDive-Season-2/
                return False, result
            elif f"{num2words(season, to='ordinal')} season" in title.lower():
                # https://anilist.co/anime/100133/One-Room-Second-Season/
                # https://anilist.co/anime/21085/Diamond-no-Ace-Second-Season/
                # https://anilist.co/anime/2014/Taiho-Shichauzo-SECOND-SEASON/
                # https://anilist.co/anime/17074/Monogatari-Series-Second-Season/
                return False, result
            # if the title has `ordinal number season` in it
            elif f"{num2words(season, to='ordinal_num')} season" in title.lower():
                # https://anilist.co/anime/10997/Fujilog-2nd-Season/
                # https://anilist.co/anime/101633/BanG-Dream-2nd-Season/
                # https://anilist.co/anime/9656/Kimi-ni-Todoke-2nd-Season/
                # https://anilist.co/anime/20985/PriPara-2nd-Season/
                # https://anilist.co/anime/97665/Rewrite-2nd-Season/
                # https://anilist.co/anime/21559/PriPara-3rd-Season/
                # https://anilist.co/anime/101634/BanG-Dream-3rd-Season/
                return False, result
            # if the title has `episode title` in it.
            elif anime.get("episode_title", None) and anime.get("episode_title", None).lower() in title.lower():
                return False, result

        # attempt to retrieve from the year it published
        # the result returned from anilist are sort by similarity,
        # we assume the first result is the first season
        # wrong guessing could come from here
        # it too naive, but it works for most cases
        # [ASW] 86 - Eighty Six - 21 [1080p HEVC][9D595499].mkv
        # [ASW] Digimon Adventure (2020) - 01 [1080p HEVC][2D916E78].mkv
        #
        if results[0]["title"]["romaji"] in result["title"]["romaji"]:
            season_year += 1
            # error when the result is not return the first season of that anime
            if season_year == season:
                candidate = result
    if candidate:
        return False, candidate
    return True, anime


@devlog.log_on_error(trace_stack=True)
def anime_check(anime: dict):
    # remove everything in bracket from the title
    # non-alphanumeric characters
    # and double spaces
    search = re.sub(r"[(\[{].*?[)\]}]|[-:]", ' ', anime['anime_title'])
    search = re.sub(r"([^\w+])+", ' ', search)
    search = re.sub(r'\s+', ' ', search).rstrip()
    f_search = search
    season = int(anime.get("anime_season", 1))
    if season > 1:
        f_search += f' {num2words(season, to="ordinal_num")} season'

    if (eps_title := anime.get("episode_title", '')).lower().startswith('part'):
        f_search += f' {eps_title}'

    # remove all unnecessary double spaces
    f_search = re.sub(r'\s+', ' ', f_search).rstrip()

    results = search_anime_info_anilist(f_search, per_page=100)['data']['Page']['media']

    if not results:
        results = search_anime_info_anilist(search, per_page=100)['data']['Page']['media']

    # try to guess the season
    fail, result = result_parser(anime, season, search, results)
    if fail:
        return result

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
    paths = anime_filepath.split("/")

    # the last element is the anime filename
    anime_filename = paths[-1]
    anime = parsing(anime_filename, is_folder)

    # ignore if the anime are recap episode, usually with float number
    try:
        if not float(anime.get("episode_number", 0)).is_integer():
            return anime
    except TypeError:
        if not is_folder:
            return anime
        # multiple episodes detected, probably from concat episode, or batch eps
        # we will ignore the episode
        CONFIG["logger"].info(f"{anime_filename} has multiple episodes or batch release")
        anime["episode_number"] = -1

    # check if we detect multiple anime season
    if isinstance(anime.get('anime_season'), list):
        # if the anime season only consist of two element,
        # we could try to guess the season.
        # Usually the first are season and the second are part of the season (e.g. s2 part 1, s2 part 2)
        if len(anime.get('anime_season', [])) == 2:
            number = int(anime['anime_season'][0])
            if number == 0:
                anime['anime_type'] = "0Season"
            else:
                anime["anime_title"] += f" {num2words(number, to='ordinal_num')} season"
                anime['anime_season'] = anime['anime_season'][1]
        else:
            CONFIG["logger"].info(f"Confused about this anime \n{anime}")
            return anime

    elif int(anime.get('anime_season', -1)) == 0:
        anime['anime_type'] = "0Season"

    if anime["anime_title"] in anime.get("episode_title", '') or \
            anime.get("episode_title", '').lower() == "end":  # usually last eps from Erai-raws release
        try:
            del anime["episode_title"]
        except KeyError:
            pass

    if (str(anime["anime_type"]).lower() not in CONFIG["ignored_type"] and
            float(anime.get("episode_number", 0)).is_integer() and
            anime.get('file_extension', '') in CONFIG["valid_ext"] or
            is_folder):
        # this anime is not in ignored type and not episode with comma (recap eps)

        # if the anime title in the custom db, return it mal, kitsu, anilist id instead.
        # attempt to parse from the title
        if anime.get("anime_title", None):
            anime = anime_check(anime)
        else:
            CONFIG["logger"].info(f"Confused about this anime \n{anime}")
            return anime
        guess = anime.copy()
        while anime.get("anime_type", None) == "torrent":
            # attempt to parse from the folder name
            # look up to 2 level above
            for path in paths[:-3:-1]:
                guess_title = parsing(path)
                if guess_title.get("anime_title", "None").lower() in CONFIG["folder_blacklist"]:
                    continue
                guess["anime_title"] = guess_title["anime_title"]
                anime = anime_check(guess)
                break
            break
        if guess.get("anime_type", None) != "torrent":
            return guess
    return anime


def parsing(filename, is_folder):
    anime = anitopy.parse(filename)
    # by default, all anime will treat as unknown type
    anime['anime_type'] = 'torrent'
    anime["anilist"] = 0
    anime["isFolder"] = is_folder
    return anime


load_update()
