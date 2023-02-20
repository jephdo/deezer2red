from fastapi import FastAPI


from .api import app
from .settings import settings


@app.on_event("startup")
async def startup():
    if settings.DEBUG:
        print(settings)


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
