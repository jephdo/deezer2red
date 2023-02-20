import os

from pydantic import BaseSettings
from deemix.settings import DEFAULTS
from deezer import TrackFormats

ROOT_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Settings(BaseSettings):

    DEBUG: bool = True
    DATABASE_URL: str = "sqlite://db.sqlite"

    REDACTED_API_KEY: str
    REDACTED_ANNOUNCE_URL: str

    DOWNLOAD_FOLDER: str

    DEEZER_ARL_COOKIE: str
    ROOT_FOLDER: str = ROOT_FOLDER

    MAX_CRAWLS_PER_RUN: int = 10

    QBITTORRENT_HOST: str
    QBITTORRENT_PORT: int
    QBITTORRENT_USERNAME: str
    QBITTORRENT_PASSWORD: str
    QBITTORRENT_CATEGORY: str = 'deezer2red'
    QBITTORRENT_TAGS: str = 'myupload'

    class Config:
        env_file = os.path.join(ROOT_FOLDER, ".env")


settings = Settings()

DEEMIX_SETTINGS = DEFAULTS.copy()
DEEMIX_SETTINGS["downloadLocation"] = settings.DOWNLOAD_FOLDER
DEEMIX_SETTINGS["albumNameTemplate"] = "%artist% - %album% (%year%) [WEB FLAC]"
DEEMIX_SETTINGS["maxBitrate"] = TrackFormats.FLAC
