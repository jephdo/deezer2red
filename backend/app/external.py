import abc
import difflib

from datetime import datetime, date
from io import BytesIO
from typing import Optional

import httpx
import torf
import qbittorrentapi
import pydantic


from deezer import Deezer
from deemix.itemgen import generateAlbumItem
from deemix.downloader import Downloader

from .models import TrackerCode, RecordType
from .schemas import (
    DeezerArtist,
    DeezerAlbum,
    GazelleSearchResult,
    DeezerTrack,
    TrackerAPIResponse,
    UploadParameters,
    DEEZER_RECORD_TYPES,
)

from .settings import settings, DEEMIX_SETTINGS


class DeezerAPI:

    API_BASE_URL = "https://api.deezer.com"

    def __init__(self, limiter=None):
        self.limiter = limiter

    async def get(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        if self.limiter is not None:
            await self.limiter.wait()
        response = await client.get(url)
        return response

    async def fetch_artist(
        self, client: httpx.AsyncClient, id: int
    ) -> Optional[DeezerArtist]:
        url = f"{self.API_BASE_URL}/artist/{id}"
        response = await self.get(client, url)
        data = response.json()

        # Artist may not exist, will return code 800
        # {'error': {'type': 'DataException', 'message': 'no data', 'code': 800}}
        if "error" in data and data["error"]["code"] == 800:
            return

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
        response = await self.get(client, url)
        data = response.json()

        albums = []
        for record in data["data"]:
            album_id = record["id"]
            try:
                album = await self.fetch_album_details(client, album_id)
            # Sometimes album metadata is incomplete like missing image_url:
            except pydantic.ValidationError:
                continue
            albums.append(album)
        return albums

    async def fetch_album_details(
        self, client: httpx.AsyncClient, id: int
    ) -> DeezerAlbum:
        """Retrieves complete metadata info about a particular album."""

        url = f"{self.API_BASE_URL}/album/{id}"
        response = await self.get(client, url)
        data = response.json()
        # The Deezer album APIs only return the release date of the digital stream
        # not the actual physical release of the album. And the only way to get this
        # information is to access the 'album' field in the Track endpoint...
        # Have to make an extra API call to the Track endpoint to get this info:
        physical_release_date = await self._fetch_release_date(client, data)
        return self.parse_album_details(
            data, physical_release_date=physical_release_date
        )

    async def _fetch_release_date(
        self, client: httpx.AsyncClient, album_raw_response: dict
    ) -> date:
        try:
            raw_tracks = album_raw_response["tracks"]["data"]
        except KeyError:
            print(album_raw_response)
            raise

        for track in raw_tracks:
            track_details = await self.fetch_track_details(client, track["id"])
            try:
                release_date = track_details["album"]["release_date"]
            except KeyError:
                continue
            release_date = datetime.strptime(release_date, "%Y-%m-%d").date()
            return release_date
        raise ValueError("Can not find album release date from Deezer track details.")

    async def fetch_track_details(self, client: httpx.AsyncClient, id: int) -> dict:
        url = f"{self.API_BASE_URL}/track/{id}"
        response = await self.get(client, url)
        data = response.json()
        return data

    def parse_album_details(
        self, raw_data: dict, physical_release_date: date
    ) -> DeezerAlbum:
        genres = [genre["name"] for genre in raw_data["genres"]["data"]]

        tracks = []
        for i, track in enumerate(raw_data["tracks"]["data"]):
            tracks.append(
                DeezerTrack(
                    id=track["id"],
                    title=track["title"],
                    duration_seconds=track["duration"],
                    # The Deezer API doesn't actually return each track position
                    # for the Album endpoint (but it does for the specific
                    # Track endpoint). I'm assuming the tracks are returned in
                    # sorted order rather than sending an API request for each track
                    position=i + 1,
                )
            )

        contributors = {}
        for contrib in raw_data["contributors"]:
            name = contrib["name"]
            role = contrib["role"]
            contributors[name] = role

        album = DeezerAlbum(
            id=raw_data["id"],
            artist_id=raw_data["artist"]["id"],
            title=raw_data["title"],
            image_url=raw_data["cover_medium"],
            digital_release_date=datetime.strptime(
                raw_data["release_date"], "%Y-%m-%d"
            ).date(),
            release_date=physical_release_date,
            record_type=RecordType(raw_data["record_type"]),
            genres=genres,
            label=raw_data["label"],
            tracks=tracks,
            contributors=contributors,
            upc=raw_data["upc"],
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
            tracker_code=self.tracker_code,  # type: ignore
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
    tracker_code = TrackerCode.RED  # type: ignore

    def __init__(self):

        super().__init__(settings.REDACTED_API_URL, settings.REDACTED_API_KEY)


class OrpheusAPI(GazelleAPI):
    tracker_code = TrackerCode.OPS  # type: ignore

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


class UploadManager:
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

    def add_to_qbittorrent(self, torrent_file: bytes):
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
