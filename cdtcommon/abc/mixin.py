from redbot.core import commands


@commands.group(name="cdt")  #eventually hide ?
async def cdtcommands(self, ctx: commands.Context, invoke_without_command=True):
    """Group command for CDT Common functions"""
    pass

class CDTMixin:
    """ This is mostly here to easily mess with things... """

    c = cdtcommands