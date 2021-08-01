import discord
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.utils import chat_formatting, menus
from ..abc import CompositeMetaClass, MixinMeta, mcoccommands
from ..cdtcore import CDT

class ChampData(MixinMeta, metaclass=CompositeMetaClass):
    """A CollectorDevTeam package for Marvel"s Contest of Champions"""

    # @mcoccommands.group(aliases=("champ","champion","mcoc"))
    # async def champions(self, ctx):
    #     data = await CDT.create_embed(ctx, title="Marvel Contest of Champions")
    #     data.description = "dummy group"
        

    @mcoccommands.group(name="data", hidden=True)
    @CDT.is_collectordevteam()
    async def champions_data(self, ctx):
        """Data commands""" 

    @champions_data.command(name="check", aliases=("words",))
    async def json_key_check(self, ctx, json_key=None):
        async with self.config.words() as words:
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
    async def champions_data_delete(self, ctx, dataset):
        """MCOC data purge"""
        if dataset in ("snapshot", "snapshots", "words"):
            answer = await CDT.get_user_confirmation(self, ctx, "Do you want to delete {} dataset?".format(dataset))
            if answer:
                answer2 = await CDT.get_user_confirmation(self, ctx, "Are you sure?  This is a delete you moron.")
                if answer2:
                    if dataset is "snapshot" or dataset is "snapshots":
                        # async with self.config.snapshots() as snapshots:
                        #     snapshots.clear_all_globals()
                        await self.config.snapshots.clear_all_globals()
                        async with self.config.snapshots() as snapshots:
                            await ctx.send("Snapshots should be cleared.  {} keys registered".format(len(snapshots.keys())))
                    elif dataset is "words":
                        # async with self.config.words() as words:
                        await self.config.words.clear_all_globals()
                        async with self.config.words() as words:
                            await ctx.send("Snapshots should be cleared.  {} keys registered".format(len(words.keys())))
        return
    

    @champions_data.group(name="import")
    async def champions_import(self, ctx):
        """Data import commands
        snapshot - scrape data from translation files"""

    @champions_import.command(name="json")
    async def champions_import_json(self, ctx, json_file=None):
        async with self.config.urls() as urls:
            jkeys = urls.keys()
            if json_file in jkeys:
                jkeys = [json_file] 
            for j in jkeys:
                filetext = await CDT.aiohttp_http_to_text(ctx, urls[j])
                if filetext is None:
                    continue
                if filetext is not None:
                    jsonfile = await CDT.convert_kabamfile_to_json(ctx, filetext)
                    if jsonfile is not None:
                        async with self.config.words() as words:
                            words.update(jsonfile["strings"])
                        async with self.config.snapshots() as snapshots:
                            snapshots.update({j : jsonfile})
                    else:
                        await ctx.send("textfile_to_json did not return json/dict")



