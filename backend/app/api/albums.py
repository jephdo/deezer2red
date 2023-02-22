import os

import httpx

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination.ext.tortoise import paginate
from fastapi_pagination import Params, Page
from tortoise.transactions import atomic
from tortoise.expressions import Subquery
from tortoise.exceptions import DoesNotExist
from tortoise.query_utils import Prefetch


from app.models import (
    DeezerAlbumTortoise,
    DeezerArtistTortoise,
    UploadTortoise,
)
from app.schemas import (
    AlbumDeezerAPI,
    DeezerAlbum,
    DeezerArtistWithAlbums,
    RecordType,
    TrackerAPIResponse,
    TrackerCode,
    UploadParameters,
    ParsedAudioFile,
)
from app.external import DeezerAPI, download_album, UploadManager


router = APIRouter()


async def get_album_or_404(id: int) -> DeezerAlbumTortoise:
    try:
        return await DeezerAlbumTortoise.get(id=id).prefetch_related("artist")
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/albums")
async def get_albums(params: Params = Depends()) -> Page[DeezerAlbum]:
    results = await paginate(DeezerAlbumTortoise, params)
    return results


@router.get("/albums/ready")
async def get_ready_albums(params: Params = Depends()) -> Page[DeezerArtistWithAlbums]:
    artists = (
        await DeezerArtistTortoise.filter(
            albums__ready_to_add=True, albums__uploads__isnull=True
        )
        .distinct()
        .values_list("id", flat=True)
    )

    queryset = (
        DeezerArtistTortoise.filter(reviewed=False, id__in=artists)
        .prefetch_related(
            Prefetch(
                "albums",
                DeezerAlbumTortoise.filter(ready_to_add=True, uploads__isnull=True),
            )
        )
        .order_by("-create_date", "-id")
    )
    return await paginate(queryset, params)


@router.get("/albums/tracked")
async def get_tracked_albums(
    params: Params = Depends(),
) -> Page[DeezerArtistWithAlbums]:
    queryset = (
        DeezerArtistTortoise.filter(
            reviewed=False,
        )
        .prefetch_related(
            Prefetch(
                "albums", DeezerAlbumTortoise.exclude(record_type=RecordType.SINGLE)
            )
        )
        .order_by("-create_date", "-id")
    )
    return await paginate(queryset, params)


@router.get("/album/{id}")
async def get_album(album: DeezerAlbum = Depends(get_album_or_404)) -> DeezerAlbum:
    return album


@router.put("/album/{id}/add")
async def add_torrent(
    album: DeezerAlbumTortoise = Depends(get_album_or_404),
) -> DeezerAlbum:
    album.ready_to_add = True  # type: ignore
    await album.save()

    return DeezerAlbum.from_orm(album)


@router.put("/album/{id}/remove")
async def add_torrent(
    album: DeezerAlbumTortoise = Depends(get_album_or_404),
) -> DeezerAlbum:
    album.ready_to_add = False  # type: ignore
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

    try:
        filenames = os.listdir(download_path)
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Album not downloaded yet"
        )
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
