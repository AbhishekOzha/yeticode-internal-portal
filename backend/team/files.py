"""Checks for files shared in team chat: documents, spreadsheets, slides, images, archives."""

from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

MAX_FILE_BYTES = 20 * 1024 * 1024

# Extension -> content type it is served with. Anything that a browser could run
# (HTML, SVG, JavaScript, executables) is deliberately not on this list.
ALLOWED = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "odt": "application/vnd.oasis.opendocument.text",
    "rtf": "application/rtf",
    "txt": "text/plain",
    "md": "text/plain",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "csv": "text/csv",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "zip": "application/zip",
    "rar": "application/vnd.rar",
    "7z": "application/x-7z-compressed",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}
IMAGES = {"png", "jpg", "jpeg", "gif", "webp"}
# Office files are ZIP containers (docx/xlsx/pptx/od*) or OLE files (doc/xls/ppt).
SIGNATURES = {
    "pdf": [b"%PDF"],
    "zip": [b"PK\x03\x04", b"PK\x05\x06"],
    "docx": [b"PK\x03\x04"], "xlsx": [b"PK\x03\x04"], "pptx": [b"PK\x03\x04"],
    "odt": [b"PK\x03\x04"], "ods": [b"PK\x03\x04"], "odp": [b"PK\x03\x04"],
    "doc": [b"\xd0\xcf\x11\xe0"], "xls": [b"\xd0\xcf\x11\xe0"], "ppt": [b"\xd0\xcf\x11\xe0"],
    "rar": [b"Rar!"],
    "7z": [b"7z\xbc\xaf\x27\x1c"],
    "rtf": [b"{\\rtf"],
}


def extension_of(name):
    return Path(name).suffix.lower().lstrip(".")


def check_attachment(file):
    """Return the file's extension, or raise if it isn't an allowed, reasonably sized file."""
    if file.size > MAX_FILE_BYTES:
        raise ValidationError("Files can be at most 20 MB.")
    if file.size == 0:
        raise ValidationError("That file is empty.")
    extension = extension_of(file.name)
    if extension not in ALLOWED:
        raise ValidationError(
            "This type of file can't be shared. Use documents, spreadsheets, slides, PDFs, images or ZIP files."
        )
    file.seek(0)
    head = file.read(16)
    file.seek(0)
    if extension in IMAGES:
        try:
            with Image.open(file) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
            raise ValidationError("That image file is damaged or isn't really an image.")
        finally:
            file.seek(0)
    elif extension in SIGNATURES and not any(head.startswith(sig) for sig in SIGNATURES[extension]):
        raise ValidationError(f"That file doesn't look like a real .{extension} file.")
    elif extension in {"txt", "md", "csv"} and b"\x00" in head:
        raise ValidationError(f"That file doesn't look like a real .{extension} file.")
    return extension
