import os
import asyncio

import httpx
from fastapi import FastAPI, Depends, HTTPException, status, Query

from tortoise.transactions import atomic
from tortoise.exceptions import DoesNotExist
from aiolimiter import AsyncLimiter

from .models import (
    DeezerArtistTortoise,
    DeezerAlbumTortoise,
    UploadTortoise,
    RecordType,
)
from .schemas import (
    AlbumDeezerAPI,
    AlbumTrackDeezerAPI,
    DeezerArtist,
    DeezerAlbum,
    GazelleSearchResult,
    ArtistUpdate,
    TrackerAPIResponse,
    TrackerCode,
    UploadParameters,
    ParsedAudioFile,
)
from .external import DeezerAPI, RedactedAPI, download_album, UploadManager
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
async def get_artists(
    remove_singles: bool = True, only_added: bool = False, remove_reviewed: bool = True
):
    artists = await DeezerArtistTortoise.all().prefetch_related("albums").limit(10)

    results = []
    for artist in artists:
        albums = artist.albums

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
    num_crawls: int = Query(..., gt=0, lt=settings.MAX_CRAWLS_PER_RUN),
    deezer: DeezerAPI = Depends(DeezerAPI),
) -> list[DeezerArtist]:
    results = []
    async with httpx.AsyncClient() as client:
        end_id = start_id + num_crawls
        tasks = [crawl_artist(client, deezer, id) for id in range(start_id, end_id)]
        results = await asyncio.gather(*tasks)

    return [result for result in results if result]


@app.put("/album/{id}/add")
async def add_torrent(
    album: DeezerAlbumTortoise = Depends(get_album_or_404),
) -> DeezerAlbum:
    album.ready_to_add = True
    await album.save()

    return DeezerAlbum.from_orm(album)


@app.put("/artist/{id}/review")
async def review_artist(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
) -> ArtistUpdate:
    artist.reviewed = True
    await artist.save()

    return ArtistUpdate.from_orm(artist)


@app.get("/album/{id}/download")
async def download_album(id):
    download_album(id)
    return {"ok": "ok"}


@app.put("/album/{id}/upload")
@atomic()
async def upload_album(
    album: DeezerAlbumTortoise = Depends(get_album_or_404),
    deezer: DeezerAPI = Depends(DeezerAPI),
    manager: UploadManager = Depends(UploadManager),
    tracker_code: TrackerCode = TrackerCode.RED,
) -> TrackerAPIResponse:

    async with httpx.AsyncClient() as client:
        album_deezer_api = await deezer.fetch_album_details(client, album.id)

    if not all(
        verify_downloaded_contents(album.download_path, album_deezer_api).values()
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Downloaded audio content does not conform to verification",
        )

    torrent = manager.generate_torrent(album.download_path, tracker_code)
    params = UploadParameters.from_deezer(album_deezer_api)
    upload = await UploadTortoise.create(
        infohash=torrent.infohash,
        upload_parameters=params.dict(by_alias=True),
        file=torrent.dump(),
        tracker_code=tracker_code,
        album=album,
    )

    await manager.add_to_qbittorrent(upload.file)

    async with httpx.AsyncClient() as client:
        tracker_response = await manager.process_upload(
            client, params, tracker_code, upload.file
        )

    upload.update_from_dict(tracker_response.dict(exclude_unset=True))
    await upload.save()

    return tracker_response


@app.get("/artist/{id}/search/redacted")
async def search_redacted(
    artist: DeezerArtistTortoise = Depends(get_artist_or_404),
    redacted=Depends(RedactedAPI),
) -> list[GazelleSearchResult]:

    async with httpx.AsyncClient() as client:
        results = await redacted.search_artist(client, artist.name)

    return results


@app.get("/album/{id}/verifications")
async def verify_album(
    album: DeezerAlbumTortoise = Depends(get_album_or_404),
    deezer: DeezerAPI = Depends(DeezerAPI),
) -> dict[str, bool]:

    async with httpx.AsyncClient() as client:
        deezer_album = await deezer.fetch_album_details(client, album.id)

    verifications = verify_downloaded_contents(album.download_path, deezer_album)
    return verifications


def verify_downloaded_contents(
    download_path: str, album: AlbumDeezerAPI
) -> dict[str, bool]:
    parsed_files = []
    for filename in os.listdir(download_path):
        if not filename.endswith(".flac"):
            continue
        filepath = os.path.join(download_path, filename)
        parsed_files.append(ParsedAudioFile.from_filepath(filepath))
    parsed_files = list(sorted(parsed_files, key=lambda x: x.position))

    if len(album.tracks) != len(parsed_files):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Number of tracks downloaded does not match album tracks",
        )
    results = {}

    for parsed, track in zip(parsed_files, album.tracks):
        results[parsed.filepath] = parsed.verify(album, track)

    return results
