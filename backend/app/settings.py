from pydantic import BaseSettings
from deemix.settings import DEFAULTS
from deezer import TrackFormats


class Settings(BaseSettings):

    DEBUG: bool = True
    DATABASE_URL: str = "sqlite://db.sqlite"

    REDACTED_API_KEY: str
    REDACTED_ANNOUNCE_URL: str

    DOWNLOAD_FOLDER: str

    DEEZER_ARL_COOKIE: str

    class Config:
        env_file = ".env"


settings = Settings()

DEEMIX_SETTINGS = DEFAULTS.copy()
DEEMIX_SETTINGS["downloadLocation"] = settings.DOWNLOAD_FOLDER
DEEMIX_SETTINGS["albumNameTemplate"] = "%artist% - %album% (%year%) [WEB FLAC]"
DEEMIX_SETTINGS["maxBitrate"] = TrackFormats.FLAC
