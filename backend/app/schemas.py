from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, HttpUrl, validator

from .models import RecordType


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


class Torrent(BaseModel):
    id: int
    create_date: datetime
    album: DeezerAlbum
    download_path: str

    class Config:
        orm_mode = True
