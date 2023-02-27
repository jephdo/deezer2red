import os
import shutil

import httpx

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi_pagination.ext.tortoise import paginate
from fastapi_pagination import Params, Page
from tortoise.transactions import atomic
from tortoise.exceptions import DoesNotExist

from pydantic import ValidationError

from app.models import (
    Album,
    Upload,
)
from app.schemas import (
    AlbumInfo,
    DeezerTrack,
    TrackerAPIResponse,
    TrackerCode,
    TrackingStatus,
    UploadParameters,
    RecordType,
    ParsedAudioFile,
)
from app.external import DeezerAPI, download_album, UploadManager


router = APIRouter()


async def get_album_or_404(id: int) -> Album:
    try:
        return await Album.get(id=id).prefetch_related("artist")
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/albums")
async def get_albums(params: Params = Depends()) -> Page[AlbumInfo]:
    results = await paginate(Album.all().prefetch_related("artist"), params)
    return results


@router.get("/albums/{status}")
async def get_albums_by_status(
    status: TrackingStatus, params: Params = Depends()
) -> Page[AlbumInfo]:
    results = await paginate(
        Album.filter(status=status)
        .exclude(artist__disabled=True, record_type=RecordType.Single)
        .order_by("-release_date")
        .prefetch_related("artist"),
        params,
    )
    return results


@router.get("/albums/upload/ready")
async def get_albums_ready_upload(params: Params = Depends()) -> Page[AlbumInfo]:
    results = await paginate(
        Album.filter(status__in=[TrackingStatus.Reviewed, TrackingStatus.Downloaded])
        .exclude(artist__disabled=True, record_type=RecordType.Single)
        .order_by("-release_date")
        .prefetch_related("artist"),
        params,
    )
    return results


@router.get("/album/{id}")
async def get_album(album: Album = Depends(get_album_or_404)) -> AlbumInfo:
    return album  # type: ignore


@router.put("/album/{id}/add")
async def add_album_upload_queue(
    album: Album = Depends(get_album_or_404),
) -> AlbumInfo:
    album.status = TrackingStatus.Reviewed
    await album.save()

    return album  # type: ignore


@router.put("/album/{id}/remove")
async def remove_album_upload_queue(
    album: Album = Depends(get_album_or_404),
) -> AlbumInfo:
    album.status = TrackingStatus.Disabled  # type: ignore
    await album.save()

    try:
        shutil.rmtree(album.download_path)
    except FileNotFoundError:
        pass

    return album  # type: ignore


@router.put("/album/{id}/download")
async def download_album_from_deezer(
    background_tasks: BackgroundTasks, album: Album = Depends(get_album_or_404)
) -> AlbumInfo:
    async def download():
        download_album(album.id)
        album.status = TrackingStatus.Downloaded
        await album.save()

    background_tasks.add_task(download)
    return album  # type: ignore


@router.put("/album/{id}/upload")
@atomic()
async def upload_album(
    album: Album = Depends(get_album_or_404),
    manager: UploadManager = Depends(UploadManager),
    tracker_code: TrackerCode = TrackerCode.RED,
) -> TrackerAPIResponse:

    if not all(verify_downloaded_contents(album).values()):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Downloaded audio content does not conform to verification",
        )

    torrent = manager.generate_torrent(album.download_path, tracker_code)
    params = UploadParameters.from_album(album)
    upload = await Upload.create(
        infohash=torrent.infohash,
        upload_parameters=params.dict(by_alias=True),
        file=torrent.dump(),
        tracker_code=tracker_code,
        album=album,
    )

    async with httpx.AsyncClient() as client:
        tracker_response = await manager.process_upload(
            client, params, tracker_code, upload.file
        )
    upload.update_from_dict(tracker_response.dict(exclude_unset=True))
    await upload.save()
    manager.add_to_qbittorrent(upload.file)
    album.status = TrackingStatus.Uploaded
    await album.save()

    return tracker_response


@router.get("/album/{id}/preview")
async def preview_upload_parameters(
    album: Album = Depends(get_album_or_404),
) -> UploadParameters:
    return UploadParameters.from_album(album)


@router.put("/album/{id}/{status}")
async def get_album(
    status: TrackingStatus,
    album: Album = Depends(get_album_or_404),
) -> AlbumInfo:
    album.status = status
    await album.save()
    return album  # type: ignore


@router.get("/album/{id}/verifications")
async def verify_downloaded_album(
    album: Album = Depends(get_album_or_404),
) -> dict[str, bool]:

    verifications = verify_downloaded_contents(album)
    return verifications


def verify_downloaded_contents(album: Album) -> dict[str, bool]:
    parsed_files = []

    try:
        filenames = os.listdir(album.download_path)
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Album not downloaded yet"
        )

    for filename in filenames:
        if not filename.endswith((".flac", "cover.jpg")):
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Encountered unexpected file in download folder: {filename}",
            )
        if not filename.endswith(".flac"):
            continue
        filepath = os.path.join(album.download_path, filename)
        parsed_files.append(ParsedAudioFile.from_filepath(filepath))
    parsed_files = list(sorted(parsed_files, key=lambda x: x.position))

    if len(album.tracks) != len(parsed_files):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Number of tracks downloaded does not match album tracks",
        )
    results = {}

    for parsed, track in zip(parsed_files, album.tracks):
        track = DeezerTrack(**track)
        results[parsed.filepath] = parsed.verify(album, track)

    return results
