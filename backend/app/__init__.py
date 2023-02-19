from fastapi.middleware.cors import CORSMiddleware

from .api import app
from .settings import settings


@app.on_event("startup")
async def startup():
    if settings.DEBUG:
        print(settings)


origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
