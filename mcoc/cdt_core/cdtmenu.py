import contextlib
from ..abc import MixinMeta
from redbot.core.utils.menus import menu, close_menu, next_page, prev_page
import discord
from redbot.core.commands import Context

class CdtMenu(MixinMeta):
    """Extend the Menu system to provide CDT functions"""

    async def menusets(list_of_lists):
        """Provide two or more menu page sets.  

        Args:
            list_of_lists ([type]): [description]
        """



    # async def nextp(*args, **kwargs):
    #     nonlocal selected
    #     if selected == (len(cache) - 1):
    #         selected = 0
    #     else:
    #         selected += 1
    #     await next_page(*args, **kwargs)

    # async def prevp(*args, **kwargs):
    #     nonlocal selected
    #     if selected == 0:
    #         selected = len(cache) - 1
    #     else:
    #         selected -= 1
    #     await prev_page(*args, **kwargs)

            
    def get_controls(int = 0):
        controls = {
            "◀️": prev_page,
            "❌": close_menu,
            "▶️": next_page,
        }
        big_controls = {
            "⏪": page_minus_five,
            "◀️": prev_page,
            "❌": close_menu,
            "▶️": next_page,
            "⏩": page_plus_five,
        }
        if int is not None and int > 8:
            return big_controls
        return controls

    def get_roster_export_controls(export_function):
        controls = {
            "◀️": prev_page,
            "❌": close_menu,
            "▶️": next_page,
            "💾" : export_function, ## REMAP this control to Roster Export
        }
        return controls


    def get_swap_controls():
        controls = {
            "◀️": prev_page,
            "❌": close_menu,
            "▶️": next_page,
            # "🔄": pages_swap,
        }

async def page_minus_five(
    ctx: Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
):
    """Extending Red menu controls to page +5 at a time for large pages menus"""
    perms = message.channel.permissions_for(ctx.me)
    if perms.manage_messages:  # Can manage messages, so remove react
        with contextlib.suppress(discord.NotFound):
            await message.remove_reaction(emoji, ctx.author)
    if page == len(pages) - 1:
        page = 0  # Loop around to the first item
    else:
        page = page + 5
    return await menu(ctx, pages, controls, message=message, page=page, timeout=timeout)

async def page_plus_five(
    ctx: Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
):
    """Extending Red menu controls to page +5 at a time for large pages menus"""
    perms = message.channel.permissions_for(ctx.me)
    if perms.manage_messages:  # Can manage messages, so remove react
        with contextlib.suppress(discord.NotFound):
            await message.remove_reaction(emoji, ctx.author)
    if page == len(pages) - 1:
        page = 0  # Loop around to the first item
    else:
        page = page - 5
    return await menu(ctx, pages, controls, message=message, page=page, timeout=timeout)


# async def pages_swap(
#     ctx: Context,
#     pages: list,
#     controls: dict,
#     message: discord.Message,
#     page: int,
#     timeout: float,
#     emoji: str,
#     ):
#     perms = message.channel.permissions_for(ctx.me)
#     if perms.manage_messages:  # Can manage messages, so remove react
#         with contextlib.suppress(discord.NotFound):
#             await message.remove_reaction(emoji, ctx.author)
#     page = 0
#     return await menu(ctx, pages, controls, message=message, page=page, timeout=timeout)