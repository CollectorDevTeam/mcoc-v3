from .abc import MixinMeta
import json
import re

    
class FetchData(MixinMeta):
    """CDT FetchData functions"""
    ## No cog dependencies##

    # def __init__(self, bot: Red):
    #     """init"""
    #     self.bot = bot
        

    async def aiohttp_http_to_text(ctx, url):
        """pull text from url, return pretty string"""
        result = None
        async with MixinMeta.session.get(url) as response:
            if response.status != 200:
                await ctx.send("Response Status: {response.status}")
            filetext = await response.text()
            filetext = FetchData.bcg_recompile(filetext) #cleanup the [15fkas] stuff
            prettytext = FetchData.prettyprint(filetext)
            if prettytext is not None:
                return prettytext
            else:
                return filetext

    async def aiohttp_http_to_json(ctx, url):
        """pull text from url, return pretty json"""
        result = None
        async with MixinMeta.session.get(url) as response:
            if response.status != 200:
                await ctx.send("Response Status: {response.status}")
            filetext = await response.text()
            filetext = FetchData.bcg_recompile(filetext)
            prettytext = FetchData.prettyprint(filetext)
            jsonfile = json.loads(prettytext)
            return jsonfile

    async def convert_kabamfile_to_json(ctx, kabamjson):
        """Convert Kabam's lists of k, v & vn to k: {v, vn}"""
        # stringlist = kabamfile["strings"].keys() #list of strings
        if isinstance(kabamjson, dict):
            next
        elif isinstance(kabamjson, str):
            kabamjson = json.loads(kabamjson)
        else:
            await ctx.send("dbg: kabam_to_json - not str or dict")
            return None
        snapshot_file = {"meta": {}, "strings": {}}
        snapshot_file["meta"].update(kabamjson["meta"])
        await ctx.send("dbg: text_to_json metacheck{}".format(snapshot_file["meta"]))
        stringlist = kabamjson["strings"]
        strings = {}
        for item in stringlist:
            if "vn" in item:
                vn = item["vn"]
                if isinstance(vn, int): #unlikely, but they might do it
                    vn = str(vn)
            else:
                vn = "0.0.0"
            pkg = {item["k"] : {"v": item["v"], "vn": vn}}
            print(pkg)
            strings.update(pkg)
        snapshot_file["strings"].update(strings)
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

    
    def bcg_recompile(str_data):
        """Scrape out the color decorators from Kabam JSON file"""
        hex_re = re.compile(r'\[[0-9a-f]{6,8}\](.+?)\[-\]', re.I)
        return hex_re.sub(r'**\1**', str_data)
