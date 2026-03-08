#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = "<3.13"
# dependencies = [
#     "beautifulsoup4<5",
#     "bs4==0.0.1",
#     "certifi",
#     "charset-normalizer<3",
#     "idna<4",
#     "lxml<5",
#     "pyinputplus<1",
#     "pysimplevalidate<1",
#     "requests<3",
#     "soupsieve<3",
#     "stdiomask<0.1",
#     "urllib3<2",
# ]
# ///


# itunestoND.py - Transfers song ratings, playcounts and play dates from I-Tunes library
# to the Navidrome database

import datetime
import pprint
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup


def max_date(d1, d2):
    if d1 is None:
        return d2
    if d2 is None:
        return d1
    return max(d1, d2)


@dataclass
class Stats:
    total: int = 0
    seen: int = 0
    skip_no_location: int = 0
    skip_not_found_video: int = 0
    skip_not_found: int = 0
    skip_duplicated: int = 0


@dataclass
class PlayStat:
    nd_exists: bool = False
    nd_play_count: int = 0
    nd_play_date: datetime.datetime = None
    nd_rating: int = 0
    nd_rated_at: datetime.datetime = None
    it_play_count: int = 0
    it_play_date: datetime.datetime = None
    it_rating: int = 0
    it_rated_at: datetime.datetime = None
    it_album_rating: int = 0

    def play_count(self):
        return self.it_play_count + self.nd_play_count

    def play_date(self):
        return max_date(self.it_play_date, self.nd_play_date)

    def rating(self):
        if self.nd_rating == 0:
            return self.it_rating
        return self.nd_rating

    def rated_at(self):
        return max_date(self.it_rated_at, self.nd_rated_at)


def get_db_path(dbID, argN):
    if len(sys.argv) > argN:
        path = Path(sys.argv[argN]).resolve()
        if not path.is_file():
            print(str(path) + " is not a file.")
        else:
            return path
    while True:
        path = Path(input("Enter the path to the %s: " % dbID)).resolve()
        if not path.is_file():
            print(str(path) + " is not a file. Try again.")
        else:
            break
    return path


def determine_userID(nd_p):
    conn = sqlite3.connect(nd_p)
    cur = conn.cursor()
    cur.execute("SELECT id, user_name FROM user")
    users = cur.fetchall()
    if len(users) == 1:
        print(
            f"Changes will be applied to the {users[0][1]} Navidrome account."
        )
    else:
        while True:
            if len(users) == 0:
                print("There are no user accounts set up with Navidrome.")
                raise Exception(
                    "There needs to be at least one user account set up with Navidrome."
                )
            else:
                print("There are multiple user accounts set up with Navidrome.")
            print("Please select the user account to apply changes to:")
            for i, user in enumerate(users):
                print(f"{i + 1}. {user[1]}")
            choice = input("Enter the number of the user account: ")
            try:
                choice = int(choice)
                if 1 <= choice <= len(users):
                    return users[choice - 1][0], users[choice - 1][1]
            except ValueError:
                pass
            print("Invalid choice. Try again.")
    conn.close()
    return users[0][0], users[0][1]


FIND_SONG_QUERY = 'SELECT f.id, f.artist_id, f.album_id, u.play_count, u.play_date, u.rating, u.rated_at FROM media_file f LEFT JOIN annotation u ON u.user_id = ? AND u.item_id = f.id AND u.item_type = "media_file" WHERE INSTR(f.path, ?) > 0'


def find_song(cur, song_path):
    cur.execute(FIND_SONG_QUERY, (userID, song_path))
    fetched = cur.fetchone()
    while fetched is None:
        if "/" in song_path:
            song_path = "/".join(*song_path.split("/")[1:])
        else:
            return fetched
        cur.execute(FIND_SONG_QUERY, (userID, song_path))
        fetched = cur.fetchone()
    return fetched


def get_itunes_local_path(song_path, it_root):
    if song_path.is_relative_to(it_root):
        return song_path.relative_to(it_root).as_posix()
    if it_root.stem == "iTunes Music":
        it_root = it_root.parent
        if it_root.stem == "iTunes":
            if song_path.is_relative_to(it_root.parent):
                return song_path.relative_to(it_root.parent).as_posix()
        if song_path.is_relative_to(it_root):
            return song_path.relative_to(it_root).as_posix()
    return None


def as_dt(val):
    if val is None:
        return None
    try:
        return datetime.datetime.strptime(val[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.datetime.strptime(val[:19], "%Y-%m-%d %H:%M:%S")


def extract_date_key(it_song_entry, key):
    date_val = it_song_entry.find("key", string=key)
    if date_val is None:
        return None
    date_val = date_val.next_sibling
    if date_val is None:
        return None
    # convert from string to datetime object. Example string: '2020-01-19T02:24:14Z'
    return as_dt(date_val.text)


def extract_int_key(it_song_entry, key, default=0):
    val = it_song_entry.find("key", string=key)
    if val is None:
        if default is None:
            raise ValueError(f"Key '{key}' not found")
        return default
    val = val.next_sibling
    if val is None:
        if default is None:
            raise ValueError(f"Key '{key}' not found")
        return default
    try:
        return int(val.text)
    except ValueError as e:
        if default is not None:
            return default
        raise e


def update_playstats(d1, id, song_info, cur, item_type):
    if id not in d1:
        d1[id] = PlayStat()
        cur.execute(
            "SELECT a.play_count, a.play_date, a.rating, a.rated_at FROM annotation a WHERE a.user_id = ? AND a.item_id = ? AND a.item_type = ?",
            (userID, id, item_type),
        )
        try:
            (
                nd_play_count,
                nd_play_date,
                nd_rating,
                nd_rated_at,
            ) = cur.fetchone()
            d1[id].nd_exists = True
            d1[id].nd_play_count = nd_play_count or 0
            d1[id].nd_play_date = as_dt(nd_play_date)
            d1[id].nd_rating = nd_rating or 0
            d1[id].nd_rated_at = as_dt(nd_rated_at)
        except TypeError:
            pass
    d1[id].it_album_rating = song_info.it_album_rating
    d1[id].it_play_count += song_info.it_play_count
    d1[id].it_play_date = max_date(d1[id].it_play_date, song_info.it_play_date)
    d1[id].it_rated_at = max_date(d1[id].it_rated_at, song_info.it_rated_at)


def write_to_annotation(dictionary_with_stats, entry_type):
    new_annotations = []
    update_annotations = []
    for item_id in dictionary_with_stats:
        this_entry = dictionary_with_stats[item_id]

        play_date = this_entry.play_date()
        if play_date is not None:
            play_date = play_date.strftime("%Y-%m-%d %H:%M:%S")

        rated_date = this_entry.rated_at()
        if rated_date is not None:
            rated_date = rated_date.strftime("%Y-%m-%d %H:%M:%S")

        if (
            this_entry.play_count() == 0
            and this_entry.rating() == 0
            and this_entry.nd_exists is False
        ):
            continue

        annotation = (
            userID,
            item_id,
            entry_type,
            this_entry.play_count(),
            play_date,
            this_entry.rating(),
            rated_date,
        )
        if this_entry.nd_exists:
            update_annotations.append(annotation)
        else:
            new_annotations.append(annotation)

    conn = sqlite3.connect(nddb_path)
    cur = conn.cursor()
    if new_annotations:
        cur.executemany(
            "INSERT INTO annotation(user_id,item_id,item_type,play_count,play_date,rating,rated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            new_annotations,
        )
        print(f"{len(new_annotations)} new annotations inserted.")
    if update_annotations:
        cur.executemany(
            "UPDATE annotation SET play_count=?, play_date=?, rating=?, rated_at=? WHERE user_id=? AND item_id=? AND item_type=?",
            update_annotations,
        )
        print(f"{len(update_annotations)} annotations updated.")
    conn.commit()
    conn.close()


nddb_path = get_db_path("Navidrome database", 1)
userID, userName = determine_userID(nddb_path)

itdb_path = get_db_path("iTunes database", 2)

print("\nParsing iTunes library. This may take a while.")
with open(itdb_path, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "lxml-xml")

it_root_music_path = Path(
    unquote(soup.find("key", string="Music Folder").next_sibling.text)
)
# example output of previous line: 'file://localhost/C:/Users/REDACTED/Music/iTunes/iTunes Music/'

songs = soup.dict.dict.find_all(
    "dict"
)  # yields result set of media files to loop through

song_count = len(songs)
print(f"Found {song_count} files in iTunes database to process.")
del soup

songID_correlation = {}  # we'll save this for later use to transfer iTunes playlists to ND (another script)
artists = {}  # artists and albums will keep count of plays and play dates for each
albums = {}
files = {}


status_interval = song_count // 8
stats = Stats()
stats.total = song_count

conn = sqlite3.connect(nddb_path)
cur = conn.cursor()

for it_song_entry in songs:
    stats.seen += 1
    if stats.seen % status_interval == 0:
        print(
            f"{stats.seen:,} files parsed so far of {song_count:,} total songs."
        )
        print("Current stats:", stats)

    # chop off first part of IT path so we can correlate it to the entry in the ND database

    if it_song_entry.find("key", string="Location") is None:
        stats.skip_no_location += 1
        continue

    song_path = Path(
        unquote(it_song_entry.find("key", string="Location").next_sibling.text)
    )
    local_path = get_itunes_local_path(song_path, it_root_music_path)
    if local_path is None:
        song_path = song_path.as_posix()
    else:
        song_path = local_path

    try:
        (
            song_id,
            artist_id,
            album_id,
            nd_play_count,
            nd_play_date,
            nd_rating,
            nd_rated_at,
        ) = find_song(cur, song_path)
        song_info = PlayStat(
            nd_exists=nd_play_count is not None,
            nd_play_count=nd_play_count or 0,
            nd_play_date=as_dt(nd_play_date),
            nd_rating=nd_rating or 0,
            nd_rated_at=as_dt(nd_rated_at),
        )
    except TypeError:
        if (
            str(song_path).endswith("mp4")
            or str(song_path).endswith("m4v")
            or str(song_path).endswith("mov")
            or str(song_path).endswith("mpg")
        ):
            stats.skip_not_found_video += 1
            continue
        print(f"NOTF: {song_path}")
        stats.skip_not_found += 1
        continue

    # correlate iTunes ID with Navidrome ID (for use in a future script)
    it_song_ID = extract_int_key(it_song_entry, "Track ID", default=None)
    songID_correlation.update({it_song_ID: song_id})

    song_info.it_rating = (
        extract_int_key(it_song_entry, "Rating", default=0) // 20
    )
    song_info.it_album_rating = (
        extract_int_key(it_song_entry, "Album Rating", default=0) // 20
    )
    song_info.it_play_count = extract_int_key(
        it_song_entry, "Play Count", default=0
    )
    song_info.it_rated_at = extract_date_key(it_song_entry, "Date Modified")
    song_info.it_play_date = extract_date_key(it_song_entry, "Play Date UTC")

    update_playstats(artists, artist_id, song_info, cur, "artist")
    update_playstats(albums, album_id, song_info, cur, "album")
    if song_id in files:
        stats.skip_duplicated += 1
    else:
        files[song_id] = song_info


conn.close()

print("Completed collecting songs information.")

_ = None
while _ != "proceed":
    print()
    print(
        "This script will migrate certain data from your ITunes library to your Navidrome database.",
        "Back up all your data in case it doesn't work properly on your setup. NO WARRANTIES. NO PROMISES.",
        f"     Navidrome path: {nddb_path}",
        f"               User: {userName} ({userID})",
        f"iTunes library path: {itdb_path}",
        f"              Stats: {stats}",
        sep="\n",
    )
    print()

    _ = input("Type PROCEED to continue, or Q to quit: ").lower()

    if _ == "q":
        print("Good bye.")
        sys.exit(0)


print("Writing changes to database:")
write_to_annotation(artists, "artist")
print("Done writing artist records to database.")
write_to_annotation(files, "media_file")
print("Done writing music file records to database.")
write_to_annotation(albums, "album")
print("Album records saved to database.")

with open("IT_file_correlations.py", "w") as f:
    f.write(
        "# Following python dictionary correlates the itunes integer ID to the Navidrome file ID for each song.\n"
    )
    f.write("# {ITUNES ID: ND ID} is the format. \n\n")
    f.write("itunes_correlations = ")
    f.write(pprint.pformat(songID_correlation))

print("Navidrome database updated.")
print(
    f"File correlation index saved to {str(Path.cwd() / 'IT_file_correlations.py')}\n"
)
print(
    "You can delete it if you want, but I will use it later in a script to transfer playlists from iTunes to Navidrome."
)
