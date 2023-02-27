import asyncio

from fastapi import FastAPI


from .api.artists import router as artists_router
from .api.albums import router as albums_router
from .crawler import repeat_every, DeezerCrawler, num_albums_in_queue
from .settings import settings


app = FastAPI()

app.include_router(artists_router, tags=["artists"])
app.include_router(albums_router, tags=["albums"])


@app.on_event("startup")
@repeat_every(minutes=5)
async def crawl_deezer():
    crawler = DeezerCrawler()
    # Have to wait for database to initialize:
    await asyncio.sleep(3)
    await crawler.crawl_deezer()


@app.get("/")
async def root():
    routes = {route.name: route.path for route in app.routes}
    response = {"message": "Hello! This is your backend speaking.", "routes": routes}
    if settings.DEBUG:
        response["settings"] = settings.dict()  # type: ignore
    return response


@app.get("/queue-size")
async def get_queue_size():
    count = await num_albums_in_queue()
    return {"queue_size": count}


def create_app() -> FastAPI:
    from fastapi.middleware.cors import CORSMiddleware
    from tortoise.contrib.fastapi import register_tortoise

    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_tortoise(
        app,
        db_url=settings.DATABASE_URL,
        modules={"models": ["app.models"]},
        generate_schemas=True,
        add_exception_handlers=True,
    )

    return app
