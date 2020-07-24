import discord
import requests
from validator_collection import validators


class Embed:
    def __init__(self, bot):
        self.bot = bot

    def create(self, ctx, color=discord.Color.gold(), title='', description='', image=None,
               thumbnail=None, url=None, footer_text=None, footer_url=None, author_text=None):
        '''Return a color styled embed with CDT footer, and optional title or description.
        user_id = user id string. If none provided, takes message author.
        color = manual override, otherwise takes gold for private channels, or author color for guild.
        title = String, sets title.
        description = String, sets description.
        image = String url.  Validator checks for valid url.
        thumbnail = String url. Validator checks for valid url.'''
        COLLECTOR_ICON = 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_icon.png'
        PATREON = 'https://patreon.com/collectorbot'
        CDT_LOGO = 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/cdt_logo.png'

        if isinstance(ctx.message.channel, discord.abc.GuildChannel):
            color = ctx.message.author.color
        if url is None:
            url = PATREON
        data = discord.Embed(color=color, title=title, url=url)
        if description is not None:
            if len(description) < 1500:
                data.description = description
        data.set_author(name=ctx.message.author.display_name,
                        icon_url=ctx.message.author.avatar_url)
        if image is not None:
            validators.url(image)
            code = requests.get(image).status_code
            if code == 200:
                data.set_image(url=image)
            else:
                print('Image URL Failure, code {}'.format(code))
                print('Attempted URL:\n{}'.format(image))
        if thumbnail is None:
            thumbnail = CDT_LOGO
        if thumbnail is not None:
            validators.url(thumbnail)
            code = requests.get(thumbnail).status_code
            if code == 200:
                # data.set_thumbnail(url=thumbnail)
                data.set_thumbnail(
                    url=thumbnail)
            else:
                data.set_thumbnail(url=CDT_LOGO)
                print('Thumbnail URL Failure, code {}'.format(code))
                print('Attempted URL:\n{}'.format(thumbnail))
        if footer_text is None:
            footer_text = "Collector | Contest of Champions | CollectorDevTeam"
        if footer_url is None:
            footer_url = CDT_LOGO
        data.set_footer(text=footer_text, icon_url=footer_url)
        return data
