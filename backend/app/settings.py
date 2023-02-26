import os

from pydantic import BaseSettings
from deemix.settings import DEFAULTS
from deezer import TrackFormats

ROOT_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Settings(BaseSettings):

    DEBUG: bool = True
    DATABASE_URL: str = "sqlite://" + os.path.join(ROOT_FOLDER, "db.sqlite")

    DOWNLOAD_FOLDER: str

    # In terms of requests per second:
    # The actual rate limit is 50 calls per 5 seconds
    # https://developers.deezer.com/api
    DEEZER_API_RATE_LIMIT: int = 5
    DEEZER_ARL_COOKIE: str

    MAX_CRAWLS_PER_RUN: int = 75

    REDACTED_API_KEY: str
    REDACTED_ANNOUNCE_URL: str

    ROOT_FOLDER: str = ROOT_FOLDER

    QBITTORRENT_HOST: str
    QBITTORRENT_PORT: int
    QBITTORRENT_USERNAME: str
    QBITTORRENT_PASSWORD: str
    QBITTORRENT_CATEGORY: str = "deezer2red"
    QBITTORRENT_TAGS: str = "myupload"

    class Config:
        env_file = os.path.join(ROOT_FOLDER, ".env")


settings = Settings()  # type: ignore


# List of full deemix settings can be found here:
# https://gitlab.com/RemixDev/deemix-py/-/blob/main/deemix/settings.py
DEEMIX_SETTINGS = DEFAULTS.copy()
DEEMIX_SETTINGS["downloadLocation"] = settings.DOWNLOAD_FOLDER
DEEMIX_SETTINGS["albumNameTemplate"] = "%artist% - %album% (%year%) [WEB FLAC]"
DEEMIX_SETTINGS["maxBitrate"] = TrackFormats.FLAC
DEEMIX_SETTINGS["queueConcurrency"] = 3
DEEMIX_SETTINGS["logErrors"] = False
DEEMIX_SETTINGS["overwriteFile"] = "y"
