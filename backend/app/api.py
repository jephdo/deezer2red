import httpx
from fastapi import FastAPI, Depends
from tortoise.contrib.fastapi import register_tortoise
from tortoise.transactions import atomic

from .models import DeezerArtistTortoise, DeezerAlbumTortoise, Torrent, Upload
from .schemas import DeezerArtist, DeezerAlbum
from .external import DeezerAPI


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


@app.get("/crawl")
@atomic()
async def crawl_deezer(
    start_id: int, num: int, deezer_api: DeezerAPI = Depends(DeezerAPI)
) -> list[DeezerArtist]:
    results = []
    async with httpx.AsyncClient() as client:
        for artist_id in range(start_id, start_id + num):
            if await DeezerArtistTortoise.get_or_none(id=artist_id):
                continue

            artist = await deezer_api.fetch_artist(client, artist_id)
            if artist:
                await DeezerArtistTortoise.create(**artist.dict())
                albums = await deezer_api.fetch_albums(client, artist_id)
                for album in albums:
                    await DeezerAlbumTortoise.create(**album.dict())
                results.append(artist)

    return results


register_tortoise(
    app,
    db_url="sqlite://db.sqlite",
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)
