import aiohttp
import json


class FetchData():

    def __init__(self):
        """init"""

    async def aiohttp_http_to_json(self, ctx, url):
        """pull JSON from url"""
        session = aiohttp.ClientSession(json_serialize=json.dumps())
        async with session.get(url) as response:
            if response.status != 200:
                await ctx.send("Response Status: {response.status}")
            if response.json():
                result = await response.json()
            else:
                result = json.loads(response.text())
            session.close()
        return result

    def convert_snapshot_to_json(self, kabamfile:json):
        """Convert Kabam's lists of k, v & vn to k: {v, vn}"""
        stringlist = kabamfile["strings"] #list of strings
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
        snapshot_file.update({"meta" : kabamfile["meta"], "strings": strings})
        return snapshot_file
        
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
