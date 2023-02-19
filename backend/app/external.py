import difflib
import os

from io import BytesIO
from typing import Optional

import httpx
from pydantic import BaseModel

from deezer import Deezer
from deemix.itemgen import generateAlbumItem
from deemix.downloader import Downloader
from deemix.utils.pathtemplates import fixName as deemix_normalize_path

from .schemas import DeezerArtist, DeezerAlbum, GazelleSearchResult
from .models import RecordType, DeezerAlbumTortoise
from .settings import settings, DEEMIX_SETTINGS


RECORD_TYPES = {
    "album": RecordType.ALBUM,
    "ep": RecordType.EP,
    "single": RecordType.SINGLE,
}


class DeezerAPI:

    API_ARTIST_ENDPOINT = "https://api.deezer.com/artist/"

    def __init__(self):
        pass

    async def fetch_artist(
        self, client: httpx.AsyncClient, id: int
    ) -> Optional[DeezerArtist]:
        url = f"https://api.deezer.com/artist/{id}"
        response = await client.get(url)
        data = response.json()

        if "error" in data:
            return None

        return DeezerArtist(
            id=data["id"],
            name=data["name"],
            image_url=data["picture"],
            nb_album=data["nb_album"],
            nb_fan=data["nb_fan"],
        )

    async def fetch_albums(
        self, client: httpx.AsyncClient, id: int
    ) -> list[DeezerAlbum]:
        url = f"https://api.deezer.com/artist/{id}/albums"
        response = await client.get(url)
        data = response.json()

        albums = []
        for record in data["data"]:
            albums.append(
                DeezerAlbum(
                    id=record["id"],
                    artist_id=id,
                    title=record["title"],
                    image_url=record["cover"],
                    release_date=record["release_date"],
                    record_type=RECORD_TYPES[record["record_type"]],
                )
            )
        return albums


class GazelleAPI:
    def __init__(self, api_url: str, apikey: str):
        self.api_url = api_url
        self.apikey = apikey

    async def upload(
        self, client: httpx.AsyncClient, params: dict, torrentfile: BytesIO
    ) -> dict:
        filename = f"{params['title']}.torrent"
        files = {"file_input": (filename, torrentfile)}

        response = await client.post(
            url=self.api_url, data=params, files=files, headers=self.headers
        )
        return response.json()

    async def search_artist(
        self, client: httpx.AsyncClient, artist: str
    ) -> list[GazelleSearchResult]:
        params = {"action": "browse", "artistname": artist}
        response = await client.get(self.api_url, params=params, headers=self.headers)

        data = response.json()

        results = []
        for result in data["response"]["results"]:
            results.append(
                GazelleSearchResult(
                    groupid=result["groupId"],
                    artist=result["artist"],
                    title=result["groupName"],
                )
            )
        return results

    @property
    def headers(self):
        return {"Authorization": self.apikey}


async def process_upload(
    client: httpx.AsyncClient, params: dict, torrentfile: bytes, tracker: GazelleAPI
):
    with BytesIO() as f:
        f.write(torrentfile)
    f.seek(0)
    response = await tracker.upload(client, params, f)

    if response["status"] == "success":
        torrentid = response["response"]["torrentid"]
        groupid = response["response"]["groupid"]
        return dict(torrentid=torrentid, groupid=groupid)
    else:
        raise Exception(f"Upload failed: {response}")


class RedactedAPI(GazelleAPI):
    def __init__(self):

        super().__init__("https://redacted.ch/ajax.php", settings.REDACTED_API_KEY)


def levenshtein_distance(str1: str, str2: str) -> int:
    counter = {"+": 0, "-": 0}
    distance = 0
    for edit_code, *_ in difflib.ndiff(str1, str2):
        if edit_code == " ":
            distance += max(counter.values())
            counter = {"+": 0, "-": 0}
        else:
            counter[edit_code] += 1
    distance += max(counter.values())
    return distance


def closeness(str1: str, str2: str) -> float:
    distance = levenshtein_distance(str1.lower(), str2.lower())

    n = max(len(str1), len(str2))

    return max(n - distance, 0) / n


def generate_folder_path(album: DeezerAlbumTortoise) -> str:
    foldername = DEEMIX_SETTINGS["albumNameTemplate"]

    substitutions = [
        ("%artist%", album.artist.name),
        ("%album%", album.title),
        ("%year%", str(album.release_date.year)),
    ]

    for template, value in substitutions:
        foldername = foldername.replace(template, value)

    return os.path.join(settings.DOWNLOAD_FOLDER, deemix_normalize_path(foldername), "")


def download_album(deezer_id: int):
    deezer = Deezer()
    deezer.login_via_arl(settings.DEEZER_ARL_COOKIE)
    album = generateAlbumItem(
        deezer,
        deezer_id,
        DEEMIX_SETTINGS["maxBitrate"],
    )

    Downloader(deezer, album, DEEMIX_SETTINGS).start()
