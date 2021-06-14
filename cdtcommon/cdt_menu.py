from redbot.vendored.discord.ext import menus
import discord

from .cdtembed import Embed

from contextlib import suppress


emojis = (
    "<:arrowleft:735628703610044488>",
    "<:circlex:735628703530483814>",
    "<:arrowright:735628703840600094>",
)


class CDTPage(menus.ListPageSource):
    def __init__(self, pages: list):
        super().__init__(pages, per_page=1)

    def is_paginating(self) -> bool:
        return True

    async def format_page(self, menu: menus.MenuPages, page: str):
        footer = f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        title = "CDT Menu"
        if await menu.ctx.embed_requested():
            return await Embed.create(menu.ctx, title=title, description=page, footer_text=footer)
        return f"{title}\n\n{page}\n{footer}"


class CDTMenu(menus.MenuPages, inherit_buttons=False):
    def __init__(self, source: CDTPage):
        super().__init__(source, clear_reactions_after=True)

    def _skip_single_buttons(self):
        max_pages = self._source.get_max_pages()
        if max_pages is None:
            return True
        return max_pages == 1

    @menus.button(emojis[0], skip_if=_skip_single_buttons)
    async def go_to_previous_page(self, pl):
        await self.show_checked_page(self.current_page - 1)

    @menus.button(emojis[1])
    async def stop_pages(self, pl):
        self.stop()
        with suppress(discord.NotFound):
            await self.message.delete()

    @menus.button(emojis[2], skip_if=_skip_single_buttons)
    async def go_to_next_page(self, pl):
        await self.show_checked_page(self.current_page + 1)
