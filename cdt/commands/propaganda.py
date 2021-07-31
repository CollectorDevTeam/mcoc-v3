from ..abc.mixin import CDTMixin, cdtcommands
from ..abc.cdt import CDT
import discord
import random


class CDTPromote(CDTMixin):

    @cdtcommands.command(name="promote", aliases=("promo",))
    @CDT.is_collectorsupportteam()
    async def cdt_promote(self, ctx, channel: discord.TextChannel, *, content):
        """Content will fill the embed description.
        title; content will split the message into Title and Content.
        An image attachment added to this command will replace the image embed."""
        if len(ctx.message.attachments) > 0:
            image = ctx.message.attachments[0]
            imgurl = image.url
        else:
            imagelist = [
                "https://cdn.discordapp.com/attachments/391330316662341632/725045045794832424/collector_dadjokes.png",
                "https://cdn.discordapp.com/attachments/391330316662341632/725054700457689210/dadjokes2.png",
                "https://cdn.discordapp.com/attachments/391330316662341632/725055822023098398/dadjokes3.png",
                "https://cdn.discordapp.com/attachments/391330316662341632/725056025404637214/dadjokes4.png",
                "https://media.discordapp.net/attachments/391330316662341632/727598814327865364/D1F5DE64D72C52880F61DBD6B2142BC6C096520D.png",
                "https://media.discordapp.net/attachments/391330316662341632/727598813820485693/8952A192395C772767ED1135A644B3E3511950BA.jpg",
                "https://media.discordapp.net/attachments/391330316662341632/727598813447192616/D77D9C96DC5CBFE07860B6211A2E32448B3E3374.jpg",
                "https://media.discordapp.net/attachments/391330316662341632/727598812746612806/9C15810315010F5940556E48A54C831529A35016.jpg",
            ]
            imgurl = random.choice(imagelist)
       
        data = await CDT.create_embed(
            ctx, title="CollectorVerse Tips:sparkles:", description=content, image=imgurl
        )

        data.set_author(
            name="{} of CollectorDevTeam".format(ctx.author.display_name),
            icon_url=ctx.author.avatar_url,
        )
        data.add_field(
            name="Alliance Template",
            value="[Make an Alliance Guild](https://discord.new/gtzuXHq2kCg4)\nRoles, Channels & Permissions pre-defined",
            inline=False,
        )
        data.add_field(
            name="Get Collector",
            value="[Invite](https://discord.com/oauth2/authorize?client_id=210480249870352385&scope=bot&permissions=8)",
            inline=False,
        )
        data.add_field(
            name="Support",
            value="[CollectorDevTeam Guild](https://discord.gg/BwhgZxk)",
            inline=False,
        )
        await channel.send(embed=data)
