import os
import enum

from datetime import datetime

from tortoise import fields
from tortoise.models import Model

from deemix.utils.pathtemplates import fixName as deemix_normalize_path

from .settings import DEEMIX_SETTINGS, settings


class TrackerCode(enum.Enum):
    RED = "RED"
    OPS = "OPS"


class RecordType(enum.Enum):
    Album = "album"
    EP = "ep"
    Single = "single"
    Compilation = "compile"


class TrackingStatus(enum.Enum):
    Added = "added"
    Reviewed = "reviewed"
    Downloaded = "downloaded"
    Uploaded = "uploaded"
    Disabled = "disabled"


class Artist(Model):
    id = fields.IntField(pk=True)
    name = fields.TextField()
    image_url = fields.TextField()
    nb_album = fields.IntField()
    nb_fan = fields.IntField()
    disabled = fields.BooleanField(default=False)
    create_date = fields.DatetimeField(default=datetime.now)


class Album(Model):
    id = fields.IntField(pk=True)
    artist = fields.ForeignKeyField(
        "models.Artist",
        related_name="albums",
    )
    title = fields.TextField()
    image_url = fields.TextField()
    digital_release_date = fields.DateField()
    release_date = fields.DateField()
    create_date = fields.DatetimeField(default=datetime.now)
    record_type = fields.CharEnumField(RecordType)
    status = fields.CharEnumField(TrackingStatus, default=TrackingStatus.Added)
    genres = fields.JSONField()
    label = fields.TextField()
    tracks = fields.JSONField()
    contributors = fields.JSONField()
    upc = fields.TextField()

    @property
    def album_url(self) -> str:
        return f"https://www.deezer.com/album/{self.id}"

    @property
    def download_path(self) -> str:
        # Reproduced and modified from the deemix-py source code:
        # https://gitlab.com/RemixDev/deemix-py/-/blob/main/deemix/utils/pathtemplates.py#L65
        foldername = DEEMIX_SETTINGS["albumNameTemplate"]
        substitutions = [
            ("%artist%", self.artist.name),
            ("%album%", self.title),
            ("%year%", str(self.release_date.year)),
        ]
        for template, value in substitutions:
            foldername = foldername.replace(template, value)

        return os.path.join(
            settings.DOWNLOAD_FOLDER, deemix_normalize_path(foldername), ""
        )


class Upload(Model):
    id = fields.IntField(pk=True, generated=True)
    upload_date = fields.DatetimeField(default=datetime.now)
    tracker_code = fields.CharEnumField(TrackerCode)
    torrent_id = fields.IntField(null=True)
    group_id = fields.IntField(null=True)
    album = fields.ForeignKeyField(
        "models.Album",
        related_name="uploads",
    )
    infohash = fields.CharField(max_length=40, unique=True)
    upload_parameters = fields.JSONField()
    file = fields.BinaryField()
