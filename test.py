from recognition import CONFIG
from recognition import helper

helper.parse_anime_relations(CONFIG["file_path"]['anime_relation'])

import logging
from pprint import pprint

import devlog

import recognition

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
file_handler = logging.FileHandler('app.log')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

test = [
    ["[Judas] 86 - Eighty Six (2021) - E11v2.mkv", 131586],  # -> returns 116589
    # there is no way to detect this anime, both part 1 and part 2 are in the same year
    ["[ASW] 86 - Eighty Six - 21 [1080p HEVC][9D595499].mkv", 131586],
    ["[Judas] Arakawa Under The Bridge - S01E06.mkv", 7647],
    ["[Judas] Black Lagoon - S01E02.mkv", 889],
    ["[Judas] Boku no Hero Academia S2 - 05.mkv", 21856],
    ["[AnimeRG] Boku No Hero Academia - 102 (1080P 10bit) (Season 5 - 14).mkv", 117193],
    ["[Judas] Boruto - 02.mkv", 97938],  # detected using fansub relation
    ["[Judas] Card Captor Sakura - S02E12.mkv", 232],  # detected using fansub relation
    ["[Judas] Date A Live - S01E13 - OVA.mkv", 17641],
    ["[ASW] Digimon Adventure (2020) - 01 [1080p HEVC][2D916E78].mkv", 114811],
    ["[ASW] Digimon Adventure (2020) - 59 [1080p HEVC][AB3B32E3].mkv", 114811],
    ["[Judas] Digimon Adventure Tri - 01 - Reunion.mkv", 20802],  # detected using fansub relation
    ["[Judas] Digimon Adventure Tri - 02 - Determination.mkv", 21500],
    # detected using fansub relation + anime relation
    ["[Judas] Digimon Adventure Tri - 03 - Confession.mkv", 21596],  # detected using fansub relation + anime relation
    ["[Judas] Digimon Adventure Tri - 04 - Loss.mkv", 97734],  # detected using fansub relation + anime relation
    ["[Judas] Digimon Adventure Tri - 06 - Future.mkv", 100181],  # detected using fansub relation + anime relation
    ["[Judas] Enen no Shouboutai (Fire Force) S1 - 19.mkv", 105310],
    ["[ASW] Enen no Shouboutai (Fire Force) - S02E17 [1080p HEVC].mkv", 114236],
    ["[Judas] Full Metal Panic S2 - 02.mkv", 72],  # detected using fansub relation
    ["[Judas] Full Metal Panic S3 - 09.mkv", 73],  # detected using fansub relation
    ["[Judas] Full Metal Panic S3 - Special 01.mkv", 1015],  # detected using fansub relation
    ["[ASW] Genjitsu Shugi Yuusha no Oukoku Saikenki - 14 [1080p HEVC][3E22FEDD].mkv", 139648],
    # Undetected due to a token between the season and episode
    ["[zza] Gundam Build Divers - S02 - Re-Rise - Part 1 - 01 [1080p.x265].mkv", 110786],
    ["[zza] Gundam Build Divers - S02 - Re-Rise - Part 2 - 01 [1080p.x265].mkv", 114233],
    ["[Judas] Honzuki no Gekokujou S1 - 01.mkv", 108268],  # detected using fansub relation
    ["[Rom & Rem] Honzuki no Gekokujou - 01 [Web][H265][10bits][1080p][AAC].mkv", 108268],
    # detected using fansub relation
    ["[Judas] Honzuki no Gekokujou (Ascendance of a Bookworm) - S03E09.mkv", 121176],  # detected using fansub relation
    ["[Judas] Kakegurui - S01E01.mkv", 98314],
    ["[BlueLobster] Kanokon - 07 [480p].mkv", 3503],
    ["[Judas] Kimi no Na Wa. (Your Name.) [BD 2160p 4K UHD][HEVC x265 10bit][Dual-Audio][Multi-Subs].mkv", 21519],
    ["[Judas] Kuma Kuma Kuma Bear - S00E09.mkv", 124896],  # detected using fansub relation
    ["[Judas] Mahouka S1 - 13.mkv", 20458],  # too ambiguous, detected using fansub relation
    ["[ASW] Night Head 2041 - 06 [1080p HEVC][3438AFC9].mkv", 125868],
    ["[Judas] Nogizaka Haruka no Himitsu - S01E03.mkv", 3467],
    ["[Judas] Ore dake Haireru Kakushi Dungeon - S01E08.mkv", 118375],
    ["[Judas] Psycho-Pass S2 - 01.mkv", 20513],
    ["[Judas] Re.Zero kara Hajimeru Isekai Seikatsu - S02E18.mkv", 119661],
    ["[Erai-raws] Re.Zero kara Hajimeru Isekai Seikatsu 2nd Season Part 2 - 12 END [1080p HEVC][Multiple Subtitle].mkv",
     119661],
    ["[ASW] The Daily Life of the Immortal King - 01 [1080p HEVC][EC9BA489].mkv", 114121],
    ["[Rom & Rem] Tate no Yuusha no Nariagari S2 - 12 [Web][H265][10bits][1080p][AAC] (Modified subtitle).mkv", 111321],
    ["[HorribleSubs] Yurumate3Dei - 26 [1080p].mkv", 14693],
    ["[EMBER] Natsu no Arashi! - S01E01-Playback Part 2 [BD00F464].mkv", 5597],
    ["Food Wars! S2 - 01.mkv", 21518],
    ["[AnimeRG] Food Wars! S2 - 01 [1080p] [x265] [pseudo].mkv", 21518],
    ["[Judas] Kimetsu no Yaiba - NCED 02 (ep 19).mkv", 101922],
    ["[ASW] Magia Record S2 - 01v3 [1080p HEVC][E268A7C4].mkv", 117002],
    ["[Judas] Hibike! Euphonium - Movie 1.mkv", 21638],
    ["[Hakata Ramen] One Piece - Movie 01 - One Piece the Movie.mkv", 464],
    ["[Hakata Ramen] Detective Conan - Movie 01 - The Time Bombed Skyscraper.mkv", 779]
]


@devlog.log_on_error(trace_stack=True)
def main():
    fail = 0
    for idx, (title, anilist_id) in enumerate(test):
        anime = recognition.track(title, not title.endswith(".mkv"))

        if anime["anilist"] == 0:
            logger.info(f"{idx}, undetected, {anime}")
            print(idx, "undetected", anime)
            fail += 1
        elif anime["anilist"] != anilist_id:
            # anime = recognition.parsing(title)
            logger.info(f"{idx}, expect {anilist_id}, {anime}")
            print(idx, f"expect {anilist_id}", anime)
            fail += 1
    if fail:
        raise ReferenceError(f"{fail}/{len(test)} failed")
    else:
        print("Yey, All passed")


def trace():
    title, anilist_id = test[19]
    anime = recognition.track(title)
    print(anime["anilist"] == anilist_id)
    pprint(anime)


main()
# trace()

# import requests
#
# requests.post("https://api.trace.moe/search",
#               data=open("demo.jpg", "rb"),
#               headers={"Content-Type": "video/*"}
#               ).json()

# from pyffmpeg import FFmpeg
#
# ff = FFmpeg()
