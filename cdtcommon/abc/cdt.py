from cdtcommon.abc.abc import MixinMeta
from cdtcommon.abc.cdtembed import Embed
from cdtcommon.abc.cdtcheck import CdtCheck
from cdtcommon.abc.fetch_data import FetchData
from cdtcommon.abc.common import CommonFunctions

       
class CDT(CommonFunctions, Embed, FetchData, CdtCheck, MixinMeta):
    """will this work?"""