from .abc import MixinMeta
import datetime
from .. import exceptions
from ..cdtcore import CDT
import re
import logging

log = logging.getLogger('red.CollectorDevTeam.mcoc')

REMOTE_ASSETS = "https://raw.githubusercontent.com/CollectorDevTeam/assets/master/data/"
STAR_GLYPH = "★"

def validate_attr(*expected_args):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            for attr in expected_args:
                if getattr(self, attr + '_data', None) is None:
                    raise AttributeError("{} for Champion ".format(attr.capitalize())
                        + "'{}' has not been initialized.".format(self.champ))
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

class Champion():

    base_tags = {'#cr{}'.format(i) for i in range(10, 130, 10)}
    base_tags.update({'#{}star'.format(i) for i in range(1, 6)})
    base_tags.update({'#{}*'.format(i) for i in range(1, 6)})
    base_tags.update({'#awake', }, {'#sig{}'.format(i) for i in range(1, 201)})
    dupe_levels = {2: 1, 3: 8, 4: 20, 5: 20, 6: 20}
    default_stars = {i: {'rank': i+1, 'sig': 99} for i in range(1,5)}
    default_stars[5] = {'rank': 5, 'sig': 200}
    default_stars[6] = {'rank': 1, 'sig': 200}

    sig_raw_per_str = '{:.2%}'
    sig_per_str = '{:.2f} ({:.2%})'

    def __init__(self, attrs=None):
        # self.warn_bold_say = partial(warn_bold_say, self.bot)
        if attrs is None:
            attrs = {}
        self.debug = attrs.pop('debug', 0)

        self._star = attrs.pop('star', 4)
        if self._star < 1:
            log.warn('Star {} for Champ {} is too low.  Setting to 1'.format(
                    self._star, self.full_name))
            self._star = 1
        if self._star > 6:
            log.warn('Star {} for Champ {} is too high.  Setting to 6'.format(
                    self._star, self.full_name))
            self._star = 6
        self._default = self.default_stars[self._star].copy()

        for k,v in attrs.items():
            if k not in self._default:
                setattr(self, k, v)
        self.tags = set()
        self.update_attrs(attrs)

    def __eq__(self, other):
        return self.immutable_id == other.immutable_id \
                and self.rank == other.rank \
                and self.sig == other.sig

    def update_attrs(self, attrs):
        self.tags.difference_update(self.base_tags)
        for k in ('rank', 'sig'):
            if k in attrs:
                setattr(self, '_' + k, attrs[k])
        if self.sig < 0:
            self._sig = 0
        if self.rank < 1:
            self._rank = 1
        if self.star >= 5:
            if self.rank > 5:
                self._rank = 5
            if self.sig > 200:
                self._sig = 200
        elif self.star < 5:
            if self.rank > (self.star + 1):
                self._rank = self.star + 1
            if self.sig > 99:
                self._sig = 99
        self.tags.add('#cr{}'.format(self.chlgr_rating))
        self.tags.add('#{}star'.format(self.star))
        self.tags.add('#{}*'.format(self.star))
        if self.sig != 0:
            self.tags.add('#awake')
        self.tags.add('#sig{}'.format(self.sig))

    def update_default(self, attrs):
        self._default.update(attrs)

    def inc_dupe(self):
        self.update_attrs({'sig': self.sig + self.dupe_levels[self.star]})

    def get_avatar(self):
        image = '{}images/portraits/{}.png'.format(REMOTE_ASSETS, self.cdt_champion_id)
        log.debug(image)
        return image

    def get_featured(self):
        image = '{}images/featured/{}.png'.format(
                    REMOTE_ASSETS, self.cdt_champion_id)
        log.debug(image)
        return image

    async def get_bio(self):
        # sgd = cogs.mcocTools.StaticGameData()
        
        key = "ID_CHARACTER_BIOS_{}".format(self.mcocjson)
        if self.debug:
            dbg_str = "BIO:  " + key
            await self.bot.say('```{}```'.format(dbg_str))
        try:
            bio = await self.config.words(key)
        except KeyError:
            raise KeyError('Cannot find Champion {} in data files'.format(self.full_name))
        return bio

    @property
    def star(self):
        return self._star

    @property
    def rank(self):
        return getattr(self, '_rank', self._default['rank'])

    @property
    def sig(self):
        return getattr(self, '_sig', self._default['sig'])

    def is_defined(self, attr):
        return hasattr(self, '_' + attr)

    @property
    def is_user_playable(self):
        return (self.released is not None
                and dateParse(self.released) <= datetime.now())
    
    @property
    def immutable_id(self):
        return (type(self), self.star)

    @property
    def duel_str(self):
        return '{0.star}{0.star_char} {0.rank}/{0.max_lvl} {0.full_name}'.format(self)

    @property
    def star_str(self):
        return '{0.stars_str} {0.rank}/{0.max_lvl}'.format(self)

    @property
    def attrs_str(self):
        return '{0.star}{0.star_char} {0.rank}/{0.max_lvl} sig{0.sig}'.format(self)

    @property
    def unique(self):
        return '{0.star}-{0.cdt_champion_id}-{0.rank}'.format(self)

    @property
    def coded_str(self):
        return '{0.star}*{0.short}r{0.rank}s{0.sig}'.format(self)

    @property
    def verbose_str(self):
        return '{0.star}{0.star_char} {0.full_name} r{0.rank}'.format(self)
        # return '{0.stars_str} {0.full_name} r{0.rank}'.format(self)

    @property
    def star_name_str(self):
        return '{0.star}{0.star_char} {0.full_name}'.format(self)
        #return '{0.star}★ {0.full_name}'.format(self)

    @property
    def rank_sig_str(self):
        return '{0.rank}/{0.max_lvl} sig{0.sig:<2}'.format(self)

    @property
    def verbose_prestige_str(self):
        return ('{0.class_icon} {0.star}{0.star_char} {0.full_name} '
                + 'r{0.rank} s{0.sig:<2} [ {0.prestige} ]').format(self)

    @property
    def stars_str(self):
        return self.star_char * self.star

    @property
    def terse_star_str(self):
        return '{0.star}{0.star_char}'.format(self)

    @property
    def star_char(self):
        if self.sig:
            return '★'
        else:
            return '☆'

    @property
    def chlgr_rating(self):
        if self.star == 1:
            return self.rank * 10
        if self.star == 6:
            return (2 * self.star - 2 + self.rank) * 10
        else:
            return (2 * self.star - 3 + self.rank) * 10

    @property
    def max_lvl(self):
        if self.star < 5:
            return self.rank * 10
        else:
            return 15 + self.rank * 10

    @property
    def all_tags(self):
        return self.tags.union(self.class_tags)

    def to_json(self):
        translate = {'sig': 'Awakened', 'hookid': 'Id', 'max_lvl': 'Level',
                    'prestige': 'Pi', 'rank': 'Rank', 'star': 'Stars',
                    'quest_role': 'Role', 'max_prestige': 'maxpi'}
        pack = {}
        for attr, hook_key in translate.items():
            pack[hook_key] = getattr(self, attr, '')
        return pack

    def get_special_attacks(self):
        with self.config.mcoc.words() as words:

        # sgd = cogs.mcocTools.StaticGameData()
            # cdt_data = sgd.cdt_data
            prefix = 'ID_SPECIAL_ATTACK_'
            desc = 'DESCRIPTION_'
            zero = '_0'
            one = '_1'
            two = '_2'
            if prefix+self.mcocjson+one in words:
                s0 = words[prefix + self.mcocjson + zero]
                s1 = words[prefix + self.mcocjson + one]
                s2 = words[prefix + self.mcocjson + two]
                s0d = words[prefix + desc + self.mcocjson + zero]
                s1d = words[prefix + desc + self.mcocjson + one]
                s2d = words[prefix + desc + self.mcocjson + two]
                specials = (s0, s1, s2, s0d, s1d, s2d)
                return specials


    @property
    @validate_attr('prestige')
    def prestige(self):
        try:
            if self.prestige_data[self.star][self.rank-1] is None:
                return 0
        except KeyError:
            return 0
        return self.prestige_data[self.star][self.rank-1][self.sig]

    @property
    def has_prestige(self):
        return hasattr(self, 'prestige_data')

    @property
    @validate_attr('prestige')
    def max_prestige(self):
        cur_rank = self.rank
        if self.star == 5:
            rank = 3 if cur_rank < 4 else 4
        else:
            rank = self.star + 1
        self.update_attrs({'rank': rank})
        maxp = self.prestige
        self.update_attrs({'rank': cur_rank})
        return maxp

    @validate_attr('prestige')
    def get_prestige_arr(self, rank, sig_arr, star=4):
        row = ['{}r{}'.format(self.short, rank)]
        for sig in sig_arr:
            try:
                row.append(self.prestige_data[star][rank-1][sig])
            except:
                logger.error(rank, sig, self.prestige_data)
                raise
        return row

    # async def missing_sig_ad(self):
    #     em = discord.Embed(color=self.class_color,
    #             title='Signature Data is Missing')
    #     em.add_field(name=self.full_name,
    #             value='Contribute your data at http://discord.gg/BwhgZxk')
    #     await self.bot.say(embed=em)


##  I don't think delta maintains his Signature stuff anymore so I'll have to see if I can pull from autnmai

    # async def process_sig_description(self, data=None, quiet=False, isbotowner=False):
    #     sd = await self.retrieve_sig_data(data, isbotowner)
    #     try:
    #         ktxt = sd['kabam_text']
    #     except KeyError:
    #         raise exceptions.MissingKabamText
    #     if self.debug:
    #         dbg_str = ['Title:  ' + ktxt['title']['k']]
    #         dbg_str.append('Simple:  ' + ktxt['simple']['k'])
    #         dbg_str.append('Description Keys:  ')
    #         dbg_str.append('  ' + ', '.join(ktxt['desc']['k']))
    #         dbg_str.append('Description Text:  ')
    #         dbg_str.extend(['  ' + self._sig_header(d)
    #                         for d in ktxt['desc']['v']])
    #         await self.bot.say(chat.box('\n'.join(dbg_str)))

    #     await self._sig_error_code_handling(sd, raise_error=quiet)
    #     if self.sig == 0:
    #         return self._get_sig_simple(ktxt)

    #     sig_calcs = {}
    #     try:
    #         stats = sd['spotlight_trunc'][self.unique]
    #     except (TypeError, KeyError):
    #         stats = {}
    #     self.stats_missing = False
    #     x_arr = self._sig_x_arr(sd)
    #     for effect, ckey, coeffs in zip(sd['effects'], sd['locations'], sd['sig_coeff']):
    #         if coeffs is None:
    #             await self.bot.say("**Data Processing Error**")
    #             if not quiet:
    #                 await self.missing_sig_ad()
    #             return self._get_sig_simple(ktxt)
    #         y_norm = sumproduct(x_arr, coeffs)
    #         sig_calcs[ckey] = self._sig_effect_decode(effect, y_norm, stats)

    #     if self.stats_missing:
    #         await self.bot.say(('Missing Attack/Health info for '
    #                 + '{0.full_name} {0.star_str}').format(self))

    #     brkt_re = re.compile(r'{([0-9])}')
    #     fdesc = []
    #     for i, txt in enumerate(ktxt['desc']['v']):
    #         fdesc.append(brkt_re.sub(r'{{d[{0}-\1]}}'.format(i),
    #                     self._sig_header(txt)))
    #     if self.debug:
    #         await self.bot.say(chat.box('\n'.join(fdesc)))
    #     title, desc, sig_calcs = ktxt['title']['v'], '\n'.join(fdesc), sig_calcs
    #     try:
    #         desc.format(d=sig_calcs)
    #     except KeyError as e:
    #         raise SignatureSchemaError("'{}' key error at {}".format(
    #                 self.full_name, str(e)))
    #     return title, desc, sig_calcs

    # async def retrieve_sig_data(self, data, isbotowner):
    #     if data is None:
    #         try:
    #             sd = dataIO.load_json(local_files['signature'])[self.full_name]
    #         except KeyError:
    #             sd = self.init_sig_struct()
    #         except FileNotFoundError:
    #             if isbotowner:
    #                 await self.bot.say("**DEPRECIATION WARNING**  "
    #                         + "Couldn't load json file.  Loading csv files.")
    #             sd = self.get_sig_data_from_csv()
    #         cfile = 'sig_coeff_4star' if self.star < 5 else 'sig_coeff_5star'
    #         coeff = dataIO.load_json(local_files[cfile])
    #         try:
    #             sd.update(coeff[self.full_name])
    #         except KeyError:
    #             sd.update(dict(effects=[], locations=[], sig_coeff=[]))
    #     else:
    #         sd = data[self.full_name] if self.full_name in data else data
    #     return sd

    # async def _sig_error_code_handling(self, sd, raise_error=False):
    #     if 'error_codes' not in sd or sd['error_codes']['undefined_key']:
    #         if raise_error:
    #             raise MissingSignatureData
    #         await self.warn_bold_say('Champion Signature data is not defined')
    #         self.update_attrs(dict(sig=0))
    #     elif sd['error_codes']['no_curve']:
    #         if raise_error:
    #             raise InsufficientData
    #         await self.warn_bold_say('{} '.format(self.star_name_str)
    #                 + 'does not have enough data points to create a curve')
    #         self.update_attrs(dict(sig=0))
    #     elif sd['error_codes']['low_count']:
    #         if raise_error:
    #             raise LowDataWarning
    #         await self.warn_bold_say('{} '.format(self.star_name_str)
    #                 + 'has low data count.  Unknown estimate quality')
    #     elif sd['error_codes']['poor_fit']:
    #         if raise_error:
    #             raise PoorDataFit
    #         await self.warn_bold_say('{} '.format(self.star_name_str)
    #                 + 'has poor curve fit.  Data is known to contain errors.')

    # def _sig_x_arr(self, sig_dict):
    #     fit_type = sig_dict['fit_type'][0]
    #     if fit_type.startswith('lin'):
    #         x_var = float(self.sig)
    #     elif fit_type.startswith('log'):
    #         x_var = log(self.sig)
    #     else:
    #         raise AttributeError("Unknown fit_type '{}' for champion {}".format(
    #                 fit_type, self.full_name ))
    #     if fit_type.endswith('quad'):
    #         return x_var**2, x_var, 1
    #     elif fit_type.endswith('lin'):
    #         return x_var, 1
    #     else:
    #         raise AttributeError("Unknown fit_type '{}' for champion {}".format(
    #                 fit_type, self.full_name ))

    # def _sig_effect_decode(self, effect, y_norm, stats):
    #     if effect == 'raw':
    #         if y_norm.is_integer():
    #             calc = '{:.0f}'.format(y_norm)
    #         else:
    #             calc = '{:.2f}'.format(y_norm)
    #     elif effect == 'flat':
    #         calc = self.sig_per_str.format(
    #                 to_flat(y_norm, self.chlgr_rating), y_norm/100)
    #     elif effect == 'attack':
    #         if 'attack' not in stats:
    #             self.stats_missing = True
    #             calc = self.sig_raw_per_str.format(y_norm/100)
    #         else:
    #             calc = self.sig_per_str.format(
    #                     stats['attack'] * y_norm / 100, y_norm/100)
    #     elif effect == 'health':
    #         if 'health' not in stats:
    #             self.stats_missing = True
    #             calc = self.sig_raw_per_str.format(y_norm/100)
    #         else:
    #             calc = self.sig_per_str.format(
    #                     stats['health'] * y_norm / 100, y_norm/100)
    #     else:
    #         raise AttributeError("Unknown effect '{}' for {}".format(
    #                 effect, self.full_name))
    #     return calc

    # def _get_sig_simple(self, ktxt):
    #     return ktxt['title']['v'], ktxt['simple']['v'], None

    # def get_sig_data_from_csv(self):
    #     struct = self.init_sig_struct()
    #     coeff = self.get_sig_coeff()
    #     ekey = self.get_effect_keys()
    #     spotlight = self.get_spotlight()
    #     if spotlight and spotlight['attack'] and spotlight['health']:
    #         stats = {k:int(spotlight[k].replace(',',''))
    #                     for k in ('attack', 'health')}
    #     else:
    #         stats = {}
    #     struct['spotlight_trunc'] = {self.unique: stats}
    #     if coeff is None or ekey is None:
    #         return struct
    #     for i in map(str, range(6)):
    #         if not ekey['Location_' + i]:
    #             break
    #         struct['effects'].append(ekey['Effect_' + i])
    #         struct['locations'].append(ekey['Location_' + i])
    #         try:
    #             struct['sig_coeff'].append((float(coeff['ability_norm' + i]),
    #                   float(coeff['offset' + i])))
    #         except:
    #             struct['sig_coeff'] = None
    #     return struct

    # def init_sig_struct(self):
    #     return dict(effects=[], locations=[], sig_coeff=[],
    #             #spotlight_trunc={self.unique: stats},
    #             kabam_text=self.get_kabam_sig_text())

    # def get_kabam_sig_text(self, sigs=None, champ_exceptions=None):
    #     '''required for signatures to work correctly
    #     preamble
    #     title = titlekey,
    #     simplekey = preample + simple
    #     descriptionkey = preamble + desc,
    #     '''

    #     sgd = cogs.mcocTools.StaticGameData()
    #     mcocsig = self.mcocsig
    #     #print(mcocsig)
    #     title = self._TITLE
    #     #print(title)
    #     simple = self._SIMPLE
    #     #print(simple)
    #     desc = [key.strip() for key in self._DESC_LIST.split(',') if key.strip()]
    #     #print(self._DESC_LIST)

    #     # allow manual override of Kabam Keys
    #     champ_exceptions = champ_exceptions if champ_exceptions else {}
    #     keymap = sgd.cdt_data.new_child(champ_exceptions)
    #     return dict(title={'k': title, 'v': keymap[title]},
    #                 simple={'k': simple, 'v': keymap[simple]},
    #                 desc={'k': desc, 'v': [keymap[k] for k in desc]})


    # def get_sig_coeff(self):
    #     return get_csv_row(local_files['sig_coeff'], 'CHAMP', self.full_name)

    # def get_effect_keys(self):
    #     return get_csv_row(local_files['effect_keys'], 'CHAMP', self.full_name)

    # def get_spotlight(self, default=None):
    #     return get_csv_row(data_files['spotlight']['local'], 'unique',
    #             self.unique, default=default)

    def get_aliases(self):
        return '```{}```'.format(', '.join(self.alias_set))

    @staticmethod
    def _sig_header(str_data):
        hex_re = re.compile(r'\[[0-9a-f]{6,8}\](.+?)\[-\]', re.I)
        return '• ' + hex_re.sub(r'**\1**', str_data)
