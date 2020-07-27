import discord
import requests
from .cdtembed import Embed
from redbot.core import commands, checks
from redbot.core.config import Config

files = {
    "bcg_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_en.json",
    "bcg_stat_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_stat_en.json",
    "special_attacks_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/special_attacks_en.json",
    "masteries_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/masteries_en.json",
    "character_bios_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/character_bios_en.json",
    "cutscenes_en": "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/cutscenes_en.json",
    # "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/dungeons_en.json",
    # "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/initial_en.json",
    # "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/alliances_en.json"
}

default_global = {
    "cdt_data": {},
    "cdt_versions": {},
    "cdt_stats": {},
    "cdt_special_attacks": {},
    "cdt_masteries": {},
    "cdt_character_bios": {},
    "masteries": {},
    "prestige": {}
}

remote_data_basepath = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/"


class FetchCdtData(commands.Cog):
    """
    Fetch data from CDT
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=7078561234,
            force_registration=True,
        )
        self.config.register_global(**default_global)

    @checks.is_owner()
    @commands.group()
    async def fetch(self, ctx):
        """CollectorDevTeam Data Retrieval"""

    @fetch.command(name="all")
    async def _fetch_cdt(self, ctx):
        """Pull all CollectorDevTeam data"""
        await self._fetch_cdt_translation_files(ctx)
        await self._fetch_cdt_mastery_file(ctx)

    @fetch.command(name="translation")
    async def _fetch_translation(self, ctx, filename):
        """bcg_en
        bcg_stats_en
        special_attacks_en
        masteries_en
        character_bios_en
        cutscenes_en
        masteries
        prestige
        """
        # @checks.is_owner()
        # @commands.command(name="fetch_gs")
        # async def _fetch_gs(self, ctx):

    async def _fetch_cdt_translation_files(self, ctx, filename=None):
        """Pull translation files from CDT, store in global config"""
        data = Embed.create(self, ctx,
                            title="Retrieving [{}] CDT JSON files\n".format(len(files.keys())))
        package = ""
        monitor = await ctx.send(embed=data)
        keycount = len(files.keys())
        af = 0
        if filename is None:
            cdt_data, cdt_versions = {}, {}
            filelist = 0
            for key in files.keys():
                r = requests.get(files[key])
                raw_data = r.json()
                if raw_data is None:
                    data.add_field(
                        name=key, value="{} has no data".format(key))
                else:
                    field = data.add_field(
                        name=key, value="0/{} completed".format(len(raw_data['strings'])))
                    counter = 0
                    for dlist in raw_data['strings']:
                        cdt_data.update({dlist['k']: dlist['v']})
                        if "vn" in dlist:
                            cdt_versions.update(
                                {dlist['k']: dlist['vn']})
                        counter += 1
                        data.set_field_at(
                            af, name=key, value="{}/{} completed".format(counter, len(raw_data['strings'])))
                    package += "\n{} stored".format(key)
                    data.description = package
                af += 1
                async with self.config.cdt_data() as cd:
                    cd.update(cdt_data)
                async with self.config.cdt_versions() as cv:
                    cv.update(cdt_versions)
                await monitor.edit(embed=data)
        elif filename in files.keys():
            async with self.config.cdt_data() as cd:
                fdata = cd[filename]
            r = requests.get(files[filename])
            raw_data = r.json()
            if raw_data is None:
                data.add_field(name=key, value="{} has no data".format(key))
            else:
                field = data.add_field(
                    name=key, value="0/{} completed".format(len(raw_data['strings'])))
                counter = 0
                for dlist in raw_data['strings']:
                    fdata.update({dlist['k']: dlist['v']})
                    if "vn" in dlist:
                        cdt_versions.update(
                            {dlist['k']: dlist['vn']})
                    counter += 1
                    data.set_field_at(
                        af, name=key, value="{}/{} completed".format(counter, len(raw_data['strings'])))
                package += "\n{} stored".format(key)
                data.description = package
                async with self.conf.filename() as f:
                    f.update(raw_data)
            await monitor.edit(embed=data)
        elif filename in ("masteries"):
            await self._fetch_cdt_mastery_file(ctx, monitor)
        return monitor

    async def _fetch_cdt_mastery_file(self, ctx, monitor=None):
        """Retrieve CDT Mastery Data"""
        r = requests.get(remote_data_basepath+"json/masteries.json")
        if r is not None:
            raw_data = r.json()
            async with self.config.masteries() as m:
                m.update(raw_data)

    @ checks.is_owner()
    @ commands.command(name="ftest")
    async def _fetch_test(self, ctx, key="ID_UI_HERO_SYNERGY_DESC_MOJO_3"):
        data = Embed.create(self, ctx, title="Fetch Test", description="")
        async with self.config.cdt_data() as cd:
            if key not in cd.keys():
                value = "Key not found"
            else:
                value = cd[key]
        data.add_field(name=key, value=value)
        await ctx.send(embed=data)
