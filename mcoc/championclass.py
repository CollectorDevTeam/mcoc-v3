# import discord
# from discord.ext import commands
# import json
# import requests
# import pages_menu
#
# class ChampConverter(commands.Converter):
#     '''Argument Parsing class that geneartes Champion objects from user input'''
#
#     arg_help = '''
#     Specify a single lib_champion with optional parameters of star, rank, or sig.
#     Champion names can be a number of aliases or partial aliases if no conflicts are found.
#
#     The optional arguments can be in any order, with or without spaces.
#         <digit>* specifies star <default: 4>
#         r<digit> specifies rank <default: 5>
#         s<digit> specifies signature level <default: 99>
#
#     Examples:
#         4* yj r4 s30  ->  4 star Yellowjacket rank 4/40 sig 30
#         r35*im        ->  5 star Ironman rank 3/45 sig 99
#         '''
# #(?:(?:s(?P<sig>[0-9]{1,3})) |(?:r(?P<rank>[1-5]))|(?:(?P<star>[1-5])\\?\*)|(?:d(?P<debug>[0-9]{1,2})))(?=\b|[a-zA-Z]|(?:[1-5]\\?\*))
#     _bare_arg = None
#     parse_re = re.compile(r'''(?:s(?P<sig>[0-9]{1,3}))
#                              |(?:r(?P<rank>[1-5]))
#                              |(?:(?P<star>[1-6])(?:★|☆|\\?\*))
#                              |(?:d(?P<debug>[0-9]{1,2}))''', re.X)
#     async def convert(self):
#         bot = self.ctx.bot
#         attrs = {}
#         if self._bare_arg:
#             args = self.argument.rsplit(' ', maxsplit=1)
#             if len(args) > 1 and args[-1].isdecimal():
#                 attrs[self._bare_arg] = int(args[-1])
#                 self.argument = args[0]
#         arg = ''.join(self.argument.lower().split(' '))
#         for m in self.parse_re.finditer(arg):
#             attrs[m.lastgroup] = int(m.group(m.lastgroup))
#         token = self.parse_re.sub('', arg)
#         if not token:
#             err_str = "No Champion remains from arg '{}'".format(self.argument)
#             #await bot.say(err_str)
#             #raise commands.BadArgument(err_str)
#             raise MODOKError(err_str)
#         return (await self.get_champion(bot, token, attrs))
#
#     async def get_champion(self, bot, token, attrs):
#         mcoc = bot.get_cog('MCOC')
#         try:
#             champ = await mcoc.get_champion(token, attrs)
#         except KeyError:
#             champs = await mcoc.search_champions('.*{}.*'.format(token), attrs)
#             if len(champs) == 1:
#                 await bot.say("'{}' was not exact but found close alternative".format(
#                         token))
#                 champ = champs[0]
#             elif len(champs) > 1:
#                 em = discord.Embed(title='Ambiguous Argument "{}"'.format(token),
#                         description='Resolved to multiple possible champs')
#                 for champ in champs:
#                     em.add_field(name=champ.full_name, inline=False,
#                             value=chat.box(', '.join(champ.alias_set)))
#                 await bot.say(embed=em)
#                 raise AmbiguousArgError('Multiple matches for arg "{}"'.format(token))
#             else:
#                 err_str = "Cannot resolve alias for '{}'".format(token)
#                 #await bot.say(err_str)
#                 #raise commands.BadArgument(err_str)
#                 raise MODOKError(err_str)
#         return champ
#
# class ChampConverterSig(ChampConverter):
#     _bare_arg = 'sig'
#     arg_help = ChampConverter.arg_help + '''
#     Bare Number argument for this function is sig level:
#         "yjr5s30" is equivalent to "yjr5 30"'''
#
# class ChampConverterRank(ChampConverter):
#     _bare_arg = 'rank'
#     arg_help = ChampConverter.arg_help + '''
#     Bare Number argument for this function is rank:
#         "yjr5s30" is equivalent to "yjs30 5"'''
#
# class ChampConverterStar(ChampConverter):
#     _bare_arg = 'star'
#     arg_help = ChampConverter.arg_help + '''
#     Bare Number argument for this function is star:
#         "5*yjr5s30" is equivalent to "yjr5s30 5"'''
#
# class ChampConverterDebug(ChampConverter):
#     _bare_arg = 'debug'
#
# class ChampConverterMult(ChampConverter):
#
#     arg_help = '''
#     Specify multiple champions with optional parameters of star, rank, or sig.
#     Champion names can be a number of aliases or partial aliases if no conflicts are found.
#
#     The optional arguments can be in any order.
#         <digit>* specifies star <default: 4>
#         r<digit> specifies rank <default: 5>
#         s<digit> specifies signature level <default: 99>
#
#     If optional arguments are listed without a lib_champion, it changes the default for all
#     remaining champions.  Arguments attached to a lib_champion are local to that lib_champion
#     only.
#
#     Examples:
#         s20 yj im        ->  4* Yellowjacket r5/50 sig 20, 4* Ironman r5/50 sig 20
#         r35*ims20 ims40  ->  5 star Ironman r3/45 sig 20, 4* Ironman r5/50 sig 40
#         r4s20 yj ims40 lc -> 4* Yellowjacket r4/40 sig 20, 4* Ironman r4/40 sig 40, 4* Luke Cage r4/40 sig 20
#         '''
#
#     async def convert(self):
#         bot = self.ctx.bot
#         champs = []
#         default = {}
#         dangling_arg = None
#         for arg in self.argument.lower().split(' '):
#             attrs = default.copy()
#             for m in self.parse_re.finditer(arg):
#                 attrs[m.lastgroup] = int(m.group(m.lastgroup))
#             token = self.parse_re.sub('', arg)
#             if token != '':
#                 champ = await self.get_champion(bot, token, attrs)
#                 dangling_arg = None
#                 champs.append(champ)
#             else:
#                 default.update(attrs)
#                 dangling_arg = arg
#         if dangling_arg:
#             em = discord.Embed(title='Dangling Argument',
#                     description="Last argument '{}' is unused.\n".format(dangling_arg)
#                         + "Place **before** the lib_champion or **without a space**.")
#             await bot.say(embed=em)
#         return champs
#
# async def warn_bold_say(bot, msg):
#     await bot.say('\u26a0 ' + chat.bold(msg))
#
# def numericise_bool(val):
#     if val == "TRUE":
#         return True
#     elif val == "FALSE":
#         return False
#     else:
#         return numericise(val)
#
# def strip_and_numericise(val):
#         return numericise_bool(val.strip())
#
# def cell_to_list(cell):
#     return [strip_and_numericise(i) for i in cell.split(',')] if cell is not None else None
#
# def cell_to_dict(cell):
#     if cell is None:
#         return None
#     ret  = {}
#     for i in cell.split(','):
#         k, v = [strip_and_numericise(j) for j in i.split(':')]
#         ret[k] = v
#     return ret
#
# def remove_commas(cell):
#     return numericise_bool(cell.replace(',', ''))
#
# def remove_NA(cell):
#     return None if cell in ("#N/A", "") else numericise_bool(cell)
#
#
# class GSExport():
#
#     default_settings = {
#                 'sheet_name': None,
#                 'sheet_action': 'file',
#                 'data_type': 'dict',
#                 'range': None,
#                 'include_empty': False,
#                 'column_handler': None,
#                 'row_handler': None,
#                 'rc_priority': 'column',
#                 'postprocess': None,
#                 'prepare_function': 'numericise_bool',
#             }
#     default_cell_handlers = (
#                 'cell_to_list',
#                 'cell_to_dict',
#                 'remove_commas',
#                 'remove_NA',
#                 'numericise',
#                 'numericise_bool'
#             )
#     cell_handler_aliases = {
#                 'to_list': 'cell_to_list',
#                 'to_dict': 'cell_to_dict',
#             }
#
#     def __init__(self, bot, gc, *, name, gkey, local, **kwargs):
#         self.bot = bot
#         self.gc = gc
#         self.name = name
#         self.gkey = gkey
#         self.local = local
#         self.meta_sheet = kwargs.pop('meta_sheet', 'meta_sheet')
#         self.settings = self.default_settings.copy()
#         self.settings.update(kwargs)
#         self.data = defaultdict(partial(defaultdict, dict))
#         self.cell_handlers = {}
#         module_namespace = globals()
#         for handler in self.default_cell_handlers:
#             self.cell_handlers[handler] = module_namespace[handler]
#         for alias, handler in self.cell_handler_aliases.items():
#             self.cell_handlers[alias] = module_namespace[handler]
#
#     async def retrieve_data(self):
#         try:
#             ss = self.gc.open_by_key(self.gkey)
#         except:
#             await self.bot.say("Error opening Spreadsheet <{}>".format(self.gkey))
#             return
#         if self.meta_sheet and self.settings['sheet_name'] is None:
#             try:
#                 meta = ss.worksheet('title', self.meta_sheet)
#             except pygsheets.WorksheetNotFound:
#                 meta = None
#         else:
#             meta = None
#
#         if meta:
#             for record in meta.get_all_records():
#                 [record.update(((k,v),)) for k,v in self.settings.items() if k not in record or not record[k]]
#                 await self.retrieve_sheet(ss, **record)
#         else:
#             await self.retrieve_sheet(ss, **self.settings)
#
#         if self.settings['postprocess']:
#             try:
#                 await self.settings['postprocess'](self.bot, self.data)
#             except Exception as err:
#                 await self.bot.say("Runtime Error in postprocess of Spreadsheet "
#                         "'{}':\n\t{}".format( self.name, err))
#                 raise
#         if self.local:
#             dataIO.save_json(self.local, self.data)
#         return self.data
#
#     async def retrieve_sheet(self, ss, *, sheet_name, sheet_action, data_type, **kwargs):
#         sheet_name, sheet = await self._resolve_sheet_name(ss, sheet_name)
#         data = self.get_sheet_values(sheet, kwargs)
#         header = data[0]
#
#         if data_type.startswith('nested_list'):
#             data_type, dlen = data_type.rsplit('::', maxsplit=1)
#             dlen = int(dlen)
#         #prep_func = self.cell_handlers[kwargs['prepare_function']]
#         prep_func = self.get_prepare_function(kwargs)
#         self.data['_headers'][sheet_name] = header
#         col_handlers = self._build_column_handlers(sheet_name, header,
#                             kwargs['column_handler'])
#         if sheet_action == 'table':
#             self.data[sheet_name] = [header]
#         for row in data[1:]:
#             clean_row = self._process_row(header, row, col_handlers, prep_func)
#             rkey = clean_row[0]
#             if sheet_action == 'merge':
#                 if data_type == 'nested_dict':
#                     pack = dict(zip(header[2:], clean_row[2:]))
#                     self.data[rkey][sheet_name][clean_row[1]] = pack
#                     continue
#                 if data_type == 'list':
#                     pack = clean_row[1:]
#                 elif data_type == 'dict':
#                     pack = dict(zip(header[1:],clean_row[1:]))
#                 elif data_type == 'nested_list':
#                     if len(clean_row[1:]) < dlen or not any(clean_row[1:]):
#                         pack = None
#                     else:
#                         pack = [clean_row[i:i+dlen] for i in range(1, len(clean_row), dlen)]
#                 else:
#                     await self.bot.say("Unknown data type '{}' for worksheet '{}' in spreadsheet '{}'".format(
#                             data_type, sheet_name, self.name))
#                     return
#                 self.data[rkey][sheet_name] = pack
#             elif sheet_action in ('dict', 'file'):
#                 if data_type == 'list':
#                     pack = clean_row[1:]
#                 elif data_type == 'dict':
#                     pack = dict(zip(header, clean_row))
#                 if data_type == 'nested_dict':
#                     pack = dict(zip(header[2:], clean_row[2:]))
#                     self.data[sheet_name][rkey][clean_row[1]] = pack
#                 elif sheet_action == 'dict':
#                     self.data[sheet_name][rkey] = pack
#                 elif sheet_action == 'file':
#                     self.data[rkey] = pack
#             elif sheet_action == 'list':
#                 if data_type == 'list':
#                     pack = clean_row[0:]
#                 elif data_type == 'dict':
#                     pack = dict(zip(header, clean_row))
#                 if sheet_name not in self.data:
#                     self.data[sheet_name] = []
#                 self.data[sheet_name].append(pack)
#             elif sheet_action == 'table':
#                 self.data[sheet_name].append(clean_row)
#             else:
#                 raise KeyError("Unknown sheet_action '{}' for worksheet '{}' in spreadsheet '{}'".format(
#                             sheet_action, sheet_name, self.name))
#
#     async def _resolve_sheet_name(self, ss, sheet_name):
#         if sheet_name:
#             try:
#                 sheet = ss.worksheet('title', sheet_name)
#             except pygsheets.WorksheetNotFound:
#                 await self.bot.say("Cannot find worksheet '{}' in Spreadsheet '{}' ({})".format(
#                         sheet_name, ss.title, ss.id))
#         else:
#             sheet = ss.sheet1
#             sheet_name = sheet.title
#         return sheet_name, sheet
#
#     def _process_row(self, header, row, col_handlers, prep_func):
#         clean_row = [row[0]]
#         # don't process first column.  Can't use list, dicts, or numbers as keys in json
#         for cell_head, cell, c_hand in zip(header[1:], row[1:], col_handlers[1:]):
#             if c_hand:
#                 clean_row.append(c_hand(cell))
#             else:
#                 clean_row.append(prep_func(cell))
#         return clean_row
#
#     def get_prepare_function(self, kwargs):
#         prep_func = kwargs['prepare_function']
#         prep_list = cell_to_list(prep_func)
#         if prep_list[0] == prep_func:  # single prep
#             return self.cell_handlers[prep_func]
#
#         #  multiple prep
#         handlers = [self.cell_handlers[i] for i in prep_list]
#         def _curried(x):
#             ret = x
#             for func in handlers:
#                 ret = func(ret)
#             return ret
#         return _curried
#
#     def get_sheet_values(self, sheet, kwargs):
#         if kwargs['range']:
#             rng = self.bound_range(sheet, kwargs['range'])
#             data = sheet.get_values(*rng, returnas='matrix',
#                     include_empty=kwargs['include_empty'])
#         else:
#             data = sheet.get_all_values(include_empty=kwargs['include_empty'])
#         return data
#
#     def _build_column_handlers(self, sheet_name, header, column_handler_str):
#         if not column_handler_str:
#             return [None] * len(header)
#         col_handler = cell_to_dict(column_handler_str)
#         #print(col_handler)
#
#         #  Column Header check
#         invalid = set(col_handler.keys()) - set(header)
#         if invalid:
#             raise ValueError("Undefined Columns in column_handler for sheet "
#                     + "'{}':\n\t{}".format(sheet_name, ', '.join(invalid)))
#         #  Callback Cell Handler check
#         invalid = set(col_handler.values()) - set(self.cell_handlers.keys())
#         if invalid:
#             raise ValueError("Undefined CellHandler in column_handler for sheet "
#                     + "'{}':\n\t{}".format(sheet_name, ', '.join(invalid)))
#
#         handler_funcs = []
#         for column in header:
#             if column not in col_handler:
#                 handler_funcs.append(None)
#             else:
#                 handler_funcs.append(self.cell_handlers[col_handler[column]])
#         return handler_funcs
#
#     @staticmethod
#     def bound_range(sheet, rng_str):
#         rng = rng_str.split(':')
#         rows = (1, sheet.rows)
#         for i in range(2):
#             if not rng[i][-1].isdigit():
#                 rng[i] = '{}{}'.format(rng[i], rows[i])
#         return rng
#
#
# class GSHandler:
#
#     def __init__(self, bot, service_file):
#         self.bot = bot
#         self.service_file = service_file
#         self.gsheets = {}
#
#     def register_gsheet(self, *, name, gkey, local, **kwargs):
#         if name in self.gsheets:
#             raise KeyError("Key '{}' has already been registered".format(name))
#         self.gsheets[name] = dict(gkey=gkey, local=local, **kwargs)
#
#     async def cache_gsheets(self, key=None):
#         gc = await self.authorize()
#         if key and key not in self.gsheets:
#             raise KeyError("Key '{}' is not registered".format(key))
#         gfiles = self.gsheets.keys() if not key else (key,)
#
#         num_files = len(gfiles)
#         msg = await self.bot.say('Pulled Google Sheet data 0/{}'.format(num_files))
#         for i, k in enumerate(gfiles):
#             gsdata = GSExport(self.bot, gc, name=k, **self.gsheets[k])
#             try:
#                 await gsdata.retrieve_data()
#             except:
#                 await self.bot.say("Error while pulling '{}'".format(k))
#                 raise
#             msg = await self.bot.edit_message(msg,
#                     'Pulled Google Sheet data {}/{}'.format(i+1, num_files))
#         await self.bot.say('Retrieval Complete')
#
#     async def authorize(self):
#         try:
#             return pygsheets.authorize(service_file=self.service_file, no_cache=True)
#         except FileNotFoundError:
#             err_msg = 'Cannot find credentials file.  Needs to be located:\n' \
#                     + self.service_file
#             await self.bot.say(err_msg)
#             raise FileNotFoundError(err_msg)
#
#
# class AliasDict(UserDict):
#     '''Custom dictionary that uses a tuple of aliases as key elements.
#     Item addressing is handled either from the tuple as a whole or any
#     element within the tuple key.
#     '''
#     def __getitem__(self, key):
#         if key in self.data:
#             return self.data[key]
#         for k in self.data.keys():
#             if key in k:
#                 return self.data[k]
#         raise KeyError("Invalid Key '{}'".format(key))
#
# class ChampionFactory():
#     '''Creation and storage of the dynamically created Champion subclasses.
#     A new subclass is created for every lib_champion defined.  Then objects are
#     created from user function calls off of the dynamic classes.'''
#
#     def __init__(self, *args, **kwargs):
#         self.cooldown_delta = 5 * 60
#         self.cooldown = time.time() - self.cooldown_delta - 1
#         self.needs_init = True
#         super().__init__(*args, **kwargs)
#         self.bot.loop.create_task(self.update_local())  # async init
#         logger.debug('ChampionFactory Init')
#
#     def data_struct_init(self):
#         logger.info('Preparing data structures')
#         self._prepare_aliases()
#         self._prepare_prestige_data()
#         self.needs_init = False
#
#     async def update_local(self):
#         now = time.time()
#         if now - self.cooldown_delta < self.cooldown:
#             return
#         self.cooldown = now
#         is_updated = await self.verify_cache_remote_files()
#         if is_updated or self.needs_init:
#             self.data_struct_init()
#
#     def create_champion_class(self, bot, alias_set, **kwargs):
#         if not kwargs['champ'.strip()]: #empty line
#             return
#         kwargs['bot'] = bot
#         kwargs['alias_set'] = alias_set
#         kwargs['klass'] = kwargs.pop('class', 'default')
#
#         if not kwargs['champ'].strip():  #empty line
#             return
#         kwargs['full_name'] = kwargs['champ']
#         kwargs['bold_name'] = chat.bold(' '.join(
#                 [word.capitalize() for word in kwargs['full_name'].split(' ')]))
#         kwargs['class_color'] = class_color_codes[kwargs['klass']]
#         kwargs['class_icon'] = class_emoji[kwargs['klass']]
#
#         kwargs['class_tags'] = {'#' + kwargs['klass'].lower()}
#         for a in kwargs['abilities'].split(','):
#             kwargs['class_tags'].add('#' + ''.join(a.lower().split(' ')))
#         for a in kwargs['hashtags'].split('#'):
#             kwargs['class_tags'].add('#' + ''.join(a.lower().split(' ')))
#         for a in kwargs['extended_abilities'].split(','):
#             kwargs['class_tags'].add('#' + ''.join(a.lower().split(' ')))
#         for a in kwargs['counters'].split(','):
#             kwargs['class_tags'].add('#!' + ''.join(a.lower().split(' ')))
#         if kwargs['class_tags']:
#             kwargs['class_tags'].difference_update({'#'})
#
#         for key, value in kwargs.items():
#             if not value or value == 'n/a':
#                 kwargs[key] = None
#
#         lib_champion = type(kwargs['mattkraftid'], (Champion,), kwargs)
#         self.champions[tuple(alias_set)] = lib_champion
#         logger.debug('Creating Champion class {}'.format(kwargs['mattkraftid']))
#         return lib_champion
#
#     async def get_champion(self, name_id, attrs=None):
#         '''straight alias lookup followed by new lib_champion object creation'''
#         #await self.update_local()
#         return self.champions[name_id](attrs)
#
#     async def search_champions(self, search_str, attrs=None):
#         '''searching through lib_champion aliases and allowing partial matches.
#         Returns an array of new lib_champion objects'''
#         #await self.update_local()
#         re_str = re.compile(search_str)
#         champs = []
#         for champ in self.champions.values():
#             if any([re_str.search(alias) is not None
#                     for alias in champ.alias_set]):
#                 champs.append(champ(attrs))
#         return champs
#
#     async def verify_cache_remote_files(self, verbose=False, force_cache=False):
#         logger.info('Check remote files')
#         if os.path.exists(file_checks_json):
#             try:
#                 file_checks = dataIO.load_json(file_checks_json)
#             except:
#                 file_checks = {}
#         else:
#             file_checks = {}
#         async with aiohttp.ClientSession() as s:
#             is_updated = False
#             for key in data_files.keys():
#                 if key in file_checks:
#                     last_check = datetime(*file_checks.get(key))
#                 else:
#                     last_check = None
#                 remote_check = await self.cache_remote_file(key, s, verbose=verbose,
#                         last_check=last_check)
#                 if remote_check:
#                     is_updated = True
#                     file_checks[key] = remote_check.timetuple()[:6]
#         dataIO.save_json(file_checks_json, file_checks)
#         return is_updated
#
#     async def cache_remote_file(self, key, session, verbose=False, last_check=None,
#                 force_cache=False):
#         dargs = data_files[key]
#         strf_remote = '%a, %d %b %Y %H:%M:%S %Z'
#         response = None
#         remote_check = False
#         now = datetime.now()
#         if os.path.exists(dargs['local']) and not force_cache:
#             if last_check:
#                 check_marker = now - timedelta(days=dargs['update_delta'])
#                 refresh_remote_check = check_marker > last_check
#             else:
#                 refresh_remote_check = True
#             local_dt = datetime.fromtimestamp(os.path.getmtime(dargs['local']))
#             if refresh_remote_check:
#                 response = await session.get(dargs['remote'])
#                 if 'Last-Modified' in response.headers:
#                     remote_dt = datetime.strptime(response.headers['Last-Modified'], strf_remote)
#                     remote_check = now
#                     if remote_dt < local_dt:
#                         # Remote file is older, so no need to transfer
#                         response = None
#         else:
#             response = await session.get(dargs['remote'])
#         if response and response.status == 200:
#             logger.info('Caching ' + dargs['local'])
#             with open(dargs['local'], 'wb') as fp:
#                 fp.write(await response.read())
#             remote_check = now
#             await response.release()
#         elif response:
#             err_str = "HTTP error code {} while trying to Collect {}".format(
#                     response.status, key)
#             logger.error(err_str)
#             await response.release()
#         elif verbose and remote_check:
#             logger.info('Local file up-to-date:', dargs['local'], now)
#         return remote_check
#
#     def _prepare_aliases(self):
#         '''Create a python friendly data structure from the aliases json'''
#         logger.debug('Preparing aliases')
#         self.champions = AliasDict()
#         raw_data = load_csv(data_files['crossreference']['local'])
#         punc_strip = re.compile(r'[\s)(-]')
#         champs = []
#         all_aliases = set()
#         id_index = raw_data.fieldnames.index('status')
#         alias_index = raw_data.fieldnames[:id_index]
#         for row in raw_data:
#             if all([not i for i in row.values()]):
#                 continue    # empty row check
#             alias_set = set()
#             for col in alias_index:
#                 if row[col]:
#                     alias_set.add(row[col].lower())
#             alias_set.add(punc_strip.sub('', row['champ'].lower()))
#             if all_aliases.isdisjoint(alias_set):
#                 all_aliases.union(alias_set)
#             else:
#                 raise KeyError("There are aliases that conflict with previous aliases."
#                         + "  First occurance with champ {}.".format(row['champ']))
#             self.create_champion_class(self.bot, alias_set, **row)
#
#     def _prepare_prestige_data(self):
#         logger.debug('Preparing prestige')
#         mattkraft_re = re.compile(r'(?P<star>\d)-(?P<champ>.+)-(?P<rank>\d)')
#         with open(data_files['prestigeCSV']['local'], newline='') as csvfile:
#             reader = csv.reader(csvfile)
#             for row in reader:
#                 champ_match = mattkraft_re.fullmatch(row.pop(0))
#                 if not champ_match:
#                     continue
#                 name = champ_match.group('champ')
#                 star = int(champ_match.group('star'))
#                 rank = int(champ_match.group('rank'))
#
#                 champ = self.champions.get(name)
#                 if not champ:
#                     logger.info('Skipping ' + name)
#                     continue
#
#                 sig_len = 201 if star >= 5 else 100
#                 sig = [0] * sig_len
#                 for i, v in enumerate(row):
#                     try:
#                         if v and i < sig_len:
#                             sig[i] = int(v)
#                     except:
#                         print(name, i, v, len(sig))
#                         raise
#                 if not hasattr(champ, 'prestige_data'):
#                     champ.prestige_data = {4: [None] * 5, 5: [None] * 5,6: [None] * 5, 3: [None] * 4, 2: [None]*3, 1: [None]*2}
#                 try:
#                     champ.prestige_data[star][rank-1] = sig
#                 except:
#                     print(name, star, rank, len(champ.prestige_data),
#                             len(champ.prestige_data[star]))
#                     raise
#
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
