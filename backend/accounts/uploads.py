"""Image uploads: profile photos and the company logo.

Files are checked by opening them with Pillow, not by trusting the file name
or the browser's content type. SVG is not accepted because it can carry
scripts.
"""

import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 2 * 1024 * 1024
IMAGE_FORMATS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}


def validate_image(file):
    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError("Images must be 2 MB or smaller.")
    try:
        file.seek(0)
        with Image.open(file) as image:
            image_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ValidationError("Upload a PNG, JPG or WebP image.")
    finally:
        file.seek(0)
    if image_format not in IMAGE_FORMATS:
        raise ValidationError("Upload a PNG, JPG or WebP image.")


def random_name(folder, filename):
    """A random file name, so an old URL never shows a newer picture."""
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension == "jpeg":
        extension = "jpg"
    if extension not in IMAGE_FORMATS.values():
        extension = "png"
    return f"{folder}/{uuid.uuid4().hex}.{extension}"


def avatar_upload_to(instance, filename):
    return random_name("avatars", filename)


def logo_upload_to(instance, filename):
    return random_name("branding", filename)


def file_url(field_file):
    return field_file.url if field_file else None


def delete_replaced_file(old_name, field_file):
    """Remove the previous file from storage once it has been replaced or cleared."""
    if old_name and old_name != field_file.name:
        field_file.storage.delete(old_name)
