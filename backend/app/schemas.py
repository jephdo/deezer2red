from datetime import datetime, date

from pydantic import BaseModel, HttpUrl, validator

from .models import RecordType


class DeezerArtist(BaseModel):
    id: int
    name: str
    image_url: HttpUrl
    nb_album: int
    nb_fan: int

    class Config:
        orm_mode = True


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
