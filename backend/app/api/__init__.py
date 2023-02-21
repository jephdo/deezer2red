from fastapi import FastAPI


from app.settings import settings
from .artists import router as artists_router
from .albums import router as albums_router


app = FastAPI()

app.include_router(artists_router, tags=["artists"])
app.include_router(albums_router, tags=["albums"])


@app.get("/")
async def root():
    response = {"message": "Hello! This is your backend speaking."}
    if settings.DEBUG:
        response["settings"] = settings.dict()  # type: ignore
    return response


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
