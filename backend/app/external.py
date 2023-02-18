import httpx
from typing import Optional

from .schemas import DeezerArtist, DeezerAlbum
from .models import RecordType

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
