import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query

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
    DeezerAlbum,
    GazelleSearchResult,
    ArtistUpdate,
)
from app.external import DeezerAPI, RedactedAPI, download_album, UploadManager
from app.settings import settings

# The actual rate limit is 50 calls per 5 seconds not 15 calls per 5 seconds:
# https://developers.deezer.com/api
DEEZER_RATE_LIMIT = AsyncLimiter(5, 1)

router = APIRouter()


async def get_artist_or_404(id: int) -> DeezerArtistTortoise:
    try:
        return await DeezerArtistTortoise.get(id=id).prefetch_related("albums")
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/artists", response_model=list[DeezerArtist])
async def get_artists(
    remove_singles: bool = True, only_added: bool = False, remove_reviewed: bool = True
):
    artists = await DeezerArtistTortoise.all().prefetch_related("albums").limit(10)

    results = []
    for artist in artists:
        albums = artist.albums  # type: ignore

        if remove_reviewed and artist.reviewed:
            continue

        if remove_singles:
            albums = [
                album for album in albums if album.record_type != RecordType.SINGLE
            ]

        if only_added:
            if not any(a.ready_to_add for a in albums):
                continue
            else:
                albums = [a for a in albums if a.ready_to_add]

        albums = [DeezerAlbum.from_orm(album) for album in albums]

        results.append(
            DeezerArtist(
                id=artist.id,
                image_url=artist.image_url,  # type: ignore
                name=artist.name,
                nb_album=artist.nb_album,
                nb_fan=artist.nb_fan,
                albums=albums,
            )
        )
    return results


@router.get("/artist/{id}", response_model=DeezerArtist)
async def get_artist(artist: DeezerArtistTortoise = Depends(get_artist_or_404)):
    return DeezerArtist.from_orm(artist)


@router.get("/artist/{id}/albums")
async def get_artist_albums(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
) -> list[DeezerAlbum]:
    albums = artist.albums  # type: ignore
    return [DeezerAlbum.from_orm(album) for album in albums]


async def crawl_artist(client: httpx.AsyncClient, deezer: DeezerAPI, artist_id: int):
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


@router.post("/crawl")
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


@router.put("/artist/{id}/review")
async def review_artist(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
) -> ArtistUpdate:

    artist.reviewed = True  # type: ignore
    await artist.save()

    return ArtistUpdate.from_orm(artist)


@router.get("/artist/{id}/search/redacted")
async def search_redacted(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
    redacted=Depends(RedactedAPI),
) -> list[GazelleSearchResult]:

    async with httpx.AsyncClient() as client:
        results = await redacted.search_artist(client, artist.name)

    return results
