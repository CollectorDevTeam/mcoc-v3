import discord
from redbot.core.config import Config
from redbot.core import commands, checks
import aiohttp
from collections import defaultdict, ChainMap, namedtuple, OrderedDict

BaseCog = getattr(commands, "Cog", object)

remote_data_basepath = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/"
GOOGLECREDENTIALS = ''


class CDTDATA(BaseCog):
    """
    CollectorDevTeam DataSets for Marvel Contest of Champions
    """

    __version__ = "1.0.0"

    def __init__(self, bot):
        self.bot = bot
        self.database = Config.get_conf(self, identifier=324631601344544778001, force_registration=True)
        default_global = {
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
            }
        }
        default_guild = {
            "alliance_name": "",
            "alliance_tag": ""
        }
        default_user = {
            "prestige": {},
            "roster": {}
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)

    async def load_cdt_data(self):
        """Load existing CDT Data
        Pull new CDT Data
        Verify new CDT Data
        Store new CDT Data
        Load new CDT Data into bot"""
        cdt_data, cdt_versions = ChainMap(), ChainMap()
        cdt_stats = None
        files = (
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/bcg_stat_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/special_attacks_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/masteries_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/character_bios_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/dungeons_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/cutscenes_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/initial_en.json',
            'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/snapshots/en/alliances_en.json'
        )
        async with aiohttp.ClientSession() as session:
            for url in files:
                raw_data = await self.fetch_json(url, session)
                val, ver = {}, {}
                for dlist in raw_data['strings']:
                    val[dlist['k']] = dlist['v']
                    if 'vn' in dlist:
                        ver[dlist['k']] = dlist['vn']
                cdt_data.maps.append(val)
                cdt_versions.maps.append(ver)

        await self.database.cdt_data.set(cdt_data)
        await self.database.cdt_versions.set(cdt_versions)

        # Test cdt_data for validity
        # IF TRUE, store cdt_data locally
        # Load Local data to config.global.cdt_data

        #Test cdt_versions for validity
        # IF TRUE, store cdt_versions locally
        # Load local data to config.global.cdt_version



            self.cdt_data = cdt_data
            self.cdt_versions = cdt_versions
            self.cdt_masteries = await self.fetch_json(
                'https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/json/masteries.json',
                session)
            # self.cdt_stats = StaticGameData.get_gsheets_data('cdt_stats')

    @commands.command()
    async def fetch(self, ctx):
        """Test Command String"""
        await self.load_cdt_data()

def setup(bot):
    bot.loop.create_task(CDTDATA.load_cdt_data())
