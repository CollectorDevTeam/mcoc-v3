# import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
import aiohttp
import json
from collections import defaultdict, ChainMap, namedtuple, OrderedDict
from .collectordevteam import CDT
#
# BaseCog = getattr(commands, "Cog", object)
#
# remote_data_basepath = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/"
# GOOGLECREDENTIALS = ''
#
#
class CDTDATA(commands.Cog):
    """
    CollectorDevTeam DataSets for Marvel Contest of Champions
    """

    __version__ = "1.0.0"

    def __init__(self):
        CDTDATA_ID = 3246316013445447780012
        self.config = Config.get_conf(self, identifier=CDTDATA_ID, force_registration=True)
        _default_global = {
            "prestige": {
                "info": "Champion Prestige"
            },
            "cdt_data": {
                "info": "Kabam JSON translation data, aggregated"
            },
            "cdt_stats": {
                "info": "CollectorDevTeam Champion Stats by Star by Rank"
            },
            "cdt_versions": {
                "info": "Champions Verions tracking 12.0+"
            },
            "cdt_masteries": {
                "info": "CollectorDevTeam Mastery information"
            },
            "date_updated": {
                "date": "Never"
            }
        }

        self.config.register_global(**_default_global)
        # self.config.register_guild(**default_guild)
        # self.config.register_user(**default_user)


    @commands.command()
    @checks.is_owner()
    async def clear_cdt_data(self, ctx):
        '''Removes all CDTDATA and resets the global data schema.
        This cannot be undone.'''
        await self.config.clear_all_globals()
        await ctx.send("All global data has been erased.")


    @commands.command()
    @checks.is_owner()
    async def check_cdt_data(self, ctx):
        '''Check last data update'''
        await ctx.send("attempting CDTDATA.get_raw")
        await ctx.send("CDTDATA last updated: {}".format(await self.config.date_updated()))
        # await ctx.send("attempting CDTDATA.get_attr")
        # await ctx.send("CDTDATA last upated: {}".format(await self.CDTDATA.updated.get_attr("date")))



    async def load_cdt_data(self, ctx):
        """Load existing CDT Data
        Pull new CDT Data
        Verify new CDT Data
        Store new CDT Data
        Load new CDT Data into bot"""
        cdt_data, cdt_versions = ChainMap(), ChainMap()
        files = (
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_stat_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/special_attacks_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/masteries_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/character_bios_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/dungeons_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/cutscenes_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/initial_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/alliances_en.json'
        )

        ## PULL CDT Data
        async with ctx.typing():
            async with aiohttp.ClientSession() as session:
                for url in files:
                    raw_data = await CDT.fetch_json(url, session)
                    val, ver = {}, {}
                    for dlist in raw_data['strings']:
                        val[dlist['k']] = dlist['v']
                        if 'vn' in dlist:
                            ver[dlist['k']] = dlist['vn']
                    cdt_data.maps.append(val)
                    cdt_versions.maps.append(ver)

        ## TEST CDT DATA VALIDITY

        ## IF PASS Load into Config
        await self.config.cdt_data.nested_update(cdt_data)
        await self.config.cdt_versions.nested_update(cdt_versions)
        await self.config.date_updated.date.set(ctx.message.timestamp)



