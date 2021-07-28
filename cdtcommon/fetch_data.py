import aiohttp
import json
from redbot.core.bot import Red


session= aiohttp.ClientSession()
class FetchData():


    def __init__(self, bot: Red):
        """init"""
        self.bot = bot
        

    async def aiohttp_http_to_text(ctx, url):
        """pull textfile from url"""
        result = None
        async with session.get(url) as response:
            if response.status != 200:
                await ctx.send("Response Status: {response.status}")
            filetext = await response.text()
            prettytext = FetchData.prettyprint(filetext)
            if prettytext is not None:
                return prettytext
            else:
                return filetext

    async def aiohttp_http_to_json(ctx, url):
        """pull jsonfile from url"""
        result = None
        async with session.get(url) as response:
            if response.status != 200:
                await ctx.send("Response Status: {response.status}")
            filetext = await response.text()
            result = json.loads(filetext)
            return result

    async def convert_textfile_to_json(ctx, filetext):
        """Convert Kabam's lists of k, v & vn to k: {v, vn}"""
        # stringlist = kabamfile["strings"].keys() #list of strings
        jdump = json.loads(filetext)
        meta = jdump["meta"]
        await ctx.send("dbg: text_to_json metacheck{}".format(meta))
        stringlist = jdump["strings"]
        snapshot_file = {}
        strings = {}
        for i in len(stringlist):
            for k, v in stringlist[i]:
                if "vn" in pkg.keys():
                    vn = pkg["vn"]
                    if isinstance(vn, int):
                        vn = str(vn)
                else:
                    vn = "0.0.0"
                pkg = {k : {"v" : v , "vn": vn}}
                print(pkg)
                strings.update(pkg)
        snapshot_file.update({"meta" : meta, "strings": strings})
        return snapshot_file
        
    
    def prettyprint(text_or_json):
        """Return prettyprint string of json file"""
        jtext = None
        if isinstance(text_or_json, str):
            jtext = json.loads(text_or_json)
        if isinstance(text_or_json, dict):
            jtext = text_or_json

        if jtext is not None:
            result = json.dumps(jtext, indent=4, sort_keys=True)
        return result
# class FetchCdtData(commands.Cog):
#     """
#     Fetch data from CDT
#     """

#     def __init__(self, bot):
#         self.bot = bot
#         self.config = Config.get_conf(
#             self,
#             identifier=7078561234,
#             force_registration=True,
#         )
#         self.config.register_global(**default_global)

#     @checks.is_owner()
#     @commands.group()
#     async def fetch(self, ctx):
#         """CollectorDevTeam Data Retrieval"""

#     @fetch.command(name="all")
#     async def _fetch_cdt(self, ctx):
#         """Pull all CollectorDevTeam data"""
#         await self._fetch_cdt_translation_files(ctx)
#         await self._fetch_cdt_mastery_file(ctx)

#     @fetch.command(name="translation")
#     async def _fetch_translation(self, ctx, filename):
#         """bcg_en
#         bcg_stats_en
#         special_attacks_en
#         masteries_en
#         character_bios_en
#         cutscenes_en
#         masteries
#         prestige
#         """
#         # @checks.is_owner()
#         # @commands.command(name="fetch_gs")
#         # async def _fetch_gs(self, ctx):

#     async def _fetch_cdt_translation_files(self, ctx, filename=None):
#         """Pull translation files from CDT, store in global config"""
#         data = Embed.create(
#             self, ctx, title="Retrieving [{}] CDT JSON files\n".format(len(files.keys()))
#         )
#         package = ""
#         monitor = await ctx.send(embed=data)
#         keycount = len(files.keys())
#         af = 0
#         if filename is None:
#             cdt_data, cdt_versions = {}, {}
#             filelist = 0
#             for key in files.keys():
#                 r = requests.get(files[key])
#                 raw_data = r.json()
#                 if raw_data is None:
#                     data.add_field(name=key, value="{} has no data".format(key))
#                 else:
#                     field = data.add_field(
#                         name=key, value="0/{} completed".format(len(raw_data["strings"]))
#                     )
#                     counter = 0
#                     for dlist in raw_data["strings"]:
#                         cdt_data.update({dlist["k"]: dlist["v"]})
#                         if "vn" in dlist:
#                             cdt_versions.update({dlist["k"]: dlist["vn"]})
#                         counter += 1
#                         data.set_field_at(
#                             af,
#                             name=key,
#                             value="{}/{} completed".format(counter, len(raw_data["strings"])),
#                         )
#                     package += "\n{} stored".format(key)
#                     data.description = package
#                 af += 1
#                 async with self.config.cdt_data() as cd:
#                     cd.update(cdt_data)
#                 async with self.config.cdt_versions() as cv:
#                     cv.update(cdt_versions)
#                 await monitor.edit(embed=data)
#         elif filename in files.keys():
#             async with self.config.cdt_data() as cd:
#                 fdata = cd[filename]
#             r = requests.get(files[filename])
#             raw_data = r.json()
#             if raw_data is None:
#                 data.add_field(name=key, value="{} has no data".format(key))
#             else:
#                 field = data.add_field(
#                     name=key, value="0/{} completed".format(len(raw_data["strings"]))
#                 )
#                 counter = 0
#                 for dlist in raw_data["strings"]:
#                     fdata.update({dlist["k"]: dlist["v"]})
#                     if "vn" in dlist:
#                         cdt_versions.update({dlist["k"]: dlist["vn"]})
#                     counter += 1
#                     data.set_field_at(
#                         af,
#                         name=key,
#                         value="{}/{} completed".format(counter, len(raw_data["strings"])),
#                     )
#                 package += "\n{} stored".format(key)
#                 data.description = package
#                 async with self.conf.filename() as f:
#                     f.update(raw_data)
#             await monitor.edit(embed=data)
#         elif filename in ("masteries"):
#             await self._fetch_cdt_mastery_file(ctx, monitor)
#         return monitor

#     async def _fetch_cdt_mastery_file(self, ctx, monitor=None):
#         """Retrieve CDT Mastery Data"""
#         r = requests.get(remote_data_basepath + "json/masteries.json")
#         if r is not None:
#             raw_data = r.json()
#             async with self.config.masteries() as m:
#                 m.update(raw_data)

#     @checks.is_owner()
#     @commands.command(name="ftest")
#     async def _fetch_test(self, ctx, key="ID_UI_HERO_SYNERGY_DESC_MOJO_3"):
#         data = Embed.create(self, ctx, title="Fetch Test", description="")
#         async with self.config.cdt_data() as cd:
#             if key not in cd.keys():
#                 value = "Key not found"
#             else:
#                 value = cd[key]
#         data.add_field(name=key, value=value)
#         await ctx.send(embed=data)
