import os

from datetime import datetime

from tortoise.models import Model
from tortoise import fields

from deemix.utils.pathtemplates import fixName as deemix_normalize_path

from .settings import DEEMIX_SETTINGS, settings

from .schemas import RecordType, TrackerCode


class DeezerArtistTortoise(Model):
    id = fields.IntField(pk=True)
    name = fields.TextField()
    image_url = fields.TextField()
    nb_album = fields.IntField()
    nb_fan = fields.IntField()
    reviewed = fields.BooleanField(default=False)


class DeezerAlbumTortoise(Model):
    id = fields.IntField(pk=True)
    title = fields.TextField()
    image_url = fields.TextField()
    release_date = fields.DateField()
    record_type = fields.CharEnumField(RecordType)
    artist = fields.ForeignKeyField(
        "models.DeezerArtistTortoise",
        related_name="albums",
    )
    create_date = fields.DatetimeField(default=datetime.now)
    ready_to_add = fields.BooleanField(default=False)

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


class UploadTortoise(Model):
    id = fields.IntField(pk=True, generated=True)
    infohash = fields.CharField(max_length=40, unique=True)
    upload_date = fields.DatetimeField(default=datetime.now)
    upload_parameters = fields.JSONField()
    file = fields.BinaryField()
    tracker_code = fields.CharEnumField(TrackerCode)
    uploaded_torrent_id = fields.IntField(null=True)
    uploaded_group_id = fields.IntField(null=True)
    album = fields.ForeignKeyField(
        "models.DeezerAlbumTortoise",
        related_name="uploads",
    )
