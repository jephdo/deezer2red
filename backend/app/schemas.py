import enum
import re
import os
import math

from datetime import datetime, date, timedelta
from typing import Optional

import audio_metadata
from pydantic import BaseModel, HttpUrl, validator, Field, conlist


class RecordType(enum.Enum):
    ALBUM = "album"
    EP = "ep"
    SINGLE = "single"
    COMPILATION = "compile"


RECORD_TYPES = {
    "album": RecordType.ALBUM,
    # "soundtrack": 3,
    "ep": RecordType.EP,
    # "anthology": 6,
    "compile": RecordType.COMPILATION,
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


class AlbumTrackDeezerAPI(BaseModel):
    id: int
    title: str
    position: int
    duration_seconds: int


class AlbumDeezerAPI(BaseModel):
    id: int
    artist: str
    title: str
    record_type: RecordType
    release_date: date
    album_url: str
    cover_url: str
    # Redacted actually requires every torrent upload to have at least
    # one genre/tag
    genres: conlist(str, min_items=1)  # type: ignore
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
    RecordType.COMPILATION: 7,
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
            artists=artists,  # type: ignore
            importance=importance,  # type: ignore
            title=album.title,
            year=album.release_date.year,
            releasetype=RELEASE_TYPES[album.record_type],
            remaster_year=album.release_date.year,
            remaster_record_label=album.label,
            tags=album.genres,
            image=album.cover_url,
            album_desc=album,
            release_desc=album.id,
        )  # type: ignore

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

        desc = f"""Sourced from [url=https://www.deezer.com/album/{id}]Deezer[/url]"""
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


class ParsedAudioFile(BaseModel):
    title: str
    album: str
    artist: str
    position: int
    duration_ms: int
    bitrate: int
    bitdepth: int
    sampling_rate: int
    filepath: str
    md5: str

    @validator("md5")
    def check_unset_md5(cls, v):
        try:
            # When the md5 signature is unset, it's set as
            # md5='00000000000000000000000000000000'
            # A dirty hack is to just try to cast this to int and if it's successful
            # it means the md5 signautre is unset. A real hash like
            # '1edd613ea1db5c870971ad5d222440e5' will raise a ValueError
            int(v)
        except ValueError:
            return v
        else:
            raise ValueError("MD5 signature unset in STREAMINFO")

    def verify(self, album: AlbumDeezerAPI, track: AlbumTrackDeezerAPI) -> bool:
        if self.title != track.title:
            return False
        if self.album != album.title:
            return False
        if self.artist != album.artist:
            return False
        if self.position != track.position:
            return False
        if self.bitdepth != 16:
            return False
        if self.sampling_rate != 44100:
            return False
        # Assuming 16-bit FLAC bitrates will be between 400kbps to 1411 kbps:
        if not (400 * 1000 < self.bitrate < 1411 * 1000):
            return False
        if not self.is_close(self.duration_ms / 1000, track.duration_seconds):
            return False

        # This is the bitrate as stated in the header of the audio file
        # Expected filesize is this bitrate times the track length
        # given by the Deezer API -- compare this to the actual filesize
        # reported by the OS
        expected_filesize_bytes = self.bitrate * track.duration_seconds / 8
        actual_filesize_bytes = os.path.getsize(self.filepath)

        if not self.is_close(expected_filesize_bytes, actual_filesize_bytes):
            return False

        return True

    def is_close(self, a, b, epsilon=0.01) -> bool:
        return math.isclose(a, b, rel_tol=epsilon)

    @classmethod
    def from_filepath(cls, filepath: str):
        info = audio_metadata.load(filepath)

        return cls(
            title=info.tags.title[0],
            album=info.tags.album[0],
            artist=info.tags.albumartist[0],
            position=info.tags.tracknumber[0],
            duration_ms=int(info.streaminfo.duration * 1000),
            bitrate=info.streaminfo.bitrate,
            bitdepth=info.streaminfo.bit_depth,
            sampling_rate=info.streaminfo.sample_rate,
            filepath=filepath,
            md5=info.streaminfo.md5,
        )
