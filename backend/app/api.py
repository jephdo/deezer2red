import asyncio

import httpx
from fastapi import FastAPI, Depends
from tortoise.contrib.fastapi import register_tortoise
from tortoise.transactions import atomic
from aiolimiter import AsyncLimiter

from .models import DeezerArtistTortoise, DeezerAlbumTortoise, Torrent, Upload
from .schemas import DeezerArtist, DeezerAlbum
from .external import DeezerAPI

# The actual rate limit is 50 calls per 5 seconds not 15 calls per 5 seconds:
# https://developers.deezer.com/api
DEEZER_RATE_LIMIT = AsyncLimiter(15, 5)

app = FastAPI()


@app.get("/")
async def hello():
    return {"hello": "world"}


@app.get("/artists", response_model=list[DeezerArtist])
async def get_artists():
    artists = await DeezerArtistTortoise.all()
    return [DeezerArtist.from_orm(artist) for artist in artists]


@app.get("/albums", response_model=list[DeezerAlbum])
async def get_albums():
    albums = await DeezerAlbumTortoise.all()
    return [DeezerAlbum.from_orm(album) for album in albums]


async def crawl_artist(client: httpx.AsyncClient, deezer: DeezerAPI, artist_id: int):
    if await DeezerArtistTortoise.get_or_none(id=artist_id):
        return None

    async with DEEZER_RATE_LIMIT:
        artist = await deezer.fetch_artist(client, artist_id)
        if artist:
            await DeezerArtistTortoise.create(**artist.dict())
            albums = await deezer.fetch_albums(client, artist_id)
            for album in albums:
                await DeezerAlbumTortoise.create(**album.dict())
            return artist
        else:
            return None


@app.get("/crawl")
@atomic()
async def crawl_deezer(
    start_id: int, num: int, deezer: DeezerAPI = Depends(DeezerAPI)
) -> list[DeezerArtist]:
    results = []
    async with httpx.AsyncClient() as client:
        end_id = start_id + num
        tasks = [crawl_artist(client, deezer, id) for id in range(start_id, end_id)]
        results = await asyncio.gather(*tasks)

    return [result for result in results if result]


register_tortoise(
    app,
    db_url="sqlite://db.sqlite",
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)
