from .cdtembed import Embed
from .fetch_data import FetchData
from .cdtcheck import CdtCheck
from .mcoc_math import McocMath
from .gsheet_data import GoogleSheets
from .cdtmenu import CdtMenu
from .discord_assets import Emoji, Branding, CDTColor

class CDT(CDTColor, CdtMenu, Branding, Embed, FetchData, CdtCheck, McocMath, Emoji, GoogleSheets):
    """Joining core subclasses"""