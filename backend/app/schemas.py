import enum
import re

from datetime import datetime, date, timedelta
from typing import Optional

from pydantic import BaseModel, HttpUrl, validator, Field

from .settings import settings


class RecordType(enum.Enum):
    ALBUM = "album"
    EP = "ep"
    SINGLE = "single"


RECORD_TYPES = {
    "album": RecordType.ALBUM,
    # "soundtrack": 3,
    "ep": RecordType.EP,
    # "anthology": 6,
    # "compilation": 7,
    "single": RecordType.SINGLE,
    # "live album": 11,
    # "remix": 13,
    # "bootleg": 14,
    # "interview": 15,
    # "mixtape": 16,
    # "demo": 17,
    # "concert recording": 18,
    # "dj mix": 19,
    # "unknown": 21,
}


class TrackerCode(enum.Enum):
    RED = "RED"
    OPS = "OPS"


class GazelleSearchResult(BaseModel):
    groupid: int
    artist: str
    title: str
    match: Optional[float] = None


class DeezerAlbum(BaseModel):
    id: int
    artist_id: int
    title: str
    image_url: HttpUrl
    release_date: date
    record_type: RecordType

    @validator("release_date", pre=True)
    def date_validate(cls, v):
        if isinstance(v, date):
            return v
        return datetime.strptime(v, "%Y-%m-%d").date()

    class Config:
        orm_mode = True


class DeezerArtist(BaseModel):
    id: int
    name: str
    image_url: HttpUrl
    nb_album: int
    nb_fan: int
    albums: Optional[list[DeezerAlbum]] = None

    class Config:
        orm_mode = True


class ArtistUpdate(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


# class AlbumUpload(BaseModel):
#     id: int
#     torrent_id: int
#     group_id: int
#     tracker_code: TrackerCode
#     url: HttpUrl


class AlbumTrackDeezerAPI(BaseModel):
    id: int
    title: str
    duration_seconds: int


class AlbumDeezerAPI(BaseModel):
    id: int
    artist: str
    title: str
    record_type: RecordType
    release_date: date
    album_url: str
    cover_url: str
    genres: list[str]
    label: str
    tracks: list[AlbumTrackDeezerAPI]
    contributors: dict[str, str]


class TrackerAPIResponse(BaseModel):
    torrentid: int
    groupid: int
    tracker_code: TrackerCode
    url: Optional[int] = None


RELEASE_TYPES = {
    RecordType.ALBUM: 1,
    # "soundtrack": 3,
    RecordType.EP: 5,
    # "anthology": 6,
    # "compilation": 7,
    RecordType.SINGLE: 9,
    # "live album": 11,
    # "remix": 13,
    # "bootleg": 14,
    # "interview": 15,
    # "mixtape": 16,
    # "demo": 17,
    # "concert recording": 18,
    # "dj mix": 19,
    # "unknown": 21,
}


class UploadParameters(BaseModel):
    # This should always be set to 0
    # Music->0, Applications->1, E-Books->2, Audiobooks->3, etc.
    category_type: int = 0
    artists: list[str] = Field(alias="artists[]")
    importance: list[int] = Field(alias="importance[]")
    title: str
    year: int
    releasetype: int
    remaster_year: int
    remaster_record_label: str
    format: str = "FLAC"
    bitrate: str = "Lossless"
    media: str = "WEB"
    tags: str
    image: str
    album_desc: str
    release_desc: str

    class Config:
        allow_population_by_field_name = True

    @classmethod
    def from_deezer(cls, album: AlbumDeezerAPI):
        (artists, importance) = cls.unzip_contributors(album.contributors)
        return cls(
            artists=artists,
            importance=importance,
            title=album.title,
            year=album.release_date.year,
            releasetype=RELEASE_TYPES[album.record_type],
            remaster_year=album.release_date.year,
            remaster_record_label=album.label,
            tags=album.genres,
            image=album.cover_url,
            album_desc=album,
            release_desc=album.id,
        )

    @validator("tags", pre=True)
    def normalize_genre_tags(cls, genres: str | list[str]):
        if isinstance(genres, str):
            return genres

        def normalize_genre(genre: str) -> str:
            return re.sub("[^0-9a-zA-Z]+", ".", genre.lower())

        def format_genres(genres: list[str]) -> str:
            return ",".join(map(normalize_genre, genres))

        return format_genres(genres)

    @validator("release_desc", pre=True)
    def generate_release_description(cls, id: str | int):
        if isinstance(id, str):
            return id

        logo_url = settings.DEEZER_LOGO_URL

        desc = f"""[img]{logo_url}[/img]
Sourced from [url=https://www.deezer.com/album/{id}]Deezer[/url]"""
        return desc

    @validator("album_desc", pre=True)
    def generate_album_description(cls, album: str | AlbumDeezerAPI):
        if isinstance(album, str):
            return album

        contents = []

        contents.append(f"[size=4][b]{album.artist} - {album.title}[/b][/size]\n\n")
        contents.append(f"[b]Label/Cat#:[/b] {album.label}\n")
        contents.append(f"[b]Year:[/b] {album.release_date.year}\n")
        contents.append(f"[b]Genre:[/b] {', '.join(album.genres)}\n")

        contents.append("\n")
        contents.append("[size=3][b]Tracklist[/b][/size]\n")

        for i, track in enumerate(album.tracks):
            contents.append(
                f"[b]{i+1}.[/b] {track.title} [i]({timedelta(seconds=track.duration_seconds)})[/i]\n"
            )

        total_duration = sum(track.duration_seconds for track in album.tracks)
        contents.append(f"\n[b]Total length:[/b] {timedelta(seconds=total_duration)}\n")
        contents.append(f"\nMore information: [url]{album.album_url}[/url]")

        return "".join(contents)

    @staticmethod
    def unzip_contributors(contributors):
        data = list(contributors.items())

        artists, importance = list(zip(*data))

        def map_artist_type(artist_type: str) -> int:
            artist_type_map = {
                "Main": 1,
                "Guest": 2,
                "Featured": 2,
                "Composer": 4,
                "Conductor": 5,
                "DJ / Compiler": 6,
                "Remixer": 3,
                "Producer": 7,
            }
            return artist_type_map[artist_type]

        importance = list(map(map_artist_type, importance))
        return list(artists), list(importance)
