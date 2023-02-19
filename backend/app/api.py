import os
import asyncio

import httpx
from fastapi import FastAPI, Depends, HTTPException, status, Query

from tortoise.contrib.fastapi import register_tortoise
from tortoise.transactions import atomic
from tortoise.exceptions import DoesNotExist
from aiolimiter import AsyncLimiter

from .models import (
    DeezerArtistTortoise,
    DeezerAlbumTortoise,
    TorrentTortoise,
    UploadTortoise,
    RecordType,
)
from .schemas import DeezerArtist, DeezerAlbum, GazelleSearchResult, Torrent
from .external import DeezerAPI, RedactedAPI, generate_folder_path, download_album
from .settings import settings

# The actual rate limit is 50 calls per 5 seconds not 15 calls per 5 seconds:
# https://developers.deezer.com/api
DEEZER_RATE_LIMIT = AsyncLimiter(5, 1)

app = FastAPI()


async def get_artist_or_404(id: int) -> DeezerArtistTortoise:
    try:
        return await DeezerArtistTortoise.get(id=id).prefetch_related("albums")
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


async def get_album_or_404(id: int) -> DeezerAlbumTortoise:
    try:
        return await DeezerAlbumTortoise.get(id=id).prefetch_related("artist")
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@app.get("/")
async def hello():
    return {"hello": "world"}


@app.get("/artists", response_model=list[DeezerArtist])
async def get_artists(remove_singles: bool = True, remove_reviewed: bool = True):
    artists = await DeezerArtistTortoise.all().prefetch_related("albums").limit(10)

    results = []
    for artist in artists:
        albums = [DeezerAlbum.from_orm(album) for album in artist.albums]
        if remove_singles:
            albums = [
                album for album in albums if album.record_type != RecordType.SINGLE
            ]
        results.append(
            DeezerArtist(
                id=artist.id,
                image_url=artist.image_url,
                name=artist.name,
                nb_album=artist.nb_album,
                nb_fan=artist.nb_fan,
                albums=albums,
            )
        )
    return results


@app.get("/artist/{id}", response_model=DeezerArtist)
async def get_artist(artist: DeezerArtistTortoise = Depends(get_artist_or_404)):
    return DeezerArtist.from_orm(artist)


@app.get("/albums", response_model=list[DeezerAlbum])
async def get_albums():
    albums = await DeezerAlbumTortoise.all()
    return [DeezerAlbum.from_orm(album) for album in albums]


@app.get("/artist/{id}/albums")
async def get_artist_albums(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
) -> list[DeezerAlbum]:
    albums = artist.albums
    return [DeezerAlbum.from_orm(album) for album in albums]


async def crawl_artist(client: httpx.AsyncClient, deezer: DeezerAPI, artist_id: int):
    if await DeezerArtistTortoise.get_or_none(id=artist_id):
        return None

    async with DEEZER_RATE_LIMIT:
        artist = await deezer.fetch_artist(client, artist_id)
        if artist:
            print(artist)
            await DeezerArtistTortoise.create(**artist.dict(exclude_unset=True))
            albums = await deezer.fetch_albums(client, artist_id)
            for album in albums:
                await DeezerAlbumTortoise.create(**album.dict())
            return artist
        else:
            return None


@app.post("/crawl")
@atomic()
async def crawl_deezer(
    start_id: int = Query(..., gt=0),
    num_crawls: int = Query(..., gt=0, lt=10),
    deezer: DeezerAPI = Depends(DeezerAPI),
) -> list[DeezerArtist]:
    results = []
    async with httpx.AsyncClient() as client:
        end_id = start_id + num_crawls
        tasks = [crawl_artist(client, deezer, id) for id in range(start_id, end_id)]
        results = await asyncio.gather(*tasks)

    return [result for result in results if result]


@app.post("/album/{id}/generate", status_code=status.HTTP_201_CREATED)
async def create_torrent(
    album: DeezerAlbumTortoise = Depends(get_album_or_404),
) -> Torrent:
    download_path = generate_folder_path(album)
    # if not os.path.exists(download_path):
    #     os.makedirs(download_path)
    torrent = await TorrentTortoise.create(
        id=album.id, album=album, download_path=download_path
    )
    return Torrent.from_orm(torrent)


# @app.get("/album/{id}/path")
# async def get_download_path(album: DeezerAlbumTortoise = Depends(get_album_or_404)):
#     return generate_folder_path(album)


@app.get("/torrent/{id}/download")
def download(id):
    download_album(id)
    return {"ok": "ok"}


@app.get("/artist/{id}/search/redacted")
async def search_redacted(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
    redacted=Depends(RedactedAPI),
) -> list[GazelleSearchResult]:

    async with httpx.AsyncClient() as client:
        results = await redacted.search_artist(client, artist.name)

    return results


register_tortoise(
    app,
    db_url=settings.DATABASE_URL,
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)
