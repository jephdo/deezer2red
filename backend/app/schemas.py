import enum
import re
import os
import math
import subprocess

from datetime import datetime, date, timedelta
from typing import Optional

import audio_metadata
from pydantic import BaseModel, HttpUrl, validator, Field


from .models import RecordType, TrackerCode, TrackingStatus, Album


DEEZER_RECORD_TYPES = {
    "album": RecordType.Album,
    "ep": RecordType.EP,
    "compile": RecordType.Compilation,
    "single": RecordType.Single,
}

REDACTED_RECORD_TYPES = {
    RecordType.Album: 1,
    # "soundtrack": 3,
    RecordType.EP: 5,
    # "anthology": 6,
    RecordType.Compilation: 7,
    RecordType.Single: 9,
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


class GazelleSearchResult(BaseModel):
    groupid: int
    artist: str
    title: str
    match: Optional[float] = None


class DeezerTrack(BaseModel):
    id: int
    title: str
    position: int
    duration_seconds: int


class DeezerAlbum(BaseModel):
    id: int
    artist_id: int
    title: str
    image_url: HttpUrl
    digital_release_date: date
    release_date: date
    create_date: datetime = Field(default_factory=datetime.now)
    record_type: RecordType
    status: TrackingStatus = TrackingStatus.Added
    genres: list[str]
    label: str
    tracks: list[DeezerTrack]
    contributors: dict[str, str]
    upc: str

    @property
    def album_url(self) -> str:
        return f"https://www.deezer.com/album/{self.id}"

    class Config:
        orm_mode = True


class DeezerArtist(BaseModel):
    id: int
    name: str
    image_url: HttpUrl
    nb_album: int
    nb_fan: int
    create_date: datetime = Field(default_factory=datetime.now)

    class Config:
        orm_mode = True


class AlbumInfo(BaseModel):
    id: int
    artist: DeezerArtist
    title: str
    image_url: HttpUrl
    digital_release_date: date
    release_date: date
    create_date: datetime
    record_type: RecordType
    status: TrackingStatus

    class Config:
        orm_mode = True


class DeezerArtistAlbums(DeezerArtist):
    albums: list[DeezerAlbum]

    @validator("albums", pre=True)
    def serialize_tortoise_albums(cls, albums):
        return [DeezerAlbum.from_orm(a) for a in albums]


class TrackerAPIResponse(BaseModel):
    torrentid: int
    groupid: int
    tracker_code: TrackerCode
    url: Optional[int] = None


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
    def from_album(cls, album):
        (artists, importance) = cls.unzip_contributors(album.contributors)
        return cls(
            artists=artists,  # type: ignore
            importance=importance,  # type: ignore
            title=album.title,
            year=album.release_date.year,
            releasetype=REDACTED_RECORD_TYPES[album.record_type],
            remaster_year=album.digital_release_date.year,
            remaster_record_label=album.label,
            tags=album.genres,
            image=album.image_url,
            album_desc=album,
            release_desc=album,
        )  # type: ignore

    @validator("remaster_record_label")
    def remove_record_dk(cls, label: str):
        # A lot of albums have their lable set to 12345 Records DK, which
        # is a fake label. Per Redacted guidelines better to leave the
        # label field empty. I do this by sending an empty string.
        if "records dk" in label.lower():
            return ""
        return label

    @validator("tags", pre=True)
    def normalize_genre_tags(cls, genres: str | list[str]):
        if isinstance(genres, str):
            return genres

        def normalize_genre(genre: str) -> str:
            return re.sub("[^0-9a-zA-Z]+", ".", genre.lower())

        return ",".join(map(normalize_genre, genres))

    @validator("release_desc", pre=True)
    def generate_release_description(cls, album: str | Album):
        if isinstance(album, str):
            return album

        desc = f"""Sourced from [url=https://www.deezer.com/album/{album.id}]Deezer[/url]\nLabel: {album.label}\nUPC: {album.upc}"""
        return desc

    @validator("album_desc", pre=True)
    def generate_album_description(cls, album: str | Album):
        if isinstance(album, str):
            return album

        contents = []
        contents.append(
            f"[size=4][b]{album.artist.name} - {album.title}[/b][/size]\n\n"
        )
        contents.append(f"[b]Label/Cat#:[/b] {album.label}\n")
        contents.append(f"[b]Year:[/b] {album.release_date.year}\n")
        contents.append(f"[b]Genre:[/b] {', '.join(album.genres)}\n")

        contents.append("\n")
        contents.append("[size=3][b]Tracklist[/b][/size]\n")

        for i, track in enumerate(album.tracks):
            track = DeezerTrack(**track)
            contents.append(
                f"[b]{i+1}.[/b] {track.title} [i]({timedelta(seconds=track.duration_seconds)})[/i]\n"
            )

        total_duration = sum(track["duration_seconds"] for track in album.tracks)
        contents.append(f"\n[b]Total length:[/b] {timedelta(seconds=total_duration)}\n")
        contents.append(f"\nMore information: [url]{album.album_url}[/url]")

        return "".join(contents)

    @staticmethod
    def unzip_contributors(contributors: dict) -> tuple[list[str], list[int]]:
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
    upc: str

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

    def verify(self, album: Album, track: DeezerTrack) -> bool:
        return self.verify_contents() and self.verify_metadata(album, track)

    def verify_metadata(self, album: Album, track: DeezerTrack) -> bool:
        if self.title != track.title:
            return False
        if self.album != album.title:
            return False
        # if self.artist != album.artist.name:
        #     return False
        if self.position != track.position:
            return False
        if self.bitdepth != 16:
            return False
        if self.sampling_rate != 44100:
            return False
        if self.upc != album.upc:
            return False
        # Assuming 16-bit FLAC bitrates will be between 400kbps to 1411 kbps:
        if not (400 * 1000 < self.bitrate < 1411 * 1000):
            return False
        if not self.tracklength_close(track.duration_seconds):
            return False

        # This is the bitrate as stated in the header of the audio file
        # Expected filesize is this bitrate times the track length
        # given by the Deezer API -- compare this to the actual filesize
        # reported by the OS
        expected_filesize_bytes = self.bitrate * track.duration_seconds // 8
        if not self.filesize_close(expected_filesize_bytes):
            return False

        return True

    def verify_contents(self) -> bool:
        result = subprocess.run(
            ["flac", "-t", self.filepath], capture_output=True, text=True
        )
        stderr = result.stderr.strip()
        if stderr.endswith("ok"):
            return True
        return False

    def tracklength_close(self, expected_duration_sec: int) -> bool:
        # Track must be within 5 seconds of the expected duration provided by
        # Deezer API
        acceptable_difference = 5
        actual_duration_sec = self.duration_ms // 1000
        return math.isclose(
            expected_duration_sec, actual_duration_sec, abs_tol=acceptable_difference
        )

    def filesize_close(self, expected_bytes: int) -> bool:
        actual_bytes = os.path.getsize(self.filepath)
        # A 3min FLAC audio file is gonna be 20MB-30MB, typically. Just
        # from inspecting lots of FLAC files the threshold difference is usually
        # at most 5%. However, need to handle the case for small audio files
        # (e.g. the track duration may be only 10 seconds) and set a minimum
        # filesize difference of 200KBs or 200_000 bytes
        acceptable_difference = max(200_000, int(actual_bytes * 0.05))
        return math.isclose(expected_bytes, actual_bytes, abs_tol=acceptable_difference)

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
            upc=info.tags.barcode[0],
        )
