import json
import discord
from redbot.core.utils import chat_formatting, menus
from ..abc import Red, Config, commands, Context, MixinMeta, CompositeMetaClass
from ..cdt_core import CDT


json_urls = {
    "bcg_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/bcg_en.json",
    "bcg_stat_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/bcg_stat_en.json",
    "special_attacks_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/special_attacks_en.json",
    "masteries_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/masteries_en.json",
    "character_bios_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/character_bios_en.json",
    "cutscenes_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/Standard/cutscenes_en.json",
},
class ChampData(MixinMeta, metaclass=CompositeMetaClass):
    """A CollectorDevTeam package for Marvel"s Contest of Champions"""

    # @mcocgroup.group(aliases=("champ","champion","mcoc"))
    # async def champions(self, ctx):
    #     data = await CDT.create_embed(ctx, title="Marvel Contest of Champions")
    #     data.description = "dummy group"
        

    @commands.group(name="data")
    @CDT.is_collectordevteam()
    async def champions_data(self, ctx: Context):
        """Data commands""" 

    @champions_data.command(name="check", aliases=("words",))
    async def json_key_check(self, ctx, json_key=None):
        async with self.config.mcoc.words() as words:
            keys = words.keys()
            if json_key is None and len(keys) == 0:
                await ctx.send("There are currently {} json keys registered.".format(len(keys)))
            if json_key is None and len(keys) > 0:
                question = "json_key_check: There are currently {} json_keys registered.\nDo you want a listing?".format(len(keys))
                answer = await CDT.confirm(self, ctx, question)
                if answer:
                    listing = "\n".join(k for k in keys)
                    pages = list(chat_formatting.pagify(listing, page_length=1000))
                    await menus.menu(ctx, pages=pages, controls=CDT.get_controls(len(pages))) 
            elif json_key is not None and json_key in keys:
                await ctx.send("keys found.  testing")
                await ctx.send("{}".format(words[json_key]['v'])) # should be a dict of {"v": <something>, "vn": }
                await ctx.send("Version {}".format(words[json_key]['vn']))
            else:
                await ctx.send("{} not found in words".format(json_key))
        return


    @champions_data.command(name="delete", aliases=("purge",))
    async def champions_data_delete(self, ctx:Context, dataset):
        """MCOC data purge"""
        if dataset in ("snapshot", "snapshots", "words"):
            answer = await CDT.get_user_confirmation(self, ctx, "Do you want to delete {} dataset?".format(dataset))
            if answer:
                answer2 = await CDT.get_user_confirmation(self, ctx, "Are you sure?  This is a delete you moron.")
                if answer2:
                    if dataset == "snapshot" or dataset == "snapshots":
                        # async with self.config.snapshots() as snapshots:
                        #     snapshots.clear_all_globals()
                        await self.config.snapshots.clear_all_globals()
                        async with self.config.snapshots() as snapshots:
                            await ctx.send("Snapshots should be cleared.  {} keys registered".format(len(snapshots.keys())))
                    elif dataset == "words":
                        # async with self.config.words() as words:
                        await self.config.words.clear()
                        async with self.config.words() as words:
                            await ctx.send("Snapshots should be cleared.  {} keys registered".format(len(words.keys())))
        return
    

    @champions_data.group(name="import")
    async def champions_import(self, ctx: Context):
        """Data import commands
        snapshot - scrape data from translation files"""

    @champions_import.command(name="json")
    async def champions_import_json(self, ctx: Context, json_file=None):
        """Import champion json strings from snapshot json files.
        Collector accesses the remote assets repository and ingests the most recent snapshots bakcup.

        Args:
            ctx (Context): [description]
            json_file ([type], optional): [description]. Defaults to None.

        Returns:
            [type]: [description]
        """
        async with self.config.urls() as urls:
            jkeys = json_urls.keys()
            if json_file in jkeys:
                jkeys = [json_file] 
            for j in jkeys:
                filetext = await CDT.aiohttp_http_to_text(ctx, urls[j])
                if filetext is None:
                    continue
                if filetext is not None:
                    jsonfile = await CDT.convert_kabamfile_to_json(ctx, filetext)
                    if jsonfile is not None:
                        async with self.config.mcoc.words() as words:
                            words.update(jsonfile["strings"])
                        async with self.config.mcoc.snapshots() as snapshots:
                            snapshots.update({j : jsonfile})
                    else:
                        await ctx.send("textfile_to_json did not return json/dict")

    @champions_import.command(name="synergies")
    async def champions_import_synergies(self, ctx: Context):
        """Import Synergyes spreadsheet

        Args:
            ctx (Context): [description]
        """
        pass

    @champions_import.command(name="xref")
    async def champions_import_xref(self, ctx: Context):
        """Import CollectorDevTeam xref data

        Args:
            ctx (Context): [description]
        """
        xref_data = await CDT.cdt_gspread_get_xref(self)
        if xref_data is None:
            await ctx.send("Uh oh Captain! There was a problem.")
        else:
            await ctx.send("export_xref retrieved")

    @champions_import.command(name="info")
    async def champions_import_info(self, ctx: Context):
        """Import CollectorDevTeam xref data

        Args:
            ctx (Context): [description]
        """
        xref_data = await CDT.cdt_gspread_get_info(self)
        if xref_data is None:
            await ctx.send("Uh oh Captain! There was a problem.")
        else:
            await ctx.send("export_info retrieved")

