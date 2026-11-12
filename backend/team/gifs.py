"""GIF and sticker search for chat, proxied to Giphy so the API key stays on the server.

A GIF or sticker is sent as a normal chat message whose body is its Giphy URL; the apps show it as a picture.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import IsTeamMember

LIMIT = 24


class GifsUnavailable(APIException):
    status_code = 503
    default_detail = "GIFs and stickers aren't set up. Add GIPHY_API_KEY to the server's .env."


def giphy(kind, query):
    endpoint = "search" if query else "trending"
    params = {"api_key": settings.GIPHY_API_KEY, "limit": LIMIT, "rating": "g"}
    if query:
        params["q"] = query
    url = f"https://api.giphy.com/v1/{kind}/{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=6) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise APIException("Couldn't reach the GIF service. Try again in a moment.")


class GifSearchView(APIView):
    """GET ?q=<words>&type=gifs|stickers (no q = trending)."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        if not settings.GIPHY_API_KEY:
            raise GifsUnavailable()
        kind = request.query_params.get("type", "gifs")
        if kind not in ("gifs", "stickers"):
            raise ValidationError({"type": "Use gifs or stickers."})
        data = giphy(kind, request.query_params.get("q", "").strip()[:60])
        results = []
        for item in data.get("data", []):
            images = item.get("images", {})
            full = images.get("fixed_height", {}).get("url") or images.get("original", {}).get("url")
            small = images.get("fixed_width_small", {}).get("url") or images.get("fixed_width", {}).get("url") or full
            if full:
                results.append({"id": item.get("id"), "url": full.split("?")[0], "preview": (small or full).split("?")[0]})
        return Response({"results": results})
