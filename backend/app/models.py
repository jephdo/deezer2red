import enum

from datetime import datetime

from tortoise.models import Model
from tortoise import fields


class RecordType(enum.Enum):
    ALBUM = "album"
    EP = "ep"
    SINGLE = "single"


class DeezerArtistTortoise(Model):
    id = fields.IntField(pk=True)
    name = fields.TextField()
    image_url = fields.TextField()
    nb_album = fields.IntField()
    nb_fan = fields.IntField()


class DeezerAlbumTortoise(Model):
    id = fields.IntField(pk=True)
    title = fields.TextField(null=False)
    image_url = fields.TextField(null=False)
    release_date = fields.DateField(null=False)
    record_type = fields.CharEnumField(RecordType)
    artist = fields.ForeignKeyField(
        "models.DeezerArtistTortoise", related_name="albums", null=False
    )


class Torrent(Model):
    id = fields.IntField(pk=True, generated=True)
    create_date = fields.DatetimeField(default=datetime.now)
    album = fields.ForeignKeyField("models.DeezerAlbumTortoise", related_name="torrent")
    # download_path str

    def get_download_path(self) -> str:
        return ""


class Upload(Model):
    id = fields.IntField(pk=True, generated=True)
    infohash = fields.CharField(max_length=40, unique=True)
    upload_date = fields.DatetimeField()
    upload_parameters = fields.JSONField()
    file = fields.BinaryField()
    # tracker = fields.CharEnumField()
    uploaded_id = fields.IntField()
