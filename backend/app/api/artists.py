import asyncio
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi_pagination.ext.tortoise import paginate
from fastapi_pagination import Params, Page

from tortoise.transactions import atomic
from tortoise.exceptions import DoesNotExist
from aiolimiter import AsyncLimiter

from app.models import (
    DeezerArtistTortoise,
    DeezerAlbumTortoise,
    RecordType,
)
from app.schemas import (
    DeezerArtist,
    DeezerArtistWithAlbums,
    DeezerAlbum,
    GazelleSearchResult,
    ArtistUpdate,
    TrackerCode,
)
from app.external import (
    DeezerAPI,
    GazelleAPI,
    RedactedAPI,
    download_album,
    UploadManager,
    TRACKER_APIS,
)
from app.settings import settings

# The actual rate limit is 50 calls per 5 seconds not 15 calls per 5 seconds:
# https://developers.deezer.com/api
DEEZER_RATE_LIMIT = AsyncLimiter(5, 1)

router = APIRouter()


async def get_artist_or_404(id: int) -> DeezerArtistTortoise:
    try:
        return await DeezerArtistTortoise.get(id=id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/artists")
async def get_artists(params: Params = Depends()) -> Page[DeezerArtist]:
    artists = await paginate(DeezerArtistTortoise.all(), params)
    return artists


async def crawl_artist(
    client: httpx.AsyncClient, deezer: DeezerAPI, artist_id: int
) -> Optional[DeezerArtist]:
    if await DeezerArtistTortoise.get_or_none(id=artist_id):
        return None

    async with DEEZER_RATE_LIMIT:
        artist = await deezer.fetch_artist(client, artist_id)
        if artist:
            await DeezerArtistTortoise.create(**artist.dict(exclude_unset=True))
            albums = await deezer.fetch_albums(client, artist_id)
            for album in albums:
                await DeezerAlbumTortoise.create(**album.dict())
            return artist
        else:
            return None


@router.post("/artists/crawl")
@atomic()
async def crawl_deezer(
    start_id: int = Query(..., gt=0),
    num_crawls: int = Query(..., gt=0, lt=settings.MAX_CRAWLS_PER_RUN),
    deezer: DeezerAPI = Depends(DeezerAPI),
) -> list[DeezerArtist]:
    results = []
    async with httpx.AsyncClient() as client:
        end_id = start_id + num_crawls
        tasks = [crawl_artist(client, deezer, id) for id in range(start_id, end_id)]
        results = await asyncio.gather(*tasks)

    return [result for result in results if result]


@router.get("/artist/{id}")
async def get_artist(
    artist: DeezerArtist = Depends(get_artist_or_404),
) -> DeezerArtist:
    return artist


@router.get("/artist/{id}/albums")
async def get_artist_albums(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
) -> DeezerArtistWithAlbums:
    await artist.fetch_related("albums")

    return artist  # type: ignore


@router.put("/artist/{id}/review")
async def review_artist(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
) -> ArtistUpdate:

    artist.reviewed = True  # type: ignore
    await artist.save()

    return ArtistUpdate.from_orm(artist)


def get_tracker_or_404(tracker_code: TrackerCode) -> GazelleAPI:
    try:
        return TRACKER_APIS[tracker_code]()
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tracker found for {tracker_code}",
        )


@router.get("/artist/{id}/search")
async def search_redacted(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
    tracker=Depends(get_tracker_or_404),
) -> list[GazelleSearchResult]:

    async with httpx.AsyncClient() as client:
        results = await tracker.search_artist(client, artist.name)

    return results
