import httpx

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi_pagination.ext.tortoise import paginate
from fastapi_pagination import Params, Page
from tortoise.exceptions import DoesNotExist


from app.models import (
    Artist,
)
from app.schemas import (
    DeezerArtist,
    DeezerArtistAlbums,
    GazelleSearchResult,
    TrackerCode,
)
from app.external import (
    GazelleAPI,
    TRACKER_APIS,
)
from app.settings import settings

router = APIRouter()


async def get_artist_or_404(id: int) -> Artist:
    try:
        return await Artist.get(id=id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/artists")
async def get_artists(params: Params = Depends()) -> Page[DeezerArtist]:
    artists = await paginate(Artist.all(), params)
    return artists


@router.get("/artist/{id}")
async def get_artist(
    artist: DeezerArtist = Depends(get_artist_or_404),
) -> DeezerArtist:
    return artist


@router.get("/artist/{id}/albums")
async def get_artist_albums(
    artist: Artist = Depends(get_artist_or_404),
) -> DeezerArtistAlbums:
    await artist.fetch_related("albums")
    return artist  # type: ignore


@router.put("/artist/{id}/disable")
async def disable_artist(
    artist: Artist = Depends(get_artist_or_404),
) -> DeezerArtist:
    artist.disabled = True  # type: ignore
    await artist.save()

    return artist  # type: ignore


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
    artist: Artist = Depends(get_artist_or_404),
    tracker=Depends(get_tracker_or_404),
) -> list[GazelleSearchResult]:

    async with httpx.AsyncClient() as client:
        results = await tracker.search_artist(client, artist.name)

    return results
