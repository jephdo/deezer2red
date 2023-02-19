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
    reviewed = fields.BooleanField(default=False)


class DeezerAlbumTortoise(Model):
    id = fields.IntField(pk=True)
    title = fields.TextField(null=False)
    image_url = fields.TextField(null=False)
    release_date = fields.DateField(null=False)
    record_type = fields.CharEnumField(RecordType)
    artist = fields.ForeignKeyField(
        "models.DeezerArtistTortoise", related_name="albums", null=False
    )


class TorrentTortoise(Model):
    id = fields.IntField(pk=True)
    create_date = fields.DatetimeField(default=datetime.now)
    album = fields.ForeignKeyField("models.DeezerAlbumTortoise")
    download_path = fields.TextField()


class UploadTortoise(Model):
    id = fields.IntField(pk=True, generated=True)
    infohash = fields.CharField(max_length=40, unique=True)
    upload_date = fields.DatetimeField()
    upload_parameters = fields.JSONField()
    file = fields.BinaryField()
    # tracker = fields.CharEnumField()
    uploaded_id = fields.IntField()
