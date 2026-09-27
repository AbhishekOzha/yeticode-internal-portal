"""Checks for chat voice messages recorded in the browser."""

from django.core.exceptions import ValidationError

MAX_VOICE_BYTES = 5 * 1024 * 1024
MAX_VOICE_SECONDS = 5 * 60

# Browsers record WebM/Opus (Chrome, Firefox, Edge) or MP4/AAC (Safari).
FORMATS = {"webm": "audio/webm", "ogg": "audio/ogg", "m4a": "audio/mp4", "mp3": "audio/mpeg", "wav": "audio/wav"}


def sniff(head):
    """The audio format from a file's first bytes, or None."""
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    if head.startswith(b"OggS"):
        return "ogg"
    if head[4:8] == b"ftyp":
        return "m4a"
    if head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "wav"
    return None


def check_voice(file):
    """Return the file's format, or raise if it isn't a small audio recording."""
    if file.size > MAX_VOICE_BYTES:
        raise ValidationError("Voice messages can be at most 5 MB.")
    file.seek(0)
    kind = sniff(file.read(16))
    file.seek(0)
    if kind is None:
        raise ValidationError("That file isn't a supported audio recording.")
    return kind
