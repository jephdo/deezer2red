import abc
import difflib
import pathlib
import hashlib

from io import BytesIO
from typing import Optional

import httpx
import torf
import pyben
import qbittorrentapi

from deezer import Deezer
from deemix.itemgen import generateAlbumItem
from deemix.downloader import Downloader

from .schemas import (
    DeezerArtist,
    DeezerAlbum,
    GazelleSearchResult,
    AlbumDeezerAPI,
    AlbumTrackDeezerAPI,
    TrackerCode,
    TrackerAPIResponse,
    UploadParameters,
    RecordType,
    RECORD_TYPES,
)

from .settings import settings, DEEMIX_SETTINGS


class DeezerAPI:

    API_BASE_URL = "https://api.deezer.com"

    def __init__(self):
        pass

    async def fetch_artist(
        self, client: httpx.AsyncClient, id: int
    ) -> Optional[DeezerArtist]:
        url = f"{self.API_BASE_URL}/artist/{id}"
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
        """Retrieves a list of albums given a specific artist ID"""
        url = f"{self.API_BASE_URL}/artist/{id}/albums"
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

    async def fetch_album_details(
        self, client: httpx.AsyncClient, id: int
    ) -> AlbumDeezerAPI:
        """Retrieves complete metadata info about a particular album."""

        url = f"{self.API_BASE_URL}/album/{id}"
        response = await client.get(url)

        data = response.json()

        return self.parse_album_details(data)

    def parse_album_details(self, raw_data: dict) -> AlbumDeezerAPI:
        genres = [genre["name"] for genre in raw_data["genres"]["data"]]

        tracks = []
        for track in raw_data["tracks"]["data"]:
            tracks.append(
                AlbumTrackDeezerAPI(
                    id=track["id"],
                    title=track["title"],
                    duration_seconds=track["duration"],
                )
            )

        contributors = {}
        for contrib in raw_data["contributors"]:
            name = contrib["name"]
            role = contrib["role"]
            contributors[name] = role

        album = AlbumDeezerAPI(
            id=raw_data["id"],
            artist=raw_data["artist"]["name"],
            title=raw_data["title"],
            record_type=RecordType(raw_data["record_type"]),
            release_date=raw_data["release_date"],
            album_url=raw_data["link"],
            cover_url=raw_data["cover_medium"],
            genres=genres,
            label=raw_data["label"],
            tracks=tracks,
            contributors=contributors,
        )
        return album


class GazelleAPI(abc.ABC):
    def __init__(self, api_url: str, apikey: str):
        self.api_url = api_url
        self.apikey = apikey

    @property
    @abc.abstractmethod
    def tracker_code(self):
        pass

    async def upload(
        self, client: httpx.AsyncClient, data: dict, torrentfile: BytesIO
    ) -> TrackerAPIResponse:
        filename = f"{data['title']}.torrent"
        files = {"file_input": (filename, torrentfile)}
        params = {"action": "upload"}

        response = await client.post(
            url=self.api_url,
            params=params,
            data=data,
            files=files,
            headers=self.headers,
        )

        data = response.json()
        data = data["response"]
        return TrackerAPIResponse(
            torrentid=data["torrentid"],
            groupid=data["groupid"],
            tracker_code=self.tracker_code,
        )

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


class RedactedAPI(GazelleAPI):
    tracker_code = TrackerCode.RED

    def __init__(self):

        super().__init__("https://redacted.ch/ajax.php", settings.REDACTED_API_KEY)


class OrpheusAPI(GazelleAPI):
    tracker_code = TrackerCode.OPS

    def __init__(self):
        raise NotImplementedError


TRACKER_APIS = {
    TrackerCode.RED: RedactedAPI,
    TrackerCode.OPS: OrpheusAPI,
}


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


def download_album(deezer_id: int):
    deezer = Deezer()
    deezer.login_via_arl(settings.DEEZER_ARL_COOKIE)
    album = generateAlbumItem(
        deezer,
        deezer_id,
        DEEMIX_SETTINGS["maxBitrate"],
    )

    Downloader(deezer, album, DEEMIX_SETTINGS).start()


def get_infohash(torrentfile: bytes) -> str:
    """Calculate the torrent infohash (v1) of a torrent file."""
    torrent, _ = pyben.bendecode(torrentfile)
    return hashlib.sha1(pyben.benencode(torrent["info"])).hexdigest()


class UploadManager:
    def check_files_ready(self, album: AlbumDeezerAPI, download_path: str):
        # TODO: Ideally this verification should be more robust
        # 1) Verify each track: generate the track filename from deemix and
        #    determine if that file actually exists
        # 2) There should be a cover.jpg file
        # 3) Filesize should be reasonable based on track duration
        #    (e.g. FLAC.bitrate * track.duration should roughly equal filesize)
        # 4) There are no superfluous hidden files like @eaDir
        path = pathlib.Path(download_path)
        files = path.glob("*.flac")

        return len(list(files)) == len(album.tracks)

    def generate_torrent(
        self, download_path: str, tracker_code: TrackerCode
    ) -> torf.Torrent:
        self.torrent = torf.Torrent(
            path=download_path,
            trackers=[settings.REDACTED_ANNOUNCE_URL],
            private=True,
            source=tracker_code.value,
        )
        self.torrent.generate()
        return self.torrent

    async def process_upload(
        self,
        client: httpx.AsyncClient,
        params: UploadParameters,
        tracker_code: TrackerCode,
        torrentfile: bytes,
    ) -> TrackerAPIResponse:
        tracker_api = TRACKER_APIS[tracker_code]()

        with BytesIO() as file_:
            file_.write(torrentfile)
            file_.seek(0)

            response = await tracker_api.upload(
                client, params.dict(by_alias=True), file_
            )
        return response

    async def add_to_qbittorrent(self, torrent_file: bytes):
        client = qbittorrentapi.Client(
            host=settings.QBITTORRENT_HOST,
            port=settings.QBITTORRENT_PORT,
            username=settings.QBITTORRENT_USERNAME,
            password=settings.QBITTORRENT_PASSWORD,
        )
        client.auth_log_in()

        client.torrents_add(
            torrent_files=torrent_file,
            category=settings.QBITTORRENT_CATEGORY,
            tags=settings.QBITTORRENT_TAGS,
        )
