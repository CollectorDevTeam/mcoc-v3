# import discord
from collections import ChainMap
import aiohttp
# import json
from redbot.core import Config
from redbot.core import checks
from redbot.core import commands
from mcoc.CDT import CDT


class CDTDATA(commands.Cog):
    """
    CollectorDevTeam DataSets for Marvel Contest of Champions
    """

    __version__ = "1.0.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = Config.get_conf(self, cog_name="CDTDATA", 
                                      identifier=3246316013445447780012, force_registration=True)
        self.config.init_custom(group_identifier="prestige", identifier_count=1)
        self.config.init_custom(group_identifier="cdt_data", identifier_count=2)
        self.config.init_custom(group_identifier="cdt_stats", identifier_count=3)
        self.config.init_custom(group_identifier="cdt_masteries", identifier_count=4)
        _default_prestige = {
            "url1": "http://gsx2json.com/api?id=1I3T2G2tRV05vQKpBfmI04VpvP5LjCBPfVICDmuJsjks&sheet=2&columns=false&integers=false",
            "url2": CDT.BASEPATH + "jason/backup_prestige.json",
            "date": "",
            "info": "Champion Prestige",
            "keylist": "",
            "data": {}
        }
        _default_data = {
            "date": "",
            "info": "Kabam JSON translation data, aggregated",
            "keylist": "",
            "data": {},
            "versions": {}
        }
        _default_stats = {
            "url1": "http://gsx2json.com/api?id=1I3T2G2tRV05vQKpBfmI04VpvP5LjCBPfVICDmuJsjks&sheet=1&columns=false&integers=false",
            "url2": None,
            "date": "",
            "info": "CollectorDevTeam Champion Stats by Star by Rank",
            "keylist": "",
            "data": {}
        }
        _default_masteries = {
            "date": "",
            "info": "CollectorDevTeam Mastery information",
            "keylist": "",
            "data": {}
        }
        _default_global = {
        }
        self.config.register_custom("prestige", **_default_prestige)
        self.config.register_custom("cdt_data", **_default_data)
        self.config.register_custom("cdt_stats", **_default_stats)
        self.config.register_custom("cdt_masteries", **_default_masteries)
        # self.config.register_global(**_default_global)
        # self.config.register_global(**default_global)
        # self.config.register_guild(**default_guild)
        # self.config.register_user(**default_user)

    @commands.command()
    async def get_defaults(self, ctx):
        prestige = self.config.custom("prestige")
        await ctx.send("Prestige\nInfo: {}\nDate: {}".format(await prestige.info(), prestige.date()))
    # @commands.command()
    # @checks.is_owner()
    # async def clear_cdt_data(self, ctx):
    #     """Removes all CDTDATA and resets the global data schema.
    #     This cannot be undone."""
    #     await self.config.clear_all_globals()
    #     # await self.config.clear_all_custom()
    #     await ctx.send("All CDT data has been erased.")
    #
    # @commands.command()
    # @checks.is_owner()
    # async def check_cdt_data(self, ctx):
    #     """Check last data update"""
    #     CDTDATA = self.config  # should be treated as a dictionary now
    #     for x in ["prestige", "cdt_data", "cdt_stats", "cdt_versions", "cdt_masteries", "date_updated"]:
    #         print(CDTDATA.prestige.info())
    #         print(CDTDATA.cdt_stats.info())
    #         print(CDTDATA.date_updated.date())
    #
    # @commands.command()
    # @checks.is_owner()
    # async def load_cdt_data(self, ctx):
    #     """Load existing CDT Data
    #     Pull new CDT Data
    #     Verify new CDT Data
    #     Store new CDT Data
    #     Load new CDT Data into bot"""
    #     ctx.send("Creating file download manifest")
    #     cdt_data, cdt_versions = ChainMap(), ChainMap()
    #     files = {
    #         "bcg_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_en.json""",
    #         "bcg_stat_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_stat_en.json",
    #         "special_attacks": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/special_attacks_en.json",
    #         # "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/masteries_en.json",
    #         "character_bios_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/character_bios_en.json",
    #         # "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/dungeons_en.json",
    #         # "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/cutscenes_en.json",
    #         # "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/initial_en.json",
    #         # "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/alliances_en.json"
    #     }
    #
    #     ## PULL CDT Data
    #     ctx.send("Attempting to create aiohttp connection")
    #     async with aiohttp.ClientSession() as session:
    #         for url in files.keys():
    #             ctx.send("Retrieving {}".format(url))
    #             async with ctx.typing():
    #                 raw_data = await CDT.fetch_json(files[url], session)
    #                 val, ver = {}, {}
    #                 for dlist in raw_data["strings"]:
    #                     val[dlist["k"]] = dlist["v"]
    #                     if "vn" in dlist:
    #                         ver[dlist["k"]] = dlist["vn"]
    #                 cdt_data.maps.append(val)
    #                 cdt_versions.maps.append(ver)
    #
    #     ## TEST CDT DATA VALIDITY
    #
    #     ## IF PASS Load into Config
    #     await self.config.cdt_data.nested_update(cdt_data)
    #     # await self.config.cdt_data.set({"keys" : cdt_data.keys()})
    #     await self.config.cdt_versions.nested_update(cdt_versions)
    #     await self.config.date_updated.date.set(ctx.message.timestamp)


    @commands.Command
    async def get_prestige(self, ctx):
        await self._get_prestige(ctx)


    async def _get_prestige(self, ctx):
        prestige = self.config.custom("prestige")
        await ctx.send("The info statement will test accessing nested information.")
        await ctx.send("Prestige Info: {}".format(await prestige.info()))
        await ctx.send("Attempting Prestige1: {}".format(await prestige.url1()))
        prestige_json = await CDT.fetch_json(ctx, await prestige.url1())
        print(prestige_json.keys())
        if prestige_json == "{}":
            ctx.say("Prestige retrieval timeout.  Loading backup.")
            await ctx.send("Attempting Backup Prestige: {}".format(await prestige.url2()))
            prestige_json = await CDT.fetch_json(ctx, await prestige.url2())
        async with ctx.typing():
            data = {}
            rows = prestige_json["rows"] #[0]
            # await ctx.send(update.keys())
            for row in rows:
                unique = row.pop("mattkraftid")
                print(unique)
                print(row)
                data.update({unique: row})
                await prestige.data.nested_update({unique: row})
                # await prestige.set_raw("data", unique, value=row)
            await prestige.date.set(ctx.message.timestamp())
            await ctx.send("Prestige data looped")

            # await ctx.send(len(data))
            # await self.config.prestige.data.nested_update(update)
        # if update["5-karnak-5"]["sig0"] is not None:
        #     ctx.say("Prestige test passed")
