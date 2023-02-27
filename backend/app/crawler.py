import asyncio
import functools

import asynciolimiter
import httpx

from tortoise.functions import Max
from tortoise.exceptions import IntegrityError

from app.external import DeezerAPI
from app.models import Artist, Album, RecordType
from app.schemas import TrackingStatus
from app.settings import settings


# Lifted directly from fastapi-utils:
# https://github.com/dmontagu/fastapi-utils/blob/master/fastapi_utils/tasks.py
def repeat_every(*, minutes: int):
    def decorator(func):
        @functools.wraps(func)
        async def wrapped() -> None:
            async def run_forever() -> None:
                while True:
                    try:
                        await func()  # type: ignore
                    except Exception as exc:
                        raise exc
                    await asyncio.sleep(minutes * 60)

            asyncio.ensure_future(run_forever())

        return wrapped

    return decorator


async def num_albums_in_queue() -> int:
    count = (
        await Album.filter(status=TrackingStatus.Added)
        .exclude(artist__disabled=True, record_type=RecordType.Single)
        .count()
    )
    return count


class DeezerCrawler:

    BATCH_SIZE = 10
    BATCH_LIMIT = 5

    def __init__(self):
        self.counter = 0
        self.is_active = False
        self.limiter = asynciolimiter.StrictLimiter(settings.DEEZER_API_RATE_LIMIT)
        self.deezer_api = DeezerAPI(self.limiter)

    async def find_start_point(self) -> int:
        id: int = (
            await Artist.all()
            .annotate(start_id=Max("id"))
            .first()
            .values_list("start_id", flat=True)
        )  # type: ignore
        print(f"Start point {id}")
        if id is None:
            return settings.DEEZER_ARTIST_START_ID
        return id

    def reset_counter(self):
        self.counter = 0

    async def crawl_deezer(self):
        print("Starting to maybe crawl...")
        queue_size = await num_albums_in_queue()
        self.reset_counter()

        while (
            queue_size < settings.DEEZER_QUEUE_LIMIT and self.counter < self.BATCH_LIMIT
        ):
            artist_id = await self.find_start_point()
            async with httpx.AsyncClient() as client:
                await self.crawl_range(client, artist_id, artist_id + self.BATCH_SIZE)

            queue_size = await num_albums_in_queue()
            self.counter += 1

    async def crawl_range(self, client: httpx.AsyncClient, start: int, end: int):
        tasks = []
        for id in range(start, end):
            tasks.append(self.scrape_artist(client, id))
        await asyncio.gather(*tasks)

    async def scrape_artist(
        self,
        client: httpx.AsyncClient,
        id: int,
    ):
        if await Artist.get_or_none(id=id):
            return None

        artist = await self.deezer_api.fetch_artist(client, id)
        print(f"Artist: {artist}")
        if artist:
            await Artist.create(**artist.dict())
            albums = await self.deezer_api.fetch_albums(client, id)

            for album in albums:
                # Some albums don't have genres listed. Deezer identifies these
                # by setting genre_id=-1. Redacted requires
                # every album to have a genre, though. Automatically disable these
                if not album.genres:
                    album.status = TrackingStatus.Disabled
                if album.release_date.year < settings.DEEZER_MINIMUM_RELEASE_YEAR:
                    album.status = TrackingStatus.Disabled
                try:
                    # print(f"Artist {artist.id} | {album.id}")
                    album = await Album.create(**album.dict())
                # An album can belong to multiple Artists. We may encounter
                # a unique constraint database error if this album was previously
                # added through another artist:
                except IntegrityError:
                    continue
