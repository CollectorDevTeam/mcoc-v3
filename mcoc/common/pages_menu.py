import discord
from redbot.core import commands
from collections import namedtuple, OrderedDict

class PagesMenu:
    '''CollectorDevTeam Pages Menu'''

    EmojiReact = namedtuple('EmojiReact', 'emoji include page_inc')

    def __init__(self, bot, *, add_pageof=True, timeout=30, choice=False,
            delete_onX=True):
        self.bot = bot
        self.timeout = timeout
        self.add_pageof = add_pageof
        self.choice = choice
        self.delete_onX = delete_onX
        self.embedded = True

    async def menu_start(self, pages):
        page_list = []
        if isinstance(pages, list):
            page_list = pages
        else:
            for page in pages:
                page_list.append(page)
        page_length = len(page_list)
        if page_length == 1:
            await ctx.send(embed=page_list[0])
            return
        self.embedded = isinstance(page_list[0], discord.Embed)
        self.all_emojis = OrderedDict([(i.emoji, i) for i in (
            self.EmojiReact("\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}", page_length > 5, -5),
            self.EmojiReact("\N{BLACK LEFT-POINTING TRIANGLE}", True, -1),
            self.EmojiReact("\N{CROSS MARK}", True, None),
            self.EmojiReact("\N{BLACK RIGHT-POINTING TRIANGLE}", True, 1),
            self.EmojiReact("\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}", page_length > 5, 5),
                      )])

        print('menu_pages is embedded: '+str(self.embedded))

        if self.add_pageof:
            for i, page in enumerate(page_list):
                if isinstance(page, discord.Embed):
                    ftr = page.footer
                    page.set_footer(text='{} (Page {} of {})'.format(ftr.text,
                            i+1, page_length), icon_url=ftr.icon_url)
                else:
                    page += '\n(Page {} of {})'.format(i+1, page_length)

        self.page_list = page_list
        await self.display_page(None, 0)

    async def display_page(self, message, page):
        if not message:
            if isinstance(self.page_list[page], discord.Embed) == True:
                message = await ctx.send(embed=self.page_list[page])
            else:
                message = await ctx.send(self.page_list[page])
            self.included_emojis = set()
            for emoji in self.all_emojis.values():
                if emoji.include:
                    await self.bot.add_reaction(message, emoji.emoji)
                    self.included_emojis.add(emoji.emoji)
        else:
            if self.embedded == True:
                message = await self.bot.edit_message(message, embed=self.page_list[page])
            else:
                message = await self.bot.edit_message(message, self.page_list[page])
        await asyncio.sleep(1)

        react = await self.bot.wait_for_reaction(message=message,
                timeout=self.timeout, emoji=self.included_emojis)
        if react is None:
            try:
                await self.bot.clear_reactions(message)
            except discord.Forbidden:
                logger.warn("clear_reactions didn't work")
                for emoji in self.included_emojis:
                    await self.bot.remove_reaction(message, emoji, self.bot.user)
            return None

        emoji = react.reaction.emoji
        pages_to_inc = self.all_emojis[emoji].page_inc if emoji in self.all_emojis else None
        if pages_to_inc:
            next_page = (page + pages_to_inc) % len(self.page_list)
            try:
                await self.bot.remove_reaction(message, emoji, react.user)
                await self.display_page(message=message, page=next_page)
            except discord.Forbidden:
                await self.bot.delete_message(message)
                await self.display_page(message=None, page=next_page)
        elif emoji == '\N{CROSS MARK}':
            try:
                if self.delete_onX:
                    await self.bot.delete_message(message)
                else:
                    await self.bot.clear_reactions(message)
            except discord.Forbidden:
                await ctx.send("Bot does not have the proper Permissions")
