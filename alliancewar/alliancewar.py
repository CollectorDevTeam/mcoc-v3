from redbot.core import commands, Config
import discord
import json
import requests
try:
    from .mcoc.common.pages_menu import PagesMenu
    print('PagesMenu loaded from mcoc Common')
except:
    from .pages_menu import PagesMenu
    print('PagesMenu loaded from alliancewar')

BASEPATH = 'https://raw.githubusercontent.com/JasonJW/mcoc-cogs/master/mcocMaps/data/'
ICON_SDF = 'https://raw.githubusercontent.com/JasonJW/mcoc-cogs/master/mcoc/data/sdf_icon.png'
COLLECTOR_ICON='https://raw.githubusercontent.com/JasonJW/mcoc-cogs/master/mcoc/data/cdt_icon.png'
JPAGS = 'http://www.alliancewar.com'
PATREON = 'https://patreon.com/collectorbot'
BOOSTDATA = requests.get('http://www.alliancewar.com/global/ui/js/boosts.json').text
BOOSTS = json.loads(BOOSTDATA)
PATHS = {'expert':{ 'color' :discord.Color.gold(),'title':'Expert','map':'', 'json':'','minis': [27,28,29,30,31,48,51,52,53,55], 'boss':[54]},
        'hard':{ 'color' :discord.Color.red(),'title':'Hard','map':'', 'json':'', 'minis': [48,51,52,53,55], 'boss':[54]},
        'challenger':{ 'color' :discord.Color.orange(),'title':'Challenger','map':'', 'json':'', 'minis': [27,28,29,30,31,48,51,52,53,55], 'boss':[54]},
        'intermediate':{ 'color' :discord.Color.blue(),'title':'Intermediate','map':'', 'json':'', 'minis': [48,51,52,53,55], 'boss':[54]},
        'advanced':{ 'color' :discord.Color.green(),'title':'Normal','map':'', 'json':'', 'minis': [], 'boss':[]},
        'normal':{ 'color' :discord.Color.green(),'title':'Normal','map':'', 'json':'', 'minis': [], 'boss':[]},
        'easy':{ 'color' :discord.Color.green(),'title':'Easy','map':'', 'json':'', 'minis': [], 'boss':[]}}
for p in PATHS.keys():
    if p == 'normal' or p == 'easy':
        PATHS[p]['map'] = '{}warmap_{}_{}.png'.format(BASEPATH, 3, 'advanced')
        pathurl ='http://www.alliancewar.com/aw/js/aw_s{}_{}_9path.json'.format(2, 'advanced')
        pathdata = requests.get(pathurl)
    else:
        PATHS[p]['map'] = '{}warmap_{}_{}.png'.format(BASEPATH, 3, p)
        pathurl ='http://www.alliancewar.com/aw/js/aw_s{}_{}_9path.json'.format(2, p)
        pathdata = requests.get(pathurl)
    if pathdata.status_code==200:
        PATHS[p]['json'] = json.loads(pathdata.text)
    else:
        print('INVALID URL: '+pathurl)

AW_PATHS={
    'bosskill': {
        'A':[1,2,19,25,46,49,50,53],
        'B':[],
        'C':[3,21,27,41,45,47,51],
        'D':[11,17,22,28,34,36,48],
        'E':[],
        'F':[12,18,24,30,35,37,48],
        'G':[4,7,13,14,31,38,42,52],
        'H':[],
        'I':[6,9,15,14,33,40,44,55]
    },
    'expert':{
        'A':[1,19,25,46,49,50,53],
        'B':[1,2,19,20,26,41,45,47],
        'C':[3,21,27,41,45,47,51],
        'D':[11,17,22,28,34,36,48],
        'E':[10,16,23,29,48],
        'F':[12,18,24,30,35,37,48],
        'G':[4,7,13,14,31,38,42,52],
        'H':[5,8,14,32,39,43,55],
        'I':[6,9,15,14,33,40,44,55]
    },
}

class AllianceWar:
    """Collector integration for JPAGS' AllianceWar.com."""

    def __init__(self):
        self.config = Config.get_conf(self, identifier=1234512345)
        default_global = {
        }

        default_guild = {
            'officer': None,
            'bg1': None,
            'bg2': None,
            'bg3': None,
            'tier': 'Expert'
        }

        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    @commands.group(pass_context=True, aliases=['aw',])
    async def alliancewar(self, ctx):
        ''' Commands [WIP]'''

    @alliancewar.group(pass_context=True, manage_guild=True, name='set') # assuming Officers are allowed to manage guild
    async def _aw_set(self, ctx):
        '''Alliance Settings'''

    @_aw_set.command(pass_context=True, name='tier')
    async def _aw_set_tier(self, ctx, tier):
        '''Set default Alliance War Tier'''
        if tier in PATHS.keys():
            await self.config.guild(ctx.guild).tier.set(tier)
            await ctx.send('Alliance War Tier for this guild set to {}'.format(tier))

    @_aw_set.command(pass_context=True, name='officers')
    async def _aw_set_officers(self, ctx, officers):
        '''Set default Alliance Officer role'''
        await self.config.guild(ctx.guild).officers.set(officers)
        await ctx.send('Alliance Officer Role for this guild set to {}'.format(self.config.guild.officers().name))

    @alliancewar.command(pass_context=True, name='report')
    async def _report(self, ctx):
        officers = self.config.guild.officers()#.name
        bg1 = self.config.guild.bg1()#.name
        bg2 = self.config.guild.bg2()#.name
        bg3 = self.config.guild.bg3()#.name
        ctx.send('```officer role: {}```'.format(officers))#\nbg1 role:     {}\nbg2 role:     {}\nbg3 role:     {}\n```'.format(officers))#.name, bg1.name, bg2.name, bg3.name))


    @alliancewar.command(pass_context=True, name="node")
    async def _node_info(self, ctx, nodeNumber, tier = 'expert'):
        '''Report Alliance War node information.'''
        if tier in {'expert','hard','challenger','intermediate','normal','easy'}:
            em = await self.get_awnode_details(ctx = ctx, nodeNumber=nodeNumber,tier=tier) #, season=season)
            await ctx.send(embed=em)
        else:
            await ctx.send('Valid tiers include: advanced, intermediate, challenger, hard, expert')

    @alliancewar.command(pass_context=True, name="map")
    async def _map(self, ctx, tier = 'expert'):
        '''Report AW track information.'''
        if tier.lower() in PATHS.keys():
            if tier.lower()=='advanced' or tier.lower()=='easy':
                tier ='normal'
            mapTitle = 'Alliance War 3.0 Normal Map'.format(tier.title())
        else:
            tier = 'expert'
            mapTitle = 'Alliance War 3.0 {} Map'.format(PATHS[tier]['title'])
        em = discord.Embed(color=PATHS[tier]['color'],title=mapTitle,url=PATREON)
        em.set_image(url=PATHS[tier]['map'])
        em.set_footer(text='CollectorDevTeam',icon_url=COLLECTOR_ICON)
        await ctx.send(embed=em)

    @alliancewar.command(pass_context=True, name="path", aliases=('tracks','track','paths'))
    async def _path_info(self, ctx, track='A', tier = 'expert'):
        '''Report AW track information.
        Tracks are labeled A - I from left to right.'''
        # tracks = {'A':1,'B':2,'C':3,'D':4,'E':5,'F':6,'G':7,'H':8,'I':9}
        tracks = ['A','B','C','D','E','F','G','H','I']
        if tier in AW_PATHS:
            paths = AW_PATHS[tier]
        else:
            paths = AW_PATHS['expert']
        if track in tracks:
            path = paths[track]
        else:
            path = paths[tracks[track]]
        page_list = []
        print('alliancewar _path_info debug: {}'.format(path))
        title='{} Track {} Summary'.format(PATHS[tier]['title'],track)
        emSummary = discord.Embed(color=PATHS[tier]['color'], title=title, descritpion='', url=JPAGS)
        emSummary.set_image(url=PATHS[tier]['map'])

        pathdata = PATHS[tier]['json']
        for nodeNumber in path:
            em = await self.get_awnode_details(ctx = ctx, nodeNumber=nodeNumber,tier=tier) #, season=season)
            em.set_image(url=PATHS[tier]['map'])
            page_list.append(em)
            #
            # if int(nodeNumber) in PATHS[tier]['minis']:
            #     title='{} Node {} MINIBOSS Boosts'.format(PATHS[tier]['title'],nodeNumber)
            # elif int(nodeNumber) in PATHS[tier]['boss']:
            #     title='{} Node {} BOSS Boosts'.format(PATHS[tier]['title'],nodeNumber)
            # else:
            #

            nodedetails = pathdata['boosts'][str(nodeNumber)]
            boostvalues=[]
            for n in nodedetails:
                boosttitle, text = '','No description. Report to @jpags#5202'
                if ':' in n:
                    nodename, bump = n.split(':')
                else:
                    nodename = n
                    bump = 0
                if nodename in BOOSTS:
                    boostvalues.append(BOOSTS[nodename]['title'])

            emSummary.add_field(name='Tile {}',value=', '.join(boostvalues))
        page_list.insert(0,emSummary)
        # menu = PagesMenu(ctx)
        # await menu.menu_start(page_list)
        await PagesMenu.menu_start(ctx, page_list)


#####
#
# Utility functions for Alliance War
#
####
    async def get_awnode_details(self, ctx, nodeNumber, tier): #, season):
        pathdata = PATHS[tier]['json']
        if int(nodeNumber) in PATHS[tier]['minis']:
            title='{} Node {} MINIBOSS Boosts'.format(PATHS[tier]['title'],nodeNumber)
        elif int(nodeNumber) in PATHS[tier]['boss']:
            title='{} Node {} BOSS Boosts'.format(PATHS[tier]['title'],nodeNumber)
        else:
            title='{} Node {} Boosts'.format(PATHS[tier]['title'],nodeNumber)
        em = discord.Embed(color=PATHS[tier]['color'], title=title, descritpion='', url=JPAGS)
        nodedetails = pathdata['boosts'][str(nodeNumber)]
        for n in nodedetails:
            title, text = '','No description. Report to @jpags#5202'
            if ':' in n:
                nodename, bump = n.split(':')
            else:
                nodename = n
                bump = 0
            if nodename in BOOSTS:
                title = BOOSTS[nodename]['title']
                if BOOSTS[nodename]['text'] is not '':
                    text = BOOSTS[nodename]['text']
                    print('nodename: {}\ntitle: {}\ntext: {}'.format(nodename, BOOSTS[nodename]['title'], BOOSTS[nodename]['text']))
                    if bump is not None:
                        try:
                            text = text.format(bump)
                        except:  #wrote specifically for limber_percent
                            text = text.replace('}%}','}%').format(bump)  #wrote specifically for limber_percent
                        print('nodename: {}\ntitle: {}\nbump: {}\ntext: {}'.format(nodename, BOOSTS[nodename]['title'], bump, BOOSTS[nodename]['text']))
                    else:
                        text = 'Description text is missing from alliancwar.com.  Report to @jpags#5202.'
                else:
                    title = 'Error: {}'.format(nodename)
                    text = 'Boost details for {} missing from alliancewar.com.  Report to @jpags#5202.'.format(nodename)
            em.add_field(name=title, value=text, inline=False)
        em.set_footer(icon_url=JPAGS+'/aw/images/app_icon.jpg',text='AllianceWar.com')
        return em
