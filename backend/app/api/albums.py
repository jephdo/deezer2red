import os

import httpx

from fastapi import APIRouter, Depends, HTTPException, status, Query
from tortoise.transactions import atomic
from tortoise.exceptions import DoesNotExist


from app.models import (
    DeezerAlbumTortoise,
    UploadTortoise,
)
from app.schemas import (
    AlbumDeezerAPI,
    DeezerAlbum,
    TrackerAPIResponse,
    TrackerCode,
    UploadParameters,
    ParsedAudioFile,
)
from app.external import DeezerAPI, RedactedAPI, download_album, UploadManager
from app.settings import settings


router = APIRouter()


async def get_album_or_404(id: int) -> DeezerAlbumTortoise:
    try:
        return await DeezerAlbumTortoise.get(id=id).prefetch_related("artist")
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/albums", response_model=list[DeezerAlbum])
async def get_albums():
    albums = await DeezerAlbumTortoise.all()
    return [DeezerAlbum.from_orm(album) for album in albums]


@router.put("/album/{id}/add")
async def add_torrent(
    album: DeezerAlbumTortoise = Depends(get_album_or_404),
) -> DeezerAlbum:
    album.ready_to_add = True  # type: ignore
    await album.save()

    return DeezerAlbum.from_orm(album)


@router.get("/album/{id}/download")
async def download(id):
    download_album(id)
    return {"ok": "ok"}


@router.put("/album/{id}/upload")
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

    manager.add_to_qbittorrent(upload.file)

    async with httpx.AsyncClient() as client:
        tracker_response = await manager.process_upload(
            client, params, tracker_code, upload.file
        )

    upload.update_from_dict(tracker_response.dict(exclude_unset=True))
    await upload.save()

    return tracker_response


@router.get("/album/{id}/verifications")
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
