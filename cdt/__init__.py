from redbot.core.bot import Red
from .cdtcog import CDT_Cog as CDT
from pathlib import Path
import json

with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]

def setup(bot: Red):
    bot.add_cog(CDT(bot))
