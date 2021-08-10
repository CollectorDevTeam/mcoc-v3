from .abc import AllianceMixin
from typing import Union

__all__ = ["Validator", "BadImage"]
_good_extensions = (
    ".png", ".jpg", ".jpeg", ".gif"
)
_imgur_links = ("http://imgur.com", "https://m.imgur.com", "https://imgur.com")


class BadImage(Exception):
    def __init__(self, url: str):
        super().__init__(f"Bad url: {url}")


class Validator(AllianceMixin):
    async def _validate_url(self, url: str) -> Union[bool, str]:
        async with self.session.get(url) as re:
            if re.status != 200:
                raise BadImage
        if url.startswith(_imgur_links):
            url += ".png"
        elif url.endswith(".mp4"):
            url = url[:-3] + "gif"
        elif url.endswith(".gifv"):
            url = url[:-1]
        elif not url.endswith(_good_extensions) and not url.startswith("https://gfycat.com"):
            return False
        return url
