# import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
import aiohttp
from collections import ChainMap
from mcoc.lib_cdt.cdt_library import CDT


class CDTDATA(commands.Cog):
    """
    CollectorDevTeam DataSets for Marvel Contest of Champions
    """

    __version__ = "1.0.0"

    def __init__(self):
        self.config = Config.get_conf(self, cog_name="CDTDATA", identifier=CDT.ID, force_registration=True)
        _default_global = {
            "prestige": {
                "info": "Champion Prestige",
                "keys": ""
            },
            "cdt_data": {
                "info": "Kabam JSON translation data, aggregated",
                "keys": ""
            },
            "cdt_stats": {
                "info": "CollectorDevTeam Champion Stats by Star by Rank",
                "keys": ""
            },
            "cdt_versions": {
                "info": "Champions Verions tracking 12.0+",
                "keys": ""
            },
            "cdt_masteries": {
                "info": "CollectorDevTeam Mastery information",
                "keys": ""
            },
            "date_updated": {
                "date": "Never",
            }
        }

        self.config.register_global(**_default_global)
        # self.config.register_global(**default_global)
        # self.config.register_guild(**default_guild)
        # self.config.register_user(**default_user)

    @commands.command()
    @checks.is_owner()
    async def clear_cdt_data(self, ctx):
        '''Removes all CDTDATA and resets the global data schema.
        This cannot be undone.'''
        await self.config.clear_all_globals()
        # await self.config.clear_all_custom()
        await ctx.send("All CDT data has been erased.")

    @commands.command()
    @checks.is_owner()
    async def check_cdt_data(self, ctx):
        '''Check last data update'''
        CDTDATA = self.config #should be treated as a dictionary now
        for x in ["prestige", "cdt_data", "cdt_stats", "cdt_versions", "cdt_masteries", "date_updated"]:
            print(CDTDATA.prestige.info())
            print(CDTDATA.cdt_stats.info())
            print(CDTDATA.date_updated.date())

    @commands.command()
    @checks.is_owner()
    async def load_cdt_data(self, ctx):
        """Load existing CDT Data
        Pull new CDT Data
        Verify new CDT Data
        Store new CDT Data
        Load new CDT Data into bot"""
        ctx.send("Creating file download manifest")
        cdt_data, cdt_versions = ChainMap(), ChainMap()
        files = {
            "bcg_en" : 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_en.json',
            "bcg_stat_en" : 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_stat_en.json',
            "special_attacks" : 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/special_attacks_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/masteries_en.json',
            "character_bios_en" : 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/character_bios_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/dungeons_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/cutscenes_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/initial_en.json',
            # 'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/alliances_en.json'
        }

        ## PULL CDT Data
        ctx.send("Attempting to create aiohttp connection")
        async with aiohttp.ClientSession() as session:
            for url in files.keys():
                ctx.send("Retrieving {}".format(url))
                async with ctx.typing():
                    raw_data = await CDT.fetch_json(files[url], session)
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
        # await self.config.cdt_data.set({"keys" : cdt_data.keys()})
        await self.config.cdt_versions.nested_update(cdt_versions)
        await self.config.date_updated.date.set(ctx.message.timestamp)



