import aiohttp
import discord

from abc import ABC, abstractmethod
from redbot.core import commands, Config
from redbot.core.bot import Red

from typing import Union
from logging import Logger


__all__ = ["AllianceMixin", "AllianceMeta"]


class AllianceMixin(ABC):
    def __init__(self, *_args):
        self.config: Config
        self.bot: Red
        self.session: aiohttp.ClientSession
        self.log: Logger

    @abstractmethod
    async def _validate_url(self, url: str) -> Union[str, bool]:
        ...


class AllianceMeta(type(ABC), type(commands.Cog)):
    pass
