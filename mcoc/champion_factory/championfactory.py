# from ..cdtcore.gsheet_data import GoogleSheets
from redbot.core.utils import chat_formatting
from redbot.core.config import Config
from collections import UserDict, defaultdict, ChainMap, namedtuple, OrderedDict

import re
import logging
import datetime
from ..cdt_core import CDT
from .championclass import Champion

logger = logging.getLogger('red.CollectorDevTeam.mcoc')




class AliasDict(UserDict):
    '''Custom dictionary that uses a tuple of aliases as key elements.
    Item addressing is handled either from the tuple as a whole or any
    element within the tuple key.
    '''
    def __getitem__(self, key):
        if key in self.data:
            return self.data[key]
        for k in self.data.keys():
            if key in k:
                return self.data[k]
        raise KeyError("Invalid Key '{}'".format(key))

class ChampionFactory():
    '''Creation and storage of the dynamically created Champion subclasses.
    A new subclass is created for every champion defined.  Then objects are
    created from user function calls off of the dynamic classes.'''
    ## Created by DeltaSigma

    def __init__(self, *args, **kwargs):
        # self.cooldown_delta = 5 * 60
        # self.cooldown = time.time() - self.cooldown_delta - 1
        # self.needs_init = True
        super().__init__(*args, **kwargs)
        # self.bot.loop.create_task(self.update_local())  # async init
        logger.debug('ChampionFactory Init')

    def data_struct_init(self):
        logger.info('Preparing data structures')
        self._prepare_aliases()
        self._prepare_prestige_data()
        # self.needs_init = False

    # async def update_local(self):
    #     now = datetime.time()
    #     # if now - self.cooldown_delta < self.cooldown:
    #     #     return
    #     # self.cooldown = now
    #     is_updated = await self.verify_cache_remote_files()
    #     if is_updated or self.needs_init:
    #         self.data_struct_init()

    async def create_champion_class(self, bot, alias_set, **kwargs):
        if not kwargs['cdt_champion_id'.strip()]: #empty line
            return
        kwargs['bot'] = bot # ?? 
        kwargs['alias_set'] = alias_set # 
        kwargs['klass'] = kwargs.pop('class', 'default')

        if not kwargs['champ'].strip():  #empty line
            return
        kwargs['full_name'] = kwargs['champ']
        kwargs['bold_name'] = chat_formatting.bold(' '.join(
                [word.capitalize() for word in kwargs['full_name'].split(' ')]))
        kwargs['class_color'] = CDT.color[kwargs['klass']]  #class_color_codes[kwargs['klass']]
        kwargs['class_icon'] = CDT.emoji[kwargs['klass']]

        kwargs['class_tags'] = {'#' + kwargs['klass'].lower()}
        for a in kwargs['abilities'].split(','):
            kwargs['class_tags'].add('#' + ''.join(a.lower().split(' ')))
        for a in kwargs['hashtags'].split('#'):
            kwargs['class_tags'].add('#' + ''.join(a.lower().split(' ')))
        for a in kwargs['extended_abilities'].split(','):
            kwargs['class_tags'].add('#' + ''.join(a.lower().split(' ')))
        for a in kwargs['counters'].split(','):
            kwargs['class_tags'].add('#!' + ''.join(a.lower().split(' ')))
        if kwargs['class_tags']:
            kwargs['class_tags'].difference_update({'#'})

        for key, value in kwargs.items():
            if not value or value == 'n/a':
                kwargs[key] = None

        champion = type(kwargs['cdt_champion_id'], (Champion,), kwargs)
        async with self.config.mcoc.champions() as champions:
            champions[tuple(alias_set)] = champion
        logger.debug('Creating Champion class {}'.format(kwargs['cdt_champion_id']))
        return champion

    async def get_champion(self, name_id, attrs=None):
        '''straight alias lookup followed by new champion object creation'''
        #await self.update_local()
        async with self.config.mcoc.champions(name_id) as champion:
            return champion(attrs)

    async def search_champions(self, search_str, attrs=None):
        '''searching through champion aliases and allowing partial matches.
        Returns an array of new champion objects'''
        #await self.update_local()
        re_str = re.compile(search_str)
        champs = []
        async with self.config.mcoc.champions() as champions:
            for champ in champions.values():
                if any([re_str.search(alias) is not None
                        for alias in champ.alias_set]):
                    champs.append(champ(attrs))
        return champs

    # async def verify_cache_remote_files(self, verbose=False, force_cache=False):
    #     logger.info('Check remote files')
    #     if os.path.exists(file_checks_json):
    #         try:
    #             file_checks = dataIO.load_json(file_checks_json)
    #         except:
    #             file_checks = {}
    #     else:
    #         file_checks = {}
    #     async with aiohttp.ClientSession() as s:
    #         is_updated = False
    #         for key in data_files.keys():
    #             if key in file_checks:
    #                 last_check = datetime(*file_checks.get(key))
    #             else:
    #                 last_check = None
    #             remote_check = await self.cache_remote_file(key, s, verbose=verbose,
    #                     last_check=last_check)
    #             if remote_check:
    #                 is_updated = True
    #                 file_checks[key] = remote_check.timetuple()[:6]
    #     dataIO.save_json(file_checks_json, file_checks)
    #     return is_updated

    # async def cache_remote_file(self, key, session, verbose=False, last_check=None,
    #             force_cache=False):
    #     dargs = data_files[key]
    #     strf_remote = '%a, %d %b %Y %H:%M:%S %Z'
    #     response = None
    #     remote_check = False
    #     now = datetime.now()
    #     if os.path.exists(dargs['local']) and not force_cache:
    #         if last_check:
    #             check_marker = now - timedelta(days=dargs['update_delta'])
    #             refresh_remote_check = check_marker > last_check
    #         else:
    #             refresh_remote_check = True
    #         local_dt = datetime.fromtimestamp(os.path.getmtime(dargs['local']))
    #         if refresh_remote_check:
    #             response = await session.get(dargs['remote'])
    #             if 'Last-Modified' in response.headers:
    #                 remote_dt = datetime.strptime(response.headers['Last-Modified'], strf_remote)
    #                 remote_check = now
    #                 if remote_dt < local_dt:
    #                     # Remote file is older, so no need to transfer
    #                     response = None
    #     else:
    #         response = await session.get(dargs['remote'])
    #     if response and response.status == 200:
    #         logger.info('Caching ' + dargs['local'])
    #         with open(dargs['local'], 'wb') as fp:
    #             fp.write(await response.read())
    #         remote_check = now
    #         await response.release()
    #     elif response:
    #         err_str = "HTTP error code {} while trying to Collect {}".format(
    #                 response.status, key)
    #         logger.error(err_str)
    #         await response.release()
    #     elif verbose and remote_check:
    #         logger.info('Local file up-to-date:', dargs['local'], now)
    #     return remote_check


    ##
    ##  Ok so the workflow should basically be:
    #   retrieve xref column 1 for champion index
    #   retrieve xref for aliases dictionary
    #   retrieve champion info 
    #   compile into a champion object - set the champion object in the config
    #   
    #   then for each champion+tier+rankmax 
    #   retrieve stats
    #   retrieve prestige
    #   set tier-champ-rank
    ##



    async def _prepare_aliases(self):
        '''Create a python friendly data structure from the aliases json'''
        logger.debug('Preparing aliases')
        self.champions = AliasDict()
        # raw_data = load_csv(data_files['crossreference']['local'])
        gs_xref = await CDT.cdt_gspread_get_xref(self)
        gs_info = await CDT.cdt_gspread_get_info(self)
        ### THIS is what I need to replace w/ gspread
        punc_strip = re.compile(r'[\s)(-]')
        champs = []
        all_aliases = set()

        # id_index = raw_data.fieldnames.index('status')
        # alias_index = raw_data.fieldnames[:id_index]
        
        for i in len(gs_xref):
            alias_set = set()
            item = gs_xref[i]
            info = gs_info[i]
            for v in item.values():
                alias_set.add(punc_strip.sub('', v.lower()))
            if all_aliases.isdisjoint(alias_set):
                all_aliases.union(alias_set)
            else:
                raise KeyError("There are aliases that conflict with previous aliases."
                        + "  First occurance with champ {}.".format(item["cdt_champion_id"]))
            
            await self.create_champion_class(self, alias_set, **info)


        # for row in raw_data:
        #     if all([not i for i in row.values()]):
        #         continue    # empty row check  
        #     alias_set = set()
        #     for col in alias_index:
        #         if row[col]:
        #             alias_set.add(row[col].lower())
        #     alias_set.add(punc_strip.sub('', row['champ'].lower()))
        #     if all_aliases.isdisjoint(alias_set):
        #         all_aliases.union(alias_set)
        #     else:
        #         raise KeyError("There are aliases that conflict with previous aliases."
        #                 + "  First occurance with champ {}.".format(row['champ']))
        #     await self.create_champion_class(self.bot, alias_set, **row)

    # def _prepare_prestige_data(self):
    #     logger.debug('Preparing prestige')
    #     mattkraft_re = re.compile(r'(?P<star>\d)-(?P<champ>.+)-(?P<rank>\d)')
    #     with open(data_files['prestigeCSV']['local'], newline='') as csvfile:
    #         reader = csv.reader(csvfile)
    #         for row in reader:
    #             champ_match = mattkraft_re.fullmatch(row.pop(0))
    #             if not champ_match:
    #                 continue
    #             name = champ_match.group('champ')
    #             star = int(champ_match.group('star'))
    #             rank = int(champ_match.group('rank'))

    #             champ = self.champions.get(name)
    #             if not champ:
    #                 logger.info('Skipping ' + name)
    #                 continue

    #             sig_len = 201 if star >= 5 else 100
    #             sig = [0] * sig_len
    #             for i, v in enumerate(row):
    #                 try:
    #                     if v and i < sig_len:
    #                         sig[i] = int(v)
    #                 except:
    #                     print(name, i, v, len(sig))
    #                     raise
    #             if not hasattr(champ, 'prestige_data'):
    #                 champ.prestige_data = {4: [None] * 5, 5: [None] * 5,6: [None] * 5, 3: [None] * 4, 2: [None]*3, 1: [None]*2}
    #             try:
    #                 champ.prestige_data[star][rank-1] = sig
    #             except:
    #                 print(name, star, rank, len(champ.prestige_data),
    #                         len(champ.prestige_data[star]))
    #                 raise

# def command_arg_help(**cmdkwargs):
#     def internal_func(f):
#         helps = []
#         for param in inspect.signature(f).parameters.values():
#             if issubclass(param.annotation, commands.Converter):
#                 arg_help = getattr(param.annotation, 'arg_help')
#                 if arg_help is not None:
#                     helps.append(arg_help)
#         if helps:
#             if f.__doc__:
#                 helps.insert(0, f.__doc__)
#             f.__doc__ = '\n'.join(helps)
#         @wraps(f)
#         async def wrapper(*args, **kwargs):
#             return await f(*args, **kwargs)
#         return commands.command(**cmdkwargs)(wrapper)
#     return internal_func